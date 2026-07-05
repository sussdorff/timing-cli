"""Decode and apply Timing.app project predicate rules.

Timing stores project auto-assignment predicates as a protobuf-like binary wire
format in ``Project.predicate``. The format is undocumented, so the decoder here
is intentionally conservative: it extracts recognized field/value conditions and
ignores unknown structure.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass

from timing_cli.models import AppUsage

RECOGNIZED_FIELDS = {
    "applicationID",
    "bundleIdentifier",
    "executable",
    "filePath",
    "keywords",
    "path",
    "title",
    "webDomain",
}

MIN_TEXT_MATCH_LENGTH = 3


@dataclass(frozen=True)
class TimingPredicateCondition:
    field: str
    values: tuple[str, ...] = ()
    int_values: tuple[int, ...] = ()

    def matches(self, usage: AppUsage) -> bool:
        if self.field == "applicationID":
            return usage.application_id in self.int_values

        haystacks = _haystacks_for_field(self.field, usage)
        if not haystacks:
            return False
        if self.field == "keywords":
            return any(
                _keyword_matches(value, haystack)
                for value in self.values
                for haystack in haystacks
            )
        return any(
            _text_value_matches(value, haystack)
            for value in self.values
            for haystack in haystacks
        )


@dataclass(frozen=True)
class TimingPredicateRule:
    project_id: int
    project_title: str
    project_title_chain: tuple[str, ...]
    conditions: tuple[TimingPredicateCondition, ...]

    def matches(self, usage: AppUsage) -> bool:
        return any(condition.matches(usage) for condition in self.conditions)


def decode_timing_predicate(blob: bytes | None) -> tuple[TimingPredicateCondition, ...]:
    """Extract recognized conditions from a Timing predicate blob."""
    if not blob:
        return ()

    conditions: list[TimingPredicateCondition] = []
    seen: set[TimingPredicateCondition] = set()
    for condition in _extract_conditions(blob):
        if condition not in seen:
            conditions.append(condition)
            seen.add(condition)
    return tuple(conditions)


def _haystacks_for_field(field: str, usage: AppUsage) -> tuple[str, ...]:
    if field == "applicationID":
        return ()
    if field == "bundleIdentifier":
        values = (usage.bundle_id,)
    elif field in {"filePath", "path"}:
        values = (usage.path, usage.title)
    elif field == "executable":
        values = (usage.app, usage.bundle_id)
    else:
        values = (usage.title, usage.path, usage.app, usage.bundle_id)
    return tuple(value.lower() for value in values if value)


def _keyword_matches(value: str, haystack: str) -> bool:
    keyword = value.strip().lower()
    if len(keyword) < MIN_TEXT_MATCH_LENGTH:
        return False
    if not re.search(r"\w", keyword):
        return False
    if re.search(r"\s", keyword):
        return keyword in haystack
    return re.search(rf"(?<!\w){re.escape(keyword)}(?!\w)", haystack) is not None


def _text_value_matches(value: str, haystack: str) -> bool:
    needle = value.strip().lower()
    if len(needle) < MIN_TEXT_MATCH_LENGTH:
        return False
    if not re.search(r"\w", needle):
        return False
    if re.search(r"\s", needle):
        return needle in haystack
    return re.search(rf"(?<!\w){re.escape(needle)}(?!\w)", haystack) is not None


def _extract_conditions(data: bytes) -> Iterator[TimingPredicateCondition]:
    try:
        fields = list(_decode_fields(data))
    except ValueError:
        return

    field_names: list[str] = []
    text_values: list[str] = []
    int_values: list[int] = []

    for field_number, wire_type, value in fields:
        if wire_type != 2 or not isinstance(value, bytes):
            continue
        if field_number == 3:
            field_names.extend(_recognized_strings(value))
        elif field_number == 4:
            text_values.extend(_value_strings(value))
            int_values.extend(_value_ints(value))

    for field_name in field_names:
        if field_name == "applicationID":
            values = tuple(v for v in int_values if v >= 0)
            if values:
                yield TimingPredicateCondition(field_name, int_values=values)
        else:
            values = tuple(_dedupe(text_values))
            if values:
                yield TimingPredicateCondition(field_name, values=values)

    for _field_number, wire_type, value in fields:
        if wire_type == 2 and isinstance(value, bytes):
            yield from _extract_conditions(value)


def _decode_fields(data: bytes) -> Iterator[tuple[int, int, int | bytes]]:
    index = 0
    while index < len(data):
        key, index = _read_varint(data, index)
        field_number = key >> 3
        wire_type = key & 0x07
        if field_number == 0:
            raise ValueError("invalid protobuf field number")

        if wire_type == 0:
            value, index = _read_varint(data, index)
            yield field_number, wire_type, value
        elif wire_type == 2:
            length, index = _read_varint(data, index)
            end = index + length
            if end > len(data):
                raise ValueError("length-delimited field exceeds message")
            yield field_number, wire_type, data[index:end]
            index = end
        else:
            raise ValueError(f"unsupported protobuf wire type: {wire_type}")


def _read_varint(data: bytes, index: int) -> tuple[int, int]:
    shift = 0
    value = 0
    while index < len(data):
        byte = data[index]
        index += 1
        value |= (byte & 0x7F) << shift
        if not byte & 0x80:
            return value, index
        shift += 7
        if shift > 63:
            raise ValueError("varint too large")
    raise ValueError("truncated varint")


def _recognized_strings(data: bytes) -> list[str]:
    return [value for value in _protobuf_text_values(data) if value in RECOGNIZED_FIELDS]


def _value_strings(data: bytes) -> list[str]:
    values: list[str] = []
    for value in _protobuf_text_values(data):
        normalized = value.strip()
        if normalized in RECOGNIZED_FIELDS:
            continue
        if len(normalized) < MIN_TEXT_MATCH_LENGTH:
            continue
        if not re.search(r"\w", normalized):
            continue
        values.append(normalized)
    return values


def _value_ints(data: bytes) -> list[int]:
    ints: list[int] = []
    try:
        fields = list(_decode_fields(data))
    except ValueError:
        return ints

    for _field_number, wire_type, value in fields:
        if wire_type == 0 and isinstance(value, int):
            ints.append(value)
        elif wire_type == 2 and isinstance(value, bytes):
            ints.extend(_value_ints(value))
    return ints


def _protobuf_text_values(data: bytes) -> list[str]:
    values: list[str] = []
    text = _decode_text_value(data)
    if text is not None:
        values.append(text)

    try:
        fields = list(_decode_fields(data))
    except ValueError:
        return values

    for _field_number, wire_type, value in fields:
        if wire_type == 2 and isinstance(value, bytes):
            values.extend(_protobuf_text_values(value))
    return list(_dedupe(values))


def _decode_text_value(data: bytes) -> str | None:
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return None
    if not text:
        return None
    if any(ord(char) < 32 or ord(char) == 127 for char in text):
        return None
    return text


def _dedupe(values: list[str]) -> Iterator[str]:
    seen: set[str] = set()
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        yield value

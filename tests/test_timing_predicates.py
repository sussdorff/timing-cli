from __future__ import annotations

from datetime import datetime

from timing_cli.models import AppUsage
from timing_cli.rules import Classifier
from timing_cli.timing_predicates import TimingPredicateRule, decode_timing_predicate


def _varint(value: int) -> bytes:
    out = bytearray()
    while value >= 0x80:
        out.append((value & 0x7F) | 0x80)
        value >>= 7
    out.append(value)
    return bytes(out)


def _field(field_number: int, value: bytes | int) -> bytes:
    if isinstance(value, int):
        return _varint(field_number << 3) + _varint(value)
    return _varint((field_number << 3) | 2) + _varint(len(value)) + value


def test_decode_timing_predicate_extracts_string_condition():
    blob = _field(3, b"webDomain") + _field(4, b"jira.example.test")

    conditions = decode_timing_predicate(blob)

    assert len(conditions) == 1
    assert conditions[0].field == "webDomain"
    assert conditions[0].values == ("jira.example.test",)


def test_decode_timing_predicate_extracts_application_id_condition():
    blob = _field(3, b"applicationID") + _field(4, _field(2, 582))

    conditions = decode_timing_predicate(blob)

    assert len(conditions) == 1
    assert conditions[0].field == "applicationID"
    assert conditions[0].int_values == (582,)


def test_classifier_applies_timing_predicate_rules_after_config_rules():
    timing_rule = TimingPredicateRule(
        project_id=7,
        project_title="Cognovis",
        project_title_chain=("Client", "Cognovis"),
        conditions=decode_timing_predicate(_field(3, b"webDomain") + _field(4, b"jira")),
    )
    usage = AppUsage(
        id=1,
        start=datetime(2026, 7, 5, 9, 0).astimezone(),
        end=datetime(2026, 7, 5, 9, 30).astimezone(),
        app="Zen",
        title="jira.example.test",
    )

    classification = Classifier([], timing_rules=[timing_rule]).classify(usage)

    assert classification.project_id == 7
    assert classification.project_title == "Cognovis"
    assert classification.source == "timing_predicate"
    assert classification.project_title_chain == ("Client", "Cognovis")


def test_keyword_predicates_do_not_match_inside_words_or_short_tokens():
    short_rule = TimingPredicateRule(
        project_id=1,
        project_title="Home Electronic",
        project_title_chain=("Home Electronic",),
        conditions=decode_timing_predicate(_field(3, b"keywords") + _field(4, b"pi")),
    )
    word_rule = TimingPredicateRule(
        project_id=2,
        project_title="UniFi",
        project_title_chain=("UniFi",),
        conditions=decode_timing_predicate(_field(3, b"keywords") + _field(4, b"unifi")),
    )

    assert not short_rule.matches(
        AppUsage(
            id=1,
            start=datetime(2026, 7, 5, 9, 0).astimezone(),
            end=datetime(2026, 7, 5, 9, 30).astimezone(),
            app="cmux",
            title="INFO Gruppierung",
        )
    )
    assert word_rule.matches(
        AppUsage(
            id=2,
            start=datetime(2026, 7, 5, 9, 0).astimezone(),
            end=datetime(2026, 7, 5, 9, 30).astimezone(),
            app="Zen",
            title="UniFi Network",
        )
    )

from __future__ import annotations

from datetime import datetime

from timing_cli.models import AppUsage
from timing_cli.rules import Classifier
from timing_cli.timing_predicates import TimingPredicateRule, decode_timing_predicate

CONTAINER_SUPPORT_PREDICATE_HEX = (
    "0aec010802122e122c08041a0822060a0470617468221a0a180a16636f6e7461696e657220"
    "496e7374616c6c6174696f6e2a0201021233123108081a0822060a0470617468221f0a"
    "1d0a1b636f6e7461696e657220496e7374616c6c6174696f6e20e296b8202a020102"
    "123e123c08041a0822060a0470617468222a0a280a265465616d7320756e64204b"
    "616ec3a46c6520e296b820436f6e7461696e6572205570646174652a0201021243"
    "124108081a0822060a0470617468222f0a2d0a2b5465616d7320756e64204b616e"
    "c3a46c6520e296b820436f6e7461696e65722055706461746520e296b8202a020102"
)


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


# Regression guard for a real Timing predicate blob whose UTF-8 values were
# previously split by ASCII scavenging, leaking protobuf framing bytes.
def test_regression_real_timing_predicate_decodes_utf8_leaf_strings_without_framing():
    blob = bytes.fromhex(CONTAINER_SUPPORT_PREDICATE_HEX)
    conditions = decode_timing_predicate(blob)
    values = [value for condition in conditions for value in condition.values]

    assert "Teams und Kan\u00e4le \u25b8 Container Update" in values
    assert "Teams und Kan\u00e4le \u25b8 Container Update \u25b8" in values
    assert "le" not in values
    assert all(not value.startswith(("&", "+", '"')) for value in values)

    rule = TimingPredicateRule(
        project_id=3,
        project_title="Container Support",
        project_title_chain=("Container Support",),
        conditions=conditions,
    )

    assert not rule.matches(
        AppUsage(
            id=3,
            start=datetime(2026, 7, 5, 9, 0).astimezone(),
            end=datetime(2026, 7, 5, 9, 30).astimezone(),
            app="Google Chrome",
            title="Google Chrome",
        )
    )


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


def test_generic_predicates_use_minimum_length_and_word_boundaries():
    short_rule = TimingPredicateRule(
        project_id=1,
        project_title="Too Broad",
        project_title_chain=("Too Broad",),
        conditions=decode_timing_predicate(_field(3, b"path") + _field(4, b"le")),
    )
    word_rule = TimingPredicateRule(
        project_id=2,
        project_title="Files",
        project_title_chain=("Files",),
        conditions=decode_timing_predicate(_field(3, b"path") + _field(4, b"file")),
    )

    profile_usage = AppUsage(
        id=3,
        start=datetime(2026, 7, 5, 9, 0).astimezone(),
        end=datetime(2026, 7, 5, 9, 30).astimezone(),
        app="Finder",
        title="profile settings",
    )
    file_usage = AppUsage(
        id=4,
        start=datetime(2026, 7, 5, 9, 0).astimezone(),
        end=datetime(2026, 7, 5, 9, 30).astimezone(),
        app="Finder",
        title="file settings",
    )

    assert not short_rule.matches(file_usage)
    assert not word_rule.matches(profile_usage)
    assert word_rule.matches(file_usage)

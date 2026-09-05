"""Tests for the packaged default Cognovis classification ruleset.

These tests don't need the live Timing database: they exercise
``DEFAULT_COGNOVIS_RULES`` directly against synthetic ``AppUsage`` slices, and
``load_config`` against temporary config files.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

from timing_cli.config import Config, Rule, load_config
from timing_cli.default_rules import DEFAULT_COGNOVIS_RULES
from timing_cli.models import AppUsage
from timing_cli.rules import UNASSIGNED, Classifier

BASE = datetime(2026, 7, 5, 9, 0, 0).astimezone()


def _slice(
    offset_min: float,
    dur_min: float,
    app: str,
    title: str = "",
    path: str | None = None,
) -> AppUsage:
    start = BASE + timedelta(minutes=offset_min)
    return AppUsage(
        id=int(offset_min * 100),
        start=start,
        end=start + timedelta(minutes=dur_min),
        app=app,
        title=title,
        path=path,
    )


def _classify(usage: AppUsage) -> str:
    return Classifier(DEFAULT_COGNOVIS_RULES).classify(usage).project_title


# --- Individual rule coverage -----------------------------------------------


def test_cmux_polaris_title_maps_to_mira():
    usage = _slice(0, 30, "cmux", title="Polaris DeID pipeline review")
    assert _classify(usage) == "MIRA"


def test_mira_path_maps_to_mira():
    usage = _slice(0, 30, "Cursor", title="untitled", path="/Users/malte/code/mira/src/app.tsx")
    assert _classify(usage) == "MIRA"


def test_repo_path_cli_tools_maps_to_cognovis_verwaltung():
    usage = _slice(
        0,
        30,
        "Cursor",
        title="config.py",
        path="/Users/malte/code/cli-tools/timing-cli/timing_cli/config.py",
    )
    assert _classify(usage) == "cognovis Verwaltung"


def test_generic_cmux_leftover_maps_to_cognovis_verwaltung():
    usage = _slice(0, 30, "cmux", title="cmux")
    assert _classify(usage) == "cognovis Verwaltung"


def test_specific_client_title_syntegon():
    usage = _slice(0, 30, "cmux", title="Kickoff Syntegon roadmap")
    assert _classify(usage) == "Syntegon"


def test_specific_client_title_romelag():
    usage = _slice(0, 30, "Slack", title="Romelag standup notes")
    assert _classify(usage) == "Romelag"


def test_short_acronym_client_uses_word_boundary():
    assert _classify(_slice(0, 30, "cmux", title="ATR status update")) == "ATR"
    # Word-boundary regex must not match "atr" inside an unrelated word.
    assert _classify(_slice(0, 30, "Safari", title="theatre tickets")) == UNASSIGNED


def test_project_open_matches_title_and_path():
    assert _classify(_slice(0, 30, "Mail", title="]project-open[ new ticket")) == "]project-open["
    usage = _slice(0, 30, "Safari", title="", path="https://po.example.com/project-open/index")
    assert _classify(usage) == "]project-open["


def test_home_electronic_matches_path():
    usage = _slice(
        0,
        30,
        "Finder",
        title="README.md",
        path="/Users/malte/code/home-infra/README.md",
    )
    assert _classify(usage) == "Home Electronic"


def test_cognovis_verwaltung_title_keywords():
    usage = _slice(0, 30, "Cursor", title="config.py — timing-cli")
    assert _classify(usage) == "cognovis Verwaltung"


def test_client_rule_wins_over_cmux_catch_all():
    """Specific client rules must be ordered before the app=cmux catch-all."""
    usage = _slice(0, 30, "cmux", title="Kolibri sprint planning")
    assert _classify(usage) == "Kolibri"


def test_unmatched_stays_unassigned():
    usage = _slice(0, 30, "Safari", title="Random news article")
    assert _classify(usage) == UNASSIGNED


# --- Synthetic normal workday: >70% classified ------------------------------


def _normal_workday() -> list[AppUsage]:
    return [
        _slice(0, 90, "cmux", title="Polaris DeID pipeline review"),
        _slice(90, 45, "cmux", title="Kickoff Syntegon roadmap"),
        _slice(
            135,
            60,
            "Cursor",
            title="config.py — timing-cli",
            path="/Users/malte/code/cli-tools/timing-cli/timing_cli/config.py",
        ),
        _slice(195, 40, "cmux", title="cmux"),
        _slice(235, 20, "Mail", title="]project-open[ new ticket"),
        _slice(255, 60, "Safari", title="Hacker News frontpage"),
        _slice(
            315,
            20,
            "Finder",
            title="README.md",
            path="/Users/malte/code/home-infra/README.md",
        ),
        _slice(335, 15, "Slack", title="Romelag standup notes"),
        _slice(350, 30, "Terminal", title="random terminal session"),
    ]


def test_normal_workday_is_mostly_classified():
    classifier = Classifier(DEFAULT_COGNOVIS_RULES)
    usage = _normal_workday()
    total = sum(slice_.duration_seconds for slice_ in usage)
    unassigned = sum(
        slice_.duration_seconds
        for slice_ in usage
        if classifier.classify(slice_).project_title == UNASSIGNED
    )
    classified_ratio = (total - unassigned) / total
    assert classified_ratio > 0.70, f"only {classified_ratio:.1%} classified"


# --- Wiring through Config / load_config ------------------------------------


def test_use_default_rules_defaults_to_true():
    assert Config().use_default_rules is True


def test_load_config_with_no_file_still_gets_defaults(tmp_path: Path):
    cfg = load_config(tmp_path / "does-not-exist.toml")
    assert cfg.use_default_rules is True
    assert cfg.rules == DEFAULT_COGNOVIS_RULES


def test_load_config_appends_defaults_after_user_rules(tmp_path: Path):
    cfg_path = tmp_path / "config.toml"
    cfg_path.write_text(
        """
[[rules]]
project = "My Own Project"
title = "myproject"
"""
    )
    cfg = load_config(cfg_path)
    assert cfg.rules[0] == Rule(project="My Own Project", title="myproject")
    assert cfg.rules[1:] == DEFAULT_COGNOVIS_RULES


def test_load_config_use_default_rules_false_disables_defaults(tmp_path: Path):
    cfg_path = tmp_path / "config.toml"
    cfg_path.write_text(
        """
use_default_rules = false

[[rules]]
project = "My Own Project"
title = "myproject"
"""
    )
    cfg = load_config(cfg_path)
    assert cfg.use_default_rules is False
    assert cfg.rules == [Rule(project="My Own Project", title="myproject")]


def test_user_rule_wins_over_default_when_earlier_in_list(tmp_path: Path):
    """User rules are placed first, so they win over a default MIRA match."""
    cfg_path = tmp_path / "config.toml"
    cfg_path.write_text(
        """
[[rules]]
project = "Custom Polaris Bucket"
title = "polaris"
"""
    )
    cfg = load_config(cfg_path)
    classifier = Classifier(cfg.rules)
    usage = _slice(0, 30, "cmux", title="Polaris something")
    assert classifier.classify(usage).project_title == "Custom Polaris Bucket"

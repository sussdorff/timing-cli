from __future__ import annotations

import sys
import subprocess
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_DIR = REPO_ROOT / "skills" / "bead-reviewer" / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

import finding_rules  # noqa: E402


def test_registry_and_dynamic_contract_rules_are_the_only_allowed_rule_ids() -> None:
    registered = finding_rules.registered_rule_ids()

    assert "REPO-PATH-STALE" in registered
    assert "ADHOC-UNCLASSIFIED" in registered
    assert "SPEC-MOC-NONCONCRETE" not in registered
    assert finding_rules.allowed_rule_ids(
        [{"rule_id": "BASE-MOC-CONCRETE"}]
    ) == registered | {"BASE-MOC-CONCRETE"}


def test_recurring_cross_cutting_classes_are_registered() -> None:
    """Existence/gate-membership regression for classes promoted in clc-ew7m.

    Scope of this test: it proves only that each promoted class is a registered
    aggregation key and passes the reviewer's rule-id gate (`allowed_rule_ids`)
    without needing a contract rule. It does NOT prove correct classification
    behavior, disambiguation from neighboring classes, or any reduction in the
    ADHOC-UNCLASSIFIED rate. That is an empirical property measured by a
    re-review pass over a live cohort, not by unit membership.

    These are repository-, graph-, and decision-aware patterns the static
    hygiene contract cannot express. Contract-expressible patterns (e.g.
    BASE-SCOPE-EPIC) deliberately stay out of the registry and are supplied by
    the resolved contract instead.
    """
    registered = finding_rules.registered_rule_ids()
    # allowed_rule_ids([]) is the reviewer's gate with no contract rules: a
    # finding may use any registered key even when the resolved contract adds none.
    gated = finding_rules.allowed_rule_ids([])

    for rule_id in (
        "DECISION-PREMISE-STALE",
        "SPEC-BEHAVIOR-UNDEFINED",
        "SPEC-IMPL-SURFACE-UNBOUND",
        "STRUCTURE-GRAPH-DRIFT",
        "STRUCTURE-MISSING-DEPENDENCY",
        "STRUCTURE-PARENT-SCOPE-CONFLICT",
        "TYPE-DEFECT-MISCLASSIFIED",
    ):
        assert rule_id in registered, rule_id
        assert rule_id in gated, rule_id


def test_finding_id_is_deterministic_and_evidence_bound() -> None:
    baseline = finding_rules.build_finding_id(
        rule_id="REPO-PATH-STALE",
        bead_id="clc-demo",
        criterion="repository",
        evidence=["src/b.py:2", "src/a.py:1", "src/a.py:1"],
    )

    reordered = finding_rules.build_finding_id(
        rule_id="REPO-PATH-STALE",
        bead_id="clc-demo",
        criterion="repository",
        evidence=[" src/a.py:1 ", "src/b.py:2"],
    )
    distinct_occurrence = finding_rules.build_finding_id(
        rule_id="REPO-PATH-STALE",
        bead_id="clc-demo",
        criterion="repository",
        evidence=["src/c.py:3"],
    )

    assert baseline == reordered
    assert baseline.startswith("REPO-PATH-STALE:clc-demo:")
    assert len(baseline.rsplit(":", 1)[1]) == 12
    assert distinct_occurrence != baseline


def test_identical_identity_inputs_define_one_occurrence() -> None:
    first = finding_rules.build_finding_id(
        rule_id="ADHOC-UNCLASSIFIED",
        bead_id="clc-demo",
        criterion="semantic",
        evidence=["bead:clc-demo#Intent"],
    )
    second = finding_rules.build_finding_id(
        rule_id="ADHOC-UNCLASSIFIED",
        bead_id="clc-demo",
        criterion="semantic",
        evidence=["bead:clc-demo#Intent"],
    )
    occurrence_specific = finding_rules.build_finding_id(
        rule_id="ADHOC-UNCLASSIFIED",
        bead_id="clc-demo",
        criterion="semantic",
        evidence=["bead:clc-demo#Acceptance-Criteria"],
    )

    assert first == second
    assert occurrence_specific != first


@pytest.mark.parametrize("rule_id", ["", "repo-path-stale", "REPO_PATH_STALE"])
def test_rule_ids_must_use_uppercase_kebab_case(rule_id: str) -> None:
    with pytest.raises(finding_rules.FindingRuleError, match="rule_id"):
        finding_rules.build_finding_id(
            rule_id=rule_id,
            bead_id="clc-demo",
            criterion="repository",
            evidence=["src/example.py:1"],
        )


def test_build_cli_emits_the_same_deterministic_id() -> None:
    expected = finding_rules.build_finding_id(
        rule_id="REPO-PATH-STALE",
        bead_id="clc-demo",
        criterion="repository",
        evidence=["src/example.py:1"],
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_DIR / "finding_rules.py"),
            "build",
            "--rule-id",
            "REPO-PATH-STALE",
            "--bead-id",
            "clc-demo",
            "--criterion",
            "repository",
            "--evidence",
            "src/example.py:1",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == expected

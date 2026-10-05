"""Finding triage keeps late review findings bounded to the admitted candidate."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import finding_triage  # noqa: E402


def _finding(**overrides):
    base = {
        "finding_id": "F1",
        "severity": "high",
        "paths": ["src/app/billing.py"],
        "ac_ref": "AC-1",
    }
    base.update(overrides)
    return base


DIFF = ["src/app/billing.py", "tests/test_billing.py"]


def test_medium_or_higher_in_diff_with_admitted_ac_enters_repair() -> None:
    result = finding_triage.triage_findings(
        [_finding()], diff_paths=DIFF, acceptance_refs=["AC-1"]
    )
    assert [f["finding_id"] for f in result["repair"]] == ["F1"]
    assert result["deferred"] == []
    assert result["repair_dispatch_authorized"] is True


def test_low_and_nit_findings_are_deferred() -> None:
    result = finding_triage.triage_findings(
        [_finding(severity="low"), _finding(finding_id="F2", severity="nit")],
        diff_paths=DIFF,
        acceptance_refs=["AC-1"],
    )
    assert result["repair"] == []
    assert {f["reason"] for f in result["deferred"]} == {"BELOW_MEDIUM"}


def test_medium_behaviour_finding_outside_the_diff_is_deferred() -> None:
    finding = _finding(
        paths=["src/legacy/other.py"], severity="medium", ac_ref="", candidate_behaviour=True
    )
    result = finding_triage.triage_findings([finding], diff_paths=DIFF, acceptance_refs=["AC-1"])
    assert result["repair"] == []
    assert result["deferred"][0]["reason"] == "OUTSIDE_PACK_DIFF"


def test_missing_case_outside_the_diff_bound_to_an_admitted_ac_enters_repair() -> None:
    # A file the change should have updated is by definition not in the diff.
    result = finding_triage.triage_findings(
        [_finding(paths=["src/legacy/other.py"])], diff_paths=DIFF, acceptance_refs=["AC-1"]
    )
    assert [f["finding_id"] for f in result["repair"]] == ["F1"]


def test_high_behaviour_finding_outside_the_diff_enters_repair() -> None:
    # A live caller the change breaks sits outside the diff.
    finding = _finding(paths=["src/caller.py"], ac_ref="", candidate_behaviour=True)
    result = finding_triage.triage_findings([finding], diff_paths=DIFF, acceptance_refs=["AC-1"])
    assert [f["finding_id"] for f in result["repair"]] == ["F1"]


def test_finding_without_paths_is_outside_the_diff() -> None:
    finding = _finding(paths=[], severity="medium", ac_ref="", candidate_behaviour=True)
    result = finding_triage.triage_findings([finding], diff_paths=DIFF, acceptance_refs=["AC-1"])
    assert result["deferred"][0]["reason"] == "OUTSIDE_PACK_DIFF"


def test_reviewer_brief_shape_is_accepted() -> None:
    """The executive-pack review brief asks for `id` and `ac`, with `own-behaviour`."""
    findings = [
        {"id": "O1", "severity": "high", "paths": ["src/app/billing.py"], "ac": "AC-1"},
        {"id": "S1", "severity": "medium", "paths": ["src/app/billing.py"], "ac": "own-behaviour"},
        {"id": "H1", "severity": "medium", "paths": ["src/app/billing.py"], "ac": "AC-9"},
    ]
    result = finding_triage.triage_findings(findings, diff_paths=DIFF, acceptance_refs=["AC-1"])
    assert [f["finding_id"] for f in result["repair"]] == ["O1", "S1"]
    assert [(f["finding_id"], f["reason"]) for f in result["deferred"]] == [
        ("H1", "NO_ADMITTED_SCOPE")
    ]


@pytest.mark.parametrize(
    "spelling", ["behaviour", "behavior", "own-behavior", "Own behaviour", "own_behavior"]
)
def test_own_behaviour_spelling_variants_are_not_dropped_as_unscoped(spelling: str) -> None:
    """A reviewer writing `behaviour` instead of `own-behaviour` must not lose a real finding."""
    result = finding_triage.triage_findings(
        [_finding(ac_ref=spelling, severity="high")], diff_paths=DIFF, acceptance_refs=["AC-1"]
    )
    assert [f["finding_id"] for f in result["repair"]] == ["F1"]
    assert result["deferred"] == []


def test_directory_level_finding_matches_changed_files_under_it() -> None:
    result = finding_triage.triage_findings(
        [_finding(paths=["src/app/"])], diff_paths=DIFF, acceptance_refs=["AC-1"]
    )
    assert [f["finding_id"] for f in result["repair"]] == ["F1"]


def test_finding_without_admitted_scope_is_deferred_unless_candidate_behaviour() -> None:
    unscoped = _finding(ac_ref="AC-9")
    behavioural = _finding(finding_id="F2", ac_ref="", candidate_behaviour=True)
    result = finding_triage.triage_findings(
        [unscoped, behavioural], diff_paths=DIFF, acceptance_refs=["AC-1"]
    )
    assert [f["finding_id"] for f in result["repair"]] == ["F2"]
    assert result["deferred"][0]["reason"] == "NO_ADMITTED_SCOPE"


def test_second_repair_round_is_refused_by_default() -> None:
    result = finding_triage.triage_findings(
        [_finding()], diff_paths=DIFF, acceptance_refs=["AC-1"], repair_rounds_used=1
    )
    assert result["repair"] == []
    assert result["deferred"][0]["reason"] == "REPAIR_ROUNDS_EXHAUSTED"
    assert result["repair_dispatch_authorized"] is False


def test_unknown_severity_and_duplicate_ids_are_typed_errors() -> None:
    with pytest.raises(finding_triage.FindingTriageError):
        finding_triage.triage_findings(
            [_finding(severity="blocker")], diff_paths=DIFF, acceptance_refs=[]
        )
    with pytest.raises(finding_triage.FindingTriageError):
        finding_triage.triage_findings([_finding(), _finding()], diff_paths=DIFF, acceptance_refs=[])


def test_cli_emits_json_envelope(tmp_path: Path) -> None:
    findings = tmp_path / "findings.json"
    findings.write_text(
        json.dumps({"findings": [_finding(), _finding(finding_id="F2", severity="low")]})
    )
    completed = subprocess.run(
        [
            sys.executable,
            str(SCRIPTS / "finding_triage.py"),
            "--findings-file",
            str(findings),
            "--diff-path",
            "src/app/billing.py",
            "--ac-ref",
            "AC-1",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    envelope = json.loads(completed.stdout)
    assert envelope["contract"] == finding_triage.CONTRACT
    assert [f["finding_id"] for f in envelope["repair"]] == ["F1"]
    assert envelope["deferred"][0]["finding_id"] == "F2"


def _local_review_findings() -> list[dict]:
    """Merged, deduplicated findings from the three local reviewers, in the brief's shape."""
    return [
        {
            "id": "R1",
            "severity": "high",
            "paths": ["src/app/billing.py"],
            "ac": "AC-1",
            "reviewer": "opus",
            "summary": "Refund path skips the lock.",
        },
        {
            "id": "R2",
            "severity": "low",
            "paths": ["src/app/billing.py"],
            "ac": "AC-1",
            "reviewer": "sonnet",
            "summary": "Name the retry constant.",
        },
        {
            "id": "R3",
            "severity": "medium",
            "paths": ["docs/unrelated.md"],
            "ac": "own-behaviour",
            "reviewer": "haiku",
            "summary": "Unrelated doc drift.",
        },
    ]


def test_deferred_findings_render_into_a_review_decisions_section() -> None:
    result = finding_triage.triage_findings(
        _local_review_findings(), diff_paths=DIFF, acceptance_refs=["AC-1"]
    )

    section = finding_triage.render_review_decisions(result["deferred"])

    assert [f["finding_id"] for f in result["repair"]] == ["R1"]
    assert section.startswith("## Review decisions\n")
    assert "`R2` (low, sonnet): Name the retry constant. -- deferred, below Medium severity." in section
    assert "`R3` (medium, haiku): Unrelated doc drift. -- deferred, outside the changed paths." in section
    assert "R1" not in section


def test_empty_deferred_set_renders_an_explicit_statement() -> None:
    section = finding_triage.render_review_decisions([])
    assert section == "## Review decisions\n\nNo local review finding was deferred.\n"


def test_cli_prints_review_decisions(tmp_path: Path) -> None:
    findings = tmp_path / "findings.json"
    findings.write_text(json.dumps({"findings": _local_review_findings()}), encoding="utf-8")

    completed = subprocess.run(
        [
            sys.executable,
            str(SCRIPTS / "finding_triage.py"),
            "--findings-file",
            str(findings),
            "--diff-path",
            DIFF[0],
            "--ac-ref",
            "AC-1",
            "--review-decisions",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.startswith("## Review decisions\n")
    assert "`R2`" in completed.stdout and "`R1`" not in completed.stdout


def _run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPTS / "finding_triage.py"), *args],
        capture_output=True,
        text=True,
        check=False,
    )


def test_ac1_repaired_finding_renders_in_a_separate_repaired_group(tmp_path: Path) -> None:
    """AC1: a finding marked repaired lands in its own group, in JSON and in Markdown."""
    findings = tmp_path / "findings.json"
    findings.write_text(json.dumps({"findings": _local_review_findings()}), encoding="utf-8")
    common = ["--findings-file", str(findings), "--diff-path", DIFF[0], "--ac-ref", "AC-1"]

    as_json = _run_cli(*common, "--repair-rounds-used", "1", "--repaired", "R1")
    as_markdown = _run_cli(
        *common, "--repair-rounds-used", "1", "--repaired", "R1", "--review-decisions"
    )

    assert as_json.returncode == 0, as_json.stdout + as_json.stderr
    envelope = json.loads(as_json.stdout)
    assert envelope["repaired"] == [
        {
            "finding_id": "R1",
            "severity": "high",
            "summary": "Refund path skips the lock.",
            "reviewer": "opus",
        }
    ]
    assert "R1" not in {f["finding_id"] for f in envelope["deferred"] + envelope["repair"]}
    assert as_markdown.returncode == 0, as_markdown.stdout + as_markdown.stderr
    assert "Repaired in the repair round:" in as_markdown.stdout
    assert (
        "- `R1` (high, opus): Refund path skips the lock. -- repaired." in as_markdown.stdout
    )
    assert "`R2` (low, sonnet): Name the retry constant. -- deferred" in as_markdown.stdout


def test_ac2_repaired_finding_is_not_deferred_after_the_repair_round() -> None:
    """AC2: after the round, repaired findings leave deferred; unmarked ones stay there."""
    repaired = _finding(finding_id="F1", severity="medium")
    unrepaired = _finding(finding_id="F2", severity="medium")

    result = finding_triage.triage_findings(
        [repaired, unrepaired],
        diff_paths=DIFF,
        acceptance_refs=["AC-1"],
        repair_rounds_used=1,
        repaired_ids=["F1"],
    )

    assert [f["finding_id"] for f in result["repaired"]] == ["F1"]
    assert [(f["finding_id"], f["reason"]) for f in result["deferred"]] == [
        ("F2", "REPAIR_ROUNDS_EXHAUSTED")
    ]
    assert result["repair"] == []
    assert result["repair_dispatch_authorized"] is False


def test_ac3_unknown_repaired_id_is_a_usage_error(tmp_path: Path) -> None:
    """AC3: marking an id that is not in the findings file fails loudly."""
    findings = tmp_path / "findings.json"
    findings.write_text(json.dumps({"findings": _local_review_findings()}), encoding="utf-8")

    completed = _run_cli(
        "--findings-file",
        str(findings),
        "--diff-path",
        DIFF[0],
        "--ac-ref",
        "AC-1",
        "--repair-rounds-used",
        "1",
        "--repaired",
        "R1",
        "--repaired",
        "R9",
    )

    assert completed.returncode == 2
    envelope = json.loads(completed.stdout)
    assert envelope["error"] == "FINDING_TRIAGE_INVALID"
    assert "R9" in envelope["message"]
    assert "R1" not in envelope["message"]


def test_blank_repaired_id_is_a_usage_error() -> None:
    with pytest.raises(finding_triage.FindingTriageError, match="empty"):
        finding_triage.triage_findings(
            [_finding()], diff_paths=DIFF, acceptance_refs=["AC-1"], repaired_ids=["  "]
        )


def test_repaired_id_is_whitespace_trimmed() -> None:
    result = finding_triage.triage_findings(
        [_finding()], diff_paths=DIFF, acceptance_refs=["AC-1"], repaired_ids=[" F1 "]
    )
    assert [f["finding_id"] for f in result["repaired"]] == ["F1"]


def test_all_repaired_renders_no_deferred_statement_and_the_repaired_list() -> None:
    section = finding_triage.render_review_decisions(
        [], [{"finding_id": "F1", "severity": "medium", "reviewer": "opus", "summary": "Fix."}]
    )
    assert section == (
        "## Review decisions\n\nNo local review finding was deferred.\n\n"
        "Repaired in the repair round:\n\n- `F1` (medium, opus): Fix. -- repaired.\n"
    )

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


def test_findings_outside_the_pack_diff_are_deferred() -> None:
    result = finding_triage.triage_findings(
        [_finding(paths=["src/legacy/other.py"])], diff_paths=DIFF, acceptance_refs=["AC-1"]
    )
    assert result["repair"] == []
    assert result["deferred"][0]["reason"] == "OUTSIDE_PACK_DIFF"


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

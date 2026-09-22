from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
MODULE = REPO_ROOT / "skills" / "bead-reviewer" / "scripts" / "finding_adjudication.py"


def _module():
    spec = importlib.util.spec_from_file_location("finding_adjudication", MODULE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_only_disputes_are_escalated() -> None:
    module = _module()
    findings = [
        {"finding_id": "formal:moc", "message": "MoC is missing.", "evidence": ["bead:body"]},
        {"finding_id": "repository:stale", "message": "Pointer is stale.", "evidence": ["src/a.py"]},
    ]
    decisions = {
        "formal:moc": {"decision": "accepted", "rationale": "Will add the row."},
        "repository:stale": {"decision": "disputed", "rationale": "The generated file exists at runtime."},
    }

    result = module.adjudicate_findings(findings, decisions)

    assert [item["finding_id"] for item in result["accepted"]] == ["formal:moc"]
    assert [item["finding_id"] for item in result["disputes"]] == ["repository:stale"]
    assert result["outcome"] == "human_required"


def test_all_accepted_returns_repair_without_escalation() -> None:
    module = _module()
    findings = [{"finding_id": "formal:moc", "message": "MoC is missing.", "evidence": ["bead:body"]}]
    decisions = {"formal:moc": {"decision": "accepted", "rationale": "Will repair."}}

    result = module.adjudicate_findings(findings, decisions)

    assert result["outcome"] == "repair"
    assert result["disputes"] == []

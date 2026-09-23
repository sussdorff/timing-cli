from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[3]
MODULE = REPO_ROOT / "skills" / "bead-reviewer" / "scripts" / "review_contract.py"
sys.path.insert(0, str(MODULE.parent))

import finding_rules  # noqa: E402


def _module():
    spec = importlib.util.spec_from_file_location("review_contract", MODULE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _bound_fields() -> dict[str, str]:
    return {"reviewer_sha": "r" * 64, "contract_sha": "c" * 64}


def _validate(module, result: dict, *, expected_digest: str = "a" * 64):
    return module.validate_review_result(
        result,
        expected_bead_id="clc-demo",
        expected_digest=expected_digest,
        expected_reviewer_sha="r" * 64,
        expected_contract_sha="c" * 64,
        allowed_rule_ids={"REPO-PATH-STALE", "ADHOC-UNCLASSIFIED"},
    )


def _finding(
    *,
    rule_id: str = "REPO-PATH-STALE",
    criterion: str = "repository",
    severity: str = "blocking",
    evidence: list[str] | None = None,
) -> dict[str, object]:
    anchors = evidence or ["src/example.py:12"]
    return {
        "rule_id": rule_id,
        "finding_id": finding_rules.build_finding_id(
            rule_id=rule_id,
            bead_id="clc-demo",
            criterion=criterion,
            evidence=anchors,
        ),
        "criterion": criterion,
        "severity": severity,
        "message": "The cited symbol does not exist.",
        "evidence": anchors,
        "recommended_change": {
            "operation": "replace",
            "target": "Context Pointers entry `src/missing.py`",
            "result": "Use `src/example.py:12` as the context pointer.",
        },
    }


def test_profiles_are_criteria_only_and_full_is_default(tmp_path: Path) -> None:
    module = _module()
    request = module.normalize_review_request(bead_id="clc-demo", target_repo=tmp_path)

    assert request == {
        "bead_id": "clc-demo",
        "profile": "full",
        "criteria": list(module.PROFILES["full"]),
        "target_repo": str(tmp_path.resolve()),
    }
    assert set(module.PROFILES) == {"formal", "semantic", "repository", "related-beads", "full"}
    assert "model" not in request
    assert "provider" not in request
    assert "description" not in request


def test_result_is_revision_bound_and_evidence_bearing() -> None:
    module = _module()
    result = {
        "bead_id": "clc-demo",
        "profile": "full",
        "reviewed_digest": "a" * 64,
        **_bound_fields(),
        "outcome": "blocked",
        "criteria": [{"criterion": "repository", "status": "ran", "reason": None}],
        "findings": [_finding()],
    }

    assert _validate(module, result) == result

    stale = {**result, "reviewed_digest": "b" * 64}
    with pytest.raises(module.ReviewContractError, match="digest"):
        _validate(module, stale)

    stale_reviewer = {**result, "reviewer_sha": "x" * 64}
    with pytest.raises(module.ReviewContractError, match="reviewer"):
        _validate(module, stale_reviewer)

    stale_contract = {**result, "contract_sha": "y" * 64}
    with pytest.raises(module.ReviewContractError, match="contract"):
        _validate(module, stale_contract)


def test_direct_answer_file_is_validated_against_request_and_resolved_rules(
    tmp_path: Path,
) -> None:
    module = _module()
    result = {
        "bead_id": "clc-demo",
        "profile": "full",
        "reviewed_digest": "a" * 64,
        **_bound_fields(),
        "outcome": "clean",
        "unavailable_reason": None,
        "criteria": [],
        "findings": [],
    }
    paths = {
        "result_file": tmp_path / "result.json",
        "bindings_file": tmp_path / "bindings.json",
        "contract_file": tmp_path / "contract.json",
    }
    paths["result_file"].write_text(json.dumps(result), encoding="utf-8")
    paths["bindings_file"].write_text(
        json.dumps({
            "content_sha": "a" * 64,
            "reviewer_sha": "r" * 64,
            "contract_sha": "c" * 64,
        }),
        encoding="utf-8",
    )
    paths["contract_file"].write_text(
        json.dumps({"status": "ok", "rules": []}), encoding="utf-8"
    )

    assert module.validate_result_files(
        **paths, bead_id="clc-demo", profile="full"
    ) == result

    with pytest.raises(module.ReviewContractError, match="profile"):
        module.validate_result_files(
            **paths, bead_id="clc-demo", profile="formal"
        )


def test_findings_require_stable_id_evidence_and_recommendation() -> None:
    module = _module()
    result = {
        "bead_id": "clc-demo",
        "profile": "formal",
        "reviewed_digest": "a" * 64,
        **_bound_fields(),
        "outcome": "warnings",
        "criteria": [],
        "findings": [{**_finding(severity="warning"), "finding_id": "", "evidence": []}],
    }

    with pytest.raises(module.ReviewContractError):
        _validate(module, result)


@pytest.mark.parametrize(
    ("outcome", "findings", "message"),
    [
        ("warnings", [], "only warning"),
        (
            "warnings",
            [_finding()],
            "only warning",
        ),
        (
            "blocked",
            [_finding(severity="warning")],
            "blocking finding",
        ),
    ],
)
def test_outcomes_require_matching_nonempty_findings(
    outcome: str, findings: list[dict[str, object]], message: str
) -> None:
    module = _module()
    result = {
        "bead_id": "clc-demo",
        "profile": "full",
        "reviewed_digest": "a" * 64,
        **_bound_fields(),
        "outcome": outcome,
        "criteria": [],
        "findings": findings,
    }

    with pytest.raises(module.ReviewContractError, match=message):
        _validate(module, result)


@pytest.mark.parametrize(
    "recommended_change",
    [
        "Append a Reviewer-Fix note.",
        {"operation": "clarify", "target": "AC 1", "result": "Make it clearer."},
        {"operation": "replace", "target": "", "result": "New text."},
        {"operation": "remove", "target": "Reviewer history", "result": ""},
    ],
)
def test_finding_rejects_unstructured_or_incomplete_edit_instruction(
    recommended_change: object,
) -> None:
    module = _module()
    result = {
        "bead_id": "clc-demo",
        "profile": "semantic",
        "reviewed_digest": "a" * 64,
        **_bound_fields(),
        "outcome": "blocked",
        "criteria": [{"criterion": "semantic", "status": "ran", "reason": None}],
        "findings": [{
            **_finding(rule_id="ADHOC-UNCLASSIFIED", criterion="semantic"),
            "message": "Two architecture statements conflict.",
            "recommended_change": recommended_change,
        }],
    }

    with pytest.raises(module.ReviewContractError, match="recommended_change"):
        _validate(module, result)


def test_disputed_is_caller_state_not_reviewer_outcome() -> None:
    module = _module()
    result = {
        "bead_id": "clc-demo",
        "profile": "full",
        "reviewed_digest": "a" * 64,
        **_bound_fields(),
        "outcome": "disputed",
        "criteria": [],
        "findings": [],
    }

    with pytest.raises(module.ReviewContractError, match="outcome"):
        _validate(module, result)


@pytest.mark.parametrize(
    ("updates", "message"),
    [
        ({"rule_id": "UNKNOWN-RULE"}, "unknown"),
        ({"rule_id": "repo-path-stale"}, "rule_id"),
        ({"finding_id": "REPO-PATH-STALE:clc-demo:000000000000"}, "deterministic"),
    ],
)
def test_findings_reject_unknown_malformed_or_nondeterministic_identity(
    updates: dict[str, str], message: str
) -> None:
    module = _module()
    result = {
        "bead_id": "clc-demo",
        "profile": "full",
        "reviewed_digest": "a" * 64,
        **_bound_fields(),
        "outcome": "blocked",
        "criteria": [],
        "findings": [{**_finding(), **updates}],
    }

    with pytest.raises(module.ReviewContractError, match=message):
        _validate(module, result)


def test_duplicate_occurrence_ids_are_rejected() -> None:
    module = _module()
    finding = _finding()
    result = {
        "bead_id": "clc-demo",
        "profile": "full",
        "reviewed_digest": "a" * 64,
        **_bound_fields(),
        "outcome": "blocked",
        "criteria": [],
        "findings": [finding, {**finding, "message": "Different prose."}],
    }

    with pytest.raises(module.ReviewContractError, match="duplicate"):
        _validate(module, result)


def test_unavailable_skips_digest_check_with_closed_empty_payload() -> None:
    module = _module()
    result = {
        "bead_id": "clc-demo",
        "profile": "full",
        "reviewed_digest": "",
        "outcome": "unavailable",
        "unavailable_reason": "target repository does not match the assigned workspace",
        "criteria": [],
        "findings": [],
    }

    assert _validate(module, result) == result


@pytest.mark.parametrize(
    ("updates", "message"),
    [
        ({"unavailable_reason": ""}, "reason"),
        (
            {"criteria": [{"criterion": "formal", "status": "unavailable", "reason": "wrong repo"}]},
            "criteria",
        ),
        (
            {"findings": [{"finding_id": "formal:wrong-repo"}]},
            "findings",
        ),
        ({"reviewed_digest": "a" * 64}, "digest"),
    ],
)
def test_unavailable_rejects_nonempty_review_payload(
    updates: dict[str, object], message: str
) -> None:
    module = _module()
    result = {
        "bead_id": "clc-demo",
        "profile": "full",
        "reviewed_digest": "",
        "outcome": "unavailable",
        "unavailable_reason": "wrong repository",
        "criteria": [],
        "findings": [],
        **updates,
    }

    with pytest.raises(module.ReviewContractError, match=message):
        _validate(module, result)

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest


REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_DIR = REPO_ROOT / "skills" / "bead-reviewer" / "scripts"
SCRIPT = SCRIPT_DIR / "write_review_cache.py"
sys.path.insert(0, str(SCRIPT_DIR))

import finding_rules  # noqa: E402


def _load_module():
    spec = importlib.util.spec_from_file_location("write_review_cache_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _bead(description: str = "reviewed body") -> dict:
    return {
        "id": "clc-cache",
        "title": "Cache results remain revision bound",
        "description": description,
        "acceptance_criteria": "- AC-1: exact result is stored",
        "issue_type": "bug",
        "dependencies": [],
        "labels": ["bead-reviewer"],
        "metadata": {},
    }


def _review_result(*, outcome: str = "warnings") -> dict:
    findings = []
    if outcome == "warnings":
        evidence = ["bead:clc-cache"]
        findings = [
            {
                "rule_id": "BASE-CLEAR-INTENT",
                "finding_id": finding_rules.build_finding_id(
                    rule_id="BASE-CLEAR-INTENT",
                    bead_id="clc-cache",
                    criterion="formal",
                    evidence=evidence,
                ),
                "criterion": "formal",
                "severity": "warning",
                "message": "One advisory remains.",
                "evidence": evidence,
                "recommended_change": {
                    "operation": "replace",
                    "target": "The ambiguous sentence",
                    "result": "State the observable behavior explicitly.",
                },
            }
        ]
    return {
        "bead_id": "clc-cache",
        "profile": "full",
        "reviewed_digest": "content-sha",
        "reviewer_sha": "reviewer-sha",
        "contract_sha": "contract-sha",
        "outcome": outcome,
        "unavailable_reason": None,
        "criteria": [
            {"criterion": "formal", "status": "ran", "reason": None},
        ],
        "findings": findings,
    }


def _install_live_state(monkeypatch: pytest.MonkeyPatch, module, beads: list[dict]) -> MagicMock:
    live = iter(beads)
    monkeypatch.setattr(module, "load_live_bead", lambda bead_id, repo_root: next(live))
    monkeypatch.setattr(
        module,
        "compute_review_shas",
        lambda bead, repo_root, reviewer_skill_path=None: {
            "content_sha": "content-sha" if bead["description"] == "reviewed body" else "changed-sha",
            "reviewer_sha": "reviewer-sha",
            "contract_sha": "contract-sha",
            "allowed_rule_ids": {"BASE-CLEAR-INTENT"},
        },
    )
    run_bd = MagicMock(return_value=MagicMock(returncode=0, stdout="ok", stderr=""))
    monkeypatch.setattr(module, "_run_bd", run_bd)
    return run_bd


def test_exact_typed_result_writes_flat_schema_v2_stamp(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = _load_module()
    run_bd = _install_live_state(monkeypatch, module, [_bead(), _bead()])

    result = module.write_review_cache(
        review_result=_review_result(),
        repo_root=tmp_path,
        timestamp="2026-07-16T09:00:00Z",
    )

    assert result["review"] == {
        "schema_version": 2,
        "reviewed_at": "2026-07-16T09:00:00Z",
        "profile": "full",
        "outcome": "warnings",
        "content_sha": "content-sha",
        "reviewer_sha": "reviewer-sha",
        "contract_sha": "contract-sha",
        "finding_ids": [
            finding_rules.build_finding_id(
                rule_id="BASE-CLEAR-INTENT",
                bead_id="clc-cache",
                criterion="formal",
                evidence=["bead:clc-cache"],
            )
        ],
        "finding_rule_ids": ["BASE-CLEAR-INTENT"],
    }
    update_args = run_bd.call_args.args[0]
    assert update_args[:2] == ["update", "clc-cache"]
    assert run_bd.call_args.kwargs["repo_root"] == tmp_path.resolve()
    written = update_args[update_args.index("--set-metadata") + 1]
    assert json.loads(written.split("=", 1)[1]) == result["review"]


def test_compute_review_shas_uses_resolved_label_families(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = _load_module()
    families = [{"id": "ui", "prefix": "ui:"}]
    monkeypatch.setattr(
        module.contract_loader,
        "resolve_contract",
        lambda repo_root: {
            "status": "ok",
            "diagnostics": [],
            "contract_sha": "contract-sha",
            "label_families": families,
            "rules": [{"rule_id": "BASE-CLEAR-INTENT"}],
        },
    )
    content_sha = MagicMock(return_value="content-sha")
    monkeypatch.setattr(
        module.compute_bead_content_sha, "compute_content_sha", content_sha
    )
    monkeypatch.setattr(
        module.compute_bead_content_sha,
        "compute_reviewer_sha",
        lambda reviewer_skill_path=None: "reviewer-sha",
    )

    result = module.compute_review_shas(_bead(), tmp_path)

    assert result["content_sha"] == "content-sha"
    assert result["allowed_rule_ids"] == {
        "BASE-CLEAR-INTENT",
        *finding_rules.registered_rule_ids(),
    }
    content_sha.assert_called_once_with(_bead(), label_families=families)


def test_compute_review_shas_wraps_invalid_rule_registry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = _load_module()
    monkeypatch.setattr(
        module.contract_loader,
        "resolve_contract",
        lambda repo_root: {
            "status": "ok",
            "diagnostics": [],
            "contract_sha": "contract-sha",
            "label_families": [],
            "rules": [],
        },
    )
    monkeypatch.setattr(
        module.finding_rules,
        "allowed_rule_ids",
        MagicMock(side_effect=module.finding_rules.FindingRuleError("invalid registry")),
    )

    with pytest.raises(module.ReviewCacheWriteError, match="invalid registry"):
        module.compute_review_shas(_bead(), tmp_path)


def test_stamp_sorts_unique_instance_and_rule_ids() -> None:
    module = _load_module()
    result = _review_result()
    second = {
        **result["findings"][0],
        "rule_id": "ADHOC-UNCLASSIFIED",
        "finding_id": finding_rules.build_finding_id(
            rule_id="ADHOC-UNCLASSIFIED",
            bead_id="clc-cache",
            criterion="formal",
            evidence=["bead:clc-cache#Acceptance-Criteria"],
        ),
        "evidence": ["bead:clc-cache#Acceptance-Criteria"],
    }
    result["findings"] = [result["findings"][0], second]

    stamp = module._stamp(result, timestamp="2026-07-16T09:00:00Z")

    assert stamp["finding_ids"] == sorted(stamp["finding_ids"])
    assert stamp["finding_rule_ids"] == [
        "ADHOC-UNCLASSIFIED",
        "BASE-CLEAR-INTENT",
    ]


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("reviewed_digest", "stale", "content"),
        ("reviewer_sha", "stale", "reviewer"),
        ("contract_sha", "stale", "contract"),
        ("bead_id", "clc-other", "bead_id"),
    ],
)
def test_mismatched_result_refuses_without_update(
    field: str,
    value: str,
    message: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_module()
    run_bd = _install_live_state(monkeypatch, module, [_bead(), _bead()])
    result = {**_review_result(), field: value}

    with pytest.raises(module.ReviewCacheWriteError, match=message):
        module.write_review_cache(review_result=result, repo_root=tmp_path)

    run_bd.assert_not_called()


def test_second_live_read_closes_the_toctou_guard_window(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = _load_module()
    run_bd = _install_live_state(
        monkeypatch,
        module,
        [_bead(), _bead(description="changed after first validation")],
    )

    with pytest.raises(module.ReviewCacheWriteError, match="content"):
        module.write_review_cache(review_result=_review_result(), repo_root=tmp_path)

    run_bd.assert_not_called()


def test_unavailable_result_cannot_be_stamped(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = _load_module()
    run_bd = MagicMock()
    monkeypatch.setattr(module, "_run_bd", run_bd)
    unavailable = {
        "bead_id": "clc-cache",
        "profile": "full",
        "reviewed_digest": "",
        "outcome": "unavailable",
        "unavailable_reason": "wrong repository",
        "criteria": [],
        "findings": [],
    }

    with pytest.raises(module.ReviewCacheWriteError, match="unavailable"):
        module.write_review_cache(review_result=unavailable, repo_root=tmp_path)

    run_bd.assert_not_called()

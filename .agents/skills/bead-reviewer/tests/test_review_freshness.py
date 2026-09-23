from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest


REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT = REPO_ROOT / "skills" / "bead-reviewer" / "scripts" / "review_freshness.py"


def _module():
    spec = importlib.util.spec_from_file_location("review_freshness", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


CURRENT = {
    "content_sha": "content-current",
    "reviewer_sha": "reviewer-current",
    "contract_sha": "contract-current",
}


def _bead(review=None) -> dict:
    metadata = {} if review is None else {"review": review}
    return {"id": "clc-review", "metadata": metadata}


def _stamp(**updates) -> dict:
    return {
        "schema_version": 2,
        "reviewed_at": "2026-07-16T09:00:00Z",
        "profile": "full",
        "outcome": "clean",
        "content_sha": CURRENT["content_sha"],
        "reviewer_sha": CURRENT["reviewer_sha"],
        "contract_sha": CURRENT["contract_sha"],
        "finding_ids": [],
        **updates,
    }


def test_legacy_stamp_is_never_reviewed() -> None:
    module = _module()
    legacy = {
        "timestamp": "2026-05-21T11:07:03Z",
        "verdict": "FACTORY_READY",
        "content_sha": CURRENT["content_sha"],
        "reviewer_sha": CURRENT["reviewer_sha"],
    }

    result = module.classify_review_freshness(_bead(legacy), current_shas=CURRENT)

    assert result["freshness"] == "never-reviewed"
    assert result["outcome"] is None
    assert result["stale_reasons"] == ["legacy-schema"]
    assert result["needs_review"] is True


def test_schema_v2_stamp_is_current_for_dict_or_json_string() -> None:
    module = _module()

    for review in (_stamp(), json.dumps(_stamp())):
        result = module.classify_review_freshness(_bead(review), current_shas=CURRENT)
        assert result == {
            "bead_id": "clc-review",
            "outcome": "clean",
            "freshness": "current",
            "stale_reasons": [],
            "needs_review": False,
        }


def test_reports_all_stale_reasons() -> None:
    module = _module()
    review = _stamp(
        content_sha="content-old",
        reviewer_sha="reviewer-old",
        contract_sha="contract-old",
    )

    result = module.classify_review_freshness(_bead(review), current_shas=CURRENT)

    assert result["freshness"] == "stale"
    assert result["outcome"] == "clean"
    assert result["stale_reasons"] == ["content", "reviewer", "contract"]
    assert result["needs_review"] is True


def test_missing_or_invalid_schema_v2_stamp_needs_review() -> None:
    module = _module()

    assert module.classify_review_freshness(_bead(), current_shas=CURRENT)[
        "freshness"
    ] == "never-reviewed"
    invalid = _stamp(outcome="unavailable")
    result = module.classify_review_freshness(_bead(invalid), current_shas=CURRENT)
    assert result["freshness"] == "stale"
    assert result["stale_reasons"] == ["invalid-outcome"]


def test_current_shas_uses_resolved_label_families(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = _module()
    families = [{"id": "focus", "prefix": "focus:"}]
    monkeypatch.setattr(
        module.contract_loader,
        "resolve_contract",
        lambda repo_root: {
            "status": "ok",
            "diagnostics": [],
            "contract_sha": "contract-current",
            "label_families": families,
        },
    )
    content_sha = MagicMock(return_value="content-current")
    monkeypatch.setattr(
        module.compute_bead_content_sha, "compute_content_sha", content_sha
    )
    monkeypatch.setattr(
        module.compute_bead_content_sha,
        "compute_reviewer_sha",
        lambda: "reviewer-current",
    )
    bead = _bead()

    result = module.current_shas(bead, repo_root=tmp_path)

    assert result == CURRENT
    content_sha.assert_called_once_with(bead, label_families=families)

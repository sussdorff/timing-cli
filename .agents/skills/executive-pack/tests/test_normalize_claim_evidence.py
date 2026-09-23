from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT = REPO_ROOT / "skills" / "executive-pack" / "scripts" / "normalize_claim_evidence.py"
SPEC = importlib.util.spec_from_file_location("normalize_claim_evidence", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def _context_payload(digest: str, contract: str) -> dict:
    return {
        "role": "context_discovery",
        "verdict": "ready",
        "bead_content_digest": digest,
        "agent": "bead-context",
        "model": "model-provided-value",
        "contract_digest": contract,
        "repository_context_digest": "model-provided-value",
        "primary_files": ["library.yaml", "missing.py"],
        "test_files": ["tests/test_guardrails_schema.py", "future.test.py"],
        "symbols": [
            {"name": "catalog", "file": "library.yaml", "line": 1},
            {"name": "future", "file": None, "line": None},
        ],
    }


def test_extracts_fenced_json_and_filters_context_candidates(tmp_path: Path) -> None:
    (tmp_path / "tests").mkdir()
    (tmp_path / "library.yaml").write_text("library: {}\n", encoding="utf-8")
    (tmp_path / "tests" / "test_guardrails_schema.py").write_text("pass\n", encoding="utf-8")
    digest = "a" * 64
    contract = "b" * 64
    raw = "Result:\n```json\n" + json.dumps(_context_payload(digest, contract)) + "\n```"

    payload = MODULE.extract_json_object(raw)
    result = MODULE.normalize_evidence(
        payload,
        repo_root=tmp_path,
        role="context_discovery",
        bead_content_digest=digest,
        contract_digest=contract,
        model="claude-haiku",
    )

    assert result["verdict"] == "ready_with_warnings"
    assert result["primary_files"] == ["library.yaml"]
    assert result["test_files"] == ["tests/test_guardrails_schema.py"]
    assert result["symbols"] == [{"name": "catalog", "file": "library.yaml", "line": 1}]
    assert result["model"] == "claude-haiku"
    assert len(result["repository_context_digest"]) == 64
    int(result["repository_context_digest"], 16)
    assert "missing.py" in result["gaps"][0]


def test_repository_digest_uses_sorted_paths_and_contents(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("alpha", encoding="utf-8")
    (tmp_path / "b.txt").write_text("beta", encoding="utf-8")

    first = MODULE._repository_digest(tmp_path, ["b.txt", "a.txt"])
    second = MODULE._repository_digest(tmp_path, ["a.txt", "b.txt"])

    assert first == second
    (tmp_path / "a.txt").write_text("changed", encoding="utf-8")
    assert MODULE._repository_digest(tmp_path, ["a.txt", "b.txt"]) != first


def test_spec_review_fails_closed_for_missing_repository_evidence(tmp_path: Path) -> None:
    payload = {
        "role": "spec_review",
        "verdict": "ready",
        "bead_content_digest": "a" * 64,
        "agent": "bead-spec-reviewer",
        "contract_digest": "b" * 64,
        "repository_context": {
            "standards": ["missing.md"],
            "adrs": [],
            "source": [],
            "tests": [],
        },
    }

    with pytest.raises(MODULE.EvidenceError, match="does not exist"):
        MODULE.normalize_evidence(
            payload,
            repo_root=tmp_path,
            role="spec_review",
            bead_content_digest="a" * 64,
            contract_digest="b" * 64,
            model="claude-opus",
        )


def test_contract_and_bead_digests_are_bound(tmp_path: Path) -> None:
    (tmp_path / "library.yaml").write_text("library: {}\n", encoding="utf-8")
    payload = _context_payload("a" * 64, "b" * 64)
    payload["primary_files"] = ["library.yaml"]
    payload["test_files"] = []
    payload["symbols"] = []

    with pytest.raises(MODULE.EvidenceError, match="another bead revision"):
        MODULE.normalize_evidence(
            payload,
            repo_root=tmp_path,
            role="context_discovery",
            bead_content_digest="c" * 64,
            contract_digest="b" * 64,
            model="claude-haiku",
        )

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "phase14_diff_scope.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("phase14_diff_scope", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _commit(repo: Path, relative_path: str, content: str, message: str) -> str:
    target = repo / relative_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    _git(repo, "add", relative_path)
    _git(repo, "commit", "-m", message)
    return _git(repo, "rev-parse", "HEAD")


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test User")
    return repo


def _manifest(path: Path, bead_id: str, changed_files: list[str]) -> Path:
    path.write_text(
        json.dumps({"bead_id": bead_id, "changed_files": changed_files}),
        encoding="utf-8",
    )
    return path


def test_regression_phase14_excludes_unrelated_base_commit(tmp_path: Path) -> None:
    """Guard the CL-j92j failure shape where Phase 14 inspected CL-v1tb files."""
    module = _load_module()
    repo = _repo(tmp_path)
    _commit(repo, "launchers/cld", "old\n", "base")
    _commit(repo, "launchers/cld", "retired boundary\n", "CL-v1tb launcher change")
    pre_impl_sha = _git(repo, "rev-parse", "HEAD")
    _commit(repo, "capabilities.yaml", "read_files: true\n", "CL-j92j capability")
    head_sha = _commit(
        repo,
        "tests/test_capabilities.py",
        "def test_capability():\n    assert True\n",
        "CL-j92j tests",
    )
    manifest = _manifest(
        tmp_path / "implementation_manifest.json",
        "CL-j92j",
        ["capabilities.yaml", "tests/test_capabilities.py"],
    )

    result = module.validate_diff_scope(
        repo=repo,
        bead_id="CL-j92j",
        pre_impl_sha=pre_impl_sha,
        bead_head_sha=head_sha,
        manifest_path=manifest,
    )

    assert result["status"] == "ok"
    assert result["reason"] == "DIFF_SCOPE_VALID"
    assert result["diff_range"] == f"{pre_impl_sha}...{head_sha}"
    assert result["changed_files"] == [
        "capabilities.yaml",
        "tests/test_capabilities.py",
    ]
    assert "launchers/cld" not in result["changed_files"]
    assert len(result["changed_file_hash"]) == 64


def test_phase14_fails_closed_on_manifest_mismatch(tmp_path: Path) -> None:
    module = _load_module()
    repo = _repo(tmp_path)
    pre_impl_sha = _commit(repo, "README.md", "base\n", "base")
    head_sha = _commit(repo, "src/change.py", "VALUE = 1\n", "change")
    manifest = _manifest(
        tmp_path / "implementation_manifest.json",
        "clc-op85",
        ["src/different.py"],
    )

    result = module.validate_diff_scope(
        repo=repo,
        bead_id="clc-op85",
        pre_impl_sha=pre_impl_sha,
        bead_head_sha=head_sha,
        manifest_path=manifest,
    )

    assert result["status"] == "error"
    assert result["reason"] == "IMPLEMENTATION_MANIFEST_MISMATCH"
    assert result["manifest_only"] == ["src/different.py"]
    assert result["diff_only"] == ["src/change.py"]


def test_phase14_fails_closed_when_head_is_not_descended_from_baseline(
    tmp_path: Path,
) -> None:
    module = _load_module()
    repo = _repo(tmp_path)
    base_sha = _commit(repo, "README.md", "base\n", "base")
    _git(repo, "switch", "-c", "other")
    pre_impl_sha = _commit(repo, "other.txt", "other\n", "other branch")
    _git(repo, "switch", "main")
    head_sha = _commit(repo, "main.txt", "main\n", "main branch")
    manifest = _manifest(tmp_path / "implementation_manifest.json", "clc-op85", [])

    result = module.validate_diff_scope(
        repo=repo,
        bead_id="clc-op85",
        pre_impl_sha=pre_impl_sha,
        bead_head_sha=head_sha,
        manifest_path=manifest,
    )

    assert result["status"] == "error"
    assert result["reason"] == "HEAD_NOT_DESCENDED_FROM_BASELINE"
    assert base_sha


def test_phase14_fails_closed_when_sha_is_missing(tmp_path: Path) -> None:
    module = _load_module()
    repo = _repo(tmp_path)
    head_sha = _commit(repo, "README.md", "base\n", "base")
    manifest = _manifest(tmp_path / "implementation_manifest.json", "clc-op85", [])

    result = module.validate_diff_scope(
        repo=repo,
        bead_id="clc-op85",
        pre_impl_sha="",
        bead_head_sha=head_sha,
        manifest_path=manifest,
    )

    assert result["status"] == "error"
    assert result["reason"] == "MISSING_PRE_IMPL_SHA"


@pytest.mark.parametrize(
    ("pre_impl_sha", "bead_head_sha", "reason"),
    [
        ("not-a-sha", "HEAD_SHA", "INVALID_PRE_IMPL_SHA"),
        ("BASE_SHA", "not-a-sha", "INVALID_BEAD_HEAD_SHA"),
    ],
)
def test_phase14_fails_closed_on_invalid_sha(
    tmp_path: Path,
    pre_impl_sha: str,
    bead_head_sha: str,
    reason: str,
) -> None:
    module = _load_module()
    repo = _repo(tmp_path)
    head_sha = _commit(repo, "README.md", "base\n", "base")
    manifest = _manifest(tmp_path / "implementation_manifest.json", "clc-op85", [])

    result = module.validate_diff_scope(
        repo=repo,
        bead_id="clc-op85",
        pre_impl_sha=head_sha if pre_impl_sha == "BASE_SHA" else pre_impl_sha,
        bead_head_sha=head_sha if bead_head_sha == "HEAD_SHA" else bead_head_sha,
        manifest_path=manifest,
    )

    assert result["status"] == "error"
    assert result["reason"] == reason


def test_phase14_fails_closed_on_empty_diff(tmp_path: Path) -> None:
    module = _load_module()
    repo = _repo(tmp_path)
    head_sha = _commit(repo, "README.md", "base\n", "base")
    manifest = _manifest(tmp_path / "implementation_manifest.json", "clc-op85", [])

    result = module.validate_diff_scope(
        repo=repo,
        bead_id="clc-op85",
        pre_impl_sha=head_sha,
        bead_head_sha=head_sha,
        manifest_path=manifest,
    )

    assert result["status"] == "error"
    assert result["reason"] == "EMPTY_BEAD_DIFF"


@pytest.mark.parametrize(
    ("manifest_content", "manifest_name", "reason"),
    [
        (None, "missing.json", "IMPLEMENTATION_MANIFEST_MISSING"),
        ("not-json", "invalid.json", "IMPLEMENTATION_MANIFEST_INVALID"),
        (
            json.dumps({"bead_id": "other-bead", "changed_files": ["change.py"]}),
            "wrong-bead.json",
            "IMPLEMENTATION_MANIFEST_BEAD_MISMATCH",
        ),
    ],
)
def test_phase14_fails_closed_on_invalid_manifest_identity(
    tmp_path: Path,
    manifest_content: str | None,
    manifest_name: str,
    reason: str,
) -> None:
    module = _load_module()
    repo = _repo(tmp_path)
    pre_impl_sha = _commit(repo, "README.md", "base\n", "base")
    head_sha = _commit(repo, "change.py", "VALUE = 1\n", "change")
    manifest = tmp_path / manifest_name
    if manifest_content is not None:
        manifest.write_text(manifest_content, encoding="utf-8")

    result = module.validate_diff_scope(
        repo=repo,
        bead_id="clc-op85",
        pre_impl_sha=pre_impl_sha,
        bead_head_sha=head_sha,
        manifest_path=manifest,
    )

    assert result["status"] == "error"
    assert result["reason"] == reason


def test_phase14_evidence_records_verdict_and_scope(tmp_path: Path) -> None:
    module = _load_module()
    repo = _repo(tmp_path)
    pre_impl_sha = _commit(repo, "README.md", "base\n", "base")
    head_sha = _commit(repo, "src/change.py", "VALUE = 1\n", "change")
    manifest = _manifest(
        tmp_path / "implementation_manifest.json",
        "clc-op85",
        ["src/change.py"],
    )
    scope = module.validate_diff_scope(
        repo=repo,
        bead_id="clc-op85",
        pre_impl_sha=pre_impl_sha,
        bead_head_sha=head_sha,
        manifest_path=manifest,
    )

    evidence = module.build_constraint_evidence(scope, checker_verdict="PASS")

    assert evidence["checker_verdict"] == "PASS"
    assert evidence["diff_range"] == f"{pre_impl_sha}...{head_sha}"
    assert evidence["changed_files"] == ["src/change.py"]
    assert len(evidence["changed_file_hash"]) == 64

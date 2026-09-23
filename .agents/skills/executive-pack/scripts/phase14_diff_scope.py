#!/usr/bin/env -S uv run python
"""Build and validate the exact Git diff scope for Phase 14 constraints."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any


_SHA_RE = re.compile(r"^[0-9a-fA-F]{7,64}$")


def _result(reason: str, **fields: Any) -> dict[str, Any]:
    return {
        "status": "ok" if reason == "DIFF_SCOPE_VALID" else "error",
        "reason": reason,
        "bead_id": fields.pop("bead_id", ""),
        "diff_range": fields.pop("diff_range", ""),
        "changed_files": fields.pop("changed_files", []),
        "changed_file_hash": fields.pop("changed_file_hash", ""),
        **fields,
    }


def _git(repo: Path, *args: str, text: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        capture_output=True,
        text=text,
        check=False,
    )


def _commit_exists(repo: Path, sha: str) -> bool:
    if not _SHA_RE.fullmatch(sha):
        return False
    return _git(repo, "cat-file", "-e", f"{sha}^{{commit}}").returncode == 0


def _load_manifest(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None, "IMPLEMENTATION_MANIFEST_MISSING"
    except (json.JSONDecodeError, OSError):
        return None, "IMPLEMENTATION_MANIFEST_INVALID"
    if not isinstance(data, dict):
        return None, "IMPLEMENTATION_MANIFEST_INVALID"
    return data, None


def _normalize_manifest_files(data: dict[str, Any]) -> list[str] | None:
    changed_files = data.get("changed_files")
    if not isinstance(changed_files, list):
        return None
    if any(not isinstance(path, str) or not path.strip() for path in changed_files):
        return None
    return sorted(set(changed_files))


def validate_diff_scope(
    *,
    repo: Path,
    bead_id: str,
    pre_impl_sha: str,
    bead_head_sha: str,
    manifest_path: Path,
) -> dict[str, Any]:
    """Validate an explicit baseline-to-head range against implementation evidence."""
    repo = repo.resolve()
    bead_id = bead_id.strip()
    pre_impl_sha = pre_impl_sha.strip()
    bead_head_sha = bead_head_sha.strip()
    diff_range = (
        f"{pre_impl_sha}...{bead_head_sha}"
        if pre_impl_sha and bead_head_sha
        else ""
    )

    if not bead_id:
        return _result("MISSING_BEAD_ID", diff_range=diff_range)
    if not pre_impl_sha:
        return _result(
            "MISSING_PRE_IMPL_SHA",
            bead_id=bead_id,
            diff_range=diff_range,
        )
    if not bead_head_sha:
        return _result(
            "MISSING_BEAD_HEAD_SHA",
            bead_id=bead_id,
            diff_range=diff_range,
        )
    if not _commit_exists(repo, pre_impl_sha):
        return _result(
            "INVALID_PRE_IMPL_SHA",
            bead_id=bead_id,
            diff_range=diff_range,
        )
    if not _commit_exists(repo, bead_head_sha):
        return _result(
            "INVALID_BEAD_HEAD_SHA",
            bead_id=bead_id,
            diff_range=diff_range,
        )

    ancestry = _git(
        repo,
        "merge-base",
        "--is-ancestor",
        pre_impl_sha,
        bead_head_sha,
    )
    if ancestry.returncode != 0:
        return _result(
            "HEAD_NOT_DESCENDED_FROM_BASELINE",
            bead_id=bead_id,
            diff_range=diff_range,
        )

    diff = _git(repo, "diff", "--name-only", "-z", diff_range, text=False)
    if diff.returncode != 0:
        return _result(
            "DIFF_COMPUTATION_FAILED",
            bead_id=bead_id,
            diff_range=diff_range,
        )
    changed_files = sorted(
        path.decode("utf-8")
        for path in diff.stdout.split(b"\0")
        if path
    )
    if not changed_files:
        return _result(
            "EMPTY_BEAD_DIFF",
            bead_id=bead_id,
            diff_range=diff_range,
        )

    manifest, manifest_error = _load_manifest(manifest_path)
    if manifest_error:
        return _result(
            manifest_error,
            bead_id=bead_id,
            diff_range=diff_range,
            changed_files=changed_files,
        )
    assert manifest is not None
    if manifest.get("bead_id") != bead_id:
        return _result(
            "IMPLEMENTATION_MANIFEST_BEAD_MISMATCH",
            bead_id=bead_id,
            diff_range=diff_range,
            changed_files=changed_files,
            manifest_bead_id=manifest.get("bead_id"),
        )
    manifest_files = _normalize_manifest_files(manifest)
    if manifest_files is None:
        return _result(
            "IMPLEMENTATION_MANIFEST_INVALID",
            bead_id=bead_id,
            diff_range=diff_range,
            changed_files=changed_files,
        )
    if manifest_files != changed_files:
        return _result(
            "IMPLEMENTATION_MANIFEST_MISMATCH",
            bead_id=bead_id,
            diff_range=diff_range,
            changed_files=changed_files,
            manifest_only=sorted(set(manifest_files) - set(changed_files)),
            diff_only=sorted(set(changed_files) - set(manifest_files)),
        )

    changed_file_hash = hashlib.sha256(
        ("\n".join(changed_files) + "\n").encode("utf-8")
    ).hexdigest()
    return _result(
        "DIFF_SCOPE_VALID",
        bead_id=bead_id,
        diff_range=diff_range,
        changed_files=changed_files,
        changed_file_hash=changed_file_hash,
        pre_impl_sha=pre_impl_sha,
        bead_head_sha=bead_head_sha,
        manifest_path=str(manifest_path.resolve()),
    )


def build_constraint_evidence(
    scope: dict[str, Any],
    *,
    checker_verdict: str,
) -> dict[str, Any]:
    """Attach the constraint verdict to a previously validated diff scope."""
    if scope.get("status") != "ok":
        raise ValueError("constraint evidence requires a valid Phase 14 diff scope")
    return {
        "contract_version": "1",
        "bead_id": scope["bead_id"],
        "diff_range": scope["diff_range"],
        "pre_impl_sha": scope["pre_impl_sha"],
        "bead_head_sha": scope["bead_head_sha"],
        "changed_files": scope["changed_files"],
        "changed_file_hash": scope["changed_file_hash"],
        "checker_verdict": checker_verdict,
    }


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate and record the exact Phase 14 Git diff scope."
    )
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--bead-id", required=True)
    parser.add_argument("--pre-impl-sha", required=True)
    parser.add_argument("--bead-head-sha", required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--checker-verdict")
    parser.add_argument("--evidence-out", type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    result = validate_diff_scope(
        repo=args.repo,
        bead_id=args.bead_id,
        pre_impl_sha=args.pre_impl_sha,
        bead_head_sha=args.bead_head_sha,
        manifest_path=args.manifest,
    )
    if result["status"] != "ok":
        print(json.dumps(result, sort_keys=True))
        return 2
    if args.checker_verdict:
        evidence = build_constraint_evidence(
            result,
            checker_verdict=args.checker_verdict,
        )
        if args.evidence_out:
            args.evidence_out.parent.mkdir(parents=True, exist_ok=True)
            args.evidence_out.write_text(
                json.dumps(evidence, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
        result["constraint_evidence"] = evidence
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())

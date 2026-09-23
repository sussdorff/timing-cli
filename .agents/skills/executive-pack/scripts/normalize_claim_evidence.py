#!/usr/bin/env python3
"""Normalize repository-aware Bead Claim evidence deterministically."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


READY_VERDICTS = {"ready", "ready_with_warnings", "blocked"}
ROLE_AGENTS = {
    "spec_review": "bead-spec-reviewer",
    "context_discovery": "bead-context",
}


class EvidenceError(ValueError):
    """Raised when raw harness evidence cannot be normalized safely."""


def extract_json_object(raw: str) -> dict[str, Any]:
    """Extract the first role-bearing JSON object from plain or fenced output."""
    stripped = raw.strip()
    try:
        direct = json.loads(stripped)
    except json.JSONDecodeError:
        direct = None
    if isinstance(direct, dict) and direct.get("role"):
        return direct

    decoder = json.JSONDecoder()
    for index, character in enumerate(raw):
        if character != "{":
            continue
        try:
            candidate, _ = decoder.raw_decode(raw[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(candidate, dict) and candidate.get("role"):
            return candidate
    raise EvidenceError("agent output does not contain a role-bearing JSON object")


def _contained_path(repo_root: Path, raw_path: Any) -> tuple[str, Path]:
    value = str(raw_path or "").strip()
    if not value or Path(value).is_absolute():
        raise EvidenceError(f"evidence path must be repository-relative: {value!r}")
    try:
        resolved = (repo_root / value).resolve(strict=True)
    except OSError as exc:
        raise EvidenceError(f"evidence path does not exist: {value}") from exc
    if not resolved.is_relative_to(repo_root):
        raise EvidenceError(f"evidence path escapes the repository: {value}")
    return resolved.relative_to(repo_root).as_posix(), resolved


def _path_content_digest(repo_root: Path, path: Path) -> str:
    if path.is_file():
        return hashlib.sha256(path.read_bytes()).hexdigest()
    if not path.is_dir():
        raise EvidenceError(f"unsupported evidence path type: {path}")

    rows: list[str] = []
    for child in sorted(item for item in path.rglob("*") if item.is_file()):
        resolved = child.resolve(strict=True)
        if not resolved.is_relative_to(repo_root):
            raise EvidenceError(f"evidence directory contains an escaping symlink: {child}")
        relative = resolved.relative_to(repo_root).as_posix()
        digest = hashlib.sha256(resolved.read_bytes()).hexdigest()
        rows.append(f"{relative}\t{digest}\n")
    return hashlib.sha256("".join(rows).encode("utf-8")).hexdigest()


def _repository_digest(repo_root: Path, paths: list[str]) -> str:
    rows: list[str] = []
    for relative in sorted(set(paths)):
        path = repo_root / relative
        rows.append(f"{relative}\t{_path_content_digest(repo_root, path)}\n")
    return hashlib.sha256("".join(rows).encode("utf-8")).hexdigest()


def _filter_context_paths(
    payload: dict[str, Any], repo_root: Path
) -> tuple[list[str], list[str]]:
    retained: list[str] = []
    removed: list[str] = []

    for field in ("primary_files", "test_files"):
        normalized: list[str] = []
        for raw_path in payload.get(field) or []:
            try:
                relative, _ = _contained_path(repo_root, raw_path)
            except EvidenceError:
                removed.append(str(raw_path))
                continue
            normalized.append(relative)
            retained.append(relative)
        payload[field] = sorted(set(normalized))

    normalized_symbols: list[dict[str, Any]] = []
    for item in payload.get("symbols") or []:
        if not isinstance(item, dict):
            continue
        try:
            relative, _ = _contained_path(repo_root, item.get("file"))
        except EvidenceError:
            removed.append(str(item.get("file") or "<missing-symbol-file>"))
            continue
        normalized = dict(item)
        normalized["file"] = relative
        normalized_symbols.append(normalized)
        retained.append(relative)
    payload["symbols"] = normalized_symbols
    return retained, sorted(set(removed))


def _spec_review_paths(payload: dict[str, Any], repo_root: Path) -> list[str]:
    context = payload.get("repository_context")
    if not isinstance(context, dict):
        raise EvidenceError("spec_review evidence is missing repository_context")

    retained: list[str] = []
    for field in ("standards", "adrs", "source", "tests"):
        normalized: list[str] = []
        for raw_path in context.get(field) or []:
            relative, _ = _contained_path(repo_root, raw_path)
            normalized.append(relative)
            retained.append(relative)
        context[field] = sorted(set(normalized))
    return retained


def normalize_evidence(
    payload: dict[str, Any],
    *,
    repo_root: Path,
    role: str,
    bead_content_digest: str,
    contract_digest: str,
    model: str,
) -> dict[str, Any]:
    """Validate identity fields, normalize paths, and attest repository content."""
    repo_root = repo_root.resolve(strict=True)
    expected_agent = ROLE_AGENTS.get(role)
    if expected_agent is None:
        raise EvidenceError(f"unsupported claim evidence role: {role}")
    if str(payload.get("role") or "") != role:
        raise EvidenceError("agent evidence role does not match the prepared action")
    if str(payload.get("agent") or "") != expected_agent:
        raise EvidenceError("agent evidence identity does not match the prepared action")
    if str(payload.get("bead_content_digest") or "") != bead_content_digest:
        raise EvidenceError("agent evidence targets another bead revision")
    if str(payload.get("contract_digest") or "") != contract_digest:
        raise EvidenceError("agent evidence uses another installed contract")
    verdict = str(payload.get("verdict") or "").lower()
    if verdict not in READY_VERDICTS:
        raise EvidenceError(f"unsupported evidence verdict: {verdict!r}")
    if not model.strip():
        raise EvidenceError("the harness must supply the resolved runtime model")

    normalized = dict(payload)
    if role == "context_discovery":
        evidence_paths, removed = _filter_context_paths(normalized, repo_root)
        if removed:
            gaps = [str(item) for item in normalized.get("gaps") or []]
            gaps.append("Discarded missing or out-of-repository candidate paths: " + ", ".join(removed))
            normalized["gaps"] = gaps
            if verdict == "ready":
                normalized["verdict"] = "ready_with_warnings"
    else:
        evidence_paths = _spec_review_paths(normalized, repo_root)

    if not evidence_paths:
        raise EvidenceError("agent evidence contains no verified repository paths")
    normalized["model"] = model.strip()
    normalized["repository_context_digest"] = _repository_digest(repo_root, evidence_paths)
    return normalized


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", required=True, type=Path)
    parser.add_argument("--role", required=True, choices=sorted(ROLE_AGENTS))
    parser.add_argument("--bead-content-digest", required=True)
    parser.add_argument("--contract-digest", required=True)
    parser.add_argument("--model", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        payload = extract_json_object(sys.stdin.read())
        normalized = normalize_evidence(
            payload,
            repo_root=args.repo_root,
            role=args.role,
            bead_content_digest=args.bead_content_digest,
            contract_digest=args.contract_digest,
            model=args.model,
        )
    except (EvidenceError, OSError) as exc:
        print(f"CLAIM_EVIDENCE_INVALID: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(normalized, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

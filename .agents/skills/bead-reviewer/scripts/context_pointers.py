#!/usr/bin/env python3
"""Parse and review bead description Context Pointers blocks."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


LIST_FIELDS = ("primary_files", "test_files", "symbols")
SCALAR_FIELDS = ("memory_search",)
KNOWN_FIELDS = set(LIST_FIELDS + SCALAR_FIELDS)
BLOCK_PATTERN = re.compile(
    r"(?ms)^##\s+Context Pointers\s*$\n?(.*?)(?=^##\s+\S|\Z)"
)
FIELD_PATTERN = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*):(?:\s*(.*))?$")


def parse_context_pointers_block(description: str) -> dict[str, Any] | None:
    """Return parsed Context Pointers data or None when the block is absent."""
    match = BLOCK_PATTERN.search(description)
    if match is None:
        return None

    parsed: dict[str, Any] = {
        "primary_files": [],
        "test_files": [],
        "symbols": [],
        "memory_search": None,
    }
    current_list: str | None = None

    for raw_line in match.group(1).splitlines():
        stripped = raw_line.strip()
        if not stripped:
            continue

        field_match = FIELD_PATTERN.match(raw_line)
        if field_match and field_match.group(1) in KNOWN_FIELDS:
            field = field_match.group(1)
            value = (field_match.group(2) or "").strip()
            if field in LIST_FIELDS:
                current_list = field
                if value:
                    parsed[field].append(_normalize_list_item(value))
            else:
                current_list = None
                parsed[field] = _strip_quotes(value)
            continue

        if current_list is None:
            continue

        if not _looks_like_list_item(raw_line):
            continue

        parsed[current_list].append(_normalize_list_item(stripped))

    return parsed


def review_context_pointers(bead: dict[str, Any], repo_root: Path) -> dict[str, Any]:
    """Validate Context Pointers presence and referenced file paths."""
    description = bead.get("description") or ""
    parsed = parse_context_pointers_block(description)

    if parsed is None:
        if _is_factory_ready(bead):
            return {
                "verdict": "BLOCKING",
                "pointers": None,
                "findings": [
                    {
                        "code": "MISSING_CONTEXT_POINTERS",
                        "severity": "blocking",
                        "message": (
                            "Factory-ready bead is missing a `## Context Pointers` "
                            "block. Add the canonical schema from "
                            "`standards/beads/context-pointers.md`."
                        ),
                    }
                ],
            }

        return {
            "verdict": "ADVISORY",
            "pointers": None,
            "findings": [
                {
                    "code": "MISSING_CONTEXT_POINTERS",
                    "severity": "advisory",
                    "message": (
                        "No `## Context Pointers` block found; fall back to dynamic "
                        "context discovery."
                    ),
                }
            ],
        }

    findings: list[dict[str, Any]] = []
    root_resolved = Path(repo_root).resolve()

    # Build sanitized pointers — only safe, repo-contained paths are included.
    # Paths that are absolute or escape the repo root are excluded from the
    # returned pointers so downstream consumers (orchestrator Phase 1) cannot
    # be steered outside the repository.  Paths that are within the repo but
    # simply missing from disk are warned about but still included (the file
    # may be created later in the same bead; the pointer is safe).
    sanitized: dict[str, Any] = {
        "primary_files": [],
        "test_files": [],
        "symbols": parsed["symbols"],
        "memory_search": parsed["memory_search"],
    }

    for field in ("primary_files", "test_files"):
        for relative_path in parsed[field]:
            # Reject absolute paths immediately — all pointers must be repo-relative
            # (per standards/beads/context-pointers.md).  Do NOT remap or perform an
            # existence check: an absolute path is always invalid regardless of whether
            # a matching relative path happens to exist under the repo root.
            if Path(relative_path).is_absolute():
                findings.append(
                    {
                        "code": "CONTEXT_POINTER_PATH_NOT_FOUND",
                        "severity": "warning",
                        "path": relative_path,
                        "field": field,
                        "message": (
                            f"Context pointer path `{relative_path}` is absolute. "
                            "All paths must be relative to the repo root."
                        ),
                    }
                )
                continue

            resolved = _resolve_repo_path(repo_root, relative_path)

            # Containment check — path traversal sequences (e.g. `../sibling/file`)
            # can escape the repo root even when the raw path is relative.  Resolve
            # symlinks and verify the canonical path is inside the repo root before
            # allowing the pointer through.
            try:
                canonical = resolved.resolve()
                if not canonical.is_relative_to(root_resolved):
                    findings.append(
                        {
                            "code": "CONTEXT_POINTER_PATH_ESCAPE",
                            "severity": "warning",
                            "path": relative_path,
                            "field": field,
                            "message": (
                                f"Context pointer path `{relative_path}` resolves outside "
                                "the repo root. Path traversal pointers are not allowed."
                            ),
                        }
                    )
                    continue
            except (OSError, ValueError):
                findings.append(
                    {
                        "code": "CONTEXT_POINTER_PATH_NOT_FOUND",
                        "severity": "warning",
                        "path": relative_path,
                        "field": field,
                        "message": (
                            f"Context pointer path `{relative_path}` could not be resolved."
                        ),
                    }
                )
                continue

            if not canonical.exists():
                findings.append(
                    {
                        "code": "CONTEXT_POINTER_PATH_NOT_FOUND",
                        "severity": "warning",
                        "path": relative_path,
                        "field": field,
                        "message": (
                            f"Context pointer path `{relative_path}` does not exist "
                            "relative to the repo root."
                        ),
                    }
                )

            # Include path even when it doesn't exist yet — it is safe (within repo)
            # and the orchestrator may need it as a hint for files to be created.
            sanitized[field].append(relative_path)

    verdict = "CLEAN" if not findings else "FINDING"
    return {"verdict": verdict, "pointers": sanitized, "findings": findings}


def _normalize_list_item(value: str) -> str:
    stripped = value.strip()
    if stripped.startswith("- "):
        stripped = stripped[2:]
    elif stripped == "-":
        stripped = ""
    return _strip_quotes(stripped.strip())


def _looks_like_list_item(raw_line: str) -> bool:
    stripped = raw_line.strip()
    if stripped.startswith("- "):
        return True
    return bool(raw_line[:1].isspace())


def _strip_quotes(value: str) -> str:
    stripped = value.strip()
    if len(stripped) >= 2 and stripped[0] == stripped[-1] and stripped[0] in {'"', "'"}:
        return stripped[1:-1]
    return stripped


def _resolve_repo_path(repo_root: Path | str, relative_path: str) -> Path:
    """Return the absolute path for a repo-relative pointer.

    Absolute paths are rejected: per the canonical schema, all Context Pointer
    paths MUST be relative to the repo root.  Returning an absolute path as-is
    would silently bypass repo-root validation (e.g. ``/etc/passwd`` would pass
    an existence check even though it is clearly not a source file).
    """
    root = Path(repo_root)
    path = Path(relative_path)
    if path.is_absolute():
        # Treat absolute paths as invalid relative paths; the caller will then
        # emit a warning finding because root / <stripped> will not match any
        # real source file inside the repo.
        return root / relative_path.lstrip("/")
    return root / path


def _is_factory_ready(bead: dict[str, Any]) -> bool:
    metadata = bead.get("metadata") or {}
    if _truthy(metadata.get("factory_ready")):
        return True
    labels = bead.get("labels") or []
    return any(label == "factory:ready" for label in labels)


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _load_bead(args: argparse.Namespace) -> dict[str, Any]:
    if args.description is not None:
        return {
            "description": args.description,
            "labels": args.labels or [],
            "metadata": {"factory_ready": args.factory_ready},
        }

    if args.bead_json is not None:
        payload = json.loads(args.bead_json)
    else:
        payload = json.load(sys.stdin)

    return payload[0] if isinstance(payload, list) else payload


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Parse and validate bead Context Pointers blocks"
    )
    parser.add_argument(
        "--repo-root",
        default=".",
        help="Repository root used for primary_files/test_files existence checks",
    )
    parser.add_argument(
        "--bead-json",
        help="Bead JSON payload (defaults to stdin)",
    )
    parser.add_argument(
        "--description",
        help="Raw bead description for parse-only or ad hoc review mode",
    )
    parser.add_argument(
        "--label",
        action="append",
        dest="labels",
        help="Label values used with --description mode",
    )
    parser.add_argument(
        "--factory-ready",
        action="store_true",
        help="Mark the bead as factory-ready in --description mode",
    )
    parser.add_argument(
        "--parse-only",
        action="store_true",
        help="Emit only the parsed Context Pointers payload",
    )
    args = parser.parse_args()

    bead = _load_bead(args)
    repo_root = Path(args.repo_root).resolve()

    if args.parse_only:
        parsed = parse_context_pointers_block(bead.get("description") or "")
        print(json.dumps(parsed))
        return 0

    review = review_context_pointers(bead, repo_root=repo_root)
    print(json.dumps(review))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

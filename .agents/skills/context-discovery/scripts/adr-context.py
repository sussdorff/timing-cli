#!/usr/bin/env -S uv run --quiet --script
# /// script
# dependencies = [
#   "pyyaml>=6.0",
# ]
# ///
"""
adr-context.py — Discover, inject, and verify ADR constraints for a bead.

Three subcommands:
  discover  — find ADRs in scope based on changed paths and bead description
  inject    — format relevant ADRs as a markdown block for implementer prompts
  verify    — re-discover ADRs from a diff range and check for violations

Output: execution-result envelope (core/contracts/execution-result.schema.json)

Usage:
  uv run core/scripts/adr-context.py discover --bead=<id> [--changed-paths=p1,p2] --output=json
  uv run core/scripts/adr-context.py inject --bead=<id> --output=markdown
  uv run core/scripts/adr-context.py verify --bead=<id> --diff=<git-range> --output=json
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import subprocess
import sys
import tomllib
from pathlib import Path
from typing import Any

import yaml

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_PRODUCER = "adr-context.py"


def _issue_tracker_name(repo_root: str | Path | None = None) -> str | None:
    override = os.environ.get("COGNOVIS_BEADS_REGISTRY")
    registry = Path(override).expanduser() if override else (
        Path(os.environ.get("XDG_CONFIG_HOME") or (Path.home() / ".config"))
        / "cognovis" / "beads-repos.toml"
    )
    try:
        loaded = tomllib.loads(registry.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return None
    checkout = Path(repo_root or Path.cwd()).expanduser().resolve()
    for entry in loaded.get("repository", []):
        raw = entry.get("path")
        if not raw:
            continue
        try:
            entry_path = Path(str(raw)).expanduser().resolve()
        except OSError:
            continue
        if entry_path != checkout:
            continue
        name = str(entry.get("tracker") or "").strip()
        if name in {"github", "forgejo"}:
            return name
        return None
    return None
_CONTRACT_VERSION = "1"
_SCHEMA_PATH = "core/contracts/execution-result.schema.json"
_MAX_ADR_BLOCK_CHARS = 2048
_ADR_NUMERIC_FILENAME_ID_RE = re.compile(r"^(ADR-\d+)(?:[-_.]|$)", re.IGNORECASE)
_ADR_SLUG_FILENAME_ID_RE = re.compile(r"^(adr-[a-z0-9]+(?:-[a-z0-9]+)*)$")
_CONTRACT_SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class AdrIdentityCollisionError(ValueError):
    """Raised when multiple ADR files declare the same stable identity."""


# ---------------------------------------------------------------------------
# Execution-result envelope
# ---------------------------------------------------------------------------


def _envelope(
    status: str,
    summary: str,
    data: dict[str, Any],
    errors: list[dict[str, Any]] | None = None,
    next_steps: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Wrap a result payload in the canonical execution-result envelope."""
    return {
        "status": status,
        "summary": summary,
        "data": data,
        "errors": errors or [],
        "next_steps": next_steps or [],
        "open_items": [],
        "meta": {
            "contract_version": _CONTRACT_VERSION,
            "producer": _PRODUCER,
            "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "schema": _SCHEMA_PATH,
        },
    }


# ---------------------------------------------------------------------------
# ADR frontmatter parsing
# ---------------------------------------------------------------------------


def _numeric_adr_id_from_filename(adr_path: Path) -> str | None:
    """Derive the legacy canonical identity from an ``ADR-<digits>`` prefix."""
    match = _ADR_NUMERIC_FILENAME_ID_RE.match(adr_path.stem)
    return match.group(1).upper() if match is not None else None


def _contract_adr_id(contract: Any) -> str | None:
    """Normalize one valid contract slug to the non-numeric ADR namespace."""
    if not isinstance(contract, str) or _CONTRACT_SLUG_RE.fullmatch(contract) is None:
        return None
    return contract if contract.startswith("adr-") else f"adr-{contract}"


def _slug_adr_id_from_filename(adr_path: Path) -> str | None:
    """Derive identity from a canonical lowercase ``adr-<slug>.md`` filename."""
    match = _ADR_SLUG_FILENAME_ID_RE.fullmatch(adr_path.stem)
    return match.group(1) if match is not None else None


def _as_string_list(value: Any) -> list[Any]:
    """Normalize a contract-legal scalar or list field to a list.

    Frontmatter ``applies_to`` and ``prohibits`` may be a string or a list.
    Callers iterate these fields; a scalar must not be walked as characters.
    """
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return list(value)
    return []


def parse_adr_frontmatter(adr_path: Path) -> dict[str, Any] | None:
    """Parse YAML frontmatter from an ADR markdown file.

    Returns a dict with keys: id, status, date, applies_to, prohibits,
    decision_summary, path — or None if no frontmatter is found. An explicit
    frontmatter ``id`` takes precedence. Numeric ``ADR-<digits>`` filenames
    retain their legacy identity. Non-numeric ADRs use a validated contract
    slug, normalized once into the ``adr-<slug>`` namespace, then fall back to
    a canonical lowercase ``adr-<slug>.md`` filename.
    """
    text = adr_path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return None
    # Extract the YAML block between the first --- delimiters
    end = text.find("---", 3)
    if end == -1:
        return None
    yaml_block = text[3:end].strip()
    try:
        loaded_meta = yaml.safe_load(yaml_block) or {}
    except yaml.YAMLError:
        return None
    if not isinstance(loaded_meta, dict):
        return None
    meta: dict[str, Any] = loaded_meta
    if "id" in meta:
        explicit_id = meta["id"]
        if not isinstance(explicit_id, str) or not explicit_id.strip():
            return None
        meta["id"] = explicit_id.strip()
    else:
        numeric_id = _numeric_adr_id_from_filename(adr_path)
        contract_id = _contract_adr_id(meta.get("contract")) if "contract" in meta else None
        filename_id = _slug_adr_id_from_filename(adr_path)
        if "contract" in meta and contract_id is None:
            return None
        derived_id = numeric_id or contract_id or filename_id
        if derived_id is None:
            return None
        meta["id"] = derived_id
    meta["path"] = str(adr_path)
    meta["applies_to"] = _as_string_list(meta.get("applies_to", []))
    meta["prohibits"] = _as_string_list(meta.get("prohibits", []))
    meta.setdefault("decision_summary", "")
    return meta


def _load_adrs(adr_dir: Path) -> list[dict[str, Any]]:
    """Walk adr_dir recursively and return all parsed ADR frontmatter dicts.

    Uses rglob (recursive) to match the previous orchestrator fallback behavior
    of `find docs/adr/ -name "*.md"`, which finds ADRs in subdirectories too.
    """
    adrs: list[dict[str, Any]] = []
    identity_paths: dict[str, str] = {}
    for md_file in sorted(adr_dir.rglob("*.md")):
        if md_file.stem.startswith("_"):
            continue
        parsed = parse_adr_frontmatter(md_file)
        if parsed is not None:
            adr_id = parsed["id"]
            if adr_id in identity_paths:
                raise AdrIdentityCollisionError(
                    f"Duplicate ADR identity {adr_id!r}: "
                    f"{identity_paths[adr_id]} and {parsed['path']}"
                )
            identity_paths[adr_id] = parsed["path"]
            adrs.append(parsed)
    return adrs


# ---------------------------------------------------------------------------
# Path glob matching
# ---------------------------------------------------------------------------


def _glob_to_regex(pattern: str) -> str:
    """Translate a path glob pattern into an anchored regex.

    Semantics:
      - `**` matches zero-or-more path segments (Bash globstar / .gitignore)
      - `*`  matches any characters within a single path segment (no `/`)
      - `?`  matches a single character within a segment
      - `/`  is a literal path separator
      - all other regex metacharacters are escaped

    Examples:
      core/**/*.py  → ^core(?:/.*)?/[^/]*\\.py$   (matches core/foo.py and core/a/b/foo.py)
      scripts/*.py  → ^scripts/[^/]*\\.py$        (matches scripts/foo.py only)
      **/*.md       → ^(?:.*/)?[^/]*\\.md$        (matches foo.md and a/b/foo.md)
    """
    # Tokenize: handle `**/`, `**`, `*`, `?`, and other characters
    out: list[str] = []
    i = 0
    n = len(pattern)
    while i < n:
        c = pattern[i]
        if pattern[i : i + 3] == "**/":
            # zero-or-more path segments followed by separator
            out.append("(?:.*/)?")
            i += 3
        elif pattern[i : i + 2] == "**":
            # zero-or-more characters incl. separators
            out.append(".*")
            i += 2
        elif c == "*":
            # any characters except separator
            out.append("[^/]*")
            i += 1
        elif c == "?":
            out.append("[^/]")
            i += 1
        else:
            out.append(re.escape(c))
            i += 1
    return "^" + "".join(out) + "$"


def _repo_root_from_adr_dir(adr_dir: Path) -> Path | None:
    """Derive repository root when adr_dir is the conventional docs/adr path."""
    resolved = adr_dir.resolve()
    if resolved.name == "adr" and resolved.parent.name == "docs":
        return resolved.parent.parent
    return None


def _matches_glob(
    path: str, pattern: str, *, repo_root: Path | None = None
) -> bool:
    """Return True if path matches the given glob pattern.

    `**` semantics: a `**` segment matches zero-or-more path segments
    (matching common .gitignore / Bash globstar semantics), so
    `core/**/*.py` matches both `core/foo.py` and `core/a/b/foo.py`.

    `*` matches within a single path segment (does NOT cross `/`), so
    `scripts/*.py` matches `scripts/foo.py` but NOT `scripts/sub/foo.py`.

    Blank selectors (no `/` and no glob tokens) resolve only when the
    corresponding workspace package directory `packages/<selector>` exists
    under ``repo_root``. They then match that directory and its descendants.
    This is not a basename heuristic: unrelated paths containing the token
    do not match.

    Implemented via _glob_to_regex because Python 3.12's
    PurePosixPath.match only matches `**` against exactly one segment
    (zero-segment case and 2+ segment cases both fail), which would skip
    ADRs with common recursive `applies_to` globs.
    """
    normalized_path = path.replace("\\", "/").removeprefix("./").rstrip("/")
    normalized_pattern = pattern.replace("\\", "/").removeprefix("./").rstrip("/")
    if not normalized_pattern:
        return False
    if not any(token in normalized_pattern for token in ("*", "?", "[")):
        if (
            normalized_path == normalized_pattern
            or normalized_path.startswith(f"{normalized_pattern}/")
        ):
            return True
        # Documented blank workspace-package selector, e.g. `pvs-x-isynet`.
        if (
            repo_root is not None
            and "/" not in normalized_pattern
            and (repo_root / "packages" / normalized_pattern).is_dir()
        ):
            package_prefix = f"packages/{normalized_pattern}"
            return (
                normalized_path == package_prefix
                or normalized_path.startswith(f"{package_prefix}/")
            )
        return False
    return re.match(_glob_to_regex(normalized_pattern), normalized_path) is not None


def _path_matches_adr(
    changed_paths: list[str],
    applies_to: list[str],
    *,
    repo_root: Path | None = None,
) -> bool:
    """Return True if any changed path matches any applies_to glob."""
    for path in changed_paths:
        for pattern in applies_to:
            if _matches_glob(path, pattern, repo_root=repo_root):
                return True
    return False


# ---------------------------------------------------------------------------
# Bead description fetching
# ---------------------------------------------------------------------------


def _fetch_bead_description(bead_id: str) -> str | None:
    """Fetch bead description text via `bd show <id>`.

    Returns the output string, or None on any failure.
    """
    try:
        tracker = _issue_tracker_name(Path.cwd())
        if not tracker:
            argv = ["bd", "show", bead_id]
        else:
            argv = ["ccore", "tracker", "show", bead_id]
        result = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=15,
        )
        if result.returncode == 0:
            return result.stdout
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass
    return None


# ---------------------------------------------------------------------------
# Core logic: discover
# ---------------------------------------------------------------------------


def discover_adrs(
    *,
    adr_dir: Path,
    changed_paths: list[str],
    bead_description_override: str | None,
    bead_id: str | None = None,
    repo_root: Path | None = None,
    _adrs: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Discover ADRs in scope for a bead.

    Args:
        adr_dir: Directory containing ADR markdown files.
        changed_paths: List of file paths that changed (from git diff or CLI).
        bead_description_override: Pre-fetched bead description (for testing).
            If None and bead_id is given, attempts to call `bd show <bead_id>`.
        bead_id: Bead identifier used to fetch description when override is None.
        repo_root: Optional repository root used to resolve blank package
            selectors against real ``packages/<name>`` directories. When omitted,
            derived from the conventional ``docs/adr`` location of ``adr_dir``.
        _adrs: Optional pre-loaded ADR list (avoids re-reading disk when the
            caller has already called _load_adrs). Internal use only.

    Returns:
        List of ADR dicts with keys: id, path, decision_summary, match_reason.
    """
    adrs = _adrs if _adrs is not None else _load_adrs(adr_dir)
    resolved_repo_root = (
        repo_root.resolve() if repo_root is not None else _repo_root_from_adr_dir(adr_dir)
    )

    # Determine bead description text for text-based matching
    if bead_description_override is not None:
        bead_text: str | None = bead_description_override
    elif bead_id is not None:
        bead_text = _fetch_bead_description(bead_id)
    else:
        bead_text = None

    seen_ids: set[str] = set()
    results: list[dict[str, Any]] = []

    for adr in adrs:
        adr_id: str = adr["id"]
        match_reason: str | None = None
        match_reasons: list[str] = []

        # Path-based matching
        matching_selectors = sorted(
            {
                str(pattern)
                for path in changed_paths
                for pattern in adr["applies_to"]
                if _matches_glob(path, str(pattern), repo_root=resolved_repo_root)
            }
        )
        if matching_selectors:
            match_reason = "path"
            match_reasons.extend(f"path:{selector}" for selector in matching_selectors)

        # Text-based matching (bead description references the ADR id)
        if bead_text and re.search(rf"\b{re.escape(adr_id)}\b", bead_text, re.IGNORECASE):
            match_reasons.append(f"bead:{adr_id}")
            if match_reason is None:
                match_reason = "text"
            else:
                match_reason = "path+text"

        if match_reason is not None and adr_id not in seen_ids:
            seen_ids.add(adr_id)
            results.append(
                {
                    "id": adr_id,
                    "path": adr["path"],
                    "decision_summary": adr["decision_summary"],
                    "match_reason": match_reason,
                    "match_reasons": match_reasons,
                    "prohibits": _as_string_list(adr.get("prohibits", [])),
                    # Lifecycle and decided topic travel with the record so a
                    # caller can compare decisions without re-reading the file.
                    "status": str(adr.get("status") or "").strip(),
                    "decides": str(adr.get("decides") or "").strip(),
                }
            )

    return results


def discover_adrs_envelope(
    *,
    adr_dir: Path,
    changed_paths: list[str],
    bead_description_override: str | None,
    bead_id: str | None = None,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    """Run discover and return execution-result envelope."""
    adrs_in_scope = discover_adrs(
        adr_dir=adr_dir,
        changed_paths=changed_paths,
        bead_description_override=bead_description_override,
        bead_id=bead_id,
        repo_root=repo_root,
    )
    count = len(adrs_in_scope)
    return _envelope(
        status="ok",
        summary=f"Discovered {count} ADR(s) in scope.",
        data={"adrs_in_scope": adrs_in_scope},
    )


# ---------------------------------------------------------------------------
# Core logic: inject
# ---------------------------------------------------------------------------


def _format_adr_block(adr_meta: dict[str, Any], adr_id: str) -> str:
    """Format a single ADR as a markdown section, truncated to _MAX_ADR_BLOCK_CHARS."""
    prohibitions = "\n".join(f"- {p}" for p in adr_meta.get("prohibits", []))
    block = (
        f"### {adr_id} — {adr_meta['decision_summary']}\n"
        f"Prohibits:\n{prohibitions}\n"
        f"Read: {adr_meta['path']}\n"
    )
    if len(block) > _MAX_ADR_BLOCK_CHARS:
        block = block[: _MAX_ADR_BLOCK_CHARS - 3] + "..."
    return block


def inject_adrs_envelope(
    *,
    adr_dir: Path,
    changed_paths: list[str],
    bead_description_override: str | None,
    bead_id: str | None = None,
) -> dict[str, Any]:
    """Discover ADRs and format them as an injected markdown block.

    Returns execution-result envelope with data.markdown.
    """
    # Load ADR metadata once — reused for both discovery and formatting.
    all_adrs_list = _load_adrs(adr_dir)
    all_adrs = {a["id"]: a for a in all_adrs_list}

    adrs_in_scope = discover_adrs(
        adr_dir=adr_dir,
        changed_paths=changed_paths,
        bead_description_override=bead_description_override,
        bead_id=bead_id,
        _adrs=all_adrs_list,
    )

    if not adrs_in_scope:
        markdown = "No ADRs in scope for this bead."
        summary = "No ADRs in scope."
    else:
        # Use already-loaded full metadata for each ADR to format prohibitions
        sections: list[str] = ["## ADR Constraints (mandatory)\n"]
        for entry in adrs_in_scope:
            adr_id = entry["id"]
            meta = all_adrs.get(adr_id, {"decision_summary": entry["decision_summary"], "prohibits": [], "path": entry["path"]})
            sections.append(_format_adr_block(meta, adr_id))
        markdown = "\n".join(sections)
        summary = f"Injected {len(adrs_in_scope)} ADR constraint(s)."

    return _envelope(
        status="ok",
        summary=summary,
        data={"markdown": markdown},
    )


# ---------------------------------------------------------------------------
# Core logic: verify
# ---------------------------------------------------------------------------


def _diff_without_file(diff_text: str, excluded_path: str) -> str:
    """Remove one file's git-diff section while preserving all other evidence."""
    excluded = Path(excluded_path)
    excluded_paths = {excluded.as_posix().removeprefix("./")}
    if excluded.is_absolute():
        try:
            excluded_paths.add(excluded.relative_to(Path.cwd()).as_posix())
        except ValueError:
            pass
    sections = re.split(r"(?=^diff --git )", diff_text, flags=re.MULTILINE)
    retained: list[str] = []

    for section in sections:
        header = section.splitlines()[0] if section else ""
        match = re.match(r"^diff --git a/(.+) b/(.+)$", header)
        if match is None:
            retained.append(section)
            continue

        old_path, new_path = match.groups()
        section_paths = (old_path, new_path)
        is_excluded = any(path in excluded_paths for path in section_paths)
        if not is_excluded:
            retained.append(section)

    return "".join(retained)


def verify_adrs_envelope(
    *,
    adr_dir: Path,
    changed_paths: list[str],
    diff_text: str,
    bead_description_override: str | None,
    bead_id: str | None = None,
) -> dict[str, Any]:
    """Re-discover ADRs from diff and check prohibitions against diff_text.

    Does NOT accept caller-provided adrs_in_scope — always re-discovers.

    Returns execution-result envelope with:
        data.verdict: "VERIFIED" or "DISPUTED"
        data.discovered_adrs: list of {id, path, decision_summary}
        data.violations: list of {adr, rule, evidence, fixability}
    """
    # Load once — reused for both discovery and violation checking.
    all_adrs_list = _load_adrs(adr_dir)
    all_adrs = {a["id"]: a for a in all_adrs_list}

    # Always re-discover from changed_paths (ignores caller-supplied provenance)
    adrs_in_scope = discover_adrs(
        adr_dir=adr_dir,
        changed_paths=changed_paths,
        bead_description_override=bead_description_override,
        bead_id=bead_id,
        _adrs=all_adrs_list,
    )

    discovered_adrs: list[dict[str, Any]] = [
        {"id": a["id"], "path": a["path"], "decision_summary": a["decision_summary"]}
        for a in adrs_in_scope
    ]

    violations: list[dict[str, Any]] = []
    for entry in adrs_in_scope:
        adr_id = entry["id"]
        meta = all_adrs.get(adr_id, {})
        prohibits: list[str] = meta.get("prohibits", [])
        # An ADR defining or changing its guardrails is not evidence that the
        # implementation violates those guardrails. Keep every other file's
        # diff section available to the existing text heuristic.
        evidence_diff_lower = _diff_without_file(diff_text, meta.get("path", "")).lower()
        for rule in prohibits:
            # Design note: violation detection uses prohibition prose as a
            # heuristic — it only catches violations where the diff contains
            # the prohibition text verbatim (typically as a comment quoting the
            # rule). It does NOT analyze code semantics, so for example a
            # prohibition "Do not use httpx" will not detect a bare
            # `import httpx` line unless the diff also contains the prose.
            # For structural violation detection, extend ADR frontmatter with a
            # `pattern:` field and check that instead. This is documented in
            # the `verify` subparser --help description.
            key = rule[:60].lower()
            if key and key in evidence_diff_lower:
                violations.append(
                    {
                        "adr": adr_id,
                        "rule": rule,
                        "evidence": f"Prohibited pattern found in diff: {rule[:80]}",
                        "fixability": "human",
                    }
                )

    verdict = "DISPUTED" if violations else "VERIFIED"
    status = "warning" if violations else "ok"
    summary = (
        f"Verification {verdict}: {len(violations)} violation(s) found across "
        f"{len(discovered_adrs)} discovered ADR(s)."
    )

    return _envelope(
        status=status,
        summary=summary,
        data={
            "verdict": verdict,
            "discovered_adrs": discovered_adrs,
            "violations": violations,
        },
    )


# ---------------------------------------------------------------------------
# Git helpers for CLI mode
# ---------------------------------------------------------------------------


def _git_changed_paths(diff_range: str | None = None) -> list[str]:
    """Return list of changed file paths from git diff.

    If diff_range is None, uses 'main...HEAD'.
    """
    range_arg = diff_range or "main...HEAD"
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", range_arg],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if result.returncode == 0:
            return [p for p in result.stdout.splitlines() if p.strip()]
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass
    return []


def _git_diff_text(diff_range: str) -> str:
    """Return full git diff text for the given range."""
    try:
        result = subprocess.run(
            ["git", "diff", diff_range],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            return result.stdout
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass
    return ""


def _find_adr_dir() -> Path | None:
    """Locate docs/adr/ relative to cwd or repo root."""
    candidates = [
        Path("docs/adr"),
        Path(".") / "docs" / "adr",
    ]
    for c in candidates:
        if c.is_dir():
            return c
    return None


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="ADR context helper for bead orchestration")
    sub = parser.add_subparsers(dest="command", required=True)

    # discover
    p_discover = sub.add_parser("discover", help="Discover ADRs in scope")
    p_discover.add_argument("--bead", default=None, help="Bead ID for text-matching")
    p_discover.add_argument("--changed-paths", default=None, help="Comma-separated list of changed paths")
    p_discover.add_argument("--output", default="json", choices=["json", "paths"])
    p_discover.add_argument("--adr-dir", default=None, help="Path to ADR directory (default: docs/adr/)")
    p_discover.add_argument(
        "--repo-root",
        default=None,
        help=(
            "Repository whose changed paths are matched. Defaults to the root derived "
            "from --adr-dir; supply it when the corpus belongs to a governing repository"
        ),
    )
    p_discover.add_argument(
        "--request-stdin",
        action="store_true",
        help="Read changed_paths and bead_description from one JSON object on stdin",
    )

    # inject
    p_inject = sub.add_parser("inject", help="Inject ADR constraints as markdown")
    p_inject.add_argument("--bead", default=None, help="Bead ID")
    p_inject.add_argument("--changed-paths", default=None, help="Comma-separated list of changed paths")
    p_inject.add_argument("--output", default="markdown", choices=["markdown", "json"])
    p_inject.add_argument("--adr-dir", default=None, help="Path to ADR directory")

    # verify
    p_verify = sub.add_parser(
        "verify",
        help=(
            "Verify ADR compliance against a diff. "
            "Heuristic: detects violations when diff contains prohibition text verbatim."
        ),
    )
    p_verify.add_argument("--bead", default=None, help="Bead ID")
    p_verify.add_argument("--diff", default="main...HEAD", help="Git diff range")
    p_verify.add_argument("--output", default="json", choices=["json"])
    p_verify.add_argument("--adr-dir", default=None, help="Path to ADR directory")

    args = parser.parse_args()

    # Resolve ADR directory
    if hasattr(args, "adr_dir") and args.adr_dir:
        adr_dir = Path(args.adr_dir)
    else:
        adr_dir = _find_adr_dir()

    if adr_dir is None or not adr_dir.is_dir():
        result = _envelope(
            status="error",
            summary="ADR directory not found. Expected docs/adr/.",
            data={"adrs_in_scope": []},
            errors=[{"code": "ADR_DIR_NOT_FOUND", "message": "docs/adr/ not found"}],
        )
        print(json.dumps(result, indent=2))
        return

    request: dict[str, Any] = {}
    if getattr(args, "request_stdin", False):
        try:
            request = json.load(sys.stdin)
        except (json.JSONDecodeError, OSError) as exc:
            parser.error(f"invalid --request-stdin JSON: {exc}")
        if not isinstance(request, dict):
            parser.error("--request-stdin requires a JSON object")

    # Resolve changed paths from CLI, stdin, or git
    changed_paths: list[str] = []
    request_paths = request.get("changed_paths")
    if isinstance(request_paths, list) and all(
        isinstance(path, str) for path in request_paths
    ):
        changed_paths = [path for path in request_paths if path.strip()]
    elif hasattr(args, "changed_paths") and args.changed_paths:
        changed_paths = [p.strip() for p in args.changed_paths.split(",") if p.strip()]
    elif args.command in ("discover", "inject"):
        changed_paths = _git_changed_paths()

    bead_id: str | None = getattr(args, "bead", None)

    if args.command == "discover":
        result = discover_adrs_envelope(
            adr_dir=adr_dir,
            changed_paths=changed_paths,
            bead_description_override=(
                str(request["bead_description"])
                if isinstance(request.get("bead_description"), str)
                else None
            ),
            bead_id=bead_id,
            repo_root=Path(args.repo_root) if args.repo_root else None,
        )
        if args.output == "paths":
            # --output=paths: bare output format (shell convenience, exception to
            # envelope contract per AK2's "where applicable" clause). Use
            # --output=json (default) for the canonical Execution-Result envelope.
            for entry in result["data"]["adrs_in_scope"]:
                print(entry["path"])
        else:
            print(json.dumps(result, indent=2))

    elif args.command == "inject":
        result = inject_adrs_envelope(
            adr_dir=adr_dir,
            changed_paths=changed_paths,
            bead_description_override=None,
            bead_id=bead_id,
        )
        if args.output == "markdown":
            # --output=markdown: bare markdown for direct prompt injection
            # (convenience format, exception to envelope contract per AK2's
            # "where applicable" clause). Use --output=json for the canonical
            # Execution-Result envelope (data.markdown contains the same text).
            print(result["data"]["markdown"])
        else:
            print(json.dumps(result, indent=2))

    elif args.command == "verify":
        diff_range: str = args.diff
        changed_paths = _git_changed_paths(diff_range)
        diff_text = _git_diff_text(diff_range)
        result = verify_adrs_envelope(
            adr_dir=adr_dir,
            changed_paths=changed_paths,
            diff_text=diff_text,
            bead_description_override=None,
            bead_id=bead_id,
        )
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

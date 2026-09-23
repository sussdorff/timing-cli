#!/usr/bin/env python3
"""Deterministic, read-only entry point for on-demand context discovery.

This is a thin caller of the shared repository/ADR context engine
(``context-discovery/scripts/context_provider.py``). It reuses that engine's
functions unchanged and never reimplements ADR selection or candidate-surface
discovery. It supports two modes:

- ``path-scoped``: explicit candidate/changed paths, no live Bead. Calls
  ``build_adr_context`` with a synthetic empty-text bead and returns the
  bounded ADR manifest plus the candidate surface.
- ``bead-scoped``: a Bead ID (or ``--bead-json`` for tests). Calls
  ``build_context_bundle`` with the exact arguments the implementation loop
  uses and returns the same bundle shape unchanged.

Both modes print exactly one JSON object to stdout and perform no writes --
no loop state file, no bead mutation, no filesystem side effects beyond
reading.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import subprocess
import sys
import tomllib
from pathlib import Path
from typing import Any


class ContextDiscoveryError(ValueError):
    """Raised when context discovery cannot proceed for a supplied request."""


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


def resolve_context_provider(repo_root: Path) -> Path:
    """Resolve a provider only from the selected repository's skill trees."""
    candidates = [
        repo_root / ".agents/skills/context-discovery/scripts/context_provider.py",
        repo_root / ".claude/skills/context-discovery/scripts/context_provider.py",
        repo_root / "skills/context-discovery/scripts/context_provider.py",
    ]
    configured = os.environ.get("CONTEXT_DISCOVERY_RUNTIME_DIR")
    if configured:
        runtime = Path(configured).expanduser().resolve()
        allowed_runtimes = [candidate.parent.parent.resolve() for candidate in candidates]
        if runtime not in allowed_runtimes:
            raise ContextDiscoveryError(
                "CONTEXT_DISCOVERY_RUNTIME_DIR must name a project-local context-discovery skill"
            )
        candidates = [runtime / "scripts/context_provider.py"]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise ContextDiscoveryError(
        "context provider is unavailable; probed: "
        + ", ".join(str(candidate) for candidate in candidates)
    )


def load_context_provider(repo_root: Path) -> Any:
    """Import ``context_provider.py`` as a module without reimplementing it."""
    path = resolve_context_provider(repo_root)
    spec = importlib.util.spec_from_file_location("context_discovery_provider", path)
    if spec is None or spec.loader is None:
        raise ContextDiscoveryError(f"cannot load context provider from {path}")
    module = importlib.util.module_from_spec(spec)
    previous_bytecode_mode = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = previous_bytecode_mode
    return module


def synthetic_bead() -> dict[str, Any]:
    """Return the synthetic no-text bead used for path-scoped discovery.

    ``build_adr_context`` only uses the bead for freshness digesting and
    bead-text ADR matching (``bead:ADR-xxx``). A path-scoped request has no
    live Bead, so this carries no meaningful text -- path-based ADR matching
    still applies in full.
    """
    return {
        "id": None,
        "title": "",
        "description": "",
        "acceptance_criteria": "",
        "metadata": {},
    }


def discover_path_scoped(
    repo_root: Path,
    candidate_paths: list[str],
) -> dict[str, Any]:
    """Discover the bounded ADR manifest for explicit candidate paths.

    No live Bead is loaded or required. Returns a typed gap (via
    ``build_adr_context`` -> ``ADR_CORPUS_NOT_FOUND``) rather than raising when
    the repository has no ``docs/adr`` corpus.
    """
    provider = load_context_provider(repo_root)
    normalized_paths = sorted({str(path) for path in candidate_paths if str(path).strip()})
    adr_context = provider.build_adr_context(synthetic_bead(), repo_root, normalized_paths)
    return {
        "mode": "path-scoped",
        "repo_root": str(repo_root.resolve()),
        "candidate_surface": normalized_paths,
        "adr_context": adr_context,
    }


def _normalize_bead(raw: Any) -> dict[str, Any]:
    if isinstance(raw, list):
        return raw[0] if raw and isinstance(raw[0], dict) else {}
    return raw if isinstance(raw, dict) else {}


def load_bead_for_discovery(
    bead_id: str,
    bead_json: Path | None,
    timeout: int,
    repo_root: Path,
) -> dict[str, Any]:
    """Load a live Bead, matching the pattern ``context_provider.py``'s own CLI uses.

    ``--bead-json`` bypasses the ``bd`` CLI (used by tests); otherwise this
    shells non-interactive ``bd show <id> --json`` with ``cwd=repo_root`` so
    ``bd`` resolves the ``.beads`` workspace under the requested repository
    rather than whatever happens to be the process's own working directory.
    """
    if bead_json is not None:
        try:
            raw = json.loads(bead_json.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ContextDiscoveryError(f"cannot read --bead-json: {exc}") from exc
        bead = _normalize_bead(raw)
        if not bead:
            raise ContextDiscoveryError("--bead-json did not contain a bead object")
        return bead

    if not bead_id.strip():
        raise ContextDiscoveryError("bead-scoped mode requires bead_id or --bead-json")

    try:
        tracker = _issue_tracker_name(repo_root)
        if not tracker:
            argv = ["bd", "show", bead_id, "--json"]
        else:
            argv = ["ccore", "tracker", "show", bead_id]
        result = subprocess.run(
            argv,
            cwd=repo_root,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ContextDiscoveryError(f"cannot run bd show for {bead_id}: {exc}") from exc
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or "bd show failed"
        raise ContextDiscoveryError(f"bd show failed for {bead_id}: {detail}")
    try:
        raw = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise ContextDiscoveryError("bd show returned malformed JSON") from exc
    bead = _normalize_bead(raw)
    if not bead:
        raise ContextDiscoveryError(f"bd show returned no bead for {bead_id}")
    return bead


def discover_bead_scoped(
    repo_root: Path,
    *,
    bead_id: str,
    bead_json: Path | None,
    timeout: int,
) -> dict[str, Any]:
    """Return the exact bundle a delivery session consumes for a live Bead.

    Calls ``build_context_bundle`` with the fixed arguments this repository
    binds for bead context (``provider="fallback"``,
    ``cbm_command="codebase-memory-mcp"``, ``allow_index=False``) so an ad-hoc
    query can never drift from what a delivery session sees. Writes nothing --
    no state file, no bead mutation.
    """
    provider = load_context_provider(repo_root)
    bead = load_bead_for_discovery(bead_id, bead_json, timeout, repo_root)
    return provider.build_context_bundle(
        bead,
        repo_root,
        provider="fallback",
        cbm_command="codebase-memory-mcp",
        timeout=timeout,
        allow_index=False,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="mode", required=True)

    path_scoped = sub.add_parser(
        "path-scoped",
        help="Discover the bounded ADR manifest for explicit candidate paths, no live Bead",
    )
    path_scoped.add_argument("--repo-root", type=Path, default=Path.cwd())
    path_scoped.add_argument(
        "--candidate-path",
        action="append",
        default=[],
        dest="candidate_paths",
        help="Repeatable. A candidate/changed path relative to --repo-root",
    )
    path_scoped.add_argument(
        "--request-stdin",
        action="store_true",
        help=(
            'Read {"candidate_paths": [...], "repo_root": "..."} JSON from stdin. '
            "Merged with --candidate-path/--repo-root when both are supplied."
        ),
    )

    bead_scoped = sub.add_parser(
        "bead-scoped",
        help="Discover the exact bundle the implementation loop consumes for a live Bead",
    )
    bead_scoped.add_argument("bead_id", nargs="?", help="Bead id used when --bead-json is omitted")
    bead_scoped.add_argument(
        "--bead-json", type=Path, help="Path to bd show --json output (bypasses bd, for tests)"
    )
    bead_scoped.add_argument("--repo-root", type=Path, default=Path.cwd())
    bead_scoped.add_argument("--timeout", type=int, default=8)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv if argv is not None else sys.argv[1:])
    try:
        if args.mode == "path-scoped":
            repo_root = args.repo_root
            candidate_paths = list(args.candidate_paths)
            if args.request_stdin:
                try:
                    request = json.load(sys.stdin)
                except json.JSONDecodeError as exc:
                    raise ContextDiscoveryError(f"invalid --request-stdin JSON: {exc}") from exc
                if not isinstance(request, dict):
                    raise ContextDiscoveryError("--request-stdin requires a JSON object")
                stdin_paths = request.get("candidate_paths")
                if isinstance(stdin_paths, list):
                    candidate_paths.extend(str(path) for path in stdin_paths)
                stdin_repo_root = request.get("repo_root")
                if isinstance(stdin_repo_root, str) and stdin_repo_root.strip():
                    repo_root = Path(stdin_repo_root)
            result = discover_path_scoped(repo_root.resolve(), candidate_paths)
        else:
            result = discover_bead_scoped(
                args.repo_root.resolve(),
                bead_id=args.bead_id or "",
                bead_json=args.bead_json,
                timeout=args.timeout,
            )
    except ContextDiscoveryError as exc:
        print(json.dumps({"error": str(exc)}, sort_keys=True), file=sys.stderr)
        return 1

    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

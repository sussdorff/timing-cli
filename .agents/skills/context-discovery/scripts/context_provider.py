#!/usr/bin/env python3
"""Build an implementation context bundle for a bead.

The provider prefers codebase-memory-mcp when it is installed and falls back to
local bead-text extraction. The output keeps the historical bead-context keys
while adding graph-aware fields that implementation agents can consume.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tomllib
from typing import Any, Callable, NamedTuple


PROVIDER_CODEBASE_MEMORY = "codebase-memory"
PROVIDER_FALLBACK = "fallback"


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


FOCUS_PRIMARY_LIMIT = 12
FOCUS_TEST_LIMIT = 8
FOCUS_TOTAL_LIMIT = 12
EXACT_SEARCH_LIMIT = 48
BREADTH_CANDIDATE_WARN = 50
EXPLICIT_ANCHOR_SLICE_THRESHOLD = 20
ADR_MANIFEST_LIMIT = 64
ADR_PROHIBITION_LIMIT = 8
ADR_TEXT_LIMIT = 500
ADR_CONTEXT_SCHEMA_VERSION = 1
ADR_GOVERNANCE_FILENAME = ".adr-governance.json"
ADR_GOVERNANCE_SCHEMA_VERSION = 1
ADR_ORIGIN_LOCAL = "local"
ADR_ORIGIN_FAMILY = "family"
ADR_CORPUS_LOCAL = "local"
ADR_PRECEDENCE_LOCAL = "local"
ADR_PRECEDENCE_GOVERNING = "governing"
ADR_STATUS_ACCEPTED = "accepted"

PATH_RE = re.compile(
    r"(?<![A-Za-z0-9_./-])"
    r"((?:[A-Za-z0-9_.-]+/)+[A-Za-z0-9_.-]+"
    r"\.(?:py|ts|tsx|js|jsx|mjs|cjs|md|json|ya?ml|toml|sh|go|rs|java|cs|cpp|c|h|sql|graphql|svelte|vue))"
    r"(?![A-Za-z0-9_./-])"
)
BACKTICK_RE = re.compile(r"`([^`]{3,})`")
CALL_RE = re.compile(r"\b([A-Za-z_][A-Za-z0-9_]{2,})\s*\(")
CLASS_RE = re.compile(r"\b([A-Z][A-Za-z0-9_]{2,})\b")
KEBAB_TOKEN_RE = re.compile(r"\b[a-z][a-z0-9]+(?:-[a-z0-9]+)+\b")
SYMBOL_TOKEN_RE = re.compile(
    r"[a-z][a-z0-9]+(?:-[a-z0-9]+)+|[A-Za-z_][A-Za-z0-9_]*"
)
BEAD_ID_RE = re.compile(r"\b[a-z][a-z0-9]+-[a-z0-9]+(?:\.[a-z0-9]+)?\b", re.IGNORECASE)
KNOWN_BEAD_PREFIXES = {"ccp", "cl", "clc", "cls", "mira", "polaris"}

STOP_SYMBOLS = {
    "Context",
    "Pointers",
    "Acceptance",
    "Criteria",
    "Description",
    "Implementation",
    "Factory",
    "Ready",
    "TODO",
    "MUST",
    "SHOULD",
    "MAY",
    "IF",
    "ELSE",
    "JSON",
    "YAML",
    "HTTP",
    "Related",
    "Test",
    "Touch",
    "Update",
    "Verify",
    "API",
}
STOP_SYMBOLS_LOWER = {symbol.lower() for symbol in STOP_SYMBOLS}

GENERIC_SEARCH_SYMBOLS = {
    "action",
    "accepted",
    "bundle",
    "callers",
    "catalog",
    "code",
    "content",
    "cfrt",
    "execution",
    "existing",
    "fact",
    "facts",
    "fields",
    "fhir",
    "implement",
    "locally",
    "mapping",
    "mira",
    "only",
    "polaris",
    "remove",
    "rule",
    "shape",
    "side",
    "source",
    "support",
    "templates",
    "test",
    "today",
    "violation",
}

EXACT_SEARCH_SKIP_DIRS = {
    ".beads",
    ".git",
    ".intake-archive",
    ".next",
    ".turbo",
    "build",
    "coverage",
    "dist",
    "node_modules",
}

EXACT_SEARCH_EXTENSIONS = {
    ".c",
    ".cpp",
    ".cs",
    ".go",
    ".graphql",
    ".h",
    ".java",
    ".js",
    ".jsx",
    ".mjs",
    ".py",
    ".rs",
    ".sh",
    ".sql",
    ".svelte",
    ".ts",
    ".tsx",
    ".vue",
}

CONTEXTUAL_KEBAB_MARKERS = {
    "accept",
    "account",
    "action",
    "adapter",
    "billing",
    "executor",
    "hzv",
    "proposal",
    "pvs",
    "rebook",
    "registry",
    "schein",
    "writeback",
}

HZV_CONTEXT_TOKENS = {
    "auto-hzv-schein",
    "ensureScheine",
    "hzv-schein-umbuchung",
    "rebookChargeItemsToHzv",
}

ACTION_CONTEXT_TOKENS = {
    "PROPOSAL_TYPE_ACTION_KIND",
    "acceptHandler",
    "actionKey",
    "dispatchAccept",
    "proposal_type",
}


CommandRunner = Callable[[list[str], int], subprocess.CompletedProcess[str]]


def run_subprocess(args: list[str], timeout: int) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def load_json_file(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def normalize_bead(raw: Any) -> dict[str, Any]:
    if isinstance(raw, list):
        if not raw:
            return {}
        first = raw[0]
        return first if isinstance(first, dict) else {}
    return raw if isinstance(raw, dict) else {}


def load_bead(bead_id: str, bead_json: Path | None, timeout: int) -> dict[str, Any]:
    if bead_json is not None:
        return normalize_bead(load_json_file(bead_json))

    tracker = _issue_tracker_name(Path.cwd())
    if not tracker:
        argv = ["bd", "show", bead_id, "--json"]
    else:
        argv = ["ccore", "tracker", "show", bead_id]
    result = run_subprocess(argv, timeout)
    if result.returncode != 0:
        return {}
    try:
        return normalize_bead(json.loads(result.stdout))
    except json.JSONDecodeError:
        return {}


def canonical_digest(value: Any) -> str:
    """Return a stable SHA-256 digest for JSON-compatible context evidence."""
    encoded = json.dumps(
        value,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _load_adr_context_module() -> Any:
    script_path = Path(__file__).with_name("adr-context.py")
    spec = importlib.util.spec_from_file_location("cognovis_adr_context", script_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load ADR selector from {script_path}")
    module = importlib.util.module_from_spec(spec)
    previous_bytecode_mode = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = previous_bytecode_mode
    return module


def _discover_adrs(
    *,
    adr_dir: Path,
    candidate_surface: list[str],
    bead_description: str,
    selector_repo_root: Path,
) -> list[dict[str, Any]]:
    """Call the shared ADR selector with PEP-723 dependency isolation when needed.

    ``selector_repo_root`` is the repository whose candidate surface is being
    matched. It stays the declaring child repository even when ``adr_dir`` is a
    governing family corpus, so a blank workspace-package selector resolves
    against the paths under discovery rather than against the family checkout.
    """
    try:
        selector = _load_adr_context_module()
    except ModuleNotFoundError as exc:
        if exc.name != "yaml":
            raise
        script_path = Path(__file__).with_name("adr-context.py")
        result = subprocess.run(
            [
                "uv",
                "run",
                "--quiet",
                "--script",
                str(script_path),
                "discover",
                "--adr-dir",
                str(adr_dir),
                "--repo-root",
                str(selector_repo_root),
                "--request-stdin",
                "--output",
                "json",
            ],
            input=json.dumps(
                {
                    "changed_paths": candidate_surface,
                    "bead_description": bead_description,
                }
            ),
            check=False,
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode != 0:
            detail = result.stderr.strip() or result.stdout.strip() or "uv run failed"
            raise RuntimeError(f"isolated ADR selector failed: {detail}")
        try:
            envelope = json.loads(result.stdout)
            discovered = envelope["data"]["adrs_in_scope"]
        except (KeyError, TypeError, json.JSONDecodeError) as parse_error:
            raise RuntimeError("isolated ADR selector returned malformed JSON") from parse_error
        if not isinstance(discovered, list):
            raise RuntimeError("isolated ADR selector returned malformed ADR results")
        return discovered
    return selector.discover_adrs(
        adr_dir=adr_dir,
        changed_paths=candidate_surface,
        bead_description_override=bead_description,
        repo_root=selector_repo_root,
    )


def _adr_dir(corpus_root: Path) -> tuple[Path | None, bool]:
    """Resolve an ADR directory without following it outside its corpus root."""
    candidate = corpus_root / "docs" / "adr"
    if not candidate.is_dir():
        return None, False
    try:
        candidate.resolve().relative_to(corpus_root.resolve())
    except ValueError:
        return None, True
    return candidate, False


def _adr_markdown_files_are_contained(corpus_root: Path, adr_dir: Path) -> bool:
    """Require every selector candidate to resolve beneath its corpus root."""
    resolved_corpus_root = corpus_root.resolve()
    for candidate in adr_dir.rglob("*.md"):
        try:
            candidate.resolve().relative_to(resolved_corpus_root)
        except ValueError:
            return False
    return True


class AdrCorpus(NamedTuple):
    """One ADR corpus governing the repository currently under discovery."""

    name: str
    origin: str
    precedence: str
    root: Path
    adr_dir: Path


def _declaration_invalid_gap(reason: str, **fields: Any) -> dict[str, Any]:
    return {
        "code": "ADR_GOVERNING_DECLARATION_INVALID",
        "resolved": False,
        "reason": reason,
        **fields,
        "resolution": {
            "action": "correct_the_adr_governance_declaration_and_rerun_provider",
            "admission": "blocked_until_the_declaration_is_well_formed",
        },
    }


def _is_direct_family_sibling(repo_root: Path, workspace_path: str) -> bool:
    """Accept only a resolved direct sibling under the declaring repository's parent."""
    resolved_repo_root = repo_root.resolve()
    resolved_family_root = resolved_repo_root.parent
    resolved_candidate = (resolved_repo_root / workspace_path).resolve()
    return (
        resolved_candidate != resolved_repo_root
        and resolved_candidate.parent == resolved_family_root
    )


def _read_governing_declaration(
    repo_root: Path,
) -> tuple[list[dict[str, str]], list[dict[str, Any]]]:
    """Read the project-local governing-corpus declaration, if there is one.

    A repository declares the corpora that govern it in ``.adr-governance.json``
    at its own root. ``workspace_path`` is relative to that root, so no machine
    path is ever recorded, and an absolute value is refused for that reason.

    A declaration that cannot be honored fails closed: the repository has said
    it is governed from elsewhere, so discarding the defect and reporting a
    complete local-only result would answer a question nobody asked. An
    *absent* declaration is not a defect and still means local-only discovery.
    """
    governance_path = repo_root / ADR_GOVERNANCE_FILENAME
    if not governance_path.is_file():
        return [], []
    try:
        declaration = load_json_file(governance_path)
    except json.JSONDecodeError as exc:
        return [], [_declaration_invalid_gap("invalid_json", detail=_bounded_text(exc))]
    except OSError as exc:
        return [], [_declaration_invalid_gap("unreadable", detail=_bounded_text(exc))]

    if not isinstance(declaration, dict):
        return [], [_declaration_invalid_gap("declaration_is_not_an_object")]
    schema_version = declaration.get("schema_version")
    if schema_version != ADR_GOVERNANCE_SCHEMA_VERSION:
        return [], [
            _declaration_invalid_gap(
                "unsupported_schema_version",
                declared_schema_version=(
                    schema_version if isinstance(schema_version, (int, str)) else None
                ),
                supported_schema_version=ADR_GOVERNANCE_SCHEMA_VERSION,
            )
        ]
    entries = declaration.get("governing_corpora")
    if not isinstance(entries, list):
        return [], [_declaration_invalid_gap("governing_corpora_is_not_a_list")]

    declared: list[dict[str, str]] = []
    gaps: list[dict[str, Any]] = []
    for entry in entries:
        if not isinstance(entry, dict):
            gaps.append(_declaration_invalid_gap("entry_is_not_an_object"))
            continue
        corpus = str(entry.get("corpus") or "").strip()
        workspace_path = str(entry.get("workspace_path") or "").strip()
        if not corpus or not workspace_path:
            gaps.append(
                _declaration_invalid_gap(
                    "entry_is_incomplete", corpus=corpus, workspace_path=workspace_path
                )
            )
            continue
        if os.path.isabs(workspace_path):
            gaps.append(
                _declaration_invalid_gap(
                    "workspace_path_is_absolute",
                    corpus=corpus,
                    workspace_path=workspace_path,
                )
            )
            continue
        if not _is_direct_family_sibling(repo_root, workspace_path):
            gaps.append(
                _declaration_invalid_gap(
                    "workspace_path_is_not_direct_sibling",
                    corpus=corpus,
                    workspace_path=workspace_path,
                )
            )
            continue
        declared.append({"corpus": corpus, "workspace_path": workspace_path})
    return declared, gaps


def _withhold_colliding_identities(
    declared: list[dict[str, str]], repo_root: Path
) -> tuple[list[dict[str, str]], list[dict[str, Any]]]:
    """Withhold every corpus identity that names more than one root.

    The identity is what a manifest entry reports as its ``corpus`` and what the
    cross-corpus conflict check compares. One identity resolving to two roots
    therefore makes both unreliable, and admitting the roots under a shared name
    would be exactly the silent merge that hides it. Those declarations are
    withheld and reported instead.
    """
    roots_by_corpus: dict[str, set[Path]] = {}
    paths_by_corpus: dict[str, set[str]] = {}
    for declaration in declared:
        corpus = declaration["corpus"]
        roots_by_corpus.setdefault(corpus, set()).add(
            (repo_root / declaration["workspace_path"]).resolve()
        )
        paths_by_corpus.setdefault(corpus, set()).add(declaration["workspace_path"])

    colliding = {
        corpus for corpus, roots in roots_by_corpus.items() if len(roots) > 1
    }
    gaps = [
        {
            "code": "ADR_GOVERNING_CORPUS_IDENTITY_COLLISION",
            "resolved": False,
            "corpus": corpus,
            "workspace_paths": sorted(paths_by_corpus[corpus]),
            "resolution": {
                "action": "give_each_governing_corpus_root_its_own_identity",
                "admission": "blocked_until_each_identity_names_one_root",
            },
        }
        for corpus in sorted(colliding)
    ]
    remaining = [
        declaration
        for declaration in declared
        if declaration["corpus"] not in colliding
    ]
    return remaining, gaps


class AdrCorpusResolution(NamedTuple):
    """Corpora that resolved, beside the typed defects of the declaration."""

    corpora: list[AdrCorpus]
    gaps: list[dict[str, Any]]


def _adr_corpora(repo_root: Path) -> AdrCorpusResolution:
    """Resolve the local corpus plus every declared governing family corpus.

    A declaration whose corpus cannot be read is reported rather than skipped:
    a governing decision that exists but is unreachable is not the same thing as
    a repository that has no decisions.
    """
    repo_root = repo_root.resolve()
    declared, gaps = _read_governing_declaration(repo_root)
    declared, collision_gaps = _withhold_colliding_identities(declared, repo_root)
    gaps.extend(collision_gaps)

    corpora: list[AdrCorpus] = []
    missing: list[dict[str, str]] = []
    unsafe: list[dict[str, str]] = []
    local_dir, _local_dir_escapes_root = _adr_dir(repo_root)
    local_unsafe = _local_dir_escapes_root
    if local_dir is not None and not _adr_markdown_files_are_contained(repo_root, local_dir):
        local_unsafe = True
    if local_dir is not None and not local_unsafe:
        corpora.append(
            AdrCorpus(
                name=ADR_CORPUS_LOCAL,
                origin=ADR_ORIGIN_LOCAL,
                precedence=ADR_PRECEDENCE_LOCAL,
                root=repo_root,
                adr_dir=local_dir,
            )
        )

    seen_roots = {repo_root}
    for declaration in declared:
        corpus_root = (repo_root / declaration["workspace_path"]).resolve()
        if corpus_root in seen_roots:
            continue
        corpus_dir, corpus_dir_escapes_root = _adr_dir(corpus_root)
        if corpus_dir_escapes_root:
            unsafe.append(dict(declaration))
            continue
        if corpus_dir is None:
            missing.append(dict(declaration))
            continue
        if not _adr_markdown_files_are_contained(corpus_root, corpus_dir):
            unsafe.append(dict(declaration))
            continue
        seen_roots.add(corpus_root)
        corpora.append(
            AdrCorpus(
                name=declaration["corpus"],
                origin=ADR_ORIGIN_FAMILY,
                precedence=ADR_PRECEDENCE_GOVERNING,
                root=corpus_root,
                adr_dir=corpus_dir,
            )
        )
    gaps.extend(_missing_corpus_gaps(missing))
    gaps.extend(_unsafe_corpus_gaps(unsafe))
    if local_unsafe:
        gaps.append(_local_unsafe_corpus_gap())
    return AdrCorpusResolution(corpora=corpora, gaps=gaps)


def _corpus_relative_path(adr_path: Path, corpus_root: Path) -> str:
    try:
        return adr_path.relative_to(corpus_root).as_posix()
    except ValueError:
        return str(adr_path)


def _attribute_to_corpus(
    discovered: list[dict[str, Any]], corpus: AdrCorpus
) -> list[dict[str, Any]]:
    """Bind provenance to each discovered ADR of one corpus."""
    return [
        {
            **adr,
            "origin": corpus.origin,
            "corpus": corpus.name,
            "precedence": corpus.precedence,
            "corpus_path": _corpus_relative_path(
                Path(str(adr["path"])).resolve(), corpus.root
            ),
        }
        for adr in discovered
    ]


def _repository_digest(repo_root: Path) -> str:
    result = run_subprocess(
        ["git", "-C", str(repo_root), "rev-parse", "--verify", "HEAD"],
        timeout=15,
    )
    head = result.stdout.strip() if result.returncode == 0 else None
    return canonical_digest({"repo_root": str(repo_root.resolve()), "head": head})


def _path_content_digest(repo_root: Path, paths: list[str]) -> str:
    records: list[dict[str, Any]] = []
    for path_text in sorted(set(paths)):
        path = repo_root / path_text
        digest = None
        if path.is_file():
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
        records.append({"path": path_text, "content_digest": digest})
    return canonical_digest(records)


def _adr_corpus_digest(corpora: list[AdrCorpus]) -> str:
    """Digest every corpus that can contribute guidance, local and governing."""
    records: list[dict[str, str]] = []
    for corpus in corpora:
        for path in sorted(corpus.adr_dir.rglob("*.md")):
            records.append(
                {
                    "corpus": corpus.name,
                    "path": _corpus_relative_path(path, corpus.root),
                    "content_digest": hashlib.sha256(path.read_bytes()).hexdigest(),
                }
            )
    return canonical_digest(records)


def _missing_corpus_gaps(missing: list[dict[str, str]]) -> list[dict[str, Any]]:
    """Report each declared governing corpus that could not be read.

    Unlike ``ADR_CORPUS_NOT_FOUND``, which records the accepted absence of a
    repository's own corpus, an unreadable declared corpus leaves guidance the
    repository claims to be governed by out of the manifest. That is a defect
    the consumer repairs, so the gap stays unresolved.
    """
    return [
        {
            "code": "ADR_GOVERNING_CORPUS_MISSING",
            "resolved": False,
            "corpus": declaration["corpus"],
            "workspace_path": declaration["workspace_path"],
            "resolution": {
                "action": "provide_the_declared_governing_corpus_or_remove_the_declaration",
                "admission": "blocked_until_every_declared_corpus_resolves",
            },
        }
        for declaration in missing
    ]


def _unsafe_corpus_gaps(unsafe: list[dict[str, str]]) -> list[dict[str, Any]]:
    """Report a declared corpus whose resolved ADR directory escapes its root."""
    return [
        {
            "code": "ADR_GOVERNING_CORPUS_OUTSIDE_ROOT",
            "resolved": False,
            "corpus": declaration["corpus"],
            "workspace_path": declaration["workspace_path"],
            "resolution": {
                "action": "make_docs_adr_resolve_within_the_declared_corpus_root",
                "admission": "blocked_until_the_declared_corpus_is_contained",
            },
        }
        for declaration in unsafe
    ]


def _local_unsafe_corpus_gap() -> dict[str, Any]:
    """Report a local ADR directory or candidate that resolves outside its root."""
    return {
        "code": "ADR_CORPUS_OUTSIDE_ROOT",
        "resolved": False,
        "resolution": {
            "action": "make_local_docs_adr_and_its_markdown_files_resolve_within_the_repository_root",
            "admission": "blocked_until_the_local_corpus_is_contained",
        },
    }


def _decision_topic(adr: dict[str, Any]) -> str:
    return str(adr.get("decides") or "").strip()


def _is_accepted_decision(adr: dict[str, Any]) -> bool:
    return str(adr.get("status") or "").strip().lower() == ADR_STATUS_ACCEPTED


def _decision_conflict_gaps(
    applicable: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Report every decided topic that more than one corpus accepts.

    Two corpora accepting the same ``decides`` topic contradict each other, and
    nothing in discovery order makes either one right. Both sides therefore keep
    their own precedence and the conflict is handed to the consumer. A record
    that is not accepted proposes rather than decides, and a topic confined to a
    single corpus is out of scope here.

    ``applicable`` is the full discovered set rather than the bounded manifest,
    so a conflicting side is named even when it ranks below the manifest bound.
    """
    sides_by_topic: dict[str, set[tuple[str, str, str]]] = {}
    for adr in applicable:
        topic = _decision_topic(adr)
        if not topic or not _is_accepted_decision(adr):
            continue
        sides_by_topic.setdefault(topic, set()).add(
            (str(adr["origin"]), str(adr["corpus"]), str(adr["id"]))
        )

    gaps: list[dict[str, Any]] = []
    for topic in sorted(sides_by_topic):
        sides = sorted(sides_by_topic[topic])
        if len({corpus for _origin, corpus, _id in sides}) < 2:
            continue
        gaps.append(
            {
                "code": "ADR_DECISION_CONFLICT",
                "resolved": False,
                "topic": topic,
                "conflicts": [
                    {"origin": origin, "corpus": corpus, "id": adr_id}
                    for origin, corpus, adr_id in sides
                ],
                "resolution": {
                    "action": "supersede_one_decision_or_narrow_its_selectors_so_one_applies",
                    "admission": "blocked_until_one_accepted_decision_governs_the_topic",
                },
            }
        )
    return gaps


def _bounded_text(value: Any) -> str:
    return str(value or "").strip()[:ADR_TEXT_LIMIT]


def _as_string_list(value: Any) -> list[Any]:
    """Normalize a contract-legal scalar or list field to a list."""
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return list(value)
    return []


def _prohibition_items(adr: dict[str, Any]) -> list[str]:
    """Return non-empty prohibition strings from one discovered ADR."""
    items = _as_string_list(adr.get("prohibits"))
    return [str(item).strip() for item in items if str(item).strip()]


def _adr_relevance_key(adr: dict[str, Any]) -> tuple[Any, ...]:
    """Sort key: constraint-bearing records first, then remaining relevance.

    Ranked once per applicable set. Identity is the final tie-break so filename
    walk order from ``rglob`` does not decide truncation.
    """
    prohibitions = _prohibition_items(adr)
    match_reasons = [str(reason) for reason in adr.get("match_reasons") or []]
    path_matches = sum(1 for reason in match_reasons if reason.startswith("path:"))
    bead_matches = sum(1 for reason in match_reasons if reason.startswith("bead:"))
    summary = str(adr.get("decision_summary") or "").strip()
    return (
        0 if prohibitions else 1,
        -len(prohibitions),
        -path_matches,
        -bead_matches,
        -len(match_reasons),
        0 if summary else 1,
        str(adr.get("id") or ""),
    )


def _select_bounded_adrs(
    discovered: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Select a bounded applicable set by relevance, not discovery order."""
    ranked = sorted(discovered, key=_adr_relevance_key)
    selected = ranked[:ADR_MANIFEST_LIMIT]
    omitted = ranked[ADR_MANIFEST_LIMIT:]
    return selected, omitted


def _adr_manifest(
    *,
    bead: dict[str, Any],
    repo_root: Path,
    candidate_surface: list[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], str]:
    resolution = _adr_corpora(repo_root)
    gaps: list[dict[str, Any]] = list(resolution.gaps)
    if not resolution.corpora:
        gaps.append(
            {
                "code": "ADR_CORPUS_NOT_FOUND",
                "resolved": True,
                "resolution": {
                    "action": "accept_absent_repository_adr_corpus",
                    "evidence": "docs/adr directory does not exist",
                },
            }
        )
        return [], gaps, "gap"

    description = bead_text(bead)
    discovered: list[dict[str, Any]] = []
    for corpus in resolution.corpora:
        try:
            corpus_adrs = _discover_adrs(
                adr_dir=corpus.adr_dir,
                candidate_surface=candidate_surface,
                bead_description=description,
                selector_repo_root=repo_root,
            )
        except (ImportError, OSError, RuntimeError, ValueError) as exc:
            gaps.append(
                {
                    "code": "ADR_DISCOVERY_FAILED",
                    "resolved": False,
                    "corpus": corpus.name,
                    "error_type": type(exc).__name__,
                    "detail": _bounded_text(exc),
                    "failure_digest": canonical_digest(
                        {"type": type(exc).__name__, "detail": str(exc)}
                    ),
                    "resolution": {
                        "action": "repair_adr_corpus_or_selector_and_rerun_provider",
                        "admission": "blocked_until_discovery_succeeds",
                    },
                }
            )
            return [], gaps, "gap"
        discovered.extend(_attribute_to_corpus(corpus_adrs, corpus))

    selected, omitted = _select_bounded_adrs(discovered)
    # Conflicts are read from the full applicable set: a contradiction that
    # ranks below the manifest bound is still a contradiction, and reporting
    # only what survived truncation would hide it behind the truncation gap.
    gaps.extend(_decision_conflict_gaps(discovered))
    if omitted:
        omitted_constraints = [item for item in omitted if _prohibition_items(item)]
        omitted_informational = [
            item for item in omitted if not _prohibition_items(item)
        ]
        first_omitted = omitted_constraints + omitted_informational
        gaps.append(
            {
                "code": "ADR_MANIFEST_TRUNCATED",
                "resolved": False,
                "discovered_count": len(discovered),
                "limit": ADR_MANIFEST_LIMIT,
                "omitted_count": len(omitted),
                "omitted_constraint_count": len(omitted_constraints),
                "discovery_digest": canonical_digest(discovered),
                "first_omitted_ids": [
                    str(item.get("id") or "") for item in first_omitted[:8]
                ],
                "resolution": {
                    "action": "split_implementation_scope_or_narrow_adr_selectors_and_rerun_provider",
                    "admission": "blocked_until_manifest_fits_bound",
                },
            }
        )

    manifest: list[dict[str, Any]] = []
    for adr in selected:
        current_path = str(adr["corpus_path"])
        prohibitions = [
            _bounded_text(item)
            for item in _as_string_list(adr.get("prohibits"))[:ADR_PROHIBITION_LIMIT]
        ]
        manifest.append(
            {
                "id": str(adr["id"]),
                "path": current_path,
                "origin": str(adr["origin"]),
                "corpus": str(adr["corpus"]),
                "precedence": str(adr["precedence"]),
                "match_reasons": sorted(set(adr.get("match_reasons", []))),
                "decision_summary": _bounded_text(adr.get("decision_summary")),
                "prohibitions": prohibitions,
                "read_pointers": [
                    {"path": current_path, "section": "Decision"},
                    {"path": current_path, "section": "Prohibitions"},
                ],
            }
        )
    manifest.sort(key=lambda item: (item["id"], item["path"]))
    return manifest, gaps, "complete" if not gaps else "gap"


def build_adr_context(
    bead: dict[str, Any],
    repo_root: Path,
    candidate_surface: list[str],
) -> dict[str, Any]:
    """Build bounded ADR guidance and bind it to current implementation context."""
    repo_root = repo_root.resolve()
    normalized_surface = sorted(set(candidate_surface))
    manifest, gaps, status = _adr_manifest(
        bead=bead,
        repo_root=repo_root,
        candidate_surface=normalized_surface,
    )
    freshness = {
        "bead_digest": canonical_digest(bead),
        "repository_digest": _repository_digest(repo_root),
        "scope_digest": _path_content_digest(repo_root, normalized_surface),
        "adr_corpus_digest": _adr_corpus_digest(_adr_corpora(repo_root).corpora),
    }
    freshness["context_digest"] = canonical_digest(
        {
            "schema_version": ADR_CONTEXT_SCHEMA_VERSION,
            "status": status,
            "manifest": manifest,
            "gaps": gaps,
            "freshness": freshness,
        }
    )
    return {
        "schema_version": ADR_CONTEXT_SCHEMA_VERSION,
        "status": status,
        "candidate_surface_count": len(normalized_surface),
        "manifest": manifest,
        "gaps": gaps,
        "freshness": freshness,
    }


def validate_adr_context(
    adr_context: Any,
    *,
    bead: dict[str, Any],
    repo_root: Path,
    candidate_surface: list[str],
) -> list[str]:
    """Return fail-closed validation errors for one provider ADR bundle."""
    if not isinstance(adr_context, dict):
        return ["ADR context is missing or malformed"]
    if adr_context.get("schema_version") != ADR_CONTEXT_SCHEMA_VERSION:
        return ["ADR context schema version is missing or unsupported"]
    manifest = adr_context.get("manifest")
    gaps = adr_context.get("gaps")
    freshness = adr_context.get("freshness")
    if not isinstance(manifest, list) or not isinstance(gaps, list):
        return ["ADR context manifest or typed gaps are malformed"]
    if not isinstance(freshness, dict):
        return ["ADR context freshness is missing or malformed"]
    if any(
        not isinstance(gap, dict)
        or not str(gap.get("code") or "")
        or gap.get("resolved") is not True
        for gap in gaps
    ):
        return ["ADR context contains an unresolved or malformed typed gap"]

    current = build_adr_context(bead, repo_root, candidate_surface)
    current_freshness = current["freshness"]
    errors: list[str] = []
    for key in (
        "bead_digest",
        "repository_digest",
        "scope_digest",
        "adr_corpus_digest",
        "context_digest",
    ):
        if freshness.get(key) != current_freshness.get(key):
            errors.append(f"ADR context is stale: {key}")
    if manifest != current["manifest"] or gaps != current["gaps"]:
        errors.append("ADR context results do not match current discovery")
    return errors


def validate_context_bundle(
    context_bundle: Any,
    *,
    bead: dict[str, Any],
    repo_root: Path,
    timeout: int = 8,
) -> list[str]:
    """Validate a bundle against an independently derived complete current surface."""
    if not isinstance(context_bundle, dict):
        return ["provider context bundle is missing or malformed"]
    candidate_files = context_bundle.get("candidate_files")
    candidate_test_files = context_bundle.get("candidate_test_files")
    if not isinstance(candidate_files, list) or not isinstance(candidate_test_files, list):
        return ["provider context bundle candidate surface is malformed"]
    provider_name = str(context_bundle.get("provider") or PROVIDER_FALLBACK)
    if provider_name not in {PROVIDER_FALLBACK, PROVIDER_CODEBASE_MEMORY}:
        return ["provider context bundle names an unsupported provider"]
    current = build_context_bundle(
        bead,
        repo_root.resolve(),
        provider=provider_name,
        cbm_command="codebase-memory-mcp",
        timeout=timeout,
        allow_index=False,
    )
    current_files = current["candidate_files"]
    current_tests = current["candidate_test_files"]
    errors: list[str] = []
    if candidate_files != current_files or candidate_test_files != current_tests:
        errors.append(
            "provider context candidate surface does not match independent current discovery"
        )
    errors.extend(
        validate_adr_context(
            context_bundle.get("adr_context"),
            bead=bead,
            repo_root=repo_root,
            candidate_surface=[*current_files, *current_tests],
        )
    )
    return errors


def reconcile_adr_context(
    baseline_adr_context: dict[str, Any],
    *,
    current_adr_context: dict[str, Any],
    bead: dict[str, Any],
    repo_root: Path,
    candidate_surface: list[str],
    changed_paths: list[str],
) -> dict[str, Any]:
    """Reconcile pre-implementation guidance against the final changed paths."""
    errors = validate_adr_context(
        current_adr_context,
        bead=bead,
        repo_root=repo_root,
        candidate_surface=candidate_surface,
    )
    if errors:
        raise ValueError("; ".join(errors))
    final_manifest, final_gaps, _status = _adr_manifest(
        bead=bead,
        repo_root=repo_root.resolve(),
        candidate_surface=sorted(set(changed_paths)),
    )
    if any(gap.get("resolved") is not True for gap in final_gaps):
        raise ValueError("final-diff ADR reconciliation has unresolved gaps")
    if not isinstance(baseline_adr_context, dict) or not isinstance(
        baseline_adr_context.get("manifest"), list
    ):
        raise ValueError("pre-implementation ADR baseline is missing or malformed")
    initial_ids = {item["id"] for item in baseline_adr_context["manifest"]}
    newly_applicable = [
        item for item in final_manifest if item["id"] not in initial_ids
    ]
    return {
        "changed_paths": sorted(set(changed_paths)),
        "applicable_adrs": final_manifest,
        "newly_applicable_adrs": newly_applicable,
        "gaps": final_gaps,
        "reconciliation_digest": canonical_digest(
            {
                "baseline_context_digest": baseline_adr_context["freshness"][
                    "context_digest"
                ],
                "current_context_digest": current_adr_context["freshness"][
                    "context_digest"
                ],
                "changed_paths": sorted(set(changed_paths)),
                "applicable_adrs": final_manifest,
                "gaps": final_gaps,
            }
        ),
    }


def bead_text(bead: dict[str, Any]) -> str:
    chunks: list[str] = []
    for key in ("id", "title", "description", "acceptance_criteria", "design"):
        value = bead.get(key)
        if isinstance(value, str):
            chunks.append(value)
        elif isinstance(value, list):
            chunks.extend(str(item) for item in value)
        elif isinstance(value, dict):
            chunks.append(json.dumps(value, sort_keys=True))
    metadata = bead.get("metadata")
    if isinstance(metadata, dict):
        for key in ("design", "notes"):
            value = metadata.get(key)
            if value:
                chunks.append(str(value))
    return "\n".join(chunks)


def load_context_pointers_parser() -> Callable[[dict[str, Any], Path], dict[str, Any]] | None:
    skills_root = Path(__file__).resolve().parents[2]
    helper_path = skills_root / "bead-reviewer" / "scripts" / "context_pointers.py"
    if not helper_path.exists():
        return None

    spec = importlib.util.spec_from_file_location("context_pointers", helper_path)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return getattr(module, "review_context_pointers", None)


def read_context_pointers(bead: dict[str, Any], repo_root: Path) -> dict[str, Any]:
    parser = load_context_pointers_parser()
    if parser is None:
        return {"status": "unavailable", "pointers": None, "findings": []}
    return parser(bead, repo_root)


def safe_repo_path(path_text: str, repo_root: Path) -> str | None:
    path_text = path_text.strip().strip(".,;:)")
    if not path_text or os.path.isabs(path_text):
        return None
    candidate = (repo_root / path_text).resolve()
    try:
        candidate.relative_to(repo_root.resolve())
    except ValueError:
        return None
    return path_text


def is_test_file(path_text: str) -> bool:
    path = Path(path_text)
    name = path.name.lower()
    parts = {part.lower() for part in path.parts}
    return (
        "tests" in parts
        or "test" in parts
        or name.startswith("test_")
        or ".test." in name
        or ".spec." in name
    )


def dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value not in seen:
            result.append(value)
            seen.add(value)
    return result


def extract_seed_files(text: str, repo_root: Path) -> list[str]:
    files: list[str] = []
    for match in PATH_RE.finditer(text):
        safe = safe_repo_path(match.group(1), repo_root)
        if safe:
            files.append(safe)
    return dedupe(files)


def split_symbol_candidate(candidate: str) -> list[str]:
    parts = re.split(r"[,;]", candidate)
    tokens: list[str] = []
    for part in parts:
        stripped = part.strip().strip("`'\"")
        if not stripped:
            continue
        for token in SYMBOL_TOKEN_RE.findall(stripped):
            tokens.append(token.split(".")[-1].split(":")[-1])
    return tokens


def is_searchworthy_symbol(name: str) -> bool:
    if (
        name in STOP_SYMBOLS
        or name.upper() in STOP_SYMBOLS
        or name.lower() in STOP_SYMBOLS_LOWER
    ):
        return False
    if name.lower() in GENERIC_SEARCH_SYMBOLS:
        return False
    if name.startswith("__") and name.endswith("__"):
        return False
    if BEAD_ID_RE.fullmatch(name) and name.split("-", 1)[0].lower() in KNOWN_BEAD_PREFIXES:
        return False
    if "-" not in name and len(name) < 3:
        return False
    if not re.match(
        r"^[A-Za-z_][A-Za-z0-9_]*$|^[a-z][a-z0-9]+(?:-[a-z0-9]+)+$",
        name,
    ):
        return False
    return True


def is_precise_search_token(name: str) -> bool:
    if not is_searchworthy_symbol(name):
        return False
    if "-" in name:
        return any(marker in name.lower() for marker in CONTEXTUAL_KEBAB_MARKERS)
    if "_" in name:
        return True
    if any(char.isupper() for char in name) and not name.isupper():
        return True
    if any(char.isdigit() for char in name) and any(char.isalpha() for char in name):
        return True
    return len(name) >= 10 and name.lower() not in GENERIC_SEARCH_SYMBOLS


def extract_seed_symbols(text: str, max_symbols: int = 24) -> list[str]:
    candidates: list[str] = []
    candidates.extend(match.group(1) for match in BACKTICK_RE.finditer(text))
    candidates.extend(match.group(1) for match in CALL_RE.finditer(text))
    candidates.extend(match.group(1) for match in CLASS_RE.finditer(text))
    candidates.extend(match.group(0) for match in KEBAB_TOKEN_RE.finditer(text))

    symbols: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        for name in split_symbol_candidate(candidate):
            if not is_searchworthy_symbol(name):
                continue
            if name not in seen:
                symbols.append(name)
                seen.add(name)
            if len(symbols) >= max_symbols:
                return symbols
    return symbols


def extract_related_beads(text: str) -> list[str]:
    return dedupe([match.group(0) for match in BEAD_ID_RE.finditer(text)])


def seed_from_bead(bead: dict[str, Any], repo_root: Path) -> dict[str, Any]:
    text = bead_text(bead)
    pointers_review = read_context_pointers(bead, repo_root)
    pointers = pointers_review.get("pointers") if isinstance(pointers_review, dict) else None
    pointers = pointers if isinstance(pointers, dict) else {}

    pointer_files = []
    for field in ("primary_files", "test_files"):
        values = pointers.get(field, [])
        if isinstance(values, list):
            pointer_files.extend(str(value) for value in values)

    pointer_symbols: list[str] = []
    for value in pointers.get("symbols", []):
        if isinstance(value, str) or value is not None:
            pointer_symbols.extend(split_symbol_candidate(str(value)))

    files = dedupe(pointer_files + extract_seed_files(text, repo_root))
    symbols = dedupe(
        [symbol for symbol in pointer_symbols if is_searchworthy_symbol(symbol)]
        + extract_seed_symbols(text)
    )

    current_bead_id = str(bead.get("id") or "")
    related_beads = [
        bead_id for bead_id in extract_related_beads(text) if bead_id != current_bead_id
    ]

    return {
        "context_pointers_present": bool(pointers),
        "context_pointers_status": (
            pointers_review.get("verdict") or pointers_review.get("status") or "unavailable"
        )
        if isinstance(pointers_review, dict)
        else "unavailable",
        "query_text": text,
        "primary_files": [path for path in files if not is_test_file(path)],
        "test_files": [path for path in files if is_test_file(path)],
        "symbols": symbols,
        "related_beads": related_beads,
        "memory_search": pointers.get("memory_search") if isinstance(pointers, dict) else None,
    }


def cbm_cli(
    executable: str,
    tool: str,
    payload: dict[str, Any] | None,
    timeout: int,
    command_runner: CommandRunner,
) -> tuple[bool, Any, str]:
    args = [executable, "cli", "--raw", tool]
    if payload is not None:
        args.append(json.dumps(payload))

    try:
        result = command_runner(args, timeout)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, None, str(exc)

    if result.returncode != 0:
        fallback_args = [executable, "cli", tool]
        if payload is not None:
            fallback_args.append(json.dumps(payload))
        try:
            result = command_runner(fallback_args, timeout)
        except (OSError, subprocess.TimeoutExpired) as exc:
            return False, None, str(exc)

    if result.returncode != 0:
        stderr = result.stderr.strip() if result.stderr else ""
        return False, None, stderr or f"{tool} exited {result.returncode}"

    stdout = result.stdout.strip()
    if not stdout:
        return True, {}, ""
    try:
        return True, json.loads(stdout), ""
    except json.JSONDecodeError:
        return True, {"raw": stdout}, ""


def iter_records(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if not isinstance(payload, dict):
        return []
    for key in ("results", "nodes", "items", "data", "matches", "projects"):
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    return [payload]


def pick(record: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in record and record[key] not in (None, ""):
            return record[key]
    return None


def normalize_symbol(record: dict[str, Any], source: str) -> dict[str, Any]:
    return {
        "name": str(pick(record, "name", "node", "qualified_name", "qualifiedName", "id") or ""),
        "file": pick(record, "file", "path", "file_path", "filepath", "source_file"),
        "line": pick(record, "line", "start_line", "lineno"),
        "kind": pick(record, "label", "type", "kind"),
        "qualified_name": pick(record, "qualified_name", "qualifiedName", "qname"),
        "source": source,
    }


def normalize_file_from_record(record: dict[str, Any]) -> str | None:
    value = pick(record, "file", "path", "file_path", "filepath", "source_file")
    return str(value) if value else None


def is_traceable_symbol_name(name: str) -> bool:
    return bool(re.match(r"^[A-Za-z_][A-Za-z0-9_]{2,}$", name))


def has_action_surface_hint(seed: dict[str, Any]) -> bool:
    text = str(seed.get("query_text") or "")
    symbols = " ".join(str(symbol) for symbol in seed.get("symbols", []))
    haystack = f"{text} {symbols}".lower()
    return bool(
        re.search(
            r"\b(action|accept|accepted|executor|primitive|proposal|proposal_type|rebook|write-?back)\b",
            haystack,
        )
    )


def exact_search_tokens(seed: dict[str, Any], max_tokens: int = 32) -> list[str]:
    text = str(seed.get("query_text") or "")
    lower_text = text.lower()
    tokens: list[str] = []

    for symbol in seed.get("symbols", []):
        name = str(symbol)
        if is_precise_search_token(name):
            tokens.append(name)

    if re.search(
        r"\bhzv\b|create-hzv-account|hzv-schein|schein-umbuchung|account-management",
        lower_text,
    ):
        tokens.extend(sorted(HZV_CONTEXT_TOKENS))

    if has_action_surface_hint(seed):
        tokens.extend(sorted(ACTION_CONTEXT_TOKENS))

    return dedupe(tokens)[:max_tokens]


def normalize_found_file(path_text: str, repo_root: Path) -> str | None:
    path = Path(path_text)
    try:
        relative = path.resolve().relative_to(repo_root.resolve())
    except ValueError:
        return None
    normalized = relative.as_posix()
    if any(part in EXACT_SEARCH_SKIP_DIRS for part in relative.parts):
        return None
    return normalized


def exact_search_with_rg(tokens: list[str], repo_root: Path, timeout: int) -> list[str] | None:
    rg = shutil.which("rg")
    if rg is None or not tokens:
        return None

    args = [
        rg,
        "-l",
        "--fixed-strings",
        "--glob",
        (
            "*.{c,cpp,cs,go,graphql,h,java,js,jsx,mjs,py,rs,sh,sql,"
            "svelte,ts,tsx,vue}"
        ),
        "--glob",
        "!node_modules/**",
        "--glob",
        "!dist/**",
        "--glob",
        "!build/**",
        "--glob",
        "!coverage/**",
    ]
    for token in tokens:
        args.extend(["-e", token])
    args.append(str(repo_root))

    try:
        result = subprocess.run(
            args,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None

    if result.returncode not in (0, 1):
        return None

    files: list[str] = []
    for line in result.stdout.splitlines():
        normalized = normalize_found_file(line, repo_root)
        if normalized:
            files.append(normalized)
    return dedupe(files)


def exact_search_with_python(tokens: list[str], repo_root: Path) -> list[str]:
    files: list[str] = []
    for path in repo_root.rglob("*"):
        if not path.is_file():
            continue
        try:
            relative = path.relative_to(repo_root)
        except ValueError:
            continue
        if any(part in EXACT_SEARCH_SKIP_DIRS for part in relative.parts):
            continue
        if path.suffix not in EXACT_SEARCH_EXTENSIONS:
            continue
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if any(token in content for token in tokens):
            files.append(relative.as_posix())
    return dedupe(files)


def exact_file_score(path_text: str, tokens: list[str], repo_root: Path) -> tuple[int, int, str]:
    path = repo_root / path_text
    content = ""
    try:
        content = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        pass

    token_hits = sum(1 for token in tokens if token in content)
    path_hits = sum(1 for token in tokens if token in path_text)
    source_rank = 0
    if path_text.startswith("src/lib/"):
        source_rank = 8
    elif path_text.startswith("src/adapters/"):
        source_rank = 7
    elif path_text.startswith("src/routes/"):
        source_rank = 6
    elif path_text.startswith("src/"):
        source_rank = 5
    elif path_text.startswith("packages/"):
        source_rank = 4
    elif path_text.startswith("scripts/"):
        source_rank = 3
    elif path_text.startswith("skills/") or path_text.startswith("agents/"):
        source_rank = 3
    elif path_text.startswith("infra/"):
        source_rank = 2
    return (token_hits * 10 + path_hits * 2 + source_rank, -len(path_text), path_text)


def rank_exact_files(
    files: list[str],
    tokens: list[str],
    repo_root: Path,
    *,
    limit: int = EXACT_SEARCH_LIMIT,
) -> list[str]:
    ranked = sorted(
        dedupe(files),
        key=lambda path: exact_file_score(path, tokens, repo_root),
        reverse=True,
    )
    return ranked[:limit]


def context_file_score(
    path_text: str,
    tokens: list[str],
    repo_root: Path,
    seed_files: set[str],
    exact_files: set[str],
) -> tuple[int, int, str]:
    score, length_score, normalized_path = exact_file_score(path_text, tokens, repo_root)
    if path_text in seed_files:
        score += 500
    if path_text in exact_files:
        score += 200
    if Path(path_text).suffix == ".md" and path_text not in seed_files:
        score -= 50
    return (score, length_score, normalized_path)


def rank_context_files(
    files: list[str],
    tokens: list[str],
    repo_root: Path,
    seed_files: list[str],
    exact_files: list[str],
    *,
    limit: int,
) -> list[str]:
    if limit <= 0:
        return []

    seed_set = set(seed_files)
    exact_set = set(exact_files)
    candidates = dedupe(files)
    ranked = sorted(
        candidates,
        key=lambda path: context_file_score(path, tokens, repo_root, seed_set, exact_set),
        reverse=True,
    )

    result: list[str] = []
    exact_reserve = min(len(exact_set), max(1, limit // 2))
    ranked_exact = sorted(
        [path for path in candidates if path in exact_set],
        key=lambda path: exact_file_score(path, tokens, repo_root),
        reverse=True,
    )
    for path in ranked_exact[:exact_reserve]:
        if path not in result:
            result.append(path)
    for path in ranked:
        if path not in result:
            result.append(path)
        if len(result) >= limit:
            break
    return result[:limit]


def query_exact_code(
    seed: dict[str, Any],
    repo_root: Path,
    *,
    timeout: int,
) -> dict[str, Any]:
    tokens = exact_search_tokens(seed)
    files = exact_search_with_rg(tokens, repo_root, timeout) if tokens else []
    if files is None:
        files = exact_search_with_python(tokens, repo_root) if tokens else []
    raw_file_count = len(files)
    files = rank_exact_files(files, tokens, repo_root) if files else []

    return {
        "tokens": tokens,
        "primary_files": [path for path in files if not is_test_file(path)],
        "test_files": [path for path in files if is_test_file(path)],
        "raw_file_count": raw_file_count,
        "hit_cap": raw_file_count > len(files),
    }


_NAMED_COMPONENT_ROOTS = frozenset({"packages", "skills"})
_REPO_LAYER_ROOTS = frozenset(
    {
        "src",
        "lib",
        "app",
        "cmd",
        "internal",
        "pkg",
        "tests",
        "test",
        "spec",
        "__tests__",
    }
)
_REPO_CONCERN = "."


def _concern_root(path_text: str) -> str:
    """Map a path to a repository or named-package concern root.

    ``packages/<name>`` and ``skills/<name>`` are distinct concerns. Conventional
    production/test layers (``src``, ``tests``, ...) of one repository share a
    single concern so a vertical feature is not treated as independent surfaces.
    """
    parts = Path(str(path_text).replace("\\", "/")).parts
    if not parts:
        return ""
    if parts[0] in _NAMED_COMPONENT_ROOTS and len(parts) >= 2:
        return f"{parts[0]}/{parts[1]}"
    if len(parts) == 1:
        return _REPO_CONCERN
    if parts[0] in _REPO_LAYER_ROOTS or parts[0] == "docs":
        return _REPO_CONCERN
    return parts[0]


def _concern_roots(paths: list[str]) -> set[str]:
    return {_concern_root(path) for path in paths if path}


def _anchors_are_coherent(paths: list[str]) -> bool:
    concerns = _concern_roots(paths)
    return len(concerns) <= 1


def assess_breadth(
    candidate_files: list[str],
    candidate_test_files: list[str],
    focus_files: list[str],
    focus_test_files: list[str],
    exact: dict[str, Any],
    *,
    seed_primary_files: list[str] | None = None,
    seed_test_files: list[str] | None = None,
    graph_files: list[str] | None = None,
) -> dict[str, Any]:
    candidate_total = len(candidate_files) + len(candidate_test_files)
    focus_total = len(focus_files) + len(focus_test_files)
    anchors = dedupe(list(seed_primary_files or []) + list(seed_test_files or []))
    graph_paths = dedupe(list(graph_files or []))
    reasons: list[str] = []
    signals: list[str] = []

    if anchors:
        signals.append("explicit_anchors")
    if exact.get("primary_files") or exact.get("test_files") or exact.get("raw_file_count"):
        signals.append("exact_search_fallback")
    if exact.get("hit_cap"):
        signals.append("hit_cap_overflow")
        reasons.append(
            f"exact search hit cap ({exact.get('raw_file_count', 0)} raw files)"
        )
    if graph_paths:
        signals.append("semantic_index")
    if candidate_total > BREADTH_CANDIDATE_WARN:
        signals.append("candidate_volume")
        reasons.append(
            f"candidate file count {candidate_total} exceeds {BREADTH_CANDIDATE_WARN}"
        )
    if focus_total >= FOCUS_TOTAL_LIMIT and candidate_total > FOCUS_TOTAL_LIMIT * 3:
        signals.append("focus_cap_filled")
        reasons.append("focus file cap filled while candidate set remains broad")

    volume_broad = bool(reasons)
    wider_than_focus = candidate_total > max(
        focus_total * 2, FOCUS_PRIMARY_LIMIT + FOCUS_TEST_LIMIT
    )
    if volume_broad:
        assessment = "broad"
    elif wider_than_focus:
        assessment = "moderate"
        reasons.append("candidate set is wider than focused context")
    else:
        assessment = "focused"
        reasons.append("candidate set fits focused context")

    coherent_anchors = _anchors_are_coherent(anchors)
    small_coherent_anchors = (
        0 < len(anchors) < EXPLICIT_ANCHOR_SLICE_THRESHOLD and coherent_anchors
    )
    graph_concerns = _concern_roots(graph_paths)
    anchor_concerns = _concern_roots(anchors)
    semantic_independent = bool(graph_paths) and len(graph_concerns - anchor_concerns) >= 1
    independent_concerns = (
        len(anchors) >= EXPLICIT_ANCHOR_SLICE_THRESHOLD
        or (bool(anchors) and not coherent_anchors)
        or semantic_independent
    )
    if independent_concerns:
        signals.append("independent_concerns")

    if independent_concerns and (volume_broad or len(anchors) >= EXPLICIT_ANCHOR_SLICE_THRESHOLD):
        slice_recommended = True
        assessment = "broad"
        if "independent explicit file anchors" not in "; ".join(reasons):
            reasons.append("independent explicit file anchors or semantic surfaces")
    elif volume_broad and small_coherent_anchors and not semantic_independent:
        slice_recommended = False
        reasons.append(
            "narrow coherent explicit anchors establish the surface; "
            "candidate volume is fallback or cap overflow"
        )
        assessment = "moderate" if wider_than_focus else "focused"
    else:
        slice_recommended = assessment == "broad"

    return {
        "assessment": assessment,
        "reason": "; ".join(reasons),
        "signals": signals,
        "slice_recommended": slice_recommended,
        "candidate_file_count": candidate_total,
        "focus_file_count": focus_total,
    }


def discover_cbm_project(
    executable: str,
    repo_root: Path,
    timeout: int,
    command_runner: CommandRunner,
) -> tuple[str | None, list[str]]:
    ok, payload, error = cbm_cli(executable, "list_projects", None, timeout, command_runner)
    diagnostics: list[str] = []
    if not ok:
        diagnostics.append(f"list_projects failed: {error}")
        return None, diagnostics

    repo_name = repo_root.name
    repo_path = str(repo_root.resolve())
    records = iter_records(payload)
    for record in records:
        name = str(pick(record, "name", "project", "id") or "")
        path = str(
            pick(record, "path", "repo_path", "repoPath", "root", "root_path", "rootPath")
            or ""
        )
        if path == repo_path or name == repo_name:
            return name or repo_name, diagnostics
    return repo_name, diagnostics


def query_codebase_memory(
    seed: dict[str, Any],
    repo_root: Path,
    *,
    executable: str,
    timeout: int,
    allow_index: bool,
    command_runner: CommandRunner,
) -> dict[str, Any]:
    diagnostics: list[str] = []
    if allow_index:
        ok, _, error = cbm_cli(
            executable,
            "index_repository",
            {"repo_path": str(repo_root.resolve())},
            timeout,
            command_runner,
        )
        if not ok:
            diagnostics.append(f"index_repository failed: {error}")

    project, project_diagnostics = discover_cbm_project(
        executable, repo_root, timeout, command_runner
    )
    diagnostics.extend(project_diagnostics)

    primary_files: list[str] = []
    test_files: list[str] = []
    symbols: list[dict[str, Any]] = []
    call_paths: list[dict[str, Any]] = []
    routes: list[dict[str, Any]] = []

    for name in seed.get("symbols", [])[:12]:
        payload: dict[str, Any] = {
            "name_pattern": f".*{re.escape(str(name))}.*",
            "limit": 12,
        }
        if project:
            payload["project"] = project
        ok, response, error = cbm_cli(
            executable, "search_graph", payload, timeout, command_runner
        )
        if not ok:
            diagnostics.append(f"search_graph({name}) failed: {error}")
            continue
        for record in iter_records(response):
            symbol = normalize_symbol(record, "codebase-memory")
            if symbol["name"]:
                symbols.append(symbol)
            file_path = normalize_file_from_record(record)
            if file_path:
                if is_test_file(file_path):
                    test_files.append(file_path)
                else:
                    primary_files.append(file_path)

    for pattern in seed.get("symbols", [])[:8]:
        payload = {"pattern": str(pattern), "limit": 8}
        if project:
            payload["project"] = project
        ok, response, error = cbm_cli(
            executable, "search_code", payload, timeout, command_runner
        )
        if not ok:
            diagnostics.append(f"search_code({pattern}) failed: {error}")
            continue
        for record in iter_records(response):
            symbol = normalize_symbol(record, "codebase-memory")
            if symbol["name"]:
                symbols.append(symbol)
            file_path = normalize_file_from_record(record)
            if file_path:
                if is_test_file(file_path):
                    test_files.append(file_path)
                else:
                    primary_files.append(file_path)

    trace_names = [symbol.get("name") for symbol in symbols]
    trace_names = [
        str(name) for name in trace_names if name and is_traceable_symbol_name(str(name))
    ][:4]
    for name in trace_names:
        payload = {"function_name": name, "direction": "both", "depth": 2, "include_tests": True}
        if project:
            payload["project"] = project
        ok, response, error = cbm_cli(executable, "trace_path", payload, timeout, command_runner)
        if ok:
            call_paths.append({"symbol": name, "result": response})
        else:
            diagnostics.append(f"trace_path({name}) failed: {error}")

    searchable_text = str(seed.get("query_text") or "") + " " + " ".join(
        seed.get("symbols", [])
    ) + " " + " ".join(
        seed.get("primary_files", []) + seed.get("test_files", [])
    )
    if re.search(r"\b(route|endpoint|api|http|rest|controller)\b", searchable_text, re.I):
        payload = {"label": "Route", "limit": 20}
        if project:
            payload["project"] = project
        ok, response, error = cbm_cli(
            executable, "search_graph", payload, timeout, command_runner
        )
        if ok:
            routes.extend(iter_records(response))
        else:
            diagnostics.append(f"route search failed: {error}")

    return {
        "provider_status": "ok",
        "cbm_project": project,
        "primary_files": dedupe(primary_files),
        "test_files": dedupe(test_files),
        "symbols": symbols,
        "call_paths": call_paths,
        "routes": routes,
        "diagnostics": diagnostics,
    }


def merge_symbol_lists(seed_symbols: list[str], graph_symbols: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    seen: set[tuple[str, str | None, Any]] = set()

    for symbol in graph_symbols:
        key = (str(symbol.get("name") or ""), symbol.get("file"), symbol.get("line"))
        if key[0] and key not in seen:
            merged.append(symbol)
            seen.add(key)

    for name in seed_symbols:
        key = (name, None, None)
        if key not in seen:
            merged.append(
                {
                    "name": name,
                    "file": None,
                    "line": None,
                    "kind": None,
                    "qualified_name": None,
                    "source": "seed",
                }
            )
            seen.add(key)
    return merged


def confidence_for(bundle: dict[str, Any]) -> str:
    has_graph = bundle.get("provider") == PROVIDER_CODEBASE_MEMORY and bundle.get(
        "provider_status"
    ) == "ok"
    file_count = len(bundle.get("focus_files", bundle.get("primary_files", []))) + len(
        bundle.get("focus_test_files", bundle.get("test_files", []))
    )
    meaningful_graph_symbol_count = sum(
        1
        for symbol in bundle.get("symbols", [])
        if symbol.get("source") == PROVIDER_CODEBASE_MEMORY
        and is_precise_search_token(str(symbol.get("name") or ""))
    )
    exact_file_count = int(
        bundle.get("diagnostics", {}).get("exact_search_primary_files", 0)
    ) + int(
        bundle.get("diagnostics", {}).get("exact_search_test_files", 0)
    )
    exact_hit_cap = bool(bundle.get("diagnostics", {}).get("exact_search_hit_cap"))
    breadth_assessment = str(bundle.get("breadth_assessment") or "")
    pointer_status = str(bundle.get("diagnostics", {}).get("context_pointers_status") or "")

    if breadth_assessment == "broad":
        return "medium" if file_count >= 1 or meaningful_graph_symbol_count >= 1 else "low"
    if exact_file_count >= 2 and not exact_hit_cap:
        return "high"
    if (
        has_graph
        and pointer_status != "FINDING"
        and meaningful_graph_symbol_count >= 1
        and file_count >= 2
        and not exact_hit_cap
    ):
        return "high"
    if file_count >= 1 or meaningful_graph_symbol_count >= 1:
        return "medium"
    return "low"


def build_context_bundle(
    bead: dict[str, Any],
    repo_root: Path,
    *,
    provider: str,
    cbm_command: str,
    timeout: int,
    allow_index: bool,
    command_runner: CommandRunner = run_subprocess,
    executable_resolver: Callable[[str], str | None] = shutil.which,
) -> dict[str, Any]:
    seed = seed_from_bead(bead, repo_root)
    provider_name = PROVIDER_FALLBACK
    provider_status = "disabled"
    graph: dict[str, Any] = {
        "primary_files": [],
        "test_files": [],
        "symbols": [],
        "call_paths": [],
        "routes": [],
        "diagnostics": [],
        "cbm_project": None,
    }
    gaps: list[str] = []

    executable = executable_resolver(cbm_command)
    should_try_cbm = provider in ("auto", PROVIDER_CODEBASE_MEMORY)
    if should_try_cbm and executable:
        provider_name = PROVIDER_CODEBASE_MEMORY
        graph = query_codebase_memory(
            seed,
            repo_root,
            executable=executable,
            timeout=timeout,
            allow_index=allow_index,
            command_runner=command_runner,
        )
        provider_status = str(graph.get("provider_status") or "ok")
    elif should_try_cbm:
        provider_status = "unavailable"
        gaps.append(f"{cbm_command} not found on PATH; used fallback extraction")

    exact = query_exact_code(seed, repo_root, timeout=timeout)

    candidate_files = dedupe(
        seed["primary_files"]
        + graph.get("primary_files", [])
        + exact.get("primary_files", [])
    )
    candidate_test_files = dedupe(
        seed["test_files"]
        + graph.get("test_files", [])
        + exact.get("test_files", [])
    )
    focus_files = rank_context_files(
        candidate_files,
        exact.get("tokens", []),
        repo_root,
        seed["primary_files"],
        exact.get("primary_files", []),
        limit=FOCUS_PRIMARY_LIMIT,
    )
    remaining_test_limit = max(0, FOCUS_TOTAL_LIMIT - len(focus_files))
    focus_test_files = rank_context_files(
        candidate_test_files,
        exact.get("tokens", []),
        repo_root,
        seed["test_files"],
        exact.get("test_files", []),
        limit=min(FOCUS_TEST_LIMIT, remaining_test_limit),
    )
    breadth = assess_breadth(
        candidate_files,
        candidate_test_files,
        focus_files,
        focus_test_files,
        exact,
        seed_primary_files=seed["primary_files"],
        seed_test_files=seed["test_files"],
        graph_files=dedupe(graph.get("primary_files", []) + graph.get("test_files", [])),
    )
    symbols = merge_symbol_lists(seed["symbols"], graph.get("symbols", []))
    candidate_surface = dedupe(candidate_files + candidate_test_files)
    adr_context = build_adr_context(bead, repo_root, candidate_surface)

    if not focus_files and not focus_test_files:
        gaps.append("No source or test files identified")
    if not symbols:
        gaps.append("No symbols identified")
    if has_action_surface_hint(seed) and exact.get("tokens") and not (
        exact.get("primary_files") or exact.get("test_files")
    ):
        gaps.append("Action/writeback tokens found no exact source-code matches")

    bundle = {
        "provider": provider_name,
        "provider_status": provider_status,
        "primary_files": focus_files,
        "test_files": focus_test_files,
        "focus_files": focus_files,
        "focus_test_files": focus_test_files,
        "candidate_files": candidate_files,
        "candidate_test_files": candidate_test_files,
        "adr_context": adr_context,
        "symbols": symbols,
        "related_beads": seed["related_beads"],
        "memory_hits": [],
        "memory_search": seed["memory_search"],
        "dependency_neighbors": [],
        "call_paths": graph.get("call_paths", []),
        "routes": graph.get("routes", []),
        "breadth_assessment": breadth["assessment"],
        "breadth_reason": breadth["reason"],
        "breadth_signals": breadth["signals"],
        "slice_recommended": breadth["slice_recommended"],
        "confidence": "low",
        "gaps": gaps,
        "diagnostics": {
            "context_pointers_present": seed["context_pointers_present"],
            "context_pointers_status": seed["context_pointers_status"],
            "seed_primary_files": len(seed["primary_files"]),
            "seed_test_files": len(seed["test_files"]),
            "seed_symbols": len(seed["symbols"]),
            "cbm_project": graph.get("cbm_project"),
            "exact_search_tokens": exact.get("tokens", []),
            "exact_search_primary_files": len(exact.get("primary_files", [])),
            "exact_search_test_files": len(exact.get("test_files", [])),
            "exact_search_raw_files": exact.get("raw_file_count", 0),
            "exact_search_hit_cap": exact.get("hit_cap", False),
            "candidate_primary_files": len(candidate_files),
            "candidate_test_files": len(candidate_test_files),
            "focus_primary_files": len(focus_files),
            "focus_test_files": len(focus_test_files),
            "breadth_signals": breadth["signals"],
            "provider_messages": graph.get("diagnostics", []),
        },
    }
    bundle["confidence"] = confidence_for(bundle)
    return bundle


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bead_id", nargs="?", help="Bead id used when --bead-json is omitted")
    parser.add_argument("--bead-json", type=Path, help="Path to bd show --json output")
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--provider",
        choices=("auto", PROVIDER_CODEBASE_MEMORY, PROVIDER_FALLBACK),
        default=os.environ.get("CONTEXT_PROVIDER", "auto"),
    )
    parser.add_argument(
        "--cbm-command",
        default=os.environ.get("CODEBASE_MEMORY_COMMAND", "codebase-memory-mcp"),
    )
    parser.add_argument("--timeout", type=int, default=8)
    parser.add_argument(
        "--allow-index",
        action="store_true",
        default=os.environ.get("CONTEXT_PROVIDER_ALLOW_INDEX", "").lower()
        in {"1", "true", "yes"},
        help="Allow codebase-memory-mcp to refresh its local graph cache",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    if not args.bead_id and args.bead_json is None:
        print("ERROR: bead_id or --bead-json is required", file=sys.stderr)
        return 2

    repo_root = args.repo_root.resolve()
    bead = load_bead(args.bead_id or "", args.bead_json, args.timeout)
    if not bead:
        print(
            json.dumps(
                {
                    "provider": PROVIDER_FALLBACK,
                    "provider_status": "bead-load-failed",
                    "primary_files": [],
                    "test_files": [],
                    "focus_files": [],
                    "focus_test_files": [],
                    "candidate_files": [],
                    "candidate_test_files": [],
                    "symbols": [],
                    "related_beads": [],
                    "memory_hits": [],
                    "memory_search": None,
                    "dependency_neighbors": [],
                    "call_paths": [],
                    "routes": [],
                    "breadth_assessment": "focused",
                    "breadth_reason": "candidate set fits focused context",
                    "breadth_signals": [],
                    "slice_recommended": False,
                    "confidence": "low",
                    "gaps": ["bd show failed or returned invalid JSON"],
                    "diagnostics": {},
                },
                sort_keys=True,
            )
        )
        return 0

    bundle = build_context_bundle(
        bead,
        repo_root,
        provider=args.provider,
        cbm_command=args.cbm_command,
        timeout=args.timeout,
        allow_index=args.allow_index,
    )
    print(json.dumps(bundle, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

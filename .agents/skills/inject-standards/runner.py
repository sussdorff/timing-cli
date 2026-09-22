#!/usr/bin/env python3
"""
inject-standards runner — CLI implementation of the inject-standards skill.

Scans .agents/standards/ (project-local) and ~/.agents/standards/ (user-global)
for markdown standard files and outputs them in the requested format.

Usage:
    python3 runner.py [--mode=full|paths|refs] [--context=<keywords>] [--files=<paths>]
    python3 runner.py [--full-out=<path>] [--paths-out=<path>] [--refs-out=<path>] [--context=...] [--files=...]

When any of --full-out/--paths-out/--refs-out is given, --mode is ignored and the
matching outputs are written to the given paths in a single discovery pass.
This lets callers (e.g. bead-orchestrator Phase 1) materialize multiple modes
without paying the discovery + context-filter cost twice.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


MAX_CHARS_PER_STANDARD = 12000
MAX_TOTAL_CHARS = 48000
SKIP_NAMES = {"_triggers.yml", "_index.yml", "index.yml"}


def _is_contained(path: Path, root: Path) -> bool:
    """Return True iff path's realpath is under root's realpath.

    Resolves both sides via realpath (strict=False to allow probing missing
    descendants). Rejects symlinks that escape the standards root — even
    when the symlink itself lives inside the root.
    """
    try:
        real_path = path.resolve(strict=True)
        real_root = root.resolve(strict=True)
    except (OSError, RuntimeError):
        return False
    try:
        real_path.relative_to(real_root)
        return True
    except ValueError:
        return False


def _standard_roots(cwd: Path, home: Path) -> list[Path]:
    """Ordered standards roots, highest precedence first.

    Tracked ``docs/standards/`` comes first: it is the durable, version-tracked
    copy that travels into every worktree (``.agents/`` is gitignored per repo,
    so a fresh worktree never receives a repo-local ``.agents/standards``). This
    closes the injector-hook gap — with no SessionStart hook copying standards in,
    the tracked ``docs/`` copy is what a dispatched agent can actually read.

    Order (first wins):
      1. ``<repo>/docs/standards``    tracked source of truth, travels w/ worktree
      2. ``<repo>/.agents/standards`` project-local scratch (gitignored)
      3. ``<repo>/standards``         Library marketplace source layout
      4. ``~/.agents/standards``      user-global fallback
    """
    return [
        cwd / "docs" / "standards",
        cwd / ".agents" / "standards",
        cwd / "standards",
        home / ".agents" / "standards",
    ]


def _discover_standards(cwd: Path, home: Path) -> dict[str, Path]:
    """Scan tracked, project-local, then user-global standards dirs.

    Returns a dict of stem -> absolute path. Higher-precedence roots (see
    ``_standard_roots``) win. For each stem within the same root, folder-form
    (<name>/<name>.md) takes precedence over the flat file (<name>.md). Bundle
    members (arbitrary `*.md` files inside a directory) are surfaced as
    `<dir>/<file-stem>`.

    Symlinks whose realpath escapes the containing root are rejected
    (security: prevents reading e.g. /etc/passwd via a planted symlink
    inside a standards root).
    """
    roots = _standard_roots(cwd, home)
    found: dict[str, Path] = {}
    for root in roots:
        if not root.is_dir():
            continue
        # Two-pass: first collect all candidates per stem in this root,
        # then pick folder-form over flat when both exist.
        flat: dict[str, Path] = {}
        folder: dict[str, Path] = {}
        bundle_members: dict[str, Path] = {}
        for item in root.iterdir():
            if item.name in SKIP_NAMES:
                continue
            # Containment guard: reject symlinks that escape this root.
            if not _is_contained(item, root):
                print(
                    f"[inject-standards] Rejecting symlink escape: {item}"
                    f" (does not resolve under {root})",
                    file=sys.stderr,
                )
                continue
            if item.is_file() and item.suffix == ".md":
                flat[item.stem] = item
            elif item.is_dir():
                main = item / f"{item.name}.md"
                if main.exists() and _is_contained(main, root):
                    folder[item.name] = main
                # Also surface bundle members: any `*.md` file directly
                # inside this directory that is NOT the folder-form main
                # file. Keyed as "<dir>/<file-stem>" per SKILL.md.
                for child in item.iterdir():
                    if not child.is_file():
                        continue
                    if child.name in SKIP_NAMES:
                        continue
                    if child.suffix != ".md":
                        continue
                    if not _is_contained(child, root):
                        print(
                            f"[inject-standards] Rejecting bundle-member"
                            f" symlink escape: {child}",
                            file=sys.stderr,
                        )
                        continue
                    if main.exists() and child.resolve() == main.resolve():
                        continue
                    bundle_key = f"{item.name}/{child.stem}"
                    bundle_members[bundle_key] = child
        # Merge: folder-form wins over flat within this root; bundle members
        # are addressed by `<dir>/<stem>` and never collide with flat/folder.
        root_candidates = {**flat, **folder, **bundle_members}
        for stem, path in root_candidates.items():
            if stem not in found:
                found[stem] = path
    return found


def _filter_by_context(standards: dict[str, Path], context: str | None) -> dict[str, Path]:
    """Filter standards by context keywords using simple scoring."""
    if not context:
        return standards
    keywords = [kw.lower() for kw in context.split()]
    if not keywords:
        return standards

    def score(stem: str) -> int:
        s = stem.lower()
        total = 0
        for kw in keywords:
            if kw == s:
                total += 3
            elif kw in s.split("-") or kw in s.split("_"):
                total += 2
            elif kw in s:
                total += 1
        return total

    scored = {stem: path for stem, path in standards.items() if score(stem) > 0}
    if scored:
        return scored
    # If no context matches, return all (do not suppress everything)
    print(
        f"[inject-standards] No standards matched context '{context}',"
        f" returning all {len(standards)} standards.",
        file=sys.stderr,
    )
    return standards


def _tokens_from_files(file_list: str) -> list[str]:
    """Extract context tokens from a comma-separated list of source file paths.

    Per SKILL.md, `--files` provides source file paths used as additional
    context for auto-suggesting relevant standards. We turn each path into
    a set of tokens drawn from:

    - The file extension (without the leading dot), e.g. ``py`` for Python.
    - The path's directory components and the file stem, split on common
      separators (``/``, ``-``, ``_``, ``.``).

    Globs are accepted but not expanded — only the literal path components
    contribute tokens. Tokens are lowercased and de-duplicated while
    preserving first-seen order.
    """
    tokens: list[str] = []
    seen: set[str] = set()

    def _add(token: str) -> None:
        token = token.strip().lower()
        if not token or token in seen:
            return
        # Skip glob wildcards
        if token in {"*", "**", "?"}:
            return
        seen.add(token)
        tokens.append(token)

    for raw in file_list.split(","):
        raw = raw.strip()
        if not raw:
            continue
        p = Path(raw)
        # Extension (without dot) — only when present and non-empty.
        if p.suffix:
            _add(p.suffix.lstrip("."))
        # Path components: directories + stem, split on separators.
        components: list[str] = list(p.parent.parts)
        components.append(p.stem)
        for component in components:
            if not component or component in {".", ".."}:
                continue
            # Split on common separators within a single component.
            for piece in component.replace(".", "-").replace("_", "-").split("-"):
                _add(piece)
    return tokens


def _read_standard(path: Path) -> str:
    """Read a standard file, truncating to the per-standard character budget."""
    try:
        content = path.read_text(encoding="utf-8")
    except OSError:
        return ""
    if len(content) > MAX_CHARS_PER_STANDARD:
        content = content[:MAX_CHARS_PER_STANDARD] + "\n[truncated]"
    return content


def output_full(standards: dict[str, Path]) -> str:
    """Produce --mode=full output."""
    parts: list[str] = ["## Loaded Standards"]
    total_chars = len(parts[0])
    for stem, path in standards.items():
        content = _read_standard(path)
        section = f"\n\n### {stem}\n{content}\n\n---"
        if total_chars + len(section) > MAX_TOTAL_CHARS:
            break
        parts.append(section)
        total_chars += len(section)
    return "\n".join(parts) + "\n"


def output_paths(standards: dict[str, Path]) -> str:
    """Produce --mode=paths output."""
    lines = ["## Standards"]
    for path in standards.values():
        lines.append(f"- {path.resolve()}")
    return "\n".join(lines) + "\n"


def output_refs(standards: dict[str, Path]) -> str:
    """Produce --mode=refs output."""
    lines = ["Add these references:", ""]
    home = Path.home()
    for path in standards.values():
        resolved = path.resolve()
        try:
            rel = resolved.relative_to(home)
            lines.append(f"@~/{rel}")
        except ValueError:
            lines.append(f"@{resolved}")
    return "\n".join(lines) + "\n"


def standard_digest(path: Path) -> str:
    """sha256[:16] of the full standard file, so a review can state exactly
    which standard text it was given."""
    import hashlib

    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        raw = ""
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def output_prompt(standards: dict[str, Path]) -> str:
    """Produce --mode=prompt output: the FULL standard content plus a
    machine-readable digest line per standard, ready to inject into an
    orchestrator/ACPX prompt.

    Unlike --mode=full (which truncates to a loose context budget), prompt mode
    injects the whole standard and digests EXACTLY the injected bytes, so the
    digest provably covers what the reviewer saw — a truncated body must never be
    certified by a full-file digest (clc-uq9g.8, Sol #7). Rules that live near
    the end of a long standard therefore actually reach the reviewer.
    """
    import hashlib

    parts: list[str] = ["## Injected Standards (content + digest)"]
    manifest: list[str] = []
    for stem, path in standards.items():
        try:
            content = path.read_text(encoding="utf-8")  # FULL, not _read_standard
        except OSError:
            content = ""
        dg = hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]
        manifest.append(f"standard-digest: {stem} {dg}")
        parts.append(f"\n\n### {stem}  (digest {dg})\n{content}\n\n---")
    # A compact, greppable manifest at the end for the gate/evidence to parse.
    parts.append("\n\n<!-- standards-manifest\n" + "\n".join(manifest) + "\n-->")
    return "\n".join(parts) + "\n"


def _select_by_keys(
    standards: dict[str, Path], keys: list[str]
) -> dict[str, Path]:
    """Filter discovered standards by explicit keys / glob patterns.

    Per SKILL.md:
      - Exact key match: `adr-location`, `python/style`
      - Glob pattern: `python/*`, `*/test*`

    Rejects keys containing `..`, leading `~`, or absolute paths (path
    traversal guard).
    """
    import fnmatch

    selected: dict[str, Path] = {}
    for key in keys:
        if not key:
            continue
        if ".." in key or key.startswith("~") or key.startswith("/"):
            print(
                f"[inject-standards] Standard keys cannot contain absolute"
                f" paths, ~, or .. segments: {key}",
                file=sys.stderr,
            )
            continue
        if any(ch in key for ch in "*?["):
            matches = {
                stem: path
                for stem, path in standards.items()
                if fnmatch.fnmatch(stem, key)
            }
            if not matches:
                print(
                    f"[inject-standards] Pattern '{key}' matched no standards.",
                    file=sys.stderr,
                )
            selected.update(matches)
        else:
            if key in standards:
                selected[key] = standards[key]
            else:
                print(
                    f"[inject-standards] Standard not found: {key}",
                    file=sys.stderr,
                )
    return selected


def main() -> int:
    parser = argparse.ArgumentParser(
        description="inject-standards: load Library standards into context"
    )
    parser.add_argument(
        "keys",
        nargs="*",
        help="Explicit standard keys or glob patterns (e.g. python/style, python/*)",
    )
    parser.add_argument(
        "--mode",
        choices=["full", "paths", "refs", "prompt"],
        default="full",
        help="Output mode (default: full)",
    )
    parser.add_argument(
        "--context",
        default="",
        help="Space-separated domain keywords for relevance filtering",
    )
    parser.add_argument(
        "--files",
        default="",
        help=(
            "Comma-separated source file paths used as additional context"
            " tokens for auto-suggesting relevant standards"
        ),
    )
    parser.add_argument(
        "--full-out",
        default="",
        help="Write --mode=full output to this path (combine with --paths-out / --refs-out for a single-pass multi-output run)",
    )
    parser.add_argument(
        "--paths-out",
        default="",
        help="Write --mode=paths output to this path",
    )
    parser.add_argument(
        "--refs-out",
        default="",
        help="Write --mode=refs output to this path",
    )
    parser.add_argument(
        "--require",
        default="",
        help=(
            "Comma-separated standard ids that MUST resolve (the requires_standards"
            " delivery guarantee). If any is missing, fail loud with the probed"
            " roots and exit non-zero instead of dispatching against a missing standard."
        ),
    )
    parser.add_argument(
        "--expect-digest",
        default=None,
        help=(
            "Comma-separated <id>:<digest> pairs. Verify the on-disk standard still"
            " matches the digest the review recorded; exit 4 on mismatch."
        ),
    )
    args = parser.parse_args()

    cwd = Path.cwd()
    home = Path.home()

    all_standards = _discover_standards(cwd, home)

    # Delivery guarantee (requires_standards): every required id must resolve in
    # one of the roots. With no injector hook and .agents/ gitignored, this is
    # the orchestrator's only proof that a gate's standard actually reached the
    # worktree before an agent runs against it.
    required = [r.strip() for r in args.require.split(",") if r.strip()]
    if required:
        missing = [rid for rid in required if rid not in all_standards]
        if missing:
            roots = _standard_roots(cwd, home)
            print(
                "[inject-standards] requires_standards NOT satisfied: "
                + ", ".join(missing),
                file=sys.stderr,
            )
            print("[inject-standards] probed roots (first wins):", file=sys.stderr)
            for root in roots:
                mark = "exists" if root.is_dir() else "absent"
                print(f"  - {root}  [{mark}]", file=sys.stderr)
            print(
                "[inject-standards] deliver the standard into a tracked root"
                " (e.g. docs/standards/<id>/<id>.md) or run /library use <id>.",
                file=sys.stderr,
            )
            return 3

    # Digest verification (Sol #7): the caller asserts the on-disk standard still
    # matches the digest the review recorded, catching a standard swapped or
    # edited between injection and review.
    if args.expect_digest is not None:
        for spec in args.expect_digest.split(","):
            spec = spec.strip()
            if not spec or ":" not in spec:
                print(
                    "[inject-standards] malformed --expect-digest entry; expected <id>:<16-hex-digest>",
                    file=sys.stderr,
                )
                return 2
            sid, expected = spec.split(":", 1)
            sid, expected = sid.strip(), expected.strip()
            if (
                not sid
                or len(expected) != 16
                or any(char not in "0123456789abcdef" for char in expected.lower())
            ):
                print(
                    "[inject-standards] malformed --expect-digest entry; expected <id>:<16-hex-digest>",
                    file=sys.stderr,
                )
                return 2
            path = all_standards.get(sid)
            actual = standard_digest(path) if path else None
            if actual != expected:
                print(
                    f"[inject-standards] digest mismatch for {sid!r}: "
                    f"expected {expected!r}, on-disk {actual!r} — the standard changed "
                    "since it was injected/recorded; failing closed.",
                    file=sys.stderr,
                )
                return 4

    standards = all_standards
    # If explicit keys/globs given, select those first; --context further
    # narrows. If no keys given, fall back to context-only filtering.
    if args.keys:
        standards = _select_by_keys(standards, args.keys)
    # Build a combined context string from --context and tokens derived
    # from --files. Both contribute keywords; neither limits the discovery
    # roots.
    context_parts: list[str] = []
    if args.context:
        context_parts.append(args.context)
    if args.files:
        file_tokens = _tokens_from_files(args.files)
        if file_tokens:
            context_parts.append(" ".join(file_tokens))
    combined_context = " ".join(context_parts).strip()
    if combined_context:
        standards = _filter_by_context(standards, combined_context)

    multi_out = any((args.full_out, args.paths_out, args.refs_out))

    if not standards:
        msg = (
            "No Library standards are installed under"
            " docs/standards, .agents/standards, standards, or ~/.agents/standards."
        )
        if multi_out:
            # Materialize empty files so callers can blindly `cat` them.
            for p in (args.full_out, args.paths_out, args.refs_out):
                if p:
                    Path(p).write_text("")
        else:
            print(msg)
        return 0

    if multi_out:
        if args.full_out:
            Path(args.full_out).write_text(output_full(standards))
        if args.paths_out:
            Path(args.paths_out).write_text(output_paths(standards))
        if args.refs_out:
            Path(args.refs_out).write_text(output_refs(standards))
        return 0

    if args.mode == "full":
        print(output_full(standards), end="")
    elif args.mode == "paths":
        print(output_paths(standards), end="")
    elif args.mode == "refs":
        print(output_refs(standards), end="")
    elif args.mode == "prompt":
        print(output_prompt(standards), end="")

    return 0


if __name__ == "__main__":
    sys.exit(main())

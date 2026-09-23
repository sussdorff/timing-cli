"""Regression guard: PEP 723 scripts must be invoked as ``uv run <script>``.

A script that declares inline PEP 723 metadata (``# /// script`` ... ``# ///``)
relies on uv building an isolated environment from that metadata. uv only reads
the metadata when the *script* is the run target:

    uv run path/to/script.py        # OK   -> reads PEP 723, provisions deps
    uv run "$SCRIPT"                # OK   -> same, via shell variable

Running the interpreter with the script as an argument silently bypasses the
metadata and falls back to the caller's ambient environment:

    uv run python path/to/script.py  # BAD -> PEP 723 ignored
    python3 path/to/script.py        # BAD -> needs deps in ambient env
    python "$SCRIPT"                 # BAD -> same

That is precisely the failure that aborted bead-orchestrator Phase 0 with
``TIER_CONFIG_ERROR: PyYAML not installed`` when run from a repo/worktree whose
environment did not happen to carry pyyaml. This test fails if any agent/skill
markdown, TOML, or shell/Python file re-introduces the anti-pattern.

``python -c '...'`` and ``python -m mod`` are inline/module invocations that do
not target a script file and are always allowed.
"""

from __future__ import annotations

import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[4]

# Directories we never scan (vendored envs, VCS, build caches, archived content).
EXCLUDE_DIRS = {
    ".git",
    ".venv",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "archived",
    "worktrees",  # transient git worktree copies under .claude/worktrees/
}

# File types that can contain invocation commands.
SCAN_SUFFIXES = {".md", ".toml", ".py", ".sh", ".bash", ".zsh", ".yml", ".yaml"}

PEP723_MARKER = "# /// script"

# Interpreter token immediately followed by its first argument. The negative
# lookahead skips ``-c`` / ``-m`` (inline code / module execution). The argument
# group captures contiguous non-space text, so it spans both a literal path
# (``$VAR/scripts/foo.py``) and a bare variable reference (``$FOO``). A leading
# backslash + quote handles TOML's escaped ``\"$VAR\"`` form.
INTERP_RE = re.compile(
    r"(?:uv\s+run\s+python|python3|python)\s+"
    r"(?!-[cm]\b)"
    r"\\?[\"']?"
    r"(\$\{?\w+\}?|[^\s\"'\\]+)"
)

# Shell assignment of a *_SCRIPT-style variable to a path. Used to resolve
# variable-indirected invocations back to the script basename.
ASSIGN_RE = re.compile(r"(\w+)=\\?[\"']?(\$?\{?[\w./{}-]*?([\w.-]+\.py))")


def _iter_files() -> list[Path]:
    files: list[Path] = []
    for path in REPO_ROOT.rglob("*"):
        if not path.is_file() or path.suffix not in SCAN_SUFFIXES:
            continue
        if any(part in EXCLUDE_DIRS for part in path.relative_to(REPO_ROOT).parts):
            continue
        files.append(path)
    return files


def _pep723_basenames(files: list[Path]) -> set[str]:
    names: set[str] = set()
    for path in files:
        if path.suffix != ".py":
            continue
        try:
            head = path.read_text(encoding="utf-8")[:600]
        except (OSError, UnicodeDecodeError):
            continue
        if PEP723_MARKER in head:
            names.add(path.name)
    return names


def _var_to_basename(text: str, pep_names: set[str]) -> dict[str, str]:
    """Map shell variables assigned to a PEP 723 script -> that script name."""
    mapping: dict[str, str] = {}
    for var, _full, base in ASSIGN_RE.findall(text):
        if base in pep_names:
            mapping[var] = base
    return mapping


def _strip_var(token: str) -> str:
    return token.lstrip("$").strip("{}")


def test_pep723_scripts_are_invoked_as_uv_run_script() -> None:
    files = _iter_files()
    pep_names = _pep723_basenames(files)
    assert pep_names, "expected to discover at least one PEP 723 script"

    self_name = Path(__file__).name
    violations: list[str] = []

    for path in files:
        if path.name == self_name:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if "python" not in text:
            continue

        var_map = _var_to_basename(text, pep_names)
        rel = path.relative_to(REPO_ROOT)

        for lineno, line in enumerate(text.splitlines(), start=1):
            # Skip negative assertions (a local guard checking the pattern is
            # absent) and explicit opt-outs.
            if "not in" in line or "# pep723-allow" in line:
                continue
            for match in INTERP_RE.finditer(line):
                arg = match.group(1)
                hit: str | None = None
                if "/" in arg or arg.endswith(".py"):
                    # Literal path argument -> check trailing basename.
                    base = arg.rsplit("/", 1)[-1]
                    if base in pep_names:
                        hit = base
                else:
                    # Bare variable reference -> resolve via assignments.
                    resolved = var_map.get(_strip_var(arg))
                    if resolved:
                        hit = resolved
                if hit:
                    violations.append(
                        f"{rel}:{lineno}: invokes PEP 723 script '{hit}' via an "
                        f"interpreter ('{match.group(0).strip()}'); use "
                        f"'uv run <script>' instead. Line: {line.strip()}"
                    )

    assert not violations, (
        "PEP 723 scripts must be run as 'uv run <script>' so uv provisions their "
        "declared deps (cwd-independent). Found anti-pattern invocations:\n"
        + "\n".join(violations)
    )

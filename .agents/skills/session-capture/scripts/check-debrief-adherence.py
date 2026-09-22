#!/usr/bin/env python3
"""
check-debrief-adherence — Lint agent .md files for the debrief contract template.

Checks all agent .md files under agents/ directories for the mandatory
### Debrief block with all four required #### headings.

Required agents (must have debrief template):
    implementer, tdd-test-author, review-agent, verification-agent

Exempt agents (by design — no debrief required):
    explorer, researcher, general-purpose, changelog-updater,
    bead-orchestrator, quick-fix

The exemption list is read from the standard doc at runtime:
    ~/.agents/standards/agents/debrief-contract.md

Falls back to the hardcoded list above if the standard doc is not found.

Usage:
    python3 check-debrief-adherence.py
    python3 check-debrief-adherence.py --search-path /path/to/repo/root
    python3 check-debrief-adherence.py --standard-doc /path/to/debrief-contract.md
    python3 check-debrief-adherence.py --exclude-pattern .claude/worktrees

Exit codes:
    0  All required agents are compliant
    1  One or more agents are missing required debrief sections
"""

import argparse
import re
import sys
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# The four required #### headings inside a ### Debrief block
REQUIRED_H4_HEADINGS: list[str] = [
    "Key Decisions",
    "Challenges Encountered",
    "Surprising Findings",
    "Follow-up Items",
]

# Hardcoded fallback exemption list (used when standard doc is unavailable)
_FALLBACK_EXEMPTIONS: set[str] = {
    "explorer",
    "researcher",
    "general-purpose",
    "changelog-updater",
    "doc-changelog-updater",
    "bead-orchestrator",
    "quick-fix",
}

# Default standard doc location
_DEFAULT_STANDARD_DOC = Path.home() / ".claude" / "standards" / "agents" / "debrief-contract.md"

# Section heading that marks the exemption allowlist in the standard doc
_ALLOWLIST_HEADING = "## Agent Allowlist (Exempt from Debrief Contract)"


# ---------------------------------------------------------------------------
# Exemption loading
# ---------------------------------------------------------------------------

def load_exemptions(standard_doc: Optional[Path] = None) -> set[str]:
    """Load the exemption list from the standard doc, or fall back to hardcoded list.

    The standard doc must contain a section headed by:
        ## Agent Allowlist (Exempt from Debrief Contract)

    Each bullet line under that section (format: "- agent-name") is treated
    as an exempt agent name.

    Args:
        standard_doc: Path to the debrief-contract.md standard doc.
                      If None or file doesn't exist, returns the hardcoded list.

    Returns:
        Set of exempt agent names (without .md extension).
    """
    if standard_doc is None:
        standard_doc = _DEFAULT_STANDARD_DOC

    if not standard_doc.exists():
        return set(_FALLBACK_EXEMPTIONS)

    text = standard_doc.read_text(encoding="utf-8")
    lines = text.splitlines()

    in_allowlist = False
    exemptions: set[str] = set()

    for line in lines:
        stripped = line.strip()
        if stripped == _ALLOWLIST_HEADING:
            in_allowlist = True
            continue
        if in_allowlist:
            # Stop at next ## heading
            if stripped.startswith("## ") and stripped != _ALLOWLIST_HEADING:
                break
            # Collect bullet items
            if stripped.startswith("- "):
                name = stripped[2:].strip()
                if name:
                    exemptions.add(name)

    # If allowlist section was found but empty, return parsed (possibly empty) set
    # If section was not found at all, fall back to hardcoded
    if not in_allowlist:
        return set(_FALLBACK_EXEMPTIONS)

    return exemptions


# ---------------------------------------------------------------------------
# Debrief template checking
# ---------------------------------------------------------------------------

def has_debrief_template(content: str) -> bool:
    """Check whether agent .md content has all four required #### headings.

    The headings must appear inside a ### Debrief block (i.e. after
    '### Debrief' and before the next ## or ### heading).

    Args:
        content: Full text of an agent .md file.

    Returns:
        True if all four required headings are present inside ### Debrief.
    """
    return len(missing_sections(content)) == 0


def missing_sections(content: str) -> list[str]:
    """Return the list of required heading names absent from the debrief block.

    Args:
        content: Full text of an agent .md file.

    Returns:
        List of missing heading names. Empty list means fully compliant.
    """
    lines = content.splitlines()
    debrief_start: Optional[int] = None

    for i, line in enumerate(lines):
        if line.strip() == "### Debrief":
            debrief_start = i
            break

    if debrief_start is None:
        # No debrief block at all — all headings are missing
        return list(REQUIRED_H4_HEADINGS)

    # Collect the debrief block content
    block_lines: list[str] = []
    for line in lines[debrief_start + 1 :]:
        stripped = line.strip()
        # Stop at next ## or ### heading (not ####)
        if re.match(r"^#{2,3}\s+\S", stripped) and not stripped.startswith("####"):
            break
        block_lines.append(line)

    block_text = "\n".join(block_lines)

    # Check for each required #### heading
    absent: list[str] = []
    for heading in REQUIRED_H4_HEADINGS:
        pattern = f"#### {heading}"
        if pattern not in block_text:
            absent.append(heading)

    return absent


# ---------------------------------------------------------------------------
# Directory scanning
# ---------------------------------------------------------------------------

def find_agent_files(search_root: Path) -> list[Path]:
    """Find all agent .md files under agents/ directories within search_root.

    Args:
        search_root: Root path to search recursively.

    Returns:
        List of paths to .md files inside any agents/ subdirectory.
    """
    agent_files: list[Path] = []
    for agents_dir in search_root.rglob("agents"):
        if agents_dir.is_dir():
            for md_file in sorted(agents_dir.glob("*.md")):
                agent_files.append(md_file)
    return agent_files


def _agent_name_from_path(path: Path) -> str:
    """Extract the agent name from its file path (stem without .md).

    Args:
        path: Path to the agent .md file.

    Returns:
        Agent name string (filename stem).
    """
    return path.stem


def check_agents_dir(
    search_root: Path,
    exemptions: Optional[set[str]] = None,
    exclude_pattern: str = ".claude/worktrees",
) -> list[dict]:
    """Check all agent files under search_root for debrief compliance.

    Args:
        search_root: Root directory to search for agents/ subdirectories.
        exemptions: Set of agent names that are exempt from the check.
                    If None, loads from standard doc (or falls back to hardcoded).
        exclude_pattern: Path substring pattern; any agent file whose path
                         contains this string is silently skipped.
                         Defaults to ".claude/worktrees" to avoid false positives
                         from open bead worktrees.

    Returns:
        List of violation dicts, each with keys:
            - "agent": agent name
            - "file": absolute path string
            - "missing": list of missing heading names
        Empty list means all required agents are compliant.
    """
    if exemptions is None:
        exemptions = load_exemptions()

    agent_files = find_agent_files(search_root)
    if exclude_pattern:
        agent_files = [f for f in agent_files if exclude_pattern not in str(f.relative_to(search_root))]
    violations: list[dict] = []

    for md_file in agent_files:
        agent_name = _agent_name_from_path(md_file)

        if agent_name in exemptions:
            continue

        content = md_file.read_text(encoding="utf-8")
        absent = missing_sections(content)

        if absent:
            violations.append({
                "agent": agent_name,
                "file": str(md_file),
                "missing": absent,
            })

    return violations


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """Run debrief adherence check and report results."""
    parser = argparse.ArgumentParser(
        prog="check-debrief-adherence",
        description=(
            "Lint agent .md files for the mandatory debrief template block.\n"
            "Checks all agents under agents/ directories for all four required\n"
            "'#### Key Decisions', '#### Challenges Encountered', \n"
            "'#### Surprising Findings', and '#### Follow-up Items' headings\n"
            "inside a '### Debrief' block."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Exit code 0: all required agents compliant\n"
            "Exit code 1: one or more agents missing required debrief sections"
        ),
    )
    parser.add_argument(
        "--search-path",
        metavar="PATH",
        default=".",
        help="Root path to search for agents/ directories (default: current dir)",
    )
    parser.add_argument(
        "--standard-doc",
        metavar="PATH",
        default=str(_DEFAULT_STANDARD_DOC),
        help=(
            "Path to debrief-contract.md standard doc for reading exemptions "
            f"(default: {_DEFAULT_STANDARD_DOC})"
        ),
    )
    parser.add_argument(
        "--exclude-pattern",
        metavar="PATTERN",
        default=".claude/worktrees",
        help=(
            "Path substring pattern; agent files whose path contains this string "
            "are silently skipped (default: .claude/worktrees)"
        ),
    )
    args = parser.parse_args()

    search_root = Path(args.search_path).resolve()
    standard_doc = Path(args.standard_doc)

    exemptions = load_exemptions(standard_doc)
    violations = check_agents_dir(search_root, exemptions, exclude_pattern=args.exclude_pattern)

    if not violations:
        print("PASS: Debrief adherence check: all agents compliant")
        sys.exit(0)

    print(f"\nFAIL: Debrief adherence check: {len(violations)} agent(s) non-compliant\n")
    for v in violations:
        print(f"  Agent: {v['agent']}")
        print(f"  File:  {v['file']}")
        print(f"  Missing sections inside '### Debrief' block:")
        for section in v["missing"]:
            print(f"    - #### {section}")
        print()
    sys.exit(1)


if __name__ == "__main__":
    main()

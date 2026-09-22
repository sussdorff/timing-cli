#!/usr/bin/env python3
# BD_LINT_CONTRACTS_MARKER
"""
bd_lint_contracts — Architecture Contracts lint check for bead descriptions.

Checks beads with 'touches-contract' label for the mandatory
'## Architecture Contracts Touched' section and validates its structure.

Also detects false negatives: beads that have the section in their description
but are missing the 'touches-contract' label.

Usage:
    python3 bd_lint_contracts.py
    python3 bd_lint_contracts.py --all
    python3 bd_lint_contracts.py --bead CCP-abc
    python3 bd_lint_contracts.py --check-false-negatives

Exit codes:
    0  All checks passed
    1  One or more beads failed validation
"""

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from typing import Optional


# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

@dataclass
class LintError:
    bead_id: str
    error: str

    def __str__(self) -> str:
        return f"[{self.bead_id}] {self.error}"


# ---------------------------------------------------------------------------
# Text helpers
# ---------------------------------------------------------------------------

def _strip_fenced_blocks(text: str) -> str:
    """Remove content inside fenced code blocks (``` ... ```)."""
    return re.sub(r"```[^\n]*\n.*?```", "", text, flags=re.DOTALL)


# ---------------------------------------------------------------------------
# bd CLI wrapper
# ---------------------------------------------------------------------------

def _run(args: list[str], timeout: int = 30) -> tuple[int, str, str]:
    """Run a bd subcommand and return (returncode, stdout, stderr)."""
    try:
        result = subprocess.run(
            ["bd"] + args,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return 1, "", f"bd {args[0]!r} timed out after {timeout}s"
    except FileNotFoundError:
        return 1, "", "bd: command not found"


class _BdUnavailableError(Exception):
    """Raised when the bd CLI is unavailable or returns an unexpected error."""


def _get_beads_json(extra_args: list[str]) -> list[dict]:
    """Run bd list with extra_args and return parsed JSON list.

    Raises _BdUnavailableError when bd is unavailable or fails, so callers
    in the main code paths can propagate a hard exit-1 instead of silently
    returning an empty list.
    """
    rc, stdout, stderr = _run(["list", "--json", "--limit", "0"] + extra_args)
    if rc != 0:
        raise _BdUnavailableError(f"bd list failed: {stderr.strip() or 'unknown error'}")
    try:
        data = json.loads(stdout) if stdout.strip() else []
        if not isinstance(data, list):
            raise _BdUnavailableError("bd list returned unexpected JSON (not a list)")
        return data
    except json.JSONDecodeError as exc:
        raise _BdUnavailableError(f"bd list JSON parse error: {exc}") from exc


def _get_bead_detail(bead_id: str) -> Optional[dict]:
    """Fetch full bead details including description."""
    rc, stdout, stderr = _run(["show", bead_id, "--json"])
    if rc != 0:
        return None
    try:
        data = json.loads(stdout)
        return data[0] if isinstance(data, list) and data else None
    except (json.JSONDecodeError, IndexError):
        return None


def _bead_has_label(bead_id: str, label: str) -> bool:
    """Return True if the bead has the given label."""
    rc, stdout, _ = _run(["label", "list", bead_id])
    return any(line.strip() == label or line.strip() == f"- {label}" for line in stdout.splitlines())


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

def extract_section(description: str, header: str) -> Optional[str]:
    """
    Extract the body of a markdown section identified by ``header``.

    Returns the text between ``header`` and the next ``## `` heading (exclusive),
    or ``None`` if the header is not found.
    """
    lines = description.split("\n")
    in_section = False
    section_lines: list[str] = []

    for line in lines:
        if line.rstrip() == header:
            in_section = True
            continue
        if in_section:
            # Stop at any next level-2 heading
            if line.startswith("## "):
                break
            section_lines.append(line)

    return "\n".join(section_lines) if in_section else None


def _bullets_in(text: str) -> list[str]:
    """Return stripped bullet lines (starting with '- ') from *text*."""
    return [ln.strip() for ln in text.split("\n") if ln.strip().startswith("- ")]


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

# ADR bullet: "- ADR-NNN (Name): description"
_ADR_RE = re.compile(r"^-\s+ADR-\d+\s+\([^)]+\):\s+\S", re.IGNORECASE)

# Optional bullet prefixes — valid if present, must use exact format
_OPTIONAL_BULLET_RES: list[re.Pattern] = [
    re.compile(r"^-\s+Helper:\s+\S"),
    re.compile(r"^-\s+Enforcer-Proactive:\s+\S"),
    re.compile(r"^-\s+Enforcer-Reactive:\s+\S"),
]

# Valid gap-close markers
_GAP_VALID_RES: list[re.Pattern] = [
    re.compile(r"^-\s+\[\s*\]\s+None$", re.IGNORECASE),
    re.compile(r"^-\s+\[\s*\]\s+\[ADR-NEEDED\]\s+\S"),
    re.compile(r"^-\s+\[\s*\]\s+\[HELPER-NEEDED\]\s+\S"),
    re.compile(r"^-\s+\[\s*\]\s+\[ENFORCER-PROACTIVE-NEEDED\]\s+\S"),
    re.compile(r"^-\s+\[\s*\]\s+\[ENFORCER-REACTIVE-NEEDED\]\s+\S"),
]


def validate_contracts_section(bead_id: str, description: str) -> list[str]:
    """
    Validate the '## Architecture Contracts Touched' section in *description*.

    Rules:
    - 3a  Empty section (header present, no bullets)  → FAIL
    - 3b  ≥1 bullet matching ADR-NNN (Name): ...      → FAIL if absent
    - 3c  '## Gaps to Close' section must exist with ≥1 valid marker bullet

    Fenced code blocks are stripped before validation so that documentation
    examples embedded in the description do not interfere with parsing.

    Returns a list of error strings (empty = OK).
    """
    errors: list[str] = []

    # Strip fenced blocks so embedded documentation examples don't confuse the parser
    description = _strip_fenced_blocks(description)

    # Must have the section at all
    section_content = extract_section(description, "## Architecture Contracts Touched")
    if section_content is None:
        errors.append("Missing section '## Architecture Contracts Touched'")
        return errors

    bullets = _bullets_in(section_content)

    # Rule 3a: empty section
    if not bullets:
        errors.append(
            "Section '## Architecture Contracts Touched' is empty (rule 3a: "
            "at least one '- ADR-NNN (Name): ...' bullet is required)"
        )
        return errors  # No point checking 3b if section is empty

    # Rule 3b: at least one ADR bullet in correct format
    if not any(_ADR_RE.match(b) for b in bullets):
        errors.append(
            "Section '## Architecture Contracts Touched' requires ≥1 ADR bullet in format "
            "'- ADR-NNN (Name): <description>' (rule 3b; Helper/Enforcer bullets are "
            "optional but do not satisfy this requirement)"
        )

    # Rule 3b (continued): optional bullets, if present, must use a recognised prefix
    for bullet in bullets:
        if _ADR_RE.match(bullet):
            continue  # Valid ADR bullet — skip
        if any(p.match(bullet) for p in _OPTIONAL_BULLET_RES):
            continue  # Valid optional bullet — skip
        errors.append(
            f"Invalid bullet in '## Architecture Contracts Touched': {bullet!r}. "
            "Each non-ADR bullet must use one of the recognised optional prefixes: "
            "'- Helper: <path>', '- Enforcer-Proactive: <path>', or '- Enforcer-Reactive: <path>' (rule 3b)"
        )

    # Rule 3c: Gaps to Close section
    gaps_content = extract_section(description, "## Gaps to Close")
    if gaps_content is None:
        errors.append(
            "Missing section '## Gaps to Close' (rule 3c: required for beads with "
            "'touches-contract' label; use '- [ ] None' if there are no gaps)"
        )
    else:
        gap_bullets = _bullets_in(gaps_content)
        checkbox_bullets = [b for b in gap_bullets if re.match(r"^-\s+\[", b)]

        if not checkbox_bullets:
            errors.append(
                "Section '## Gaps to Close' has no checkbox bullets (rule 3c: "
                "must contain '- [ ] None' or '- [ ] [*-NEEDED] ...')"
            )
        else:
            valid = [
                b for b in checkbox_bullets
                if any(p.match(b) for p in _GAP_VALID_RES)
            ]
            if not valid:
                errors.append(
                    "Section '## Gaps to Close' has bullets but none match required format "
                    "(rule 3c: use '- [ ] None' or '- [ ] [ADR-NEEDED] ...' / "
                    "[HELPER-NEEDED] / [ENFORCER-PROACTIVE-NEEDED] / [ENFORCER-REACTIVE-NEEDED])"
                )
            else:
                # Rule 3c (mutual exclusion): - [ ] None cannot coexist with NEEDED markers
                _NONE_RE = _GAP_VALID_RES[0]  # The None pattern is index 0
                none_bullets = [b for b in checkbox_bullets if _NONE_RE.match(b)]
                needed_bullets = [b for b in checkbox_bullets if not _NONE_RE.match(b)]
                if none_bullets and needed_bullets:
                    errors.append(
                        "Section '## Gaps to Close' contains '- [ ] None' alongside other gap markers — "
                        "these are mutually exclusive (rule 3c): remove '- [ ] None' if there are gaps, "
                        "or remove all [*-NEEDED] markers if there are no gaps"
                    )

    return errors


# ---------------------------------------------------------------------------
# Main lint logic
# ---------------------------------------------------------------------------

def check_false_negatives(labeled_ids: set[str], all_beads: list[dict]) -> list[LintError]:
    """
    Rule Y: Detect beads whose description contains '## Architecture Contracts Touched'
    but that lack the 'touches-contract' label.
    """
    errors: list[LintError] = []

    for bead in all_beads:
        bead_id = bead.get("id", "")
        if bead_id in labeled_ids:
            continue  # Already checked via labeled path

        description = bead.get("description") or ""
        stripped = _strip_fenced_blocks(description)
        if "## Architecture Contracts Touched" in stripped:
            errors.append(LintError(
                bead_id=bead_id,
                error=(
                    "Section '## Architecture Contracts Touched' found in description "
                    "but bead lacks 'touches-contract' label (rule Y). "
                    "Add the label: bd label add " + bead_id + " touches-contract"
                ),
            ))

    return errors


def lint_bead(bead_id: str) -> list[LintError]:
    """Lint a single bead regardless of its label (--bead flag)."""
    errors: list[LintError] = []

    detail = _get_bead_detail(bead_id)
    if detail is None:
        return [LintError(bead_id=bead_id, error=f"Could not load bead '{bead_id}'")]

    description = detail.get("description") or ""
    has_section = "## Architecture Contracts Touched" in _strip_fenced_blocks(description)
    has_label = _bead_has_label(bead_id, "touches-contract")

    # Rule Y for single-bead mode
    if has_section and not has_label:
        errors.append(LintError(
            bead_id=bead_id,
            error=(
                "Section '## Architecture Contracts Touched' found but bead lacks "
                "'touches-contract' label (rule Y). "
                "Add: bd label add " + bead_id + " touches-contract"
            ),
        ))

    if has_label:
        for msg in validate_contracts_section(bead_id, description):
            errors.append(LintError(bead_id=bead_id, error=msg))

    return errors


def lint_all(status: str) -> list[LintError]:
    """Lint all beads with 'touches-contract' label + false-negative check.

    Raises _BdUnavailableError if bd cannot be reached.
    """
    extra = ["--all"] if status == "all" else ["--status", "open"]
    labeled_beads = _get_beads_json(["--label", "touches-contract"] + extra)
    all_beads = _get_beads_json(extra)

    all_errors: list[LintError] = []
    labeled_ids: set[str] = set()

    for bead in labeled_beads:
        bead_id = bead.get("id", "")
        labeled_ids.add(bead_id)
        description = bead.get("description") or ""
        for msg in validate_contracts_section(bead_id, description):
            all_errors.append(LintError(bead_id=bead_id, error=msg))

    # False-negative check (rule Y)
    all_errors.extend(check_false_negatives(labeled_ids, all_beads))

    return all_errors


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        prog="bd-lint-contracts",
        description=(
            "Lint bead descriptions for the mandatory 'Architecture Contracts Touched' section.\n"
            "By default checks open beads that carry the 'touches-contract' label."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Exit code 0: all checks passed\n"
            "Exit code 1: one or more beads failed validation\n\n"
            "To use as 'bd lint --check=architecture-contracts' (preferred — works in CI):\n"
            "  bash skills/cognovis-beads/scripts/install-bd-wrapper.sh\n\n"
            "Legacy (requires sourcing in each shell):\n"
            "  source skills/cognovis-beads/scripts/bd-lint-extension.sh"
        ),
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Include closed beads (default: open beads only)",
    )
    parser.add_argument(
        "--bead",
        metavar="ID",
        help="Check a single bead by ID (ignores --all)",
    )
    parser.add_argument(
        "--check-false-negatives",
        action="store_true",
        help="Only run the false-negative check (rule Y), skip label-based validation",
    )
    args = parser.parse_args()

    status = "all" if args.all else "open"

    try:
        if args.bead:
            all_errors = lint_bead(args.bead)
        elif args.check_false_negatives:
            extra = ["--all"] if args.all else ["--status", "open"]
            all_beads = _get_beads_json(extra)
            all_errors = check_false_negatives(set(), all_beads)
        else:
            all_errors = lint_all(status)
    except _BdUnavailableError as exc:
        print(f"\n\u274c Architecture contracts lint: bd unavailable — {exc}\n", file=sys.stderr)
        sys.exit(1)

    if all_errors:
        print(f"\n\u274c Architecture contracts lint: {len(all_errors)} error(s) found\n")
        for err in all_errors:
            print(f"  {err}")
        print()
        sys.exit(1)
    else:
        print("\u2713 Architecture contracts lint: all checks passed")


if __name__ == "__main__":
    main()

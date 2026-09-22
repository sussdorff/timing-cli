"""
Bead Orchestrator — Plan Review Gate
=====================================

Phase 1.5 gate logic: determines whether a bead should pass through
the Plan Review Gate before proceeding to implementation.

Size categories:
    S  — micro, small, empty non-feature → skip gate
    M+ — medium, large, xl, extra-large, empty feature → trigger gate
"""

from __future__ import annotations

from pathlib import Path


def _classify_severity(text: str) -> str:
    """Severity classifier based on bracketed tags in review output.

    Returns one of "CRITICAL", "WARNING", "NOTE", or "NONE". This is a
    self-contained regex-based classifier with no external dependencies.
    """
    for level in ("CRITICAL", "WARNING", "NOTE"):
        if f"[{level}]" in text:
            return level
    return "NONE"

# Efforts that map to S (skip gate)
_SMALL_EFFORTS = {"micro", "small"}

# Efforts that map to M+ (trigger gate)
_LARGE_EFFORTS = {"medium", "large", "xl", "extra-large"}


def classify_bead_size(effort: str, bead_type: str = "") -> str:
    """Map metadata.effort to size category.

    Args:
        effort: One of "micro", "small", "medium", "large", "xl", "extra-large", or "" (unknown).
        bead_type: Bead type string (e.g. "feature", "task", "bug").

    Returns:
        "S" if the gate should be skipped, "M+" if the gate should run.
    """
    effort = effort.strip().lower()
    bead_type = bead_type.strip().lower()
    if effort in _SMALL_EFFORTS:
        return "S"
    if effort in _LARGE_EFFORTS:
        return "M+"
    # Empty/unknown effort: feature beads default to M+, everything else to S
    if bead_type == "feature":
        return "M+"
    return "S"


def should_run_gate(
    effort: str,
    bead_type: str = "",
    skip_gates: bool = False,
) -> bool:
    """Return True if the Plan Review Gate should run for this bead.

    Args:
        effort: Bead effort value from metadata.
        bead_type: Bead type string.
        skip_gates: When True, gate is bypassed regardless of size.

    Returns:
        True if gate should run, False if it should be skipped.
    """
    if skip_gates:
        return False
    return classify_bead_size(effort, bead_type) == "M+"


def is_council_available(council_skill_path: str | None = None) -> bool:
    """Check if the council skill is available by verifying council.py exists.

    Args:
        council_skill_path: Path to council.py. Caller must provide the path
            explicitly; there is no default. Pass None to indicate the path
            is unknown/unavailable (returns False).

    Returns:
        True if the file exists at the given path, False otherwise.
    """
    if council_skill_path is None:
        return False
    return Path(council_skill_path).exists()


def parse_gate_result(gate_output: str) -> dict[str, str]:
    """Parse council/reviewer output into a gate result dict.

    Uses council.py's classify_severity() internally (with fallback).

    Args:
        gate_output: Raw text output from the council or reviewer agent.

    Returns:
        Dict with keys:
            status   — "CRITICAL" | "WARNING" | "CLEAN"
            findings — the raw gate_output text
    """
    gate_output = gate_output or ""
    severity = _classify_severity(gate_output)
    # NOTE and NONE both map to CLEAN — agent.md treats them identically (proceed, no notes appended)
    status = severity if severity in ("CRITICAL", "WARNING") else "CLEAN"
    return {"status": status, "findings": gate_output}

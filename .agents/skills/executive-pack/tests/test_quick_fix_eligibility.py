"""Quick-tier eligibility gate: which beads may take the short path.

This is the bead-shaped gate that also decides whether implementation may run on
a foreign family (standards/dispatch/model-routing.md). Extracted from the former
line/tier smoke matrix when route profiles were removed with ADR-0009.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
# The single-bead loop's compatibility copy was deleted with the rest of its
# scripts (clc-rm0o). The live gate lives with the bead tooling that dispatches
# quick fixes.
ELIGIBILITY_SCRIPT = (
    REPO_ROOT
    / "skills"
    / "executive-pack"
    / "scripts"
    / "check_quick_fix_eligibility.py"
)

def run(
    script: Path,
    *,
    stdin: str = "",
    args: list[str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run a helper script as a subprocess and return the completed process."""
    return subprocess.run(
        [sys.executable, str(script)] + (args or []),
        input=stdin,
        capture_output=True,
        text=True,
        timeout=15,
    )


def _bead(
    *,
    bead_type: str = "task",
    effort: str = "small",
    labels: list[str] | None = None,
) -> list[dict]:
    return [
        {
            "id": "smoke-bead-1",
            "title": "Smoke test bead",
            "type": bead_type,
            "labels": labels or [],
            "metadata": {"effort": effort},
        }
    ]


# ===========================================================================
# AC1 + AC3: cld line — GSD and PAUL non-quick routing
# ===========================================================================


class TestQuickIneligibleBlocked:
    """AC5: Quick-ineligible beads are rejected by -bq unless --force-tier=quick."""

    def test_medium_effort_bead_is_rejected_by_bq(self) -> None:
        """A medium-effort bead must be rejected without --force-tier."""
        bead = _bead(bead_type="task", effort="medium")
        result = run(ELIGIBILITY_SCRIPT, stdin=json.dumps(bead))
        assert result.returncode == 1, (
            f"medium-effort bead must be rejected by -bq; "
            f"stdout={result.stdout!r} stderr={result.stderr!r}"
        )
        assert "-bq rejected" in result.stderr, "Rejection message must say '-bq rejected'"

    def test_large_effort_bead_is_rejected_by_bq(self) -> None:
        """A large-effort bead must be rejected without --force-tier."""
        bead = _bead(bead_type="task", effort="large")
        result = run(ELIGIBILITY_SCRIPT, stdin=json.dumps(bead))
        assert result.returncode == 1
        assert "effort" in result.stderr

    def test_feature_type_bead_is_rejected_by_bq(self) -> None:
        """Feature type beads are ineligible for quick tier."""
        bead = _bead(bead_type="feature", effort="small")
        result = run(ELIGIBILITY_SCRIPT, stdin=json.dumps(bead))
        assert result.returncode == 1, (
            f"feature-type bead must be rejected by -bq; stderr={result.stderr!r}"
        )
        assert "type" in result.stderr

    def test_quick_ineligible_message_is_useful(self) -> None:
        """Rejection message must mention the specific failing criterion."""
        bead = _bead(bead_type="task", effort="medium")
        result = run(ELIGIBILITY_SCRIPT, stdin=json.dumps(bead))
        assert result.returncode == 1
        stderr = result.stderr
        # Message must mention effort= and the actual effort value
        assert "effort" in stderr
        assert "medium" in stderr

    def test_type_rejection_message_mentions_type(self) -> None:
        """Feature rejection must mention type and value."""
        bead = _bead(bead_type="feature", effort="small")
        result = run(ELIGIBILITY_SCRIPT, stdin=json.dumps(bead))
        assert result.returncode == 1
        assert "feature" in result.stderr

    def test_micro_effort_task_is_eligible(self) -> None:
        """Micro-effort task must pass eligibility check."""
        bead = _bead(bead_type="task", effort="micro")
        result = run(ELIGIBILITY_SCRIPT, stdin=json.dumps(bead))
        assert result.returncode == 0, (
            f"micro-effort task must be eligible; stderr={result.stderr!r}"
        )

    def test_small_effort_bug_is_eligible(self) -> None:
        """Small-effort bug must pass eligibility check."""
        bead = _bead(bead_type="bug", effort="small")
        result = run(ELIGIBILITY_SCRIPT, stdin=json.dumps(bead))
        assert result.returncode == 0, (
            f"small-effort bug must be eligible; stderr={result.stderr!r}"
        )

    def test_force_tier_quick_bypasses_effort_check(self) -> None:
        """--force-tier=quick bypasses effort check (but not PIPELINE_SURFACES)."""
        bead = _bead(bead_type="task", effort="large")
        result = run(
            ELIGIBILITY_SCRIPT,
            stdin=json.dumps(bead),
            args=["--force-tier=quick"],
        )
        assert result.returncode == 0, (
            f"--force-tier=quick must bypass effort check; stderr={result.stderr!r}"
        )

    def test_force_tier_quick_bypasses_type_check(self) -> None:
        """--force-tier=quick bypasses type check (but not PIPELINE_SURFACES)."""
        bead = _bead(bead_type="feature", effort="small")
        result = run(
            ELIGIBILITY_SCRIPT,
            stdin=json.dumps(bead),
            args=["--force-tier=quick"],
        )
        assert result.returncode == 0


# ===========================================================================
# Final f1b audit
# ===========================================================================

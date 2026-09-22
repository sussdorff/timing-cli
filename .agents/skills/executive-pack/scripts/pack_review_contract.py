"""Small validation helpers for prompt-owned Executive Pack review.

The repository delivery owner, not this module, selects actors and progresses the
review conversation. These helpers protect only the observable delivery seams:
required perspectives, repair-session continuity, the single cumulative repair
dispatch, and opaque terminal evidence.
"""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import re
import subprocess
from typing import Any


REQUIRED_PERSPECTIVES = {
    "agentic_acceptance",
    "adversarial",
    "security",
    "project",
}
COMPLETION_OUTCOMES = {"passed", "not_applicable"}
REPAIR_OUTCOME = "changes_requested"
REPAIR_SEVERITIES = {"medium", "high", "critical"}
INTERRUPT_DISPOSITIONS = {
    "disputed",
    "contradictory",
    "suspicious",
    "intent_mismatch",
}
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
SESSION_CLOSE_RE = re.compile(r"^sc-[0-9a-z]+$")
HANDOFF_CONTEXT_FIELDS = {
    "contract_and_adrs",
    "open_work",
    "relevant_paths",
    "evidence",
}
REPAIR_DISPATCH_MODE = "cumulative_post_review_bugfix"
REPAIR_REENTRY_FORBIDDEN = (
    "implementation-loop",
    "tdd-test-author",
    "member_sequence",
)


class PackReviewError(ValueError):
    """Raised when review evidence cannot authorize normal progression."""


def _text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PackReviewError(f"{field} must be non-empty text")
    return value.strip()


def _finding_ids(findings: object, field: str) -> list[str]:
    if not isinstance(findings, list):
        raise PackReviewError(f"{field} must be a list")
    ids = [
        _text(item.get("id"), f"{field} finding id")
        if isinstance(item, dict)
        else _text(None, f"{field} finding id")
        for item in findings
    ]
    if len(ids) != len(set(ids)):
        raise PackReviewError(f"{field} finding ids must be unique")
    return ids


def _git(repository: Path, *args: str) -> str:
    try:
        return subprocess.run(
            ["git", "-C", str(repository), *args],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError) as error:
        raise PackReviewError("repository must be a readable Git worktree") from error


def _is_ancestor(repository: Path, ancestor: str, descendant: str) -> bool:
    try:
        result = subprocess.run(
            [
                "git",
                "-C",
                str(repository),
                "merge-base",
                "--is-ancestor",
                ancestor,
                descendant,
            ],
            capture_output=True,
            text=True,
        )
    except OSError as error:
        raise PackReviewError("repository must be a readable Git worktree") from error
    if result.returncode not in {0, 1}:
        raise PackReviewError("candidate ancestry could not be verified")
    return result.returncode == 0


def create_implementation_handoff(
    *,
    repository: Path,
    previous_logical_owner: str,
    logical_owner: str,
    old_session: str,
    new_session: str,
    candidate_sha: str,
    previous_remaining_findings: list[dict[str, Any]],
    remaining_findings: list[dict[str, Any]],
    context: dict[str, Any],
) -> dict[str, Any]:
    """Validate one compact, committed implementation-session handoff.

    This protects the data boundary only. The delivery owner remains responsible
    for stopping the old writer before dispatching the new session.
    """

    owner = _text(logical_owner, "logical_owner")
    if owner != _text(previous_logical_owner, "previous_logical_owner"):
        raise PackReviewError("logical implementation owner cannot change at handoff")
    old = _text(old_session, "old_session")
    new = _text(new_session, "new_session")
    if old == new:
        raise PackReviewError("handoff requires distinct old and new sessions")
    if not SHA_RE.fullmatch(candidate_sha):
        raise PackReviewError("candidate_sha must be a full lowercase Git SHA")

    worktree = Path(repository)
    if _git(worktree, "rev-parse", "HEAD") != candidate_sha:
        raise PackReviewError("handoff candidate is stale and does not equal worktree HEAD")
    if _git(worktree, "status", "--porcelain", "--untracked-files=all"):
        raise PackReviewError("handoff requires a clean worktree with all work committed")

    prior_ids = _finding_ids(previous_remaining_findings, "previous_remaining_findings")
    current_ids = _finding_ids(remaining_findings, "remaining_findings")
    if prior_ids != current_ids or previous_remaining_findings != remaining_findings:
        raise PackReviewError("handoff must preserve every remaining finding exactly")
    if not isinstance(context, dict) or set(context) != HANDOFF_CONTEXT_FIELDS:
        raise PackReviewError(
            "compact handoff context fields must be exactly: "
            + ", ".join(sorted(HANDOFF_CONTEXT_FIELDS))
        )
    normalized_context: dict[str, list[str]] = {}
    for field in sorted(HANDOFF_CONTEXT_FIELDS):
        values = context[field]
        if not isinstance(values, list):
            raise PackReviewError(f"handoff context {field} must be a list")
        normalized_context[field] = [
            _text(value, f"handoff context {field} item") for value in values
        ]

    return {
        "logical_owner": owner,
        "session_lineage": {"old_session": old, "new_session": new},
        "candidate_sha": candidate_sha,
        "remaining_findings": deepcopy(remaining_findings),
        "context": normalized_context,
    }


def accept_implementation_handoff(
    history: dict[str, Any], handoff: dict[str, Any], *, repository: Path
) -> dict[str, Any]:
    """Rotate repair convergence to a previously validated compact handoff."""

    if not isinstance(history, dict) or not isinstance(handoff, dict):
        raise PackReviewError("repair history and handoff must be objects")
    if set(handoff) != {
        "logical_owner",
        "session_lineage",
        "candidate_sha",
        "remaining_findings",
        "context",
    }:
        raise PackReviewError("implementation handoff has unexpected fields")
    lineage = handoff.get("session_lineage")
    if not isinstance(lineage, dict) or set(lineage) != {"old_session", "new_session"}:
        raise PackReviewError("handoff session lineage is invalid")
    old = _text(lineage.get("old_session"), "handoff old_session")
    new = _text(lineage.get("new_session"), "handoff new_session")
    if old == new:
        raise PackReviewError("handoff requires distinct old and new sessions")
    if history.get("repair_session") != old:
        raise PackReviewError("handoff is stale or replayed for this repair session")
    if history.get("pending_dispatch") is not None:
        raise PackReviewError("cannot hand off while a repair dispatch is pending")
    if handoff.get("remaining_findings") != history.get("remaining_findings"):
        raise PackReviewError("handoff remaining findings do not match repair history")
    owner = _text(handoff.get("logical_owner"), "logical_owner")
    if history.get("logical_owner") != owner:
        raise PackReviewError("handoff changes the logical implementation owner")
    candidate = _text(handoff.get("candidate_sha"), "candidate_sha")
    if not SHA_RE.fullmatch(candidate):
        raise PackReviewError("handoff candidate must be a full lowercase Git SHA")
    context = handoff.get("context")
    if not isinstance(context, dict) or set(context) != HANDOFF_CONTEXT_FIELDS:
        raise PackReviewError("implementation handoff context is invalid")
    for field in HANDOFF_CONTEXT_FIELDS:
        values = context[field]
        if not isinstance(values, list):
            raise PackReviewError(f"handoff context {field} must be a list")
        for value in values:
            _text(value, f"handoff context {field} item")
    _finding_ids(handoff.get("remaining_findings"), "remaining_findings")
    worktree = Path(repository)
    if _git(worktree, "rev-parse", "HEAD") != candidate:
        raise PackReviewError("handoff candidate is stale and does not equal worktree HEAD")
    if _git(worktree, "status", "--porcelain", "--untracked-files=all"):
        raise PackReviewError("handoff acceptance requires a clean committed worktree")
    prior_candidate = history.get("candidate_sha")
    if not isinstance(prior_candidate, str) or not SHA_RE.fullmatch(prior_candidate):
        raise PackReviewError("repair history is not bound to a candidate")
    if not _is_ancestor(worktree, prior_candidate, candidate):
        raise PackReviewError("handoff candidate must descend from repair history")

    updated = deepcopy(history)
    updated["repair_session"] = new
    updated["logical_owner"] = owner
    updated["candidate_sha"] = candidate
    updated.setdefault("session_handoffs", []).append(deepcopy(handoff))
    return updated


def evaluate_perspectives(
    perspectives: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    """Validate final perspectives and select repair or interrupt findings.

    Perspective answers remain natural-language review evidence. The caller
    normalizes only the small facts needed at this boundary; no actor route,
    provider profile, exact verdict schema, or candidate lifecycle is accepted.
    """

    if not isinstance(perspectives, list):
        raise PackReviewError("perspectives must be a list")
    by_kind: dict[str, dict[str, Any]] = {}
    for perspective in perspectives:
        if not isinstance(perspective, dict):
            raise PackReviewError("each perspective must be an object")
        kind = _text(perspective.get("kind"), "perspective kind")
        if kind in by_kind:
            raise PackReviewError(f"duplicate {kind} perspective")
        by_kind[kind] = perspective

    missing = sorted(REQUIRED_PERSPECTIVES - set(by_kind))
    if missing:
        raise PackReviewError(f"missing required perspective: {', '.join(missing)}")
    unknown = sorted(set(by_kind) - REQUIRED_PERSPECTIVES)
    if unknown:
        raise PackReviewError(f"unknown perspective kind: {', '.join(unknown)}")

    accepted: list[dict[str, Any]] = []
    interrupts: list[dict[str, str]] = []
    for kind in sorted(REQUIRED_PERSPECTIVES):
        perspective = by_kind[kind]
        outcome = _text(perspective.get("outcome"), f"{kind} outcome").lower()
        if outcome not in COMPLETION_OUTCOMES | {REPAIR_OUTCOME}:
            raise PackReviewError(f"non-passing {kind} perspective: {outcome}")
        if kind == "agentic_acceptance" and outcome == REPAIR_OUTCOME:
            raise PackReviewError("agentic_acceptance cannot request source changes")
        findings = perspective.get("findings", [])
        if not isinstance(findings, list):
            raise PackReviewError(f"{kind} findings must be a list")
        perspective_accepted: list[dict[str, Any]] = []
        perspective_interrupts: list[dict[str, str]] = []
        for finding in findings:
            if not isinstance(finding, dict):
                raise PackReviewError(f"{kind} finding must be an object")
            finding_id = _text(finding.get("id"), "finding id")
            disposition = _text(
                finding.get("disposition"), "finding disposition"
            ).lower()
            if disposition in INTERRUPT_DISPOSITIONS:
                perspective_interrupts.append(
                    {
                        "finding_id": finding_id,
                        "reason": disposition,
                        "perspective": kind,
                    }
                )
                continue
            severity = _text(finding.get("severity"), "finding severity").lower()
            if disposition == "accepted" and severity in REPAIR_SEVERITIES:
                perspective_accepted.append(deepcopy(finding))
        if outcome == "not_applicable" and findings:
            raise PackReviewError(f"not_applicable {kind} perspective has findings")
        if outcome == "passed" and perspective_accepted:
            raise PackReviewError(
                f"passed {kind} perspective has accepted substantive findings"
            )
        if outcome in COMPLETION_OUTCOMES and perspective_interrupts:
            raise PackReviewError(
                f"{outcome} {kind} perspective has interrupt findings"
            )
        if outcome == REPAIR_OUTCOME and not (
            perspective_accepted or perspective_interrupts
        ):
            raise PackReviewError(
                f"changes_requested {kind} perspective has no actionable finding"
            )
        accepted.extend(perspective_accepted)
        interrupts.extend(perspective_interrupts)
    return {"accepted_findings": accepted, "interrupts": interrupts}


def start_repair_convergence(
    *,
    repair_session: str,
    accepted_findings: list[dict[str, Any]],
    logical_owner: str,
    candidate_sha: str,
) -> dict[str, Any]:
    """Bind one candidate-owned repair lineage with its current writing session."""

    session = _text(repair_session, "repair_session")
    owner = _text(logical_owner, "logical_owner")
    if not SHA_RE.fullmatch(candidate_sha):
        raise PackReviewError("candidate_sha must be a full lowercase Git SHA")
    if not isinstance(accepted_findings, list):
        raise PackReviewError("accepted_findings must be a list")
    _finding_ids(accepted_findings, "accepted_findings")
    history = {
        "repair_session": session,
        "status": "repairing" if accepted_findings else "clean",
        "remaining_findings": deepcopy(accepted_findings),
        "rounds": [],
        "dispatches": [],
        "pending_dispatch": None,
        "logical_owner": owner,
        "candidate_sha": candidate_sha,
        "session_handoffs": [],
    }
    return history


def record_repair_round(
    history: dict[str, Any],
    *,
    repair_session: str,
    dispatch_id: str,
    repaired_findings: list[str],
    remaining_findings: list[dict[str, Any]],
) -> dict[str, Any]:
    """Consume one authorized repair response without introducing a new actor."""

    session = _text(repair_session, "repair_session")
    if session != history.get("repair_session"):
        raise PackReviewError("all rounds must use the persistent repair session")
    pending = history.get("pending_dispatch")
    if not isinstance(pending, dict):
        raise PackReviewError("repair round requires an authorized pending dispatch")
    dispatch = _text(dispatch_id, "dispatch_id")
    if dispatch != pending.get("dispatch_id"):
        raise PackReviewError("repair round dispatch_id does not match pending dispatch")
    if session != pending.get("repair_session"):
        raise PackReviewError("pending dispatch belongs to another repair session")
    if not isinstance(repaired_findings, list) or not isinstance(
        remaining_findings, list
    ):
        raise PackReviewError("repair round findings must be lists")
    if history.get("status") != "repairing":
        raise PackReviewError("repair convergence is already clean")
    prior_ids = set(
        _finding_ids(history.get("remaining_findings", []), "prior findings")
    )
    pending_ids = pending.get("finding_ids")
    if not isinstance(pending_ids, list):
        raise PackReviewError("pending dispatch finding ids must be a list")
    normalized_pending_ids = {_text(item, "pending finding id") for item in pending_ids}
    if len(normalized_pending_ids) != len(pending_ids) or normalized_pending_ids != prior_ids:
        raise PackReviewError("pending dispatch must cover every prior finding exactly")
    repaired_ids = {_text(item, "repaired finding id") for item in repaired_findings}
    remaining_ids = {
        _text(item.get("id"), "remaining finding id") for item in remaining_findings
    }
    if len(repaired_ids) != len(repaired_findings):
        raise PackReviewError("repaired finding ids must be unique")
    if len(remaining_ids) != len(remaining_findings):
        raise PackReviewError("remaining finding ids must be unique")
    unknown_repaired = sorted(repaired_ids - prior_ids)
    if unknown_repaired:
        raise PackReviewError(
            f"repair round names unknown finding ids: {', '.join(unknown_repaired)}"
        )
    overlap = sorted(repaired_ids & remaining_ids)
    if overlap:
        raise PackReviewError(
            f"finding ids cannot be repaired and remaining: {', '.join(overlap)}"
        )
    dropped = sorted(prior_ids - repaired_ids - remaining_ids)
    if dropped:
        raise PackReviewError(
            "prior finding ids are neither repaired nor remaining: "
            + ", ".join(dropped)
        )
    updated = deepcopy(history)
    updated["rounds"].append(
        {
            "dispatch_id": dispatch,
            "repaired_findings": deepcopy(repaired_findings),
            "remaining_findings": deepcopy(remaining_findings),
        }
    )
    updated["remaining_findings"] = deepcopy(remaining_findings)
    updated["status"] = "clean" if not remaining_findings else "repairing"
    updated["pending_dispatch"] = None
    return updated


def authorize_repair_dispatch(
    history: dict[str, Any],
    *,
    repair_session: str,
    dispatch_id: str,
    finding_ids: list[str] | None = None,
) -> dict[str, Any]:
    """Certify one cumulative repair dispatch for the persistent repair session.

    Repair convergence is a single closing bugfix phase, not a new implementation
    loop. One dispatch therefore reuses the persistent repair session, carries
    every remaining accepted finding at once, and names the re-entries that are
    forbidden: the bead execution loop, a separate RED author, and the member
    sequence. Omit `finding_ids` to dispatch the complete remaining set.
    """

    if not isinstance(history, dict):
        raise PackReviewError("repair history must be an object")
    session = _text(repair_session, "repair_session")
    if session != history.get("repair_session"):
        raise PackReviewError(
            "repair convergence reuses the persistent repair session; "
            "do not dispatch a new implementer"
        )
    if history.get("status") != "repairing":
        raise PackReviewError("repair convergence has no remaining finding to dispatch")
    if history.get("pending_dispatch") is not None:
        raise PackReviewError("a repair dispatch is already pending")
    remaining = history.get("remaining_findings", [])
    remaining_ids = _finding_ids(remaining, "remaining_findings")
    if finding_ids is None:
        requested = list(remaining_ids)
    else:
        if not isinstance(finding_ids, list):
            raise PackReviewError("finding_ids must be a list")
        requested = [_text(item, "finding id") for item in finding_ids]
    if len(requested) != len(set(requested)):
        raise PackReviewError("dispatch finding ids must be unique")
    missing = sorted(set(remaining_ids) - set(requested))
    if missing:
        raise PackReviewError(
            "a repair dispatch must carry every remaining finding at once; missing: "
            + ", ".join(missing)
        )
    unknown = sorted(set(requested) - set(remaining_ids))
    if unknown:
        raise PackReviewError(
            "dispatch names findings that are not remaining: " + ", ".join(unknown)
        )
    dispatch = _text(dispatch_id, "dispatch_id")
    updated = deepcopy(history)
    dispatches = updated.get("dispatches")
    if not isinstance(dispatches, list):
        raise PackReviewError("repair history dispatches must be a list")
    if any(item.get("dispatch_id") == dispatch for item in dispatches):
        raise PackReviewError("dispatch_id is already authorized for this convergence")
    pending = {
        "dispatch_id": dispatch,
        "repair_session": session,
        "finding_ids": deepcopy(requested),
    }
    dispatches.append(deepcopy(pending))
    updated["pending_dispatch"] = deepcopy(pending)
    return {
        "history": updated,
        "dispatch": {
            **pending,
            "mode": REPAIR_DISPATCH_MODE,
            "reentry_forbidden": list(REPAIR_REENTRY_FORBIDDEN),
            "repair_implementer_owns_tests": True,
        },
    }


def terminal_repository_evidence(
    *, canonical_main_sha: str, session_close_id: str
) -> dict[str, str]:
    """Return the complete opaque success result exposed to an outer caller."""

    if not SHA_RE.fullmatch(canonical_main_sha):
        raise PackReviewError("canonical_main_sha must be a full lowercase Git SHA")
    if not SESSION_CLOSE_RE.fullmatch(session_close_id):
        raise PackReviewError("session_close_id is invalid")
    return {
        "status": "complete",
        "canonical_main_sha": canonical_main_sha,
        "session_close_id": session_close_id,
    }

#!/usr/bin/env -S uv run python
"""Triage local review findings into one bounded repair set.

The three local reviewers return findings on one candidate. The main session
merges them into one deduplicated list; this helper partitions that list
deterministically:

- ``repair``: Medium or higher and tied to an acceptance criterion of the work
  order or to the candidate's own behaviour. A finding outside the delivery diff
  still enters repair when it is bound to an admitted criterion (a missing case
  lives in a file the change did not touch) or when it is a High or Critical
  finding on the change's own behaviour (a live caller the change breaks). The
  delivery's designated repair author repairs this set in one round.
- ``repaired``: findings the main session marks as fixed by the repair commit
  (``--repaired <finding-id>``, repeatable). They are reported as repaired
  whatever their severity, scope or the repair rounds used, and never enter
  ``repair`` or ``deferred``. An id that names no finding is a usage error.
- ``deferred``: everything else, with the reason. ``render_review_decisions``
  turns it and the ``repaired`` group into the "Review decisions" section of the
  pull request body, which pr-agent reads so it does not raise the same findings
  again.

The helper does not judge finding quality; it applies the scope and severity
rules so the main session does not reason them out in prose. It reads the shape
the review brief asks for (``id``, ``ac`` with ``own-behaviour`` for the
change's own behaviour) as well as ``finding_id``/``ac_ref``/``candidate_behaviour``.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path, PurePosixPath
from typing import Any, Iterable

CONTRACT = "cognovis.finding-triage.v1"
SEVERITIES = ("nit", "low", "medium", "high", "critical")
REPAIR_SEVERITIES = frozenset({"medium", "high", "critical"})
OUTSIDE_DIFF_BEHAVIOUR_SEVERITIES = frozenset({"high", "critical"})
OWN_BEHAVIOUR = "own-behaviour"
# Reviewers write the own-behaviour scope in several spellings; every one of them must
# reach triage as own behaviour instead of being dropped as NO_ADMITTED_SCOPE.
OWN_BEHAVIOUR_SPELLINGS = frozenset({"behaviour", "behavior", "own-behaviour", "own-behavior"})
MAX_REPAIR_ROUNDS = 1


class FindingTriageError(ValueError):
    """Raised when a finding lacks the fields triage needs."""


def _severity(finding: dict[str, Any]) -> str:
    value = str(finding.get("severity") or "").strip().lower()
    if value not in SEVERITIES:
        raise FindingTriageError(
            f"finding {finding.get('finding_id')!r} has unknown severity {value!r}; "
            f"expected one of {', '.join(SEVERITIES)}"
        )
    return value


def _normalized(path: str) -> str:
    return PurePosixPath(path.strip().replace("\\", "/")).as_posix().lstrip("./")


def _in_diff(paths: list[str], diff_paths: set[str]) -> bool:
    for raw in paths:
        candidate = _normalized(raw)
        if candidate in diff_paths:
            return True
        # A directory-level finding counts when any changed file sits under it.
        if any(changed.startswith(candidate.rstrip("/") + "/") for changed in diff_paths):
            return True
    return False


def triage_findings(
    findings: list[dict[str, Any]],
    *,
    diff_paths: list[str],
    acceptance_refs: list[str],
    repair_rounds_used: int = 0,
    repaired_ids: Iterable[str] = (),
) -> dict[str, Any]:
    """Partition findings into ``repair``, ``repaired`` and ``deferred``."""
    changed = {_normalized(p) for p in diff_paths if p.strip()}
    accepted_refs = {ref.strip() for ref in acceptance_refs if ref.strip()}
    marked_repaired = {str(raw).strip() for raw in repaired_ids}
    if "" in marked_repaired:
        raise FindingTriageError("repaired finding IDs must not be empty")
    repair: list[dict[str, Any]] = []
    repaired: list[dict[str, Any]] = []
    deferred: list[dict[str, Any]] = []
    seen: set[str] = set()

    for finding in findings:
        finding_id = str(finding.get("finding_id") or finding.get("id") or "").strip()
        if not finding_id or finding_id in seen:
            raise FindingTriageError("finding IDs must be present and unique")
        seen.add(finding_id)
        severity = _severity(finding)
        paths = [str(p) for p in (finding.get("paths") or [])]
        ac_ref = str(finding.get("ac_ref") or finding.get("ac") or "").strip()
        candidate_behaviour = bool(finding.get("candidate_behaviour", False))
        if ac_ref.lower().replace("_", "-").replace(" ", "-") in OWN_BEHAVIOUR_SPELLINGS:
            candidate_behaviour = True
            ac_ref = ""
        bound_to_ac = bool(ac_ref) and ac_ref in accepted_refs
        record = {"finding_id": finding_id, "severity": severity}
        for optional in ("summary", "reviewer"):
            value = str(finding.get(optional) or "").strip()
            if value:
                record[optional] = value

        if finding_id in marked_repaired:
            repaired.append(record)
            continue
        if severity not in REPAIR_SEVERITIES:
            deferred.append({**record, "reason": "BELOW_MEDIUM"})
            continue
        if not candidate_behaviour and not bound_to_ac:
            deferred.append({**record, "reason": "NO_ADMITTED_SCOPE"})
            continue
        in_diff = bool(paths) and _in_diff(paths, changed)
        if not in_diff and not bound_to_ac and severity not in OUTSIDE_DIFF_BEHAVIOUR_SEVERITIES:
            deferred.append({**record, "reason": "OUTSIDE_PACK_DIFF"})
            continue
        if repair_rounds_used >= MAX_REPAIR_ROUNDS:
            deferred.append({**record, "reason": "REPAIR_ROUNDS_EXHAUSTED"})
            continue
        repair.append(record)

    unknown = sorted(marked_repaired - seen)
    if unknown:
        raise FindingTriageError(
            f"repaired finding IDs not in the findings file: {', '.join(unknown)}"
        )

    return {
        "contract": CONTRACT,
        "repair": repair,
        "repaired": repaired,
        "deferred": deferred,
        "repair_dispatch_authorized": bool(repair),
        "repair_rounds_used": repair_rounds_used,
        "max_repair_rounds": MAX_REPAIR_ROUNDS,
    }


REASON_TEXT = {
    "BELOW_MEDIUM": "below Medium severity",
    "OUTSIDE_PACK_DIFF": "outside the changed paths",
    "NO_ADMITTED_SCOPE": "not bound to an acceptance criterion or the change's own behaviour",
    "REPAIR_ROUNDS_EXHAUSTED": "the single repair round is used",
}


def _finding_line(item: dict[str, Any], outcome: str) -> str:
    summary = item.get("summary") or "(no summary)"
    source = f", {item['reviewer']}" if item.get("reviewer") else ""
    return f"- `{item['finding_id']}` ({item['severity']}{source}): {summary} -- {outcome}."


def render_review_decisions(
    deferred: list[dict[str, Any]], repaired: Iterable[dict[str, Any]] = ()
) -> str:
    """Markdown "Review decisions" section for the pull request body."""
    lines = ["## Review decisions", ""]
    if not deferred:
        lines.append("No local review finding was deferred.")
    else:
        lines.append(
            "Local review findings not repaired in this pull request, with the reason:"
        )
        lines.append("")
        for item in deferred:
            reason = REASON_TEXT.get(item["reason"], item["reason"])
            lines.append(_finding_line(item, f"deferred, {reason}"))
    repaired = list(repaired)
    if repaired:
        lines.extend(["", "Repaired in the repair round:", ""])
        lines.extend(_finding_line(item, "repaired") for item in repaired)
    return "\n".join(lines) + "\n"


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--findings-file", required=True, type=Path)
    parser.add_argument(
        "--diff-path", action="append", default=[], help="Changed path; repeatable."
    )
    parser.add_argument("--diff-paths-file", type=Path, help="One changed path per line.")
    parser.add_argument(
        "--ac-ref", action="append", default=[], help="Admitted AC reference; repeatable."
    )
    parser.add_argument("--repair-rounds-used", type=int, default=0)
    parser.add_argument(
        "--repaired",
        action="append",
        default=[],
        metavar="FINDING_ID",
        help="Finding fixed by the repair commit; repeatable.",
    )
    parser.add_argument(
        "--review-decisions",
        action="store_true",
        help="Print the Review decisions Markdown section instead of JSON.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    findings = json.loads(args.findings_file.read_text(encoding="utf-8"))
    if isinstance(findings, dict):
        findings = findings.get("findings") or []
    diff_paths = list(args.diff_path)
    if args.diff_paths_file:
        diff_paths.extend(args.diff_paths_file.read_text(encoding="utf-8").splitlines())
    try:
        result = triage_findings(
            findings,
            diff_paths=diff_paths,
            acceptance_refs=args.ac_ref,
            repair_rounds_used=args.repair_rounds_used,
            repaired_ids=args.repaired,
        )
    except FindingTriageError as error:
        json.dump(
            {"contract": CONTRACT, "error": "FINDING_TRIAGE_INVALID", "message": str(error)},
            sys.stdout,
        )
        sys.stdout.write("\n")
        return 2
    if args.review_decisions:
        sys.stdout.write(render_review_decisions(result["deferred"], result["repaired"]))
        return 0
    json.dump(result, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env -S uv run python
"""Triage final-review findings into one bounded repair set.

Late findings from the final Pack perspectives are closing bugfixes on an
existing candidate, not a licence to keep repairing until every reviewer is
silent. This helper partitions accepted findings deterministically:

- ``repair``: Medium or higher, touching a path inside the Pack diff, and tied
  to an admitted acceptance criterion or to the candidate's own behaviour.
- ``deferred``: everything else, with the reason, so the delivery owner records
  it as a pull request comment or a follow-up work order instead of a repair.

Only the ``repair`` set enters ``pack_review_contract.start_repair_convergence``.
The helper does not judge finding quality; it applies the scope and severity
rules so the delivery owner does not reason them out in prose.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path, PurePosixPath
from typing import Any

CONTRACT = "cognovis.finding-triage.v1"
SEVERITIES = ("nit", "low", "medium", "high", "critical")
REPAIR_SEVERITIES = frozenset({"medium", "high", "critical"})
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
) -> dict[str, Any]:
    """Partition findings into ``repair`` and ``deferred`` with typed reasons."""
    changed = {_normalized(p) for p in diff_paths if p.strip()}
    accepted_refs = {ref.strip() for ref in acceptance_refs if ref.strip()}
    repair: list[dict[str, Any]] = []
    deferred: list[dict[str, Any]] = []
    seen: set[str] = set()

    for finding in findings:
        finding_id = str(finding.get("finding_id") or "").strip()
        if not finding_id or finding_id in seen:
            raise FindingTriageError("finding IDs must be present and unique")
        seen.add(finding_id)
        severity = _severity(finding)
        paths = [str(p) for p in (finding.get("paths") or [])]
        ac_ref = str(finding.get("ac_ref") or "").strip()
        candidate_behaviour = bool(finding.get("candidate_behaviour", False))
        record = {"finding_id": finding_id, "severity": severity}

        if severity not in REPAIR_SEVERITIES:
            deferred.append({**record, "reason": "BELOW_MEDIUM"})
            continue
        if not paths or not _in_diff(paths, changed):
            deferred.append({**record, "reason": "OUTSIDE_PACK_DIFF"})
            continue
        if not candidate_behaviour and (not ac_ref or ac_ref not in accepted_refs):
            deferred.append({**record, "reason": "NO_ADMITTED_SCOPE"})
            continue
        if repair_rounds_used >= MAX_REPAIR_ROUNDS:
            deferred.append({**record, "reason": "REPAIR_ROUNDS_EXHAUSTED"})
            continue
        repair.append(record)

    return {
        "contract": CONTRACT,
        "repair": repair,
        "deferred": deferred,
        "repair_dispatch_authorized": bool(repair),
        "repair_rounds_used": repair_rounds_used,
        "max_repair_rounds": MAX_REPAIR_ROUNDS,
    }


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
        )
    except FindingTriageError as error:
        json.dump(
            {"contract": CONTRACT, "error": "FINDING_TRIAGE_INVALID", "message": str(error)},
            sys.stdout,
        )
        sys.stdout.write("\n")
        return 2
    json.dump(result, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())

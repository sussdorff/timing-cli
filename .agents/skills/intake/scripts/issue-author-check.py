#!/usr/bin/env python3
"""Check a hosted issue body against the issue-intake contract before mutation.

Input is exactly one of:

- ``--body-file PATH``: a drafted issue body in Markdown
- ``--issue REF``: an existing issue read through ``ccore tracker show REF``
- Markdown on stdin when neither flag is given

The verdict is printed as JSON ``{"verdict", "findings"}``. Exit code 0 means the
body may be handed to ``ccore tracker create --body-file`` or ``ccore tracker
update``; exit code 2 means a critical finding (or a checker failure) blocks it.

The rules come from the resolved issue-intake contract (see ``issue_contract.py``).
The Review-Risk vocabulary and parser live in the sibling ``review_risk.py``.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import Any, Callable

SCRIPT_DIR = Path(__file__).resolve().parent

READY = "FACTORY_READY"
READY_WITH_WARNINGS = "FACTORY_READY_WITH_WARNINGS"
NOT_READY = "NEEDS_INTERACTIVE_WORK_CRITICAL_OVERLAY"

Runner = Callable[..., subprocess.CompletedProcess[str]]
RemediationResolver = Callable[[str], "dict[str, Any] | None"]


def _load_sibling_module(name: str, filename: str) -> ModuleType:
    """Load a sibling script module without relying on sys.path order."""
    cached = sys.modules.get(name)
    if cached is not None and Path(getattr(cached, "__file__", "")).resolve().parent == SCRIPT_DIR:
        return cached
    spec = importlib.util.spec_from_file_location(name, SCRIPT_DIR / filename)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {filename} from {SCRIPT_DIR}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


_contract = _load_sibling_module("_intake_issue_contract", "issue_contract.py")
_review_risk = _load_sibling_module("_intake_review_risk", "review_risk.py")

# ---------------------------------------------------------------------------
# issue fields read by `ccore tracker create` (ccore/capabilities/tracker.py)
# ---------------------------------------------------------------------------

ISSUE_TYPES = ("feature", "task", "bug")
GOAL_LINE_RE = re.compile(r"^Goal:(?P<value>.*)$", re.MULTILINE)
TYPE_LINE_RE = re.compile(r"^Type:(?P<value>.*)$", re.IGNORECASE | re.MULTILINE)
BLOCKED_BY_LINE_RE = re.compile(r"^Blocked by:(?P<value>.*)$", re.IGNORECASE | re.MULTILINE)
H1_RE = re.compile(r"^#[ \t]+(?P<title>\S.*?)[ \t]*#*[ \t]*$")
ISSUE_URL_RE = re.compile(
    r"^https?://[^/\s]+/(?P<owner>[^/\s]+)/(?P<repo>[^/\s]+)/issues/(?P<number>\d+)/?$"
)
SHORT_ISSUE_REF_RE = re.compile(
    r"^(?P<owner>[A-Za-z0-9_.-]+)/(?P<repo>[A-Za-z0-9_.-]+)#(?P<number>\d+)$"
)
TYPE_LABEL_RE = re.compile(r"^type:(?P<type>\S+)$", re.IGNORECASE)

# Exact copies of the body parsers in ccore/capabilities/tracker.py. `ccore tracker
# create` and `ccore tracker update` derive the title and labels with these, from the
# raw body and without excluding fenced code blocks. The round-trip test compares
# this view with the installed ccore.
CCORE_GOAL_LINE_RE = re.compile(r"^Goal:\s*(.+)$", re.MULTILINE)
CCORE_REVIEW_RISK_LABEL_RE = re.compile(r"review-risk:(\S+)", re.IGNORECASE)
CCORE_TYPE_LABEL_RE = re.compile(r"(?:^|\s)type:(task|bug|feature)\b", re.IGNORECASE)
CCORE_REVIEW_RISK_FIELD_RE = re.compile(r"^Review-Risk:\s*(\S+)", re.IGNORECASE | re.MULTILINE)
CCORE_TYPE_FIELD_RE = re.compile(r"^Type:\s*(task|bug|feature)\b", re.IGNORECASE | re.MULTILINE)
CCORE_BLOCKED_BY_RE = re.compile(r"^Blocked by:\s*(\S+)", re.IGNORECASE | re.MULTILINE)
# Column-0 field lines as ccore sees them, counted over the raw body.
CCORE_FIELD_LINE_RES = {
    "Goal": re.compile(r"^Goal:", re.MULTILINE),
    "Type": re.compile(r"^Type:", re.IGNORECASE | re.MULTILINE),
    "Review-Risk": re.compile(r"^Review-Risk:", re.IGNORECASE | re.MULTILINE),
    "Blocked by": re.compile(r"^Blocked by:", re.IGNORECASE | re.MULTILINE),
}

# ---------------------------------------------------------------------------
# FHIR production-data impact (installed contributor standard)
# ---------------------------------------------------------------------------

FHIR_EMISSION_LABEL = "fhir-emission-change"
FHIR_PDI_FIELDS = (
    "classification",
    "existing-data disposition",
    "identifier stability",
    "convergence",
    "projection refresh",
    "remediation",
)
FHIR_PDI_CLASSIFICATIONS = {
    "additive-stable-id",
    "stop-emission-tombstone",
    "identity-representation-supersession",
}
FHIR_ADDITIVE_NO_OP_CONTRACT = {
    "existing-data disposition": "no-op:self-heals-existing-resources",
    "identifier stability": "stable-id-preserved",
    "convergence": "stable-id-resync:terminal-no-writes",
}
FHIR_DESTRUCTIVE_OPERATION_RE = re.compile(
    r"\b(?:"
    r"reseed(?:s|ed|ing)?|reset(?:s|ting)?|reimport(?:s|ed|ing)?|"
    r"drop(?:ping)?\s+and\s+recreat(?:e|ing)"
    r")\b",
    re.IGNORECASE,
)
FHIR_PROOF_CLAIM_RE = re.compile(
    r"\b(?:clean|converg\w*|remediat\w*|evidence|proof|pass(?:es|ed)?|works?)\b",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# title, acceptance criteria and Means of Compliance
# ---------------------------------------------------------------------------

PHASE_TITLE_RE = re.compile(
    r"^(setup|refactor|migration|initialize|configure|deploy|migrate)\b", re.IGNORECASE
)
ACTIVITY_TITLE_RE = re.compile(r"^(implement|write|create)\b", re.IGNORECASE)
STEP_AC_RE = re.compile(
    r"^(write a function|create a class|add a method|implement)\b", re.IGNORECASE
)
TRIVIAL_AC_RE = re.compile(
    r"^(works correctly|no bugs|tests green|all tests pass|functions as expected)\b",
    re.IGNORECASE,
)
PLACEHOLDER_RE = re.compile(r"\b(TBD|todo|see ticket)\b", re.IGNORECASE)
AC_ITEM_RE = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+(\S.*)$")
# Column zero only: a wrapped list item is always indented, so an indented
# `# ...` continuation line does not truncate the criteria list.
NESTED_HEADING_RE = re.compile(r"^#{1,6}(?:[ \t]|$)")
FENCE_RE = re.compile(r"^ {0,3}(`{3,}|~{3,})[ \t]*(.*)$")
# Criterion column inside an `## Acceptance Criteria` table.
AC_TABLE_COLUMN_RE = re.compile(
    r"^(?:ac|ak|criterion|acceptance criteri(?:on|a))$", re.IGNORECASE
)
TABLE_SEPARATOR_CELL_RE = re.compile(r"^:?-+:?$")
MOC_AC_COLUMN_RE = re.compile(r"^(?:ac|acceptance criteri(?:on|a))$", re.IGNORECASE)
HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
REVIEW_HISTORY_HEADING_RE = re.compile(
    r"^#{1,6}\s+(?:reviewer[- ]fix|review[- ]round|reviewer[- ]repair|correction[- ]log)\b",
    re.IGNORECASE | re.MULTILINE,
)

# ---------------------------------------------------------------------------
# Human Decision Gate (standards/judge-layer/decision-gate.md)
# ---------------------------------------------------------------------------

HUMAN_GATE_REQUIRED_FIELDS = {
    "decision owner",
    "allowed outcomes",
    "trigger timing",
    "minimum evidence plan",
    "operational do-nothing/default outcome",
    "delivery consequence",
    "overrideability",
    "sequencing constraints",
}
JUDGE_OUTCOMES = {"ALLOW", "BLOCK", "REVISE", "ESCALATE"}
MANDATE_GATE_FIELDS = {
    "scope",
    "limits",
    "evidence_refs",
    "granted_at",
    "granted_by",
    "expires_at",
    "supersedes",
}
HUMAN_GATE_ACTOR = r"(?:human|user|manager|owner|stakeholder)"
HUMAN_GATE_DECISION = r"(?:approval|sign-?off|confirmation|decision)"
HUMAN_GATE_PROCESS_ANCHOR = (
    r"(?:this\s+)?(?:issue|change|implementation|work|deployment|release|pull\s+request|pr)"
    r"|deploy(?:ed|ment)?|merge(?:d)?|ship(?:ped)?|close(?:d)?|proceed(?:ing)?|continue"
    r"|rollback\s+plan|blast[-\s]radius|evidence\s+plan"
)
HUMAN_CONFIRMATION_GATE_RE = re.compile(
    rf"\b{HUMAN_GATE_ACTOR}\s+{HUMAN_GATE_DECISION}\s+(?:is\s+)?required\b"
    rf".{{0,120}}\b(?:before|until|to)\b.{{0,80}}\b(?:{HUMAN_GATE_PROCESS_ANCHOR})\b"
    rf"|\b{HUMAN_GATE_ACTOR}\b.{{0,80}}"
    r"\b(?:must|needs?\s+to|required\s+to)\b.{0,80}"
    r"\b(?:approve|sign\s+off|confirm|decide)\b"
    rf".{{0,120}}\b(?:{HUMAN_GATE_PROCESS_ANCHOR})\b"
    r"|\b(?:do\s+not|must\s+not|cannot|can't)\s+(?:proceed|continue|deploy|close)\b"
    r".{0,80}\b(?:until|before)\b.{0,80}"
    rf"\b{HUMAN_GATE_ACTOR}\b",
    re.IGNORECASE | re.DOTALL,
)
HUMAN_EVIDENCE_AUDITOR_RES = [
    re.compile(
        r"\b(?:human|user|manager|owner|stakeholder)\b.{0,80}"
        r"\b(?:verify|audit|review|validate|sign\s+off|sign-?off|confirm)\b.{0,80}"
        r"\b(?:evidence|tests?|implementation|completion|done|correctness|correct)\b",
        re.IGNORECASE | re.DOTALL,
    ),
    re.compile(
        r"\b(?:evidence|tests?|implementation|completion|done|correctness|correct)\b.{0,80}"
        r"\b(?:human|user|manager|owner|stakeholder)\b.{0,80}"
        r"\b(?:verify|audit|review|validate|sign\s+off|sign-?off|confirm)\b",
        re.IGNORECASE | re.DOTALL,
    ),
]


# ===========================================================================
# public API
# ===========================================================================


def evaluate_body(
    markdown: str,
    repo_root: str | Path,
    *,
    labels: list[Any] | None = None,
    remediation_resolver: RemediationResolver | None = None,
) -> dict[str, Any]:
    """Evaluate one issue body against the resolved issue-intake contract."""
    root = _repository_root(Path(repo_root))
    contract = _contract.resolve_contract(repo_root=root)
    if contract["status"] != "ok":
        return _verdict(_contract_findings(contract))

    draft = _normalize(markdown, labels or [])
    resolver = remediation_resolver or (lambda ref: _resolve_remediation(ref, repo_root=root))
    findings: list[dict[str, str]] = []
    for rule in contract["rules"]:
        if not _contract.apply_type_filter(rule, draft["type"]):
            continue
        findings.extend(_evaluate_rule(rule, draft, remediation_resolver=resolver))
    findings.extend(_decision_gate_findings(draft))
    findings.extend(_review_risk_findings(draft, repo_root=root, raw_body=markdown))
    findings.extend(_ccore_view_findings(markdown, draft))
    return _verdict(findings)


def ccore_view(body: str) -> dict[str, Any]:
    """Title, labels and dependency record that ccore derives from this raw body."""
    goal = CCORE_GOAL_LINE_RE.search(body)
    title: str | None = goal.group(1).strip().rstrip(".") if goal else None
    if title is None:
        title = "Issue"
        for line in body.splitlines():
            stripped = line.strip()
            if stripped.startswith("#"):
                title = stripped.lstrip("#").strip()
                break
    risk_field = CCORE_REVIEW_RISK_FIELD_RE.search(body)
    risk_label = CCORE_REVIEW_RISK_LABEL_RE.search(body)
    kind_field = CCORE_TYPE_FIELD_RE.search(body)
    kind_label = CCORE_TYPE_LABEL_RE.search(body)
    risk = (
        risk_field.group(1) if risk_field else risk_label.group(1) if risk_label else "none"
    ).rstrip(".,")
    kind = kind_field.group(1) if kind_field else kind_label.group(1) if kind_label else "task"
    return {
        "title": title,
        "review_risk": risk.lower(),
        "type": kind.lower(),
        "blocked_by": [match.group(1) for match in CCORE_BLOCKED_BY_RE.finditer(body)],
    }


def main(argv: list[str] | None = None, *, runner: Runner | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--body-file", type=Path, help="Drafted issue body in Markdown.")
    source.add_argument("--issue", help="Existing issue reference, read through ccore tracker show.")
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=None,
        help="Target repository (default: the repository that contains the working directory).",
    )
    args = parser.parse_args(argv)
    repo_root = _repository_root(args.repo_root or Path.cwd())
    try:
        labels: list[Any] = []
        if args.issue:
            markdown, labels = _load_issue(args.issue, repo_root=repo_root, runner=runner)
        elif args.body_file:
            markdown = Path(args.body_file).read_text(encoding="utf-8")
        else:
            markdown = sys.stdin.read()
        if not markdown.strip():
            raise ValueError("the issue body is empty")
        result = evaluate_body(markdown, repo_root, labels=labels)
    except Exception as exc:  # noqa: BLE001 - the checker must fail closed
        result = _verdict(
            [
                _finding(
                    severity="critical",
                    code="CHECK-ERROR",
                    message=f"issue-author-check failed: {exc}",
                    suggestion="Fix the failure before creating or updating the issue.",
                )
            ]
        )
    print(json.dumps(result))
    return 2 if result["verdict"] == NOT_READY else 0


# ===========================================================================
# input loading
# ===========================================================================


def _ccore_show(ref: str, *, repo_root: Path, runner: Runner | None) -> dict[str, Any]:
    run = runner or subprocess.run
    argv = ["ccore", "tracker", "show", ref]
    result = run(
        argv,
        capture_output=True,
        text=True,
        cwd=repo_root,
        timeout=30,
        check=False,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        raise RuntimeError(f"ccore tracker show {ref} failed: {detail or 'no output'}")
    payload = json.loads(result.stdout, strict=False)
    if not isinstance(payload, dict) or payload.get("status") not in {"ok", "warning"}:
        summary = payload.get("summary") if isinstance(payload, dict) else None
        raise RuntimeError(f"ccore tracker show {ref} failed: {summary or 'unexpected output'}")
    data = payload.get("data")
    if not isinstance(data, dict):
        raise RuntimeError(f"ccore tracker show {ref} returned no issue")
    return data


def _load_issue(ref: str, *, repo_root: Path, runner: Runner | None) -> tuple[str, list[Any]]:
    data = _ccore_show(ref, repo_root=repo_root, runner=runner)
    return str(data.get("body") or ""), list(data.get("labels") or [])


def _resolve_remediation(ref: str, *, repo_root: Path) -> dict[str, Any] | None:
    try:
        return _ccore_show(ref, repo_root=repo_root, runner=None)
    except (OSError, RuntimeError, ValueError, subprocess.SubprocessError):
        return None


def _label_names(labels: list[Any]) -> list[str]:
    names: list[str] = []
    for label in labels:
        if isinstance(label, str) and label.strip():
            names.append(label.strip())
        elif isinstance(label, dict):
            name = str(label.get("name") or "").strip()
            if name:
                names.append(name)
    return names


def _repository_root(start: Path) -> Path:
    """The Git repository that owns ``start``, or ``start`` itself when none exists."""
    resolved = start.expanduser().resolve()
    for candidate in (resolved, *resolved.parents):
        if (candidate / ".git").exists():
            return candidate
    return resolved


# ===========================================================================
# normalization
# ===========================================================================


def _normalize(markdown: str, labels: list[Any]) -> dict[str, Any]:
    body = _restore_escaped_newlines(markdown)
    goals = [match.group("value").strip() for match in GOAL_LINE_RE.finditer(body)]
    types = [match.group("value").strip() for match in TYPE_LINE_RE.finditer(body)]
    declared_type = _declared_type(types)
    goal = goals[0].rstrip(".").strip() if goals else ""
    h1 = _first_h1(body)
    acceptance = _acceptance_from_body(body)
    return {
        "description": body,
        "labels": _label_names(labels),
        "goals": goals,
        "goal": goal,
        "h1": h1,
        "title": goal or h1 or "",
        "types": types,
        "declared_type": declared_type,
        # ccore labels an issue without a Type field as a task.
        "type": declared_type or "task",
        "blocked_by": [match.group("value").strip() for match in BLOCKED_BY_LINE_RE.finditer(body)],
        "acceptance_criteria": acceptance or "",
        "acceptance_lines": _acceptance_lines(acceptance or ""),
        "has_moc": _has_moc_table(body),
        "has_intent_block": _has_intent_block(body),
    }


def _declared_type(values: list[str]) -> str | None:
    if len(values) != 1:
        return None
    value = values[0].strip().rstrip(".,").lower()
    return value if value in ISSUE_TYPES else None


def _first_h1(body: str) -> str | None:
    for _, line in _unfenced_lines(body):
        match = H1_RE.match(line.rstrip("\r\n"))
        if match is not None:
            return match.group("title").strip()
    return None


def _restore_escaped_newlines(text: str) -> str:
    """Repair a body stored with literal backslash-n sequences and no real newline."""
    if "\n" in text or "\\n" not in text:
        return text
    return text.replace("\\n", "\n")


# ===========================================================================
# rule evaluation
# ===========================================================================


def _evaluate_rule(
    rule: dict[str, Any],
    draft: dict[str, Any],
    *,
    remediation_resolver: RemediationResolver,
) -> list[dict[str, str]]:
    text = str(rule["text"])
    severity = str(rule["severity"]).lower()
    findings = _required_section_findings(rule, draft, severity=severity)
    if str(rule.get("rule_id") or "").startswith("FHIR-PDI-"):
        finding = _evaluate_fhir_production_data_impact(
            rule, draft, severity=severity, remediation_resolver=remediation_resolver
        )
        return findings + ([finding] if finding else [])
    if "Type field required:" in text:
        return findings + _type_findings(draft, severity=severity, text=text)
    if "Goal title required:" in text:
        return findings + _goal_findings(draft, severity=severity, text=text)
    if "Blocked-by issue URL required:" in text:
        return findings + _blocked_by_findings(draft, severity=severity, text=text)
    finding = _evaluate_content_rule(text, severity, draft)
    return findings + ([finding] if finding else [])


def _required_section_findings(
    rule: dict[str, Any], draft: dict[str, Any], *, severity: str
) -> list[dict[str, str]]:
    """Enforce the rule's ``requires-section`` annotations.

    Each annotation is satisfied by one non-empty ``## <Heading>`` section outside
    fenced code, under any of its alternative headings. HTML comments alone do not
    make a section non-empty. Rules without the annotation stay model-reviewed.
    """
    missing: list[str] = []
    empty: list[str] = []
    for alternatives in rule.get("requires_sections") or []:
        sections = [
            section
            for section in (
                _extract_markdown_section(draft["description"], heading)
                for heading in alternatives
            )
            if section is not None
        ]
        named = " or ".join(f"`## {heading}`" for heading in alternatives)
        if not sections:
            missing.append(named)
        elif not any(_section_has_content(section) for section in sections):
            empty.append(named)
    if not missing and not empty:
        return []
    details: list[str] = []
    if missing:
        details.append(f"Missing section: {'; '.join(missing)}.")
    if empty:
        details.append(f"The section is empty: {'; '.join(empty)}.")
    return [
        _finding(
            severity=severity,
            code=str(rule["rule_id"]),
            message=f"{rule['text']} {' '.join(details)}",
            suggestion="Add each required section under one of its headings with concrete content.",
        )
    ]


def _section_has_content(section: str) -> bool:
    return bool(HTML_COMMENT_RE.sub("", section).strip())


def _evaluate_content_rule(
    text: str, severity: str, draft: dict[str, Any]
) -> dict[str, str] | None:
    body = draft["description"]
    if "REVIEW-HISTORY" in text and REVIEW_HISTORY_HEADING_RE.search(body):
        return _finding(
            severity=severity,
            code="REVIEW-HISTORY",
            message=text,
            suggestion=(
                "Replace the complete issue body with one coherent specification; "
                "remove review-history headings and superseded text."
            ),
        )
    if "MoC Table required" in text and not draft["has_moc"]:
        return _finding(
            severity=severity,
            code="MOC-MISSING",
            message=text,
            suggestion="Add a `## Means of Compliance` table with one row per acceptance criterion.",
        )
    if "## Intent block required" in text and not draft["has_intent_block"]:
        return _finding(
            severity=severity,
            code="INTENT-BLOCK-MISSING",
            message=text,
            suggestion="Add `## Intent` with a column-0 `Goal:` line, then `Scope-In:` and `Scope-Out:`.",
        )
    if "Clear Intent required" in text and (not body.strip() or PLACEHOLDER_RE.search(body)):
        return _finding(
            severity=severity,
            code="CLEAR-INTENT",
            message=text,
            suggestion="Replace placeholders with a concrete problem statement or intended outcome.",
        )
    if "Outcome-Focused Acceptance Criteria required" in text and not draft["acceptance_lines"]:
        return _finding(
            severity=severity,
            code="AC-MISSING",
            message=text,
            suggestion="Add at least one observable acceptance criterion.",
        )
    if "TITLE-PHASE:" in text and _title_phase_violation(draft["title"]):
        return _finding(
            severity=severity,
            code="TITLE-PHASE",
            message=text,
            suggestion="Rewrite the Goal to name the delivered outcome, not just the phase.",
        )
    if "TITLE-ACTIVITY:" in text and _title_activity_violation(draft["title"]):
        return _finding(
            severity=severity,
            code="TITLE-ACTIVITY",
            message=text,
            suggestion="Rewrite the Goal in outcome form.",
        )
    if "AC-STEP:" in text:
        ac = _first_matching_line(draft["acceptance_lines"], STEP_AC_RE)
        if ac:
            return _finding(
                severity=severity,
                code="AC-STEP",
                message=f"{text} Trigger: {ac}",
                suggestion="Rewrite the acceptance criterion as observable behavior.",
            )
    if "AC-ZERO:" in text and not draft["acceptance_lines"]:
        return _finding(
            severity=severity,
            code="AC-ZERO",
            message=text,
            suggestion="Add at least one acceptance criterion.",
        )
    if "AC-TRIVIAL:" in text:
        ac = _first_matching_line(draft["acceptance_lines"], TRIVIAL_AC_RE)
        if ac:
            return _finding(
                severity=severity,
                code="AC-TRIVIAL",
                message=f"{text} Trigger: {ac}",
                suggestion="Replace the placeholder criterion with observable behavior.",
            )
    return None


def _type_findings(draft: dict[str, Any], *, severity: str, text: str) -> list[dict[str, str]]:
    types = draft["types"]
    allowed = ", ".join(ISSUE_TYPES)
    if not types:
        return [
            _finding(
                severity=severity,
                code="TYPE-MISSING",
                message=f"{text} No column-0 `Type:` line was found.",
                suggestion=f"Add one line `Type: <{'|'.join(ISSUE_TYPES)}>` at column 0.",
            )
        ]
    if len(types) > 1:
        return [
            _finding(
                severity=severity,
                code="TYPE-REPEATED",
                message=f"{text} Found {len(types)} `Type:` lines: {', '.join(types)}.",
                suggestion="Keep exactly one `Type:` line.",
            )
        ]
    if draft["declared_type"] is None:
        return [
            _finding(
                severity=severity,
                code="TYPE-UNKNOWN",
                message=f"{text} `Type: {types[0]}` is not one of {allowed}.",
                suggestion=f"Use one of {allowed}; split a portfolio into independent issues.",
            )
        ]
    return []


def _goal_findings(draft: dict[str, Any], *, severity: str, text: str) -> list[dict[str, str]]:
    goals = draft["goals"]
    if not goals or not goals[0]:
        return [
            _finding(
                severity=severity,
                code="GOAL-MISSING",
                message=f"{text} No non-empty column-0 `Goal:` line was found.",
                suggestion="Add `Goal: <outcome>` at column 0 inside `## Intent`.",
            )
        ]
    findings: list[dict[str, str]] = []
    if len(goals) > 1:
        findings.append(
            _finding(
                severity=severity,
                code="GOAL-REPEATED",
                message=f"{text} Found {len(goals)} column-0 `Goal:` lines; ccore uses the first.",
                suggestion="Keep exactly one column-0 `Goal:` line.",
            )
        )
    h1 = draft["h1"]
    if h1 is not None and h1.rstrip(".").strip() != draft["goal"]:
        findings.append(
            _finding(
                severity=severity,
                code="TITLE-GOAL-MISMATCH",
                message=(
                    f"{text} The heading `# {h1}` differs from the Goal "
                    f"`{draft['goal']}`, which becomes the issue title."
                ),
                suggestion="Make the H1 repeat the Goal verbatim, or remove the H1.",
            )
        )
    return findings


def _blocked_by_findings(
    draft: dict[str, Any], *, severity: str, text: str
) -> list[dict[str, str]]:
    invalid = [value for value in draft["blocked_by"] if not ISSUE_URL_RE.fullmatch(value)]
    if not invalid:
        return []
    return [
        _finding(
            severity=severity,
            code="BLOCKED-BY-NOT-URL",
            message=f"{text} Not a full issue URL: {', '.join(invalid) or '(empty)'}.",
            suggestion="Write `Blocked by: https://<host>/<owner>/<repo>/issues/<number>`.",
        )
    ]


# ===========================================================================
# FHIR production-data impact
# ===========================================================================


def _evaluate_fhir_production_data_impact(
    rule: dict[str, Any],
    draft: dict[str, Any],
    *,
    severity: str,
    remediation_resolver: RemediationResolver,
) -> dict[str, str] | None:
    if FHIR_EMISSION_LABEL not in draft["labels"]:
        return None
    section = _extract_markdown_section(draft["description"], "Production Data Impact")
    field_entries = _production_data_impact_field_entries(section or "")
    fields = dict(field_entries)
    duplicate_fields = sorted(
        name
        for name in FHIR_PDI_FIELDS
        if sum(entry_name == name for entry_name, _ in field_entries) > 1
    )
    rule_id = str(rule["rule_id"])
    text = str(rule["text"])
    if rule_id == "FHIR-PDI-BLOCK":
        missing = [name for name in FHIR_PDI_FIELDS if not fields.get(name)]
        classification = fields.get("classification", "").lower()
        if missing or duplicate_fields or classification not in FHIR_PDI_CLASSIFICATIONS:
            details: list[str] = []
            if missing:
                details.append(f"Missing fields: {', '.join(missing)}.")
            if duplicate_fields:
                details.append(f"Duplicate fields: {', '.join(duplicate_fields)}.")
            if not missing and classification not in FHIR_PDI_CLASSIFICATIONS:
                details.append(f"Invalid classification: {classification}.")
            return _finding(
                severity=severity,
                code=rule_id,
                message=f"{text} {' '.join(details)}",
                suggestion=(
                    "Add the complete Production Data Impact block and use one "
                    "declared classification."
                ),
            )
    if rule_id == "FHIR-PDI-REMEDIATION" and fields:
        return _remediation_finding(
            fields, rule_id=rule_id, text=text, severity=severity, resolver=remediation_resolver
        )
    if rule_id == "FHIR-PDI-DESTRUCTIVE-PROOF" and section:
        moc = _extract_markdown_section(draft["description"], "Means of Compliance")
        evidence_text = "\n".join(
            (
                _unfenced_text(section),
                _unfenced_text(draft["acceptance_criteria"]),
                _unfenced_text(moc or ""),
            )
        )
        if _uses_destructive_fresh_state_as_proof(evidence_text):
            return _finding(
                severity=severity,
                code=rule_id,
                message=text,
                suggestion=(
                    "Replace fresh-state evidence with a repeatable operation over "
                    "existing production-shaped data."
                ),
            )
    return None


def _remediation_finding(
    fields: dict[str, str],
    *,
    rule_id: str,
    text: str,
    severity: str,
    resolver: RemediationResolver,
) -> dict[str, str] | None:
    classification = fields.get("classification", "").lower()
    remediation = fields.get("remediation", "").strip()
    is_no_op = remediation.lower() == "no-op"
    if classification in FHIR_PDI_CLASSIFICATIONS:
        if is_no_op:
            if classification != "additive-stable-id":
                return _finding(
                    severity=severity,
                    code=rule_id,
                    message=text,
                    suggestion="Replace the remediation value with an executable remediation issue.",
                )
        else:
            error = _remediation_reference_error(remediation, resolver)
            if error:
                return _finding(
                    severity=severity,
                    code=rule_id,
                    message=f"{text} {error}",
                    suggestion=(
                        "Reference an existing executable remediation issue (`owner/repo#N` or "
                        "its full issue URL) with Intent, Acceptance Criteria and Means of Compliance."
                    ),
                )
    if classification == "additive-stable-id" and is_no_op:
        invalid_contract_fields = [
            name
            for name, expected in FHIR_ADDITIVE_NO_OP_CONTRACT.items()
            if fields.get(name, "").strip().lower() != expected
        ]
        if invalid_contract_fields:
            return _finding(
                severity=severity,
                code=rule_id,
                message=(
                    f"{text} Invalid additive no-op field values: "
                    f"{', '.join(invalid_contract_fields)}."
                ),
                suggestion=(
                    "Use the exact additive no-op contract values declared by the "
                    "FHIR Production Data Impact standard, without free-text suffixes."
                ),
            )
    return None


def _parse_issue_ref(ref: str) -> tuple[str, str, int] | None:
    for pattern in (SHORT_ISSUE_REF_RE, ISSUE_URL_RE):
        match = pattern.fullmatch(ref)
        if match is not None:
            return match.group("owner"), match.group("repo"), int(match.group("number"))
    return None


def _remediation_reference_error(ref: str, resolver: RemediationResolver) -> str | None:
    parsed = _parse_issue_ref(ref)
    if parsed is None:
        return (
            f"Remediation `{ref}` is neither `no-op` nor an issue reference "
            "(`owner/repo#N` or a full issue URL)."
        )
    owner, repo, number = parsed
    try:
        issue = resolver(ref)
    except Exception as exc:  # noqa: BLE001 - reported as a finding
        return f"Remediation issue `{ref}` could not be resolved: {exc}."
    if not isinstance(issue, dict):
        return f"Remediation issue `{ref}` does not exist."
    url = str(issue.get("html_url") or issue.get("url") or "").rstrip("/")
    resolved_number = issue.get("number")
    if resolved_number is not None and str(resolved_number) != str(number):
        return f"Remediation issue `{ref}` resolved to a different issue number."
    if url and not url.endswith(f"/{owner}/{repo}/issues/{number}"):
        return f"Remediation issue `{ref}` resolved to a different issue ({url})."
    issue_type = _issue_type(issue)
    if issue_type not in ISSUE_TYPES:
        return f"Remediation issue `{ref}` is not executable (type `{issue_type}`)."
    body = str(issue.get("body") or "")
    missing = [
        heading
        for heading in ("Intent", "Acceptance Criteria", "Means of Compliance")
        if _extract_markdown_section(body, heading) is None
    ]
    if missing:
        return f"Remediation issue `{ref}` is not executable; missing {', '.join(missing)}."
    return None


def _issue_type(issue: dict[str, Any]) -> str:
    for name in _label_names(list(issue.get("labels") or [])):
        match = TYPE_LABEL_RE.match(name)
        if match is not None:
            return match.group("type").lower()
    field = TYPE_LINE_RE.search(str(issue.get("body") or ""))
    if field is not None:
        return field.group("value").strip().rstrip(".,").lower()
    return "task"


def _uses_destructive_fresh_state_as_proof(text: str) -> bool:
    operations = list(FHIR_DESTRUCTIVE_OPERATION_RE.finditer(text))
    claims = list(FHIR_PROOF_CLAIM_RE.finditer(text))
    return any(
        abs(operation.start() - claim.start()) <= 120
        for operation in operations
        if not _is_non_destructive_operation_reference(text, operation)
        for claim in claims
    )


def _is_non_destructive_operation_reference(text: str, operation: re.Match[str]) -> bool:
    before = text[max(0, operation.start() - 50) : operation.start()]
    after = text[operation.end() : operation.end() + 50]
    if re.search(
        r"\b(?:no|without|never|avoid(?:s|ed|ing)?)\b[^.;\n]{0,35}$",
        before,
        re.IGNORECASE,
    ):
        return True
    if re.match(
        r"[^.;\n]{0,20}\b(?:is|are|was|were)?\s*not\s+(?:needed|required|used)",
        after,
        re.IGNORECASE,
    ):
        return True
    context = f"{before[-35:]}{operation.group(0)}{after[:35]}"
    return bool(
        re.search(
            r"(?:projection\s+(?:cursor|checkpoint)[^.;\n]{0,15}reset"
            r"|reset[^.;\n]{0,20}(?:projection\s+)?(?:cursor|checkpoint))",
            context,
            re.IGNORECASE,
        )
    )


def _production_data_impact_field_entries(section: str) -> list[tuple[str, str]]:
    entries: list[tuple[str, str]] = []
    for _, line in _unfenced_lines(section):
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        normalized = key.strip().lower()
        if normalized in FHIR_PDI_FIELDS:
            entries.append((normalized, value.strip()))
    return entries


# ===========================================================================
# acceptance criteria and Means of Compliance parsing
# ===========================================================================


def _has_moc_table(body: str) -> bool:
    section = _extract_markdown_section(body, "Means of Compliance")
    if section is None:
        return False
    return any(_is_moc_header_row(line) for line in section.splitlines())


def _is_moc_header_row(line: str) -> bool:
    stripped = line.strip()
    if not stripped.startswith("|"):
        return False
    cells = [cell.strip().strip("*` ") for cell in stripped.strip("|").split("|")]
    return any(MOC_AC_COLUMN_RE.fullmatch(cell) for cell in cells)


def _has_intent_block(body: str) -> bool:
    section = _extract_markdown_section(body, "Intent")
    return section is not None and GOAL_LINE_RE.search(section) is not None


def _acceptance_from_body(body: str) -> str | None:
    """Acceptance criteria declared in the body, or None when the section is absent."""
    section = _extract_markdown_section(body, "Acceptance Criteria")
    if section is None:
        return None
    lines, fenced = _acceptance_section_lines(section.splitlines())
    items: list[str] = []
    for index, raw in enumerate(lines):
        if index in fenced:
            continue
        match = AC_ITEM_RE.match(raw)
        if match is not None:
            items.append(match.group(1).strip())
            continue
        continuation = raw.strip()
        if continuation and items and raw[:1].isspace():
            items[-1] = f"{items[-1]} {continuation}"
    if not items:
        # A tabulated criteria list, consulted only when there is no list.
        items = _acceptance_table_items(lines, fenced)
    if not items:
        # A single criterion stated as plain prose.
        items = _acceptance_prose_items(lines, fenced)
    return "\n".join(items)


def _acceptance_section_lines(lines: list[str]) -> tuple[list[str], set[int]]:
    """The section's own content, cut at the first nested heading."""
    fenced = _fenced_line_indices(lines)
    for index, raw in enumerate(lines):
        if index not in fenced and NESTED_HEADING_RE.match(raw):
            return lines[:index], {i for i in fenced if i < index}
    return lines, fenced


def _acceptance_prose_items(lines: list[str], skip: set[int]) -> list[str]:
    items: list[str] = []
    paragraph: list[str] = []
    for index, raw in enumerate(lines):
        if index in skip or raw.strip().startswith("|"):
            continue
        text = raw.strip()
        if not text:
            if paragraph:
                items.append(" ".join(paragraph))
                paragraph = []
            continue
        paragraph.append(text)
    if paragraph:
        items.append(" ".join(paragraph))
    return items


def _acceptance_table_items(lines: list[str], skip: set[int]) -> list[str]:
    items: list[str] = []
    block: list[list[str]] = []
    for index, raw in enumerate(lines):
        if index in skip:
            continue
        stripped = raw.strip()
        if stripped.startswith("|"):
            block.append(_table_cells(stripped))
            continue
        items.extend(_table_block_criteria(block))
        block = []
    items.extend(_table_block_criteria(block))
    return items


def _table_block_criteria(block: list[list[str]]) -> list[str]:
    if not block:
        return []
    header: list[str] | None = None
    if len(block) >= 2 and _is_table_separator(block[1]):
        header = block[0]
        rows = block[2:]
    else:
        rows = [row for row in block if not _is_table_separator(row)]
    column = _criterion_column(header)
    criteria = []
    for row in rows:
        text = _criterion_text(row, column)
        if text:
            criteria.append(text)
    return criteria


def _table_cells(row: str) -> list[str]:
    return [cell.strip().strip("*` ") for cell in row.strip("|").split("|")]


def _is_table_separator(cells: list[str]) -> bool:
    return (
        bool(cells)
        and all(TABLE_SEPARATOR_CELL_RE.match(cell) for cell in cells if cell)
        and any(cell for cell in cells)
    )


def _criterion_column(header: list[str] | None) -> int | None:
    if header is None:
        return None
    for index, cell in enumerate(header):
        if AC_TABLE_COLUMN_RE.fullmatch(cell):
            return index
    return None


def _criterion_text(row: list[str], column: int | None) -> str:
    if column is not None and column < len(row):
        return row[column]
    # Without a labelled column the criterion is the substantial cell.
    return max(row, key=len, default="")


def _fenced_line_indices(lines: list[str]) -> set[int]:
    """Indices of lines inside a properly closed fenced code block."""
    fenced: set[int] = set()
    opened_at: int | None = None
    marker = ""
    for index, line in enumerate(lines):
        match = FENCE_RE.match(line)
        if match is None:
            continue
        delimiter = match.group(1)
        if opened_at is None:
            opened_at = index
            marker = delimiter
            continue
        closes = (
            delimiter[0] == marker[0]
            and len(delimiter) >= len(marker)
            and not match.group(2).strip()
        )
        if closes:
            fenced.update(range(opened_at, index + 1))
            opened_at = None
            marker = ""
    return fenced


def _acceptance_lines(text: str) -> list[str]:
    lines: list[str] = []
    for raw in text.splitlines():
        cleaned = raw.strip().lstrip("-").strip()
        if cleaned:
            lines.append(cleaned)
    return lines


def _title_phase_violation(title: str) -> bool:
    return bool(PHASE_TITLE_RE.search(title)) and " so " not in title.lower()


def _title_activity_violation(title: str) -> bool:
    return bool(ACTIVITY_TITLE_RE.search(title)) and " can " not in title.lower()


def _first_matching_line(lines: list[str], pattern: re.Pattern[str]) -> str | None:
    for line in lines:
        if pattern.search(line):
            return line
    return None


# ===========================================================================
# Human Decision Gate
# ===========================================================================


def _decision_gate_findings(draft: dict[str, Any]) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    body = draft["description"]
    gate_section = _extract_markdown_section(body, "Human Decision Gate")

    if gate_section is not None:
        errors = _validate_human_decision_gate(gate_section)
        if errors:
            findings.append(
                _finding(
                    severity="critical",
                    code="HUMAN-GATE-MALFORMED",
                    message="`## Human Decision Gate` is malformed: " + "; ".join(errors),
                    suggestion=(
                        "Use standards/judge-layer/decision-gate.md and include every required "
                        "field with judge outcomes ALLOW, BLOCK, REVISE, or ESCALATE."
                    ),
                )
            )
    elif HUMAN_CONFIRMATION_GATE_RE.search(body):
        findings.append(
            _finding(
                severity="critical",
                code="HUMAN-GATE-UNDECLARED",
                message=(
                    "Human confirmation gate wording appears without a "
                    "`## Human Decision Gate` section."
                ),
                suggestion=(
                    "Move the human decision contract into `## Human Decision Gate` "
                    "or remove the gate wording."
                ),
            )
        )

    ac_gate = _first_matching_line(draft["acceptance_lines"], HUMAN_CONFIRMATION_GATE_RE)
    if ac_gate:
        findings.append(
            _finding(
                severity="critical",
                code="HUMAN-GATE-IN-AC",
                message=(
                    "Human decision gates must stay outside ordinary acceptance criteria. "
                    f"Trigger: {ac_gate}"
                ),
                suggestion=(
                    "Move the decision owner, timing, outcomes, and evidence plan into "
                    "`## Human Decision Gate`."
                ),
            )
        )

    auditor_match = _first_human_evidence_auditor_match(body)
    if auditor_match:
        findings.append(
            _finding(
                severity="critical",
                code="HUMAN-AS-EVIDENCE-AUDITOR",
                message=(
                    "Issue wording casts a human as the code or evidence auditor. "
                    f"Trigger: {auditor_match}"
                ),
                suggestion=(
                    "Replace human-as-auditor wording with executable evidence, review artifacts, "
                    "or a `## Human Decision Gate` for manager-decidable risk."
                ),
            )
        )
    return findings


def _parse_field_labels(section: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for line in section.splitlines():
        match = re.match(
            r"^\s*(?:[-*]\s*)?(?:\*\*)?([^:\n`*][^:\n]*?)(?:\*\*)?:\s*(.*?)\s*$", line
        )
        if match is None:
            continue
        fields[match.group(1).strip().lower()] = match.group(2).strip()
    return fields


def _validate_human_decision_gate(section: str) -> list[str]:
    fields = _parse_field_labels(section)
    errors: list[str] = []
    missing = sorted(
        field for field in HUMAN_GATE_REQUIRED_FIELDS if not fields.get(field, "").strip()
    )
    if missing:
        errors.append("missing required field(s): " + ", ".join(missing))

    allowed_outcomes = fields.get("allowed outcomes", "")
    tokens = [
        token.strip().strip(".`").upper()
        for token in re.split(r"[,/]", allowed_outcomes)
        if token.strip()
    ]
    invalid = [token for token in tokens if token not in JUDGE_OUTCOMES]
    if not tokens or invalid:
        errors.append("allowed outcomes must use ALLOW, BLOCK, REVISE, or ESCALATE")

    mandate_fields = sorted(MANDATE_GATE_FIELDS & set(fields))
    if mandate_fields:
        errors.append("gate must not redefine Mandate field(s): " + ", ".join(mandate_fields))
    return errors


def _first_human_evidence_auditor_match(text: str) -> str | None:
    for pattern in HUMAN_EVIDENCE_AUDITOR_RES:
        match = pattern.search(text)
        if match is not None:
            return " ".join(match.group(0).split())
    return None


# ===========================================================================
# Review-Risk (vocabulary owned by review_risk.py)
# ===========================================================================


def _review_risk_findings(
    draft: dict[str, Any], *, repo_root: Path, raw_body: str
) -> list[dict[str, str]]:
    try:
        declared = _review_risk.review_risk_from_body(draft["description"])
    except _review_risk.ReviewRiskError as error:
        return [
            _finding(
                severity="critical",
                code=error.code.replace("_", "-"),
                message=error.message,
                suggestion=f"Record exactly one `Review-Risk:` line. {error.remedy}",
            )
        ]
    return _ccore_review_risk_findings(raw_body, declared)


def _ccore_review_risk_findings(raw_body: str, declared: str) -> list[dict[str, str]]:
    """The review-risk label ccore derives must be exactly the declared risk."""
    lines = CCORE_FIELD_LINE_RES["Review-Risk"].findall(raw_body)
    labelled = ccore_view(raw_body)["review_risk"]
    suggestion = f"Write exactly one line `Review-Risk: {declared}` at column 0, not in a list."
    if not lines:
        return [
            _finding(
                severity="critical",
                code="REVIEW-RISK-NOT-COLUMN-0",
                message=(
                    f"The body declares Review-Risk `{declared}`, but not on a column-0 "
                    f"`Review-Risk:` line; ccore would label the issue `review-risk:{labelled}`."
                ),
                suggestion=suggestion,
            )
        ]
    if len(lines) > 1:
        return [
            _finding(
                severity="critical",
                code="REVIEW-RISK-CCORE-REPEATED",
                message=(
                    f"ccore sees {len(lines)} column-0 `Review-Risk:` lines, including any in "
                    f"fenced code blocks, and labels the issue `review-risk:{labelled}` from the "
                    "first one."
                ),
                suggestion=suggestion + " Indent Review-Risk lines inside fenced examples.",
            )
        ]
    if labelled != declared:
        return [
            _finding(
                severity="critical",
                code="REVIEW-RISK-CCORE-MISMATCH",
                message=(
                    f"The declared Review-Risk is `{declared}`, but ccore would label the issue "
                    f"`review-risk:{labelled}`."
                ),
                suggestion=suggestion,
            )
        ]
    return []


def _ccore_view_findings(raw_body: str, draft: dict[str, Any]) -> list[dict[str, str]]:
    """Flag bodies whose ccore-derived title or type differs from what was checked."""
    findings: list[dict[str, str]] = []
    fenced = _fenced_field_lines(raw_body)
    if fenced:
        findings.append(
            _finding(
                severity="critical",
                code="CCORE-FIELD-IN-FENCE",
                message=(
                    "A fenced code block contains column-0 field lines that ccore parses as "
                    f"part of the issue: {', '.join(fenced)}."
                ),
                suggestion=(
                    "Indent field lines inside fenced examples so that only the real "
                    "`Goal:`, `Type:`, `Review-Risk:` and `Blocked by:` lines start at column 0."
                ),
            )
        )
    view = ccore_view(raw_body)
    if draft["goal"] and view["title"] != draft["goal"]:
        findings.append(
            _finding(
                severity="critical",
                code="GOAL-CCORE-MISMATCH",
                message=(
                    f"The checked Goal is `{draft['goal']}`, but ccore would title the issue "
                    f"`{view['title']}`."
                ),
                suggestion="Write the Goal on one column-0 `Goal: <outcome>` line.",
            )
        )
    if view["type"] != draft["type"]:
        findings.append(
            _finding(
                severity="critical",
                code="TYPE-CCORE-MISMATCH",
                message=(
                    f"The checked type is `{draft['type']}`, but ccore would label the issue "
                    f"`type:{view['type']}`."
                ),
                suggestion="Write exactly one column-0 `Type: <feature|task|bug>` line.",
            )
        )
    return findings


def _fenced_field_lines(raw_body: str) -> list[str]:
    unfenced = {offset for offset, _ in _unfenced_lines(raw_body)}
    hits: list[str] = []
    offset = 0
    for line in raw_body.splitlines(keepends=True):
        if offset not in unfenced:
            for name, pattern in CCORE_FIELD_LINE_RES.items():
                if pattern.match(line):
                    hits.append(f"`{line.rstrip()}`")
                    break
        offset += len(line)
    return hits


# ===========================================================================
# markdown helpers
# ===========================================================================


def _extract_markdown_section(markdown: str, heading: str) -> str | None:
    # Headings vary in case and may carry a trailing qualifier that starts with
    # punctuation; `## Acceptance Criteria Rationale` is a different section.
    heading_pattern = re.compile(
        rf"^##[ \t]+{re.escape(heading)}[ \t]*(?:[^\w\s].*)?$",
        re.IGNORECASE,
    )
    section_start: int | None = None
    for offset, line in _heading_candidate_lines(markdown):
        line_without_ending = line.rstrip("\r\n")
        if section_start is None:
            if heading_pattern.fullmatch(line_without_ending):
                section_start = offset + len(line_without_ending)
            continue
        if re.match(r"^##\s+", line_without_ending):
            return markdown[section_start:offset]
    if section_start is None:
        return None
    return markdown[section_start:]


def _unfenced_lines(markdown: str) -> list[tuple[int, str]]:
    """Source-offset lines outside Markdown fenced code blocks."""
    lines: list[tuple[int, str]] = []
    offset = 0
    fence_character: str | None = None
    fence_length = 0
    for line in markdown.splitlines(keepends=True):
        fence_match = re.match(r"^[ \t]{0,3}(`{3,}|~{3,})", line)
        if fence_match is not None:
            marker = fence_match.group(1)
            if fence_character is None:
                info_string = line[fence_match.end() :].rstrip("\r\n")
                valid_opener = marker[0] == "~" or "`" not in info_string
                if valid_opener:
                    fence_character = marker[0]
                    fence_length = len(marker)
                else:
                    lines.append((offset, line))
            elif (
                marker[0] == fence_character
                and len(marker) >= fence_length
                and re.fullmatch(
                    rf"[ \t]{{0,3}}{re.escape(fence_character)}{{{fence_length},}}[ \t]*",
                    line.rstrip("\r\n"),
                )
                is not None
            ):
                fence_character = None
                fence_length = 0
            offset += len(line)
            continue
        if fence_character is None:
            lines.append((offset, line))
        offset += len(line)
    return lines


def _heading_candidate_lines(markdown: str) -> list[tuple[int, str]]:
    """Unfenced lines that do not start inside an HTML comment.

    A heading inside `<!-- ... -->` is not rendered, so it neither opens nor
    closes a section. A comment may span lines; an unterminated one runs to the
    end of the body.
    """
    lines: list[tuple[int, str]] = []
    in_comment = False
    for offset, line in _unfenced_lines(markdown):
        if not in_comment:
            lines.append((offset, line))
        position = 0
        while True:
            if in_comment:
                end = line.find("-->", position)
                if end < 0:
                    break
                in_comment = False
                position = end + 3
            else:
                start = line.find("<!--", position)
                if start < 0:
                    break
                in_comment = True
                position = start + 4
    return lines


def _unfenced_text(markdown: str) -> str:
    return "".join(line for _, line in _unfenced_lines(markdown))


# ===========================================================================
# results
# ===========================================================================


def _contract_findings(contract: dict[str, Any]) -> list[dict[str, str]]:
    diagnostics = contract.get("diagnostics") or [
        {"code": "CONTRACT-ERROR", "message": f"contract status {contract.get('status')}"}
    ]
    return [
        _finding(
            severity="critical",
            code=str(item.get("code") or "CONTRACT-ERROR"),
            message=f"Issue-intake contract resolution failed: {item.get('message', '')}",
            suggestion="Repair the issue-intake contract installation before authoring issues.",
        )
        for item in diagnostics
    ]


def _verdict(findings: list[dict[str, str]]) -> dict[str, Any]:
    critical = any(finding["severity"] == "critical" for finding in findings)
    if critical:
        verdict = NOT_READY
    elif findings:
        verdict = READY_WITH_WARNINGS
    else:
        verdict = READY
    return {"verdict": verdict, "findings": findings}


def _finding(*, severity: str, code: str, message: str, suggestion: str) -> dict[str, str]:
    return {
        "severity": severity.lower(),
        "code": code,
        "message": message,
        "suggestion": suggestion,
    }


if __name__ == "__main__":
    raise SystemExit(main())

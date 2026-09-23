#!/usr/bin/env -S uv run python
"""Resolve the landing policy of one repository delivery.

This module is the only place the landing-policy decision exists. Every caller --
the `executive-pack` skill, the `session-close` skill, and the shared runtime
instructions -- references it instead of restating the defaults, the elevation
order, or the fail-closed refusals in prose. Two prose copies of a decision are
two contracts, and they drift.

The three user-facing policies map onto released `ccore` commands:

| Policy      | Publication                                | Terminal completion                          |
|-------------|--------------------------------------------|----------------------------------------------|
| `direct`    | `ccore session-close run --delivery merge`  | the same run; status `completed`             |
| `pr-auto`   | `run --delivery pr --merge-authority agent_bot` | same run; status `completed`             |
| `pr-review` | `run --delivery pr --merge-authority human` | human merge, then `complete-pr` without merge|

Defaults:

- a solo delivery of a `bug` bead classified `none` lands `direct`;
- every other solo delivery lands `pr-auto`;
- an Executive Pack lands `pr-review`.

Elevation sources -- repository policy, branch protection, the durable review-risk
classification, and an explicit caller override -- may only move the policy along
`direct -> pr-auto -> pr-review`. A resolved policy is never lowered: a lower
repository policy or branch-protection input is recorded as an ignored input, and
an explicit lower override is refused outright rather than dropped in silence.

Payment, PII, authentication/access-control, and compliance risk always resolve to
`pr-review`. A missing, unknown, or conflicting classification is a typed refusal
that stops the delivery before dispatch.

The classification itself is resolved by `resolve_review_risk` from three
sources, in this order: an issue label `review-risk:<value>` (case-insensitive
prefix), a bead-body `Review-Risk:` line, then an explicit `--review-risk` flag.
A label wins over the body. A flag that contradicts the body is refused rather
than preferred. `personal-data` is an alias of `pii`.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

CONTRACT = "cognovis.landing-policy.v1"

POLICIES = ("direct", "pr-auto", "pr-review")
_RANK = {policy: index for index, policy in enumerate(POLICIES)}

DELIVERY_MODES = ("solo", "executive-pack")

# Closed, like every other input. An unrecognized type would otherwise fall
# through to the `pr-auto` branch and look like a decision rather than a typo.
BEAD_TYPES = ("feature", "epic", "task", "bug", "chore")

REVIEW_RISKS = ("none", "payment", "pii", "auth", "compliance")
ELEVATING_REVIEW_RISKS = frozenset({"payment", "pii", "auth", "compliance"})
_REVIEW_RISK_ALIASES = {"personal-data": "pii"}
_REVIEW_RISK_LABEL_PREFIX = "review-risk:"

REVIEW_RISK_FIELD = "Review-Risk"
_REVIEW_RISK_LINE_RE = re.compile(
    rf"^\s*(?:[-*+]\s*)?(?:\*\*)?{REVIEW_RISK_FIELD}(?:\*\*)?\s*:\*{{0,2}}\s*(.*?)\s*$",
    re.IGNORECASE,
)
_FENCE_RE = re.compile(r"^ {0,3}(`{3,}|~{3,})")

# `--session-id` is a required argument of the released `complete-pr`, so the
# terminal command carries the session identity or an explicit placeholder the
# caller must substitute. A plan without it is not executable.
SESSION_ID_PLACEHOLDER = "<session-id>"

_COMMANDS: dict[str, dict[str, Any]] = {
    "direct": {
        "publish": ["ccore", "session-close", "run", "--delivery", "merge"],
        "publication_status": "completed",
        "terminal": None,
        "terminal_status": "completed",
        "merge_authority": "session_close_merge",
    },
    "pr-auto": {
        "publish": ["ccore", "session-close", "run", "--delivery", "pr",
                    "--merge-authority", "agent_bot"],
        "publication_status": "completed",
        "terminal": None,
        "terminal_status": "completed",
        "merge_authority": "agent_bot",
    },
    "pr-review": {
        "publish": ["ccore", "session-close", "run", "--delivery", "pr",
                    "--merge-authority", "human"],
        "publication_status": "review_pending",
        "terminal": [
            "ccore",
            "session-close",
            "complete-pr",
            "--session-id",
            SESSION_ID_PLACEHOLDER,
        ],
        "terminal_status": "completed",
        "merge_authority": "human",
    },
}


# Session Close statuses. Landing is terminal only when `ccore` says the
# candidate is in the target branch; an open pull request is a handoff.
TERMINAL_LANDING_STATUSES = ("completed", "completed_with_warnings")
NON_TERMINAL_LANDING_STATUSES = (
    "review_pending",
    "blocked",
    "retryable",
    "in_progress",
)


class LandingPolicyError(RuntimeError):
    """A landing policy could not be resolved from the supplied inputs."""

    def __init__(
        self, code: str, message: str, remedy: str, **details: Any
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.remedy = remedy
        self.details = details

    def as_result(self) -> dict[str, Any]:
        return {
            "contract": CONTRACT,
            "status": "error",
            "code": self.code,
            "message": self.message,
            "remedy": self.remedy,
            "details": self.details,
        }


def commands(policy: str, session_id: str | None = None) -> dict[str, Any]:
    """The released `ccore` command plan for one resolved policy.

    Pass the Session Close ID once publication has produced one; without it the
    terminal command keeps `SESSION_ID_PLACEHOLDER` and reports it under
    `placeholders`, so a caller cannot mistake the plan for something runnable.
    """
    try:
        plan = _COMMANDS[policy]
    except KeyError:
        raise LandingPolicyError(
            "LANDING_POLICY_UNKNOWN",
            f"Unknown landing policy {policy!r}.",
            f"Use one of {', '.join(POLICIES)}.",
            policy=policy,
        ) from None
    resolved = json.loads(json.dumps(plan))
    identity = str(session_id or "").strip()
    terminal = resolved["terminal"]
    if terminal and identity:
        resolved["terminal"] = [
            identity if token == SESSION_ID_PLACEHOLDER else token
            for token in terminal
        ]
    resolved["placeholders"] = [
        token
        for token in (resolved["terminal"] or [])
        if token.startswith("<") and token.endswith(">")
    ]
    return resolved


def is_terminal_landing(status: str) -> bool:
    """Whether one Session Close status means the candidate actually landed.

    Callers gate everything that must only happen after a landing -- reporting
    terminal success, and this marketplace's post-Session-Close Library sync --
    on this answer rather than on "Session Close returned".
    """
    text = str(status or "").strip().lower()
    if text in TERMINAL_LANDING_STATUSES:
        return True
    if text in NON_TERMINAL_LANDING_STATUSES:
        return False
    raise LandingPolicyError(
        "SESSION_CLOSE_STATUS_UNKNOWN",
        f"Unknown Session Close status {text!r}.",
        (
            "Read the status from `ccore session-close status --session-id <id>`. "
            "Treat anything unrecognized as not landed."
        ),
        status=text,
    )


def review_risk_from_body(description: str) -> str:
    """The single durable review-risk classification declared by a bead body.

    Issue labels are a separate source, resolved by `resolve_review_risk`. This
    helper still reads the body line that `bd create --body-file` and
    `bd update --body-file` always carry, so the authoring check and the
    admission path share the same parser for that field.
    """
    declared = _review_risk_declarations(description or "")
    if not declared:
        raise LandingPolicyError(
            "REVIEW_RISK_MISSING",
            "The bead body declares no review-risk classification.",
            _risk_remedy(),
        )
    if len(declared) > 1:
        raise LandingPolicyError(
            "REVIEW_RISK_CONFLICTING",
            "The bead body declares more than one review-risk classification.",
            f"Keep exactly one `{REVIEW_RISK_FIELD}:` line in the bead body.",
            declared=declared,
        )
    return _validated_review_risk(declared[0])


def resolve_review_risk(
    *,
    labels: list[Any] | None = None,
    description: str | None = None,
    review_risk: str | None = None,
) -> str:
    """The one classification, reconciled across every source that states it.

    Precedence is label > body > flag. A `review-risk:<value>` issue label wins
    over a bead-body `Review-Risk:` line, including a body that says `none`.
    Unrelated labels fall through to the body. A flag that contradicts the
    body is refused, not preferred: letting the flag win would lower an already
    recorded policy through the back door, which is the same move the
    monotonic elevation rule forbids everywhere else.
    """
    labelled = _review_risk_from_labels(labels)
    if labelled is not None:
        return labelled

    recorded = review_risk_from_body(description) if description is not None else None
    declared = _validated_review_risk(review_risk) if review_risk not in (None, "") else None
    if recorded is not None and declared is not None and recorded != declared:
        raise LandingPolicyError(
            "REVIEW_RISK_CONFLICTING",
            (
                f"The supplied review risk {declared!r} contradicts the "
                f"classification {recorded!r} recorded in the bead body."
            ),
            (
                "Drop the flag, or correct the bead body first. The durable "
                "classification is the one that counts."
            ),
            declared=declared,
            recorded=recorded,
        )
    resolved = recorded if recorded is not None else declared
    if resolved is None:
        raise LandingPolicyError(
            "REVIEW_RISK_MISSING",
            "No review-risk classification was supplied.",
            _risk_remedy(),
        )
    return resolved


def resolve(
    *,
    delivery_mode: str,
    bead_type: str,
    review_risk: str | None,
    repository_policy: str | None = None,
    branch_protection: bool = False,
    override: str | None = None,
    session_id: str | None = None,
) -> dict[str, Any]:
    """Resolve one landing policy, failing closed on unusable input."""
    mode = _validated_choice(
        delivery_mode,
        DELIVERY_MODES,
        missing_code="DELIVERY_MODE_MISSING",
        unknown_code="DELIVERY_MODE_UNKNOWN",
        label="delivery mode",
    )
    kind = str(bead_type or "").strip().lower()
    if not kind:
        raise LandingPolicyError(
            "BEAD_TYPE_MISSING",
            "No bead type was supplied.",
            "Pass the bead's `issue_type` from `bd show <id> --json`.",
        )
    if kind not in BEAD_TYPES:
        raise LandingPolicyError(
            "BEAD_TYPE_UNKNOWN",
            f"Unknown bead type {kind!r}.",
            f"Pass one of {', '.join(BEAD_TYPES)} from `bd show <id> --json`.",
            bead_type=kind,
        )
    risk = _validated_review_risk(review_risk)
    repository = (
        _validated_choice(
            repository_policy,
            POLICIES,
            missing_code="REPOSITORY_POLICY_MISSING",
            unknown_code="REPOSITORY_POLICY_UNKNOWN",
            label="repository policy",
        )
        if repository_policy not in (None, "")
        else None
    )
    caller_override = (
        _validated_choice(
            override,
            POLICIES,
            missing_code="OVERRIDE_MISSING",
            unknown_code="OVERRIDE_UNKNOWN",
            label="override",
        )
        if override not in (None, "")
        else None
    )

    baseline = default_policy(mode, kind)
    policy = baseline
    elevations: list[dict[str, str]] = []
    ignored: list[dict[str, Any]] = []

    # `candidate` is the floor an input imposes; `reported` is the input itself,
    # so an ignored record names what the caller passed rather than the floor it
    # would have set.
    for source, candidate, reported in (
        ("repository_policy", repository, repository),
        ("branch_protection", "pr-auto" if branch_protection else None, True),
        (
            "review_risk",
            "pr-review" if risk in ELEVATING_REVIEW_RISKS else None,
            risk,
        ),
    ):
        if candidate is None:
            continue
        if _RANK[candidate] > _RANK[policy]:
            elevations.append(
                {
                    "source": source,
                    "from": policy,
                    "to": candidate,
                    "reason": _ELEVATION_REASONS[source],
                }
            )
            policy = candidate
        else:
            # These three sources state a floor, not a demand. A floor at or
            # below the resolved policy got everything it asked for, so calling
            # it a refused downgrade would read as if it had been overruled.
            # The only input that can genuinely be refused is an explicit
            # caller override, which raises below rather than landing here.
            ignored.append(
                {
                    "source": source,
                    "value": reported,
                    "disposition": "already_satisfied",
                    "reason": "the resolved policy already meets this floor",
                }
            )

    if caller_override is not None:
        if _RANK[caller_override] < _RANK[policy]:
            raise LandingPolicyError(
                "LANDING_POLICY_DOWNGRADE_REFUSED",
                (
                    f"The caller override {caller_override!r} is lower than the "
                    f"resolved policy {policy!r}."
                ),
                (
                    "Remove the override, or raise it to at least "
                    f"{policy!r}. An override may only elevate."
                ),
                resolved_policy=policy,
                override=caller_override,
                elevations=elevations,
            )
        if _RANK[caller_override] > _RANK[policy]:
            elevations.append(
                {
                    "source": "override",
                    "from": policy,
                    "to": caller_override,
                    "reason": _ELEVATION_REASONS["override"],
                }
            )
            policy = caller_override

    return {
        "contract": CONTRACT,
        "status": "ok",
        "policy": policy,
        "baseline": baseline,
        "inputs": {
            "delivery_mode": mode,
            "bead_type": kind,
            "review_risk": risk,
            "repository_policy": repository,
            "branch_protection": bool(branch_protection),
            "override": caller_override,
            "session_id": str(session_id).strip() if session_id else None,
        },
        "elevations": elevations,
        "ignored_inputs": ignored,
        "commands": commands(policy, session_id=session_id),
    }


def default_policy(delivery_mode: str, bead_type: str) -> str:
    """The policy before any elevation source is applied.

    Risk is deliberately not an input here. "A low-risk solo bug lands direct" is
    the same statement as "a solo bug lands direct unless something elevates it",
    and expressing it that way keeps the recorded elevation chain honest about
    which source raised the policy.
    """
    if delivery_mode == "executive-pack":
        return "pr-review"
    if bead_type == "bug":
        return "direct"
    return "pr-auto"


_ELEVATION_REASONS = {
    "repository_policy": "the repository declares a higher landing policy",
    "branch_protection": "the target branch is protected, so the head cannot be pushed directly",
    "review_risk": "payment, PII, auth, or compliance work always lands through human review",
    "override": "the caller explicitly requested a higher landing policy",
}


def _risk_remedy() -> str:
    return (
        f"Add exactly one `{REVIEW_RISK_FIELD}: <value>` line to the bead body, "
        f"where <value> is one of {', '.join(REVIEW_RISKS)}."
    )


def _validated_review_risk(value: str | None) -> str:
    text = str(value or "").strip().lower()
    if not text:
        raise LandingPolicyError(
            "REVIEW_RISK_MISSING",
            "No review-risk classification was supplied.",
            _risk_remedy(),
        )
    text = _REVIEW_RISK_ALIASES.get(text, text)
    if text not in REVIEW_RISKS:
        raise LandingPolicyError(
            "REVIEW_RISK_UNKNOWN",
            f"Unknown review-risk classification {text!r}.",
            _risk_remedy(),
            review_risk=text,
        )
    return text


def _label_names(labels: list[Any]) -> list[str]:
    names: list[str] = []
    for item in labels:
        if isinstance(item, str):
            names.append(item)
        elif isinstance(item, dict) and item.get("name") is not None:
            names.append(str(item["name"]))
    return names


def _review_risk_from_labels(labels: list[Any] | None) -> str | None:
    if labels is None:
        return None
    declared: list[str] = []
    for name in _label_names(labels):
        stripped = name.strip()
        if not stripped.lower().startswith(_REVIEW_RISK_LABEL_PREFIX):
            continue
        declared.append(stripped[len(_REVIEW_RISK_LABEL_PREFIX) :].strip())
    if not declared:
        return None
    validated = [_validated_review_risk(value) for value in declared]
    unique = list(dict.fromkeys(validated))
    if len(unique) > 1:
        raise LandingPolicyError(
            "REVIEW_RISK_CONFLICTING",
            "The issue labels declare more than one review-risk classification.",
            f"Keep exactly one `{_REVIEW_RISK_LABEL_PREFIX}<value>` label.",
            declared=unique,
        )
    return unique[0]


def _validated_choice(
    value: str | None,
    allowed: tuple[str, ...],
    *,
    missing_code: str,
    unknown_code: str,
    label: str,
) -> str:
    text = str(value or "").strip().lower()
    if not text:
        raise LandingPolicyError(
            missing_code,
            f"No {label} was supplied.",
            f"Pass one of {', '.join(allowed)}.",
        )
    if text not in allowed:
        raise LandingPolicyError(
            unknown_code,
            f"Unknown {label} {text!r}.",
            f"Pass one of {', '.join(allowed)}.",
            **{label.replace(" ", "_"): text},
        )
    return text


def _review_risk_declarations(description: str) -> list[str]:
    declared: list[str] = []
    fenced = False
    marker = ""
    for line in description.splitlines():
        fence = _FENCE_RE.match(line)
        if fence is not None:
            delimiter = fence.group(1)
            if not fenced:
                fenced, marker = True, delimiter
            elif delimiter[0] == marker[0] and len(delimiter) >= len(marker):
                fenced, marker = False, ""
            continue
        if fenced:
            continue
        match = _REVIEW_RISK_LINE_RE.match(line)
        if match is not None:
            declared.append(match.group(1).strip().strip("`*").strip())
    return declared


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="landing_policy.py",
        description="Resolve the landing policy of one repository delivery.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    resolve_parser = sub.add_parser("resolve", help="Resolve one landing policy.")
    resolve_parser.add_argument("--delivery-mode", required=True, choices=DELIVERY_MODES)
    resolve_parser.add_argument("--bead-type", required=True)
    resolve_parser.add_argument(
        "--review-risk",
        help=(
            "The classification, when no bead body is at hand. Supplying one that "
            "contradicts --bead-body-file is refused, never preferred."
        ),
    )
    resolve_parser.add_argument(
        "--bead-body-file",
        type=Path,
        required=False,
        help=(
            "Required. The bead body holding the durable classification; the "
            "resolver reads it rather than trusting a flag."
        ),
    )
    resolve_parser.add_argument("--repository-policy")
    resolve_parser.add_argument("--branch-protection", action="store_true")
    resolve_parser.add_argument("--override")
    resolve_parser.add_argument(
        "--session-id",
        help=(
            "Session Close ID from publication; substituted into the terminal "
            f"command in place of {SESSION_ID_PLACEHOLDER}."
        ),
    )

    risk_parser = sub.add_parser(
        "review-risk", help="Report the durable classification of one bead body."
    )
    risk_parser.add_argument("--body")
    risk_parser.add_argument("--bead-body-file", type=Path)

    return parser.parse_args(argv)


def _body_text(args: argparse.Namespace) -> str | None:
    if getattr(args, "body", None) is not None:
        return str(args.body)
    if getattr(args, "bead_body_file", None) is not None:
        return Path(args.bead_body_file).read_text(encoding="utf-8")
    return None


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        if args.command == "review-risk":
            body = _body_text(args)
            if body is None:
                raise LandingPolicyError(
                    "REVIEW_RISK_MISSING",
                    "No bead body was supplied.",
                    "Pass --body or --bead-body-file.",
                )
            payload = {
                "contract": CONTRACT,
                "status": "ok",
                "review_risk": review_risk_from_body(body),
            }
        else:
            # The CLI is the agent-facing surface, so the durable body is
            # mandatory here: a flag alone would let a caller assert a
            # classification the bead never recorded. `resolve_review_risk`
            # stays flexible for in-process callers that already hold it.
            if args.bead_body_file is None:
                raise LandingPolicyError(
                    "BEAD_BODY_REQUIRED",
                    "No bead body was supplied.",
                    (
                        "Pass --bead-body-file pointing at the bead body. "
                        "--review-risk is only a cross-check and cannot stand alone."
                    ),
                )
            payload = resolve(
                delivery_mode=args.delivery_mode,
                bead_type=args.bead_type,
                review_risk=resolve_review_risk(
                    review_risk=args.review_risk,
                    description=_body_text(args),
                ),
                repository_policy=args.repository_policy,
                branch_protection=args.branch_protection,
                override=args.override,
                session_id=args.session_id,
            )
    except LandingPolicyError as error:
        print(json.dumps(error.as_result(), sort_keys=True))
        return 2
    except OSError as error:
        print(
            json.dumps(
                LandingPolicyError(
                    "BEAD_BODY_UNREADABLE",
                    f"The bead body could not be read: {error}",
                    "Pass a readable --bead-body-file path.",
                ).as_result(),
                sort_keys=True,
            )
        )
        return 2
    print(json.dumps(payload, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())

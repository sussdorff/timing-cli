"""Classify app usage onto projects.

Only ~15% of raw app activity is auto-assigned to a project by Timing's own
predicate rules. To generate useful time entries we layer our own rules on top:

  1. If Timing already assigned a project to the slice, keep it.
  2. Otherwise, apply the user's configured rules (first match wins).
  3. Otherwise, the slice is left "Unassigned".

Rules match on app name / bundle id (case-insensitive substring) and on window
title / document path (regex). See ``timing_cli.config.Rule``.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass

from timing_cli.config import Rule
from timing_cli.models import (
    MAX_ASSIGNMENT_ALTERNATIVES,
    MAX_PROJECT_TITLE_CHAIN,
    AppUsage,
    AssignmentAlternative,
    AssignmentExplanation,
    AssignmentTarget,
)
from timing_cli.timing_predicates import TimingPredicateRule


@dataclass(frozen=True)
class Classification:
    """The project a slice was classified into and where the decision came from."""

    project_title: str
    project_id: int | None
    source: str  # "timing" | "rule" | "unassigned"
    project_title_chain: tuple[str, ...] = ()


UNASSIGNED = "Unassigned"


def assignments_equivalent(
    left: AssignmentTarget | AssignmentAlternative,
    right: AssignmentTarget | AssignmentAlternative,
) -> bool:
    """Compare project identity without inventing conflicts from missing IDs."""
    if left.project_id is not None and right.project_id is not None:
        return left.project_id == right.project_id
    if left.project_title != right.project_title:
        return False

    left_chain = tuple(left.project_title_chain or [left.project_title])
    right_chain = tuple(right.project_title_chain or [right.project_title])
    if left_chain == right_chain:
        return True
    return len(left_chain) == 1 or len(right_chain) == 1


class _CompiledRule:
    __slots__ = ("rule", "origin", "rule_id", "_title_re", "_path_re")

    def __init__(self, rule: Rule, *, origin: str) -> None:
        self.rule = rule
        self.origin = origin
        canonical = json.dumps(rule.model_dump(), sort_keys=True, separators=(",", ":"))
        digest = hashlib.sha256(canonical.encode()).hexdigest()[:16]
        self.rule_id = f"{origin}:{digest}"
        self._title_re = re.compile(rule.title, re.IGNORECASE) if rule.title else None
        self._path_re = re.compile(rule.path, re.IGNORECASE) if rule.path else None

    def matches(self, usage: AppUsage) -> bool:
        r = self.rule
        if r.app and r.app.lower() not in (usage.app or "").lower():
            return False
        if r.bundle_id and r.bundle_id.lower() not in (usage.bundle_id or "").lower():
            return False
        if self._title_re and not self._title_re.search(usage.title or ""):
            return False
        if self._path_re and not self._path_re.search(usage.path or ""):
            return False
        # A rule with no criteria at all should never match everything.
        return any((r.app, r.bundle_id, r.title, r.path))

    def match_evidence(self, usage: AppUsage) -> tuple[str, str, str] | None:
        if not self.matches(usage):
            return None
        rule = self.rule
        candidates = (
            ("app", usage.app, rule.app),
            ("bundle_id", usage.bundle_id, rule.bundle_id),
            ("title", usage.title, rule.title),
            ("path", usage.path, rule.path),
        )
        for field, actual_value, criterion in candidates:
            if criterion and actual_value is not None:
                return field, actual_value, criterion
        return None


class Classifier:
    """Apply project classification rules.

    Order is deliberate: already-assigned Timing slices win, then explicit user
    config rules, then decoded Timing project predicate rules, then Unassigned.
    """

    def __init__(
        self,
        rules: list[Rule],
        timing_rules: list[TimingPredicateRule] | None = None,
        *,
        user_rule_count: int | None = None,
    ) -> None:
        explicit_count = len(rules) if user_rule_count is None else user_rule_count
        if not 0 <= explicit_count <= len(rules):
            raise ValueError("user_rule_count must fit the supplied rules")
        self._compiled = [
            _CompiledRule(
                rule,
                origin="user_rule" if index < explicit_count else "packaged_rule",
            )
            for index, rule in enumerate(rules)
        ]
        self._timing_rules = timing_rules or []

    def classify(self, usage: AppUsage) -> Classification:
        # 1. Trust Timing's own project assignment when present.
        if usage.project_id is not None and usage.project_title:
            chain = tuple(usage.project_title_chain or [usage.project_title])
            return Classification(usage.project_title, usage.project_id, "timing", chain)

        # 2. First matching user rule wins.
        for compiled in self._compiled:
            if compiled.matches(usage):
                return Classification(
                    compiled.rule.project,
                    None,
                    "rule",
                    (compiled.rule.project,),
                )

        # 3. Reuse Timing's own project predicate rules from the local DB.
        for timing_rule in self._timing_rules:
            if timing_rule.matches(usage):
                return Classification(
                    timing_rule.project_title,
                    timing_rule.project_id,
                    "timing_predicate",
                    timing_rule.project_title_chain,
                )

        # 4. Fall back to unassigned.
        return Classification(UNASSIGNED, None, "unassigned", (UNASSIGNED,))

    def explain(self, usage: AppUsage, *, source_reference: str) -> AssignmentExplanation:
        """Explain every matching assignment while retaining existing precedence."""
        alternatives: list[AssignmentAlternative] = []
        alternatives_complete = True
        for compiled in self._compiled:
            evidence = compiled.match_evidence(usage)
            if evidence is None:
                continue
            if len(alternatives) >= MAX_ASSIGNMENT_ALTERNATIVES:
                alternatives_complete = False
                break
            matched_field, matched_value, criterion = evidence
            alternatives.append(
                AssignmentAlternative(
                    project_title=compiled.rule.project,
                    project_title_chain=[compiled.rule.project],
                    origin=compiled.origin,
                    rule_id=compiled.rule_id,
                    matched_field=matched_field,
                    matched_value=matched_value,
                    criterion=criterion,
                )
            )

        if alternatives_complete:
            for timing_rule in self._timing_rules:
                evidence = timing_rule.match_evidence(usage)
                if evidence is None:
                    continue
                if len(alternatives) >= MAX_ASSIGNMENT_ALTERNATIVES:
                    alternatives_complete = False
                    break
                matched_field, matched_value, criterion = evidence
                canonical = json.dumps(
                    [
                        timing_rule.project_id,
                        timing_rule.project_title,
                        [
                            [condition.field, condition.values, condition.int_values]
                            for condition in timing_rule.conditions
                        ],
                    ],
                    separators=(",", ":"),
                )
                rule_id = (
                    "timing_predicate:"
                    f"{hashlib.sha256(canonical.encode()).hexdigest()[:16]}"
                )
                title_chain = list(timing_rule.project_title_chain)
                alternatives.append(
                    AssignmentAlternative(
                        project_id=timing_rule.project_id,
                        project_title=timing_rule.project_title,
                        project_title_chain=title_chain[-MAX_PROJECT_TITLE_CHAIN:],
                        project_title_chain_complete=(
                            len(title_chain) <= MAX_PROJECT_TITLE_CHAIN
                        ),
                        origin="timing_predicate",
                        rule_id=rule_id,
                        matched_field=matched_field,
                        matched_value=matched_value,
                        criterion=criterion,
                    )
                )

        existing = None
        if usage.project_id is not None and usage.project_title:
            title_chain = usage.project_title_chain or [usage.project_title]
            existing = AssignmentTarget(
                project_id=usage.project_id,
                project_title=usage.project_title,
                project_title_chain=title_chain[-MAX_PROJECT_TITLE_CHAIN:],
                project_title_chain_complete=(
                    usage.project_title_chain_complete
                    and len(title_chain) <= MAX_PROJECT_TITLE_CHAIN
                ),
            )

        if existing is not None:
            conflicts = [
                alternative
                for alternative in alternatives
                if not assignments_equivalent(alternative, existing)
            ]
            return AssignmentExplanation(
                existing_assignment=existing,
                selected_assignment=existing,
                origin="existing",
                source_references=[source_reference],
                alternatives=alternatives,
                alternatives_complete=alternatives_complete,
                conflicts=conflicts,
                conflicts_complete=alternatives_complete,
                uncertainty_reason=(
                    "existing_assignment_conflicts_with_alternatives"
                    if conflicts
                    else "assignment_alternatives_truncated"
                    if not alternatives_complete
                    else None
                ),
            )

        if alternatives:
            selected = alternatives[0]
            conflicts = [
                alternative
                for alternative in alternatives[1:]
                if not assignments_equivalent(alternative, selected)
            ]
            return AssignmentExplanation(
                selected_assignment=AssignmentTarget(
                    project_id=selected.project_id,
                    project_title=selected.project_title,
                    project_title_chain=selected.project_title_chain,
                    project_title_chain_complete=selected.project_title_chain_complete,
                ),
                origin=selected.origin,
                rule_id=selected.rule_id,
                matched_field=selected.matched_field,
                matched_value=selected.matched_value,
                source_references=[source_reference],
                alternatives=alternatives,
                alternatives_complete=alternatives_complete,
                conflicts=conflicts,
                conflicts_complete=alternatives_complete,
                uncertainty_reason=(
                    "multiple_matching_projects"
                    if conflicts
                    else "assignment_alternatives_truncated"
                    if not alternatives_complete
                    else None
                ),
            )

        return AssignmentExplanation(
            origin="unresolved",
            source_references=[source_reference],
            alternatives=[],
            conflicts=[],
            uncertainty_reason="no_matching_assignment_evidence",
        )

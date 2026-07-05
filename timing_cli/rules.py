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

import re
from dataclasses import dataclass

from timing_cli.config import Rule
from timing_cli.models import AppUsage
from timing_cli.timing_predicates import TimingPredicateRule


@dataclass(frozen=True)
class Classification:
    """The project a slice was classified into and where the decision came from."""

    project_title: str
    project_id: int | None
    source: str  # "timing" | "rule" | "unassigned"
    project_title_chain: tuple[str, ...] = ()


UNASSIGNED = "Unassigned"


class _CompiledRule:
    __slots__ = ("rule", "_title_re", "_path_re")

    def __init__(self, rule: Rule) -> None:
        self.rule = rule
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


class Classifier:
    """Apply project classification rules.

    Order is deliberate: already-assigned Timing slices win, then explicit user
    config rules, then decoded Timing project predicate rules, then Unassigned.
    """

    def __init__(
        self,
        rules: list[Rule],
        timing_rules: list[TimingPredicateRule] | None = None,
    ) -> None:
        self._compiled = [_CompiledRule(r) for r in rules]
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

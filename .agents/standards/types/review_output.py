"""Python mirror of constants declared in standards/types/review-output.ts.

This module exports the eight named constant vocabularies that define the
review-output sidecar format. The TypeScript file is the source of truth for
non-Python consumers; this module mirrors those values for Python code.
"""

from __future__ import annotations

REVIEW_OUTPUT_SCHEMA_VERSION: int = 2

REVIEWER_TYPES: tuple[str, ...] = (
    "stream",
    "work-order-readiness",
    "work-order-review",
    "verification",
    "wave-pre-dispatch",
)

FINDING_SEVERITIES: tuple[str, ...] = (
    "blocking",
    "advisory",
    "observation",
)

FINDING_CATEGORIES: tuple[str, ...] = (
    "ig-drift",
    "metadata-drift",
    "dead-code",
    "sync-gap",
    "anti-pattern-propagation",
    "scope-creep",
    "test-quality",
    "adr-compliance",
    "acceptance-drift",
    "premise-verification",
    "duplicate-detection",
    "empty-spec",
    "cross-repo-placement",
    "seed-data-drift",
    "ac-incomplete",
    "verification-claim-mismatch",
)

FINDING_DISPOSITIONS: tuple[str, ...] = (
    "keep",
    "fold",
    "weed",
    "move-to-sibling",
    "cluster-into-epic",
)

EVIDENCE_TYPES: tuple[str, ...] = (
    "file",
    "git",
    "registry",
    "work-order-field",
    "shell",
)

SUGGESTED_ACTION_TYPES: tuple[str, ...] = (
    "file_work_order",
    "fix_code",
    "update_close_reason",
    "sync_standard",
    "add_dependency",
    "delete_dead_code",
    "save_feedback_memory",
    "fold_into_work_order",
    "move_to_sibling_repo",
    "weed_with_reason",
    "no_action",
)

COHORT_SELECTOR_TYPES: tuple[str, ...] = (
    "epic",
    "wave",
    "label",
    "time-window",
)

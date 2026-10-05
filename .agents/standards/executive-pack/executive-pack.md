---
domain: executive-pack
description: Ownership, review and merge boundaries of one repository delivery that runs through the executive-pack skill.
---

# Executive Pack

> **Scope**: Loaded by primitives that take part in a repository delivery and must agree
> on who owns it, what counts as review and verification, and when a merge is allowed.

## One delivery

A delivery is one hosted work order in one repository, worked in one linked worktree and
landed through one pull request. The invoking session is the main session and owns the
delivery from grilling to the merge decision; it is never spawned, replaced or handed to
another agent. There are no packs of several work orders, no shards, no admission
packets and no coordinator threads.

Steps and actors (models per the `dispatch/model-routing` standard):

1. grilling - main session; only product or preference questions reach the human.
2. implementation - `implementer` subagent with `tdd`; it owns source and tests.
3. adversarial review - three read-only reviewers on `opus`, `sonnet` and `haiku`, same
   brief, in parallel, on one fixed candidate; the `opus` reviewer is named the
   designated repair author before dispatch; the main session merges their findings.
4. triage - `finding_triage.py`; one repair round by the designated repair author, which
   receives write authority only for the accepted set; the rest goes to the pull
   request's Review decisions section.
5. verification - an agent that authored neither the implementation nor any repair runs
   the changed artifact and returns `PASS`, `PASS+NOTES` or `FAIL` bound to the head
   commit.
6. pull request - always; pr-agent reviews it once for standards and conventions and
   sets the `review-risk:*` label as classification.
7. merge decision - the main session, under the conditions in the executive-pack skill.
8. session retro - `session-retro`.

## Boundaries

- Reviewers start read-only. Exactly one of them, the designated repair author, may be
  granted write authority afterwards, bounded to the accepted repair set; the others and
  the implementer do not write while it does.
- The repair author is a coauthor from its first commit, so it can no longer verify or
  approve that delivery. A verifier authored neither the implementation nor any repair.
- Ambiguity or scope beyond the accepted set returns to the main session, never a
  silent edit, and never a silent fall back to the implementer.
- Tests alone are not verification; a green CI or a pr-agent approval is not the verdict.
- A missing actor, a failed dispatch or an incomplete answer never counts as approval.
- The PR's `review-risk:*` label classifies and informs; the work order's `Review-Risk:`
  line is its floor, applied by pr-agent. No class blocks an agent merge by itself, but
  a merge needs both a pr-agent review on the pull request and a pr-agent
  classification of the current head that is not `unclassified`. They are separate
  outputs; a classification without a review is missing pr-agent evidence.
- The main session merges itself unless the change makes a product decision that differs
  from the work order, or economic damage is to be expected (money movement, billing or
  invoices, irreversible customer-data loss, a realistic personal-data leak, contractual
  or legal exposure). It records both assessments in the pull request body. Product
  owner rule, 2026-09-28: "Wenn hier keine Produktentscheidung anders getroffen wurde als
  im Ticket und kein wirtschaftlicher Schaden zu erwarten ist, dann selber mergen."
- The main session never sets, changes or removes a `review-risk:*` label.
- A generated/sync or documentation-only pull request without a work order is not a
  full delivery; its minimal evidence, which replaces step 5's verification, is in the
  executive-pack skill's "Pull requests without a work order" section, and its
  product-decision assessment compares against the user's authorization instead of the
  work order. Every other merge condition still holds. Changes to merge, authorization,
  review or guard rules always need a work order. That section grants no new merge
  permission.
- A documentation-only change, with or without a work order, is verified by the
  relevant link and metadata checks plus an instruction review by a non-author agent.
- An explicit human merge gate from the user or the repository always wins.

## Review risk

This section is the single source for when a review-risk class other than `none` is
valid and what it means for the merge. The class is the work order's `Review-Risk:` line
or the `review-risk:*` label pr-agent set on the pull request. The `cognovis-pr` skill
holds the Risk statement format and an example.

- A class is never a bare label. Every pull request whose class is not `none` carries a
  checkable Risk statement in its body: data class, boundary before and after, damage
  scenario, reach, reversal and the evidence that proves the new boundary.
- A class needs a concrete damage scenario. When none can be named, the classification
  is wrong and should be `none`; the Risk statement says so instead of inventing one.
  Touching an auth, payment or data area without moving a boundary is not a scenario.
- `pii` is valid only when the diff changes a crossing that the repository's PII
  boundary standard defines, `.agents/standards/pii-boundary.md` in that repository. The
  Risk statement and pr-agent's classification cite that crossing. The generic crossing
  types a repository standard refines are:
  - a new reader or role gains access to personal data;
  - a new egress of personal data: an export, an LLM call with patient or other
    personal context, log or audit output, a third-party service, a backup;
  - a check that protects personal data is removed or weakened.
- Typically not personal data: terminology and catalogues, configuration, profiles and
  synthetic fixtures. A change confined to them crosses no PII boundary.
- When the repository has no PII boundary standard yet, the Risk statement names the
  boundary it assumes, so a reviewer can check the claim against the diff.
- Economic damage includes data protection. A realistic leak of personal data is
  economic damage: GDPR fines, the notification duty and lost customer trust. An actual
  PII boundary crossing with a realistic scenario that reaches real personal data
  therefore holds the merge for a human; a `pii` label without such a scenario does not.

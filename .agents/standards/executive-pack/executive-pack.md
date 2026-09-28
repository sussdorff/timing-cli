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
   brief, in parallel; the main session merges their findings.
4. triage - `finding_triage.py`; one repair round by the implementer; the rest goes to
   the pull request's Review decisions section.
5. verification - a non-author agent runs the changed artifact and returns `PASS`,
   `PASS+NOTES` or `FAIL` bound to the head commit.
6. pull request - always; pr-agent reviews it once for standards and conventions and
   sets the `review-risk:*` label.
7. merge decision - the main session, under the conditions in the executive-pack skill.
8. session retro - `session-retro`.

## Boundaries

- Reviewers and verifiers are read-only and never the author of the change.
- Tests alone are not verification; a green CI or a pr-agent approval is not the verdict.
- A missing actor, a failed dispatch or an incomplete answer never counts as approval.
- The PR label `review-risk:none` for the current head is the only risk signal an agent
  merge accepts; the work order's `Review-Risk:` line is its floor, applied by pr-agent.
- The main session never sets, changes or removes a `review-risk:*` label.
- An explicit human merge gate from the user or the repository always wins.

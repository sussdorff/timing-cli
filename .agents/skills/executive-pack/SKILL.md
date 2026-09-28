---
name: executive-pack
description: Deliver one hosted work order in the invoking session - grilling, tdd implementation, three-model adversarial review with triage, independent verification, one pull request, merge decision and session retro.
requires_standards: [executive-pack, dispatch/model-routing]
requires:
  - script:ccore
  - skill:playwright-cli
  - skill:session-retro
  - agent:implementer
  - standard:executive-pack
scripts:
  - path: scripts/finding_triage.py
    role: helper
    entrypoint: true
    language: python
    output_contract: json-envelope
compatibility: {}
metadata: {}
---

# Delivery

The invoking session is the main session (`opus`). It owns one hosted work order from
grilling to the merge decision and never hands that ownership to another agent. Work
happens in the delivery worktree the session already owns (the T3 thread worktree, or a
self-managed linked worktree). Read the work order with `ccore tracker show <ref>`.

The Pocock skills `grilling`, `tdd`, `code-review` and `pr` are installed globally per
host; `playwright-cli` comes from the Library. Model aliases and their `ccore agent`
fallback routes are in the injected `dispatch/model-routing` standard: use the native
subagent with the alias first, the named `ccore agent` route only when the alias is
unavailable.

Resolve the installed helper root local-first and fail closed if none exists:
`<repo>/.agents/skills/executive-pack`, `<repo>/.claude/skills/executive-pack`,
`~/.agents/skills/executive-pack`, `~/.claude/skills/executive-pack`. The only helper is
`scripts/finding_triage.py`.

## 1. Grilling (main session, `opus`)

Run `grilling` against the work order until the intent, the acceptance criteria and the
boundaries are unambiguous. A question that reading code, running the artifact or
building a throwaway prototype can answer is answered by the agent, not asked. Only
product or preference decisions go to the human. When the answers change the work
order, update it with the intake author check and `ccore tracker update`.

## 2. Implementation (`implementer` subagent on `opus`, with `tdd`)

Dispatch one `implementer` subagent on `opus` in the delivery worktree. It receives the
work order, the grilling outcome, the worktree and its base commit, implements with
`tdd`, runs the affected checks and commits the candidate. It does not review or verify
its own change.

## 3. Adversarial review (three models, read-only, in parallel)

Dispatch three read-only reviewer subagents in parallel, one each on `opus` (a fresh
context, not the implementer's), `sonnet` and `haiku`. All three get the same
adversarial brief, with no per-model persona:

- the stated intent and the acceptance criteria of the work order,
- the complete diff from the base commit to the candidate,
- the instruction: find where this change fails its intent - incorrect behaviour,
  missing cases, and claims the change or its tests do not prove. Return each finding
  with an id, a severity (`nit`, `low`, `medium`, `high`, `critical`), the paths, the
  acceptance criterion it concerns (or that it concerns the change's own behaviour) and
  a one-sentence summary.

Each reviewer applies the `code-review` skill's review method and checklist itself; it
does not start that skill's own subagents. Each reviewer works alone and returns one
finding list. When a native alias fails, that
reviewer runs through its `ccore agent` fallback route. When no route works for a
reviewer, stop and report the dispatch failure; never continue with fewer reviewers and
never treat a transport failure as a clean review. Record the route each reviewer used.

The main session merges the three result sets into one deduplicated finding list. This
review looks for failures against intent; pr-agent covers the standards and conventions
lens later. Neither a green CI nor a pr-agent approval counts as the verification verdict.

## 4. Triage (one repair round)

Run `scripts/finding_triage.py --findings-file <merged.json> --diff-path <path>...
--ac-ref <AC>...`. Its `repair` set goes back to the same `implementer` subagent in one
round, all findings at once, ending in one repair commit. Run it again with
`--review-decisions --repair-rounds-used 1` and one `--repaired <id>` per finding the
repair commit fixed, to render the deferred and the repaired findings as the "Review
decisions" section of the pull request body. An unknown repaired id fails the call. A
second repair round needs a reason the main session states in that section.

## 5. Verification (always, by a non-author agent)

Every delivery is verified by an agent that did not write the change. Only evidence from
running the changed artifact counts: a command, a request or a UI path, with its
observed result. Tests passing are not verification.

- When the delivered repository has a skill matching `.agents/skills/verify-*`, the
  verifier uses it.
- UI changes are driven with `playwright-cli` by a `haiku` subagent. When that alias is
  unavailable or cannot operate `playwright-cli`, run the verifier through
  `ccore agent run --model gpt-6-luna --harness codex`.
- Other changes are verified by a `haiku` subagent that runs the changed command,
  endpoint or script.

The verifier returns one verdict - `PASS`, `PASS+NOTES` or `FAIL` - together with the
head commit SHA it verified and each run path with its outcome. A new commit on the
branch invalidates the verdict; verify again. A `FAIL` goes back to the implementer as a
repair. When the change cannot be run at all, record that reason instead of a verdict;
such a delivery is never merged by the main session.

## 6. Pull request (`pr`)

Always open a pull request: write its text with `pr` and publish it with
`ccore pr ensure --repo <worktree> --summary <text>`, which picks `gh` or `fgj`
from the remote. `ccore pr ensure` rebases the branch onto the target before its first
push; when that changes the head commit, verify again (step 5) and update the
Verification section. Push later repair commits with a plain `git push`. Rerunning
`ccore pr ensure` on an already published branch can rebase and force-push it; that is a
history rewrite and needs the user's authorization for this branch. The body carries,
besides the summary:

- a reference to the work order: `Closes #<n>` when the issue lives in the same
  repository, the full issue URL otherwise,
- a **Review decisions** section from step 4,
- a **Verification** section with the verdict, the verified head SHA and every run path
  with its outcome,
- the model route each of the three reviewers used.

pr-agent on Atlas reviews the pull request once, from `.agents/standards/review.md` and
`AGENTS.md`, and does not re-raise findings listed under Review decisions. It sets
exactly one `review-risk:*` label and names the head SHA it classified. For each
pr-agent finding, repair it (then verify again) or add it to Review decisions with the
reason.

## 7. Merge decision

The main session merges only when all of the following hold for the current head
commit; otherwise it leaves the pull request open for a human and lists the missing
evidence:

- the pull request carries exactly one `review-risk:*` label, it is `review-risk:none`,
  and pr-agent's latest classification comment names the current head commit SHA. A
  missing, stale or `review-risk:unclassified` label, or any other risk label, leaves
  the pull request for a human. The main session never sets, changes or removes that
  label.
- required checks pass.
- the Verification section records `PASS` or `PASS+NOTES` for the current head commit
  SHA.
- no accepted local finding is unrepaired.
- the pr-agent review has no unresolved finding that Review decisions does not cover.

An explicit human merge gate from the user or the repository still requires the human.

After a merge, confirm with `ccore tracker show <ref>` that the work order closed and
close it with `ccore tracker close <ref>` otherwise. Remove a self-managed worktree with
`worktree-cleanup`; a T3 thread worktree belongs to T3 and stays. Run any
post-merge postcondition the repository's `AGENTS.md` names.

## 8. Session retro

After the merge, or after handing the pull request to a human, run `session-retro` on
the finished session. It encodes learnings as structure first and stores them in Open
Brain and the standards; it does not merge, push, close issues or clean worktrees.
Report the pull request, its merge state, the verdict and the retro result.

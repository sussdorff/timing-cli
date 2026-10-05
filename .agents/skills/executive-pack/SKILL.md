---
name: executive-pack
description: Deliver one hosted work order in the invoking session - grilling, tdd implementation, three-model adversarial review with triage, independent verification, one pull request, merge decision and session retro.
requires_standards: [executive-pack, dispatch/model-routing]
requires:
  - script:ccore
  - skill:playwright-cli
  - skill:cognovis-pr
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
context, not the implementer's), `sonnet` and `haiku`. Name the `opus` reviewer the
**designated repair author** in its brief before dispatching: it reviews read-only like
the others now, and it is the one actor that may later receive write authority for the
triaged repair set. Dispatch it as an agent type that has write tools and instruct it
to stay read-only during review: a read-only agent type (for example `Explore`) cannot
take the repair later, and the hand-off then needs a replacement. All three review the
same fixed candidate commit. All three get the
same adversarial brief, with no per-model persona:

- the stated intent and the acceptance criteria of the work order,
- the complete diff from the base commit to the candidate,
- the instruction: find where this change fails its intent - incorrect behaviour,
  missing cases, and claims the change or its tests do not prove. Return each finding
  with an id, a severity (`nit`, `low`, `medium`, `high`, `critical`), the paths, the
  acceptance criterion it concerns (or the literal `own-behaviour` when it concerns the
  change's own behaviour) and a one-sentence summary.

Each reviewer applies the `code-review` skill's review method and checklist itself; it
does not start that skill's own subagents. Each reviewer works alone and returns one
finding list. When a native alias fails, that
reviewer runs through its `ccore agent` fallback route. When no route works for a
reviewer, stop and report the dispatch failure; never continue with fewer reviewers and
never treat a transport failure as a clean review. Record the route each reviewer used.

The main session merges the three result sets into one deduplicated finding list. This
review looks for failures against intent; pr-agent covers the standards and conventions
lens later. Neither a green CI nor a pr-agent approval counts as the verification verdict.

## 4. Triage (one repair round, by the designated repair author)

Run `scripts/finding_triage.py --findings-file <merged.json> --diff-path <path>...
--ac-ref <AC>...`. Its `repair` set goes to the designated `opus` reviewer from step 3,
in one round, all findings at once, ending in one repair commit.

That hand-off is where its write authority starts, and the accepted repair set is all of
it. Give it the bounded set, the candidate it reviewed and the worktree; it applies
every finding in that set, runs the affected checks, commits, and reports the repaired
finding ids, the new head SHA and the checks it ran. It becomes a coauthor of the
delivery. The `implementer` and the other two reviewers write nothing while it works —
one writer at a time, so a finding is never repaired twice or reverted by a concurrent
edit. A finding whose requirement is ambiguous, or whose fix would exceed the accepted
set, goes back to the main session instead of being decided in the repair commit.

The repair author cannot verify or approve its own repair, and the main session keeps
acceptance and the merge decision. If that reviewer's session is gone when triage
finishes, a replacement takes the role only after reading the pinned candidate and the
accepted findings; record why the original was unavailable and which route the
replacement used. There is no silent fall back to the implementer.

Run `finding_triage.py` again with `--review-decisions --repair-rounds-used 1` and one
`--repaired <id>` per finding the repair commit fixed, to render the deferred and the
repaired findings as the "Review decisions" section of the pull request body. An unknown
repaired id fails the call. A second repair round needs a reason the main session states
in that section.

## 5. Verification (always, by a non-author agent)

Every delivery is verified by an agent that authored neither the implementation nor any
repair — so never the `implementer` and never the designated repair author once it has
committed. Only evidence from running the changed artifact counts: a command, a request or a UI path, with its
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
branch invalidates the verdict; verify again. A `FAIL`, and any later finding from
verification or from the pull request, goes back through the main session to the same
designated repair author, so the delivery keeps one writer after review. When the change cannot be run at all, record that reason instead of a verdict;
such a delivery is never merged by the main session. A documentation-only change, with
or without a work order, is not such a delivery: its step 5 evidence is the relevant
link and metadata checks plus an instruction review of the changed text by a non-author
agent, recorded in the Verification section. A generated/sync or documentation-only
pull request without a work order has its evidence defined under
[Pull requests without a work order](#pull-requests-without-a-work-order).

## 6. Pull request (`cognovis-pr`)

Always open a pull request. Write its text with `cognovis-pr`, which reads the
installed `pr` skill for the template and owns the sections a Cognovis delivery adds;
do not restate those sections here. Hand it the `finding_triage.py --review-decisions`
output from step 4, the verifier's verdict and verified head SHA from step 5, the work
order reference, the model route each of the three reviewers used, the product
decision and economic damage assessments of step 7, and, when the review risk is not
`none`, the Risk statement content. The injected `executive-pack` standard's Review
risk section defines when a class is valid; `cognovis-pr` holds the statement format.

Publish the result with `ccore pr ensure --repo <worktree> --summary <text>`, which
picks `gh` or `fgj` from the remote. `ccore pr ensure` rebases the branch onto the
target before its first push; when that changes the head commit, verify again (step 5)
and update the Verification section. Push later repair commits with a plain `git push`.
Rerunning `ccore pr ensure` on an already published branch can rebase and force-push it;
that history rewrite of the delivery's own task branch is internal work and needs no
confirmation; never force-push a shared or default branch.

pr-agent on Atlas reviews the pull request once, from `.agents/standards/review.md` and
`AGENTS.md`, and does not re-raise findings listed under Review decisions. It sets
exactly one `review-risk:*` label, as classification, and names the head SHA it
classified. When that class is not `none` and the body has no Risk statement yet, add
it. For each pr-agent finding, repair it (then verify again) or add it to Review
decisions with the reason.

## 7. Merge decision

The main session merges only when all of the following hold for the current head
commit; otherwise it leaves the pull request open for a human and lists the missing
evidence. A pull request without a work order reads the Verification and
product-decision conditions as substituted under
[Pull requests without a work order](#pull-requests-without-a-work-order):

- pr-agent's latest classification comment names the current head commit SHA. A
  missing or stale classification, or `review-risk:unclassified`, is missing pr-agent
  evidence. The class itself (`none`, `payment`, `pii`, `auth`, `compliance`) classifies
  and informs; it does not block the merge. The main session never sets, changes or
  removes that label.
- a pr-agent review comment exists on the pull request: it starts with
  `## PR Reviewer Guide`, is edited in place on later reviews, and is written by the
  provider's pr-agent identity (`cognovis-pr-agent` on git.cognovis.de, the GitHub App
  `cognovis-atlas-pr-agent[bot]` on GitHub). The classification and the review are
  separate outputs, so a missing review is missing pr-agent evidence even when a
  classification exists; the pull request stays open until a writer's `/review`
  produces one.
- required checks pass, read after the last edit of the pull request body: a body edit
  re-runs the `pull_request` workflows that trigger on `edited`, so a status that was
  green before the edit can be pending again. Merge with the head commit SHA pinned once
  it is green again. A body edit does not re-run a workflow that triggers only on new
  commits, so it cannot retry a failed run of one.
- the Verification section records `PASS` or `PASS+NOTES` for the current head commit
  SHA.
- no accepted local finding is unrepaired.
- the pr-agent review has no unresolved finding that Review decisions does not cover.
- no product decision deviates: the main session compared the delivered behaviour with
  the work order's decisions, Scope-In/Scope-Out and acceptance criteria, and found no
  default, rule, scope boundary, user-visible behaviour or data-model choice that the
  work order does not state or states otherwise.
- no economic damage is to be expected: the main session assessed money movement,
  billing or invoices, irreversible customer-data loss, a realistic personal-data leak,
  and contractual or legal exposure. Damage is expected when the delivered and verified
  behaviour would cause one of these, or when a known open risk of that kind remains;
  touching such an area with verified behaviour is not damage by itself. An actual PII
  boundary crossing with a realistic scenario that reaches real personal data is
  expected damage; a `pii` label without such a scenario is not (the `executive-pack`
  standard, Review risk).
- the Merge assessment section of the pull request body names both assessments for the
  current head, each with its reason.
- when the review risk is not `none`, the Risk statement section names every field for
  the current head, and a `pii` class cites its crossing from the repository's PII
  boundary standard or the assumed boundary. A missing Risk statement is missing
  evidence; a statement that names no concrete scenario does not hold the merge.

These two conditions are the product owner's rule (2026-09-28), adopted verbatim with no
category carved out: "Wenn hier keine Produktentscheidung anders getroffen wurde als im
Ticket und kein wirtschaftlicher Schaden zu erwarten ist, dann selber mergen." When
either assessment fails, the pull request stays open for a human with that assessment
as the reason. An explicit human merge gate from the user or the repository still
requires the human.

The Atlas missing-review notice carries the hidden marker
`<!-- pr-agent-webhook:review-missing head=<sha> -->`, where `head=<sha>` names the head
it concerns. The notice stays on the pull request, so it holds the merge only while no
pr-agent review comment was written or edited after it; once such a review exists, the
review condition above holds and the notice no longer blocks. While the notice holds,
the main session comments `/review` on the pull request once per notice, not on every
pass, and waits for the review instead of merging. The delivery request that invokes
this skill authorizes that `/review` comment on the delivery's own pull request; it
authorizes no other comment. If no review arrives after the `/review`, for example
because Atlas posts a further notice, the pull request stays open for a human with the
missing review as the reason.

After a merge, confirm with `ccore tracker show <ref>` that the work order closed and
close it with `ccore tracker close <ref>` otherwise. Remove a self-managed worktree with
`worktree-cleanup`; a T3 thread worktree belongs to T3 and stays. Run any
post-merge postcondition the repository's `AGENTS.md` names.

## 8. Session retro

After the merge, or after handing the pull request to a human, run `session-retro` on
the finished session. It encodes learnings as structure first and stores them in Open
Brain and the standards; it does not merge, push, close issues or clean worktrees.
Report the pull request, its merge state, the verdict and the retro result.

## Pull requests without a work order

Two kinds of pull request may have no work order and are then not a full delivery
through steps 1 to 5:

- a generated or sync pull request, whose diff is only generator output, for example a
  Library sync;
- a documentation-only pull request, whose diff changes only documentation or
  instruction text.

This clarifies how the product owner's rule of 2026-09-28 quoted in step 7 applies to
them; it is not a new merge permission. A pull request that changes behaviour beyond
the generated output or the documentation is a normal delivery and needs a work order.
So does any change to merge, authorization, review or guard rules, even when it touches
only instruction text: it is never on this route.

The pull request body records this minimal evidence for the current head commit:

- the user's explicit authorization for this pull request, cited in place of the work
  order reference; it stands in for the work order.
- generated or sync: re-running the generator yields no diff, and the tests of the
  synced helpers pass.
- documentation-only: the relevant link and metadata checks pass, and an instruction
  review of the changed text by a non-author agent left no open finding.
- the Merge assessment. The product-decision assessment compares the change with the
  user's authorization instead of a work order; the economic-damage assessment is
  unchanged.
- the Risk statement, when the review risk is not `none`.

For this kind of pull request these items replace step 5's verification, and step 7
applies with two substitutions: the evidence above satisfies its Verification
condition, and its product-decision condition compares against the user's
authorization. Every other step 7 condition still holds: pr-agent's latest
classification names the current head commit, a pr-agent review comment exists on the
pull request, required checks pass after the last body edit, no accepted local finding
is unrepaired, the pr-agent review has no unresolved finding, the Merge assessment
names both assessments, the Risk statement is complete when the class is not `none`,
and an explicit human merge gate still requires the human.

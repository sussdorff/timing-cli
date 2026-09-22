### Creating and editing beads

Read and mutate bead state with direct, non-interactive `bd` commands (`--json`
where available). When the registry entry declares a tracker, use `ccore tracker`
instead of `bd`; with no tracker field, keep `bd` for the Beads archive. For a new bead or a body-changing update, write the factory-ready
payload to a temp file, validate it with the bead-author-check validator, then run
`bd create --body-file <file>` or `bd update <id> --body-file <file>`. This keeps
bead hygiene enforced (Intent, Acceptance Criteria, MoC, dependency links).

The validator lives at exactly two paths — probe them in this order and use the
first hit:

1. `<repo>/scripts/bead-author-check.py` (project-local copy, when the repo ships one)
2. `~/.agents/scripts/bead-author-check.py` (global install, works from any repo)

If neither exists, skip validation, say so in your report, and continue with
`bd create`/`bd update`. NEVER search the filesystem for the script (`find`,
`locate`, recursive `ls`/glob over `$HOME` or `/`) — a filesystem-wide hunt is
always wrong; the two paths above are the entire search space.

#### One request, one bead

One request is one bead. The steps toward it are an internal workplan, not sub-beads.
A bead's Acceptance Criteria bundle is the reviewer's unit of judgment over one
coherent change, so slicing one requirement into one bead per Acceptance Criterion is
a local optimization that loses the whole-system view.

Two tells that candidate beads are really one bead:

- they touch the same file, or
- an ordering between them was invented by the author rather than forced by the work.

Either tell raises a presumption to merge, not a verdict: merge the candidates,
implement in one pass, and take one consolidated review — unless a candidate is
independently verifiable, carries a different risk profile or verification
environment, or enables genuine parallelism. Record that rationale in the bead when
you keep them separate. The full contract — cohesive scope, artificial split, and
over-slicing rules — is `workflow/bead-hygiene`.

#### Refactoring found along the way

Code that should be refactored but is not the current task stays untouched. Do
not refactor as a side effect of an unrelated task — it widens the diff a
reviewer has to judge and hides the change that was actually requested.

Name the finding in the final report and let the user decide. Do not file it as
a `[DISCOVERED]` or `[REFACTOR]` side-observation bead; those accumulate into a
backlog nobody carries.

#### A note never changes the work order

When a decision supersedes part of a bead, **rewrite the body** — Intent, Scope-In,
Scope-Out, Acceptance Criteria, Pre-Mortem — and use a note only to record why it
changed and when.

Notes carry context, evidence, and history. The body is the instruction, and whoever
picks the bead up reads the body. A body that contradicts its own note is worse than
an uncorrected one, because it hands out the superseded instruction silently. Writing
a note *because* the body is now wrong is the signal to rewrite the body.

#### Bug-bead proportionality

STATUS: AUTHORING POLICY. `bead-author-check.py` enforces structure but cannot
determine the semantic boundary of a reported defect; authors and reviewers apply
this rule directly (clc-2acb).

For `bug` beads, keep Acceptance Criteria and Means of Compliance at the defect
boundary:

- Default to one AC: the reported failing case now behaves as expected. Add one
  adjacent control-case AC only when the fix can plausibly regress that behavior.
- Put implementation constraints such as "no customer-specific logic" in
  `Scope-Out` or constraints, not in separate ACs.
- Use the smallest focused regression check that fails before and passes after the
  fix. A targeted unit or integration test is normally sufficient.
- Do not require full test suites, unrelated services or systems, tenant/customer
  data, browser/platform matrices, E2E/UAT/demo evidence, deployments, or release
  builds unless the reported defect itself exists across that exact boundary.
- Keep health checks, repository-wide CI, build, lint, and push-preflight checks as
  delivery gates. They are not additional bug ACs or MoC rows.
- Missing local production-like data does not justify inventing a staging,
  Playwright, or UI substitute flow. Verify the reported defect at the lowest layer
  that proves the fix.

Feature beads may require broader capability and system evidence. Do not import
that feature-scale verification policy into bug beads.

Never delegate bead authoring to a subagent; the interactive session remains
the original author. Sync bead
state with `ccore beads sync` and a stable operation ID
before reporting a bead handoff-ready. `bd dolt push --force` is reserved for
explicit human recovery; the path is in `cognovis-beads/references/dolt-sync.md`.


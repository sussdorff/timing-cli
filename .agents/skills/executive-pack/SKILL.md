---
name: executive-pack
description: Own an approved repository delivery in the invoking session, from hosted-issue admission through review and Session Close.
requires_standards: [executive-pack, workflow/uat-config-schema, dispatch/model-routing]
requires:
  - skill:implementation-loop
  - skill:context-discovery
  - skill:playwright-cli
  - skill:session-close
  - agent:implementer
  - agent:uat-validator
  - agent:focus-review-agent
  - agent:plan-reviewer
  - agent:doc-changelog-updater
  - standard:executive-pack
scripts:
  - path: scripts/landing_policy.py
    role: helper
    entrypoint: true
    language: python
    output_contract: json-envelope
  - path: scripts/pack_review_contract.py
    role: helper
    entrypoint: false
    language: python
    output_contract: json-envelope
compatibility: {}
metadata: {}
---

# Repository Delivery

Consumer-owned helpers are in `scripts/` of the **installed** skill root, not
the marketplace source path `skills/executive-pack/`. Resolve `$SKILL_ROOT`
local-first and fail closed if none of these exist:

1. `<repo>/.agents/skills/executive-pack`
2. `<repo>/.claude/skills/executive-pack`
3. `<repo>/skills/executive-pack`
4. `~/.agents/skills/executive-pack`
5. `~/.claude/skills/executive-pack`

Helpers include quick-fix and live-network checks, effort
classification, workspace guards, Phase 14 scope, the landing-policy resolver,
and the plan-review gate. Delivery identity is `ccore delivery start`.

Own one approved repository delivery in this invoking session. `solo` admits exactly
one hosted issue; `executive-pack` admits an ordered issue list in one repository. The normal
shape uses one linked worktree (T3 thread worktree by default). An optional Sub-Pack shape adds isolated execution
worktrees around one parent integration worktree without creating nested repository
deliveries. A direct skill invocation and a launcher-created initial prompt enter this
same repository delivery contract. Never spawn or rename a delivery-owner agent.

STATUS: BEHAVIORAL ROLE AND REVIEW POLICY. The initiating prompt names actors in a
readable role paragraph. The delivery owner follows that paragraph and the applicable review reference. Transport can prove that a distinct session ran, but routing tables or
deterministic model-selection machinery do not interpret the paragraph.

## Presets

The Light preset is the default: one fresh Reviewer 1 per member, one fresh whole-Pack
Reviewer 1 pass at the end, no Reviewer 2, and security or acceptance only where the
repository policy or a claim makes them applicable. High Assurance adds the fresh
different-family Reviewer 2 and the security perspective. High Assurance is selected
when the landing-policy envelope reports an elevating `review_risk` (payment, PII,
auth, compliance), when the caller names it in the role paragraph, or when the
repository's own instructions require it. Record the preset in the admission packet;
it does not change after admission.

## Admission session and coordinator

Admission may run in a more capable session than delivery. Read
[admission-packet.md](references/admission-packet.md): a Fable or Astra session
grills the work order, derives seams, resolves landing policy and writes the compact
admission packet; a large-context, lower-cost coordinator session (Sonnet 5 under the
Claude provider, or Luna medium under the Codex provider) starts fresh from that
packet and owns the delivery from `ccore delivery start` through Session Close. The owner is
fixed at the end of admission. Never spawn, replace or rotate it afterwards; the
compact handoff rotates implementation sessions only. When the operator instead
preselects Luna for one session that does both phases, read
[luna-coordination.md](references/luna-coordination.md) for its role prompt, packet
and bounded fresh-Astra advisor rules. Prompt text cannot switch a session's model.

## Admission

Validate the explicit mode, repository, linked worktree, unique ordered issue
refs, dependency readiness, proposed TDD seams and prerequisite evidence. Read
each work order with `ccore tracker show`. Registry entries must declare
`github` or `forgejo`; unhosted entries fail closed. Never infer the backend
from git remotes. Derive seams
from approved AC/MoC; ask only when an unresolved boundary changes scope or risk.
Preserve explicit authorization for the same concrete work and local repairs.
Freeze this contract for the current delivery; edits to it do not change this run.

Name the implementation owner, Reviewer 1, Reviewer 2 and fallback in one role
paragraph, preserving distinct actors and required different-family final review.
Under the Light preset Reviewer 2 is named as `not required`; the fresh Reviewer 1
must still differ in family from the implementation actor. Missing actors or
incomplete answers never imply approval. The invoking session
owns delivery identity, sequencing, finding disposition, callbacks and Session Close. The
same logical implementation owner owns all source and repairs; reviewers are read-only.
Its current session changes only through the compact committed handoff in
[compact-handoff.md](references/compact-handoff.md). This internal handoff needs no
human approval. The logical implementation owner remains distinct from the delivery
owner and reviewers, and exactly one current implementation session may write.
An optional plan-reviewer advises on an admitted plan and grants no authority. Under
the Luna profile, the bounded Astra advisor in the profile reference is also advisory;
it never enters the implementation or review lineage.

Before dispatch read [admission.md](references/admission.md). Call
`ccore delivery start` and scripts/landing_policy.py resolve; use their
typed envelopes, not process exit alone or a prose reconstruction of policy. Record
the exact issue refs, candidate, branches, worktree owner and session identity. Provider
worktree ownership is declared, never guessed from paths.

### Optional work-kind delegation

Use the work kinds in the injected model-routing standard as responsibilities, not Bead
types or an actor checklist. Optional context lookup or research runs only when it has a
bounded concrete question, relevant paths and constraints, a concise evidence-bearing
result, and useful delivery-owner work can continue independently. Give it a compact
fresh context without parent history. Under the Luna profile, a fresh Astra advisor may
also answer the explicit planning and unresolved-blocker cases in
[luna-coordination.md](references/luna-coordination.md), including a blocker that leaves
the delivery owner with no independent progress. It returns one terminal advisory
answer; do not keep a watchdog or monitoring session. Name any difficult lookup that
justifies escalation beyond Luna medium; use high for that escalation. A native generic
actor may instead use Luna max only for the same named difficulty and when its current
spawn surface advertises that exact model and effort. Astra xhigh likewise requires an
advertised native choice and remains limited to bounded decision support after lookup.
Validate the choice against the actual target surface instead of inferring ccore
support from native spawn metadata or native support from ccore. Never blanket-upgrade
reasoning for the delivery.

Honor the selected actor's effective configuration. In Codex, do not try to override a
hard-pinned custom agent at spawn time; choose a compatible generic actor or retain the
declared configuration with a reason. Optional delegation neither transfers logical
source ownership nor replaces TDD authorship, required foreign-family review,
acceptance, security or project-specific evidence.

## Implement members

`implementation-loop` is the member loop for one admitted issue. It is not the vehicle
for post-review Pack repairs; see Repair convergence below.

For each ordered issue, record delivery identity with `ccore delivery start`
before invoking implementation-loop. Start
the first fresh implementation session from the compact admission packet; later fresh
sessions start from the preceding compact committed handoff. Disable parent history
inheritance (`fork_turns="none"` where the native dispatch supports it). The same
logical implementation owner retains source, TDD, focused MoC and commit responsibility.
Within a large bead, rotate again after a clean committed handoff before the working
context stops being compact.

Use `ccore agent` for implementation dispatch when that transport is selected; a
native subagent is also valid. Both receive the same compact input and distinct-writer
constraints.

Dispatch a fresh Reviewer 1 context for every member. Give it the live issue, focused
evidence, and the member diff plus affected interactions identified by relevant paths
and evidence. Those paths are review starting points; the reviewer may inspect other
impacted code independently. Disable parent history inheritance for the reviewer. Send
accepted findings back to the logical implementation owner in its
current session, verify focused repairs, then advance without an immediate repeated
full review. Earlier member diffs remain covered by the final whole Pack review.

Only for a requested Sub-Pack shape: read
[subpack-progression.md](references/subpack-progression.md) and
[subpacks.md](references/subpacks.md), then call scripts/subpack_contract.py admit
before dispatch. Delegated Sub-Pack owners sequence, but do not implement, review,
finalize or invoke Session Close; distinct member actors and a parent repair owner
retain those boundaries.

## Review and complete

After the final member and repository gates, read
[final-review.md](references/final-review.md). It defines candidate-bound acceptance,
the preset-dependent Reviewer 2, security and project-specific perspectives, allowed
not-applicable evidence, finding triage and repair convergence. Call
scripts/pack_review_contract.py for its evidence seams and scripts/finding_triage.py
to partition late findings before any repair. Do not drop a perspective the preset
requires because this entry is shorter.

### Repair convergence is one cumulative bugfix phase

Accepted findings from the final Pack perspectives are closing repairs on one existing
candidate, never new Bead implementations. Start convergence bound to the current
logical owner, implementation session and committed candidate. Therefore:

- In normal serial execution, rotate once through the compact committed handoff to one
  fresh repair session (Sol with high reasoning for Codex) under the same logical owner.
  A Sub-Pack instead keeps its already-bound parent repair session.
- The current repair implementer receives **all** remaining accepted findings at once,
  in the one shared Pack worktree.
- It owns the whole cumulative repair diff, including any test its own fix needs, and
  its own focused verification. No separate `tdd-test-author`, no RED/GREEN slice
  choreography.
- Do not re-enter `implementation-loop` and do not replay the ordered member sequence.
  Further turns, if any, go to the same persistent repair session, again with every
  remaining finding at once.
- Only findings that `scripts/finding_triage.py` places in its `repair` set enter
  convergence: Medium or higher, inside the Pack diff, and bound to an admitted AC or
  the candidate's own behaviour. Everything it defers becomes a pull request comment
  or a follow-up work order, never a repair turn.
- One repair round is the default. Consume it with its matching `record_repair_round`;
  a second round needs a typed reason recorded by the delivery owner. Then rerun
  invalidated acceptance, run focused verification, and create exactly one closing
  repair commit.
- Authorize each dispatch with
  `pack_review_contract.authorize_repair_dispatch`; it refuses a replacement
  implementer and refuses a dispatch that carries only part of the remaining findings.
  Use `start_repair_convergence` and `record_repair_round` around it.

After clean final evidence and focused verification, write the pull request text with
the installed `cognovis-pr` skill: Summary, Evidence, Merge Danger and Known residuals,
title on line one, saved outside the worktree. Pass that file's content as the Session
Close `--summary`. Then invoke the installed
session-close skill exactly once in this session for all delivery issues and the parent worktree.
Use ccore session-close --help for the live interface and the landing-policy result
for authority. Never use a skill-bundled fallback when ccore is absent.

Resume only the returned Session Close ID. Internal review/repair records remain
caller-owned and are not a Session Close input. Do not duplicate CLI transitions.
The outer result is a concise blocker, review-pending handoff or terminal
result with canonical-main SHA and Session Close ID. Publication alone is not terminal
success; honor human merge authority and report any still-open review gate.
Cross-repository Topic scheduling and callbacks remain outside this skill.

## Usage evidence

Report observed development usage across the whole delivery, including implementation
repairs, as separate `uncached_input`, `cached_input`, and `output` values. When
transport telemetry does not expose one of those classes, report that value as
`unavailable`; do not estimate it. Do not add cached input to an already cache-inclusive
input total, and do not use usage reporting as a budget or approval gate.

For a measured Luna-profile pilot, also apply the comparison record in
[luna-coordination.md](references/luna-coordination.md). Record observed token classes
and repair outcomes without converting them into savings or causal claims.

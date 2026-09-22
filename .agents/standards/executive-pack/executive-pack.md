---
domain: executive-pack
description: Ownership and identity boundaries for simple bead delivery, repository-scoped Executive Packs, and cross-repository Topics.
---

# Executive Pack

> **Scope**: Loaded by planning, dispatch, and execution primitives that must agree on Bead, Pack, and Topic ownership without sharing delivery state across repositories.

## Execution Units

| Unit | Repository | Worktree | Session Close | Content |
|------|------------|----------|---------------|---------|
| Solo delivery | One | One | One | Exactly one Bead |
| Executive Pack | One | One parent integration worktree; optional isolated Sub-Pack worktrees | One | One or more ordered bead executions with preserved commits |
| Topic | One or more | None | None | Delivery DAG coordination and one content-level final acceptance |

A repository delivery owner owns admission, sequencing, review decisions, callbacks,
and Session Close. In the normal execution shape, one logical implementation owner
owns TDD, every source change, every repair, focused Means of Compliance, and each
bead-labelled commit. Fresh writing sessions may continue that ownership only through
a compact handoff at a clean committed candidate. In the optional Sub-Pack shape, each
isolated shard has a
delegated owner plus distinct implementer and reviewer contexts for every member; the
parent integration worktree has one distinct persistent repair session. Owners and
reviewers never implement or repair findings.

The delivery wrapper owns the parent integration worktree and Session Close. A one-bead
wrapper closes once after its one execution. The active Pack-owner session closes once
after every ordered bead execution, every admitted Sub-Pack integration, and the
pack-wide gates succeed. A Sub-Pack never closes independently.

## Pack Membership

- A pack has exactly one repository and cannot share any of its worktrees with another repository.
- Repository-local beads that depend on each other's work normally belong to the same pack.
- Every bead keeps its identity, Acceptance Criteria, Means of Compliance, and commit boundary.
- A Sub-Pack is a pack-internal execution shard, not a repository delivery. It has one
  disjoint ordered Bead chain, one isolated linked worktree, and one delegated owner
  that dispatches per-member implementer/reviewer loops. It owns no callback, aggregate review, outer result, or
  Session Close.
- A Topic node is an opaque Solo or Executive Pack repository delivery. Cross-repository relationships connect delivery IDs through explicit dependencies; repeated repositories remain distinct nodes.
- A downstream delivery receives a fresh worktree and surface only when ready, based on that repository's then-current canonical Main after upstream Session Close.

## Review Placement

Simple Solo and High-Assurance Solo are presets over the same prompt-owned repository
delivery contract. Simple, also called Light, is the default and uses one complete
Reviewer 1 pass. High Assurance adds a fresh different-family Reviewer 2 plus
applicable security and project perspectives. It is selected by an elevating
landing-policy review risk (payment, PII, auth, compliance), by the caller's role
paragraph, or by repository instructions, and the choice is frozen at admission.
Accepted repairs return to the same implementation owner and proceed after focused
verification without an immediate full repair-confirmation review.

An Executive Pack normally runs Beads serially in one worktree. After each member, a
fresh Reviewer 1 context inspects that member's diff plus affected interactions, using
the live contract, relevant paths, and focused evidence. Accepted findings return to
the logical implementation owner in its current writing session. The final Pack review
examines the whole Pack base-to-candidate change and preserves aggregate coverage.

## Optional Sub-Pack Execution

Sub-Packs allow at least two independent Bead chains in the same Executive Pack to run
concurrently from one frozen reviewed parent base. The parent Pack owner remains the
only delivery owner. Each Sub-Pack owner is dispatched through `ccore agent` or a native
harness subagent, runs its chain serially, and delegates each member to distinct
implementer and internal reviewer contexts. Repairs return to the original member
implementer. The root owner does not implement or review shard source.

Sub-Pack topology and progression are deterministic invariants. The Pack owner calls
`uv run python skills/executive-pack/scripts/subpack_contract.py`; prose interpretation
does not admit or advance a Sub-Pack wave. The contract requires a complete disjoint
partition of the Pack Beads, live dependency order derived from `bd show`, no
cross-Sub-Pack dependency edge, no declared write-set overlap, unique worktrees and
owner/implementer/reviewer sessions, one frozen base, and one integration order.
Declared paths are normalized at admission; the actual candidate diff and shard
worktree HEAD are checked at completion.

Completed Sub-Packs may finish in any order but integrate only in the declared order.
Before each merge, the same Sub-Pack-owner session reconciles its branch with the current
parent candidate, returning source repairs to the original member implementer. The parent integration
worktree then receives that reconciled branch, runs repository gates, and records the
new parent candidate. A stale parent SHA, replacement owner or actor session, missing
completion evidence, missing reconciliation verification, or missing post-merge gate
evidence cannot advance the contract.

The parent-integration repair session owns cross-shard, post-merge, and final-review
repairs. A clean fully integrated Sub-Pack worktree may be retired; a dirty worktree is
never removed. A focused gate follows every integration and one full repository gate
follows the wave. Final Pack perspectives begin only after that full gate.
Any later aggregate-review source repair runs in the bound parent repair session,
supersedes the prior gate, reopens the wave, and requires a new full gate.
They inspect the complete parent candidate across the whole cohort, then exactly one
Session Close receives every Pack Bead and the parent integration worktree.

## Final Pack Review

After all Bead commits and repository gates, the active Pack-owner session runs only the evidence
providers made applicable by the Pack. Current implementation and documentation complete first.
The delivery owner then captures live claims and the signed resource registry, then runs
`ccore acceptance run`.

Any user-observable claim makes `agentic_acceptance` applicable. A fresh independent
`uat-validator` operates the resolved signed browser, CLI, PTY-TUI, API, and artifact
resources through their real user interfaces. Browser interaction uses the bounded
interactive `playwright-cli` wrapper, never authored Playwright tests. Default
transport is `codex-cli`. Use the `acpx` transport only with an explicit project
`.acpxrc.json`. Failed, unavailable, incomplete, stale, or challenged acceptance
blocks aggregate review. Not-applicable is valid only when every admitted claim is
non-executable.

Agentic acceptance retains its caller-owned trust material independently of the evidence: one
authority id, a registry HMAC key, and a dispatch-attestation HMAC key. The first binds
the resolved candidate registry and current documentation; the second binds the exact
authenticated transport route, session, terminal event stream, request, report, and receipt. The
repository delivery owner retains only the authority and key digests. Implementer-supplied trust material,
unsigned documentation, or a structurally plausible but unattested receipt cannot admit
aggregate review.

STATUS: This is a deterministic workflow-integrity boundary between the Pack owner and
its isolated actors, not a security boundary against the same machine owner. A process
that can read the caller's trust environment or rewrite contract code and state can
forge local evidence. The keys prevent ordinary implementer-authored evidence from
being accepted as caller-attested evidence; they do not make a compromised host trusted.

Acceptance evidence binds complete claim coverage, actions, observations, artifacts,
candidate and resource provenance, validator identity, and attempt. Repairs invalidate
both documentation and acceptance. The repository delivery owner records newly signed
current documentation, then runs fresh `ccore acceptance run` for the repaired candidate
before final perspectives continue. One candidate permits no more than three product
outcomes; recorded route and infrastructure failures reuse the same product-attempt
ordinal. Security-focus and documentation checks remain read-only evidence providers;
they never repair source.

After acceptance, final review is agentic and perspective-based. Under the Light
preset it is one fresh whole-Pack Reviewer 1 pass plus applicable project-specific
perspectives; under High Assurance it is one complete different-family adversarial
review, one security review, and every applicable project-specific perspective. Each
produces distinct evidence. Accepted findings pass through deterministic triage
(Medium or higher, inside the Pack diff, bound to an admitted AC or the candidate's
behaviour) before one implementation-owned repair lineage; its current session can
rotate only through a validated compact committed handoff. One repair round is the
default; deferred findings become pull request comments or follow-up work orders.
`passed` is a completion outcome with no accepted substantive finding;
`changes_requested` carries accepted Medium-or-higher findings into that repair loop.

Clean consistent evidence bypasses adjudication. A disputed finding, contradictory
recommendation, suspicious summary, or intent mismatch interrupts progression and
returns a typed disposition to the repository delivery owner. Missing providers,
incomplete answers, or non-passing evidence never become approval.

The outer boundary exposes only decision-bearing preflight questions, genuine blockers,
or terminal repository evidence containing canonical-main and Session Close identity.
Reviewer answers, findings, and repair transitions remain private delivery state.

## Session Temperature

The active repository delivery owner remains persistent for the complete delivery. In
the normal shape, one logical implementation owner remains responsible while fresh
sessions take over between members or within a large bead through compact committed
handoffs. In the Sub-Pack shape, one implementation session remains hot per
shard through member review and parent reconciliation, while one parent-integration
repair session remains hot for cross-shard and final repairs. Each member gets a fresh
bounded Reviewer 1 context; final perspectives are fresh, distinct, and cover the whole
Pack. A separate
Pack never reuses these worktrees or delivery sessions.

## Human Boundary

The human chooses the execution path. Direct Solo or Executive Pack delivery does not require a Topic. Development token usage is not a preflight decision, and the gate must never ask the human to set or approve a development token budget. Parallelize may propose packs but cannot launch, claim, mutate, or close work. A Topic consumes one human-approved delivery DAG and forwards each node's prompt additions unchanged.

Only decision-bearing ambiguity interrupts preflight or review. Routine clean
progression does not ask for token budgets, repair counts, or confirmation rounds.
Internal compact handoffs are routine progression and require no human approval.

Observed usage reports separate uncached input, cached input, and output when the
transport exposes them. Missing classes are reported as unavailable, without estimates.
Cached input is never added to a total that already includes it.

## Finalization

Repository-delivery completion means canonical Main is merged and pushed, Bead state is closed, and exactly one Session Close has finished. Allocation binds one safe worker surface, coordinator surface, and unique callback identity to the running delivery. The repository runner uses those bindings with the Topic manifest path and `ccore topic record-event` to persist a typed terminal event. If optional cmux dispatch is present, it may additionally send an attention-only wake to the coordinator surface. The Topic then independently reconciles those three facts; process exit, flash, wake text, and scrollback are never authoritative. Blocked and failed callbacks remain explicit terminal delivery states. The pure-state manifest rejects known stale same-repository dependency bases, while the coordinator remains responsible for resolving live canonical Main and Git provenance immediately before allocation. After every node lands, exactly one Topic Finalize evaluates cross-repository contracts, integration, UAT, release, and documentation. A failure recommends a new focused repair delivery; it never reopens a closed worktree, reruns Finalize inside that Topic, or rewrites landed history.

## Later Revalidation

Delivered capability documentation states what users can do and gives repeatable
user-facing guidance. A later human or economical agent may use those claims to inspect a
new candidate through the same resource registry. That later run is new candidate-bound
evidence; previous evidence is never reused across candidate or documentation changes.

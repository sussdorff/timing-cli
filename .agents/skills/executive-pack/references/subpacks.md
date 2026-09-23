# Internal Sub-Packs

Use Sub-Packs when one repository-scoped Executive Pack contains at least two
dependency-safe, write-disjoint Bead chains that can execute concurrently. A Sub-Pack
is a pack-internal execution shard with its own linked worktree and delegated owner. It
behaves like a small execution pack through its member implementation, review, and
repair loops, but it never runs aggregate Pack reviews or Session Close.

## Ownership

The root Pack owner admits and dispatches the wave, receives completed candidates,
reconciles them in declared order, merges them into the parent integration worktree,
runs integration gates, and owns aggregate Pack review and the single Session Close.
Any parent-worktree source repair is delegated to the separately bound persistent parent
repair session; the root owner never performs it.

Each Sub-Pack owner operates only its assigned worktree. For every member Bead it must
delegate implementation and review to distinct contexts through `ccore agent` or native
harness subagents. The owner may not implement, review, or repair source itself.
Accepted repairs return to that Bead's original implementation session. This fixed
receipt binding is a scoped exception to normal serial compact session handoff; actor
loss uses the typed failure or serial fallback path rather than rebinding. The internal
reviewer remains distinct from both owner and implementer. Each member review still
starts in a fresh bounded context with its member diff plus affected interactions. A
Sub-Pack returns only after
every member loop ends in `accepted` and its cumulative candidate is clean. Actual
transport session IDs must be distinct across owner, implementers, and reviewers.

## Admission

Call:

```text
uv run python "$SKILL_ROOT/scripts/subpack_contract.py" admit \
  --plan-file <plan.json> \
  --state-file <state.json> \
  --bead-repo <repository>
```

The plan supplies Pack identity, repository, parent worktree and session binding, base
SHA, complete ordered Bead IDs, integration order, a distinct parent repair binding,
and two or more Sub-Packs. Each
Sub-Pack supplies its owner binding, linked worktree, ordered members,
`declared_write_sets` by Bead, and `member_actor_bindings` containing one implementer
and one reviewer binding per Bead. A binding declares `transport` as `ccore_agent` or
`native_subagent`, plus session name, adapter, and worktree cwd. `ccore_acpx` remains
a valid alias for existing plans.

The caller must not supply `bead_dependencies`. Admission calls
`ccore tracker show <ref>` when the registry entry declares a tracker, or
`bd show <id> --json` for the Beads archive,
itself, follows blocking dependencies, stores the repository-local snapshot and its
digest, rejects unresolved external dependencies, cross-shard dependencies, dependency
order violations, unlinked or repeated worktrees, repeated actor sessions, and declared
write-set overlap. Patterns are normalized, repository-relative, and conservatively
case-folded. Completion checks the actual base-to-candidate diff against the declared
union and requires the candidate to equal the linked shard worktree HEAD. Context
Pointer overlap is recorded only as
`heuristic_admission_signal_only`; it is useful evidence but not a complete write-set
proof. `context_pointer_analysis` distinguishes an empty parsed section from a Bead
whose `## Context Pointers` section could not be analyzed.

## Member loops and completion

For each Bead, completion records one or more ordered rounds. Every round contains an
implementation receipt, a reviewer receipt, observed intervals, and a verdict of
`repair_required` or `accepted`. All repairs must use the original actual implementer
session, all reviews remain in the original reviewer session, and only the final round
may be accepted. The Sub-Pack owner also supplies its own receipt, the real candidate
SHA, and one real commit per member:

```text
subpack_contract.py complete --state-file <state.json> --subpack-id <id> \
  --owner-session-receipt-file <owner.json> --candidate-sha <sha> \
  --bead-commits-file <commits.json> --member-loops-file <loops.json> \
  --implementation-interval-file <interval.json>
```

Receipts bind a session name and cwd to a content-digested transport artifact. `ccore
agent` receipts consume `cognovis.agent-evidence.v1`. Compatibility ACPX receipts still
consume `cognovis.acpx-transport-evidence.v1`. Native subagent receipts consume
`executive_subpack_native_subagent_evidence_v1` with completed status, cwd, session ID,
and answer digest. Every receipt also binds the transition candidate SHA, and one
transport artifact may authorize exactly one recorded transition.

STATUS: ACPX evidence independently exposes the actual transport session ID and answer
digest. Native harnesses currently have no common signed receipt API; their native
evidence artifact is caller-produced and therefore detects malformed or inconsistent
state, not a dishonest caller. Worktree cwd in ACPX is likewise bound by the caller-owned
receipt because the current transport evidence does not expose cwd.

## Reconciliation and integration

Only the next declared Sub-Pack may reconcile. Reconciliation returns to the same
actual Sub-Pack-owner session, incorporates the current parent candidate into the shard
candidate, records content-digested verification evidence and conflict files, and proves
both Git ancestries. It then returns control to the root owner:

```text
subpack_contract.py reconcile ...
subpack_contract.py integrate ...
```

Integration occurs only in the persistent root-owner session and carries a receipt for
the distinct persistent parent repair actor. The merged parent must
descend from both the previous parent and reconciled shard candidates. Run a focused
integration gate after each merge. After every shard is integrated, run one full
repository gate in the same root-owner session and record it with `final-gate`; only then can
`ready_for_final_review` become true. Aggregate Pack review still examines the complete
parent candidate across the whole cohort.

## Failure and measurement

`fail`, `abort`, and `fallback-serial` are explicit transitions. Serial fallback keeps
already integrated Sub-Packs, uses the current parent SHA as its base, and emits the
exact remaining Bead IDs. No state file deletion is required.

An aggregate-review repair uses `parent-repair`: it binds the descendant candidate to
the persistent parent repair session, supersedes the prior full gate, reopens the wave,
and requires another `final-gate`. Abort and serial fallback remain available from
review-ready state. Failed, aborted, and fallback states cannot overwrite one another.

STATUS: Reconciliation deliberately requires the original actual Sub-Pack-owner
session. If it is lost, use typed failure and serial fallback; there is no unaudited
owner rebind. Keep each owner session available until its declared integration turn.

The state reports observed implementation total, union, and overlap seconds, combined
review/reconciliation/gate seconds, and conflict-file count. These values show whether
parallel overlap occurred in this wave. They are observations, not a predictive speed
claim; migrations and other implementation-heavy packs can produce materially different
ratios from small packs.

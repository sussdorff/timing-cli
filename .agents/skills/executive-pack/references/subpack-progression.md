### Optional Sub-Packs

A Sub-Pack is a pack-internal execution pack with a delegated owner and isolated
worktree, not a nested repository delivery. It owns no delivery callback, aggregate
Pack review, Session Close, or outer result. Use Sub-Packs
only when the admitted issues form at least two disjoint dependency-safe chains from one
frozen reviewed parent base. Cross-Sub-Pack issue dependencies make that parallel wave
invalid; keep the dependency chain in one Sub-Pack or use the normal serial shape.
Read [subpacks.md](subpacks.md) before admitting this shape.

After `uv run python "$SKILL_ROOT/scripts/subpack_contract.py" admit` succeeds,
run the admitted Sub-Packs concurrently.
The root owner dispatches each Sub-Pack owner through `ccore agent` or a native subagent;
it does not implement or review in the shard worktree. The delegated owner runs issues
serially. For each member it calls `ccore delivery start` and only then
dispatches a distinct implementer and internal reviewer. Repairs return to the same
implementer, and the Sub-Pack returns only after all loops end in `accepted`. Record
receipts, commits, and intervals with `uv run python
"$SKILL_ROOT/scripts/subpack_contract.py" complete`.

Integrate completed Sub-Packs only in the declared order:

1. Send the current parent candidate to the same Sub-Pack-owner session. It returns any
   source repair to the original member implementer and produces a verified reconciled
   candidate in its isolated worktree. Record this with
   `uv run python "$SKILL_ROOT/scripts/subpack_contract.py" reconcile`; a
   replacement owner session or stale parent SHA is refused.
2. Merge the reconciled shard into the parent integration worktree. The parent-integration
   repair session owns any cross-shard or post-merge source repair and supplies its
   receipt to `integrate`. Run the repository
   focused integration gates after the merge and record the new parent SHA and evidence with
   `uv run python "$SKILL_ROOT/scripts/subpack_contract.py" integrate`.
3. Retire only clean, fully integrated Sub-Pack worktrees. Never remove a worktree with
   uncommitted changes. The final candidate and all later repairs stay in the parent
   integration worktree.

After all integrations, record one full repository gate with `final-gate` from the
persistent parent-owner session. Aggregate-review fixes use `parent-repair`, which
delegates to the parent repair actor, supersedes the gate, and requires re-gating. Do not begin
final Pack perspectives until the contract reports
`ready_for_final_review: true`.

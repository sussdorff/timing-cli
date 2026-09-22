# Parallel Orchestration

Rules for running several implementation agents concurrently on related work.

| Rule | Detail |
| --- | --- |
| Dependency-ordered spawning | For an epic where A and B are independent and C depends on both: A and B run in parallel, both merge to main, then C spawns. Spawning C early leaves it on a stale base without A's and B's outputs. |
| Stale-base reconciliation is planned, not discovered | When parallel agents implement interdependent modules, the dependent agent works from a stale worktree base and produces incompatible APIs. A manual reconciliation pass after all agents complete is part of the plan. |
| Shared files are briefed explicitly | Each agent is told which shared files already exist on main and must not be recreated from scratch; otherwise every agent writes its own version. |
| Later branches rebase before merge | After parallel agents commit to their branches, later branches rebase onto main to pick up earlier agents' commits. A bare merge without rebase produces divergent file versions. |
| Shared interface files are audited at reconciliation | A parallel agent that touched a shared interface file (types, adapter base classes) may carry stale type imports that break after another agent's renames. Reconciliation includes an explicit audit of shared interface files. |
| The better design wins over the earlier design | When a later agent produces a pragmatically superior API design, the later design is preferred and the earlier work discarded — merging conflicting paradigms costs more than redoing the smaller part. |

# Judge Layer

> Pre-action authorization and authoring-time decision contracts for the agent
> stack. Read this file before reading the individual contract pages.

## What This Is

The judge layer is the **judgment slot** in Nate Jones's managed-worker model.
It is the system that decides whether a proposed side effect is allowed to
execute, before the actor runs it. It is distinct from:

- **Orchestration** (who does the work) — `bead-orchestrator`
- **Coordination** (how work moves) — beads / bd
- **Continuity** (what is remembered) — OpenBrain
- **Post-action review** — `review-agent` reviews committed code;
  `verification-agent` verifies completion claims; both run *after* work has
  happened. The judge layer runs *before*.

See `library/meta/docs/managed-worker-stack.md` for the full slot model and
`cognovis-core/docs/adr/ADR-0003-judge-layer-architecture.md` for the
architectural decisions behind these contracts.

## Contract Pages

These pages define everything a judge needs to consume and produce, everything
a side-effecting actor needs to declare and submit, and the authoring-time
decision controls used before human escalation.

| Contract | Purpose | Read this when |
|----------|---------|----------------|
| [`action-proposal.md`](action-proposal.md) | Structured object the actor submits before a side effect | Designing a skill that produces side effects; integrating with the judge layer |
| [`judge-outcomes.md`](judge-outcomes.md) | ALLOW / BLOCK / REVISE / ESCALATE decision shape, composition precedence, required output fields | Building a judge agent; parsing judge output in an orchestrator |
| [`provenance-labels.md`](provenance-labels.md) | Six-label evidence system (`observed`, `inferred`, `generated`, `confirmed`, `disputed`, `superseded`), transition rules | Tagging evidence references in proposals, mandates, or memory writes |
| [`mandate-schema.md`](mandate-schema.md) | AP2-style authorization-as-evidence record (scope, limits, evidence, granted_at, expires_at, supersedes) | Representing user authorization that needs to travel with the proposal |
| [`decision-brief.md`](decision-brief.md) | Compact manager view plus evidence appendix for human operational decisions | Presenting a manager-decidable gate without asking the manager to audit code |
| [`decision-gate.md`](decision-gate.md) | `## Human Decision Gate` authoring contract mapped to judge outcomes | Authoring a human decision point in a bead |
| [`stop-taxonomy.md`](stop-taxonomy.md) | Stop vocabulary and operational-risk rules crosswalked to ADR-0003 | Deciding when delivery pressure, risk, evidence, or authority requires a stop |
| [`judge-eval-suite.md`](judge-eval-suite.md) | Eval discipline: ≥20 cases, all four outcomes, ≥4 ALLOW cases, nine required metrics | Shipping a new judge agent; auditing an existing one |

## The Deterministic-First / Reasoned-Second Pattern

A judge does not have to be an LLM call. Many policy decisions are fully
deterministic (schema validation, missing-field detection, expired-mandate
check, secret/credential prohibition). The reference implementation runs
deterministic gates first as Python rules, then optionally invokes a
model-reasoned gate only on proposals that pass deterministic ALLOW.

```
Action Proposal
      |
      v
+-----------------+
| Schema parse    |  fail -> ESCALATE schema
+-----------------+
      | pass
      v
+----------------------+
| Deterministic gates  |  BLOCK/REVISE/ESCALATE -> return
+----------------------+
      | ALLOW
      v
+----------------------+
| Reasoned gate (opt)  |  ALLOW/BLOCK/REVISE/ESCALATE
+----------------------+
      |
      v
   Outcome
```

Benefits:
- **Cost** — most proposals never reach the model. Bad ones get caught by
  deterministic rules.
- **Auditability** — most rejections are auditable as code with line numbers,
  not as model prose.
- **Failure surface** — schema violations and bright-line prohibitions
  (`secret`, `credential`) cannot be reasoned around.

The pattern is implemented in `open-brain/python/src/open_brain/
memory_write_judge.py`. The cognovis-core `judge-default` agent is the
model-reasoned half of the same pattern.

## How a Side-Effecting Skill Wires Into the Judge Layer

Three steps:

1. **Declare `action_boundary` in frontmatter.** See `meta/docs/PRIMITIVES.md`
   §1 (Skill) and §3 (Agent). The block names which proposal schema, which
   judge, and which `risk_class` / `effect_type` the skill operates under.
2. **Produce an Action Proposal** at runtime, before the side effect.
   Validate with `standards/judge-layer/scripts/validate_action_proposal.py`
   if running outside an orchestrator that does it automatically.
3. **Wait for the judge outcome** before executing. Honor the composition
   precedence (`BLOCK > ESCALATE > REVISE > ALLOW`). For REVISE, apply the
   `revised_proposal` and submit once more.

The repository delivery owner handles steps 2 and 3 for any skill declaring
`action_boundary` with `risk_class: external-side-effect` or `high-risk`. See
the `action_boundary` block in `cognovis-core/skills/implementation-loop/SKILL.md`
for a declaring skill.

## How a Judge Agent Wires Into the Judge Layer

Three steps:

1. **`requires_standards: [judge-layer]`** in frontmatter, plus narrow
   read-only tools (`Read, Grep`).
2. **Consume an Action Proposal**, produce an outcome matching
   `judge-outcomes.md` exactly: `decision`, `reason`, `reason_category`,
   `provenance_refs`, optional `policy_version`, plus conditional
   `constraints` (ALLOW) / `revised_proposal` (REVISE) /
   `escalation_target` (ESCALATE).
3. **Ship a paired eval suite** of at least 20 cases. `skill-forge` audit mode
   treats a judge without a paired suite as a blocking quality finding. See
   `cognovis-core/skills/judge-eval/SKILL.md` for the runner.

The reference judge is `cognovis-core/agents/judge-default.md`. The default
eval suite is `cognovis-core/skills/judge-eval/assets/judge-default-cases.yml`.

## Specialist Judges

Start with the generic `judge-default`. Split into specialists only when the
prompt becomes unreasoned. Likely first specialists per Nate's May 11 article:

- `authorization-judge` — does the user/mandate authorize this class of action
- `privacy-judge` — what data is exposed and to whom
- `reversibility-judge` — can the action be undone; what is rollback
- `quality-judge` — domain-specific output quality bar
- `security-judge` — touches secrets, permissions, production, sensitive infra

Specialist judges inherit the same Action Proposal schema, outcome set,
provenance labels, and mandate rules. Composition (when multiple judges run on
the same proposal): combine via the same `BLOCK > ESCALATE > REVISE > ALLOW`
precedence.

## Consumer-Side Examples

| Consumer | Repo path | What it judges |
|----------|-----------|----------------|
| Memory-Write Judge | `open-brain/python/src/open_brain/memory_write_judge.py` | OpenBrain `save_memory` calls with structured 7-field proposals |
| Pre-action gate | `cognovis-core/skills/implementation-loop/SKILL.md` §`action_boundary` | Any side-effecting skill invoked during a repository delivery |
| (Future) Action-Proposal CLI | `cognovis-core/standards/judge-layer/scripts/validate_action_proposal.py` is the deterministic validator; downstream consumers wire it into their orchestrator path |

## What This Layer Is Not

- **Not a post-action reviewer.** Use `review-agent` for committed code review;
  `verification-agent` for completion-claim verification.
- **Not a hook or guardrail.** Hooks fire unconditionally based on
  deterministic rules with no model reasoning. The deterministic portion of
  the judge layer can run as a hook-equivalent; the reasoned portion cannot.
  When the entire policy is deterministic, use a hook directly.
- **Not a permission system.** Permission systems answer "is this user
  allowed to call this API." The judge layer answers "is this *specific
  proposed action*, with this evidence, in this scope, against this mandate,
  authorized." It reasons about intent, not access.
- **Not a replacement for human review.** ESCALATE outcomes route to human
  review. The judge layer reduces the volume of decisions humans must make; it
  does not eliminate it.

## Open Items

- Composition logic for multi-judge dispatch is described above as
  `BLOCK > ESCALATE > REVISE > ALLOW` but no orchestrator currently runs
  multiple specialist judges in parallel. The composition rule is documented
  for when specialist judges land.
- Read-time Retrieval Contract (`open-brain-ekn.4`) is the continuity-slot
  counterpart to the write-time judge: a seven-question contract for retrieving
  task-shaped context bundles. Owned by `open-brain`, not this layer, but tied
  by the same provenance vocabulary.

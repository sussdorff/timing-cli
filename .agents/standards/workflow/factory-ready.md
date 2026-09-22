# Factory-Ready Standard: Spec Quality Gate for Autonomous Execution

## What "Factory-Ready" Means

A bead is **factory-ready** when its specification contains enough information for an agent to execute autonomously without requiring interactive clarification. This gate is about spec quality, before implementation — not about implementation quality, which the bead's Means of Compliance covers afterwards.

```
Spec quality   (factory-ready gate)  <-  THIS STANDARD
Authoring      (/intake)
Implementation (bead implementation loop)
Verification   (Means of Compliance discharged, tests green)
```

Factory-ready answers the question: *"Can an agent start this bead and finish it without getting stuck on unresolved questions?"*

## The Six Criteria

### Criterion 1: Clear Intent (Description Quality)

Machine-readable contract: `standards/workflow/bead-hygiene.md ## Pflichtfelder`

**Pass**: Description contains a clear problem statement or goal. Someone unfamiliar with the context can understand what needs to happen.

**Fail**: Description is empty, one word, a placeholder ("TBD", "See ticket"), or so vague that multiple interpretations are possible.

```bash
bd show <id> --json | jq -r '.[0].description'
```

Signals of failure: empty string, fewer than 20 words for a feature, no mention of what changes.

### Criterion 2: Outcome-Focused Acceptance Criteria

Machine-readable contract: `standards/workflow/bead-hygiene.md ## Pflichtfelder`

**Pass**: At least one AC exists. Each AC describes an observable outcome ("User can do X", "System returns Y when Z"), not an implementation step ("Write a function that…").

**Fail**: No ACs present, or all ACs describe implementation tasks rather than observable outcomes.

```bash
bd show <id> --json | jq -r '.[0].acceptance_criteria'
```

Signals of failure: empty ACs, ACs starting with "Implement…" / "Write…" / "Add code to…" instead of describing observable behavior.

### Criterion 3: Means of Compliance (MoC) Table

Machine-readable contract: `standards/workflow/bead-hygiene.md ## Pflichtfelder`

**Pass**: Description or ACs contain a MoC table specifying how each acceptance criterion will be verified (`unit`, `e2e`, `integ`, `review`, `demo`, `doc`).

**Fail**: No MoC table. Agent cannot determine whether an AC requires a test, a code review, or a manual demo.

```bash
bd show <id> --json | jq -r '.[0].description' | grep -i "MoC\|Means of Compliance\|verification"
```

MoC table format (example):
```markdown
| # | Criterion | MoC | Notes |
|---|-----------|-----|-------|
| 1 | Feature works end-to-end | e2e | playwright spec |
| 2 | Error handling correct | unit | jest test |
| 3 | Documented in README | doc | README section |
```

### Criterion 4: NLSpec / Design Populated (for features and epics)

Machine-readable contract: `standards/workflow/bead-hygiene.md ## Pflichtfelder`

**Pass** (for features/epics): `intent` metadata is populated and describes the behavioral goal, scope-in, and scope-out. `contracts` metadata populated if the feature has public interfaces.

**Pass** (for tasks/bugs): Not required. Skip this criterion.

**Fail** (for features/epics): `intent` is null or empty; design questions are unresolved; no scope boundaries defined.

```bash
bd show <id> --json | jq -r '.[0].metadata.intent'
bd show <id> --json | jq -r '.[0].metadata.contracts'
bd show <id> --json | jq -r '.[0].type'
```

### Criterion 5: Sizing Validated (Single Concern, Single Platform)

Machine-readable contract: `standards/workflow/bead-hygiene.md ## Pflichtfelder`

**Pass**: Bead addresses a single concern (one feature, one fix, one refactor). Can be implemented by one agent in one session (typically ≤1 day effort).

**Fail**: Bead mixes concerns ("refactor X AND add feature Y"), spans multiple platforms without clear separation, or effort is "epic-level" (many weeks).

```bash
bd show <id> --json | jq -r '.[0].metadata.effort'
bd show <id> --json | jq -r '.[0].type'
```

Signals of failure: effort > 5, epic type with no child beads, description describes multiple unrelated features.

### Criterion 6: Dependencies Resolved (No Active Blockers)

**Pass**: No open blockers. All prerequisite beads are closed or the bead explicitly handles the dependency.

**Fail**: Active blockers exist. Agent will hit dependency walls mid-execution.

```bash
bd show <id> --json | jq -r '.[0].blocked_by'
bd blocked | grep <id>
```

Also check: `bd ready` output — `bd ready` already surfaces this as a readiness signal.

## Scoring Table: Required vs Optional per Bead Type

| Criterion | feature | epic | task | bug | chore |
|-----------|---------|------|------|-----|-------|
| 1. Clear intent in description | required | required | required | required | optional |
| 2. Outcome-focused ACs | required | required | required | required | optional |
| 3. MoC table | required | required | recommended | recommended | — |
| 4. NLSpec intent/contracts | required | required | optional | — | — |
| 5. Sizing validated | required | required | required | required | optional |
| 6. Dependencies resolved | required | required | required | required | required |

**Minimum to be factory-ready**:
- All "required" criteria for the bead type must pass
- "recommended" criteria: warn but don't block
- "optional" criteria: not checked

## Factory-Ready vs Needs Interactive Work

| Condition | Classification | Action |
|-----------|---------------|--------|
| All required criteria pass | FACTORY READY | `cld -b <id>` |
| Missing MoC table (task/bug) | FACTORY READY with warning | Proceed; agent will skip MoC gate |
| Vague description (fixable) | NEEDS INTERACTIVE WORK | Run `/intake <id>` to resolve |
| No ACs | NEEDS INTERACTIVE WORK | Add ACs, re-check |
| Feature missing NLSpec intent | NEEDS INTERACTIVE WORK | Run `/intake <id>` — authoring adds NLSpec |
| Active blockers | BLOCKED | Resolve blockers first |
| Oversized bead | NEEDS SLICING | `bd slice <id>` or epic init |

## Quick-Check Procedure

Manual assessment of a bead (also automated by `/bead-reviewer`):

```bash
# 1. Get bead data
bd show <id>

# 2. Check description length and clarity
bd show <id> --json | jq -r '.[0].description' | wc -w

# 3. Count acceptance criteria
bd show <id> --json | jq '.[0].acceptance_criteria | length'

# 4. Check for MoC table (look for pipe table in description)
bd show <id> --json | jq -r '.[0].description' | grep -c "|"

# 5. Check NLSpec (for features/epics)
bd show <id> --json | jq '{type: .[0].type, intent: .[0].metadata.intent, contracts: .[0].metadata.contracts}'

# 6. Check blockers
bd show <id> --json | jq '.[0].blocked_by'
```

## Project Overlay Convention (Pass 3)

Projects can extend the factory-ready check with project-specific bead hygiene rules by placing an overlay file at:

```
$REPO_ROOT/.agents/standards/bead-hygiene.md
```

When this file is present, `/bead-reviewer` loads it as **Pass 3** after the standard Pass 1 (structural) and Pass 2 (semantic) evaluations. Pass 3 rules can flag Critical findings that override the verdict to NEEDS INTERACTIVE WORK, or lower-severity findings that appear as warnings.

The overlay file supports two rule sections:
- `## Pflichtfelder` — required fields or elements that every bead must include
- `## Anti-Patterns` — prohibited patterns a bead must not exhibit

Each rule defaults to Critical severity. Override with `<!-- severity: major|minor -->` prefix.

If the file is absent, Pass 3 is silently skipped with no effect on the verdict.

Full specification: `standards/workflow/bead-hygiene.md`

## Relationship to Other Standards

- **bead-spec.md**: Defines the NLSpec metadata keys (`intent`, `contracts`, `constraints`) used by Criterion 4
- **verification-discipline.md**: Discharging a bead's Means of Compliance after implementation — separate from factory-ready, which gates the spec before it
- **workplan.md**: Uses autonomy scoring that aligns with factory-ready criteria
- `/bead-reviewer`: Automated command that evaluates all 6 criteria for a bead
- **bead-hygiene.md**: Project overlay convention — project-specific rules applied as Pass 3

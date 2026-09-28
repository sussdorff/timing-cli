# Factory-Ready Standard: Spec Quality Gate for Autonomous Execution

## What "Factory-Ready" Means

A hosted issue is **factory-ready** when its body contains enough information for an agent to execute autonomously without requiring interactive clarification. This gate is about spec quality, before implementation — not about implementation quality, which the issue's Means of Compliance covers afterwards.

```
Spec quality   (factory-ready gate)  <-  THIS STANDARD
Authoring      (/intake)
Implementation (implementation loop)
Verification   (Means of Compliance discharged, tests green)
```

Factory-ready answers the question: *"Can an agent start this issue and finish it without getting stuck on unresolved questions?"*

The deterministic part of this gate is the intake skill's author check. It reads the issue body the way `ccore tracker` parses it and applies the resolved `workflow/issue-intake` contract:

```bash
# A drafted body, before ccore tracker create/update
uv run python "$INTAKE_ROOT/scripts/issue-author-check.py" --body-file <file> --repo-root <repo>

# An existing hosted issue, read through ccore tracker show
uv run python "$INTAKE_ROOT/scripts/issue-author-check.py" --issue <owner/repo#N> --repo-root <repo>
```

`$INTAKE_ROOT` is the installed intake skill root (project-local first, then global). Exit 0 means `FACTORY_READY` or `FACTORY_READY_WITH_WARNINGS`; exit 2 means a critical finding blocks the issue. The criteria below explain what the check and a reviewer look for.

## The Six Criteria

### Criterion 1: Clear Intent

Machine-readable contract: `standards/workflow/issue-intake.md ## Pflichtfelder` (`BASE-CLEAR-INTENT`, `BASE-INTENT-BLOCK`, `BASE-GOAL-TITLE`)

**Pass**: The body has an `## Intent` section with exactly one column-0 `Goal:` line that states the outcome. The Goal is the issue title. Someone unfamiliar with the context can understand what needs to happen.

**Fail**: No Goal, a repeated Goal, an H1 that differs from the Goal, a placeholder ("TBD", "See ticket"), or an intent so vague that multiple interpretations are possible.

```bash
ccore tracker show <owner/repo#N> | jq -r '.data.title, .data.body'
```

### Criterion 2: Outcome-Focused Acceptance Criteria

Machine-readable contract: `standards/workflow/issue-intake.md ## Pflichtfelder` (`BASE-OUTCOME-AC`)

**Pass**: `## Acceptance Criteria` lists at least one criterion. Each describes an observable outcome ("User can do X", "System returns Y when Z"), not an implementation step ("Write a function that…").

**Fail**: No criteria, or all criteria describe implementation tasks rather than observable outcomes.

Signals of failure: an empty section, criteria starting with "Implement…" / "Write…" / "Add code to…" instead of describing observable behavior.

### Criterion 3: Means of Compliance (MoC) Table

Machine-readable contract: `standards/workflow/issue-intake.md ## Pflichtfelder` (`BASE-MOC`)

**Pass**: `## Means of Compliance` contains one table row per acceptance criterion specifying how it is verified (`unit`, `e2e`, `integ`, `review`, `demo`, `doc`) and concrete evidence.

**Fail**: No MoC table. An agent cannot determine whether a criterion requires a test, a code review, or a manual demo.

MoC table format (example):
```markdown
| AC | Criterion | MoC | Evidence |
|----|-----------|-----|----------|
| AC1 | Feature works end-to-end | e2e | tests/e2e/export.spec.ts |
| AC2 | Error handling correct | unit | tests/unit/test_export_errors.py |
| AC3 | Documented in README | doc | README.md#export |
```

### Criterion 4: Classification and Scope

Machine-readable contract: `standards/workflow/issue-intake.md ## Pflichtfelder` (`BASE-TYPE`, `BASE-REVIEW-RISK`)

**Pass**: exactly one column-0 `Type: feature|task|bug` line and exactly one `Review-Risk:` line (`none`, `payment`, `pii`, `auth`, or `compliance`). Features name their scope boundaries (`Scope-In:` / `Scope-Out:`) and any public interface they change.

**Fail**: missing, repeated or unknown `Type:` or `Review-Risk:`; a feature with unresolved design questions and no scope boundaries.

```bash
ccore tracker show <owner/repo#N> | jq -r '.data.labels[].name'
```

The labels `type:<value>` and `review-risk:<value>` are derived from the body by `ccore tracker create`.

### Criterion 5: Cohesive Scope

Machine-readable contract: `standards/workflow/issue-intake.md ## Pflichtfelder` (`BASE-COHESIVE-SCOPE`)

**Pass**: The issue addresses one coherent outcome whose Acceptance Criteria can be reviewed together as one change.

**Fail**: The issue mixes unrelated concerns ("refactor X AND add feature Y"), or one requirement is split across several issues so that no reviewer sees the whole change. Size is a review decision, not a duration or effort estimate.

### Criterion 6: Dependencies Resolved (No Active Blockers)

Machine-readable contract: `standards/workflow/issue-intake.md ## Pflichtfelder` (`BASE-BLOCKED-BY-URL`)

**Pass**: Every prerequisite is declared as a column-0 `Blocked by: <full issue URL>` line, and each blocking issue is closed or the issue explicitly handles the dependency.

**Fail**: An open blocker exists. An agent will hit dependency walls mid-execution.

```bash
ccore tracker show <owner/repo#N> | jq -r '.data.dependencies[]'
ccore tracker show <blocking-issue-url> | jq -r '.data.state'
```

## Scoring Table: Required vs Optional per Issue Type

| Criterion | feature | task | bug |
|-----------|---------|------|-----|
| 1. Clear intent | required | required | required |
| 2. Outcome-focused ACs | required | required | required |
| 3. MoC table | required | required | required |
| 4. Classification and scope | required | required | required |
| 5. Cohesive scope | required | required | required |
| 6. Dependencies resolved | required | required | required |

Bug issues follow the proportionality rules in `issue-intake.md` (`BASE-BUG-PROPORTIONAL-AC`, `BASE-BUG-PROPORTIONAL-MOC`): the reported failing case as one criterion with the smallest focused regression check as its MoC.

**Minimum to be factory-ready**:
- All critical findings of the author check are resolved
- major and minor findings: warn but don't block

## Factory-Ready vs Needs Interactive Work

| Condition | Classification | Action |
|-----------|---------------|--------|
| Author check exits 0 without findings | FACTORY READY | Deliver through executive-pack |
| Author check exits 0 with warnings | FACTORY READY with warnings | Proceed; address the warnings when cheap |
| Vague intent (fixable) | NEEDS INTERACTIVE WORK | Run `/intake` on the issue to resolve |
| No ACs or no MoC | NEEDS INTERACTIVE WORK | Add them, then `ccore tracker update --ref <ref> --body-file <file>` |
| Missing or malformed `Type:` / `Review-Risk:` | NEEDS INTERACTIVE WORK | Classify, re-check, update the body |
| Active blockers | BLOCKED | Resolve blockers first |
| Mixed concerns | NEEDS RE-SCOPING | Separate only independently valuable outcomes |

## Quick-Check Procedure

Manual assessment of a hosted issue (the author check automates the structural part; the reader judges the semantic fit):

```bash
# 1. Run the deterministic author check against the live body
uv run python "$INTAKE_ROOT/scripts/issue-author-check.py" --issue <owner/repo#N> --repo-root <repo>

# 2. Read the body, labels and dependencies
ccore tracker show <owner/repo#N> | jq '{title: .data.title, labels: [.data.labels[].name], dependencies: .data.dependencies}'

# 3. Check each blocker's state
ccore tracker show <blocking-issue-url> | jq -r '.data.state'
```

## Project Overlay Convention (Pass 3)

Projects can extend the factory-ready check with project-specific issue rules by placing an overlay file at:

```
$REPO_ROOT/.agents/standards/issue-intake.md
```

When this file is present, the intake author check loads its rules after the library baseline. Critical overlay rules block the verdict; lower-severity rules appear as warnings.

The overlay file supports two rule sections:
- `## Pflichtfelder` — required fields or elements that every issue must include
- `## Anti-Patterns` — prohibited patterns an issue must not exhibit

Each rule defaults to Critical severity. Override with `<!-- severity: major|minor -->` prefix.

If the file is absent, only the library baseline applies. A legacy overlay under the previous standard name without the new file is a critical configuration error: rename it to `.agents/standards/issue-intake.md` so project rules are not silently dropped.

Full specification: `standards/workflow/issue-intake.md`

## Relationship to Other Standards

- **issue-intake.md**: The machine-parseable issue contract and overlay format used by every criterion above
- **verification-discipline.md**: Discharging an issue's Means of Compliance after implementation — separate from factory-ready, which gates the spec before it
- **workplan.md**: Uses autonomy scoring that aligns with factory-ready criteria

---
name: bug-triage
description: Investigate reported defects, verify causes and guide a focused fix and regression check.
requires_standards: [dev-tools/tool-standards]
---

# Bug Triage

Systematic 4-phase workflow for diagnosing and fixing bugs. Prevents premature action by enforcing investigation before execution.

## When to Use

Trigger on: bug, broken, kaputt, geht nicht, Fehler, regression, something is wrong, doesn't work, it's broken.

Do NOT use for: feature requests, performance improvements, or refactoring unrelated to a defect.

## Phase 1: Reproduce

<investigation>
Verify the bug actually exists before analyzing causes.

1. Identify the exact reproduction steps from the bug report.
2. Set up the environment as described (OS, version, dependencies).
3. Execute the exact failing command or action.
4. Observe the actual behavior vs. expected behavior.
5. Confirm: does the bug occur consistently or intermittently?

**If not reproducible:** Ask only for missing evidence that changes the next
investigation step. Continue safe independent code, existing-test and log inspection
while awaiting it. Label hypotheses as unconfirmed; never invent a reproduction or
report an unverified cause as established. Stop only work that depends on unavailable
evidence or additional authorization.
</investigation>

## Phase 2: Root Cause

<investigation>
Analyze the confirmed bug to find its root cause. Consult historical data first.

Use relevant existing bug history, recent logs and cross-session memory when available.
When the request refers to past work, search memory first. Missing integrations do
not block local investigation; do not require unrelated history queries.

### Step 4: Synthesize

From available evidence, form a hypothesis:
- What line/function is the defect in?
- What condition triggers it?
- Is it a regression (recently introduced)?
</investigation>

## Phase 3: Fix

<execution>
Implement a minimal fix. One concern only: fix the bug.

**Rules:**
- No cleanup, no refactoring, no opportunistic improvements.
- Touch only the files necessary to fix the confirmed root cause.
- Leave unrelated refactoring untouched and mention it in the report; do not file
  speculative follow-up beads.
- Use the existing bead. If a new work order is needed, author it inline through
  intake before implementation; touching multiple files does not justify a duplicate.
- A diagnosis request alone does not authorize a fix. For an authorized fix, the
  current implementation owner keeps source and repairs.

Keep that bug bead proportional:

- Default to one AC for the reported failing case.
- Add one adjacent control-case AC only when the fix can plausibly regress it.
- Put constraints such as "no customer-specific logic" in Scope-Out, not in ACs.
- Use the smallest focused regression test as MoC. Do not require full suites,
  unrelated systems, customer datasets, E2E/UAT, deployments, release builds,
  health checks, or push preflight unless the reported defect itself crosses that
  boundary.

Then proceed with the fix, referencing the bead ID in the commit message.
</execution>

## Phase 4: Regression Test

<execution>
Write a test that encodes the bug as a permanent guard.

### Step 1: Write the regression test

The test must:
- **Fail without the fix** (confirms the test catches the bug)
- **Pass with the fix** (confirms the fix addresses the bug)

Follow the active delivery's test ownership: independent test author for RED and
implementation owner for GREEN. Use the recorded baseline or an isolated workspace
to demonstrate failure without overwriting unrelated or uncommitted changes. Rerun
checks affected by the repair without repeating approval for the same scope.

### Step 3: Keep verification proportional

```bash
uv run pytest <focused-test-path> -k "<regression-test>" -v
```

Expand only to the smallest affected package or module suite when the fix touches
shared behavior or the focused test cannot cover a plausible adjacent regression.
Do not invent a broader UI, Playwright, staging, customer-data, or cross-system flow
because production-like fixtures are unavailable locally.

Repository-wide CI, builds, lint, health checks, and push preflight may still run as
delivery gates. They are not additional bug Acceptance Criteria or MoC evidence.
</execution>

## Out of Scope

- Performance tuning unrelated to a defect
- Feature additions discovered during investigation
- Refactoring "while we're in here"
- Bugs in external dependencies (fork or workaround instead)

## Reference

- Bead mutation gateway: author check followed by direct `bd create --body-file`

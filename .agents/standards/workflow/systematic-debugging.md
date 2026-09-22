# Systematic Debugging: Root Cause Before Fix

When debugging, follow this 4-phase process. Never jump to fixes without understanding the root cause.

## The Debugging Iron Law

**No fix without a hypothesis. No hypothesis without investigation.**

Random fix attempts waste time and create new bugs. Systematic debugging finds root causes faster.

## The 4-Phase Process

```
Phase 1: INVESTIGATE  → Reproduce, gather evidence, understand symptoms
Phase 2: ANALYZE      → Find patterns, identify what works vs. what doesn't
Phase 3: HYPOTHESIZE  → Form ONE clear hypothesis about root cause
Phase 4: FIX          → Implement fix, verify with reproduction case
```

### Phase 1: Investigate

Before anything else, reproduce the bug and gather evidence:

1. **Reproduce**: Run the exact failing scenario. Get the exact error output.
2. **Isolate**: Find the smallest input/state that triggers the bug.
3. **Gather context**: Read the failing code path. Check recent changes (`git log --oneline -10`).
4. **Map the symptom**: What was expected? What actually happened? Where does the divergence start?

**Output**: A clear symptom statement:
```
SYMPTOM: When <input>, expected <X> but got <Y>.
REPRODUCER: <exact command or steps>
ERROR: <exact error message>
```

### Phase 2: Analyze

Look for patterns in the evidence:

1. **What works**: Which similar cases succeed? What's different about the failing case?
2. **Boundary conditions**: Does it fail for all inputs or specific ones? Since when?
3. **Related code**: What else touches this code path? Are there race conditions, shared state, or ordering dependencies?
4. **Similar bugs**: Has this type of bug occurred before in this codebase? (`git log --grep="fix:"`)

**Output**: A pattern analysis:
```
WORKS: <what succeeds>
FAILS: <what fails>
DIFFERENCE: <the specific factor that distinguishes success from failure>
```

### Phase 3: Hypothesize

Form ONE specific, testable hypothesis:

```
HYPOTHESIS: The bug is caused by <specific cause> because <evidence from Phase 1-2>.
TEST: If I <specific action>, I expect <specific outcome>.
```

**Rules:**
- One hypothesis at a time. Don't shotgun multiple fixes.
- The hypothesis must explain ALL observed symptoms, not just some.
- If the hypothesis is wrong (test fails), go back to Phase 2 with new evidence.

### Phase 4: Fix

1. **Write a test** that reproduces the bug (RED — the test must fail before the fix)
2. **Implement the minimal fix** for the root cause (not the symptom)
3. **Verify the test passes** (GREEN)
4. **Run the full test suite** to check for regressions
5. **Verify the original reproducer** from Phase 1 no longer fails

**Output**: Cite evidence for the fix:
```
FIX: <what was changed>
RAN: <test command>
SAW: <test output showing pass>
REPRODUCER: <original reproducer now succeeds>
```

## Escalation: The 3-Attempt Rule

If 3 fix attempts fail for the same bug:

1. **STOP** attempting fixes
2. **Document** what was tried, what happened, and what was ruled out
3. **Escalate**: Report to the user or write a debug log to bead notes

Append this record with `bd update <id> --append-notes`:

```text
Debug log: Attempted 3 fixes for <symptom>.
Tried: (1) <fix1> -> <result1>, (2) <fix2> -> <result2>, (3) <fix3> -> <result3>.
Ruled out: <what's definitely not the cause>.
Remaining hypotheses: <what might still be the cause>.
Recommend: fresh session with clean context.
```

**Why stop at 3:** Each failed attempt adds noise to your mental model. A fresh session
with the documented history is more likely to find the root cause than a 4th attempt
in a polluted context.

## Parallel Debugging (Multi-Test Failures)

When multiple tests fail simultaneously:

1. **Triage**: Are the failures independent or do they share a root cause?
2. **Independent failures**: Dispatch parallel debugging agents, one per failure
3. **Shared root cause**: Debug the common cause first, then verify all tests pass

**How to detect shared root cause:**
- Failures in the same module/package → likely shared
- Same error type across different modules → likely shared
- Failures appeared in the same commit → likely shared
- Unrelated modules with different errors → likely independent

## Anti-Patterns

| Anti-Pattern | Symptom | Fix |
|-------------|---------|-----|
| Shotgun debugging | Try 5 things at once | One hypothesis at a time |
| Symptom fixing | Fix the error message, not the cause | Ask "why does this happen?" |
| Fix-and-pray | Change something, don't verify | Run reproducer after every fix |
| Context hoarding | Keep debugging with 500KB of context | Escalate after 3 attempts |
| Skip reproduction | "I think I know what's wrong" | Always reproduce first |
| Blame the framework | "Must be a library bug" | Verify with minimal reproduction |

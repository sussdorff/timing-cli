# Verification Discipline: Evidence Over Assertions

No completion claims without fresh verification evidence. Every status report must be backed by a command output, not a belief.

## The Verification Iron Law

**Before claiming something works, run a command and cite the output.**

```
BAD:  "The tests should pass now."
GOOD: "All 42 tests pass: `pytest tests/ -> 42 passed in 3.2s`"

BAD:  "The server is running."
GOOD: "Server responds: `curl -s localhost:8080/health -> {"status":"ok"}`"

BAD:  "I fixed the bug."
GOOD: "Bug no longer reproduces: `python reproduce.py -> exit code 0, output: 'Success'`"
```

## Evidence Requirements

### What Counts as Evidence

| Evidence Type | Example | Sufficient? |
|---------------|---------|-------------|
| Command output with exit code | `pytest -> 42 passed, exit 0` | Yes |
| Tool result showing state | `Read file.py -> line 42 shows corrected code` | Yes |
| API response | `curl /api/health -> 200 OK` | Yes |
| Log output | `docker logs app -> "Started on port 8080"` | Yes |
| Git diff showing change | `git diff -> +fixed_line, -broken_line` | Yes |

### What Does NOT Count

| Non-Evidence | Why | Instead |
|-------------|-----|---------|
| "It should work" | Belief, not observation | Run it |
| "I changed the code" | Change != working | Run tests |
| "The logic is correct" | Reasoning, not verification | Execute and observe |
| "Same pattern as before" | Analogy, not proof | Test this specific case |
| Previous test run (stale) | State may have changed | Run again after changes |

## Red Flags in Status Reports

### Language Patterns That Signal Missing Verification

| Red Flag | What It Means | Required Action |
|----------|---------------|-----------------|
| "should" | Prediction, not observation | Run and observe |
| "probably" | Uncertainty | Verify before reporting |
| "seems to" | Incomplete verification | Check more thoroughly |
| "I think" | Belief without evidence | Execute and confirm |
| "likely" | Probability, not certainty | Test the specific case |
| "as expected" (without output) | Assumed match | Show the actual output |

### Premature Satisfaction Expressions

These phrases before verification are warning signs:

| Expression | Problem | Fix |
|-----------|---------|-----|
| "Done!" | Claimed completion without evidence | Run verification first |
| "That fixes it!" | Assumed fix without test | Run the failing test |
| "All good!" | Blanket assertion | Run specific checks |
| "Works perfectly!" | Hyperbole without proof | Show test output |

## Verification at Means-of-Compliance Gates

### Gate Verification Protocol

Every Means of Compliance row a bead declares must be discharged by this protocol
before the bead is reported complete:

```
1. RUN: Execute the verification command
2. READ: Read the full output (don't skim)
3. CHECK: Verify exit code AND output content
4. CITE: Include specific output in the report
5. DECIDE: PASS only if evidence supports it
```

Example for a unit-test Means of Compliance:
```
1. RUN:   `uv run pytest tests/ -v`
2. READ:   Output shows "42 passed, 0 failed"
3. CHECK:  Exit code 0, no failures, no skipped tests
4. CITE:   "Test Coverage: PASS — 42 passed, 0 failed (pytest 8.x)"
5. DECIDE: PASS
```

### Final Report Evidence

The implementation loop's final report must cite evidence for every claim:

```markdown
### Means of Compliance
- Code Review: PASS — No quality issues found in 5 changed files
- Security Review: PASS — No secrets, no injection, no unsafe deserialization
- Test Coverage: PASS — `pytest tests/ -> 42 passed in 3.2s`
- Documentation: PASS — Changelog entry matches `git diff --stat` changes
```

NOT:

```markdown
### Means of Compliance
- Code Review: PASS
- Security Review: PASS
- Test Coverage: PASS
- Documentation: PASS
```

## Verification Timing

### When to Verify

| Moment | Verify What | How |
|--------|-------------|-----|
| After writing code | Syntax, imports work | Run the file / compile |
| After writing test | Test fails correctly (RED) | Run test, check failure reason |
| After fixing code | Test passes (GREEN) | Run test, check pass |
| After all changes | No regressions | Run full test suite |
| Before committing | All DoD gates | Run all verification commands |
| Before reporting status | Claimed state is actual state | Re-run relevant checks |

### Stale Evidence

Evidence has a shelf life. After making changes, previous verification is stale:

```
STALE: "Tests passed" (ran 5 minutes ago, before last edit)
FRESH: "Tests passed" (ran after all edits, just now)
```

Rule: If you changed ANY file after the last test run, re-run tests before claiming they pass.

## Anti-Patterns

| Anti-Pattern | Example | Fix |
|-------------|---------|-----|
| Verify-once | Run tests once at the start, never again | Re-verify after every change |
| Trust-the-diff | "I can see in the diff it's correct" | Run it, diffs lie by omission |
| Selective-verification | Run one test, claim all pass | Run full suite |
| Output-skimming | "42 passed" (missed the "1 failed" line) | Read complete output |
| Exit-code-only | Exit 0 but warnings in output | Check exit code AND output |
| Proxy-verification | "Linter passes" (but didn't run tests) | Each check is independent |
| Scope-aligned-only test | "X and Y agree" assertion that sets matching flags on both — passes while production defaults still diverge | Add at least one assertion that invokes both commands with **no arguments** so defaults are exercised |
| Diff-only review | Approving a change by reading the diff without running the CLI on real data | Run the new/changed command against the real lockfile / real fixtures and compare counts before approving |

## Adversarial Review Protocol

Adversarial review of a finished implementation is not a re-reading of the diff. It is a run.

1. **Replay the bead's "Why" section as a test plan.** Each numbered defect in the Why becomes a probe; run the actual CLI/code path that should have been fixed and capture the output.
2. **Run with default arguments.** If the bead claims two commands agree, run both with no args. Scope-aligned fixtures hide default-value bugs.
3. **Run against real-machine state.** Diff reading misses footguns that only appear on a populated lockfile, full catalog, or production-scale dataset. The 173-vs-45 catalog-diff misclassification in CL-uyp was invisible from the diff and obvious from a single CLI run against the actual lockfile.
4. **Run from unexpected working directories.** `/tmp`, `$HOME`, sibling project — the bead may have promised "run-anywhere" but only fixed the new verb.
5. **Cite the command and its output for every finding.** No "I think this is broken" — every adversarial finding ships with `command -> output`.

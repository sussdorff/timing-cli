# TDD Discipline: RED-GREEN-REFACTOR

Test-Driven Development as an optional but recommended mode for code changes.

## The TDD Iron Law

**No production code without a failing test first.**

When TDD mode is active, every code change follows this cycle:

```
1. RED:    Write a failing test for the desired behavior
2. VERIFY: Run it. Confirm it fails for the RIGHT reason.
3. GREEN:  Write the MINIMUM production code to make it pass
4. VERIFY: Run it. Confirm it passes. No other tests broke.
5. REFACTOR: Clean up production code and test code
6. VERIFY: Run it. Everything still passes.
```

### Why Verify RED Matters

A test that passes immediately proves nothing. Before writing production code, confirm:
- The test actually runs (no syntax errors, no skips)
- The test fails for the expected reason (not an import error or wrong assertion)
- The test exercises the code path you intend to change

### Why Verify GREEN Matters

After writing production code, confirm:
- The new test passes
- ALL existing tests still pass (no regressions)
- You didn't accidentally break a related test

## When TDD Mode Applies

### Use TDD (Default for Code Changes)

| Change Type | TDD Mode | Rationale |
|-------------|----------|-----------|
| New function/method | Yes | Write test first, then implement |
| Bug fix | Yes | Write test that reproduces the bug, then fix |
| Behavior change | Yes | Write test for new behavior, then change code |
| Refactoring | Partial | Existing tests should cover. Add tests for uncovered paths first. |
| API endpoint | Yes | Test expected request/response, then implement |

### Skip TDD

| Change Type | TDD Mode | Rationale |
|-------------|----------|-----------|
| Config file changes | No | No testable behavior |
| Documentation only | No | No code to test |
| Dependency updates | No | Run existing tests, don't write new ones |
| CSS/styling | No | Visual, not behavioral |
| Rename/move files | No | Existing tests cover behavior |
| CI/CD pipeline | No | Test by running the pipeline |

## Applying TDD

When TDD mode is active, implementation and unit tests interleave:

```
For each task in "Step by Step Tasks":
  1. Read relevant code (understand current state)
  2. Write failing test for the desired change (RED)
  3. Run test -> confirm it fails correctly (VERIFY RED)
  4. Write production code (GREEN)
  5. Run test -> confirm it passes (VERIFY GREEN)
  6. Run full test suite -> confirm no regressions
  7. Refactor if needed -> run tests again (REFACTOR)
  8. Mark task complete
```

This replaces the sequential "implement everything, then test everything" flow.

## The 12 Rationalisations (and Why They're Wrong)

Common excuses for skipping TDD, and why they don't hold:

### 1. "This is too simple to need a test"
**Counter**: Simple code that breaks costs the same to debug. The test takes 30 seconds to write. The debugging takes 30 minutes.

### 2. "I'll add the test after"
**Counter**: You won't. And if you do, you'll write a test that passes by definition, proving nothing. TDD tests are written with knowledge of what SHOULD fail.

### 3. "I'm just refactoring, tests already exist"
**Counter**: Verify tests actually cover the refactored paths. Run coverage on the specific functions. If coverage is < 80%, write tests for uncovered paths FIRST, then refactor.

### 4. "The test framework isn't set up for this"
**Counter**: Set it up. This is infrastructure, not an excuse. If setup is genuinely blocking, document it as a blocker and move on.

### 5. "I need to see the implementation first to know what to test"
**Counter**: You should know the BEHAVIOR before writing code. Test the behavior. If you can't describe what the code should do, you're not ready to write it.

### 6. "Tests will slow me down"
**Counter**: Tests that catch bugs during development are faster than debugging in production. The perceived slowdown is the PREVENTION of a longer slowdown later.

### 7. "This is a prototype / spike"
**Counter**: Valid only if the code will be thrown away. If any prototype code survives into production, it needs tests. Mark clearly: "SPIKE - no tests, will rewrite."

### 8. "The function is private / internal"
**Counter**: Test through the public interface. If the private function has complex logic, that's a sign it should be extracted and tested.

### 9. "It's just a wrapper"
**Counter**: Wrappers that transform data, handle errors, or have conditional logic need tests. Trivial pass-through wrappers don't.

### 10. "I'm fixing a test, not production code"
**Counter**: Correct. Test fixes don't follow TDD. But verify the fixed test actually tests production behavior.

### 11. "The existing code doesn't have tests"
**Counter**: Write tests for the code you're changing. Don't use legacy debt as permission to add more debt.

### 12. "I'm under time pressure"
**Counter**: TDD doesn't take longer. Writing code without tests and then debugging takes longer. The pressure makes TDD MORE important, not less.

## Scale-Adaptive TDD

TDD discipline scales with task size:

### Micro (quick fix)
- Write test for the fix, verify RED, fix, verify GREEN
- Single cycle, no refactor phase needed

### Small (bug fix, small feature)
- Full RED-GREEN-REFACTOR per function
- Run full suite at the end

### Medium (feature, refactor)
- Full TDD per component
- Integration test at the boundary
- Refactor phase after all components work

### Large (major feature)
- TDD per module
- Integration tests between modules
- Dedicated refactor pass at the end

## Anti-Patterns to Detect

| Anti-Pattern | Symptom | Fix |
|--------------|---------|-----|
| Test-after | All tests written after all code | Interleave: test, code, test, code |
| Green-bar-only | Tests written to pass immediately | Write test FIRST, see it fail, then code |
| Assertion-free tests | Tests run code but don't assert | Every test needs at least one meaningful assertion |
| Over-mocking | Everything mocked, nothing tested | Mock dependencies only, test real logic |
| Giant steps | Writing 200 lines then testing | Write test for one behavior, implement, repeat |
| Skipped RED verification | "I know it'll fail" | Run it. Your assumptions are wrong more often than you think. |

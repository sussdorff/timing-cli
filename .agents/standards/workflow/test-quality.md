# Test Quality: Universal Testing Principles

Framework-agnostic test quality standards for test authors, implementation
executors, and DoD Gate 3 (Test Coverage Verification).

## Trigger Context

Apply when writing, reviewing, or verifying unit tests in any framework (pytest, Jest, Vitest, Pester, Go testing, RSpec, etc.).

## Core Principles

### 1. Test Behavior, Not Implementation

Tests assert WHAT the code does, not HOW it does it internally.

```
GOOD: "When user submits valid form, response is 201 Created"
BAD:  "Function calls _validate() then _save() then _notify()"
```

If refactoring internals breaks tests without changing behavior, the tests are wrong.

### 2. Mock Dependencies, Not the Subject

Mock external dependencies (database, API, filesystem). Never mock the function under test.

```
GOOD: Mock the HTTP client, test that your function handles the response correctly
BAD:  Mock your function's return value and assert the mock worked
```

**Red flag**: If your test file has more mock setup than assertions, you're testing mocks, not code.

### 3. One Assertion Per Behavior

Each test validates one specific behavior. Multiple assertions are fine if they all verify the same behavior.

```
GOOD: test_login_success: assert status 200, assert token present, assert user in session
BAD:  test_login: assert success, assert failure, assert rate limit, assert lockout
```

### 4. Tests Are Environment-Independent

No hardcoded paths, machine-specific values, or timezone assumptions.

| Anti-Pattern | Fix |
|-------------|-----|
| `/Users/john/project/data.json` | Use `tmp_path`, `tempfile`, or test fixtures |
| `assert time == "14:30"` | Assert relative time or mock clock |
| `assert hostname == "ci-server-1"` | Don't assert infrastructure details |
| `assert output.contains("C:\\Windows")` | Use `os.sep` or platform-agnostic paths |

### 5. Arrange-Act-Assert (AAA)

Every test has three clear phases:

```
# Arrange: Set up preconditions
user = create_test_user(role="admin")

# Act: Execute the behavior under test
result = delete_user(user.id)

# Assert: Verify the outcome
assert result.success is True
assert User.objects.filter(id=user.id).count() == 0
```

### 6. Tests Must Fail for the Right Reason

When writing tests before code (TDD RED phase), verify the failure message matches your expectation:

```
GOOD: "AssertionError: expected 201 but got 404" (endpoint doesn't exist yet)
BAD:  "ImportError: cannot import 'UserService'" (infrastructure problem, not a behavior gap)
```

## Test Smells to Flag

| Smell | Why It's Bad | Fix |
|-------|-------------|-----|
| Test mirrors implementation | Breaks on refactor | Test observable behavior |
| Excessive mocking (>3 mocks) | Testing wiring, not logic | Simplify design or use integration test |
| Sleep/wait in tests | Flaky, slow | Use polling/retries with timeout, or async await |
| Shared mutable state | Order-dependent failures | Fresh fixtures per test |
| Asserting exception type only | Misses wrong exception message | Assert message or code too |
| No negative tests | Only tests happy path | Add error/edge case tests |
| Test data as magic numbers | Unclear intent | Use named constants or builders |

## Coverage Expectations

### What to Cover

- All new public functions/methods
- All modified behavior (even one-line changes)
- Error paths and edge cases
- Boundary conditions (empty input, max values, null/nil)

### What NOT to Require Coverage For

- Pure data classes / DTOs with no logic
- Framework boilerplate (app config, middleware registration)
- Trivial getters/setters with no validation
- Third-party library wrappers with no custom logic

## Framework-Specific Extensions

This standard provides universal principles. Framework-specific depth comes from skills:

| Framework | Skill (if available) | What It Adds |
|-----------|---------------------|--------------|
| Pester | `pester-testing` | InModuleScope, ParameterFilter, PowerShell 5.1 quirks |
| pytest | Python standards | Fixtures, conftest patterns, parametrize |
| Jest/Vitest | (future) | Module mocking, snapshot testing, async patterns |
| Go testing | (future) | Table-driven tests, testify patterns |

A test-writing agent detects the project's framework from these signals and loads the matching skill when one exists.

## Usage in Workflow

- **Bead authoring**: A bead's test-related Means of Compliance references these principles
- **Implementation**: TDD cycles follow these principles
- **Verification**: A test Means of Compliance is discharged against these principles

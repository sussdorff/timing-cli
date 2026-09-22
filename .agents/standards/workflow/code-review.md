# Code Review: Universal Quality Patterns

Framework-agnostic code review checklist for discharging a code-review Means of Compliance.

## Trigger Context

Apply when reviewing code changes during implementation or as part of DoD verification.

## Review Categories

### 1. Wrapper Functions (External Call Isolation)

Every call to an external system should be wrapped in a dedicated function.

```
GOOD: result = self.http_client.get(url)          # Injected dependency
GOOD: result = fetch_user_data(user_id)            # Wrapper function
BAD:  result = requests.get(f"{BASE_URL}/users")   # Direct library call in business logic
```

**Why**: Testability (mock the wrapper, not the library), centralized error handling, single point of change.

**Check**: Are there direct calls to external libraries (HTTP, DB, filesystem, shell) embedded in business logic?

### 2. Code Reuse

Could existing functions be extended instead of duplicating logic?

**Check sequence**:
1. Does similar functionality already exist in the codebase?
2. Can the existing function be parameterized to handle the new case?
3. If not, is the new code truly distinct enough to warrant a separate function?

**Red flags**:
- Two functions with >70% similar code
- Copy-paste with minor modifications
- Utility functions recreated in a new module

### 3. Return Values

All result fields must be set before success/failure checks.

```
GOOD:
  result.data = processed_data
  result.count = len(processed_data)
  result.success = True
  return result

BAD:
  if success:
    result.success = True
    return result           # result.data never set!
```

**Check**: Does every code path set all expected fields before returning?

### 4. YAGNI (You Aren't Gonna Need It)

No unused parameters, return fields, configuration options, or abstractions.

| Anti-Pattern | Example | Fix |
|-------------|---------|-----|
| Unused parameter | `def process(data, verbose=False)` where verbose is never checked | Remove parameter |
| Premature abstraction | Factory pattern for a single implementation | Use the implementation directly |
| Feature flags for unrequested features | `if config.enable_new_algo` for algo nobody asked for | Don't build it |
| Over-generalized interface | Interface with 10 methods, only 3 implemented | Narrow the interface |

### 5. Minimal Diff

Changes should be surgical and focused on the task.

**Check**:
- Are all changes related to the ticket/task?
- No formatting-only changes to untouched code
- No import reorganization of unrelated files
- No renamed variables that aren't part of the task

**Exception**: If a rename or format change is needed for the task, it's fine. The rule prevents drive-by refactoring.

### 6. Error Handling

Errors should be handled at the appropriate level, not swallowed or over-caught.

| Anti-Pattern | Fix |
|-------------|-----|
| `except Exception: pass` | Catch specific exceptions, log or re-raise |
| Error message without context | Include what failed, with what input, and why |
| Returning `None` on error | Raise exception or return Result type |
| Try/catch around entire function | Narrow the scope to the specific risky call |

### 7. Naming and Clarity

Code should be self-explanatory without excessive comments.

**Check**:
- Do function names describe what they do? (`get_active_users` not `process_data`)
- Do variable names convey meaning? (`retry_count` not `n`)
- Are boolean names questions? (`is_valid`, `has_access`, `should_retry`)
- Are abbreviations avoided unless universally understood? (`req`/`res` OK, `usr_grp_mgr` not)

## Review Output Format

The review produces:

```markdown
### Code Review Results

**Files reviewed**: [list]
**Issues found**: [count]

| File | Line | Category | Severity | Issue | Suggestion |
|------|------|----------|----------|-------|------------|
| ... | ... | Wrapper | MEDIUM | Direct HTTP call in business logic | Extract to service method |

**Verdict**: PASS / NEEDS_FIX (with specific fixes)
```

## Severity Levels

| Severity | Action | Examples |
|----------|--------|----------|
| HIGH | Must fix before commit | Security issue, data loss risk, broken functionality |
| MEDIUM | Should fix, auto-fixable | Missing wrapper, code duplication, unclear naming |
| LOW | Nice to have, skip if tight | Style preference, minor naming improvement |

## Relationship to Other Standards

- **Security Review** (Gate 2): Handles injection, secrets, unsafe deserialization separately
- **Test Coverage** (Gate 3): Handled by the implementation executor, not code review
- **Documentation** (Gate 4): Handled conditionally by `doc-changelog-updater`
- **Linting**: Automated formatting/style checks run before code review

Code review focuses on DESIGN quality (patterns, structure, maintainability) that linters cannot catch.

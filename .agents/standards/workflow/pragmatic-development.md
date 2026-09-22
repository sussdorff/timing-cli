# Pragmatic Development: Language-Agnostic Engineering Principles

Practical engineering principles that apply regardless of programming language, framework, or platform.

## Trigger Context

Apply as general development guidance during implementation. These principles inform how code is written, not what is tested or reviewed (see `test-quality.md` and `code-review.md` for those).

## Principles

### 1. Make It Work, Make It Right, Make It Fast

Implement in this order. Never optimize before the feature works correctly with tests.

| Phase | Focus | Anti-Pattern |
|-------|-------|-------------|
| Work | Correct behavior with tests | Premature optimization, architecture astronautics |
| Right | Clean code, good naming, no duplication | Skipping straight to "fast" |
| Fast | Profile-guided optimization | Optimizing without measurements |

### 2. Prefer Explicit Over Clever

Code is read far more often than it is written. Favor clarity over conciseness.

```
GOOD: if user.is_active and user.has_permission("admin"):
BAD:  if u.a and u.p & 0x01:
```

**Exception**: Idiomatic patterns in a language (list comprehensions in Python, LINQ in C#, stream operations in Java) are "explicit" within that language's culture.

### 3. Fail Fast, Fail Loud

Validate inputs at system boundaries. Crash early with clear error messages rather than silently producing wrong results.

```
GOOD: raise ValueError(f"Expected positive int, got {value}")
BAD:  return max(0, value)  # Silently "fixes" bad input
```

**Boundary validation points**:
- CLI argument parsing
- API request handlers
- Configuration loading
- File/data import
- User input processing

**Internal code**: Trust function contracts. Don't re-validate inside private/internal functions.

### 4. Composition Over Inheritance

Build behavior by combining small, focused pieces rather than deep inheritance hierarchies.

| Prefer | Over |
|--------|------|
| Functions that take functions | Abstract base classes with template methods |
| Dependency injection | Service locators or global state |
| Flat module structure | Deep nested namespaces |
| Mixins/traits (if language supports) | Multi-level inheritance chains |

**Rule of thumb**: If your inheritance chain is >2 levels deep, reconsider the design.

### 5. Single Source of Truth

Every piece of knowledge should have a single, unambiguous representation.

| Duplication | Fix |
|------------|-----|
| Same constant in multiple files | Extract to shared config/constants module |
| Same validation in frontend and backend | Validate at the API boundary, trust internally |
| Same logic in two functions | Extract shared logic to a helper |
| Documentation that paraphrases code | Remove the comment, make the code clearer |

### 6. Convention Over Configuration

Follow the project's existing patterns rather than introducing new ones.

**Before writing new code**:
1. Search for similar functionality in the codebase
2. Follow the same structure, naming, and organization
3. If the existing pattern is bad, fix it in a separate task (not the current one)

**New projects**: Establish conventions early, then follow them consistently.

### 7. Minimal Dependency Principle

Add dependencies only when the value clearly exceeds the cost.

**Before adding a dependency, check**:
- Can the standard library handle it? (often yes for simple cases)
- Is the dependency actively maintained?
- What's the transitive dependency count?
- Does it have known vulnerabilities?
- Is it a large library for a small need? (e.g., lodash for one utility)

### 8. Separation of Concerns

Each module/function/class should have one reason to change.

**Signals of poor separation**:
- Function name contains "and" (`validateAndSave`, `parseAndTransform`)
- Module imports from unrelated domains
- Change in UI requires change in business logic
- Database schema change breaks API contracts

## Error Handling Strategy

### Layer-Appropriate Error Handling

| Layer | Strategy |
|-------|----------|
| Library/utility | Raise specific exceptions with context |
| Business logic | Catch known errors, add business context, re-raise |
| API boundary | Catch all, translate to user-facing error codes/messages |
| CLI | Catch all, print human-readable message, exit with code |

### Error Message Quality

Every error message should answer three questions:
1. **What** happened? ("Database connection failed")
2. **Where**? ("while connecting to PostgreSQL at db.example.com:5432")
3. **What to do**? ("Check that the database is running and credentials are correct")

## When to Break the Rules

These principles have one override: **shipping working software**. If following a principle strictly would prevent delivering a working solution:

1. Ship the pragmatic solution
2. Document the shortcut
3. Create an author-checked P3 refactor task with `bd create --body-file <file>`
4. Move on

Perfection is the enemy of done.

# Git Best Practices: Beyond Conventional Commits

Git workflow practices for safe, clean version control. Complements `git/conventional-commits.md` (commit message format) with operational practices.

## Trigger Context

Apply during implementation when committing, and in Session Close when pushing and tagging.

## Commit Practices

### Atomic Commits

One logical change per commit. A commit should be revertable without breaking unrelated functionality.

| Good | Bad |
|------|-----|
| `feat(auth): Add JWT refresh token endpoint` | `feat: Add auth, fix typo, update deps` |
| `fix(parser): Handle empty input gracefully` | `fix various bugs` |
| `test(auth): Add tests for refresh token` | `add tests and fix linting` |

**Test**: If you can't describe the commit in one sentence without "and", split it.

### Commit Completeness

Every commit should leave the codebase in a working state:
- Tests pass
- Linting passes
- Application starts (if applicable)

**Never commit**: Half-implemented features, broken tests, commented-out code "for later".

### Staging Discipline

Stage specific files, not everything:

```bash
git add src/auth/refresh.py tests/test_refresh.py   # GOOD: specific files
git add .                                             # BAD: catches everything
git add -A                                            # BAD: even worse
```

**Why**: Prevents accidental inclusion of `.env`, debug files, large binaries, or unrelated changes.

## Branch Practices

### Branch Naming

Follow the project convention: `type/ticket-id/short-description`

```
feat/claude-pa3/jwt-refresh-tokens
fix/zahnrad-42/null-pointer-parser
chore/claude-pa5/update-dependencies
```

### Rebase Safety

| Action | Safe? | When |
|--------|-------|------|
| `git rebase main` | Yes | Before pushing, to linearize |
| `git rebase -i` | Careful | Only on unpushed commits |
| `git push --force` | Dangerous | Only on YOUR branch, never on main/develop |
| `git push --force-to-lease` | Safer | Preferred over `--force` when needed |

**Rule**: Never force-push to shared branches (main, develop, release/*).

### Branch Lifecycle

```
Create branch from main
  |-> Make commits
  |-> Rebase on main (before push)
  |-> Push with -u (set upstream)
  |-> Create MR/PR
  |-> Merge (squash or rebase, per project convention)
  |-> Delete branch (after merge)
```

## Merge/Rebase Strategy

### Default: Rebase + Fast-Forward

```bash
git fetch origin
git rebase origin/main
git push
```

**Why**: Clean linear history, easy to read, easy to bisect.

### When to Merge Instead

- Long-lived branches with many collaborators
- When preserving branch context matters
- When the project convention requires merge commits

### Conflict Resolution

1. **Understand** both sides of the conflict before resolving
2. **Never** just accept "ours" or "theirs" blindly
3. **Test** after resolution (run full test suite)
4. **Document** non-obvious resolution choices in the commit message

## Protected Practices

### Never Do This

| Action | Why | Instead |
|--------|-----|---------|
| Commit `.env` or secrets | Security breach | Use `.gitignore`, secret managers |
| Force-push to main | Destroys shared history | Create a revert commit |
| `git reset --hard` on shared branches | Loses others' work | Use `git revert` |
| Delete remote branches others use | Breaks their workflow | Coordinate first |
| Amend pushed commits | Rewrites shared history | New commit with fix |
| Skip pre-commit hooks (`--no-verify`) | Bypasses quality checks | Fix the hook failure |

### When in Doubt

If you're unsure whether a git operation is safe:
1. Check if the branch has been pushed (`git log --oneline origin/branch..branch`)
2. Check if others are using the branch
3. If destructive and shared: DON'T. Create a new commit instead.

## Integration with Workflow

- **Bead authoring**: No git operations
- **Implementation**: Creates atomic commits following conventional format
- **Session Close**: Pushes, tags per the artifact's version scheme (`sdk-versioning`), optionally creates MR/PR

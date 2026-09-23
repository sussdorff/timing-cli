# Git Commit Convention

This project uses **Conventional Commits**.

## Format

```
<type>[!](<scope>): <description>

[body]

[footer(s)]
```

## Types

| Type | Use for |
|------|---------|
| `feat` | New feature |
| `fix` | Bug fix |
| `test` | Adding or changing tests |
| `refactor` | Restructuring without behavior change |
| `docs` | Documentation |
| `chore` | Maintenance (deps, config) |
| `style` | Formatting (no code change) |
| `perf` | Performance improvement |
| `ci` | CI/CD changes |
| `build` | Build system changes |
| `revert` | Revert of an earlier commit |

## Breaking Changes

For breaking changes put `!` after the type:

```bash
feat!: Remove deprecated API endpoint
feat(api)!: Change authentication flow
```

## Scope

Module or area, for example: `compliance`, `platform`, `api`, `cli`

## Footer

### Issue Reference

```
Closes: project-123
Refs: project-456
```

### Agent Attribution

When an AI agent creates the commit:

```
Agent: claude-opus-4.5
```

## Examples

```bash
# Feature with scope and bead reference
feat(compliance): Add Password Policy check

Implements the check with Windows/macOS support.

Closes: zahnrad-abc
Agent: claude-opus-4.5
```

```bash
# Breaking change
feat!: Remove legacy PowerShell module

Migration to Python complete.

BREAKING CHANGE: ZahnradCompliance.psm1 removed

Closes: zahnrad-xyz
```

```bash
# Simple fix
fix: Resolve null pointer in parser
```

## What Does NOT Belong in a Commit

Detailed decision rationale belongs in:
- **Beads notes** (for traceable documentation)
- **Audit log** (for learnings and assumptions)

Commits stay lean and focused.

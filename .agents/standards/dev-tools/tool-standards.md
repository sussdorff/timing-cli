# Dev-Tools Agent Tool Standards

Dev-tools agents (implementers, test authors, validators) must follow these constraints.

## Required Reading
- `agents/tool-boundaries.md` — defines the allowed tool set per agent role
- `dev-tools/hook-exit-codes.md` — three-tier exit code standard for hooks

## Key Rules
1. Implementers (Read, Write, Edit, Bash, Grep, Glob): No Agent spawning
2. Reviewers/Validators (Read, Bash, Grep, Glob): No file writes — observe only
3. All hooks: fail-open on errors (exit 0, not exit 1) unless a security check (then exit 2)
4. Performance hooks: complete in <100ms at p95

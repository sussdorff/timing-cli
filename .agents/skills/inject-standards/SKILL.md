---
name: inject-standards
description: Load and merge global and project-specific coding standards into current context. Use when applying standards, patterns, or compliance requirements. Triggers on inject standards, load standards, standards, check patterns, apply patterns.
---

# Inject Standards

Load relevant Library standards into the current context. Resolve project-local
standards first, then user-global standards, and merge duplicates by standard key
with project-local files taking precedence.

## When to Use

- Starting implementation work and relevant coding standards should be loaded.
- Preparing a subagent prompt that must follow project patterns.
- Checking which standards apply to a task or file type.
- Loading specific standard documents by name or glob pattern.

## Usage

```text
# Auto-suggest from the current conversation.
inject-standards

# Explicit standard key.
inject-standards python-cli-patterns
inject-standards python/style

# Multiple keys.
inject-standards workflow/code-review release/changelog

# Glob patterns.
inject-standards python/*
inject-standards */test*

# Explicit context.
inject-standards --context="migration test compliance"
inject-standards --files="src/billing/*.py"

# Output mode.
inject-standards --mode=paths workflow/code-review
inject-standards --mode=refs python/style
inject-standards --mode=full release/changelog
```

## Standard Discovery

Scan these roots in order (first wins):

1. Tracked project source of truth: `docs/standards/` — versioned and copied into
   every worktree, so a dispatched agent can read it even though `.agents/` is
   gitignored per repo.
2. Project-local scratch: `.agents/standards/` (gitignored)
3. Library marketplace source layout: `standards/`
4. User-global: `~/.agents/standards/`

### Delivery guarantee (`--require`)

With no standards-injector hook, the orchestrator must prove a `requires_standards`
standard actually reached the worktree before dispatching an agent that cites it.
Pass `--require <id1,id2>`: if any id resolves in none of the roots above, the
runner prints the missing ids and the probed roots to stderr and exits `3` — it
never silently dispatches against a missing standard.

```
uv run python skills/inject-standards/runner.py --require seam-contract --mode=refs seam-contract
```

Support both Library layouts:

| Layout | Key | File |
|--------|-----|------|
| Flat standard | `adr-location` | `adr-location.md` |
| Folder-form standard | `python-cli-patterns` | `python-cli-patterns/python-cli-patterns.md` |
| Bundle member | `workflow/code-review` | `workflow/code-review.md` |

Also load `_triggers.yml` files when present in a bundle directory. They are
optional trigger metadata, not an index. Do not require `index.yml`; the current
Library install layout does not generate one.

## Merge Rules

| Scenario | Behavior |
|----------|----------|
| Standard exists only globally | Load the global file |
| Standard exists only project-locally | Load the project file |
| Same key exists in both roots | Load the project file |
| Folder-form and flat aliases both exist | Prefer folder-form when the requested key matches the folder name |

## Mode Selection

If no `--mode` is supplied:

1. Plan or skill-authoring context: `refs`
2. Delegated subagent prompt: `paths`
3. Otherwise: `full`

If the situation is genuinely ambiguous, ask the user which output mode they
want: `full`, `refs`, or `paths`.

## Auto-Suggest

When no explicit standard keys are supplied:

1. Build context from `--context`, `--files`, the user prompt, mentioned file
   paths, and currently opened files.
2. Score standard keys, descriptions, paths, and trigger metadata.
3. Return the top matches.

Scoring:

```text
Exact word match: +3
Token match:      +2
Substring match:  +1
Minimum score:    2
```

Keep auto-suggest focused: return at most three standards unless the user asks
for a broader scan.

## Validation

For every selected standard:

- The resolved file path must stay under one of the standards roots.
- The file must be Markdown.
- The file must exist.
- No `..`, absolute-path, or home-expansion path traversal is allowed in user
  supplied keys.

## Output

### `--mode=full`

```markdown
## Loaded Standards

### workflow/code-review
[Full content, truncated to the token budget if needed]

---

### release/changelog
[Full content]
```

### `--mode=refs`

```markdown
Add these references:

@.agents/standards/workflow/code-review.md
@~/.agents/standards/release/changelog.md
```

### `--mode=paths`

```markdown
## Standards
- /absolute/path/to/.agents/standards/workflow/code-review.md
- /absolute/path/to/.agents/standards/release/changelog.md
```

## Token Budget

- Auto-suggest: maximum three standards.
- Explicit keys: maximum ten standards unless the user asks for more.
- Maximum 2,000 characters per standard by default.
- Maximum 8,000 characters total by default.

## Error Handling

| Error | Message |
|-------|---------|
| No standards roots exist | `No Library standards are installed under .agents/standards or ~/.agents/standards.` |
| Invalid key | `Invalid standard key: <key>` |
| File not found | `Standard not found: <key>` |
| Glob no match | `Pattern '<pattern>' matched no standards. Available: <list>` |
| Path traversal | `Standard keys cannot contain absolute paths, ~, or .. segments: <key>` |

## Integration

This skill is used manually and by planning or orchestration workflows that need
standards loaded into context. For subagents, prefer `--mode=paths` so the
callee can read only the standards it needs.

## Implementation

The executable implementation of this skill is at `skills/inject-standards/runner.py`.
It supports all modes (`--mode=full|refs|paths`), `--context` and `--files` flags,
plus positional standard keys / glob patterns as documented in the Usage section above.

```bash
# Auto-discover with context filtering
python3 skills/inject-standards/runner.py --mode=full --context="migration python"

# Explicit standard keys (exact match)
python3 skills/inject-standards/runner.py --mode=paths adr-location python/style

# Glob patterns
python3 skills/inject-standards/runner.py --mode=full "python/*"

# Combine with --files for source-context auto-suggestion
python3 skills/inject-standards/runner.py --mode=full --files="src/billing/invoice.py"
```

### Security

The runner rejects symlinks whose realpath escapes the standards root, and rejects
standard keys containing `..`, leading `~`, or absolute paths. See SKILL.md
Validation section for the full path-traversal contract.

### Returncode contract

The runner exits 0 on success (including the "no standards installed" message).
Callers MUST gate on the returncode — silent failure suppression (`2>/dev/null`
without a `||` clause) is forbidden when standards loading is MANDATORY.

### Runner path resolution

When `INJECT_STANDARDS_RUNNER` env var is set, use that path. Otherwise resolve
relative to the caller's expected install location (e.g. `$(dirname
"$BEADS_RUNTIME")/inject-standards/runner.py`) and fall back to the
project-local `skills/inject-standards/runner.py`.

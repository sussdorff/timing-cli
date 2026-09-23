# Session Learning Capture

Shared capture semantics for substantive agent sessions. `session-capture` uses
these rules for non-coding work. `session-close` preserves the same semantics
inside its ordered coding finalization state machine.

## Capture Record

Capture a concise record that a later session can find and trust:

- **Result**: what changed, concluded, or was verified.
- **Decisions**: material choices and the reason for each choice.
- **Learnings**: reusable discoveries, including surprising constraints.
- **References**: repository project, optional Bead reference, agent type, and the required
  stable origin `agent-session:<harness>:<session-id>`.

Use one `session_summary` for the complete record. Every `ob save` uses
`--producer=<agent-or-skill>` and `--source-ref=agent-session:<harness>:<session-id>`.
Save a separate decision or
learning only when it remains useful outside the session summary. Do not capture
transient command output, credentials, or unverified speculation.

## Boundaries

- `session-capture` only extracts and persists knowledge. It does not integrate
  Git, mutate Beads, stop Docker, or clean worktrees.
- `session-close` owns coding finalization. Its `remember` stage must finish
  before `cleanup`; this standard does not create a second close workflow.

## Agent Prompt Guidance

The following prompt guidance applies when an agent itself must capture the
session before returning.

## When to Include

Add this instruction to agents that:
- Perform significant implementation, testing, or analysis work
- Make decisions or discoveries relevant to future sessions
- Run for more than a few minutes

Do NOT add to: micro-agents (constraint-checker, file-analyzer), focused validators
(playwright-tester, uat-validator, holdout-validator) that return structured reports,
or utility agents (git-operations, branch-synchronizer).

## Closing Instruction Template

Paste the following section at the end of an agent's prompt, adapted per agent type.

### For Implementation Agents (implementer)

```markdown
## Session Capture

Before returning your final response, save a session summary:

**Coding harness (Claude Code CLI)**: write the authored text to a file and invoke the helper through an argv-capable tool: `["uv", "run", "session-capture/scripts/save_capture.py", "--input-file", "<path>", "--project", "<project>", "--title", "<title>", "--harness", "<harness>", "--session-id", "<session-id>"]` (faster, no MCP round-trip and no shell interpolation).
**Mobile (claude.ai/iOS)** or when MCP tool is available: use `mcp__open-brain__save_memory`.

- **title**: Short headline of what was done (max 80 chars)
- **text**: 3-5 sentences covering: core result, what was unexpected or tricky, decisions made and why
- **type**: `session_summary`
- **project**: Derive from repo root (`basename $(git rev-parse --show-toplevel)`)
- **source_ref**: Required stable `agent-session:<harness>:<session-id>` origin
- **producer**: `<agent-name>`

Skip if your work was trivial (< 5 min, no discoveries worth preserving).
```

### For Orchestrator Agents (bead-orchestrator)

```markdown
## Session Capture

Before returning, save a session summary:

**Coding harness (Claude Code CLI)**: write the authored text to a file and invoke the helper through an argv-capable tool: `["uv", "run", "session-capture/scripts/save_capture.py", "--input-file", "<path>", "--project", "<project>", "--title", "<title>", "--harness", "<harness>", "--session-id", "<session-id>"]` (faster, no MCP round-trip and no shell interpolation).
**Mobile (claude.ai/iOS)** or when MCP tool is available: use `mcp__open-brain__save_memory`.

- **title**: "Bead {ID}: {outcome}" (max 80 chars)
- **text**: 3-5 sentences: bead outcome, subagents spawned and their results, key decisions, blockers or follow-ups
- **type**: `session_summary`
- **project**: Derive from repo root
- **source_ref**: Required stable `agent-session:<harness>:<session-id>` origin
- **producer**: `bead-orchestrator`
```

### Conditional Documentation Updater

`doc-changelog-updater` is not subject to this capture contract. Its owning
implementation loop records a typed completion result, commit, verification
evidence, and refreshed provider context before the final review. The agent does
not require open-brain access or a separate session summary.

## Agent Type Tagging

All session summaries and learnings saved to open-brain include a stable producer and
source reference. This enables:

- Filtering memories by producer: `ob search "..." --project "<project-name>"`
- Understanding which agent discovered a pattern or made a decision
- Tuning specific agents based on their historical learnings

## MCP Access

Agents need access to `mcp__open-brain__save_memory`. Configure via:

- **agent.md with frontmatter**: Add `mcpServers: [open-brain]`
- **agent.yml**: Add `mcp__open-brain__save_memory` to `tools` list

**CLI-based agents** (running inside Claude Code or Codex CLI harnesses) can use
`ob save` / `ob search` directly instead of requiring MCP access. Do NOT add
`mcpServers: [open-brain]` to coding harness agent frontmatter — use the `ob` CLI.

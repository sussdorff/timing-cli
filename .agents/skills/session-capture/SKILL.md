---
name: session-capture
description: >-
  use when: closing a non-coding or analysis session that produced durable
  decisions, discoveries, or learnings. Captures them to Open Brain without Git,
  Beads, Docker, worktree cleanup, or ccore Session Close.
requires:
  - skill:ob-cli
requires_standards: [workflow/agent-session-capture]
disableModelInvocation: true
---

# Session Capture

Capture durable session knowledge only. This is the lightweight neighbour of
`session-close`, not an alternate coding-finalization workflow.

## Inputs

- A short summary of the result.
- Material decisions, surprises, and reusable learnings.
- The repository project name when a repository was involved.
- A stable session identifier used as `agent-session:<harness>:<session-id>`.
  The resulting write uses `--source-ref=agent-session:<harness>:<session-id>`.

## Workflow

1. Read `workflow/agent-session-capture` and extract the summary, decisions, and
   learnings with its shared semantics.
   Use `scripts/parse_debrief.py` and `scripts/aggregate_debriefs.py` when a
   structured agent debrief is the available source.
2. Write the caller-authored capture text to a UTF-8 file. Invoke the helper through
   an argv-capable tool with one value per array entry, for example
   `["uv", "run", "scripts/save_capture.py", "--input-file", "<path>",
   "--project", "<project>", "--title", "<title>", "--harness", "<harness>",
   "--session-id", "<session-id>"]`. The helper invokes `ob` with an argv list,
   `--producer=session-capture`, and the required stable source reference; it never
   interpolates capture text into a shell command.
3. Save a separate decision or learning only when it is independently useful for a
   later search. Reuse the same source reference and identify the producing agent with
   `--producer`.
4. Report the Open Brain reference or the exact reason capture could not run.

## Exclusions

- Do not perform Git integration, commits, pushes, or branch operations.
- Do not claim, update, close, sync, or infer Beads.
- Do not stop Docker containers or clean worktrees.
- Do not invoke `ccore session-close`.

Coding delivery uses `session-close`, which retains the ordered
`stop -> contain -> finalize -> remember -> cleanup` state machine and its
memory-before-cleanup invariant.

## Tool-argv Shape

```json
["uv", "run", "scripts/save_capture.py", "--input-file", "<caller-authored-capture.txt>",
 "--project", "<project>", "--title", "<title>", "--harness", "<harness>",
 "--session-id", "<session-id>"]
```

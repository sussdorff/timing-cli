# Test Fixture: context-handoff

## Test 1 - File-backed handoff

**Input:** Use `$context-handoff` before I run `/clear`; no issue is active and the harness exposes session `thr_123`.

**Expected behavior:** Write only the resolver's absolute `data.path` ending in `.intake/context-handoff/thr_123.md` with every required context section and return a bootstrap sentence naming that exact absolute path.

**Pass criteria:** The ID is canonical, the path is ignored by Git, no timestamp fallback or extra documentation file appears, and the output does not call `/clear`.

## Test 2 - Active issue

**Input:** Use `$context-handoff` while the conversation and branch explicitly identify issue `cognovis/demo#12`.

**Expected behavior:** After an allowed Action Proposal, post one timestamp-headed `Context Handoff` comment with `ccore tracker comment cognovis/demo#12 --body ...`, leave the issue body unchanged, and return a bootstrap sentence naming `cognovis/demo#12` and its `html_url`.

**Pass criteria:** No `.intake` handoff is created and no other assigned issue is considered.

## Test 3 - Ambiguous issue state

**Input:** Several open, assigned issues exist, but this conversation identifies none.

**Expected behavior:** Ignore the open-issue set and use the file-backed route.

**Pass criteria:** No issue is selected or commented on.

## Test 4 - Missing session ID

**Input:** No issue is active and the harness exposes no canonical session ID.

**Expected behavior:** Stop with the resolver's actionable error and ask for the exact harness session ID.

**Pass criteria:** No file is written and no timestamp, UUID, or conversational guess is used.

## Test 5 - Repeated invocation

**Input:** Use `$context-handoff` again in the same session after its handoff file already exists.

**Expected behavior:** Observe `data.exists: true` and append a clearly separated new `Context Handoff` section to the same absolute path.

**Pass criteria:** Earlier handoff sections remain intact and no second file is created.

## Test 6 - Nested Claude session

**Input:** Claude Code exposes `CLAUDE_CODE_SESSION_ID` and its active-harness marker while inheriting a different `CODEX_THREAD_ID` from a parent process.

**Expected behavior:** Resolve the Claude session ID and report `source: CLAUDE_CODE_SESSION_ID`.

**Pass criteria:** The inherited Codex ID never names the Claude handoff file.

## Test 7 - Git-visible handoff path

**Input:** The target repository does not ignore `.intake/context-handoff/`.

**Expected behavior:** Stop with `HANDOFF_PATH_NOT_IGNORED` and identify the ignore rule needed.

**Pass criteria:** No conversation content is written to a Git-visible path.

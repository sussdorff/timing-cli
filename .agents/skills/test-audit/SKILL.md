---
name: test-audit
description: Audit test quality and resource cleanup in one repository, and repair on request.
disable-model-invocation: true
requires_standards: [workflow/test-quality]
---

# Test Audit

Take an existing suite that grew test-first and find out which of its tests still
protect behaviour. Audit reports; repair changes the suite. Both work on **one
repository or one bounded path set per invocation** — never a sweep across every
registered repository.

## Invocation

This is a command: a person names it, and nothing else starts it. Auditing a suite
reads every test in scope and is far too heavy to fire off the back of an ordinary
test edit, so both harnesses have implicit invocation switched off —
`disable-model-invocation: true` here, `policy.allow_implicit_invocation: false` in
[agents/openai.yaml](agents/openai.yaml).

```text
/test-audit                          audit the current repository
/test-audit audit src/billing        audit a bounded path set
/test-audit repair src/billing       audit, then repair under existing authorization
```

The first argument selects the mode and defaults to `audit`; the rest is the path
set. Harnesses that expose skills as slash commands take `/test-audit`; Codex takes
`$test-audit` (see its [skills documentation](https://developers.openai.com/codex/skills/)).
Where neither prefix is available, ask for the skill by name.

## Resolve the testing method first

The general method belongs to the installed `tdd` skill, not to this skill. Read its
`SKILL.md`, `tests.md` and `mocking.md` from the first root that exists, checking
project-local before global:

```text
<repo>/.agents/skills/tdd   <repo>/.claude/skills/tdd
~/.agents/skills/tdd        ~/.claude/skills/tdd
```

Read `codebase-design` from the same root set when a finding turns on where a seam
belongs. If no root has `tdd`, stop and report a setup failure. A missing skill is
not permission to invent a replacement testing policy.

Then read the repository's own `AGENTS.md`, `GLOSSARY.md` and standards. Domain, data
provenance, credential and safety obligations recorded there survive this audit
unchanged, and a textual contract can be one of them: in a repository whose product
is instructions, a test over Markdown may be the only oracle for a real contract.

## Scope and inventory

Name the target and the path set before reading tests. Then find the real entry
points — the runner, its scripts, its configuration, which paths are unit and which
need a service — and record them.

Inventory resources created or started by the tests: temporary files and directories,
compiled binaries, child processes, containers, test-built images, networks and
volumes. Record their owner, teardown and what remains after a run; disk-backed
temporary storage still needs cleanup.

Before running anything, find out what that runner does to the tree: caches and
coverage files it writes, snapshots it can rewrite under an update flag, database
rows or live calls the integration path makes. Take the baseline from the safest
bounded command that exists — the isolated unit path, snapshot updating off,
generated artifacts directed outside the target. If no invocation leaves the tree
alone, report the baseline as unverified rather than running it anyway. Baseline
failures, skipped tests and unreachable services are findings in their own right;
never report a suite green on the strength of tests that skipped.

Counts, runtimes and slowest-file lists are targeting aids that decide reading order.
They are never evidence that a test is worthless.

## The question

For every test you inspect, ask:

> Which concrete defect would make this test fail?

A named defect that a caller or user would care about means the test protects
behaviour. No such defect — the assertion recomputes the result the way the code
does, pins an intermediate shape nobody depends on, or asserts that the code is
shaped the way it is currently shaped — means the test is a finding.

Record each actionable finding with all five fields:

| Field | Content |
|---|---|
| Protected behaviour | What a user or caller would lose, or "none found" |
| Seam | The public boundary the test observes, with file and test name |
| Plausible defect | The concrete defect that would make it fail, or why none exists |
| Evidence | What you read, ran, mutated, or could not reach |
| Proposed disposition | keep, repair, replace, remove, or unresolved |

## Resource cleanup

A test owns the lifecycle of the resources it creates. Missing or ineffective
teardown is a **repair** finding even when its assertions protect useful behaviour.
The fix belongs in the owning test, shared fixture or test harness; moving binaries
from RAM to disk or changing the guest configuration leaves the leak unresolved.

In audit mode, inspect teardown and report leaks without deleting resources. In
repair mode, apply these requirements within the admitted path set:

- Give each run isolated temporary paths and resource identities. Register cleanup
  as soon as a resource is acquired, so partially failed setup is covered too.
- Use runner teardown, fixture finalizers or `try/finally` so cleanup runs after
  success, failed assertions and exceptions. A deletion after the last assertion
  alone is insufficient. Await asynchronous cleanup before the test run ends.
- Remove generated files, binaries and temporary directories after their last
  consumer finishes. For Node-based tests, use `rmSync` on the exact owned path in
  teardown or `finally`; use `{ recursive: true, force: true }` for an owned temporary
  directory. Terminate and wait for owned child processes before removing their files.
- Stop and remove test-created containers, then remove test-built images once their
  consumers are gone, and remove test-created networks and disposable volumes. Track
  exact IDs or unique run labels; preserve pre-existing images, shared caches,
  developer services and persistent data. Global Docker prune and broad filesystem
  deletion are not teardown.
- Make teardown safe after partial setup and repeated calls. Attempt the remaining
  cleanup steps if one fails, and report cleanup errors alongside the original test
  failure. Retained failure artifacts need an explicit diagnostic option with bounded
  retention and their paths reported; automatic cleanup is the default.

Verify an affected passing run, a controlled assertion or setup failure, and a repeat
run. Compare the owned paths and resource IDs before and after: no temporary binary,
directory, process, container, test-built image, network or disposable volume may
remain. Use disposable local fixtures for failure checks. A killed runner may bypass
finalizers; when that interruption is in scope, give its launcher an owned-resource
recovery path and verify it. If a path cannot be exercised, report it as unverified.

## Audit mode

An audit request changes nothing in the target. No edits, no commits, no deleted
fixtures, no re-run of a formatter, and no deliberate defect in the audited tree: a
finding that needs a mutation to settle it either gets that mutation in a disposable
copy outside the target, or stays `unresolved` for repair mode. Report the findings,
what you inspected, and what you could not inspect or run, and stop there.

## Repair mode

A repair request carries the authorization it already has into the repository's
established delivery workflow — its `intake` and `executive-pack` path, with the
review and verification gates that workflow already requires. When this skill is
invoked **inside** an already admitted delivery, the repairs are that delivery's test
work: do not open a second intake or a nested delivery for them.

Whatever carries the repairs onward — a work order, a delivery handoff, a repair set
— carries the audit with it: the target and path set, the report, and for every
admitted finding its disposition and the evidence behind it, with an explicit
instruction to apply `test-audit` while making the change. A handoff stripped of
those loses the constraints that made the dispositions safe, and the implementer
re-decides them blind.

Dispositions are earned by behavioural evidence, not by a quota:

- **Keep** anything uncertain. A test whose protected behaviour you cannot rule out
  stays, and the finding stays `unresolved` in the report.
- **Repair** a test that protects real behaviour through the wrong observation: move
  it to the public seam, replace a recomputed expectation with an independent known
  value, drop the internal mock.
- **Replace** a test whose behaviour deserves protection at a different seam. The
  replacement lands before the original goes.
- **Remove** on one of two grounds. A **duplicate** claim names the stronger retained
  test at the same seam that still fails when the behaviour breaks; if you cannot name
  it, the test stays. A test that observes **no product behaviour or contract at all**
  — it compares a local constant with itself, or asserts only that the code is shaped
  the way it is currently shaped — goes on the evidence that nothing it touches can
  regress, and has no survivor to name. Uncertain tests, unique regression tests and
  meaningful textual-contract tests stay under either ground. There is no deletion
  target to hit.

Targeted mutation is how you settle a disputed case: break the behaviour, confirm the
named survivor fails, restore the code exactly. It belongs in the tree your repair
already owns, or in a disposable copy — never in a tree you are only auditing. Use it
where the argument is actually in doubt; it is selective evidence, not a gate every
test must pass.

Restore every temporary defect before moving on, and prove the restore by re-running
the suite, not by diffing the file. A restored source can still run as the mutant:
`__pycache__`, a build output directory or a watch-mode bundle keeps the mutated
bytecode when the edit and the restore land inside the same timestamp granularity,
and the stale artifact then reads as a real result. Clear the cache, re-run, and only
then trust the outcome. Touch nothing outside the files your own change owns; other
agents may be working in the same tree.

When a test fails because the product is wrong, the contract is ambiguous, or a
service is unavailable, report that. Loosening the assertion to reach green hides a
defect and is not a repair.

## Report

Close with the target and path set, the entry points and baseline you observed, the
findings in the table format above, and an explicit limitations section: what you did
not read, could not run, and left unresolved. In repair mode, add the kept-versus-
changed outcome for each finding and the checks you re-ran.
Include the resource inventory, cleanup repairs, before/after residue and failure-path
evidence; name any retained artifacts, cleanup errors or unverified teardown paths.

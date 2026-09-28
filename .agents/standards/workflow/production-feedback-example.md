# Production Feedback Example: Restic Backup Error Handling

This is a concrete walkthrough of the production feedback loop using a real signal from a PVS adapter server's feedback archives.

## The Signal

**Source**: `~/.claude/learnings/archive/pvs-adapter-x-server/feedback-extractions-CH2-16001.json`, item `fb-5e0b6ec2`
**Ticket**: CH2-16001
**Confidence**: 0.95
**Feedback type** (as classified by feedback-extractor): correction

> "okay. one more refinement loop.
>
> 0. on windows we should use the restic parameter --use-fs-snapshot which should hopefully not let us run into locked files that often.
> 1. when restic exits with warnings or errors, we should still continue our scripts.
> 2. the warnings or errors (e.g. the files which could not be transferred) should show up in our backup messages.
>
> So the idea is we continue our scripts to note the backup as succeded with warnings or failed"

## Step 1: Classify the Signal

Apply the three decision rules:

**Question 1: Does the service currently match its spec?**

The restic backup integration was implemented to spec. It calls restic and treats any non-zero exit code as a failure, stopping the script. This is exactly what the spec said. → Service matches spec.

**Question 2: Does the spec address this situation at all?**

The original backup spec contemplated two states: success (restic exits 0) and failure (restic exits non-zero, stop everything). It never contemplated:
- Locked files producing restic warnings (exit code 1, partial success)
- Continuing execution after a non-zero exit
- Surfacing warning-level information in backup messages
- A "success-with-warnings" state as a distinct outcome

→ **Specification Gap.** The spec simply never handled nuanced exit states.

**Question 3** does not apply — we stopped at Step 2.

## Step 2: Locate the Affected Spec

The backup functionality was implemented in the pvs-adapter-x server restic backup bead. The original spec's `intent` only defined binary success/failure. The `contracts` section defined the restic call but not the exit code handling policy.

## Step 3: Spec Amendment

The gap requires extending the spec in two areas:

1. **intent**: Add scope for nuanced backup outcome states
2. **contracts**: Define what happens on restic warning-level exits (exit code 1 with `--use-fs-snapshot` on Windows)

Amended intent (addition):
> Scope IN: Three backup outcome states — success (exit 0), success-with-warnings (exit 1, restic warnings only), failed (unrecoverable error). On Windows, use `--use-fs-snapshot` to minimize locked file events. Warnings must surface in backup messages regardless of script continuation.

## Step 4: Create the Issue

The author validates the body with the intake skill's `scripts/issue-author-check.py
--body-file <file>` and creates it with `ccore tracker create --repo <prefix> --body-file <file>`:

```markdown
Type: task
Review-Risk: none

## Intent

Goal: Backups report success, success with warnings, or failure after restic runs
Scope-In: Three backup outcome states, restic warning exits, the Windows `--use-fs-snapshot` parameter, backup messages.
Scope-Out: Backup scheduling and retention.

## Signal Origin

Source: feedback-extractions-CH2-16001.json, item fb-5e0b6ec2
Signal type: Specification Gap
Original feature issue: unknown (restic backup integration)

## What the Signal Shows

User feedback during CH2-16001 (verbatim):

> when restic exits with warnings or errors, we should still continue our scripts.
> the warnings or errors (e.g. the files which could not be transferred) should show up in our backup messages.
> So the idea is we continue our scripts to note the backup as succeded with warnings or failed

Also: "on windows we should use the restic parameter --use-fs-snapshot"

## Why This Is a Specification Gap

The original backup spec defined two outcomes: success (exit 0) or failure (stop the script).
It never covered a restic exit with warnings (partial success due to locked files) after which
the backup should continue and be reported differently. The spec has a gap; the implementation
matched it.

## What the Spec Needs

1. Three outcome states: success, success with warnings, failed.
2. The Windows parameter `--use-fs-snapshot` to reduce locked-file events.
3. On a warning exit the script continues, collects the warning output and reports it.
4. A message format that distinguishes the three states for operators.

## Acceptance Criteria

1. A restic run ends in exactly one of the states success, success with warnings, or failed.
2. Windows restic calls pass `--use-fs-snapshot`.
3. Backup messages list the restic warnings and errors of the run.
4. A restic warning exit does not stop the backup script.
5. Runs that exit 0 or fail unrecoverably report the same outcome as before.

## Means of Compliance

| AC | Criterion | MoC | Evidence |
|---|---|---|---|
| AC1 | Three outcome states | unit | backup outcome state tests |
| AC2 | Windows snapshot parameter | unit | restic command builder test |
| AC3 | Warnings in backup messages | unit | backup message format test |
| AC4 | Warning exit continues | integ | warning exit script test |
| AC5 | Existing outcomes preserved | unit | backup outcome regression tests |
```

## Classification Summary

| Attribute | Value |
|-----------|-------|
| Signal source | CH2-16001, item fb-5e0b6ec2 |
| Signal type | Specification Gap |
| Issue type | task |
| Confidence | 0.95 |
| Spec area | intent + contracts (exit code policy) |
| Priority | High (affects backup reliability reporting) |

## What Made This a Gap (Not Drift or Regression)

- The implementation correctly matched its spec — nothing was broken
- The spec never mentioned nuanced exit codes or warning states
- Users discovered the gap through real-world use (locked files in production)
- The fix requires amending the spec, not re-running the factory with the old spec

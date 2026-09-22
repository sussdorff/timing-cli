# Production Feedback Example: Restic Backup Error Handling

This is a concrete walkthrough of the production feedback loop using a real signal from the charly-server feedback archives.

## The Signal

**Source**: `~/.claude/learnings/archive/charly-server/feedback-extractions-CH2-16001.json`, item `fb-5e0b6ec2`
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

The backup functionality was implemented in the charly-server restic backup bead. The original spec's `intent` only defined binary success/failure. The `contracts` section defined the restic call but not the exit code handling policy.

## Step 3: Spec Amendment

The gap requires extending the spec in two areas:

1. **intent**: Add scope for nuanced backup outcome states
2. **contracts**: Define what happens on restic warning-level exits (exit code 1 with `--use-fs-snapshot` on Windows)

Amended intent (addition):
> Scope IN: Three backup outcome states — success (exit 0), success-with-warnings (exit 1, restic warnings only), failed (unrecoverable error). On Windows, use `--use-fs-snapshot` to minimize locked file events. Warnings must surface in backup messages regardless of script continuation.

## Step 4: Create the Bead

The author validates the body and calls `bd create --body-file <file>` with this structured payload:

```yaml
title: "[GAP] Backup: nuanced restic outcome states (success-with-warnings)"
type: task
context: |
  ## Signal Origin
Source: feedback-extractions-CH2-16001.json, item fb-5e0b6ec2
Signal type: Specification Gap
Original feature bead: (restic backup integration bead)

## What the Signal Shows
User feedback during CH2-16001 (verbatim):

'when restic exits with warnings or errors, we should still continue our scripts.
the warnings or errors (e.g. the files which could not be transferred) should show up in our backup messages.
So the idea is we continue our scripts to note the backup as succeded with warnings or failed'

Also: 'on windows we should use the restic parameter --use-fs-snapshot'

## Why This Is a Specification Gap
The original backup spec defined binary outcomes: success (exit 0) or failure (stop script).
It never contemplated that restic can exit with warnings (partial success due to locked files)
while the overall backup operation should continue and be reported differently.
This situation was not anticipated — the spec has a gap, not the implementation.

## What the Spec Needs
1. Define three outcome states: success, success-with-warnings, failed
2. Add Windows-specific parameter: --use-fs-snapshot to reduce locked file events
3. Define behavior on warning exit: continue script, collect warning output, surface in message
  4. Define message format that distinguishes the three states for operators
acceptance_criteria:
  - Three backup outcome states are defined and implemented
  - Windows restic calls use --use-fs-snapshot
  - Backup notifications surface restic warnings and errors
  - Warning exits do not abort the script
  - Existing success and failure behavior is preserved
means_of_compliance:
  - acceptance_criterion: Three backup outcome states are defined and implemented
    method: test
  - acceptance_criterion: Windows restic calls use --use-fs-snapshot
    method: test
metadata:
  intent: Extend backup outcomes with a warning state and Windows snapshots
  component: backup
  signal_source: CH2-16001
  signal_type: gap
  effort: 3
```

## Classification Summary

| Attribute | Value |
|-----------|-------|
| Signal source | CH2-16001, item fb-5e0b6ec2 |
| Signal type | Specification Gap |
| Bead type | task |
| Confidence | 0.95 |
| Spec area | intent + contracts (exit code policy) |
| Priority | High (affects backup reliability reporting) |

## What Made This a Gap (Not Drift or Regression)

- The implementation correctly matched its spec — nothing was broken
- The spec never mentioned nuanced exit codes or warning states
- Users discovered the gap through real-world use (locked files in production)
- The fix requires amending the spec, not re-running the factory with the old spec

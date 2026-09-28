# Conditional intake modes

## Bug reports

Use bug-triage in the current authoring session for evidence and investigation;
do not delegate issue authoring. A single clear bug-fix request needs no routine
confirmation. Missing reproduction does not stop safe independent investigation.
Describe unconfirmed observations honestly and ask only for decisive missing facts.
File an investigation work order when that is the requested outcome; do not
fabricate a verified cause or failing test. Default to the reported failing case
as one AC with the smallest focused regression check as MoC. Add an adjacent
control only for a plausible regression; keep implementation constraints in Scope-Out.
Keep full suites, unrelated systems, customer data, E2E/UAT, deployments, health checks
and push preflight out of bug AC/MoC unless the reported defect itself crosses that
boundary.

## Multiple outcomes and initiatives

An implementation workplan is not a set of separate requirements. Default to one
issue per coherent outcome. A shared release unit, verification boundary, or
producer/sole-consumer pair is presumed one issue. Separate only for independent
value/verifiability, different risk or verification environment, or real parallelism;
record that rationale against workflow/issue-intake.

For genuine multiple outcomes, show proposed boundaries and ask only unresolved
merge/split, ownership or dependency decisions. Existing explicit approval remains
valid. Author each approved body inline. There is no portfolio issue type; link
independently deliverable issues with a `Blocked by: <full issue URL>` line in the
dependent body before it is created, or add the line through `ccore tracker update`
after the same author-check. Do not create issues merely to represent sequential
implementation steps.

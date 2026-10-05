# TDD Discipline

The red-green loop is owned by the installed `tdd` skill. Read it rather than a
Library copy: `SKILL.md`, `tests.md` and `mocking.md` under the first root that
exists, project-local before global.

```text
<repo>/.agents/skills/tdd   <repo>/.claude/skills/tdd
~/.agents/skills/tdd        ~/.claude/skills/tdd
```

It owns the rules of the loop (red before green, one vertical slice at a time,
refactoring outside the loop), what a good test is, where seams go, and the
anti-patterns. This file adds only the evidence obligation that is local here.

## Verified red is the evidence

A test for behaviour that does not exist yet, or for a defect you are fixing, is
evidence only once you have observed it fail for the reason you intend — a wrong
assertion result, not an import error or a collection error. Report a red you did not
observe as unverified rather than asserting it.

A test-only change around behaviour that is already correct is the other case, and it
carries no red. A repaired or replacement assertion may pass the moment it is written;
demanding a failure there would only invite breaking working code to manufacture one.
Its evidence is that the expected value comes from an independent source, and that a
plausible defect it now catches does make it fail. A preserved provenance or contract
assertion needs neither: it protects a contract that already holds.

## What does not need a test

Changes with no behaviour to observe — documentation, formatting, renames, dependency
bumps, configuration without a code path — are covered by running the existing suite.
There is no blanket rule that every acceptance criterion produces a new test; a
criterion discharged by review or by an existing test is discharged. State which
Means of Compliance each criterion uses and why.

Auditing or repairing a suite that already exists is the explicit-only `test-audit`
skill, which a person runs as `/test-audit`.

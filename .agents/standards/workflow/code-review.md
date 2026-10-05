# Code Review

What to look for in a diff is owned by the installed `code-review` skill, not by this
standard. This file holds only what is local to reviews in these repositories.

## The method lives in the `code-review` skill

Read it from the first root that exists, project-local before global:

```text
<repo>/.agents/skills/code-review   <repo>/.claude/skills/code-review
~/.agents/skills/code-review        ~/.claude/skills/code-review
```

It owns the two review axes — Standards (does the change follow what this repository
documents?) and Spec (does it implement what the work order asked for?) — and the smell
baseline that applies when a repository documents nothing. Read `codebase-design` from
the same root set when a finding turns on module depth, an interface or where a seam
belongs. If no root has `code-review`, that is a setup failure to report, not permission
to invent a checklist.

A reviewer inside a delivery applies that method itself and does not start the skill's
own sub-agents; `executive-pack` says so and owns the brief.

## Findings are hypotheses

Every finding, at every severity, is checked against the live code before it drives a
change. A finding that does not reproduce is withdrawn, not downgraded. See
[review-governance/finding-adjudication.md](../review-governance/finding-adjudication.md).

## The delivery owns the finding shape

Do not invent a severity scale or a report table here. Inside a delivery, the finding
fields, the severities and the triage into repair, defer or drop come from the
`executive-pack` skill and its `finding_triage.py`; a review that feeds the structured
review-output contract uses the categories in
[standards/types/review_output.py](../types/review_output.py).

## Scope of a review finding

A review reports on the change under review. Something wrong nearby but outside it is
reported, not fixed in passing, and
[orchestrator/scope-creep-policy.md](../orchestrator/scope-creep-policy.md) decides
whether it becomes part of the repair or its own work order.

## What a review does not cover

- Anything a linter or formatter already enforces.
- Whether the change runs. Tests passing is not verification; see
  [verification-discipline.md](verification-discipline.md).
- Test value in an existing suite, which is the explicit-only `test-audit` skill.

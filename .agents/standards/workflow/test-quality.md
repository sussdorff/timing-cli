# Test Quality

What counts as a test worth keeping is owned by the installed `tdd` skill, not by
this standard. This file holds only the constraints that skill does not cover and
that apply to every repository here.

## The method lives in the `tdd` skill

Read `SKILL.md`, `tests.md` and `mocking.md` of the installed `tdd` skill from the
first root that exists, project-local before global:

```text
<repo>/.agents/skills/tdd   <repo>/.claude/skills/tdd
~/.agents/skills/tdd        ~/.claude/skills/tdd
```

It owns seams, behaviour over implementation, the tautological and
implementation-coupled anti-patterns, the vertical-slice loop and the mocking
boundary. Do not restate those rules in a repository standard, an agent prompt or a
work order; reference the skill. If no root has it, that is a setup failure to
report, not permission to invent a replacement policy.

Auditing and repairing an existing suite is the `test-audit` skill, which a person
runs as `/test-audit`. It is explicit-only: recommend it when a suite needs the
review, and do not start one yourself.

## Environment independence

A test asserts nothing about the machine it runs on. No hardcoded home directories,
no fixed ports, no wall-clock or timezone assumptions, no hostnames, no
platform-specific path separators. Runner-specific isolation recipes live in
[Python test-suite upkeep](../python-cli-patterns/test-suite-upkeep.md#isolation) and
[TypeScript test-suite upkeep](../typescript/test-suite-upkeep.md#isolation).

## A skipped test is not evidence

A conditionally registered test passes green when it skips. Green-because-skipped
discharges no Means of Compliance; report it as a `test-quality` finding and name the
unreachable dependency. See
[seed-data-parity.md](seed-data-parity.md#companion-rule-skipped-integration-tests-are-not-evidence).

## Framework-specific standards

| Runner | Standard |
|--------|----------|
| pytest | [Python test-suite upkeep](../python-cli-patterns/test-suite-upkeep.md) |
| bun test / Vitest / node --test | [TypeScript test-suite upkeep](../typescript/test-suite-upkeep.md) |

These add runner operation — parallelism switches, isolation fixtures, subprocess and
lint scope — on top of the `tdd` skill. They do not carry a second value method.

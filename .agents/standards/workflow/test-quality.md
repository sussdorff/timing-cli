---
requires_standards:
  - python-cli-patterns/test-suite-upkeep
  - workflow
  - typescript/test-suite-upkeep
---

# Test Quality

What counts as a test worth keeping is owned by the installed `tdd` skill, not by
this standard. This file holds only the constraints that skill does not cover and
that apply to every repository here.

## The method lives in the `tdd` skill

Read `SKILL.md`, `tests.md` and `mocking.md` of the installed `tdd` skill from the
first root that has a readable `SKILL.md`, project-local before global:

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

## Declared test units

The `tdd` skill tests at a pre-agreed seam but leaves open where that seam lies.
A repository can settle it once by declaring its test units. Without a
declaration nothing here applies: the `tdd` seam rules hold as before and nothing
new is required.

### Declaration

The repository's `AGENTS.md` names one JSON declaration file; its path is the
repository's choice. All paths in it are repository-relative POSIX paths.

```json
{
  "modules": [
    {"name": "proposals", "dir": "src/proposals", "entry": "src/proposals/index.ts"}
  ],
  "ports": [
    {
      "name": "storage",
      "port": "src/storage/port.ts",
      "contract": "src/storage/contract.ts",
      "adapters": [
        {"name": "memory", "path": "src/storage/memory.ts", "in_memory": true},
        {"name": "postgres", "path": "src/storage/postgres"}
      ]
    }
  ]
}
```

- `modules`: each has a unique `name`, a `dir` and an `entry` file inside that
  `dir`. Module dirs do not nest. The entry exports by name; it does not widen
  itself with wildcard re-exports of internals.
- `ports` (optional): `port` is the port's interface file or module entry,
  `contract` its contract suite, and each adapter `path` a file or directory. At
  least one adapter is marked `"in_memory": true`.
- `aliases` (optional): TS/JS import prefixes mapped to repository-relative
  directories, such as `{"@/": "app/"}`, so aliased imports can be checked.
- `import_roots` (optional): repository-relative directories Python absolute
  imports resolve against; the default is `["", "src"]`, where `""` is the
  repository root.

A declared entry or port is the seam the `tdd` skill tests at. In such a
repository, do not pick the nearest function as the seam.

### Boundary

Code outside a module, tests included, imports the module only through its
entry; a module mock from outside targets the entry. A test inside a module that
imports a file behind the entry states why, in a line of that test file:

```text
test-boundary-exception: <reason>
```

The repository's dependency checker (dependency-cruiser, import-linter or an
equivalent) generates its boundary rules from the declaration and enforces them
for production code and tests alike. Tests are not excluded from its scope, and
static, dynamic and type-only imports all count. An invalid declaration fails the
check instead of silently dropping a boundary. MIRA's `app/backend/modules.json`
with one generated dependency-cruiser rule per module is one implementation.

### Ports and adapters

Each port has one contract suite, written against the port, that runs against
every adapter, the in-memory adapter included. Callers' tests use the in-memory
adapter through the port instead of mocking internals.

Only the contract suite, its run against an adapter and the tests inside an
adapter's own path import a real adapter. Every other test imports the port and
the in-memory adapter; importing a real adapter from it reaches past the port.

`test-audit` reads the declaration and reports, per module and port, tests that
bypass a boundary and adapters without a contract suite run.

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

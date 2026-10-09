---
description: TypeScript Test Suite Upkeep
requires_standards:
  - python-cli-patterns/test-suite-upkeep
  - toolchains/node
---

# TypeScript Test Suite Upkeep

A TypeScript repository built test-first accumulates one test per RED step.
This standard carries the runner operation of the
[Python test-suite upkeep standard](../python-cli-patterns/test-suite-upkeep.md)
over to `bun test`, vitest and `node --test` suites and adds only what differs
in TypeScript. New code uses `bun test` (see the
[Node rule](../toolchains/node.md)); the vitest and `node --test` sections
cover existing suites until they move. The measured pilot is
[reference-data-adapter PR #68](https://git.cognovis.de/cognovis/reference-data-adapter/pulls/68)
(rda#65).

## Value Review

The keep and delete decision is the `test-audit` skill's procedure, including the
rule that a "duplicate" claim names the stronger retained test at the same seam.
The installed `tdd` skill owns the general testing method and holds no audit rules.
A value review is an explicit `/test-audit` run a person asks for, not something an
agent starts while editing a test. This standard adds only what differs in
TypeScript.

`test-audit` is distributed by the `cognovis-daily` Workspace. Where a repository's
Workspace does not carry it, it has to be installed explicitly; report the missing
command as a setup gap rather than installing it, running it unasked, or rebuilding
its dispositions here.

Review the suite at least once per release train, and sooner when the serial unit
suite exceeds about one minute or one file exceeds about 3 s.

As part of an authorized repair in the existing delivery, kept tests move into files
named after the behaviour they protect rather than after the review round that
produced them, and every document that lists test files by path — an architecture
inventory, for instance — is updated with them. An audit-only review recommends those
moves in its report; it does not make them.

```text
proposed: delete "rejects a draft with rows" (duplicate)
rejected: no test at the same seam fails when the row check is removed;
          the test is the only oracle and stays (rda#65)
moved:    src/server/review-round-3.test.ts -> src/server/idle-timeout.test.ts
```

## Unit and Integration Separation First

Tests that need Aidbox, Postgres, Docker or the network share external state.
Keep them out of the unit path before you parallelise the unit suite, whether
or not the service is reachable. Give them their own path and script:

```json
{
  "scripts": {
    "test": "bun test --parallel src/",
    "test:serial": "bun test src/",
    "test:integration": "bun test integration/"
  }
}
```

If integration tests must stay next to the code, gate them on an explicit
opt-in that only the integration job sets, for example
`describe.skipIf(process.env.RUN_INTEGRATION !== "1")`, and run that job
serially. Do not gate on the service URL: where it is set, the tests would
run inside the parallel unit suite. The unit suite must pass on a machine
without any of these services.

## Parallel Execution

Each runner has its own switch. Do not copy the bun snippet into a vitest or
`node --test` repository. Checked on 2026-09-25 against Bun 1.4.2,
vitest 5.0.1 and Node 24.21.0 (`--help` of each CLI).

**bun.** `--parallel` runs files in worker processes, one per core by default,
and implies `--isolate`. It works in Bun 1.3.14 and 1.4.2. Use the `test` and
`test:serial` scripts shown above.

**vitest.** Files run in parallel by default. Choose the pool explicitly;
`forks` is the default and the safer choice for native modules, `threads`
starts faster.

```ts
// vitest.config.ts
import { defineConfig } from "vitest/config";

export default defineConfig({
  test: { pool: "threads", fileParallelism: true },
});
```

Debug serially with `vitest run --no-file-parallelism`.

**node --test.** By default each test file runs in its own process and files
run concurrently. Set the concurrency explicitly when the default is too
high for shared resources:

```json
{
  "scripts": {
    "test": "node --test --test-concurrency=4 'test/**/*.test.js'",
    "test:serial": "node --test --test-concurrency=1 'test/**/*.test.js'"
  }
}
```

A test that fails only in parallel shares state (a port, a path, the home
directory or `process.env`). Fix the sharing; do not move the test to the
serial script.

## Sleep Rule

No test waits a fixed 1 s or more. Inject a short configured timeout instead
of waiting for the production default, or use fake timers:

- bun: `jest.useFakeTimers()` and `jest.advanceTimersByTime()` from
  `bun:test`, and `setSystemTime()` for the clock
- vitest: `vi.useFakeTimers()` and `vi.advanceTimersByTime()`
- node: `t.mock.timers.enable({ apis: ["setTimeout"] })` and
  `t.mock.timers.tick()`

```ts
import { expect, jest, test } from "bun:test";

test("retry fires after the backoff", () => {
  jest.useFakeTimers();
  const retry = scheduleRetry({ backoffMs: 30_000 });
  jest.advanceTimersByTime(30_000);
  expect(retry.attempts).toBe(1);
  jest.useRealTimers();
});
```

A proof against a real listener keeps a small configured value. Split it into
one fast test that the configured value reaches the server, one bounds check,
and one short real-listener test.

## Isolation

The reasoning is in the
[Python isolation section](../python-cli-patterns/test-suite-upkeep.md#isolation).
In TypeScript:

- listen on port 0 and read the assigned port, never a fixed port
- create temp directories with `mkdtemp` under `os.tmpdir()`
- redirect `HOME` and `XDG_CONFIG_HOME`, `XDG_DATA_HOME`, `XDG_STATE_HOME`
  and `XDG_CACHE_HOME` into the temporary home
- restore every `process.env` change in `afterEach`
- set `GIT_CONFIG_GLOBAL=/dev/null` for tests that run real git

```ts
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { afterEach, beforeEach } from "bun:test";

let home: string;
const saved = { ...process.env };

beforeEach(async () => {
  home = await mkdtemp(join(tmpdir(), "test-home-"));
  process.env.HOME = home;
  process.env.XDG_CONFIG_HOME = join(home, ".config");
  process.env.XDG_DATA_HOME = join(home, ".local", "share");
  process.env.XDG_STATE_HOME = join(home, ".local", "state");
  process.env.XDG_CACHE_HOME = join(home, ".cache");
  process.env.GIT_CONFIG_GLOBAL = "/dev/null";
});

afterEach(async () => {
  process.env = { ...saved };
  await rm(home, { recursive: true, force: true });
});

// const server = Bun.serve({ port: 0, fetch }); use server.port
```

Two Bun traps, checked on Bun 1.4.2: `os.homedir()` ignores a `HOME` change
made at runtime, and `Bun.spawn` without an `env` option does not see runtime
`process.env` changes (`node:child_process` does). Let code under test take
its home directory from `process.env.HOME` or a parameter, and pass
`env: { ...process.env }` to `Bun.spawn` explicitly.

## Pre-push Hook

A tracked hook gives feedback before the push. It runs typecheck and the
parallel suite:

```sh
#!/bin/sh
# .githooks/pre-push
set -e
bun run typecheck
bun run test
```

Git skips a hook that is not executable, so commit it with mode 100755:

```sh
chmod +x .githooks/pre-push
git update-index --chmod=+x .githooks/pre-push
```

Each clone enables it once with `git config core.hooksPath .githooks`. The
hook is per clone and can be skipped with `--no-verify`, so CI remains the
merge gate. Do not remove CI unit jobs because the hook exists.

## Pilot Learnings (rda#65)

Measured in [PR #68](https://git.cognovis.de/cognovis/reference-data-adapter/pulls/68)
(candidate a69fe0d, Bun 1.4.2, 8 cores):

| | Before (48be181) | After |
|---|---|---|
| Tests | 1122 (1111 pass, 11 skip), 104 files | 1097 (1086 pass, 11 skip), 116 files |
| Parallel `bun test --parallel src/` | 11.27 s | about 4.9 s |
| Serial `bun test src/` | 21.76 s | about 14.5 s |
| Slowest file | idle-timeout test 11.11 s | idle-timeout test 4.62 s |

- Seven repair-round files held 186 tests: 161 kept, 25 deleted (21
  duplicates, 4 implementation-detail pins). Most were real invariants in
  badly named files. The main gains came from removing an 11 s sleep and from
  parallel execution.
- Review showed that two "duplicates" were the only oracles for their
  behaviour (a draft with rows, the exact 200,000 volume bound). Both were
  restored and proven by mutation RED.
- Bun checks idle sockets only about every 4 s, so a real-listener
  idle-timeout proof cannot drop below about 4.5 s. That file was accepted
  above the 3 s target.
- Moving tests exposed a WeakRef assertion that failed in 3 of 8 serial runs
  because of conservative stack scanning. Call `Bun.gc(true)` up to five
  times before asserting; a retaining mutant must still fail.
- Each extra file costs about 0.03 s of startup; 12 were negligible.
- In a scratch clone with `core.hooksPath=.githooks`, a failing test blocked
  `git push` to a local bare remote. CI runs the parallel suite in the Docker
  test image (Bun 1.3.14) without flakes.

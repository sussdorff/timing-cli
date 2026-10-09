---
domain: toolchains
description: Toolchain currency for every Cognovis repository - latest Bun, Node only as a Bun migration candidate, Python 3.14+ on its latest patch with the latest uv, CI setup actions on the latest tool, stateful service images on the latest release of their major line, and the bundled check_toolchain_versions.py check.
---

# Toolchains

> **Scope**: Every Cognovis repository that builds or tests with Bun, Node,
> Python or uv, or runs stateful service images. Language conventions stay in
> the `typescript` and `python` standards. Those standards link here for the
> runtime versions.

Released artifacts stay pinned: lockfiles, image digests in a release manifest,
and base-image digests between rotations. "Latest" applies to what the next
build uses. A release image pins the digest that the latest release resolved to
at its last base build or rotation. A release image without a pinned base is
not allowed.

## What This Standard Covers

| File | Topic |
|------|-------|
| [bun.md](bun.md) | Rule 1: Bun is always the latest release, in CI, `package.json`, version files, images and on hosts |
| [node.md](node.md) | Rule 2: Bun replaces Node as runtime and test runner; where Node remains it runs the latest LTS |
| [python.md](python.md) | Rule 3: Python 3.14 minimum on the latest patch of its minor line; uv always the latest release |
| [service-images.md](service-images.md) | Rule 5: stateful service images on the latest release of their own major line |
| [check.md](check.md) | `scripts/check_toolchain_versions.py`: what it scans, statuses, exit codes, lookups and overrides |

## Core Rules

1. Bun is the latest release everywhere.
2. Node is a Bun migration candidate. New TypeScript code uses Bun as its
   runtime and `bun test` as its test runner. Node remains only where a
   third-party tool requires it, and there it runs the latest LTS.
3. Python is at least 3.14, always on the latest patch of the minor line in
   use. It moves to a new minor once the dependencies support it. uv is always
   the latest release.
4. CI setup actions (`setup-bun`, `setup-python`, `setup-uv`, `setup-node`)
   request the latest tool version, never a fixed old one: `latest`, or for
   `setup-python` a minor line together with `check-latest: true`. The check
   fails an explicit older version and reports a step that omits the version
   (or `check-latest`) as an `implicit` note, which the rollout fixes.
5. Stateful service images (Postgres, Aidbox, Keycloak and similar) use the
   latest release of their current major line. Each major upgrade is deliberate
   and gets its own work order, so a tag that names no major line (`latest`,
   `edge`, a variant only) is not allowed.

`scripts/check_toolchain_versions.py` enforces rules 1, 3, 4 and 5 and reports
rule 2 without failing. A repository runs it from its tracked pre-push hook and
as a CI step; see [check.md](check.md).

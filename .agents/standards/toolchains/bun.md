# Bun

All Cognovis TypeScript code builds, tests and ships on the latest released Bun.
There is no fixed Bun pin (product owner decision, 2026-10-08: track latest).

Reason: on 2026-10-07 one release chain ran three Bun versions. Product CI used
`setup-bun` without a version and took 1.4.2, a developer host still had 1.3.14
and failed the pre-push gate, and a gateway release base
`oven/bun:1@sha256:e10577…` was Bun 1.3.14. The shipped gateway had upload bugs
that Bun 1.4.2 had already fixed.

| Place | Rule |
|-------|------|
| CI `setup-bun` steps | Set `bun-version: latest`. An older number, or a `bun-version-file` with an older pin, fails the check. A step without `bun-version` follows setup-bun's default: the check reports it as an `implicit` note, and the rollout sets `bun-version: latest`. |
| `package.json` | `packageManager` does not pin an older Bun (`bun@X`). `engines.bun` and a `bun` npm dependency admit the latest release (`>=1.1` is fine, `~1.3.0` is not once 1.4 is out). |
| `.bun-version`, `.tool-versions`, mise configs | No Bun version older than the latest release, including every fallback version an entry lists. `latest` is fine. |
| Dockerfile and Compose, development and CI | Floating Bun tags are fine: `oven/bun:latest`, `oven/bun:1`, variant tags such as `oven/bun:1-alpine`. |
| Release images | The base is pinned by an immutable digest. Every base build or rotation resolves the latest Bun tag and pins that digest. The check compares the digest with the ones the registry lists for the tag, for a floating tag (`oven/bun:1@sha256:…`) and a full version tag (`oven/bun:1.4.2@sha256:…`) alike. Between rotations the check fails once the tag moves, and that failure is the signal to rotate. |
| Developer and fleet hosts | Updated with `bun upgrade`, or with the fleet's latest-Bun installer. Never installed at a fixed version. |
| Documentation | Says "the latest released Bun" instead of a version number. Dated evidence such as "checked on Bun 1.4.2 on 2026-10-08" is fine. |
| `@types/bun` | A type package, not a runtime pin. It stays current through normal dependency updates. The check does not judge it. |

An image tag is judged at its own precision. `1.3.14` fails once a newer
release is out. `1.3` fails once the latest is outside 1.3.x. `1` fails only on
a new major.

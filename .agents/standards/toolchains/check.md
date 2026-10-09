# Toolchain Check

`scripts/check_toolchain_versions.py` ships with this standard and needs only
the Python 3 standard library (any `python3`, no uv; TOML validity is checked
only on Python 3.11 or newer, see below). In a consumer repository
the installed copy runs from the repository's tracked pre-push hook and as a CI
step:

```text
python3 .agents/standards/toolchains/scripts/check_toolchain_versions.py [--root DIR] [--latest-version KEY=VERSION ...]
```

## What It Scans

It scans the files git lists under `--root` (tracked and untracked, not
ignored; default: the current directory). It skips `node_modules`, `.agents`,
`.claude`, `.codex`, `dist` and `vendor`.

| Source | Declarations |
|--------|--------------|
| `.github`, `.forgejo`, `.gitea` workflows, and `action.yml` of local actions under their `actions/` directories | `setup-bun`, `setup-python`, `setup-uv`, `setup-node` steps with their version and version-file inputs, setup-python `check-latest`, setup-uv `python-version`, `resolution-strategy` and `working-directory`; job `container:`/`image:` values; `node --test` in `run:` commands. Block and single-line flow style (`- {uses: …, with: {…}}`, quoted keys) are both read |
| `package.json` (any depth) | `packageManager: bun@…`, `engines.bun`, `engines.node`, a `bun` npm dependency, `node --test` scripts and scripts that run `node` directly |
| `pyproject.toml`, `uv.toml` | `requires-python`, `[tool.uv] required-version`, `required-version` |
| Version files | `.bun-version`, `.python-version`, `.nvmrc`, `.node-version`, `.tool-versions` (every listed version), mise configs (`mise.toml`, `.mise.toml`, `mise.local.toml`, `mise.<env>.toml`, `.config/mise/config.toml`; every listed version) |
| Dockerfiles, Compose files | `FROM` and `COPY --from=` (backslash continuations joined), Compose `image:` in block or flow style |

A `${{ … }}` expression in a setup input or in a judged image tag is not
evaluated. It becomes an `implicit` note. This includes a version-file path
(`python-version-file: ${{ matrix.version_file }}`) and a setup-uv
`working-directory`: the file they name is not read.

A Python range, in setup-python or `requires-python`, is judged against the
newest released minor line it admits, and has to admit the latest patch of
that line: `>=3.14 <3.15.2` is `range_excludes_latest` once 3.15.2 is
released. Only a range that admits every Python 3 from 3.14 on (`>=3.14`,
`^3.14`, `>=3.14,<4`) needs no lookup. Otherwise the admitted lines are looked
up from the lowest upwards, and the first line without a release yet (both
endoflife.date sources answer 404 or name only a prerelease) ends the walk.
So while 3.16 is unreleased, `>=3.14 <3.16.1` and `>=3.14,!=3.15.3,<3.17` are
both judged on 3.15, and the second fails once 3.15.3 is the latest. Any
other failure of a lookup stays `python_lookup_failed`.

On Python 3.11 or newer, where the standard library has `tomllib`, a
`pyproject.toml`, `uv.toml` or mise configuration that is not valid TOML is
one `unparseable` error entry, whether it is scanned directly or named as a
version file. An older `python3` has no TOML parser: the checker then reads
these files with a line scan, does not check that they are valid TOML, and
reports nothing for a declaration the scan cannot read.

Variables in image references are resolved before judging. In a Dockerfile,
`FROM` lines use the `ARG` defaults declared before the first `FROM`; an `ARG`
inside a stage applies only to that stage's `COPY --from=`, and a bare `ARG`
there takes over the global default. `${NAME:-default}` and `${NAME-default}`
take the default when the name has no value; Compose references always take
their inline default, because `.env` files and the shell environment are not
read. A variable left without a value on an image the check judges is an
`unparseable` error. Images the check does not judge are ignored, templated or
not; a templated `node` image is still a Node usage.

A setup step without a version input follows the action's default. The check
reports it as an `implicit` note instead of failing, because only an explicit
older declaration fails; the rollout sets `latest` (for setup-python, a minor
together with `check-latest: true`).

## Result

The result is a JSON envelope on stdout: `status`, `summary`, `data`, `errors`,
`next_steps`. `data.latest` maps each lookup the run resolved to its version,
for example `{"bun": "1.4.2", "python3.14": "3.14.8", "postgres:16-alpine": "16.15-alpine3.24"}`.
`data.declarations` lists every declaration with `file`, `line`, `kind`,
`value`, `status` and `detail`. An entry that is not `ok` also has a `reason`.
Node usages are part of `data.declarations`.

| Status | Meaning | Fails the run |
|--------|---------|---------------|
| `ok` | Follows the rule | no |
| `outdated` | `older_than_latest`, `range_excludes_latest`, `below_minimum`, `digest_not_latest`, `major_unpinned` (a stateful image tag without a major line) or `lowest_resolution` (setup-uv `resolution-strategy: lowest`) | yes (exit 1) |
| `implicit` | No version declared, setup-python without `check-latest: true`, an expression, a PyPy or GraalPy version, a value that is not a version (`workspace:*`), or a digest that cannot be resolved | no |
| `node_usage` | A Node usage, reason `bun_migration_candidate` | no |
| `error` | `unparseable` or `unreadable` (exit 1), or `<tool>_lookup_failed` (exit 2) | yes |

| Exit | Meaning |
|------|---------|
| 0 | Nothing outdated. Notes and Node usages are allowed. |
| 1 | At least one declaration is `outdated`, `unparseable` or `unreadable`. |
| 2 | A typed error: `bun_lookup_failed`, `uv_lookup_failed`, `python_lookup_failed`, `image_lookup_failed` or `digest_lookup_failed` while an explicit declaration needed that lookup, or `usage`. A repository without such a declaration never fails on a lookup. |

## Lookups and Overrides

Each lookup runs at most once per run, and only when a declaration needs it.

| Key | Source, then fallback |
|-----|-----------------------|
| `bun` | npm `bun/latest`, then the GitHub release `oven-sh/bun` |
| `uv` | PyPI `uv`, then the GitHub release `astral-sh/uv` |
| `python3.N` | endoflife.date `python/3.N.json`, then its v1 release API |
| `<image>:<line>[-<variant>]` | Docker Hub or Quay tag list of that line, at most 10 pages of 100; a listing still incomplete at that bound is `image_lookup_failed`. A PostGIS line is `<postgres major>-<postgis major>`, for example `postgis/postgis:16-3` |
| digest of a tag | Docker Hub or Quay tag API, for floating and full version tags alike, once the tag itself is current. Other registries, such as ghcr.io, give an `implicit` note for the digest |

`GITHUB_TOKEN` is sent when set, as a Bearer `Authorization` header, only
to the fixed `api.github.com` release URLs. A redirect keeps that header only
when it stays on the same scheme, host and port; a redirect to any other
origin, including an `http` downgrade, drops it. Prerelease versions never count as
the latest. `--latest-version KEY=VERSION` replaces one lookup, for offline
runs and tests, for example `bun=1.4.2`, `uv=0.12.23`, `python3.14=3.14.8` or
`postgres:16-alpine=16.15-alpine3.24`. `--latest X` is short for
`--latest-version bun=X`.

## Command Line

The command line is exactly `--root DIR`, `--latest-version KEY=VERSION`
(repeatable) and `--latest X`. There is no positional path, no `--no-network`,
no `--exclude`, no `--release-url` and no `--image-release-url`; each exits 2
`usage`. A wrapper changes to the repository root and runs the check without
arguments, or passes `--root`. Tests and offline runs use `--latest-version`
overrides, and the resolved versions are in `data.latest`.

- No positional path: `--root` already names the directory to scan.
- No `--no-network`: a lookup that a declaration needs and that cannot run
  already fails typed (exit 2), so the flag would add nothing.
- No release-URL overrides: they would let a caller redirect the lookups, which
  carry `GITHUB_TOKEN`, to an arbitrary host.
- No `--exclude`: it would let a repository hide declarations from the
  standard.

---
name: cognovis-forgejo
description: Inspect Forgejo Actions runs, logs and runners on git.cognovis.de using fgj. Excludes workflow mutation and publishing.
compatibility: {}
metadata: {}
---

# Cognovis Forgejo

Inspect git.cognovis.de Actions with `fgj`. `fj` lists tasks, not runs or logs.

## Default host

Without a configured default, `fgj` 0.5.0 falls back to `codeberg.org` outside a
primary git.cognovis.de checkout, including every linked worktree. It picks the host in
this order:

1. the `--hostname` flag;
2. `FGJ_HOSTNAME`;
3. the top-level `hostname:` key in `$HOME/.config/fgj/config.yaml`, read from `$HOME`
   even when `XDG_CONFIG_HOME` is set;
4. `FGJ_HOST`;
5. the origin host of the current checkout, detected only where `.git` is a directory
   (a primary checkout). It fails in every linked worktree, including T3 thread
   worktrees and `~/code/.worktrees`; a GitHub checkout detects `github.com`;
6. `codeberg.org`.

The top-level `hostname: git.cognovis.de` key is the harness-neutral default. Nothing
provisions it per host: cognovis/harness-cli#31 planned that, but no released
`harness bootstrap` step (`harness/v2026.10.1`) provisions it yet. Until the check below
passes, pass `--hostname git.cognovis.de` (and `-R owner/repo`) or set
`FGJ_HOSTNAME=git.cognovis.de`. `fgj auth login` rewrites the hosts file
(`$XDG_CONFIG_HOME/fgj/config.yaml` when set, else `$HOME/.config/fgj/config.yaml`) with
only `hosts:`; it drops the key when that is the same file. Because the key and
`FGJ_HOSTNAME` outrank remote detection, pass `--hostname` explicitly in a Codeberg or
GitHub checkout.

Whenever `FGJ_TOKEN` is exported, `FGJ_HOSTNAME` or `FGJ_HOST` is mandatory. With
`FGJ_TOKEN` set, an unconfigured host does not fail: fgj sends that token to the
fallback host, `codeberg.org`.

Check, with `FGJ_TOKEN` unset: `env -u FGJ_TOKEN fgj api /version` run from a directory
outside any checkout, such as `/tmp`, returns the git.cognovis.de Forgejo version.
`no configuration found for host codeberg.org` means the default is missing.

## Inputs

- `owner/repo` on `git.cognovis.de`, or a checkout whose `origin` is that host
- `fgj` auth for that host, or `FORGEJO_TOKEN` from `~/.config/cognovis/forgejo.env`

## Outputs

- Run list/view (API id + UI index), plaintext job logs via `jobs[].id`, visible runners

## Exclusions

- Dispatch, rerun, cancel, runner register, GitHub/`fj-ex`/`ccore fj`, Forgejo PyPI

## Workflow

1. Preconditions. `fgj auth status` lists `git.cognovis.de`, or load `set -a; source ~/.config/cognovis/forgejo.env; set +a` and export `FGJ_TOKEN` together with `FGJ_HOSTNAME=git.cognovis.de` (or `FGJ_HOST=git.cognovis.de`) without printing values; never export `FGJ_TOKEN` alone ([Default host](#default-host)). Done when the auth and the `fgj api /version` check pass.
2. Route via the table. Pass `-R owner/repo --hostname git.cognovis.de` outside a primary checkout of the repo, including in a linked worktree. Done when the command matches the task.
3. Logs only after [references/ids.md](references/ids.md): `GET /actions/runs/{run_id}/jobs` and use field `id`, never `task_id` or UI `#N`. Done when the log request used that `id`.
4. Verify: list `ID` is the API run id, `view` prints `Run: #N`, logs are `200 text/plain`, runners used `--visible`. Done when those facts are reported.

| Question | Command |
|---|---|
| Which runs exist? | `fgj actions run list` |
| What is this run? | `fgj actions run view <api-id> --verbose` |
| What did the job print? | `fgj api repos/<owner>/<repo>/actions/jobs/<job-id>/logs` |
| Which runners can take this repo? | `fgj actions runner list --visible` |
| Raw endpoint? | `fgj api` |

## Invariants

- `fj actions` is tasks/variables/secrets/dispatch only — not the run/log client
- UI `#N` = `index_in_repo`; list `ID` = API run id; verbose Job ID = `task_id`
- Empty repo-owned `runner list` is not "no runners"; inherited runners need `--visible`

## Do NOT

- Feed the UI number or verbose Job ID to the job-logs path
- Use `fj actions tasks`, `fj-ex`, host `.zst` files, or a `ccore fj` wrapper
- Print `FORGEJO_TOKEN` / `FGJ_TOKEN` or the `hosts:` section of `~/.config/fgj/config.yaml`

## Resources

| File | Purpose |
|------|---------|
| [references/ids.md](references/ids.md) | UI index, run id, task id, job id |
| [references/failures.md](references/failures.md) | Failure signatures |

---
name: cognovis-forgejo
description: Inspect Forgejo Actions runs, logs and runners on git.cognovis.de using fgj. Excludes workflow mutation and publishing.
compatibility: {}
metadata: {}
---

# Cognovis Forgejo

Inspect git.cognovis.de Actions with `fgj`. `fj` lists tasks, not runs or logs.

## Inputs

- `owner/repo` on `git.cognovis.de`, or a checkout whose `origin` is that host
- `fgj` auth for that host, or `FORGEJO_TOKEN` from `~/.config/cognovis/forgejo.env`

## Outputs

- Run list/view (API id + UI index), plaintext job logs via `jobs[].id`, visible runners

## Exclusions

- Dispatch, rerun, cancel, runner register, GitHub/`fj-ex`/`ccore fj`, Forgejo PyPI

## Workflow

1. Preconditions. `fgj auth status` lists `git.cognovis.de`, or load `set -a; source ~/.config/cognovis/forgejo.env; set +a` and export `FGJ_TOKEN`/`FGJ_HOST=git.cognovis.de` without printing values. Done when status or those variables are set.
2. Route via the table. Pass `-R owner/repo --hostname git.cognovis.de` outside the repo. Done when the command matches the task.
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
- Print `FORGEJO_TOKEN` / `FGJ_TOKEN`

## Resources

| File | Purpose |
|------|---------|
| [references/ids.md](references/ids.md) | UI index, run id, task id, job id |
| [references/failures.md](references/failures.md) | Failure signatures |

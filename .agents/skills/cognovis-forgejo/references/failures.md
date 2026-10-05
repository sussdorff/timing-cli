# Failure signatures

| Symptom | Meaning | Remedy |
|---|---|---|
| `fj actions` has only `tasks` / `dispatch` | fj 0.6.x has no run/log/runner commands | Use `fgj` |
| `resource does not exist` on `.../jobs/<n>/logs` | `<n>` is `task_id` or the UI index | Fetch `/actions/runs/<api-id>/jobs` and use field `id` |
| `404 page not found` on `.../jobs/<n>` | Same wrong id, or job metadata path not implemented | Jobs live under `/actions/runs/<api-id>/jobs` |
| `UnicodeDecodeError` / binary on run logs | `/actions/runs/<id>/logs` is a ZIP | Use per-job plaintext logs |
| `fgj actions run view --log` 404 | fgj passes `task_id` as job id | Bypass with `fgj api .../jobs/<job-id>/logs` |
| `run list -L N` returns more than N | `--limit` is ignored | Slice after fetch; do not trust `-L` |
| `run view --json` has `jobs: []` | JSON view omits jobs | Use `--verbose` or `/actions/runs/<id>/jobs` |
| `runner list` empty, jobs still run | Repo has no owned runner; org/instance runners are inherited | `fgj actions runner list --visible` |
| `fj actions dispatch` panics `Unknown variable: $ref` after trigger | Localization bug after a successful dispatch | Do not retry; confirm via `fgj actions run list` |
| `event` empty on `run view` | Dedicated run view drops event | `/actions/tasks` or run JSON `event` when present |
| `keys file not found` from `fj` | fj's own token store, not `forgejo.env` | Stay on `fgj`; do not mix stores |
| Interactive `fgj auth login` in a non-TTY agent | Login wants a prompt | `FGJ_TOKEN` + `FGJ_HOST=git.cognovis.de` from `forgejo.env` |
| `no configuration found for host codeberg.org` | Outside a primary git.cognovis.de checkout (for example in a linked or T3 worktree) fgj fell back to `codeberg.org`; no default host is set and `FGJ_TOKEN` is unset | `--hostname git.cognovis.de`; restore the top-level `hostname: git.cognovis.de` key in `$HOME/.config/fgj/config.yaml` (dropped by `fgj auth login` when it rewrites that file) or set `FGJ_HOSTNAME` |
| Codeberg error or version (for example `token is malformed`, `access token does not exist`) instead of git.cognovis.de | `FGJ_TOKEN` is exported without a host, so fgj sent the git.cognovis.de token to `codeberg.org` | Stop; set `FGJ_HOSTNAME=git.cognovis.de` or `FGJ_HOST=git.cognovis.de` with every `FGJ_TOKEN` export and report the token as exposed to codeberg.org |

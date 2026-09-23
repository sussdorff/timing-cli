# Forgejo Actions identifiers on git.cognovis.de

Four numbers look interchangeable. They are not.

| Number | Where it appears | Use it for |
|---|---|---|
| UI run index `#N` | Actions tab, `fgj actions run view` line `Run: #N`, tasks payload `run_number` | Talking to humans and the web UI |
| API run id | `fgj actions run list` column `ID`, `GET /repos/{owner}/{repo}/actions/runs/{id}` | `run view`, `run watch`, `/actions/runs/{id}` |
| Task id | Verbose `Job: name (ID: T)`, `/actions/runs/{id}/jobs` field `task_id`, `/actions/tasks` `workflow_runs[].id` | Runner task records only |
| Job id | `/actions/runs/{id}/jobs` field `id` | `/actions/jobs/{id}/logs` |

Worked example (library-cli Release UI `#12`):

- API run id `381`
- Job `id` `720`
- `task_id` `279`

`fgj actions run view 381 --verbose` prints `Job ID: 279`. `GET .../jobs/279/logs` is 404. `GET .../jobs/720/logs` is plaintext.

Resolve logs:

```text
fgj api --hostname git.cognovis.de repos/<owner>/<repo>/actions/runs/<api-run-id>/jobs
# take .[0].id  (not .task_id)
fgj api --hostname git.cognovis.de repos/<owner>/<repo>/actions/jobs/<job-id>/logs
```

`GET .../actions/runs/<api-run-id>/logs` returns a ZIP (`PK`). Do not parse it as UTF-8.

`GET .../actions/tasks` is GitHub-shaped (`workflow_runs`, `run_number`). Do not treat its `id` as the job-logs id.

Forgejo folds GitHub `status`/`conclusion` into one string. Terminal values: `success`, `failure`, `cancelled`, `skipped`.

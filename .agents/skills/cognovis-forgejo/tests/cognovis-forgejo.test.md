# Test Fixture: cognovis-forgejo

## Test 1 — Happy path

**Input:** "Warum ist der library-cli Release rot? Zeig die Action-Logs."

**Expected behavior:** Authenticate via `fgj` on `git.cognovis.de`, list runs with `-R cognovis/library-cli`, take the API `ID` (not UI `#N`), fetch `/actions/runs/<id>/jobs`, then `/actions/jobs/<jobs[].id>/logs`.

**Pass criteria:** The log request uses job `id`, not `task_id`. Tokens are not printed. `fj` is not used for runs or logs.

## Test 2 — Edge case: UI number vs job id

**Input:** "Hol die Logs von Run #12."

**Expected behavior:** Treat `#12` as `index_in_repo`. Resolve the API run id from `run list`/`run view`. Load `references/ids.md`. Refuse to call `/jobs/12/logs` or the verbose Job ID.

**Pass criteria:** Live mapping `#12` → run `381` → job `720` (task `279` is rejected). 404 `resource does not exist` is diagnosed as the wrong id.

## Test 3 — Routing boundary

**Input:** "fj actions tasks reicht doch, oder dispatch nochmal."

**Expected behavior:** `fj` is not the Actions client. Dispatch/rerun/cancel are outside this skill. Empty `runner list` without `--visible` is not "no runners".

**Pass criteria:** Agent switches to `fgj`, does not retry dispatch, and uses `--visible` for inherited runners.

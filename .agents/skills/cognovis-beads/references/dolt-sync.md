# Dolt engine, setup, and sync recovery

Load this when a project needs a beads database created, a fresh checkout needs one
restored, or `bd dolt push/pull` fails. Ordinary `bd` reads and writes need nothing from
here.

> **Version gate**: trust `bd --version`, `bd dolt --help`, and the CHANGELOG over this
> file if they disagree.

## Engine

bd runs Dolt in-process. There is no daemon, no port, and no local network call. The
database lives in the repository at `.beads/embeddeddolt/<prefix>/`, which beads' own
`.beads/.gitignore` excludes from Git.

Cross-machine sync is a *remote*, not a server: `bd dolt push` / `bd dolt pull` against
`https://dolt.cognovis.de/<db>`, exactly like `git push`. Dolt merges at cell level,
so two machines editing different fields of the same issue reconcile cleanly.

Two names, and this file keeps them apart:

| Placeholder | What it names | Example |
|---|---|---|
| `<prefix>` | the local store directory under `.beads/embeddeddolt/`; bd names it after the issue prefix (`bd dolt status`, `metadata.json` `dolt_database`) | `ccore` |
| `<db>` | the remote database on the shared host, `beads_<repo>` with hyphens as underscores | `beads_ccore` |

They coincide only by accident. Every local path in this file uses `<prefix>`; every remote
URL and host directory uses `<db>`.

**Worktrees share the main checkout's engine** through the git common directory. A worktree
has no `.beads/embeddeddolt` of its own, so a claim set in the main checkout is visible in
every worktree with no sync step and no ordering between claiming and creating a worktree.

Two files select the mode, and both must agree:

```
.beads/metadata.json   "dolt_mode": "embedded"    <- SELECTS the mode
.beads/config.yaml     dolt.shared-server: false  <- must agree, not sufficient alone
```

Confirm with `bd dolt status`, which reports the engine and the data location.

Dolt is the source of truth. `.beads/issues.jsonl` is a passive export for viewers,
interchange, and quick diffs — never the sync protocol. If bd reports
`auto-importing ... from .beads/issues.jsonl into empty database`, the local database has
been seeded from a derived export: do not push that state, restore from the remote instead.

## Beads upgrade ordering

Immediately after upgrading the Beads binary, open each local database with a harmless
command such as `bd list --limit 1` and let the Smart Gate finish before any `bd dolt pull`
or any workflow that owns a pull.

An ordinary store open applies pending deterministic migrations. Pulling first mixes the
remote schema history into an unmigrated local database and defeats the safe first-mover
path. Once the local open has completed, return to the normal journaled sync flow. Do not
substitute `bd migrate --force`.

[`scripts/sync-verify.sh`](../scripts/sync-verify.sh) encodes that order — local open
first, then journaled sync — and exercises a create/close round trip against the remote.

## New repository

`ccore project new` runs the whole sequence: the local Git repository, the Forgejo
repository, the host Dolt database, the Beads workspace, and the registry entry.

```bash
ccore project new <repo> --prefix <prefix>
```

Pass `--prefix` whenever the bead prefix was chosen up front. Without it the command derives
a default prefix from the repository name, and a chosen prefix never reaches the tracker.

The order is what makes the first push a fast-forward. The host database is created with
`dolt init` over `ssh dolt-server`. The local store is then produced by `dolt clone --user
malte https://dolt.cognovis.de/<db> .beads/embeddeddolt/<prefix>`, so it descends from the
host root. The clone target is `<prefix>`, not `<db>` (see [Engine](#engine)): bd adopts
only the prefix-named directory, so a clone placed under the database name is silently
ignored and `bd init` builds a fresh unrelated store beside it, after which the push fails
as user `root` (observed live on 2026-08-17).
`.beads/config.yaml` is written with `issue-prefix` and no `sync.remote` yet,
`bd init --reinit-local --prefix <prefix>` adopts the cloned store, `bd dolt remote add
origin` plus `remotes.origin.params.__DOLT__grpc_username` in `repo_state.json` supply the
remote and its user, and the closing `bd dolt push` fast-forwards. Nothing force-pushes,
and nothing needs to.

The database is named `beads_<repo>` — the repository name with hyphens replaced by
underscores — not `beads_<prefix>`.

Creating the database is only half the job: the prefix has to reach the curated registry in
the same operation, or nothing can resolve it. `ccore project new` writes that entry itself;
running the sequence by hand means writing it by hand too.

## Repository registry

`~/.config/cognovis/beads-repos.toml` maps each bead ID prefix to the repository that owns
it. It is the only resolution source; an unlisted prefix does not resolve.

That is deliberate, because inference is unsafe here. `bd -C <repo>` answers from an
unrelated database when the repository has no database of its own, silently and
inconsistently. The mapping is not derivable from configuration either, and scanning does
not help since hundreds of worktrees carry their own `.beads` directory.

```toml
[[repository]]
prefix = "<bead id prefix>"
path = "/absolute/path/to/repository"
database = "beads_<name>"
```

Read a repository's remote with `bd dolt remote list`, not from `.beads/config.yaml` — the
`sync.remote` key is optional and frequently absent in repositories whose remote is
configured and working. `bd dolt show` renders the remote inconsistently; `bd dolt remote
list` is the one to trust.

Check for drift with `ccore beads resolve-repo --audit`, which reports stale paths, unlisted
candidates, and duplicate prefixes. It never writes: the registry is curated, not generated.

## Fresh clone, new machine, or a broken database

`.beads/embeddeddolt/` is gitignored, so a fresh checkout has no database. `bd bootstrap`
is the supported path — it is non-destructive and never deletes existing issues:

```bash
bd bootstrap --dry-run     # shows the plan
bd bootstrap
```

It clones from `sync.remote` when one is configured, and otherwise falls back to git Dolt
data, a backup, or a fresh database. Follow it with the auth step below, because bd does
not write the RemoteAPI username itself.

## Auth

Remote push and pull authenticate with a per-database username stored in the Dolt repo
state, plus a password from the environment:

| What | Where |
|---|---|
| `__DOLT__grpc_username` | `.beads/embeddeddolt/<prefix>/.dolt/repo_state.json` |
| `DOLT_REMOTE_PASSWORD` | `~/.zshenv` |

```bash
uv run skills/cognovis-beads/scripts/set-remote-user.py \
  .beads/embeddeddolt/<prefix>/.dolt/repo_state.json malte
```

Pitfalls:

- `bd dolt remote add` does **not** write `__DOLT__grpc_username`. Without it every push
  fails as user `root`. Set it after adding a remote, and after `bd bootstrap`.
- `DOLT_REMOTE_USER` is not an official env var — only `DOLT_REMOTE_PASSWORD` is read.
- `dolt clone` and `DOLT_CLONE()` ignore env vars for the username; pass `--user malte`.
- `dolt creds` (keypair auth) is DoltHub-only and does not apply to the self-hosted remote.

## Diagnose push and pull failures

```bash
bd dolt status                  # engine + data location
bd dolt remote list             # origin present?
```

| Error | Cause | Fix |
|---|---|---|
| `Access denied for user 'root'` | `__DOLT__grpc_username` missing | Set it (see [Auth](#auth)) |
| `Access denied for user 'malte'` | Wrong or missing `DOLT_REMOTE_PASSWORD` | Check `~/.zshenv` |
| `target has uncommitted changes` | [dolthub/dolt#10807](https://github.com/dolthub/dolt/issues/10807) | Retry the same `ccore beads sync` operation |
| `no common ancestor` | Local and remote diverged | Established repository: move the store aside and `bd bootstrap` — do **not** force-push. Fresh project: [see below](#no-common-ancestor-on-a-fresh-project) |
| `database not found` (remote) | Remote database missing | Create it on the host (see below) |
| `TLS handshake failed` | Reverse proxy on the host | Check the host, see below |
| `invalid journal record length` | Crash or power loss mid-write | `dolt fsck --revive-journal-with-data-loss` in `.beads/embeddeddolt/<prefix>`, else `bd bootstrap` |

### `no common ancestor` on a fresh project

A local store that never descended from the host root shares no history with it, so this is
not divergence and neither divergence remedy applies. `bd bootstrap` makes it worse: its
clone passes no `--user`, so it cannot authenticate against the self-hosted remote, and it
rebuilds `repo_state.json` from scratch, dropping the Dolt remote that was already
configured — observed while creating harness-cli on 2026-08-17. A force-push would replace
the host root rather than build on it.

Recreating the project is not the remedy either. By the time this error appears the local
path, the Forgejo repository, and usually the host database already exist, and
`ccore project new` refuses that state by design — reach for it only when nothing has been
created yet (see [New repository](#new-repository)).

Rebuild the workspace alone. Move the broken store aside and clone the host root in its
place:

```bash
mv .beads/embeddeddolt/<prefix> /tmp/<prefix>.broken   # outside embeddeddolt, not a second database
dolt clone --user malte https://dolt.cognovis.de/<db> .beads/embeddeddolt/<prefix>
```

The local directory is the prefix (`bd dolt status` and `.beads/metadata.json`
`dolt_database` name it); only the remote is `<db>`.

Then confirm `.beads/config.yaml` carries `issue-prefix` and no `sync.remote` yet, run
`bd init --reinit-local --prefix <prefix>` so bd adopts the cloned store, add the remote
with `bd dolt remote add origin https://dolt.cognovis.de/<db>`, write
`__DOLT__grpc_username` into `repo_state.json` (see [Auth](#auth)), and finish with
`bd dolt push` — it fast-forwards now that the local store descends from the host root.

## Force-push recovery

`bd dolt push --force` is blocked by the DCG rule
`cognovis.beads_safety:beads-direct-dolt-push` and is never part of a normal flow. It
overwrites remote state that other machines may already have pulled.

Exhaust the ordinary options first: retry the journaled
`ccore beads sync --operation-id <stable-id>`, and on divergence in an established
repository move the local store aside and `bd bootstrap` from the remote. A fresh project
that never shared a root is a different case — rebuild the workspace store from the host
root, see [`no common ancestor` on a fresh project](#no-common-ancestor-on-a-fresh-project).
A forced
push is a deliberate human recovery decision, taken with the user in the loop and never on
an agent's own initiative.

## Repositories without a remote

A handful of machine-local repositories have no Dolt remote — the embedded store is the
only copy of their issues. `bd bootstrap` cannot restore them and a corrupted journal is
unrecoverable beyond `dolt fsck`. If such a repository's issue history starts to matter,
give it a remote rather than relying on recovery.

## The remote host

`dolt.cognovis.de` is a Hetzner VPS reached with `ssh dolt-server`. Its roster entry —
current host, service layout, reverse proxy, ports, and backup strategy — lives in
`~/code/infra-devops/hetzner/docs/inventory.yml` and is maintained there.

Read it rather than trusting a copy: the service moved hosts, changed reverse proxy, and
changed backup mechanism while duplicated notes elsewhere went stale unnoticed.

Creating a remote database means creating a directory under `/var/lib/dolt`, initializing
it as the `dolt` user, fixing ownership to `dolt:dolt`, and restarting the service so
RemoteAPI sees it. `ccore project new` does exactly that. The restart interrupts every
project's sync, so schedule it rather than running it mid-session. Anything beyond that —
vhost, certificates, backups — is an infrastructure change and belongs in
`infra-devops/hetzner`, not here.

# Continuing Earlier Work from Memory

A new session inherits no state. When the request continues work that a previous
session started — "finish the release setup", "did that access get granted?",
"carry on with the deployment" — recover that session's record before proposing
anything. Proposing first and reading second is how a narrower or already-refused
action gets recommended again.

## Procedure

### 1. Find the prior record, bounded

```bash
ob --json search "<project or host> release readiness" --limit=5 | jq -c '[.results[]
  | {id, title, type, created_at, excerpt: ((.excerpt // .content // "") | .[0:300])}]'
```

Search terms that work: the host or customer name, the repository, the artifact,
the failing action. Read the excerpts before fetching anything in full.

### 2. Fetch only what matters

```bash
ob --json get <id> --inspect
```

One or two IDs, chosen from the excerpts. `--inspect` avoids changing recall
priority while you are triaging. Do not loop `get` over every hit.

### 3. Separate four things

Write them down explicitly, because they carry different authority:

| What | How to treat it |
|---|---|
| **Decisions** | Binding until something newer contradicts them. Do not relitigate. |
| **Completed actions** | Done. Do not repeat; verify only if the current task depends on the result. |
| **Open checks and blockers** | The actual work list. |
| **Authorization state** | Only a human decision grants authority. A recorded *request* stays pending until that decision exists; a recorded grant stays valid. |

### 4. Re-check live state before recommending

A memory is evidence about the moment it was written. Before acting, verify the
part you are about to rely on with a read-only check, and label every claim as
either "recorded on <date>" or "verified now". If the live check contradicts the
memory, the live check wins on **facts** and the memory needs updating.

A live check never moves authority. It tells you what is currently true or
currently possible — a token works, a host answers, a path resolves. It does not
turn a pending request into a grant, and a probe that unexpectedly succeeds is a
capability finding to report, not permission to use. Authority changes only when
a human decides; a concrete authorization already given stays given.

Bound those checks too. For one known key, `ccore repo resolve <owner/repo>
--json` is the narrowest query and the right default. When an operation spans a
known set of repositories, list once and filter to exactly that set **before**
any cap, so the result is the operation's own targets and a missing one is
visible instead of trimmed away:

```bash
# bounded-projection: ccore-repo-list
ccore repo list --json | jq -c --argjson keys '["example/product-a","example/product-b","example/product-c"]' 'if .status != "ok" then {code: (.code // "unknown_error"), summary: (.summary // "")} | halt_error(1) else ([.data.repositories[] | select(.key as $k | $keys | index($k) != null) | {key, path, tracker}]) as $found | {requested: ($keys | length), records: $found, missing: ($keys - [$found[].key])} end'
```

Never take an arbitrary slice of the whole catalog: `.[0:10]` over every resolved
entry can drop the very repositories the task is about.

The failure branch comes first on purpose. `ccore` answers a failure with
`status: "error"` and a typed top-level `code`, and that envelope carries no
`repositories` — running the success projection over it produces an iteration
error and hides the real cause. Reporting `code` and `summary` and exiting
non-zero keeps the actionable diagnostic, for example `repo_unknown`,
`repo_path_unresolved` or `repo_registry_unreadable`.

### 5. Keep the scope bound to its target

Carry forward the exact repositories, hosts and accounts the record names. Do not
widen a permission request because a broader one would be more convenient, and do
not narrow the target set because only part of it is in front of you now.

## Worked example: a release that stopped at an access gate

A saved session summary records the state a later session has to continue from.
Read it as four separate things:

- **Completed**: release and deploy tooling installed on the operator
  workstations; credentials, signing identity and registry logins verified;
  release source paths resolved through the registry; target trust provisioned
  from the packaged public key; plan and read-only preflight passed with `READY`.
- **Decisions**: no deployment, publication or migration was performed; the full
  target doctor stayed `DEGRADED` and was deliberately not repaired.
- **Open, still blocking**: the workbench token returns HTTP 403 for Actions on
  **all three** release repositories — `example/product-a`, `example/product-b`
  and `example/product-c`. A continuation that names only one of them has
  narrowed the blocker and will produce an incomplete scope request.
- **Authorization state**: appending the existing workbench public key on the
  customer-operated host was *asked for* and left pending. The prepared script
  was deliberately not executed. It stays pending until the human answers — later
  evidence that the key would work, or that the change is now easy, does not
  answer it. The access-control review gate still applies, so the continuation
  does not run it.

What a continuation does with that:

1. Restate all three repositories and the pending host gate.
2. Re-check the live blocker read-only before asking again — whether the token
   still fails for those repositories, and whether the login route is still
   rejected — without mutating credentials, authorized-keys files or permissions.
3. Ask for exactly the scope the evidence supports, naming every repository the
   record names. This particular access grant is still pending a human decision,
   so it stays with the human, as do passwords and MFA codes.

The boundary here is the unresolved decision, not the host: work this session has
already been concretely authorized to do on those targets remains authorized
under the shared authorization policy. What an agent may not do is treat its own
need, or a successful probe, as the missing approval.

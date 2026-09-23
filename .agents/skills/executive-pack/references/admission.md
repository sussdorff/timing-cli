## Delivery identity

A coordinator records delivery identity before implementation dispatch. Call
`ccore delivery start`; do not post a claim comment and do not treat host
assignee as an admission lock:

```bash
ccore delivery start \
  --repo <canonical-checkout> \
  --issue <owner/repo#N> \
  --worktree <current-worktree> \
  --branch <feature-branch> \
  --coordinator <session-id> \
  --writer <implementation-actor>
```

First start and same-coordinator resume admit. Overlapping open issue refs on
this host are `delivery_already_open`: resume that delivery instead of starting
another. Keep the returned envelope in caller-owned delivery state. Do not
persist a loop state file. Optional `ccore tracker claim --assignee` is a human
signal only.

## Landing policy

Every repository delivery lands through exactly one of `direct`, `pr-auto`, or
`pr-review`. That choice is deterministic, so resolve it — never reason it out in
prose:

```bash
uv run python "$SKILL_ROOT/scripts/landing_policy.py" resolve \
  --delivery-mode solo --bead-type bug --bead-body-file <body> \
  --repository-policy pr-auto --branch-protection --override pr-review \
  --session-id <id>
```

`scripts/landing_policy.py` owns the defaults, the monotonic elevation order
`direct -> pr-auto -> pr-review`, and every fail-closed refusal. Read that module
when a decision is in question; do not copy its matrix here or into any other
caller. A missing, unknown, or conflicting `Review-Risk:` classification in the
Bead body is a typed refusal, and the delivery stops before dispatch instead of
guessing. Pass the Bead body, not a hand-typed `--review-risk`: a flag that
contradicts the recorded classification is refused, never preferred. An explicit
override below the resolved policy is refused rather than silently applied.

Run `ccore session-close run --help` before using the resolved plan. The released
interface requires `--merge-authority` for PR delivery:

- direct uses `--delivery merge`.
- pr-auto uses `--delivery pr --merge-authority agent_bot`; the run requests merge,
  verifies target containment and can finish completed in that same run.
- pr-review uses `--delivery pr --merge-authority human`; publication returns
  review_pending. A human merges before `ccore session-close complete-pr
  --session-id <id>` observes the recorded PR's containment and finishes.

Only a terminal completed or completed_with_warnings result proves completion.
For review_pending, report the Session Close ID and PR reference with issues still
open. Use that same ID to resume; publication alone is not completion. Do not infer
bot authority from a request merely to watch or inspect a PR.

### Worktree ownership

A worktree is admitted by declared ownership, not by location. A provider-owned
worktree — one an external coding provider such as T3Code created — is accepted at
whatever path that provider chose and stays provider-owned through terminal
cleanup. Declare it with `--worktree-owner self` or `--worktree-owner
provider:<id>` when calling `scripts/agent_workspace_guard.py`; the guard also
reads the spellings `ccore` Session Close records, `session-close` for
self-managed and `t3code` for provider-owned, so the durable field round-trips.
An unrecognized owner is refused rather than guessed.

`self` is the default, so it is also the rule that has to hold: a task worktree
declared `self` must sit under `~/code/.worktrees/<repo>/<bead-or-purpose>`, and
one outside that root is refused with `SELF_MANAGED_WORKTREE_OUTSIDE_ROOT` naming
both the declared owner and the root. Otherwise a provider worktree passed with no
owner would be admitted as self-managed and later cleaned by a non-owner. A
harness-native worktree — Claude's own `cld -b` path, for instance — is
`provider:<id>`, not `self`. The guard never reads a path to *decide* an owner; it
only holds a declared `self` to the declared root, and `provider:<id>` is exempt.

A ticket-bearing branch name helps a human read the queue and is never delivery
identity. Identity is the recorded set — delivery ID, Session Close ID, the exact
issue refs, the repository, the branches, the candidate SHA, the harness, and
the worktree owner — carried in the delivery journal, the Session Close journal,
and the pull-request footer. Never re-derive any of it by parsing a worktree
path or a branch spelling.

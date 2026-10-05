# Model Routing

Which model runs which delivery step. Claude Code on fleet hosts reaches every provider
through CLIProxyAPI (`ANTHROPIC_BASE_URL`); `~/.claude/settings.json` maps the `sonnet`
and `haiku` aliases to other model families. Confirm that mapping in the settings file
when the family matters; a host without it silently runs real Sonnet or Haiku.

## Roster

| Alias | Model | Family | Delivery steps |
|---|---|---|---|
| `opus` | Claude Opus 5.5 | Claude | main session, `implementer` subagent, one of the three reviewers (fresh context) and, after triage, that reviewer as the designated repair author |
| `fable` | Claude Fable 5.1 | Claude | planning |
| `sonnet` | `gpt-6-astra` | GPT | one of the three reviewers; its findings go through triage because Astra is picky |
| `haiku` | `grok-4.7` | Grok | one of the three reviewers; verification, including browser and UI verification with `playwright-cli` |

`opus`, `sonnet` and `haiku` together cover three model families for the adversarial
review. The repair role follows the actor, not a family: repairs go to the designated
`opus` reviewer whichever family surfaced the finding.

## Dispatch rule

Native subagent with the alias first. The named `ccore agent` route only when the alias
is unavailable, or when the native attempt fails:

| Alias | Fallback route (`ccore agent run --model <alias> --harness <harness>`) |
|---|---|
| `opus` | `claude-opus` on `claude` |
| `fable` | `claude-fable` on `claude` |
| `sonnet` (review) | `gpt-6-sol` on `codex`; the catalog has no Astra route |
| `haiku` (review, non-UI verification) | `grok-4.7` on `grok` |
| `haiku` (UI verification) | `gpt-6-luna` on `codex` |

A native subagent works in the invoking session's worktree and cannot leave it. When the
candidate lives in another worktree, for example a retro pull request in a self-managed
worktree while the session runs in a T3 thread worktree, dispatch the fallback route
directly with `--cwd <worktree>`; `ccore agent run` also requires `--events-file`.

The catalog is `ccore agent models --json`. A configured catalog entry is not proof that
the route is reachable right now. When neither the alias nor the fallback route works,
stop and report the dispatch diagnostic; never substitute another model silently and
never continue a step with fewer actors than it requires.

## Not routed

The model family the shared instructions prohibit is never routed. opencode models
hold no delivery step.

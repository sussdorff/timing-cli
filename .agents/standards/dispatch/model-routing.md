# Model Routing

Model selection for repository delivery is behavioral prompt policy. The initiating
prompt supplies one readable paragraph naming the implementation owner, Reviewer 1,
Reviewer 2, and fallback. Explicit caller wording overrides launcher defaults, provided
the implementation actor remains distinct and the required review perspectives remain
different-family.

STATUS: BEHAVIORAL POLICY. The repository delivery owner follows the role paragraph.
Transport proves session execution, not semantic role compliance. Normal Solo and
Executive Pack progression has no JSON role payload, route resolver, profile registry,
candidate selector, or deterministic model-selection choreography.

## Defaults

Fable is the Claude-family review preference, not a proven exact version. Wherever a
Claude-family reviewer or fallback is named below, select an exact Fable model advertised
by the target native surface or, when native dispatch is unavailable or fails, the ccore
`claude-fable` route. The ccore catalog currently records that alias with backend model
`fable[1m]` on the `claude` harness; those fields do not establish an equivalent native
ID or an exact upstream version. Leave the exact version unresolved when the target
surface does not establish it; do not silently substitute another Claude model.
Opus may be selected only when the target surface advertises it or the ccore catalog
configures it for a caller that names it explicitly; a catalog entry still needs an
actual dispatch result. Opus is no longer a launcher default for review.

For a Codex-owned delivery, prefer `gpt-6-astra` with medium reasoning for the invoking
delivery owner. This is an invoking-session model choice, not an assumption that ccore
provides an Astra route. Use a distinct `gpt-5.6-sol` implementation sub-agent with high
reasoning and a distinct `gpt-5.6-sol` RED author with high reasoning when TDD applies.
Fable is Reviewer 1. Use Grok as Reviewer 2 only when the selected Solo preset or final
Pack review requires that second review perspective. Prefer a compatible native Grok
actor; otherwise select its configured ccore route from the general catalog.

For a Claude-owned delivery, use a distinct Opus implementation sub-agent, a fresh
`gpt-5.6-sol` Reviewer 1 with high reasoning, and Grok as Reviewer 2 when required.
Prefer the target native surface for Grok and use its catalog-reported ccore harness as
fallback. The implementation model is unchanged by the Fable preference above, which
covers review roles only.

Reviewer 2 and the security perspective belong to the High-Assurance preset. The Light
preset is the default and names Reviewer 2 as `not required`; High Assurance is
selected by an elevating landing-policy review risk, by the caller, or by repository
instructions. A Light delivery still keeps its fresh Reviewer 1 in a different family
from the implementation actor.

### Admission session and coordinator

Admission and delivery may run in different sessions. The admission session uses the
most capable available model, Claude Fable or `gpt-6-astra`, and ends by writing the
compact admission packet defined in the Executive Pack's `admission-packet.md`. The
coordinator session then owns delivery from claim admission through Session Close; it
uses a large-context, lower-cost model: Claude Sonnet 5 under the Claude provider or
`gpt-5.6-luna` at medium reasoning under the Codex provider. Both are valid; the packet
names the one used. The coordinator is the fixed repository delivery owner from that
point and is never rotated. Implementation, RED authorship and review keep the actor
rules above regardless of which coordinator runs.

### Optional Luna coordination profile

The Astra-medium Codex delivery owner remains the default. Before sending the
initiating prompt, an operator may instead start the invoking delivery session with
`gpt-5.6-luna` at medium reasoning and name the Luna coordination profile in the
role paragraph. Prompt text cannot switch the invoking model. That already-running
Luna session is the repository delivery owner; it does not spawn a new owner, replace
an admitted owner, transfer ownership later in the delivery, or rotate through the
compact implementation-handoff contract. The selection freezes with the rest of the
delivery contract at admission.

The profile changes only coordination and optional decision support. It retains a
distinct `gpt-5.6-sol` high implementation owner, a distinct `gpt-5.6-sol` high RED
author when TDD applies, and the selected Solo or Pack preset's foreign-family review,
acceptance, security, repair and Session Close responsibilities. A fresh read-only
`gpt-6-astra` advisor at xhigh reasoning may answer one bounded planning question or one
concrete unresolved blocker after repository lookup. It returns advice to the Luna
owner and receives no source, claim, finding-disposition or completion authority. Read
the Executive Pack's optional Luna coordination reference for the activation rules,
compact packet and initiating prompt.

## Delivery work kinds

A work kind names a responsibility and its expected result. It is neither a Bead issue
type nor a model identity, and this table is not a required fan-out checklist. Required
roles and evidence come from the selected delivery preset and the live Bead; optional
work runs only when it helps that delivery.

The [setup-pstack role mapping](https://github.com/cursor/plugins/blob/889ec4b68fa5aab0e867dad71ec3fdf386ae48f3/pstack/skills/setup-pstack/SKILL.md)
motivates the useful separation here: work responsibility and model choice stay
distinct and overrideable. Its configured role lists, setup flow and panel fan-out are
not part of this delivery contract.

| Work kind | Applies when | Existing actor and expected result |
|---|---|---|
| Delivery coordination | Every repository delivery | The invoking delivery owner returns admission, sequencing and finding decisions, callbacks, usage evidence and one Session Close result. For Codex, prefer Astra with medium reasoning; the optional Luna profile above must be selected before admission. |
| Bounded context or documentation lookup | A concrete repository question can be answered independently | `bead-context` for admitted context, or a compatible native generic/explorer actor, returns concise file or document pointers, evidence and open uncertainty. For Codex, prefer Luna with medium reasoning. |
| Bounded decision support | Difficult uncertainty remains after concrete lookup | `plan-reviewer` uses its declared configuration for an admitted implementation plan and returns evidence, options and the unresolved decision. For Codex, a compatible native generic advisory actor may use Astra with xhigh reasoning for this bounded analysis when its spawn surface advertises that exact choice. |
| Multi-source research | The work needs broad source discovery and synthesis | `researcher` returns a sourced research summary. Its Sol high configuration reflects that broader job and is not a narrow-lookup default. |
| Implementation | Each admitted Bead | `implementer` remains the stable logical source owner and returns the candidate diff plus focused verification. For Codex, use Sol with high reasoning. |
| Independent RED authorship | TDD applies to an implementation slice | `tdd-test-author` returns independently sourced RED evidence. For Codex, use Sol with high reasoning in a session distinct from the implementer. |
| Pack repair convergence | Final Pack review leaves accepted findings on an existing candidate | One current repair implementer receives every remaining finding at once in the shared Pack worktree and owns the cumulative repair diff, its tests and focused verification. Normal serial Codex execution rotates once through the compact handoff to a fresh Sol session with high reasoning; a Sub-Pack keeps its fixed parent repair session. This is a closing bugfix phase: no `implementation-loop` re-entry, no separate RED author, no member-sequence replay. |
| Documentation | The implementation changes a material user-visible, API, configuration, deployment, operator or developer workflow | `doc-changelog-updater` updates affected documentation before final review; otherwise the implementation owner keeps scoped documentation aligned with its source change. The result states the changed behavior and verification. |
| Review | The selected Solo or Pack preset requires the perspective | Reviewer 1 and, when required, Reviewer 2 return candidate-bound findings from fresh different-family contexts. Keep the Fable, Grok and fallback rules below. |
| Acceptance, security or project evidence | Claims, risk or repository policy make the perspective applicable | The existing specialist actor returns its own candidate-bound evidence and never repairs source. Its declared configuration remains authoritative. |

For optional lookup or research, give the actor one bounded concrete question, relevant
paths and constraints, the required evidence shape, and the uncertainty it must report.
Delegate only when the delivery owner has useful independent work to continue while the
answer is produced. Start with a compact fresh context without inherited delivery
history. Use Luna high only for a named difficult lookup, such as cross-subsystem
ambiguity, and record why medium was insufficient. A native generic actor may escalate
that difficult lookup to Luna max only when its current spawn surface explicitly
offers that exact model and effort.
Use Astra xhigh only for bounded decision support after lookup and only when the target
native surface advertises that exact choice. Validate every model and effort against the
actual target surface; a ccore route and a native spawn catalog do not imply support for
each other. Escalation does not transfer source ownership or replace any required
foreign-family review or evidence perspective.

Under the optional Luna profile only, a decision-support advisor may activate for an
explicit plan challenge or when one concrete unresolved blocker prevents the delivery
owner from continuing independently. The owner may wait for that single terminal
answer and then either decide or report the remaining blocker. One Astra advisor
handles one question and stops after its answer. A later, materially different blocker
may use another fresh advisor. Do not keep an advisor attached as a watchdog, forward
the delivery transcript, or ask it to monitor progress, review the candidate, repair
source, or approve progression.

In Codex, a custom agent's native configuration wins over a model requested at spawn
time. Do not instruct callers to override a hard-pinned custom agent. Select an already
compatible actor, use a generic actor whose model can be set explicitly, or retain the
custom agent's declared model and state the reason.

## Review families and fallbacks

Different-family is measured against the implementation actor. The invariant every
reviewer must satisfy is that its model family differs from the family that produced the
candidate, and that it is a fresh actor that has not touched the candidate. Two reviewers
sharing a family with each other is a loss of perspective diversity, not a violation of
that invariant: the launcher defaults avoid it, a fallback may accept it, and the delivery
owner records the reason in the Bead notes when it does. The complete fallback matrix is:

| Implementer family | Unreachable provider | Replacement |
|---|---|---|
| GPT (Codex-owned) | Fable (Reviewer 1) | Closed. Both remaining families are GPT (same as the implementer) and Grok (already Reviewer 2). Report the provider gap; do not review around it. |
| GPT (Codex-owned) | Grok (Reviewer 2) | Fresh Fable, distinct from the Reviewer 1 session; both reviewers are then Claude-family, recorded as a diversity loss. |
| Claude (Claude-owned) | GPT-5.6-sol (Reviewer 1) | Fresh Fable is not allowed (same family as the implementer). Fresh Grok, distinct from the Reviewer 2 session, recorded as a diversity loss; report the gap when Grok is also unreachable. |
| Claude (Claude-owned) | Grok (Reviewer 2) | Fresh `gpt-5.6-sol` with high reasoning, distinct from the Reviewer 1 session, recorded as a diversity loss. |

A caller that names another implementation family, for example Grok, applies the same
two rules: the replacement differs from the implementer's family and is fresh. In
particular, `gpt-5.6-sol` with high reasoning is an allowed Reviewer 1 fallback for any
non-GPT implementer when Fable is unreachable, and a fresh Fable fallback is allowed for
any non-Claude implementer. A row that reads "report the gap" ends the review, not the
invariant: provider absence never becomes approval.

For ccore fallback, select Grok from the harness reported by the current general catalog;
do not infer a Cursor route from a marketing or provider-CLI name. A native surface may
dispatch an exact Grok ID that it advertises. The historical Cursor observations below
record prior transport behavior but do not gate current native dispatch.

These are launcher defaults, not a registry. A compatible caller may name other actors
in the paragraph. It may not make the repository delivery owner the implementation
actor, reuse one actor for required distinct perspectives, or turn provider absence into
approval.

## Transport boundary

Subject to explicit caller constraints, prefer the intended actor's native subagent
surface when it advertises the exact model and supports the required role. This order
overrides transport defaults in skills, roles, profiles, and launchers. When native
dispatch is unavailable or fails, use `ccore agent`. Its agent-shell transport uses the
installed dispatcher with an exact adapter, catalog route, reasoning effort, stable
session, linked worktree, complete prompt file,
permissions, and unique event and answer files. A route names an adapter, never a shell
fragment. Do not bypass ccore with a provider CLI or direct ACPX call. A review has no
turn budget.

The `ccore agent run` default of `approve-reads` grants only read-only tools and
no shell, so it cannot implement, repair, or run verification. The implementation
owner and every reviewer that executes tests or git therefore dispatch with an
explicit `--permissions approve-all`; the CLI confines that grant to a linked
worktree and refuses it in a main checkout. Code reviewers receive worktree-confined
`approve-all` so they can run verification while remaining behaviorally read-only;
a purely reading perspective may stay on `approve-reads`. Agentic acceptance needs
no caller flag: `ccore acceptance run` owns its validator permissions itself.

Persistent prompt execution is the default. One-shot execution requires an explicit
transport choice. A zero exit, terminal stop reason, and non-empty answer prove transport
completion only. Missing output, unavailable providers, or a non-passing semantic result
return control to the delivery owner and never authorize progression.

### Model identifiers

Model identifiers belong to their dispatch surface. For native dispatch, use only an
exact model ID advertised by the native subagent tool; visibility in a user-interface
picker alone does not establish subagent support. For ccore fallback, begin a Claude
lookup with `ccore agent models --harness claude --json` and use
`ccore agent models --json` for other or unknown harnesses. Keep each result's
`canonical_alias`, `backend_model`, and `harness` distinct and dispatch with
`ccore agent run --model <canonical_alias> --harness <harness>`; do not translate a
native ID into a ccore alias or guess that a backend ID is accepted on another surface.

The ccore output is a configured catalog, not live discovery. It does not prove current
reachability, an exact upstream version, or equivalence with a native model. Actual
dispatch supplies the availability diagnostic. If neither native dispatch nor a ccore
route can provide the required actor, report that diagnostic without weakening model
prohibitions, explicit caller constraints, actor separation, or family separation. Do
not silently substitute a different model; an exact version that neither surface proves
remains unresolved rather than becoming a generic family match.

The adapter observations below were verified by live dispatch on 2026-08-17. They are
historical transport notes, not an allowlist or a gate against current native dispatch.

- The cursor adapter advertises bracketed identifiers through its `model` configuration
  option, for example `grok-4.6[effort=high,fast=true]`.
  ACPX normalizes a bare name only when exactly one bracketed variant matches it.
  Provider-CLI identifiers, such as the `cursor-grok-4.6-high-fast` and `auto` values
  that `agent models` prints, are rejected with ACP error `-32602`. (2026-08-17)
- A persistent ACPX session keeps the model it was last set to, so the caller passes
  `--model` explicitly on every dispatch rather than relying on session state.
  (2026-08-17)

## Reviewer route status

This section records historical dispatch observations that may help diagnose a fallback.
It is not a machine-resolved routing table or an allowlist. Current native surface
advertisement and actual dispatch determine whether a newly available route can run;
configured ccore routes still require an actual dispatch result.

Grok observations below were made on 2026-08-26 against ccore 2026.8.35 (build
c7d7fda3972b32), ACPX 0.13, cursor-agent 2026.08.11-e8db854, and Grok Build 1.0.5.
Fable and Cursor observations were made on 2026-09-04 against ccore 2026.9.2, ACPX
0.13.1, cursor-agent 2026.08.25-3e8eec8, and Claude Code 2.1.260 on yakushido.

### Fable: transport-verified Claude-family reviewer route

`ccore agent run --model claude-fable` used backend model `fable[1m]` on the ccore
`claude` harness. On 2026-09-04 it returned a terminal answer with
`stop_reason: end_turn` on two hosts: a macOS workstation whose Claude Code holds a
Claude Max OAuth login, and yakushido, whose Claude Code authenticates through an
`apiKeyHelper` against the cliproxy endpoint. Both observations were single-word probes
(`PONG`) under `deny-all` permissions, so they proved reachability of the route at that
time, not review quality; a review dispatch still carries worktree-confined
`approve-all` as the transport boundary requires. As of that observation, this was the
only Fable route known to have answered on this fleet.

One host caveat, not a route limit: Claude Code reads a user-level `apiKeyHelper` only
from `~/.claude/settings.json`. A helper placed in `~/.claude/settings.local.json` applies
only when the working directory is the home directory, so a dispatch from any repository
worktree fails with `Failed to authenticate: OAuth session expired and could not be
refreshed`. The remedy is an operator edit of the user settings file; ccore does not work
around it.

### Grok: verified reviewer family

Grok accepts reasoning effort `low`, `medium`, `high`, and `xhigh`, and rejects `max`.
That matrix was verified by ccore-x0n.

The installed route applies the effort through the `GROK_CONFIG` environment variable,
which ccore merges as `models.default_reasoning_effort` before launching the agent. It is
not applied by an ACP `set model` `_meta` call: ACPX 0.13 sends only `modelId` on set
model and does not forward `_meta`, so that route cannot carry reasoning effort even
though Grok Build implements `set_model` itself. It is also not applied by a
command-line flag. ACPX launches the plain argv `grok agent stdio`, so although the Grok
CLI does expose `--reasoning-effort`, the installed route never passes it, and a caller
who reasons from that flag will mispredict what the dispatch does.

The historical `-32601` came from none of those. ccore-x0n records it against the retired
`acpx grok-build set reasoning_effort` call, which reaches ACP
`session/set_config_option`, a method Grok Build does not implement for effort. That call
is gone, which is why nothing in the current route sets effort over ACP at all.

For that recorded ccore route, a caller passes `--reasoning` to
`ccore agent run --harness grok` and lets ccore put it into `GROK_CONFIG`; there is no
acpx `set` call to reach for, and a missing one is not a defect. Native dispatch instead
uses the exact model and effort exposed by its own surface. Confirmed on 2026-08-26: the
ACP session record for a ccore-dispatched turn
carries `modelId: grok-4.6` with `reasoningEffort: xhigh` (and `high` on a second run),
and ccore's evidence contract reports `reasoning_setup_status: applied` with
`reasoning_source: grok_config`.

Grok qualifies as a Reviewer 2 family for both a Claude-led and a Codex-led delivery.
It is a third provider family, distinct from Anthropic and from OpenAI, so it satisfies
the different-family requirement in either direction without collapsing a perspective.

One account caveat, not a capability limit: on 2026-08-26 four dispatches reached the
model and then ended with `stop_reason: error` and
`API error (status 402 Payment Required): Grok Build usage balance exhausted`. Transport
and effort application were sound; the account balance was not. An exhausted balance
yields an empty answer, and an empty answer returns control to the delivery owner. Note
that ccore surfaces this as a bare `ACPX exited 1:` with no detail, so the operator reads
the actual cause from the raw ACP stream under `~/.acpx/sessions/<session-id>.stream.ndjson`.

### Cursor: transport verified, Fable gated

On 2026-09-04 the persistent-session dispatch `ccore agent run --harness cursor`
completed `sessions ensure`, `set model`, and a prompt turn on yakushido with cursor-agent
logged in. Two exact advertised ids returned a terminal answer with `stop_reason:
end_turn`:

- `claude-opus-5[thinking=true,context=300k,effort=high,fast=false]`
- `gpt-5.6-sol[context=272k,reasoning=medium,fast=false]`

Both Fable ids, `claude-fable-5-1[thinking=true,context=300k,effort=high]` and
`claude-fable-5[thinking=true,context=300k,effort=high]`, completed the same transport
steps and returned the single agent message `Check your settings to continue` with
`stop_reason: end_turn` and zero token usage. The raw ACP stream carries that text as an
ordinary `agent_message_chunk` from the agent, after `set model` succeeded, so it arrived
through the same transport path as the answers above. The same reply has been reported by
other ACP clients for Anthropic models on some Cursor accounts. Its cause is not
established here and is outside this standard. During that observation, Fable through
Cursor did not qualify as a verified reviewer route; the answered fallback used the
ccore `claude` harness above.

A verified Cursor transport does not by itself make a cursor-hosted model a launcher
default. The recorded ccore catalog places Grok on its `grok` harness, and Reviewer 2
for both delivery families stays Grok. A caller who names a cursor-hosted Opus 5 or
GPT-5.6 reviewer must still keep the different-family invariant against the
implementation actor.

The two conditions recorded on 2026-08-26 did not reproduce on this host: cursor-agent
was logged in, and the persistent-session spawn reached the ACP handshake. The earlier
pre-handshake failure, `ACP agent exited before initialize completed ... Device not
configured (os error 6)`, was observed on a different host and cursor-agent build; its
ruled-out set lives in clc-c2lt, which still owns either recording a verified cursor
reviewer route with an effort value or dropping Cursor from the reviewer options.

Two ccore transport findings from that diagnosis belong to ccore-8el, not to this
standard: ccore's native ACPX path never sets or forwards `--no-terminal`, and ccore
discards the provider error detail when ACPX exits non-zero.

## Ownership

- The repository delivery owner chooses and prompts actors, sequences Beads, evaluates
  findings, owns callbacks, and invokes Session Close.
- The logical implementation owner remains stable for source changes and every
  accepted repair. In normal serial execution, fresh sessions take over only from a
  compact clean committed handoff; optional Sub-Pack receipt bindings remain fixed.
- A fresh Reviewer 1 context supplies bounded member-diff and affected-interaction
  coverage in an Executive Pack.
- Reviewer 2 supplies the complete different-family final adversarial perspective over
  the whole Pack.
- Agentic acceptance, security, and applicable project-specific checks remain distinct
  evidence perspectives and never repair source.

Transport telemetry is operational evidence only. Usage reports keep uncached input,
cached input, and output separate when those values exist, mark missing classes
unavailable, and never estimate or double count them. Role quality, perspective
quality, finding severity, and repair decisions remain caller-owned judgment.

# Admission session and coordinator

A repository delivery has two phases with different needs. Admission is a
conversation: read the work order, grill the boundaries, derive seams, freeze
the role paragraph. Delivery is bookkeeping: claim, dispatch, collect evidence,
dispose findings, close. The first wants the most capable model available; the
second wants a large context and a low price. This reference lets the two run
in different sessions with one compact packet between them, so the expensive
model is not kept alive for the whole delivery.

The split is optional. A single session may still own both phases. What it
changes is when the delivery owner becomes fixed: at the end of admission, not
at the start of the conversation. From that point on the ownership rules in
[SKILL.md](../SKILL.md) apply unchanged, and the coordinator session is never
rotated, replaced, or shadowed by a watcher.

## Admission session

Use Claude Fable or GPT-6 Astra. In T3 Code this is the thread the human is
talking to. It:

1. reads the work order through `ccore tracker show` and the repository
   instructions, ADRs and affected paths;
2. uses `skill:grilling` or `skill:grill-with-docs` where the acceptance
   criteria leave a boundary open, and `skill:codebase-design` for a seam
   decision; interviews only when a reading would change scope or risk;
3. derives the TDD seams and states where TDD does not apply;
4. resolves the landing policy with `scripts/landing_policy.py resolve` and
   records its envelope, including `review_risk`;
5. writes the role paragraph: implementation owner, Reviewer 1, Reviewer 2
   when the preset requires it, fallback; and
6. emits the admission packet below and stops. It does not claim, dispatch, or
   close.

## Coordinator session

Use a large-context, lower-cost model. In T3 Code: Claude Sonnet 5 under the
Claude provider, or GPT-5.6 Luna at medium reasoning under the Codex provider.
Either is a valid choice; name the one used in the packet. The coordinator
starts a fresh thread from the packet with no admission chat history, runs
`ccore delivery start`, and owns the delivery from there through
one Session Close. It follows the model-standard for the model it runs on and
escalates a decision it cannot settle from repository evidence back to a fresh
bounded advisor, as [luna-coordination.md](luna-coordination.md) already
describes for Luna.

## Admission packet

The packet is the only handoff. It points at repository material rather than
copying it, and it carries no transcript:

```text
Mode: <solo|executive-pack>
Repository: <path>   Worktree: <path>   Owner: <self|provider:<id>>
Base SHA: <sha>
Work items: <ordered IDs with one-line titles>
Preset: <light|high-assurance>   Review risk: <landing_policy review_risk>
Landing policy: <direct|pr-auto|pr-review>   Session Close delivery flags: <...>
Roles: <implementation owner> / <Reviewer 1> / <Reviewer 2 or "not required"> / <fallback>
Coordinator: <model and effort this packet is handed to>
Seams: <public seam and RED test per vertical slice, or the non-TDD reason>
Decisions: <boundary decisions from admission, each with its reason>
Pointers: <work-order refs, ADR paths, affected paths, focused commands>
Open: <anything admission could not settle, with who decides>
```

The packet is delivery state, not repository content; conversation chronology
is neither. Write it to the repository's shared Git directory, never to the
working tree:

```bash
packet="$(git rev-parse --path-format=absolute --git-common-dir)/delivery/admission-<first-work-item>.md"
mkdir -p "$(dirname "$packet")"
```

Every linked worktree of the repository on this machine resolves the same
path, so a coordinator thread in its own worktree reads the packet without a
commit, and Git can never stage it. Admission and coordinator run on the same
machine. Do not commit the packet, do not copy it into the worktree, and do
not cite it from source, tests or documentation; move a decision that must
outlive the delivery into the work order, an ADR or the pull request text.
Pass the absolute path in the initiating prompt.

## Initiating prompt for the coordinator

```text
You are the repository delivery owner for <mode> delivery of <work items> in
<repository> at <worktree>. Admission is complete; read the admission packet at
<path> and the executive-pack skill, then run `ccore delivery start` and proceed. Keep
this ownership through sequencing, finding disposition, callbacks and one Session
Close. Do not re-open admission decisions; record a new blocker instead. Use the
roles and preset in the packet; Reviewer 2, security and acceptance run only
where the packet's preset or review risk requires them. Write the pull request
text with cognovis-pr before Session Close.
```

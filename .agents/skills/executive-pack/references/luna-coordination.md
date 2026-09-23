# Optional Luna coordination

Use this profile only when the operator preselects Luna medium for the invoking session
and names the profile in the initiating prompt before admission. The prompt declares the
already-selected role; it cannot switch the session model. This is a behavioral role
choice, not a runtime profile, resolver or model switch. The default remains an
Astra-medium Codex delivery owner.

## Ownership and activation

Start the invoking repository-delivery session with `gpt-5.6-luna` at medium reasoning.
That session owns admission, sequencing, finding disposition, callbacks and exactly one
Session Close. Freeze the selection at admission. Never spawn a second delivery owner,
move an already admitted delivery to Luna, make an advisor the owner, or rotate the
delivery owner through the compact implementation-handoff contract.

Keep the existing delivery actors and evidence boundaries:

- one distinct `gpt-5.6-sol` implementation owner at high reasoning owns source and
  accepted repairs through the normal committed-handoff rules;
- one distinct `gpt-5.6-sol` RED author at high reasoning owns independent tests when
  TDD applies; and
- the selected Solo or Pack preset keeps its required fresh foreign-family reviews,
  acceptance, security and project-specific evidence.

Use a fresh read-only generic advisor with `gpt-6-astra` at xhigh reasoning only for one
of these cases:

1. **Planning:** the Luna owner has gathered the repository facts and wants one explicit
   challenge to a proposed plan, seam or sequencing decision before it acts.
2. **Blocker:** repository lookup leaves one concrete admission, sequencing, finding or
   completion decision unresolved. If that decision prevents the Luna owner from doing
   useful independent work, it may wait for the bounded answer.

One advisor answers one question and stops. A materially different later blocker uses a
new fresh context. The advisor does not inherit chat history, monitor the delivery,
write source, author RED evidence, review the candidate, dispose findings, approve
progression or invoke Session Close. If its answer does not resolve the blocker, the
Luna owner reports the actual human or provider decision needed.

## Compact coordination packet

Keep coordination state compact and recoverable from authoritative repository and
tracker material. Refresh this packet at admission, after each member or vertical slice,
after review disposition, and before Session Close:

- mode, repository, linked worktree, base or candidate SHA, ordered work items and the
  frozen role paragraph;
- current phase, next bounded action, selected public seam and applicable AC/MoC;
- open blocker or accepted finding, with its owner and exact completion condition;
- pointers to work-order text, ADRs, affected paths, focused commands and stored
  evidence, rather than copied file contents; and
- current implementation-session lineage, reviewer or advisor receipt, observed usage
  classes, and the last verified candidate SHA.

The tracker, repository, commits and evidence receipts remain authoritative. Conversation
chronology and transcripts are not delivery state. For implementation-session rotation,
use [compact-handoff.md](compact-handoff.md); an advisory result enters the packet only
as the Luna owner's decision, remaining uncertainty and evidence pointers.

## Bounded advisor packet

Send a fresh advisor only the material needed to answer one question:

```text
Role: Read-only decision advisor. Return advice; do not claim work, edit files,
review the candidate, approve progression, or take delivery ownership.

Question: <one planning decision or concrete unresolved blocker>
Decision owner: <Luna delivery-session identity>
Repository state: <repository, worktree, base/candidate SHA, current phase>
Constraints: <scope, authorization, applicable AC/MoC, fixed actor boundaries>
Evidence pointers: <work item, ADRs, paths, commands/results; no transcript>
Options already considered: <short list with the Luna owner's strongest objection>

Return:
1. recommendation and rationale;
2. repository-backed evidence for and against it;
3. risks or conditions that would change the answer; and
4. unresolved decision, if evidence cannot settle it.
```

When `skill:grilling` is available, use its design-tree idea in this bounded form.
Otherwise apply the same principle directly: challenge the current decision and its
settled prerequisites without turning every delivery into an interview or mandatory
fan-out. For an interface or seam decision, consult `skill:codebase-design` when
available. Without it, prefer a small public interface that hides complexity behind
one seam, gives callers leverage, keeps change local for maintainers, and lets tests
observe behavior through that interface. For implementation sequencing, follow the
repository's installed `skill:tdd` (`skills/tdd/SKILL.md`): one public seam, one RED
test and the minimum GREEN implementation per vertical slice. These are planning
principles; they do not add actors when the live work does not need them.

## Initiating prompt

First preselect `gpt-5.6-luna` with medium reasoning on the native surface that starts
the invoking session. Then replace the placeholders and send this paragraph before
admission. The paragraph records the role choice; it does not perform the model switch:

```text
Use the optional Luna coordination profile for <solo|executive-pack> delivery of
<work-item IDs> in <repository> at <linked worktree>, based on <base SHA>. You are the
already-running invoking repository delivery owner, preselected as gpt-5.6-luna with
medium reasoning; keep that ownership through admission, sequencing, finding
disposition, callbacks and one Session Close. Never rotate the delivery owner through
an implementation handoff. Use a distinct gpt-5.6-sol high implementation owner and,
when TDD applies, a distinct gpt-5.6-sol high RED author. Keep the selected preset's
required fresh foreign-family reviewers and existing acceptance, security and
completion roles. Maintain the compact repository-backed coordination packet. After
repository lookup, you may ask one fresh read-only gpt-6-astra xhigh advisor one
explicit planning question or one concrete unresolved blocker, then end that advisor
session and decide yourself. Do not create a watcher or transfer source, review or
completion authority.
```

Add the concrete Reviewer 1, Reviewer 2 and fallback names required by the model-routing
standard to that paragraph. Validate every requested model and effort against the native
spawn surface. A hard-pinned custom agent keeps its declared configuration; use a
compatible generic actor for the Astra advisory role.

## Measured pilot comparison

Compare this opt-in profile with the existing Astra-medium owner only across deliveries
with similar mode, scope class, repository surface and review preset. For each delivery,
record observed values rather than estimates:

- coordinator, advisor, implementation, RED, review and repair model/effort plus each
  available `uncached_input`, `cached_input` and `output` token class; mark missing
  classes `unavailable` and avoid double counting cache-inclusive totals;
- advisor activation reason and whether its answer was actionable, unused, or left a
  human/provider decision;
- accepted findings entering repair, repair rounds, focused verification result and
  terminal delivery outcome; and
- changed-path and public-seam counts needed to judge whether the compared work was
  actually similar.

Report the observations and material differences. A small or unmatched sample does not
demonstrate savings, and this pilot makes no token, cost, quality or repair-savings
claim. Do not add telemetry or delay delivery to complete a comparison when the existing
transport does not expose a value.

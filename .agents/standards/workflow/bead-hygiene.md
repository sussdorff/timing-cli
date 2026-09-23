# Bead Hygiene Standard — Library Default + Overlay Format

<!-- Decision: new file (cognovis-core/standards/workflow/bead-hygiene.md) vs extending factory-ready.md.
  Chosen: new file — separates Phase 1 gate (factory-ready: can an agent start?) from discipline
  standards (bead-hygiene: how do humans and agents review bead quality?). Decided in bead clc-dyw.5.

  IG-Capabilities NOT promoted to library default: the concept (list what the IG must provide, not
  which version) is universal, but the values are always project-specific — each project defines its
  own FHIR profile and CodeSystem surface. A library rule that says "list IG-Capabilities" without
  knowing which capabilities apply is not checkable by bead-reviewer. polaris and mira each define
  IG-Capabilities as a Major Pflichtfeld in their project overlays. -->

> **Shared contract:** This file is the machine-parseable bead spec contract shared by bead
> producers (`/create` and `/intake`) and the bead consumer
> (`bead-reviewer`). Keep only declarative required-field rules and anti-pattern rules here.
> Dynamic checks do NOT live in this file: dependency resolution, ADR-gap evaluation, the
> 5-category semantic rubric, and cache validity remain in `skills/bead-reviewer/SKILL.md`.
>
> **Calibration principle:** Each Critical Pflichtfeld must answer "would an agent get stuck
> without this?" — not "is this in my preferred slot or shape?"

## What This Is

A `bead-hygiene.md` file defines the machine-readable bead spec contract that projects and
`/bead-reviewer` share on top of the standard 6-criterion factory-ready check. When present,
these rules are loaded by `/bead-reviewer` as **Pass 3** and applied to every bead review.

This file serves two purposes:

1. **Library Default Contract** — the `## Pflichtfelder` and `## Anti-Patterns` sections below are
   auto-loaded by bead-reviewer from `~/.agents/standards/workflow/bead-hygiene.md` when available.
   They define the universal baseline that applies to all projects without any per-project configuration.
2. **Overlay Format Documentation** — the rest of this file describes how projects extend the library
   baseline with project-specific rules.

## Why Bead Size Is a Review Decision

The sizing rules below exist because a bead's Acceptance Criteria bundle is the reviewer's
unit of judgment. A reviewer — human or agent — judges one coherent change against the full
set of criteria that change is meant to satisfy. Under TDD that same bundle is the test
contract: the ACs of one bead are what RED and GREEN are written against, inside one
continuous lifecycle.

Slicing one requirement into one bead per Acceptance Criterion destroys that unit. Each
fragment is then reviewed against a criterion too narrow to show whether the change is right
for the system, and the whole-system view — the interactions, the shared surface, the
ordering the fragments imply — belongs to no reviewer at all. One-AC-per-ticket slicing is
therefore a rejected local optimization: it makes every ticket look tidy and makes their sum
unreviewable.

This is an explicit counterweight to the generic ticket habit of "split the work into many
small tickets". That habit is sound where tickets queue to different humans over weeks and
small batches reduce hand-off risk. It does not transfer here: an autonomous agent
implements and verifies a bead in one continuous lifecycle, so an extra split adds
coordination surface and review blind spots while buying back none of the hand-off savings.
Size a bead so that one requirement's Acceptance Criteria can be reviewed together as one
coherent change.

The rules below make that reasoning checkable: `BASE-COHESIVE-SCOPE` for what belongs in one
bead, `BASE-ARTIFICIAL-SPLIT` and `BASE-SLICE-INDEPENDENT-VALUE` for splits that fail this
test, and `BASE-SCOPE-EPIC` for the opposite error of packing unrelated outcomes together.

## Pflichtfelder

<!-- Library default — auto-loaded by bead-reviewer as Pass 3 baseline.
     Projects add project-specific Pflichtfelder in their project overlay at
     $REPO_ROOT/.agents/standards/bead-hygiene.md -->

- <!-- rule-id: BASE-CLEAR-INTENT --><!-- severity: critical -->Clear Intent required: feature, epic, task, and bug beads MUST describe the problem or goal in enough concrete detail that an unfamiliar agent can start without guessing. Empty placeholders (`TBD`, `See ticket`), one-line fragments without context, or descriptions that permit multiple materially different interpretations are not valid. Chore beads MAY stay brief, but the maintenance intent still has to be explicit.
  <!-- agent would get stuck because the bead would not state what problem or outcome to pursue. -->
- <!-- rule-id: BASE-OUTCOME-AC --><!-- severity: critical -->Outcome-Focused Acceptance Criteria required: feature, epic, task, and bug beads MUST include at least one Acceptance Criterion stated as an observable outcome or externally verifiable behavior. Acceptance Criteria written only as implementation steps, internal code tasks, or tool operations are not valid. Chore beads MAY omit Acceptance Criteria when the maintenance scope is already explicit in the description.
  <!-- agent would get stuck because there would be no externally checkable definition of done. -->
- <!-- rule-id: BASE-BUG-PROPORTIONAL-AC --><!-- severity: critical --><!-- types: bug -->Bug AC proportionality required: default to one Acceptance Criterion for the reported failing case now behaving as expected. Add one adjacent control-case AC only when the fix can plausibly regress that behavior. Implementation constraints, general quality goals, delivery gates, and nearby feature behavior belong in Scope-Out or constraints, not in additional bug ACs.
  <!-- semantic authoring policy from clc-2acb; the deterministic author check validates rule shape but cannot infer the defect boundary. -->
- <!-- rule-id: BASE-MOC --><!-- severity: critical --><!-- types: feature,epic,task,bug -->MoC Table required: feature, epic, task, and bug beads MUST contain a Means of Compliance table with one row per Acceptance Criterion. Valid MoC values: `unit`, `integ`, `e2e`, `smoke`, `review`, `UAT`, `demo`, `doc`. Concrete anchor evidence may appear in the Evidence column, inline in the MoC cell, or inline in the Acceptance Criterion body. Evidence MUST be a concrete anchor (file path, test name, query, screenshot location); placeholders are not valid.
  <!-- verification obligations follow the outcome and risk, not a size label. -->
- <!-- rule-id: BASE-BUG-PROPORTIONAL-MOC --><!-- severity: critical --><!-- types: bug -->Bug MoC proportionality required: use the smallest focused regression check that fails before and passes after the fix. Do not require a full test suite, unrelated service or system, tenant/customer dataset, browser/platform matrix, E2E/UAT/demo flow, deployment, release build, health check, or push preflight unless the reported defect itself exists across that exact boundary. Repository-wide delivery gates are not additional bug MoC rows. Missing production-like data does not justify an invented staging, Playwright, or UI substitute flow.
  <!-- semantic authoring policy from clc-2acb; the deterministic author check validates rule shape but cannot infer the defect boundary. -->
- <!-- rule-id: BASE-INTENT-BLOCK --><!-- severity: critical --><!-- types: feature,epic,task,bug -->## Intent block required: feature, epic, task, and bug beads MUST include a `## Intent` block in the description following `standards/beads/intent-section.md` with exactly `Goal:`, `Scope-In:`, and `Scope-Out:` keys. Chore beads MAY omit the block when the maintenance intent is already explicit in the description.
  <!-- agent would get stuck because it could not determine the behavioral goal, in-scope surface, or explicit exclusions before starting implementation. -->
- <!-- rule-id: BASE-HUMAN-DECISION-GATE --><!-- severity: critical --><!-- types: feature,epic,task,bug -->Human Decision Gate required when human confirmation controls execution: if a bead requires a human to decide whether work may proceed, deploy, close, or continue, the gate MUST be authored as a `## Human Decision Gate` section following `standards/judge-layer/decision-gate.md`. The gate MUST stay outside ordinary outcome Acceptance Criteria.
  <!-- agent would get stuck because the decision owner, timing, allowed outcomes, and minimum evidence plan would be implicit. -->
- <!-- rule-id: BASE-REVIEW-RISK --><!-- severity: critical --><!-- types: feature,epic,task,bug -->Review-Risk classification required: feature, epic, task, and bug beads MUST declare exactly one `Review-Risk:` line in the description with one of `none`, `payment`, `pii`, `auth`, or `compliance`. Repository Delivery reads that single durable classification to resolve its landing policy; payment, PII, authentication/access-control, and compliance work always lands through human pull-request review. A missing, unknown, or repeated declaration blocks dispatch. The classification may be recorded at authoring or at admission, but it MUST exist before dispatch: Chore beads MAY omit it at authoring, and admission MUST record one before handing the bead to a repository delivery, which refuses every unclassified bead regardless of type.
  <!-- agent would get stuck because the delivery would have to guess whether the change may land without human review. -->
- <!-- rule-id: BASE-PRIORITY-CONSEQUENCE --><!-- severity: major --><!-- types: feature,epic,task,bug,chore -->Priority by consequence of delay required: `priority` answers "what gets worse while this bead stays open", never how large the diff is, how much effort it takes, or how new the work is. Scale: `P0` while open, the harness, a delivery process, or production produces wrong results, or every delivery in its area reproduces a known failure class - nothing else in that area is dispatched first; `P1` while open, a committed outcome (customer, release, dependent bead) is blocked or degrades; `P2` default - value is delayed, nothing gets worse; `P3` improvement whose only cost of delay is the missed benefit; `P4` idea or backlog. A bead whose description shows a P0 or P1 consequence but carries a lower priority is mis-prioritised; a small diff with a P0 consequence is P0.
  <!-- 2026-08-27: five harness-recovery beads were authored at P1/P2 because their diffs were small, while every adapter delivery in every repository kept reproducing the failure they fix. -->
- <!-- rule-id: BASE-COHESIVE-SCOPE --><!-- severity: critical -->Cohesive Scope required: a bead MUST describe one coherent outcome that can be implemented and verified in one continuous task lifecycle. Mixed unrelated outcomes or work requiring independent child delivery is invalid. This is a cohesion rule, not a duration or size estimate.
  <!-- agent would get stuck because the work would split into multiple incompatible execution paths. -->
- <!-- rule-id: BASE-IG-OVERLAY --><!-- severity: major --><!-- types: chore -->IG-bump chores are not exempt from project overlay Pflichtfelder: if the bead purpose is to bump an IG, bundle, or codegen pin, it MUST include `## Aidbox-Schema-Impact`, `## Adapter-Test-Tier`, and project-level `## IG-Capabilities`.
- <!-- rule-id: BASE-IG-CLOSE-EVIDENCE --><!-- severity: major --><!-- types: chore -->IG-bump chores MUST close only after the final pin is recorded in `close_reason` with the actual version scheme (`SemVer`, `CalVer`, or `build-hash`), README/comment references match the landed pin, readiness flags such as `*_BUNDLE_READY` are flipped, and downstream gates are green.
- <!-- rule-id: BASE-IG-VERSION-SCHEME --><!-- severity: major --><!-- types: chore -->When an IG-bump chore migrates between version schemes (`SemVer` ↔ `CalVer` ↔ `build-hash`), `close_reason` MUST record the actual landed version scheme, not the intended one.

## Anti-Patterns

<!-- Library default — auto-loaded by bead-reviewer as Pass 3 baseline. -->

- <!-- rule-id: BASE-TITLE-PHASE --><!-- severity: critical -->TITLE-PHASE: Phase-name without outcome — title starts with or consists primarily of "Setup", "Refactor", "Migration", "Initialize", "Configure", "Deploy", or "Migrate" without naming the user or system outcome delivered. A title such as "Setup Database so users can register" is valid because the outcome is explicit.
- <!-- rule-id: BASE-TITLE-ACTIVITY --><!-- severity: critical -->TITLE-ACTIVITY: Activity-named instead of outcome-named — title says "Implement X", "Write Y", or "Create Z" where X/Y/Z is a technical artifact instead of a user or system outcome.
- <!-- rule-id: BASE-TITLE-PATH --><!-- severity: critical -->TITLE-PATH: File/path as title — title is literally a file path, module name, or implementation surface instead of the outcome being delivered.
- <!-- rule-id: BASE-TITLE-VAGUE --><!-- severity: critical -->TITLE-VAGUE: Vague title — titles such as "Improve performance", "Fix issues", "Cleanup", or "Refactor code" without a concrete target or outcome are not actionable enough.
- <!-- rule-id: BASE-AC-STEP --><!-- severity: critical -->AC-STEP: Acceptance Criterion as implementation step — an AC starts with "Write a function", "Create a class", "Add a method", "Implement", or similar internal build-step phrasing instead of observable behavior.
- <!-- rule-id: BASE-AC-ZERO --><!-- severity: critical -->AC-ZERO: Zero Acceptance Criteria — feature, epic, task, or bug bead contains no Acceptance Criteria at all.
- <!-- rule-id: BASE-AC-TRIVIAL --><!-- severity: critical -->AC-TRIVIAL: Trivial Acceptance Criterion — AC says only "works correctly", "no bugs", "tests green", "all tests pass", "functions as expected", or a similarly unmeasurable placeholder.
- <!-- rule-id: BASE-AC-REF --><!-- severity: critical -->AC-REF: Acceptance Criterion references only other beads — AC says "see bead X", "as per bead Y", or "per spec in bead Z" without restating the actual criterion here.
- <!-- rule-id: BASE-SCOPE-EPIC --><!-- severity: critical -->SCOPE-EPIC: Epic-scope packed into a single bead — description or ACs combine multiple separate features or unrelated outcomes that should be sliced into child beads.
- <!-- rule-id: BASE-SCOPE-DOCS-ONLY --><!-- severity: critical -->SCOPE-DOCS-ONLY: Pure docs-bead inside feature work — the bead's only output is documentation for functionality delivered by another implementation bead.
- <!-- rule-id: BASE-SCOPE-FORWARD-DEP --><!-- severity: critical -->SCOPE-FORWARD-DEP: Forward-dependency on unplanned work — description or ACs justify the bead mainly by speculative future work ("this will be used by future bead X", "once bead Y exists, this will enable Z") rather than current value.
- <!-- rule-id: BASE-SCOPE-MULTI-CONCERN --><!-- severity: critical -->SCOPE-MULTI-CONCERN: Multi-concern requiring separate review sessions — the bead combines concerns that need independent UAT, separate stakeholder review, or different domain expertise.
- <!-- rule-id: BASE-ARTIFICIAL-SPLIT --><!-- severity: major -->ARTIFICIAL-SPLIT: Same-repo open or in-progress beads that share the same release unit, package/artifact publish, version bump, review path, single verification gate/environment, or UAT intent — or that stand in a producer→sole-consumer relationship (an extracted module and the migration that first uses it; an inventory/dump step and the evidence layer that gives it meaning) — are presumed to be one bead unless this bead records a concrete no-fit rationale for staying separate.
- <!-- rule-id: BASE-SLICE-INDEPENDENT-VALUE --><!-- severity: major -->SLICE-NO-INDEPENDENT-VALUE: Over-slicing — a proposed slice that cannot be reviewed or verified on its own (its correctness only becomes checkable once a sibling slice lands), or where every sibling shares the same single verification gate, is not a valid standalone bead. A slice earns its own bead ONLY via at least one of: (a) independent verifiability/value, (b) different risk profile or verification environment, or (c) genuine parallelism. Otherwise merge the slices.
- <!-- rule-id: BASE-PRIORITY-BY-SIZE --><!-- severity: major -->PRIORITY-BY-SIZE: Priority derived from diff size, effort, or novelty - the priority is justified (in the bead or by the author) with "small change", "quick", "large refactor", "only a doc edit", or an effort word, instead of with what gets worse while the bead stays open.
- <!-- rule-id: BASE-MOC-CONCRETE --><!-- severity: critical -->A MoC entry without a concrete Evidence anchor is not a MoC. Every MoC row must identify exactly where compliance can be verified (file path, test name, query), not a future placeholder.
- <!-- rule-id: BASE-NO-HUMAN-EVIDENCE-AUDITOR --><!-- severity: critical -->Human-as-evidence-auditor: bead wording MUST NOT make a human prove tests, evidence, implementation correctness, completion, or "done" status. Humans may make manager-decidable risk decisions through `## Human Decision Gate`; executable evidence and review artifacts prove implementation outcomes.
- <!-- rule-id: BASE-IG-CAPABILITIES --><!-- severity: critical -->Pin IG capabilities, not version numbers, in bead descriptions and Acceptance Criteria. Reference the latest published version. If a required capability is missing, extend the IG in a dedicated bead rather than mocking it locally.
- <!-- rule-id: BASE-REF-FABRICATED --><!-- severity: major -->REF-FABRICATED: an identifier cited anywhere in the bead MUST correspond to a real, verifiable source. If it cannot be verified at authoring time, omit it or mark it explicitly as unverified; never present a guessed key as established fact.
- <!-- rule-id: BASE-REVIEW-HISTORY --><!-- severity: critical -->REVIEW-HISTORY: Reviewer-Fix, review-round, and correction-log sections are not specification content. Accepted findings MUST change or remove the affected authoritative text; they MUST NOT be appended as review chronology while superseded wording remains.
- <!-- rule-id: BASE-COMMIT-ATTRIBUTION --><!-- severity: critical --><!-- types: chore -->Mis-attributed commits: do not piggyback unrelated work onto a closed bead's commit prefix. Use one bead prefix per commit.

## Optionale Felder (Universally Recommended)

These are not enforced by Pass 3, but strongly recommended in all project beads:

- **Out of Scope** — explicitly list what is NOT part of this bead. Prevents scope creep during review.
- **Pre-Mortem** — assess risk level GREEN / AMBER / RED with mitigations. Required when risk is AMBER or RED.

## IG-Bump Chore

Use this section when the bead purpose is to bump an IG, bundle, or codegen pin. These chores are a special case: the usual chore exemption does not apply because the pin change is the moment new CodeSystems, ValueSets, and StructureDefinitions become installable in Aidbox.

### Pattern 1: Chore exempt from hygiene sections is wrong here

For IG-bump chores, the following sections are REQUIRED and not exempt:

- `## Aidbox-Schema-Impact`
- `## Adapter-Test-Tier`
- project-level `## IG-Capabilities`

This override applies even though the bead type is `chore`. If the bead purpose is to bump an IG/bundle/codegen pin, the chore-exempt pattern does not apply.

### Pattern 2: Sizing default under-estimates blast radius

Default sizing for IG-bump chores is `medium`. An IG-bump can touch hundreds of generated files, CI allowlists, bundle-readiness gates, and downstream capability sections. Do not size it as `small`.

### Pattern 3: Close-criteria omit downstream gates

Close criteria for IG-bump chores MUST include all of the following:

- Actual final pin recorded in `close_reason`, including the version scheme used (`SemVer`, `CalVer`, or `build-hash`)
- All README and comment references aligned with the landed pin, with no scheme drift
- Readiness flags flipped before close, for example `*_BUNDLE_READY`
- Downstream gates green:
  - CI canonical allowlist updated
  - bundle-readiness check passes
  - post-codegen patches are scripted and reproducible, not manual edits
  - downstream bead capability sections updated where relevant

### Pattern 4: close_reason drift between scheme migrations

When a project migrates between version schemes (`SemVer` ↔ `CalVer` ↔ `build-hash`), `close_reason` and follow-up references tend to diverge. The `close_reason` MUST record the actual landed version scheme, not the intended one.

### Pattern 5: Mis-attributed commits

Commit-prefix discipline: one bead prefix per commit. Do not piggyback unrelated work onto a closed bead's prefix. That pollutes retrospective analysis and makes it look like the bead had more fix cycles than it really did.

> **Note:** A future machine-checkable `bead-reviewer` follow-up that detects IG-bump chores automatically is out of scope for this section, but it is a recommended enhancement.

## How Projects Extend This

Projects place their overlay at:

```
$REPO_ROOT/.agents/standards/bead-hygiene.md
```

bead-reviewer loads rules from **two sources** and merges them:

1. **Library default** at `~/.agents/standards/workflow/bead-hygiene.md` — the `## Pflichtfelder` and
   `## Anti-Patterns` sections above. Applied to every project automatically when installed.
2. **Project overlay** at `$REPO_ROOT/.agents/standards/bead-hygiene.md` — project-specific additions.

Projects define ONLY their project-specific rules — no need to copy universal rules from this file.

Cross-link format for project overlays:

```markdown
> **Library defaults:** Universal contract rules are auto-loaded from the cognovis-core library
> default. See
> [cognovis-core/standards/workflow/bead-hygiene.md](https://github.com/cognovis/library-core/blob/main/standards/workflow/bead-hygiene.md).
> This file contains only project-specific additions.
```

---

## Overlay Format Reference

### File Location

```
$REPO_ROOT/.agents/standards/bead-hygiene.md
```

`$REPO_ROOT` is the git repository root (resolved via `git rev-parse --show-toplevel`), or the parent directory of `.beads/` as a fallback.

### File Structure

The overlay file is a Markdown document with two optional sections:

```markdown
# Bead Hygiene Overlay

## Pflichtfelder

- Each bullet item here is a required-field rule.
- A rule may start with a severity comment: <!-- severity: critical|major|minor -->
- Default severity if no comment is present: Critical.

## Anti-Patterns

- Each bullet item here is a prohibited pattern rule.
- <!-- severity: major -->This rule is Major severity, not Critical.
- Rules without severity comments default to Critical.
```

Rules outside these two sections are ignored. Both sections are optional — if a section is absent, it is silently skipped.

### Sections

#### `## Pflichtfelder` (Required Fields)

Rules in this section express what a bead MUST contain. Each rule is evaluated by asking: "Does this bead include the required element described in this rule?"

Examples:
- Every feature bead MUST reference Aidbox-Schema-Impact in the description when modifying FHIR resources.
- Every bead MUST include a rollback note in the description.

#### `## Anti-Patterns` (Prohibited Patterns)

Rules in this section express what a bead MUST NOT do or contain. Each rule is evaluated by asking: "Does this bead exhibit the prohibited pattern described in this rule?"

Examples:
- Bead description or ACs reference a hardcoded tenant ID instead of parameterizing.
- Feature bead modifies a shared library without a compatibility note.

### Per-Rule Severity

Each rule defaults to **Critical** severity. A rule can declare a lower severity by prefixing the rule text with an HTML comment:

```markdown
- <!-- severity: critical -->This rule is Critical — overrides verdict to NEEDS INTERACTIVE WORK.
- <!-- severity: major -->This rule is Major — appears in warnings, does not override verdict.
- <!-- severity: minor -->This rule is Minor — appears in warnings, does not override verdict.
```

Only **Critical** findings override the verdict to NEEDS INTERACTIVE WORK. Major and Minor findings are included in the Warnings section of the report.

### Per-Rule Type Filter (Optional)

A rule may optionally restrict itself to specific bead types:

```markdown
- <!-- types: feature,task -->Rule applies only to feature and task beads.
- <!-- severity: major --><!-- types: feature -->Rule is Major severity, applies only to feature beads.
- Rule without types comment applies to ALL bead types (default).
```

Both `<!-- severity: ... -->` and `<!-- types: ... -->` comments may appear on the same rule, in any order. Type matching is case-insensitive. If the bead's `type` does not appear in the types list, the rule is skipped for that bead — no finding is emitted.

### Behavior When Both Sources Are Missing

The library baseline is mandatory. A missing baseline is a configuration error. The project delta
at `$REPO_ROOT/.agents/standards/bead-hygiene.md` is optional and its absence is reported as such.

### Behavior on Parse Errors

If a file exists but cannot be parsed (no recognized sections, malformed content), `/bead-reviewer`
emits a single warning line and continues with Pass 1 + Pass 2 results only.

### Example Overlay File

```markdown
# Bead Hygiene Overlay — Polaris Project

> **Library defaults:** Universal contract rules are auto-loaded from the cognovis-core library
> default. This file contains only polaris-specific additions.

## Pflichtfelder

- <!-- severity: critical -->Every bead that modifies an Aidbox resource schema MUST include a
  section "## Aidbox-Schema-Impact" describing new/changed resource types, whether aidbox-reset.sh
  is required, and any provisioning changes (CodeSystems, ValueSets, ConceptMaps).

## Anti-Patterns

- <!-- severity: critical -->Aidbox-Schema-Impact omitted: A bead modifies an Aidbox resource
  (adds/removes fields, changes cardinality) but does not include the Aidbox-Schema-Impact section.
```

## Reference

- `/bead-reviewer` — automated command that runs Pass 1, Pass 2, and Pass 3 for a bead
- `standards/workflow/factory-ready.md` — core 6-criterion factory-ready spec quality gate

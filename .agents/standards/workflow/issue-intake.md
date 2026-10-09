# Issue Intake Standard - Library Default + Overlay Format

> **Shared contract:** This file is the machine-parseable issue contract shared by the issue
> producer (`intake`, which runs `issue-author-check.py` before every `ccore tracker create`
> or `ccore tracker update`) and the issue consumers (`workplan` scoring and delivery
> admission). Keep only declarative required-field rules and anti-pattern rules here. Dynamic
> checks do NOT live in this file: dependency resolution, ADR-gap evaluation, the semantic
> rubric, and cache validity remain in the consuming skills.
>
> **Calibration principle:** Each critical Pflichtfeld must answer "would an agent get stuck
> without this?" - not "is this in my preferred slot or shape?"

## What This Is

A hosted issue (GitHub or Forgejo) is the work order. `ccore tracker create --body-file` turns
the Markdown body into the issue: the first column-0 `Goal:` line becomes the title, the
first column-0 `Type:` line becomes the `type:<value>` label, and the first column-0
`Review-Risk:` line becomes the `review-risk:<value>` label. `ccore` reads these lines from the
raw body, including lines inside fenced code blocks, and it does not see a bulleted or indented
field. Column-0 `Blocked by:` lines are the body's dependency record. On Forgejo,
`ccore tracker create` (ccore 2026.9.18 or later) also wires each one as a native issue
dependency; on GitHub they stay a body record that `ccore tracker show` reports. The rules
below make that body both parseable by `ccore` and executable by an agent.

This file serves two purposes:

1. **Library Default Contract** - the `## Pflichtfelder` and `## Anti-Patterns` sections below
   are the universal baseline. Consumers load them from
   `.agents/standards/workflow/issue-intake.md` in the target repository, then from
   `~/.agents/standards/workflow/issue-intake.md`.
2. **Overlay Format Documentation** - the rest of this file describes how projects extend the
   library baseline with project-specific rules.

## Issue Body Shape

```markdown
Type: feature
Review-Risk: none
Blocked by: https://git.cognovis.de/cognovis/library-core/issues/12

## Intent

Goal: Finance users can export the filtered invoice list as CSV
Scope-In: Export trigger, CSV response, filtered query reuse.
Scope-Out: New billing calculations.

## Acceptance Criteria

1. Finance users can export the filtered invoice list as CSV.

## Means of Compliance

| AC | Criterion | MoC | Evidence |
|---|---|---|---|
| AC1 | Filtered export as CSV | e2e | tests/billing/invoice-export.spec.ts |
```

- `Type:` is one of `feature`, `task`, or `bug`. Portfolio containers are not issue types; a
  larger change is a set of independent issues linked by `Blocked by:`.
- An optional H1 heading must repeat the Goal verbatim. Without an H1 the Goal is the title.
- `Blocked by:` is optional and may repeat; each value is a full issue URL. It records the
  dependency in the body; it does not create a host-side dependency link.
- Write the `Goal:`, `Type:` and `Review-Risk:` lines exactly once at column 0; only
  `Blocked by:` may repeat. A fenced example with a column-0 field line changes what `ccore`
  parses; indent such example lines instead.

## Why Issue Size Is a Review Decision

The sizing rules below exist because an issue's Acceptance Criteria bundle is the reviewer's
unit of judgment. A reviewer - human or agent - judges one coherent change against the full
set of criteria that change is meant to satisfy. Under TDD that same bundle is the test
contract: the ACs of one issue are what RED and GREEN are written against, inside one
continuous lifecycle.

Slicing one requirement into one issue per Acceptance Criterion destroys that unit. Each
fragment is then reviewed against a criterion too narrow to show whether the change is right
for the system, and the whole-system view - the interactions, the shared surface, the
ordering the fragments imply - belongs to no reviewer at all. One-AC-per-ticket slicing is
therefore a rejected local optimization: it makes every ticket look tidy and makes their sum
unreviewable.

This is an explicit counterweight to the generic ticket habit of "split the work into many
small tickets". That habit is sound where tickets queue to different humans over weeks and
small batches reduce hand-off risk. It does not transfer here: an autonomous agent
implements and verifies an issue in one continuous lifecycle, so an extra split adds
coordination surface and review blind spots while buying back none of the hand-off savings.
Size an issue so that one requirement's Acceptance Criteria can be reviewed together as one
coherent change.

The rules below make that reasoning checkable: `BASE-COHESIVE-SCOPE` for what belongs in one
issue, `BASE-ARTIFICIAL-SPLIT` and `BASE-SLICE-INDEPENDENT-VALUE` for splits that fail this
test, and `BASE-SCOPE-EPIC` for the opposite error of packing unrelated outcomes together.

## Pflichtfelder

<!-- Library default. Projects add project-specific Pflichtfelder in their project overlay at
     $REPO_ROOT/.agents/standards/issue-intake.md -->

- <!-- rule-id: BASE-TYPE --><!-- severity: critical -->Type field required: every issue MUST declare exactly one column-0 `Type:` line with `feature`, `task`, or `bug`. `ccore tracker create` reads only a column-0 line; a bullet or indented `Type:` is invisible to it and silently yields `type:task`.
  <!-- agent would get stuck because the delivery could not tell which verification profile applies. -->
- <!-- rule-id: BASE-GOAL-TITLE --><!-- severity: critical -->Goal title required: every issue MUST contain exactly one non-empty column-0 `Goal:` line. `ccore tracker create` uses the first one as the issue title; an optional H1 heading MUST repeat that Goal verbatim.
  <!-- agent would get stuck because the issue title and the stated goal would disagree. -->
- <!-- rule-id: BASE-BLOCKED-BY-URL --><!-- severity: critical -->Blocked-by issue URL required: every column-0 `Blocked by:` line MUST name one full issue URL (`https://<host>/<owner>/<repo>/issues/<number>`). Short references, pull-request URLs, and tracker-local IDs are not valid dependency records.
  <!-- agent would get stuck because the ordering the author intended would not exist on the tracker. -->
- <!-- rule-id: BASE-CLEAR-INTENT --><!-- severity: critical -->Clear Intent required: every issue MUST describe the problem or goal in enough concrete detail that an unfamiliar agent can start without guessing. Empty placeholders (`TBD`, `See ticket`), one-line fragments without context, or descriptions that permit multiple materially different interpretations are not valid.
  <!-- agent would get stuck because the issue would not state what problem or outcome to pursue. -->
- <!-- rule-id: BASE-OUTCOME-AC --><!-- severity: critical -->Outcome-Focused Acceptance Criteria required: every issue MUST include at least one Acceptance Criterion stated as an observable outcome or externally verifiable behavior. Acceptance Criteria written only as implementation steps, internal code tasks, or tool operations are not valid.
  <!-- agent would get stuck because there would be no externally checkable definition of done. -->
- <!-- rule-id: BASE-BUG-PROPORTIONAL-AC --><!-- severity: critical --><!-- types: bug -->Bug AC proportionality required: default to one Acceptance Criterion for the reported failing case now behaving as expected. Add one adjacent control-case AC only when the fix can plausibly regress that behavior. Implementation constraints, general quality goals, delivery gates, and nearby feature behavior belong in Scope-Out or constraints, not in additional bug ACs.
  <!-- semantic authoring policy; the deterministic author check validates rule shape but cannot infer the defect boundary. -->
- <!-- rule-id: BASE-MOC --><!-- severity: critical --><!-- types: feature,task,bug -->MoC Table required: every issue MUST contain a `## Means of Compliance` table with one row per Acceptance Criterion. Valid MoC values: `unit`, `integ`, `e2e`, `smoke`, `review`, `UAT`, `demo`, `doc`. Concrete anchor evidence may appear in the Evidence column, inline in the MoC cell, or inline in the Acceptance Criterion body. Evidence MUST be a concrete anchor (file path, test name, query, screenshot location); placeholders are not valid.
  <!-- verification obligations follow the outcome and risk, not a size label. -->
- <!-- rule-id: BASE-BUG-PROPORTIONAL-MOC --><!-- severity: critical --><!-- types: bug -->Bug MoC proportionality required: use the smallest focused regression check that fails before and passes after the fix. Do not require a full test suite, unrelated service or system, tenant/customer dataset, browser/platform matrix, E2E/UAT/demo flow, deployment, release build, health check, or push preflight unless the reported defect itself exists across that exact boundary. Repository-wide delivery gates are not additional bug MoC rows. Missing production-like data does not justify an invented staging, Playwright, or UI substitute flow.
  <!-- semantic authoring policy; the deterministic author check validates rule shape but cannot infer the defect boundary. -->
- <!-- rule-id: BASE-INTENT-BLOCK --><!-- severity: critical --><!-- types: feature,task,bug -->## Intent block required: every issue MUST include a `## Intent` section that carries the column-0 `Goal:` line. `Scope-In:` and `Scope-Out:` SHOULD follow the Goal to name the in-scope surface and the explicit exclusions.
  <!-- agent would get stuck because it could not determine the behavioral goal before starting implementation. -->
- <!-- rule-id: BASE-HUMAN-DECISION-GATE --><!-- severity: critical --><!-- types: feature,task,bug -->Human Decision Gate only for a production change or a customer message: an issue that changes a service customers use (or one holding real customer or patient data), or sends a customer a message with content, MUST author that approval as one `## Human Decision Gate` section following `standards/judge-layer/decision-gate.md`, with `Approval class: production-change` or `customer-message`. One gate covers every listed action, retry and rollback; do not stage separate approvals. Internal work (own and managed machines, CI, Forgejo, secrets in the `cognovis-dev` vault, test and synthetic environments) MUST NOT carry a gate. The gate MUST stay outside ordinary outcome Acceptance Criteria.
  <!-- agent would get stuck because the decision owner, timing, allowed outcomes, and minimum evidence plan would be implicit. -->
- <!-- rule-id: BASE-REVIEW-RISK --><!-- severity: critical --><!-- types: feature,task,bug -->Review-Risk classification required: every issue MUST declare exactly one `Review-Risk:` line in the body with one of `none`, `payment`, `pii`, `auth`, or `compliance`. pr-agent applies that single durable classification as the floor of the pull request's `review-risk:*` label. The class classifies and informs; it does not by itself require human pull-request review. A class other than `none` needs a concrete damage scenario, and `pii` needs a crossing defined in the repository's PII boundary standard; the `executive-pack` standard's Review risk section holds these rules. A missing, unknown, or repeated declaration blocks authoring and dispatch.
  <!-- agent would get stuck because reviewers and pr-agent would have to guess the sensitive scope of the change. -->
- <!-- rule-id: BASE-COHESIVE-SCOPE --><!-- severity: critical -->Cohesive Scope required: an issue MUST describe one coherent outcome that can be implemented and verified in one continuous task lifecycle. Mixed unrelated outcomes or work requiring independent child delivery is invalid. This is a cohesion rule, not a duration or size estimate.
  <!-- agent would get stuck because the work would split into multiple incompatible execution paths. -->
- <!-- rule-id: BASE-IG-BUMP --><!-- severity: major -->IG-bump issues carry the project overlay Pflichtfelder: if the issue bumps an IG, bundle, or codegen pin, it MUST include `## Aidbox-Schema-Impact`, `## Adapter-Test-Tier`, and project-level `## IG-Capabilities`, and its Acceptance Criteria MUST cover the landed pin and its version scheme, aligned references, flipped readiness flags, and green downstream gates (see "IG-Bump Issues" below).

## Anti-Patterns

<!-- Library default. -->

- <!-- rule-id: BASE-TITLE-PHASE --><!-- severity: critical -->TITLE-PHASE: Phase-name without outcome - the Goal starts with or consists primarily of "Setup", "Refactor", "Migration", "Initialize", "Configure", "Deploy", or "Migrate" without naming the user or system outcome delivered. A Goal such as "Setup Database so users can register" is valid because the outcome is explicit.
- <!-- rule-id: BASE-TITLE-ACTIVITY --><!-- severity: critical -->TITLE-ACTIVITY: Activity-named instead of outcome-named - the Goal says "Implement X", "Write Y", or "Create Z" where X/Y/Z is a technical artifact instead of a user or system outcome.
- <!-- rule-id: BASE-TITLE-PATH --><!-- severity: critical -->TITLE-PATH: File/path as title - the Goal is literally a file path, module name, or implementation surface instead of the outcome being delivered.
- <!-- rule-id: BASE-TITLE-VAGUE --><!-- severity: critical -->TITLE-VAGUE: Vague title - Goals such as "Improve performance", "Fix issues", "Cleanup", or "Refactor code" without a concrete target or outcome are not actionable enough.
- <!-- rule-id: BASE-AC-STEP --><!-- severity: critical -->AC-STEP: Acceptance Criterion as implementation step - an AC starts with "Write a function", "Create a class", "Add a method", "Implement", or similar internal build-step phrasing instead of observable behavior.
- <!-- rule-id: BASE-AC-ZERO --><!-- severity: critical -->AC-ZERO: Zero Acceptance Criteria - the issue contains no Acceptance Criteria at all.
- <!-- rule-id: BASE-AC-TRIVIAL --><!-- severity: critical -->AC-TRIVIAL: Trivial Acceptance Criterion - AC says only "works correctly", "no bugs", "tests green", "all tests pass", "functions as expected", or a similarly unmeasurable placeholder.
- <!-- rule-id: BASE-AC-REF --><!-- severity: critical -->AC-REF: Acceptance Criterion references only other issues - AC says "see issue X", "as per issue Y", or "per spec in issue Z" without restating the actual criterion here.
- <!-- rule-id: BASE-WHY-AC-COVERAGE --><!-- severity: major -->WHY-AC-GAP: Motivation defect without Acceptance Criterion - the Intent, motivation or problem statement names a defect that no Acceptance Criterion covers and no `Scope-Out:` line excludes. Before creating the issue, point at the criterion that covers each named defect or write the exclusion. A defect that spans several commands or entry points needs one criterion per command, and at least one criterion must exercise the defaults rather than a fixture that sets matching flags.
- <!-- rule-id: BASE-SCOPE-EPIC --><!-- severity: critical -->SCOPE-EPIC: Several outcomes packed into a single issue - the body or ACs combine multiple separate features or unrelated outcomes that should be independent issues linked by `Blocked by:`.
- <!-- rule-id: BASE-SCOPE-DOCS-ONLY --><!-- severity: critical -->SCOPE-DOCS-ONLY: Pure docs issue inside feature work - the issue's only output is documentation for functionality delivered by another implementation issue.
- <!-- rule-id: BASE-SCOPE-FORWARD-DEP --><!-- severity: critical -->SCOPE-FORWARD-DEP: Forward-dependency on unplanned work - the body or ACs justify the issue mainly by speculative future work ("this will be used by a future issue", "once issue Y exists, this will enable Z") rather than current value.
- <!-- rule-id: BASE-SCOPE-MULTI-CONCERN --><!-- severity: critical -->SCOPE-MULTI-CONCERN: Multi-concern requiring separate review sessions - the issue combines concerns that need independent UAT, separate stakeholder review, or different domain expertise.
- <!-- rule-id: BASE-ARTIFICIAL-SPLIT --><!-- severity: major -->ARTIFICIAL-SPLIT: Open same-repo issues that share the same release unit, package/artifact publish, version bump, review path, single verification gate/environment, or UAT intent - or that stand in a producer-to-sole-consumer relationship (an extracted module and the migration that first uses it; an inventory/dump step and the evidence layer that gives it meaning) - are presumed to be one issue unless this issue records a concrete no-fit rationale for staying separate.
- <!-- rule-id: BASE-SLICE-INDEPENDENT-VALUE --><!-- severity: major -->SLICE-NO-INDEPENDENT-VALUE: Over-slicing - a proposed slice that cannot be reviewed or verified on its own (its correctness only becomes checkable once a sibling slice lands), or where every sibling shares the same single verification gate, is not a valid standalone issue. A slice earns its own issue ONLY via at least one of: (a) independent verifiability/value, (b) different risk profile or verification environment, or (c) genuine parallelism. Otherwise merge the slices.
- <!-- rule-id: BASE-MOC-CONCRETE --><!-- severity: critical -->A MoC entry without a concrete Evidence anchor is not a MoC. Every MoC row must identify exactly where compliance can be verified (file path, test name, query), not a future placeholder.
- <!-- rule-id: BASE-NO-HUMAN-EVIDENCE-AUDITOR --><!-- severity: critical -->Human-as-evidence-auditor: issue wording MUST NOT make a human prove tests, evidence, implementation correctness, completion, or "done" status. Humans may make manager-decidable risk decisions through `## Human Decision Gate`; executable evidence and review artifacts prove implementation outcomes.
- <!-- rule-id: BASE-IG-CAPABILITIES --><!-- severity: critical -->Pin IG capabilities, not version numbers, in issue bodies and Acceptance Criteria. Reference the latest published version. If a required capability is missing, extend the IG in a dedicated issue rather than mocking it locally.
- <!-- rule-id: BASE-REF-FABRICATED --><!-- severity: major -->REF-FABRICATED: an identifier cited anywhere in the issue MUST correspond to a real, verifiable source. If it cannot be verified at authoring time, omit it or mark it explicitly as unverified; never present a guessed key as established fact.
- <!-- rule-id: BASE-AC-UNMEASURED-STATE --><!-- severity: major -->AC-UNMEASURED-STATE: an Acceptance Criterion that an existing check (a security audit, lint, build or test command) passes on existing code MUST rest on a run of that check at authoring time. Run it on the current base, record the result in `context`, and narrow the criterion or the scope to what the issue's change can make pass; an unrun assertion can make the criterion unreachable inside the issue's own Scope-Out.
- <!-- rule-id: BASE-REVIEW-HISTORY --><!-- severity: critical -->REVIEW-HISTORY: Reviewer-Fix, review-round, and correction-log sections are not specification content. Accepted findings MUST change or remove the affected authoritative text; they MUST NOT be appended as review chronology while superseded wording remains.

## Optionale Felder (Universally Recommended)

These are not enforced by the author check, but strongly recommended in all project issues:

- **Out of Scope** - explicitly list what is NOT part of this issue. Prevents scope creep during review.
- **Pre-Mortem** - assess risk level GREEN / AMBER / RED with mitigations. Required when risk is AMBER or RED.

## IG-Bump Issues

Use this section when the issue bumps an IG, bundle, or codegen pin. The pin change is the
moment new CodeSystems, ValueSets, and StructureDefinitions become installable in Aidbox, so a
pin bump is never a trivial maintenance edit.

### Required sections

- `## Aidbox-Schema-Impact`
- `## Adapter-Test-Tier`
- project-level `## IG-Capabilities`

### Blast radius

An IG bump can touch hundreds of generated files, CI allowlists, bundle-readiness gates, and
downstream capability sections. Scope-In names these surfaces explicitly.

### Acceptance Criteria cover the downstream gates

The Acceptance Criteria and Means of Compliance of an IG-bump issue cover all of the following:

- The final landed pin, including the version scheme used (`SemVer`, `CalVer`, or `build-hash`),
  is recorded in the pull request and the landing note.
- All README and comment references are aligned with the landed pin, with no scheme drift.
- Readiness flags are flipped before landing, for example `*_BUNDLE_READY`.
- Downstream gates are green:
  - CI canonical allowlist updated
  - bundle-readiness check passes
  - post-codegen patches are scripted and reproducible, not manual edits
  - downstream capability sections updated where relevant

### Version-scheme migrations

When a project migrates between version schemes (`SemVer`, `CalVer`, `build-hash`), the landing
evidence records the actual landed version scheme, not the intended one.

## How Projects Extend This

Projects place their overlay at:

```
$REPO_ROOT/.agents/standards/issue-intake.md
```

Consumers load rules from **two sources** and merge them:

1. **Library default** at `.agents/standards/workflow/issue-intake.md` (project install) or
   `~/.agents/standards/workflow/issue-intake.md` (global install) - the `## Pflichtfelder` and
   `## Anti-Patterns` sections above. Applied to every project automatically when installed.
2. **Project overlay** at `$REPO_ROOT/.agents/standards/issue-intake.md` - project-specific
   additions.

Projects define ONLY their project-specific rules - no need to copy universal rules from this
file. An overlay that restates a baseline rule with a different meaning is a contract conflict
and blocks authoring. A project overlay left at the retired pre-issue-intake location is also
blocking: move it to `.agents/standards/issue-intake.md`.

Cross-link format for project overlays:

```markdown
> **Library defaults:** Universal contract rules are auto-loaded from the cognovis-core library
> default. See
> [cognovis-core/standards/workflow/issue-intake.md](https://git.cognovis.de/cognovis/library-core/src/branch/main/standards/workflow/issue-intake.md).
> This file contains only project-specific additions.
```

---

## Overlay Format Reference

### File Location

```
$REPO_ROOT/.agents/standards/issue-intake.md
```

`$REPO_ROOT` is the git repository root (resolved via `git rev-parse --show-toplevel`).

### File Structure

The overlay file is a Markdown document with two optional sections:

```markdown
# Issue Intake Overlay

## Pflichtfelder

- Each bullet item here is a required-field rule.
- A rule may start with a severity comment: <!-- severity: critical|major|minor -->
- Default severity if no comment is present: Critical.

## Anti-Patterns

- Each bullet item here is a prohibited pattern rule.
- <!-- severity: major -->This rule is Major severity, not Critical.
- Rules without severity comments default to Critical.
```

Rules outside these two sections are ignored. Both sections are optional - if a section is
absent, it is silently skipped. Bullets inside fenced code blocks are never rules.

### Sections

#### `## Pflichtfelder` (Required Fields)

Rules in this section express what an issue MUST contain. Each rule is evaluated by asking:
"Does this issue include the required element described in this rule?"

Examples:
- Every feature issue MUST reference Aidbox-Schema-Impact in the body when modifying FHIR resources.
- Every issue MUST include a rollback note in the body.

#### `## Anti-Patterns` (Prohibited Patterns)

Rules in this section express what an issue MUST NOT do or contain. Each rule is evaluated by
asking: "Does this issue exhibit the prohibited pattern described in this rule?"

Examples:
- Issue body or ACs reference a hardcoded tenant ID instead of parameterizing.
- Feature issue modifies a shared library without a compatibility note.

### Per-Rule Severity

Each rule defaults to **Critical** severity. A rule can declare a lower severity by prefixing
the rule text with an HTML comment:

```markdown
- <!-- severity: critical -->This rule is Critical - it blocks authoring.
- <!-- severity: major -->This rule is Major - it appears as a warning.
- <!-- severity: minor -->This rule is Minor - it appears as a warning.
```

Only **Critical** findings block authoring (`NEEDS_INTERACTIVE_WORK_CRITICAL_OVERLAY`). Major and
Minor findings are reported as warnings (`FACTORY_READY_WITH_WARNINGS`).

### Per-Rule Type Filter (Optional)

A rule may optionally restrict itself to specific issue types:

```markdown
- <!-- types: feature,task -->Rule applies only to feature and task issues.
- <!-- severity: major --><!-- types: feature -->Rule is Major severity, applies only to feature issues.
- Rule without types comment applies to ALL issue types (default).
```

Both `<!-- severity: ... -->` and `<!-- types: ... -->` comments may appear on the same rule, in
any order. Type matching is case-insensitive. The issue type is its `Type:` field (`task` when
absent). If the type does not appear in the types list, the rule is skipped for that issue.

### Per-Rule Required Sections (Optional)

A rule that requires a body section declares it machine-readably, so that
`issue-author-check.py` enforces it instead of leaving it to a reviewing model:

```markdown
- <!-- rule-id: PROJ-UAT-SCENARIO --><!-- severity: critical --><!-- types: feature,task,bug --><!-- requires-section: UAT Scenario | UAT-Szenario -->UAT Scenario required: ...
```

- The value names one `## <Heading>` section. Alternative headings, such as a German alias,
  are separated by `|`. A leading `##` in the value is ignored.
- Several `requires-section` comments on one rule require every named section.
- A section satisfies the annotation when a column-0 `## <Heading>` line outside fenced code
  matches one alternative case-insensitively (a trailing qualifier that starts with
  punctuation, such as `## UAT Scenario (API)`, still matches) and the section has content
  other than whitespace and HTML comments.
- A missing or empty section is a finding whose code is the rule's `rule-id` and whose
  severity is the rule's severity, so a Critical rule blocks authoring. The `types:` filter
  applies as for every rule.
- An annotation without any heading is a contract error
  (`CONTRACT-REQUIRES-SECTION-PARSE`) that blocks authoring.
- The annotation checks only that the section exists and is not empty. Its content quality,
  and every conditional rule without the annotation, stays with the reviewing model; the
  checker does not infer section requirements from rule prose.

### Behavior When Sources Are Missing

The library baseline is mandatory. A missing baseline is a configuration error that blocks
authoring. The project overlay at `$REPO_ROOT/.agents/standards/issue-intake.md` is optional.

### Contributor Standards

An installed standard that declares `contributes_issue_intake: true` in its frontmatter adds its
`## Pflichtfelder` and `## Anti-Patterns` rules to the contract (for example
`fhir-production-data-impact`). The frontmatter key keeps its historical name for installed
compatibility.

### Example Overlay File

```markdown
# Issue Intake Overlay - Platform Project

> **Library defaults:** Universal contract rules are auto-loaded from the cognovis-core library
> default. This file contains only platform-specific additions.

## Pflichtfelder

- <!-- severity: critical -->Every issue that modifies an Aidbox resource schema MUST include a
  section "## Aidbox-Schema-Impact" describing new/changed resource types, whether aidbox-reset.sh
  is required, and any provisioning changes (CodeSystems, ValueSets, ConceptMaps).

## Anti-Patterns

- <!-- severity: critical -->Aidbox-Schema-Impact omitted: An issue modifies an Aidbox resource
  (adds/removes fields, changes cardinality) but does not include the Aidbox-Schema-Impact section.
```

## Reference

- `skills/intake/scripts/issue-author-check.py` - deterministic author check run before every
  issue create or update
- `skills/intake/scripts/issue_contract.py` - baseline, overlay, and contributor resolution
- `standards/workflow/factory-ready.md` - core factory-ready spec quality gate

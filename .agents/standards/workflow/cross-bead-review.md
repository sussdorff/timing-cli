# Cross-Bead Review Standard - Library Default + Overlay Format

<!-- Decision: new file (cognovis-core/standards/workflow/cross-bead-review.md)
  vs embedding the checklist in individual reviewer or dispatcher prompts.
  Chosen: new file - keeps the cross-bead review checklist, disposition taxonomy,
  per-bead metadata stamp, and cohort selector grammar reviewable, composable,
  versionable, and shared. Decided in bead clc-9czd.

  Project-specific patterns are not promoted into the library default. Projects
  add those checks in a project overlay at $REPO_ROOT/.agents/standards/
  cross-bead-review.md.

  Provenance: finding.category schema and the Categories section derive from
  clc-k89p. The Finding Disposition Taxonomy, the premise-verification,
  duplicate-detection, empty-spec, and cross-repo-placement categories, and
  their verifier scripts derive from clc-71y5 (finding F1). -->


> **Shared contract:** This file is the machine-parseable cross-bead review
> contract shared by `stream-reviewer`, `/stream-review`, and explicit multi-bead review
> post-wave review. Keep only library-default categories, checks, disposition
> values, metadata stamp shape, cohort selector grammar, and overlay extension
> rules here.

## What This Is

A `cross-bead-review.md` file defines the universal cross-bead review checklist
and the metadata schema used to stamp reviewed beads. Cross-bead review finds
cohort-level defects that a single-bead reviewer cannot structurally see.

This file serves two purposes:

1. **Library Default Standard** - the `## Categories`, `## Finding Disposition
   Taxonomy`, `## Per-Bead Metadata Schema`, and `## Cohort Selector Grammar`
   sections below define the universal baseline that applies to all projects.
2. **Project Overlay Documentation** - the `## Library Default vs Project
   Overlay` section describes how projects extend the library baseline with
   project-specific checks.

## Categories

Each category heading below maps to `finding.category` in the output schema as
a kebab-case slug (e.g. `IG / dependency drift` -> `ig-drift`,
`Acceptance-criteria drift` -> `acceptance-drift`). Checks within a category
are independent library-default checks.

### IG / dependency drift

- Pinned version in `package.json` / lock vs latest published on registry
- New CodeSystems / profiles / extensions in latest version that the cohort's beads researched manually or hardcoded URLs for
- Generated codegen artefacts missing for IG-shipped capabilities

### Metadata drift

- `close_reason` contradicts the bead's notes
- `close_reason` references a foreign bead-id (copy-paste bug from another bead)
- Bead claims final pin / version X but `git log -p` shows revert to Y
- `acceptance_criteria` text contains conditions the close evidence doesn't satisfy

### Dead code / feature flags

- Feature-flag constant permanently `true` with "follow-up bead may delete" comment
- Tests that assert the constant value (tautological)
- Code marked `// TODO remove after X` where X has passed

### Standard / library sync gap

- `.library.lock` `source_commit` lags canonical `HEAD` for a standard
- Local copy of a synced standard diverges from canonical
- A standard's `requires_standards` references files that don't exist in the consumer's vendor tree

### Anti-pattern propagation

- Same anti-pattern reinforced across multiple beads
- Project-overlay patterns (e.g. polaris `Patient/unknown`, `as any` casts) that the cohort's beads preserved without examining
- Banned APIs introduced or preserved

### Scope creep

- >=N fix-commits on the same file in one bead (N project-configurable, default 10)
- Bead's title doesn't match what `git log --grep=<id>` actually shipped
- Bead spec said "verify X" but PR shipped "rewrite X"

### Test quality

- Profile-conformance tests check `meta.profile` URL but never call `.validate()`
- Test added "for AC verification" doesn't actually exercise the AC behaviour
- Tests rationalize wrong behaviour via comments
- Coverage claimed in `close_reason` but not present in `git log --grep=<id>` diff
- **Skipped-test evidence:** an integration test counts as MoC evidence only if it actually ran. Conditionally-registered tests (`test.if(BACKEND_OK)(...)`, `@pytest.mark.skipif`, gated by an env/health probe) pass green when they skip — "green because skipped" is not evidence the behaviour works or the seed data exists. Distinct from `seed-data-drift`: that catches "no seed added"; this catches "the test never ran". See `standards/workflow/seed-data-parity.md`.

### ADR / project-rule compliance

- Code construction bypasses a documented helper (e.g. polaris ADR-001: every FHIR id via `makeIdHelper`)
- Mappers use forbidden raw types
- Source PK persistence (polaris ADR-002) missing from adapter-written resources

### Acceptance-criteria drift

- AC stated "live DB queries against tables A/B/C" but evidence shows only schema-level analysis
- AC stated "Docker smoke" but bead closed with codegen-only evidence
- AC stated "X canonical-URL lookups return 200" but the actual evidence covers Y < X
- "All ACs VERIFIED" close_reason where one or more ACs were demonstrably not exercised

### Premise verification *(new, 2026-05-21)*

- Bead description references a file path that no longer exists in repo
- Bead references an agent / skill / script that has been renamed, removed, or never existed
- Bead's "after merging X to main" precondition where X never landed
- Verifier: `scripts/refinement/verify-premises.py`

### Duplicate detection *(new, 2026-05-21)*

- Two beads with identical or near-identical title + description
- Beads filed by different sessions covering the same outcome
- Verifier: `scripts/refinement/find-duplicates.py`

### Empty-spec *(new, 2026-05-21)*

- Bead with `description == ""` or trivial placeholder
- Bead with no acceptance criteria after >7 days

### Cross-repo placement *(new, 2026-05-21)*

- Bead conceptually belongs to a sibling repository (e.g. memory features -> open-brain)
- Detected via `.beads/refinement-config.yml` `repos[].keywords` matching (`sibling_repos[].keywords` accepted as a fallback alias)
- Verifier: `scripts/refinement/list-sibling-repos.py`

### Seed / demo data drift *(new, 2026-05-23)*

- A cohort bead fired a seed-data Trigger Indicator (live-system dependency, integration test, or adapter/backend-seed touch) but its diff did not touch the configured seed surface
- A bead seeded an upstream-owned surface locally (forbidden-local-surface) instead of reconciling it via its owning repo
- Integration test added "for AC verification" that can only run against the live system because the seed surface was never reconciled
- Seed artifacts reconciled by hand instead of through the overlay-defined update mechanism for their seed-source type
- Rule + taxonomy + indicators: `standards/workflow/seed-data-parity.md`. The mechanical gate is `scripts/refinement/check-seed-data-parity.py` (triage, not verification), reading the machine-readable overlay at `$REPO_ROOT/.agents/standards/seed-data-parity.yml`

## Finding Disposition Taxonomy

Each finding carries a `disposition` aligned with the triage-pattern taxonomy in
[standards/workflow/triage-pattern.md](triage-pattern.md):

| Disposition | Meaning | Typical action |
|---|---|---|
| `keep` | Finding informational; no action | Record in audit, leave bead open |
| `fold` | This bead should fold into another | `bd close <id> --reason "Folded into <target>"` |
| `weed` | Bead obsolete; close with cited evidence | `bd close <id> --reason <reason>` |
| `move-to-sibling` | Belongs in sibling repo | Create equivalent bead in sibling, close source with pointer |
| `cluster-into-epic` | Multiple beads should share an epic parent | Create an author-checked epic with `bd create`, then add edges with `bd dep add` |

## Per-Bead Metadata Schema

Idempotency is critical. Each bead's metadata carries an append-only list of
review stamps:

```yaml
metadata:
  stream_reviews:
    - run_id: "2026-05-21-a1b2c3"
      cohort:
        type: label
        value: "stream:fpde-064-runtime"
        member_count: 6
      reviewed_at: "2026-05-21T06:30:00Z"
      reviewer_run_sha: "8d1d9a5e..."
      verdict: findings
      findings_touching_this_bead: 2
      report_ref: ".beads/reviews/2026-05-21-a1b2c3.md"
      categories_flagged:
        - ig-drift
        - acceptance-drift
        - premise-verification
```

| Field | Type | Semantics |
|---|---|---|
| `run_id` | string | Stable identifier for one cross-bead review run. Use this for idempotency and rerun filtering. |
| `cohort` | object | Selector metadata for the reviewed cohort. Contains `type`, selector `value` when applicable, and `member_count`. |
| `reviewed_at` | string | UTC timestamp for when this bead was reviewed, formatted as an ISO 8601 timestamp. |
| `reviewer_run_sha` | string | SHA or content identifier for the reviewer run that produced this stamp. |
| `verdict` | string enum | Review verdict for the run, such as `clean`, `findings`, `dispute`, or `partial`. |
| `findings_touching_this_bead` | integer | Number of findings in the run that cite this bead. |
| `report_ref` | string | Relative reference to the human-readable review report for this run. |
| `categories_flagged` | string array | `finding.category` values flagged by findings that touch this bead. |

### Deferred Verification Ledger Extension

`metadata.deferred_verification[]` is the canonical source-bead record for
integration, UAT, or manual acceptance checks that could not run before bead
close. `stream-verification-ledger` reads these entries and creates a per-label
ledger bead; the ledger is an index, not the source of truth.

```yaml
metadata:
  deferred_verification:
    - entry_id: "<stable hash, optional on input>"
      ak: "AK-4"
      kind: "integration|uat|manual"
      reason: "requires the live customer system"
      command: "INTEGRATION_TESTS=true ..."
      manual_flow: ""
      preconditions:
        - "VPN up"
      evidence_required: "passing command output and date"
      status: "pending|passed|waived|superseded|removed"
```

If `entry_id` is absent, consumers compute it as:

```text
sha256(source_bead_id + "\n" + normalized_ak + "\n" + normalized_kind + "\n" + normalized_command_or_manual_flow)
```

Normalization trims outer whitespace and collapses internal whitespace to one
space. `command` is used when non-empty; otherwise `manual_flow` is used. If
both are non-empty, the entry is invalid. If `entry_id` is supplied, it must
match the recomputed hash; consumers reject mismatches instead of trusting input.
Status defaults to `pending`.

`metadata.verification_ledgers[]` records which ledger bead has indexed the
source entries for a cohort:

```yaml
metadata:
  verification_ledgers:
    - ledger_bead: "<tracker bead id>"
      cohort:
        type: "label"
        value: "stream:live-cutover"
      entry_ids:
        - "<stable entry id>"
      ledgered_at: "<ISO timestamp>"
      run_id: "<ledger run id>"
```

The stamp is idempotent. Reruns merge missing `entry_ids` into an existing stamp
for the same `ledger_bead` and cohort instead of appending duplicates.

Filter by `run_id`:

```bash
bd list --json | jq '.[] | select((.metadata.stream_reviews // [])[]? | .run_id == "2026-05-21-a1b2c3") | .id'
```

Filter by `verdict`:

```bash
bd list --json | jq '.[] | select((.metadata.stream_reviews // [])[]? | .verdict == "findings") | .id'
```

## Cohort Selector Grammar

```typescript
type CohortSelector =
  | { type: "label"; value: string }
  | { type: "wave_id"; value: string }
  | { type: "parent"; value: string }
  | { type: "time-range"; start: string; end: string }
  | { type: "ids"; value: string[] }
  // ids: explicit bead-ID list (added clc-zi1u).
  // Each id is checked via bd show; missing or non-closed ids are skipped
  // with a pre-flight warning — the run never hard-fails on partial input.
  //
  // Primary use case: reviewing a session-close output from another session.
  //   bead-cohort.sh ids:clc-a,clc-b,clc-c
  //   clw stream-review --cohort ids:clc-a,clc-b,clc-c
  //
  // JSON sidecar normalization: { "type": "list", "value": "clc-a,clc-b,clc-c" }
```

`stream-verification-ledger` v1 intentionally supports only the `label` selector.
The narrower helper scope is additive to the shared grammar; it does not redefine
the grammar.

## Stream Verification Ledger Preflight

Before `stream-reviewer` or `/stream-review` reviews a label cohort, run the
stream verification ledger preflight for the same label. The preflight:

- scans source beads with `bd list --label <label> --json`;
- reads canonical deferred checks from `metadata.deferred_verification[]`;
- creates or refreshes one active `[VERIFICATION]` tracker bead for that label,
  or creates a successor when a previous tracker was manually closed while
  active source entries remain;
- stamps each source bead in `metadata.verification_ledgers[]`; and
- leaves source beads canonical for pass, waiver, supersede, and removal status.

This preflight prevents deferred integration and human acceptance checks from
being hidden in close notes while preserving stream review's separate
responsibility for cross-bead defects.

## Library Default vs Project Overlay

| Section | Library default | Project overlay |
|---|---|---|
| **Categories** | 14 universal categories above | Projects MAY add categories but MAY NOT remove library categories |
| **Checks** | Universal checks per category | Projects add project-specific checks under universal categories |
| **Severity defaults** | No per-check severity mapping; library checks are unranked | Per-check severity defaults (e.g. BLOCKING / ADVISORY / OBSERVATION) MAY be defined in project overlays |
| **Disposition** | 5-outcome triage taxonomy (above) | Projects MAY add disposition values; MAY NOT remove library values |
| **Metadata schema** | `metadata.stream_reviews[]`, `metadata.deferred_verification[]`, and `metadata.verification_ledgers[]` shapes | Projects MAY add per-finding fields under `finding.project_extensions` |

Extension rules:

- Projects MAY add categories, checks, and disposition values.
- Projects MUST NOT remove library categories, library checks, or library disposition values.
- Projects MAY add fields only under `finding.project_extensions`.
- Project overlays define only project-specific additions; they do not copy the library default.

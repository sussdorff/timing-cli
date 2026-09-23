---
name: seed-data-parity
description: When work needs live data, ships an integration test, or touches an adapter/backend seed, the demo/seed data must be reconciled in lockstep through the overlay-defined source/update mechanism. Member of the workflow bundle; pairs with cross-bead-review.md.
---

# Seed / Demo Data Parity Standard - Library Default + Overlay Format

<!-- Decision: a workflow-bundle-member standard (flat, alongside
  cross-bead-review.md) rather than a standalone folder-form installable.
  Reason: it is consumed as part of the workflow bundle by the same agents and
  the same `_triggers.yml`, and pairs tightly with cross-bead-review.md's
  `seed-data-drift` category. The first mechanical gate is the checker
  scripts/refinement/check-seed-data-parity.py (a triage gate, not a semantic
  verifier); this file is the human-readable rule, the seed-source taxonomy, and
  the overlay contract. -->

> **Shared contract:** This file defines the project-agnostic rule, the
> seed-source taxonomy, and the three Trigger Indicators. The first mechanical
> gate is `scripts/refinement/check-seed-data-parity.py` — a **triage gate, not a
> semantic verifier** — which both `bead-orchestrator` (per-bead) and
> `stream-reviewer` (`seed-data-drift` category) call. Concrete project paths,
> commands, and skip-guards live in the machine-readable project overlay, NOT
> here. Do not claim the checker "deterministically enforces" the rule; it
> triages, and a human/agent dispositions the finding.

## What This Is

Demo installations exist so that automated integration tests can run against a
seeded backend instead of the live system. When work changes what the system
produces or consumes, the demo/seed data must move in lockstep — otherwise the
demo installation drifts from reality and its integration tests silently rot
(or never run without the live system).

This standard makes "is the seed data reconciled?" a **checkable** gate, scoped
to the work that actually needs it, rather than a per-bead ritual or a rule
interpreted from prompt prose.

## The Rule

If a unit of work requires live/production data, ships or modifies an
integration test, or changes an adapter or a seeded backend, then the seed
surface MUST be reconciled in the same unit of work, through the
**overlay-defined source/update mechanism**, so that the demo installation and
its integration tests remain runnable without the live system.

"Reconcile" is deliberately broader than "regenerate" — how the seed surface is
updated depends on its seed-source type (below).

## Seed-Source Taxonomy

A project's seed surface is one or more of these types. The overlay names which
applies to each surface and how it is reconciled:

| Type | Meaning | Reconciliation |
|---|---|---|
| `generated` | Produced from a structured source-of-truth by a command | Re-run the documented generator (e.g. a `generate-data` script) |
| `vendored-export` | Committed export of data captured from a real/representative instance | Re-export and commit the updated artifact via the owning pipeline |
| `upstream-consumed` | Owned by a sibling repo; this repo only consumes it | File a bead in the upstream repo; do not fork the data locally |
| `live-prohibited` | The live system is explicitly NOT an allowed source | Data must be seeded; depending on the live system is the defect |

`live-prohibited` is a property every demo installation has: "I ran it against
the live system" is never acceptable evidence — it is the defect this standard
exists to catch.

## Trigger Indicators

Any one of these is sufficient to make the rule apply. The overlay maps each to
concrete keywords and path globs that the checker consumes.

1. **Live-system dependency.** The bead text asks for the live/production system
   (e.g. "I need the live customer system", "needs the live system", "run against the real PVS"). A
   live-data dependency is, by definition, a missing-seed signal.
2. **Integration test present.** The bead adds or changes a test that exercises
   a seeded backend or a real adapter. An integration test cannot be simulated
   without staging/demo data.
3. **Adapter or backend-seed touch.** The bead touches an adapter or the backend
   seed. Producer/consumer changes must be reflected in the seed.

## The Checker — a Triage Gate, Not a Verifier

`scripts/refinement/check-seed-data-parity.py` is the first mechanical gate for
this rule — better than prompt prose, but explicitly a triage/checklist gate. It
does keyword + path-glob matching: it reads the bead text, the changed-path set,
and the project overlay config, and returns JSON:

**What it does NOT prove** (a clean result is triage-passed, not verified):

- that the seed data was *correctly* updated for the affected scenario,
- that the generator actually ran,
- that a touched seed file matches the scenario the bead changed.

Two additional gaps can be narrowed by opt-in inputs:

- **`--upstream-repo-path <dir>`** — probes the referenced upstream bead via `bd show`
  and reports its state as `exists | open | closed | unknown`. Degrades to `unknown`
  when the path is unreachable or `bd` is absent; does not block the gate.
- **`--runner-report <file>`** — reads a test-runner JSON report and flags
  registered-but-skipped integration tests as a distinct `skipped-integration-tests`
  finding. Without this input the checker cannot see whether tests ran or skipped.

A human or agent dispositions the finding; the gate only routes attention.

```bash
git diff --name-only <base>...HEAD > /tmp/changed.txt
bd show <id> --json > /tmp/bead.json
python3 scripts/refinement/check-seed-data-parity.py \
    --bead /tmp/bead.json --changed-paths /tmp/changed.txt --root "$REPO_ROOT" \
    [--upstream-repo-path /path/to/upstream] \
    [--runner-report /tmp/runner.json]
```

Output `data` carries `applicable`, `required`, `indicators{...}`,
`seed_surface_touched`, `missing`, `forbidden_local_touched`,
`followup_allowed`, `upstream_followup_referenced`, `seed_source_type`,
`update_command`, `upstream_repo`, and `evidence`. When
`--upstream-repo-path` is given, `data.evidence.upstream_bead_existence[]`
contains `{id, status}` entries where `status` is
`exists | open | closed | unknown`.

Exit codes: `0` not-applicable or triage-passed; `1` a finding (`missing-seed`,
`forbidden-local-surface`, and/or `skipped-integration-tests`); `2` input/config
error.

A project ships its config as a machine-readable overlay at
`$REPO_ROOT/.agents/standards/seed-data-parity.yml`:

```yaml
seed_source_type: generated            # or vendored-export | upstream-consumed | mixed
update_command: "<how the seed surface is reconciled>"
upstream_repo: <sibling repo>          # set when seed is upstream-consumed
live_indicators: ["live customer system", "live system", ...]      # indicator 1
integration_test_globs: ["**/*.integ.test.ts", ...]   # indicator 2
seed_surface_globs: ["packages/install-pvs/data/**", ...]  # must be touched to satisfy
adapter_globs: ["packages/pvs-*/**", ...]              # indicator 3
forbidden_local_surfaces: ["data/live-anon/**", ...]    # must NOT be seeded locally
```

`forbidden_local_surfaces` encodes upstream-owned data this project must not seed
locally (e.g. mira must not seed FHIR/Aidbox data owned by polaris). Touching one
raises a separate `forbidden-local-surface` finding regardless of indicators, and
never counts as satisfying parity. `upstream_followup_referenced` is a light
signal — it only records that a `<upstream_repo>-<id>` reference is present in the
bead text; it does not verify that bead exists or is open.

If a project ships no config, the check is **not-applicable** (exit 0) — safe to
call from any project. Projects without demo installations need no overlay.

## `followup_allowed`: resolving a missing-seed finding

A `missing` finding is resolved by **one** of, with evidence:

- reconciling the seed surface now (via the overlay's `update_command`), or
- filing a follow-up bead that explicitly owns the seed-data update (for
  `upstream-consumed` surfaces, in the upstream repo), with a stated reason it
  could not happen here.

The checker reports `followup_allowed: true`; the orchestrator/human chooses.

## How to Apply: bead-orchestrator (per-bead gate)

Indicator-gated, so it is not a per-bead ritual. When the checker returns
`required: true` and `missing: true`, treat seed reconciliation as part of the
bead's definition of done; resolve per `followup_allowed`. Never satisfy a
live-data request by reaching for the live system.

> **Injection note (accurate mechanism):** `inject-standards` (bead-orchestrator
> Phase 1) scores `--context` keywords against standard **filename stems**; it
> does not read `_triggers.yml`. The `_triggers.yml` entry for this standard
> serves the SessionStart standards-loader hook, a separate mechanism. The
> reliable gate here is the **checker** (run explicitly), not keyword-based
> auto-injection. Do not claim "the customer stack auto-injects the standard."

## How to Apply: stream-reviewer (`seed-data-drift` category)

`seed-data-drift` is a library-default cross-bead-review category (see
`standards/workflow/cross-bead-review.md`). Run the checker per cohort bead and
flag any bead where `missing: true`. Project-specific stream-review checks live
in the project's `cross-bead-review.md` overlay (the file the reviewer loads),
not in `seed-data-parity.md`.

## Companion rule: skipped integration tests are not evidence

An integration test counts as MoC evidence only if it **actually ran**.
Conditionally-registered tests (`test.if(BACKEND_OK)(...)`, `@pytest.mark.skipif`,
etc.) pass green when they skip — "green because skipped" is not evidence that
the seed/demo data exists or that the behaviour works. This is enforced as a
`test-quality` check in cross-bead-review (and at verification time, where the
runner's skip report is observable). It is a distinct gate from seed-data-drift:
seed-drift catches "no seed was added"; this catches "the test never ran".

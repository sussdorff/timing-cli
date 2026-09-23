# Bead Spec Standard: Description-First Bead Specs

## Canonical Spec Surface

The bead description is the canonical spec surface consumed by implementers,
reviewers, and verifiers. The `## Intent` block defined in
`standards/beads/intent-section.md` is the load-bearing structure for behavioral
goal, scope-in, and scope-out.

Producer-authored `metadata.intent`, `metadata.contracts`, `metadata.constraints`,
and `metadata.effort` are legacy fields. New workflows should not rely on them.

## Acceptance-Criteria Coverage

AKs are the contract the orchestrator and verification agents check against. They must cover **every defect named in the bead's "Why" / motivation section**, or the bead must explicitly mark the un-covered defects as out of scope.

| Failure mode | Symptom | Fix |
|---|---|---|
| AKs scope-narrowed below the Why | "Why" lists a defect across multiple commands; only one AK fires for one command; verification passes; the other commands remain broken | Add one AK per command in the defect set, OR add an explicit "Out of scope: defect-X for commands Y, Z (separate follow-up bead)" line |
| AKs assume single-fixture conditions | "Status and sync agree" AK passes only because the test fixture sets matching flags on both; defaults still diverge in production | Add at least one assertion that invokes both commands with **no arguments** so defaults are exercised |
| Implicit AK ("the spirit of the bead") | Implementer ships the literal AKs; reviewer waves the bead through; user finds the Why-section defect unfixed | Convert every Why-section bullet into an explicit AK or out-of-scope line before claiming the bead is factory-ready |

**Rule:** at bead-creation time, run a one-line audit — for each numbered defect in the Why section, identify the AK that covers it. If you cannot point at one, either write it or write the out-of-scope line.

## metadata.review Schema

The optional `metadata.review` key may be written after an explicitly requested manual
Bead review returns a typed result and the exact live bindings are rechecked. Intake,
creation, updates, implementation, and Session Close neither require this key nor invoke
a reviewer when it is absent or stale. Workplan may use it as advisory triage evidence.

```yaml
metadata.review:
  schema_version: 2
  reviewed_at: <ISO 8601 UTC>
  profile: <formal|semantic|repository|related-beads|full>
  outcome: <clean|warnings|blocked>
  content_sha: <sha256 hex>
  reviewer_sha: <sha256 hex>
  contract_sha: <sha256 hex>
  finding_ids: [<deterministic occurrence IDs, lexical order>]
  finding_rule_ids: [<stable aggregation rule IDs, lexical order>]
```

Every non-unavailable finding has a `rule_id` and `finding_id`. The rule ID is an
uppercase-kebab aggregation key from either the resolved baseline/project contract
or the reviewer-owned cross-cutting registry. The finding ID has the form
`<RULE-ID>:<bead-id>:<12-hex>` and hashes the rule ID, bead ID, criterion, and
sorted unique evidence anchors. Identical inputs define one merged occurrence;
distinct occurrences require occurrence-specific evidence. Message and
recommendation wording do not affect identity. Consumers aggregate by
`finding_rule_ids` and use `finding_ids` only for occurrence traceability.

`unavailable` is a transport or repository-binding failure, not a reusable review,
and must never be written. A `blocked` result records the manual review outcome but does
not create an automatic dispatch gate. Live dependency state is never cached here.

**Content hash inputs (content_sha):**

The content digest hashes one canonical JSON object containing:

1. `title`
2. `description`
3. `acceptance_criteria`
4. `issue_type`, with legacy `type` as fallback
5. parent bead ID
6. labels from contract-declared families, sorted
7. all outgoing dependency/relationship pairs, sorted by type and target ID

Incoming dependents and children are excluded. Parent, declared-family labels,
and every outgoing relationship are authored classification or portfolio context
and therefore invalidate the bead-level review when changed. Undeclared labels
are operational or unclassified context and do not invalidate the review.

Explicitly excluded from the hash: `status`, `priority`, `claim`, `metadata.review` itself,
`closed_at`, `updated_at`, `metadata.routing.*`, `metadata.intent`,
`metadata.contracts`, `metadata.constraints`, `metadata.effort`. Changing only these
fields does NOT invalidate a cached review.

**reviewer_sha computation:**

SHA256 over the live reviewer skill, review-contract implementation files,
finding-rule registry, and deterministic finding-identity helper.
The result is portable across install locations when those files are byte-identical.

**contract_sha computation:**

SHA256 over the normalized, fully resolved semantic contract. The payload contains
merged baseline-plus-project rules and merged label families exactly once. File paths,
source digests, provenance diagnostics, timestamps, and ordering differences are
excluded. Rule or label-family semantics change the digest.

**Manual review record validity:**

A cached review is current when all of the following hold:

1. `metadata.review` exists
2. `schema_version == 2`
3. `outcome` is `clean`, `warnings`, or `blocked`
4. stored and current `content_sha` match
5. stored and current `reviewer_sha` match
6. stored and current `contract_sha` match

The record is advisory evidence only. A failed binding condition makes it stale but
never invokes a new review. Another review requires an explicit user request.

Any stamp without `schema_version: 2`, including old `FACTORY_READY` and
`NEEDS_INTERACTIVE_WORK*` vocabularies, is `never-reviewed` under this contract.
Legacy stamps likewise have no effect on dispatch.

**Write-time binding rule:**

The writer accepts the exact typed reviewer result rather than a caller-supplied
verdict. It loads the live bead and recomputes all three bindings, validates the
typed result, builds the stamp, then repeats the live read and validation immediately
before `bd update`. Any mismatch causes no write. This is a TOCTOU guard, not a
database transaction.

**Implementation:** `skills/bead-reviewer/scripts/compute_bead_content_sha.py` — ships
inside the `bead-reviewer` skill so it travels with the skill via
`/library use bead-reviewer` to any consumer (cognovis-core, polaris, mira, etc.).
Callers resolve the helper with the standard fallback chain (worktree →
`~/.agents/skills/bead-reviewer/scripts/` → `~/.claude/skills/bead-reviewer/scripts/`).
`skills/bead-reviewer/scripts/review_freshness.py` exposes the same three-way
freshness classification for workplan.

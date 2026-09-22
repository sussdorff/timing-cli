## Phase 2: Inline Extraction and Bead Creation

For every auto-approved or explicitly approved candidate, draft the bead inline
and create it with
`ccore tracker create --body-file` when the repository registry entry
declares a tracker. Use direct `bd create --body-file` only for the Beads
archive (no `tracker` in the registry). Do not spawn an agent. For each candidate:

1. **Normalize** the approved candidate into a complete factory-ready body,
   following `standards/workflow/bead-hygiene.md`:
   - outcome-oriented `title`
   - explicit bead `type`
   - `classification_evidence` naming the observable semantic signals for that type;
     never use size or estimated implementation effort as type evidence
   - `context` for background that does not belong in the intent block
   - `intent_goal`
   - `scope_in`
   - `scope_out`
   - `acceptance_criteria` as observable outcomes
   - `means_of_compliance`, exactly one row per acceptance criterion with `moc` and
     concrete `evidence` (a file path, test name, query, or screenshot location —
     never a placeholder)
   - exactly one `Review-Risk:` line — `none`, `payment`, `pii`, `auth`, or
     `compliance` — for every feature, epic, task, and bug bead. This is the single
     durable classification Repository Delivery reads to resolve its landing policy;
     `bead-author-check.py` rejects a missing, unknown, or repeated declaration.
     Classify from the source: payment processing, personal data, authentication or
     access control, and regulatory obligations are never `none`.
   - `additional_sections` for project-overlay Pflichtfelder when the source supplies them
   - `additional_sections["Human Decision Gate"]` when the approved candidate requires
     a human decision before proceeding. Follow `standards/judge-layer/decision-gate.md`:
     include decision owner, allowed outcomes from `ALLOW` / `BLOCK` / `REVISE` /
     `ESCALATE`, trigger timing, minimum evidence plan, operational do-nothing/default
     outcome, delivery consequence, overrideability, and sequencing constraints.
     Keep this gate out of ordinary Acceptance Criteria.
   - **Verify every cited identifier** before writing it (anti-pattern `REF-FABRICATED`).
     Catalog/fact keys, schema fields, CodeSystem/ValueSet codes, file paths, and test
     names that appear in the body, Acceptance Criteria, or MoC Evidence must be grepped
     against their actual source first (e.g. `rg "<key>" <catalog-path>`). If a key
     cannot be verified, omit it or mark it `TO-VERIFY: <key>` — never write a guessed
     key as fact. When the source references a known catalog, grep it up front and
     constrain the draft to keys that exist.
2. **Validate** the body with `bead-author-check.py` before mutation.
3. If validation fails, revise the body and re-run the check.
4. **Create** with `ccore tracker create --repo <prefix> --body-file <file>`
   (declared tracker) or `bd create --title <title> --type <type> --priority <priority> --body-file <file>`
   (Beads archive) and record the returned ID.
5. **Stop after persistence and deterministic validation.** Do not dispatch
   `bead-spec-reviewer`, `bead-reviewer`, Council, or an author/reviewer loop. If the
   user explicitly requested a review, run that separate manual action after creation.

Carry the source text, approved candidate boundary, Phase 0.5 duplicates, HITL
merge/split decisions, and any infrastructure-sensitive source hints (CI / pipeline /
harness / permissions / git / bd / Dolt / orchestrator / session-close signals) into
the normalization so they shape `context`, scope, and labels.


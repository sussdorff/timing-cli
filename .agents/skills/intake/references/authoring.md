## Phase 2: Inline Extraction and Issue Creation

For every auto-approved or explicitly approved candidate, draft the issue body inline
and create it with `ccore tracker create --body-file` in the repository whose registry
entry declares `github` or `forgejo`. Do not spawn an agent. For each candidate:

1. **Normalize** the approved candidate into a complete factory-ready body, following
   the resolved `workflow/issue-intake` standard (`standards/workflow/issue-intake.md`)
   plus the project overlay `.agents/standards/issue-intake.md` when it exists. `ccore`
   reads the body as follows:
   - a column-0 `Goal:` line inside `## Intent`, exactly once; it becomes the issue
     title. An optional H1 heading must repeat the Goal verbatim.
   - exactly one column-0 `Type: feature|task|bug` line; it becomes the `type:` label.
   - `classification_evidence` naming the observable semantic signals for that type;
     never use size or estimated implementation effort as type evidence
   - `context` for background that does not belong in the intent block
   - `scope_in` and `scope_out` (`Scope-In:` / `Scope-Out:` in the Intent block)
   - `acceptance_criteria` as observable outcomes under `## Acceptance Criteria`
   - `means_of_compliance`, exactly one row per acceptance criterion under
     `## Means of Compliance` with `moc` and concrete `evidence` (a file path, test
     name, query, or screenshot location - never a placeholder)
   - exactly one column-0 `Review-Risk:` line, not bulleted, bold or indented - `none`,
     `payment`, `pii`, `auth`, or `compliance` - for every feature, task, and bug issue.
     It becomes the
     `review-risk:` issue label and is the work order's review risk, which pr-agent
     applies as the floor of the pull request's `review-risk:*` label;
     `issue-author-check.py` rejects a missing,
     unknown, or repeated declaration, and one whose `review-risk:` label from ccore would
     differ from the declared value. Classify from the source: work that moves a
     payment, personal-data, authentication/access-control or regulatory boundary with
     a concrete damage scenario is never `none`; touching such an area without moving a
     boundary is `none`. `pii` needs a crossing that the repository's PII boundary
     standard defines. The `executive-pack` standard's Review risk section holds these
     rules.
   - one column-0 `Blocked by: <full issue URL>` line per live dependency; a bare
     number or `owner/repo#N` is not a valid dependency record. The lines are the body's
     dependency record; on Forgejo, `ccore tracker create` (2026.9.18 or later) also wires
     them as native dependencies.
   - ccore also reads column-0 field lines inside fenced code blocks. Indent `Goal:`,
     `Type:`, `Review-Risk:` and `Blocked by:` lines in fenced examples; the checker
     rejects a fenced column-0 field line.
   - additional sections for project-overlay Pflichtfelder when the source supplies them.
     An overlay rule annotated `<!-- requires-section: Heading | Alias -->` is enforced
     by `issue-author-check.py`: the body needs a non-empty `## Heading` (or alias)
     section for every issue type the rule's `types:` filter covers.
   - one `## Human Decision Gate` section only when the work changes a production
     system or sends a customer a message with content (shared `AGENTS.md`, Scope and
     authorization); internal work, including CI secrets and internal hosts, takes no
     gate. Follow `standards/judge-layer/decision-gate.md`: include decision owner,
     approval class (`production-change` or `customer-message`), allowed outcomes from `ALLOW` / `BLOCK` / `REVISE` /
     `ESCALATE`, trigger timing, minimum evidence plan, operational do-nothing/default
     outcome, delivery consequence, overrideability, and sequencing constraints.
     Keep this gate out of ordinary Acceptance Criteria.
   - **Verify every cited identifier** before writing it (anti-pattern `REF-FABRICATED`).
     Catalog/fact keys, schema fields, CodeSystem/ValueSet codes, file paths, and test
     names that appear in the body, Acceptance Criteria, or MoC Evidence must be grepped
     against their actual source first (e.g. `rg "<key>" <catalog-path>`). If a key
     cannot be verified, omit it or mark it `TO-VERIFY: <key>` - never write a guessed
     key as fact. When the source references a known catalog, grep it up front and
     constrain the draft to keys that exist.
2. **Validate** the body before mutation:
   `uv run python "$INTAKE_ROOT/scripts/issue-author-check.py" --body-file <file> --repo-root <repo>`.
   Exit 0 (`FACTORY_READY` or `FACTORY_READY_WITH_WARNINGS`) permits persistence; exit 2
   blocks it.
3. If validation fails, revise the body and re-run the check.
4. **Create** with `ccore tracker create --repo <registry-key> --body-file <file>` and
   record the returned issue reference. `<registry-key>` is `owner/repo` or a registry
   alias (see SKILL.md); the title is the body's `Goal:` line, with no `--title`. A
   substantive change to an existing issue runs the same check, then
   `ccore tracker update --ref <owner/repo#N> --body-file <file>`; an existing issue can
   be re-checked with `issue-author-check.py --issue <owner/repo#N>`.
5. **Stop after persistence and deterministic validation.** Do not dispatch
   a spec reviewer, Council, or an author/reviewer loop. If the
   user explicitly requested a review, run that separate manual action after creation.

Carry the source text, approved candidate boundary, Phase 0.5 duplicates, HITL
merge/split decisions, and any infrastructure-sensitive source hints (CI / pipeline /
harness / permissions / git / tracker / orchestrator / delivery signals) into
the normalization so they shape `context`, scope, and labels.

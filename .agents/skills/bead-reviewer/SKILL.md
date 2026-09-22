---
description: Explicitly requested manual review of one live bead by ID against specification and target-repository reality; never runs during create or update
argument-hint: <bead-id> [formal|semantic|repository|related-beads|full]
tags: workflow
requires:
  - standard:review-governance
requires_standards: [dispatch/model-routing, review-governance]
---

# Bead Reviewer

The skill owns the review quality-signals runner at
`scripts/review_quality_signals_runner.py`.

Run only after an explicit user request to review a Bead. Intake, Bead creation,
substantive updates, implementation, and Session Close must never invoke this skill
automatically. The review is advisory evidence for the requesting human; it does not
write readiness metadata or start a repair/re-review loop.

Review one authoritative live artifact. The input is a Bead ID plus an optional
profile; `full` is the default. Profiles select criteria only and never widen the
review beyond evidence needed to judge the specification.

## Direct dispatch review

> STATUS: BEHAVIORAL PROMPT ASSEMBLY. `ccore agent` is the transport and cannot
> prove that a caller copied every semantic input. Source tests keep the agent
> schema and skill route complete; digest computation and post-dispatch validation
> are the deterministic gates. A caller that cannot assemble the complete prompt
> must stop instead of dispatching a partial request.

1. Resolve the target repository and load the authoritative Bead with
   `bd show <bead-id> --json`. Stop with `unavailable` if the Bead or repository
   binding cannot be read.
2. Select a reviewer from a different model family than the lead, using the active
   model-routing standard. Resolve the exact installed `bead-spec-reviewer` projection
   for that target harness; this is both the prompt source and reviewer identity. For
   a Claude Markdown projection use its complete instruction body; for a Codex TOML
   projection use the complete `developer_instructions` value.
3. Run `scripts/compute_bead_content_sha.py --bead-id <bead-id> --repo-root
   <target-repo> --reviewer-agent-path <exact-agent-projection>` and
   `scripts/contract_loader.py --repo-root <target-repo>`.
   The first result supplies `content_sha`, `reviewer_sha`, and `contract_sha`; the
   second supplies the fully resolved review rules and label families.
   Preserve both JSON results unmodified in unique temporary files for final validation.
   Stop before dispatch if the contract is not `ok` or any digest is missing,
   `unknown`, or not a SHA-256 value.
4. Create one unique prompt file containing, in this order:
   - the complete instructions from the exact agent projection resolved in step 2;
   - a `## Review Request` section with the exact Bead ID, absolute target repository,
     selected profile, live Bead JSON, binding JSON, and resolved contract JSON;
   - an explicit instruction to echo the three supplied digests unchanged and to
     return only the agent's JSON result.
   Do not summarize or omit any of those inputs. The prompt file is the complete
   semantic contract; `ccore agent` adds nothing to it.
5. Confirm `.beads/reviews/` is Git-ignored in the target repository and create the
   directory when absent. Then invoke the installed dispatcher directly with the route
   selected in step 2:

```text
ccore agent run \
  --model <canonical-alias> \
  --harness <claude|codex> \
  --reasoning <adapter-supported-reasoning-level> \
  --session <stable-review-session> \
  --cwd <target-repo> \
  --caller bead-reviewer \
  --prompt-file <complete-prompt-file> \
  --permissions approve-reads \
  --events-file <target-repo>/.beads/reviews/<unique-run>.events.ndjson \
  --answer-file <target-repo>/.beads/reviews/<unique-run>.verdict.json
```

   Do not pass write-capable permissions in a main checkout: the reviewer needs
   read-only `bd`, Git, search, and test inspection. Never invoke operational `acpx`
   and never ask another model to relay the dispatch.
6. Validate the extracted answer before returning it:

```text
uv run python <bead-reviewer-skill-root>/scripts/review_contract.py validate \
  --result-file <verdict-file> \
  --bindings-file <bindings-json-file> \
  --contract-file <resolved-contract-json-file> \
  --bead-id <bead-id> \
  --profile <profile>
```

   A non-JSON or contract-invalid answer is a failed review, never a clean review.
   Return only this validated typed result to the requesting user.
   Do not retry an unchanged prompt after a schema failure; correct the local prompt
   contract first or report the harness blocker.
   Preserve every requested criterion in the result as `ran`, `skipped`, or
   `unavailable`, with a reason for every non-ran criterion.

The reviewer is read-only. Never edit files, run `bd update`, write review metadata,
repair the Bead, or start another agent. Warning findings are recorded as advisory
evidence and may proceed without repair. The original author adjudicates blocking findings before applying any accepted change.
A new review requires another explicit request. `unavailable` is never persisted as a
reusable review stamp.

Implementation-diff review belongs to `review-agent`.

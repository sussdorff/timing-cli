---
name: cognovis-pr
description: Write the pull request title and body for a Cognovis delivery from the installed pr skill's template plus the local review, verification and residual sections; `ccore pr ensure` publishes it.
compatibility: {}
metadata: {}
---

# Cognovis Pull Requests

Write one outcome-led pull request text that a reviewer can judge in a minute.
This skill produces text only. `ccore pr ensure` publishes it; the `executive-pack`
delivery owns the merge decision. The Forgejo
review channel is operated by `forgejo-review-channel`, not here.

## Inputs

- Repository root, the delivered change, the work order or spec it answers.
- Verified evidence: commands run with verdicts, screenshots for a user-visible
  surface, and known residuals.
- From the delivery: the `finding_triage.py --review-decisions` output, the
  non-author verifier's verdict with the head SHA it verified, the model route
  each reviewer used, the product decision and economic damage assessments, and the
  Risk statement content when the review risk is not `none`.

## Outputs

- One Markdown file outside the worktree. Line one is the title, at most 120
  characters; the sections follow in the order defined by
  `references/authoring.md`.

## Workflow

1. Read the installed `pr` skill, project-local before global, and use its live
   template for the body. `references/authoring.md` resolves it and holds only
   what Cognovis adds. `pr` is installed globally on each host by `harness bootstrap`; the Library does not ship
   it, and a missing one is a setup failure to report.
2. Write the body from that template, then add the Cognovis sections defined in
   `references/authoring.md`: the work-order reference, Review decisions,
   Verification, reviewer routes, Merge assessment, Risk statement and Known residuals.
   That reference is the only place this list is held; a caller supplies the content,
   not a second list.
3. Attach walkthrough evidence only when a user-visible surface changed, after the
   pull request exists, per the reference.
4. Pass the file to `ccore pr ensure` as its `--summary` value. Do not add the
   identity footer; ccore appends harness, session and work-order identity.

## Do NOT

- Print or commit secret values, prompts, customer data, or pilot identifiers.
- Commit screenshots or other binary evidence into the repository.
- Publish or merge from here, or create a second creation transport beside
  `ccore pr ensure`.

## Resources

| File | Purpose |
|---|---|
| `references/authoring.md` | Resolving the installed `pr` skill, the title rule, the Cognovis sections, screenshot handling, ccore handoff. |

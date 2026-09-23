---
name: cognovis-pr
description: Write the pull request title and body for a Cognovis delivery from the pr template plus evidence and residual sections; ccore owns publication and merge.
compatibility: {}
metadata: {}
---

# Cognovis Pull Requests

Write one outcome-led pull request text that a reviewer can judge in a minute.
This skill produces text only. `ccore pr ensure` publishes it and Ccore Session
Close owns delivery choice, integration, merge, push, and cleanup. The Forgejo
review channel is operated by `forgejo-review-channel`, not here.

## Inputs

- Repository root, the delivered change, the work order or spec it answers.
- Verified evidence: commands run with verdicts, screenshots for a user-visible
  surface, and known residuals.

## Outputs

- One Markdown file outside the worktree. Line one is the title, at most 120
  characters; the sections follow in the order defined by
  `references/authoring.md`.

## Workflow

1. Read `references/authoring.md`. When the `pr` skill from the Matt Pocock
   catalog is installed, its template is the same one; this reference adds the
   Cognovis sections and the handoff.
2. Write Summary, Evidence, Merge Danger and Known residuals. Pick the smallest
   Summary view that makes the change legible; do not narrate files.
3. For a user-visible surface, capture two to four walkthrough screenshots and
   attach them after the pull request exists, per the reference.
4. Run the unslop checklist in the reference over the text.
5. Hand the file to Session Close as its `--summary` value. Do not add the
   identity footer; ccore appends harness, session and work-order identity.

## Do NOT

- Print or commit secret values, prompts, customer data, or pilot identifiers.
- Commit screenshots or other binary evidence into the repository.
- Publish or merge from here, or create a second creation transport beside
  `ccore pr ensure`.

## Resources

| File | Purpose |
|---|---|
| `references/authoring.md` | Title, body sections, screenshots, diagram rule, unslop checklist, ccore handoff. |

---
name: session-retro
description: Run a retro on a finished delivery session and encode each learning as structure first (lint, test, check, script), prose only when no structure can hold it; store the result in Open Brain and the standards.
requires:
  - skill:ob-cli
compatibility: {}
metadata: {}
---

# Session Retro

Run at the end of an executive-pack delivery, after the merge or after the pull request
was handed to a human. This skill exists because the Pocock `retro` skill sets
`disable-model-invocation: true` and cannot run on its own at the end of a delivery.

## 1. Retro

Read the installed Pocock `retro` skill (`~/.agents/skills/retro/SKILL.md` or
`~/.claude/skills/retro/SKILL.md`) and apply its method to the finished session. When it
is not installed, review the session for: what cost time or tokens without value, what
failed and why, which review or pr-agent findings were real, which were dismissed and
why, and what the next delivery in this repository should do differently. Keep only
learnings a later session would act on.

## 2. Encode each learning, structure first

For each learning, in this order:

1. **Structure in the delivered repository.** A lint rule, a test, a check or a script
   that makes the mistake impossible or loud. Commit it on a branch in the delivered
   repository and open a pull request with `pr`; do not merge it here.
2. **Prose, only when no structure can hold it.**
   - Project learnings go into the delivered repository's `.agents/standards/`.
   - Review-relevant learnings go into `.agents/standards/review.md` there. A pr-agent
     finding that was dismissed with a reason is recorded as a dismiss pattern: what the
     finding looks like, the condition under which it is skipped, and the risk boundary
     beyond which it must not be skipped.
   - Cross-project learnings are opened as a pull request against `standards/` in
     cognovis/library-core.

## 3. Open Brain

Save the retro with `ob save --project <repo> --type session_summary --title "<retro
title>" --source-ref <harness>:<session-id> "<text>"`. The text lists each learning with
where it was encoded (file, pull request link) or why it stayed prose. Report the Open
Brain memory id.

## Boundaries

This skill performs no merge, no push of the delivery branch, no issue closure and no
worktree cleanup. Its own changes land only through the pull requests it opens.

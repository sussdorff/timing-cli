# Pull request authoring contract

Everything about the body's shape — the template, the section order, which visual to
pick for Summary, how to word Merge Danger — belongs to the installed `pr` skill. This
file holds only what Cognovis adds on top of it.

## Resolve the installed `pr` skill

Read its `SKILL.md` from the first root that exists, project-local before global:

```text
<repo>/.agents/skills/pr   <repo>/.claude/skills/pr
~/.agents/skills/pr        ~/.claude/skills/pr
```

Use its live template as it stands; it is the single source for the body. If no root
has it, report that setup failure instead of writing a template from memory.

## Title

Line one of the file, at most 120 characters, naming the observable result rather than
the activity. `Reduce the Praxis IG to two extensions and eight code systems` beats
`Refactor IG`.

## Cross-repository references

Anywhere in the title or body, write an issue or pull request in another repository on
the same host as the pull request as `owner/repo#N` (for example
`cognovis/library-core#121` in a git.cognovis.de pull request) or as its full URL. When
the target lives on another host, write its full URL: `owner/repo#N` links on the pull
request's own host, so `cognovis/library-core#121` in a GitHub MIRA pull request links
the GitHub repository of that name, not the Forgejo issue. Never write a bare `#N` or
`<repo> #N` for another repository: Forgejo, GitHub and pr-agent link a bare `#N` to the
current repository, so `library-core #121` in a MIRA pull request links MIRA issue #121.
A bare `#N` is only for the same repository, as in `Closes #<n>`.

## Sections Cognovis adds

Append these after the sections the `pr` skill defines. This is the single list of
what a Cognovis delivery adds to the upstream template; a calling skill supplies the
content and does not keep its own copy of the list.

### Work order reference

`Closes #<n>` when the issue lives in the same repository, the full issue URL
otherwise.

### Review decisions

Rendered by `finding_triage.py --review-decisions`: the local review findings that were
deferred, and the ones the repair commit fixed. Take its output as given rather than
restating the findings.

### Verification

The verdict from the delivery's non-author verifier, the head SHA it verified, and each
run path with its observed result. A new commit on the branch invalidates the verdict.
`executive-pack` owns both this section's content and the verifier; do not produce a
verdict here.

### Reviewer routes

The model route each of the delivery's three reviewers actually used, as reported by
the delivery. Record a fallback route as the route; do not present an alias that was
unavailable.

### Merge assessment

Two lines supplied by `executive-pack` for the current head, each with a one-sentence
reason:

```text
Product decision: none deviating from <work order or user authorization> - <reason>
Economic damage: none expected - <reason>
```

Name the deviation or the expected damage instead when one exists. `executive-pack`
owns both assessments and the merge decision; this section only records them.

### Risk statement

Required when the review risk is not `none`, whether the work order's `Review-Risk:`
line or pr-agent's `review-risk:*` label set it. When pr-agent raises the class after
publication, add the section then. Each field must be checkable against the diff:

```text
Data class: <affected data: patient data, staff data, credentials, terminology/catalogues ...>
Boundary: <who can read, write or export what, before> -> <after>
Crossing: <for pii: the crossing cited from .agents/standards/pii-boundary.md, or the assumed boundary when the repository has none>
Scenario: <how damage would concretely occur, and what must already have gone wrong>
Reach: <dev stack or synthetic data only | customer instance with real personal data>
Reversal: <revertible, and how | what has already left the system>
Evidence: <the test or live check that proves the new boundary>
```

Omit `Crossing` for a class other than `pii`. When no concrete scenario can be named,
write `Scenario: none nameable - <reason>`: the classification is wrong and should be
`none`. The validity rules, the PII crossing types and what counts as economic damage
are in the `executive-pack` standard's Review risk section; do not restate them here.

Example, a blanket read-only terminology operation for workforce users of their own
tenant, labelled `auth`:

```text
Data class: terminology and catalogues; no personal data
Boundary: workforce users of a tenant cannot run the operation -> they can run it read-only on their own tenant
Scenario: none nameable - terminology holds no personal data and no new user group gains access
Reach: every instance, terminology content only
Reversal: revertible by restoring the previous pin
Evidence: the test that a workforce user of another tenant is still refused
```

The change touches auth but moves no data boundary, so the class should be `none` and
does not hold the merge.

### Known residuals

What the reviewer must still know: remaining risk, external configuration, a staged
rollout, intentionally excluded behaviour. Write `None known` when empty.

## Evidence that is not text

For a user-visible surface, the verification walkthrough (Playwright, CLI, or a scripted
check) captures what the user now sees. Attach it only when such a surface changed; a
change with no visual surface needs no screenshot.

1. Capture the headline frames, before and after where possible, into a scratch location
   outside the worktree.
2. Screen each one for secret values, customer data, prompts or pilot identifiers.
   Recapture or omit, and record the omission in the body.
3. Attach after the pull request exists. On GitHub, `gh pr edit <n> --attach
   './shot.png#alt text'` or the same flag on `gh pr comment`. On Forgejo, `POST` each
   file to `/api/v1/repos/{owner}/{repo}/issues/{index}/assets` with the multipart field
   `attachment` and embed the returned `browser_download_url`.
4. Authorize from the environment or existing ccore credential state; never on the
   command line, never in the body.
5. Never commit, diff or store this evidence inside the repository.

## Language

The `writing/unslop` and `writing/plain-technical-english` standards apply to the
finished text; they are not repeated here.

## Handoff to ccore

Write the file outside the worktree, for example `/tmp/pr-<branch>.md`, and pass its
full content as the summary:

```bash
ccore pr ensure --repo <worktree> --summary "$(cat /tmp/pr-<branch>.md)"
```

ccore takes line one as the title, truncated at 120 characters, keeps the whole text as
the body, picks `gh` or `fgj` from the remote, and appends the identity footer with
harness, session and work-order references. Do not write that footer yourself. It
rebases onto the target before its first push; when that moves the head commit, the
Verification section needs a fresh verdict. Push later commits with a plain `git push`.
The merge decision stays with the `executive-pack` delivery.

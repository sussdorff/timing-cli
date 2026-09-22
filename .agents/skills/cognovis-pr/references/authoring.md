# Pull request authoring contract

The body follows the `pr` skill template from the Matt Pocock catalog, which
credits `show-me` by Dex Horthy (Humanlayer). Two Cognovis sections and the
ccore handoff are added here. Skip preambles; keep prose brief; use the
repository's own domain language.

## Title

Line one of the file. Name the observable result, not the activity, in at most
120 characters. `Reduce the Praxis IG to two extensions and eight code systems`
beats `Refactor IG`.

## Body

```markdown
## Summary

<diagram, diff sketch, call tree, component tree, or shallow file tree>

## Evidence

- **Before:** <screenshot, output, or failing test run>
  **After:** <screenshot, output, or passing test run>

## Merge Danger

**Door:** <one-way or two-way>

**Blast Radius:** <one word>

<optional ramifications>

## Known residuals

<remaining risk, external configuration, staged rollout, excluded behavior, or `None known`>
```

### Summary

Pick the smallest view that makes the key point clear, and place each visual
next to the sentence it supports. Use one or two of these, never all:

- pseudocode for logic or an algorithm;
- a call tree for runtime control flow;
- a component tree for UI structure, including the state that matters;
- a shallow file tree for responsibility or a broad refactor;
- Mermaid for interaction, control flow, or data flow;
- a `diff` sketch of any of the above when the surrounding shape already exists.

Add a Mermaid diagram only when it makes a material relationship easier to see:
a sequence of three or more dependent steps, a state transition, a hierarchy,
or one source affecting three or more consumers. Label real system boundaries
and keep the diagram consistent with the prose. A diagram is never executable
evidence, and a decorative one for a file list or a single linear action is
noise.

### Evidence

Show that the change works, before and after. Screenshots rank highest when the
change is visual and the environment can capture them. Execution evidence ranks
next: the exact test or command that failed and now passes, with its verdict.
Label a live check that has not run as pending; never infer it.

### Merge Danger

A two-way door can be walked back; a one-way door cannot. Destructive actions,
migrations, and published interfaces are one-way doors. The blast radius names
what breaks if the change is wrong: layout, consumers, mobile, billing.

### Known residuals

Name what the reviewer must still know: remaining risk, external configuration,
staged rollout, intentionally excluded behavior. Write `None known` when empty.

## Walkthrough screenshots

For a user-visible surface the verification walkthrough (Playwright, CLI, or a
scripted check) captures what the user now sees.

1. Capture two to four headline screenshots, before and after where possible,
   into a scratch location outside the worktree.
2. Screen each one for secret values, customer data, prompts, or pilot
   identifiers; recapture or omit and record the omission in the body.
3. Attach after the pull request exists. On GitHub use `gh pr edit --attach` or
   `gh pr comment --attach` on the existing pull request. On Forgejo `POST`
   each file to `/api/v1/repos/{owner}/{repo}/issues/{index}/assets` with the
   multipart field `attachment` and embed the returned `browser_download_url`.
4. Authorize with a token from the environment or the existing ccore credential
   state; never on the command line, never in the body.
5. Never commit, diff, or store screenshots inside the repository.

## Unslop checklist

Run this over the finished text. It is the working subset of
`standards/writing/unslop.md`.

- No puffery, promotional adjectives, or generic conclusions; state what
  happened.
- No AI vocabulary: additionally, crucial, delve, enhance, foster, leverage,
  pivotal, robust, seamless, showcase, underscore.
- No "not just X, but Y", no forced triads, no synonym cycling; one name per
  thing.
- No em dashes, no colon as a mid-sentence hinge, no bold on every noun, no
  emoji, straight quotes.
- No chat artifacts: no greeting, no "hope this helps", no "great question".
- No metaphor nouns where a plain word exists: base for substrate, goal for
  north star, add for wedge in.
- Cut any sentence that could appear unchanged in another project's pull
  request.

## Handoff to ccore

Write the file outside the worktree, for example `/tmp/pr-<branch>.md`, and pass
its full content as the Session Close summary:

```bash
ccore session-close run ... --summary "$(cat /tmp/pr-<branch>.md)"
```

ccore takes line one as the title, truncated at 120 characters, keeps the whole
text as the body, and appends the identity footer with harness, session, and
work-order references. Publication
through `ccore pr ensure`, delivery choice, merge, push, and cleanup stay with
Session Close.

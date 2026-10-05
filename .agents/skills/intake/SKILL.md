---
name: intake
description: Turn notes, bug reports or initiatives into author-checked hosted issues; continue to delivery when the request authorizes implementation.
requires: [standard:workflow/issue-intake, skill:bug-triage, skill:executive-pack]
requires_standards: [workflow/issue-intake, writing/plain-technical-english, writing/unslop, writing/unambiguous-english]
---

# Intake

Turn source notes into factory-ready hosted issues. The original request is the authority
source: creating a work order and implementing it are different requested outcomes.
This active session remains the original author; do not delegate authoring. Never
run issue review automatically; review is a separate explicitly requested action.

The helpers ship in `scripts/` of the **installed** intake skill root, not the
marketplace source path. Resolve `$INTAKE_ROOT` local-first and fail closed if none
exists: `<repo>/.agents/skills/intake`, `<repo>/.claude/skills/intake`,
`~/.agents/skills/intake`, `~/.claude/skills/intake`. Never search the filesystem.

## Establish the request

Read the provided source and preserve it in local .intake scratch space. With no
source, ask for the missing input. Before extraction, read
[history.md](references/history.md) and run `scripts/issue_history.py` for the
target repository. Surface duplicate matches before creating another work order.

Classify the requested outcome by meaning:

- author-only: create, file or track work; stop with the created issue.
- author-and-execute: fix, build or deliver the requested change; continue after
  author-check and persistence.
- unclear: ask only the question that decides between those outcomes.

## Approve the boundary

One coherent outcome is one issue; implementation steps are internal work, not
sub-issues. When there is exactly one candidate, a clear target and requested outcome,
no duplicate choice and no competing boundary or Human Decision Gate, record
`approval_source: original_request`. Do not ask for a routine confirmation.

Ask only when multiple plausible candidate boundaries remain, whether to append
to the existing issue or create a new one is unresolved, the target repository is
ambiguous, the requested outcome is unclear, or a product/architecture/policy choice
is needed. Record `approval_source: explicit_hitl` for that decision. Never repeat
approval already given for the same scope.

For bug reports or multiple outcomes/initiatives, read [modes.md](references/modes.md).
Bug signals use the same conditional boundary gate; investigate safely while missing
evidence is pending. Do not turn an initiative into an epic automatically.

## Author and persist

Drafting happens **inline** in this session. Do not spawn an agent. Read
[authoring.md](references/authoring.md) for the body contract, including
classification_evidence, AC/MoC, Review-Risk and any genuine Human Decision Gate.
Validate the drafted body with `$INTAKE_ROOT/scripts/issue-author-check.py --body-file`
before `ccore tracker create --body-file` or `ccore tracker update --body-file`.
`ccore tracker create` and `ccore tracker list` take `--repo` as the registry key
`owner/repo` (for example `cognovis/library-core`) or a registry alias (for example
`clc`), as shown by `ccore repo resolve <key|alias>`; a bare repository name, path or
URL fails (`--repo library-core` returns `tracker_repo_unregistered`). There is no
`--title`: the title is the body's `Goal:` line in `## Intent`.
`ccore tracker` is the single interface: registry entries must declare `github` or
`forgejo`. Unhosted entries fail closed. If the checker cannot be resolved, stop and
report that limitation; an unvalidated body is never persisted.

Revise validation failures before mutation. Every issue needs exactly one Review-Risk
classification: none, payment, pii, auth or compliance. It is the work order's review
risk; pr-agent applies it as the floor of the pull request's `review-risk:*` label.
The class informs; it does not by itself hold a merge for a human. A class other than
`none` needs a concrete damage scenario, and `pii` a crossing of the repository's PII
boundary standard (the `executive-pack` standard, Review risk).
Use the original source and actual identifiers; do not invent evidence names.

## Continue according to authority

Author-only ends after persistence and deterministic validation with the issue
reference and check result. Author-and-execute invokes executive-pack in this active
session; do not ask for another implementation confirmation. That skill owns the
implementation entry path. Author-check failure never dispatches implementation. Manual review findings do not grant execution authority or
upgrade an author-only request.

Report created/updated issue references, duplicate dispositions, validation results
and whether delivery continued. Existing metadata/dependency updates use
`ccore tracker comment`; substantive body updates use
`ccore tracker update --ref --body-file` after the same inline author-check without a
new intake lifecycle.

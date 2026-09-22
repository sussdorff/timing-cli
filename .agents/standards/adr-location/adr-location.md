# ADR Location Standard

## Canonical Directory

Architecture Decision Records (ADRs) live at **`/docs/adr/`** in the project root.

## Bootstrap Structure

When `/project-setup` scaffolds or upgrades a project, it creates:

```
docs/
└── adr/
    ├── README.md              # ADR convention and MADR template
    └── ADR-0001-record-architecture-decisions.md  # Self-referential bootstrap ADR
```

## README.md Template (MADR-style)

The `docs/adr/README.md` should contain:

```markdown
# Architecture Decision Records

This directory contains Architecture Decision Records (ADRs) using the
[MADR](https://adr.github.io/madr/) (Markdown Any Decision Records) format.

## Template

Use this template for new ADRs:

---
# [short title of solved problem and solution]

## Status

[proposed | accepted | deprecated | superseded by ADR-NNNN]

## Context

[Describe the context and the problem you are trying to solve]

## Decision

[Describe the decision that was made and why]

## Consequences

[Describe the resulting context after applying the decision — good, bad, and neutral]
```

## New ADRs

Name files: `ADR-NNNN-kebab-case-title.md`

Start the ADR counter at 0001. The ADR-0001 is the self-referential bootstrap.

## Bootstrap ADR Content

`ADR-0001-record-architecture-decisions.md` should contain:

```markdown
# ADR-0001: Record Architecture Decisions

## Status

Accepted

## Context

We need to record architectural decisions made for this project so that:
- Future team members understand why decisions were made
- We can revisit decisions when context changes
- We avoid relitigating settled decisions

## Decision

We will use Architecture Decision Records (ADRs) in the MADR format, stored in `/docs/adr/`.

## Consequences

- All significant architectural decisions must be recorded as ADRs
- ADRs are immutable once accepted; superseded ADRs reference their successor
- The ADR directory is bootstrapped by `/project-setup` and tracked in git
```

## Governing Corpora

A repository that is governed by decisions recorded in another repository of
the same family declares that in `.adr-governance.json` at its own root:

```json
{
  "schema_version": 1,
  "governing_corpora": [
    {"corpus": "fhir-management", "workspace_path": "../fhir-management"}
  ]
}
```

`corpus` is the stable identity reported for every ADR selected from it.
`workspace_path` is resolved relative to the declaring repository root, and
`docs/adr` under the resolved root is the corpus. The path MUST be relative:
an absolute path would bind the declaration to one machine's checkout layout,
so absolute entries are ignored.

Context discovery then selects from the local corpus and every declared
corpus, matching family selectors against the declaring repository's own
candidate surface. A repository without this file keeps local-only discovery.

A declared corpus that has no `docs/adr` is reported as an unresolved
`ADR_GOVERNING_CORPUS_MISSING` gap, not skipped: guidance the repository
claims to be governed by must not go missing quietly.

## Declaring a Decided Topic

An ADR MAY name the topic it decides in frontmatter:

```yaml
decides: polaris-client-access
status: accepted
```

The topic key is what makes contradiction detectable instead of a matter of
reading prose. When two or more applicable ADRs with `status: accepted` decide
the same topic in different corpora, context discovery reports an unresolved
`ADR_DECISION_CONFLICT` gap naming the topic and every conflicting record. It
does not pick a winner — both remain visible with their own precedence, and a
human supersedes one or narrows its `applies_to`. A record whose status is not
`accepted` proposes rather than decides and never conflicts.

## Legacy Alternatives

The following legacy paths are accepted by verification tooling for backwards compatibility:
- `/docs/adrs/` (plural)
- `.claude/adrs/`

New projects MUST use `/docs/adr/`. Legacy paths should be migrated on next `/project-setup --upgrade`.

## inject-standards Triggers

This standard is loaded on: `ADR`, `architecture decision`, `decision record`, `adr-location`, `docs/adr`

# Unslop: removing AI tells from prose

> **Scope**: Prose written for people. [plain-technical-english.md](plain-technical-english.md)
> owns sentence mechanics; this file lists the patterns that mark a text as
> machine-written. An exact output contract (a template, a schema, a fixed
> heading) overrides a presentation tell. Adapted from the `unslop` skill in
> cursor/plugins ([pinned source](https://github.com/cursor/plugins/blob/99559f2f52047978602ef365589275831e76af07/pstack/skills/unslop/SKILL.md),
> MIT, copyright 2026 Lauren Tan, notice in [third-party-notices.md](third-party-notices.md)).
> `requires_standards` has no runtime loader; a skill that needs this checklist
> embeds it, as `cognovis-pr` does for pull request text.

Whatever would make a text obviously AI-generated to its reader is a tell,
listed here or not.

- Puffery, promotional adjectives, vague attribution, formulaic arcs, generic
  conclusions: state what happened, name the source, or end earlier.
- AI vocabulary (additionally, crucial, delve, enhance, foster, leverage,
  pivotal, robust, seamless, showcase, tapestry, underscore) and fancy "is"
  ("serves as", "boasts"): use the plain word.
- "Not just X, but Y", forced triads, synonym cycling, false ranges: say Y,
  use the natural number, one name per thing.
- Em dashes, colons as mid-sentence hinges, bold on every noun, inline-header
  lists that restate the line, Title Case headings, emoji, curly quotes.
- Chat artifacts ("I hope this helps", "Great question", cutoff disclaimers):
  delete.
- Metaphor nouns (substrate, wedge, vector, nexus, flywheel, north star,
  paradigm, scaffolding): the plain concrete word. Exact repository-defined
  senses such as a Library `primitive`, a coding `harness`, or a permission
  `surface` stay.
- Voice, for editorial prose only: react to the facts, vary rhythm, prefer the
  specific observation, and cut any sentence that could appear unchanged in
  another project's docs.

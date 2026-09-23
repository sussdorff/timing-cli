# Unambiguous English

> **Scope**: Prose written for people, alongside
> [plain-technical-english.md](plain-technical-english.md). That file makes
> sentences short and plain; this file makes them parse exactly one way for a
> non-native reader, a translator, and an agent alike. Core rules restated
> from Kohl, *The Global English Style Guide* (SAS Press); see
> [third-party-notices.md](third-party-notices.md). Rule 0 and the
> quoted-material exclusions of plain-technical-english override every rule
> here: exact technical notation, paths, URLs, citations, and quoted material
> keep their form.

## Placement and reference

- Keep "only" and "not" next to the word they change. "Only fails on growth"
  and "fails only on growth" say different things.
- Make every "it", "they", and "this" point at one obvious noun. Repeat the
  noun when in doubt. Never use "this" or "which" to point at a whole clause.
- Call each thing by one name, everywhere. A document that says "the gate",
  "the check", and "the budget" for one thing teaches three things.

## Structure words

- Keep the small words that show structure. "Ensure that the switch is off"
  keeps "that" because it forces one parse. Never trade clarity for word
  count.
- Do not omit a required article. "Remove backup file" reads two ways;
  "remove the backup file" reads one. Generic plurals and mass nouns take no
  article and need none.
- Repeat the article in a series when it prevents a misread: "the client and
  the host" when they are two things.
- Do not drop verbs in parallel clauses. "Phase 1 moves the converters and
  Phase 2 the runtime" leaves phase 2 without a verb.

## Grouping

- Say which parts "and" or "or" joins when a sentence can group two ways.
  "Both … and", "either … or", and "if … then" are explicit grouping markers
  that cost nothing.
- Rewrite long noun strings: "the proto import budget check script" becomes
  "the script that checks the proto-import budget".

## Notation

- No slash shorthand between words: write "a, b, or both" instead of "a/b" or
  "and/or". Slashes in paths, URLs, and literal technical names stay.
- No "(s)" plurals; pick singular or plural.
- Periods over semicolons. An em dash becomes a new sentence.
  [unslop.md](unslop.md) states the em-dash rule.
- Text in parentheses is a full grammatical unit or its own sentence. Short
  glosses of a technical term stay allowed, as
  plain-technical-english.md rule 0 defines them.
- Prefer "for example" and "that is" over Latin abbreviations in running
  prose. Citations and literal terminology keep their exact form.

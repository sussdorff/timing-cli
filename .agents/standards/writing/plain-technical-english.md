# Plain Technical English

> **Scope**: Prose written for people — reports, summaries, explanations, bead
> bodies, commit messages, PR descriptions, review findings, and documentation.
> Derived from ASD-STE100 Simplified Technical English, a controlled English
> written for aircraft maintenance manuals so that non-native readers understand
> it on the first pass.

## Rule 0 — a technical term keeps its name

Never simplify a technical term away. Use the exact name, then gloss it once at
first use in a clause or a short parenthesis.

This rule outranks every rule below. When plain wording and precision conflict,
precision wins.

| Write | Do not write |
|-------|--------------|
| a race condition (two writers reach the same value at once) | a timing problem |
| the call is idempotent — a repeat run changes nothing | it is safe to run twice |
| the worktree (a second checkout of the same repository) | the folder |

Gloss a term once per document, not once per paragraph.

## Where this standard applies

Applies to prose a person reads.

Does **not** apply to:

- Structured output — JSON returns, tool arguments, schema field values.
- Bead field structure, Acceptance Criteria wording driven by `bead-hygiene`, and
  reviewer finding shapes.
- Code, identifiers, log messages, and error strings. `english-only` governs those.
- Quoted material, command output, and file contents.

Never rewrite a field value to sound simpler. Shape rules win over style rules.

## The rules

1. **Use the active voice.** Name the actor. "The loader skips the file", not
   "the file is skipped".
2. **Write short sentences.** One idea per sentence. Split a sentence that carries
   two claims.
3. **Prefer the short word** when the short word means the same thing. Rule 0
   holds: a precise long term is not a long word.
4. **Cut every word that carries nothing.** Delete hedges, throat-clearing, and
   restatement.
5. **Keep one meaning per word** inside a document. If `entry` means a catalog
   record in paragraph one, it does not mean a log line in paragraph four.
6. **Avoid worn metaphors and jargon** when a plain word exists. No "under the
   hood", no "leverage" where "use" works.
7. **Break any rule above** rather than write something unclear or ugly.

Rules 1, 2, 4, and 7 come from George Orwell's six rules for writing. Rules 3, 5,
and 6 restate ASD-STE100 principles that survive contact with engineering text.

## What this standard does not adopt

ASD-STE100 also holds authors to an approved word list of roughly 900 entries,
one part of speech per word, and counted sentence limits. This standard adopts
none of that. The word list has no entry for most terms in this codebase, and
enforcing it would breach Rule 0.

Treat sentence length as judgement, not as a counted limit.

## Examples

<example-good>
A consumer declares each automatically delivered standard in
`requires_standards`. An undeclared standard reaches the model only on an
explicit request.
</example-good>

<example-bad>
It should be noted that standards may not be delivered automatically in the
event that they have not been declared, since automatic injection is operating
on what is generally referred to as an explicit-declaration basis.
</example-bad>

<example-bad>
The injector is picky about which standards it lets through.
</example-bad>

The second bad example is short and active, and it still fails: "picky" replaces
the exact behaviour that "explicit declaration" names.

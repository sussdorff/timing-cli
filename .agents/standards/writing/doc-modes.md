# Documentation modes

> **Scope**: Technical documentation that serves a tutorial, how-to,
> reference, or explanation need: guides, feature docs, READMEs. Loaded by
> doc-writing primitives, not by summary or handoff writers. Adapted from the
> Diátaxis framework by Daniele Procida (diataxis.fr, CC BY-SA 4.0) and the
> Google developer documentation style guide (CC BY 4.0); this file is
> distributed under CC BY-SA 4.0. Full notices in
> [third-party-notices.md](third-party-notices.md).

## One passage, one reader need

Two questions pick the mode: does the content inform **action** (doing) or
**understanding** (thinking), and does it serve **learning** or **work**?

| | Learning | Work |
|---|---|---|
| **Action** | Tutorial | How-to |
| **Understanding** | Explanation | Reference |

The unit of classification is the reader need a passage serves, not its
Markdown form; a table can be tutorial content and a paragraph can be
reference. The compass applies from a single sentence up to a whole document.
The failure to avoid is serving two needs in one passage: teaching pauses
inside a how-to, task walkthroughs inside reference, persuasion inside
lookup material. When a passage genuinely serves another need, split it out
or link to it. A document works best when it commits to one dominant mode
and links outward for the others.

## The four modes

- **Tutorial** (learning by doing): the learner's success is the author's job.
  Open with what the learner will build. Every step produces a visible result,
  and the text says what the learner should see. Explanation stays at one
  clause plus a link.
- **How-to** (steps to a goal): solves a problem a person has, not an
  operation the machine can perform. Assumes competence, skips teaching,
  allows forks ("if you want x, do y"). Named by the task: "How to calibrate
  the radar array", not "Radar array calibration".
- **Reference** (facts for lookup): describes. Dry, complete, no hedging, no
  persuasion. No task procedures and no teaching; concise usage constraints,
  mandatory conditions, and warnings remain reference. Mirrors the structure
  of the thing described; generated from code where possible.
- **Explanation** (understanding and why): one bounded topic, readable away
  from the product. Each title tolerates an implicit "About …" in front.
  Design decisions, history, constraints, alternatives. Among the four
  documentation modes, explanation is the one for opinion and perspective;
  editorial genres outside these modes carry judgment under
  [unslop.md](unslop.md)'s voice rules.

## Instruction sentences

In tutorial and how-to passages:

- Write steps as commands with an imperative verb: "Click Submit."
- Put the circumstance, condition, or goal before the instruction: "To delete
  the document, click Delete." The reader skips what does not apply.
- Never "simply", "easy", or "quickly" in a procedure. If it were simple, the
  reader would not be here.
- Numbered lists for sequences, bullets for everything else.

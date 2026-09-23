# PASS3-TYPE-EXEMPT-CHORE Golden File

## Fixture

`fixtures/PASS3-TYPE-EXEMPT-CHORE.json` + `fixtures/overlay-type-exempt.md` as project overlay

## What This Tests

A rule with `<!-- types: feature -->` must NOT trigger for a `chore` bead.

## Expected Outcome

Pass 3 must NOT report the "Missing Aidbox-Schema-Impact section" finding.
The chore bead is exempt from this rule because its type is not in the `<!-- types: feature -->` filter.

## Pass 3 Output Requirements

- No `[OVERLAY-RULE]` Critical finding in the output
- The Overlay Source section lists the rules count from the overlay
- Verdict is NOT overridden to NEEDS INTERACTIVE WORK due to this rule

## Minimum Required in Output

Pass 3 findings section must either:
- Be absent (if all Pass 3 checks pass), OR
- Show "Project overlay check: CLEAN — no overlay rule violations detected."

The output must NOT contain a Critical finding referencing "Aidbox-Schema-Impact" for this chore bead.

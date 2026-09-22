# Expected Finding: TITLE-ACTIVITY

**Fixture**: `fixtures/TITLE-ACTIVITY.json`
**Pattern**: TITLE-ACTIVITY — Activity-named instead of outcome-named
**Expected severity**: Critical
**Expected finding excerpt**: The title "Implement OAuth Handler" names a technical artifact ("OAuth Handler") via an activity verb ("Implement") rather than stating the user or system outcome. A reviewer cannot determine what value is delivered from the title alone.
**Anti-pattern code in finding**: [TITLE-ACTIVITY]
**Minimum required in output**: A Critical finding referencing TITLE-ACTIVITY, citing the title text "Implement OAuth Handler", noting the activity-verb + technical-artifact naming pattern.

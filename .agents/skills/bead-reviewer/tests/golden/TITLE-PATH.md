# Expected Finding: TITLE-PATH

**Fixture**: `fixtures/TITLE-PATH.json`
**Pattern**: TITLE-PATH — File/path as title
**Expected severity**: Critical
**Expected finding excerpt**: The title "Update auth.py" is a file path (module name with file extension) rather than a description of the outcome the work delivers. The title names the artifact being modified, not the change in system behaviour.
**Anti-pattern code in finding**: [TITLE-PATH]
**Minimum required in output**: A Critical finding referencing TITLE-PATH, citing the title text "Update auth.py", noting that the title is a file path or module name.

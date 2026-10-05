## Phase 0.5: Duplicate Search

Run the duplicate search before extraction or drafting. Use the intake skill's own
helper from the resolved installed skill root (`$INTAKE_ROOT`, see SKILL.md); never
search the filesystem for another copy:

```bash
uv run python "$INTAKE_ROOT/scripts/issue_history.py" "$INTAKE_INPUT" --repo <registry-key>
```

`--repo` is the registry key (`owner/repo`) or a registry alias of the target
repository, as accepted by `ccore tracker list --repo`. The helper returns JSON with
three lists:

- `open_issues`: open hosted issues whose title or body shares terms with the input,
  highest overlap first (`number`, `title`, `url`, `score`)
- `match_fields`: the issue fields the search compared. `["title", "body"]` means every
  listed issue was matched on title and body; `ccore tracker list` returns bodies on
  GitHub and Forgejo since ccore 2026.9.18. `["title"]` means title-only coverage: at
  least one listed issue carried no body, for example from an older ccore. `[]` means the
  repository has no open issues.
- `open_brain_memories`: related Open Brain memories, or an empty list when the `ob`
  CLI is not installed

A failing tracker call exits non-zero with the reason on stderr. Report it; "could not
search" is not "no duplicate".

Title-only coverage is weaker: a duplicate whose title uses other words is missed. When
`match_fields` is `["title"]`, say so in the report, and read the bodies of plausible
candidates with `ccore tracker show <owner/repo#N>` before concluding there is no
duplicate. The helper does not fetch missing bodies itself; upgrade ccore instead.

Review `open_issues` and `open_brain_memories` for duplicates or already-completed
work. If the input matches an existing issue, surface it before doing anything else:

```text
This appears to be already filed as <owner/repo#N>: <title>.
```

Ask whether to append context to the existing issue, continue with a new candidate, or
stop. Do not proceed to drafting until the user confirms the intended path.

## Phase 0.5: History Query

Run the history query before extraction or drafting. Probe only these paths in order,
using the first file found:

1. `<repo>/.agents/scripts/triage/query_history.py`
2. `<repo>/scripts/triage/query_history.py`
3. `~/.agents/scripts/triage/query_history.py`

Never search broadly. If none of these paths exists, fail loudly and report every
probed path:

```bash
if test -f ".agents/scripts/triage/query_history.py"; then
  history_query_script=".agents/scripts/triage/query_history.py"
elif test -f "scripts/triage/query_history.py"; then
  history_query_script="scripts/triage/query_history.py"
elif test -f "$HOME/.agents/scripts/triage/query_history.py"; then
  history_query_script="$HOME/.agents/scripts/triage/query_history.py"
else
  printf '%s\n' "Intake history helper unavailable. Probed: .agents/scripts/triage/query_history.py; scripts/triage/query_history.py; $HOME/.agents/scripts/triage/query_history.py" >&2
  exit 1
fi

uv run python "$history_query_script" "$INTAKE_INPUT" --repo .
```

Review `closed_beads` and `open_brain_memories` for duplicates or already-completed
work. If the input matches an existing bead, surface it before doing anything else:

```text
This is already filed as X when X=<bead-id>.
This appears to be already filed as <bead-id>: <title>.
```

Ask whether to append context to the existing bead, continue with a new candidate, or stop.
Do not proceed to drafting until the user confirms the intended path.

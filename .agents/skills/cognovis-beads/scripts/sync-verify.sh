#!/usr/bin/env bash
set -euo pipefail

# Beads archive verification. When the registry entry declares a tracker, use
# `ccore tracker` instead of `bd`; with no tracker field, keep `bd`.

RUN_ID="sync-verify:$(date +%s):$$"

RUN_ID="sync-verify:$(date +%s):$$"

bd list --limit 1
ccore beads sync --operation-id "$RUN_ID:initial"

TEST_ID=$(bd create --title="push test" --type=task --priority=4 | grep -oE '[A-Z]+-[a-z0-9]+' | head -1)
ccore beads sync --operation-id "$RUN_ID:create"
bd close "$TEST_ID" --reason="test"
ccore beads sync --operation-id "$RUN_ID:close"

#!/usr/bin/env bash
# Repository preflight: fail when the toolchain version check fails.
# The fleet global pre-push hook (~/.githooks/pre-push) runs this script;
# .githooks/pre-push delegates to it for clones with their own hooks.
set -euo pipefail

top="$(git rev-parse --show-toplevel)"
cd "$top"

if ! python3 .agents/standards/toolchains/scripts/check_toolchain_versions.py; then
    echo "preflight: toolchain version check failed; push aborted." >&2
    exit 1
fi

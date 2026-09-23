#!/usr/bin/env bash
set -euo pipefail

STANDARD_FILE="$(git rev-parse --show-toplevel)/standards/workflow/uat-config-schema.md"

for resource_type in browser cli tui api artifact; do
  rg -q "type: ${resource_type}" "$STANDARD_FILE"
done

rg -q "agentic_acceptance:" "$STANDARD_FILE"
rg -q "Forbidden registry keys" "$STANDARD_FILE"
rg -q "interactive .*playwright-cli" "$STANDARD_FILE"
rg -q "ccore acceptance run" "$STANDARD_FILE"

if rg -q "playwright_scenarios|uat_strategy\.mode" "$STANDARD_FILE"; then
  echo "FAIL: obsolete scenario-driven UAT schema remains"
  exit 1
fi

if rg -q "live_acceptance_canary.py" "$STANDARD_FILE"; then
  echo "FAIL: uat-config standard still names live_acceptance_canary.py"
  exit 1
fi

if ! command -v ccore >/dev/null 2>&1; then
  echo "FAIL: ccore is not installed"
  exit 1
fi

ccore acceptance run --help >/dev/null

echo "PASS: resource-only agentic acceptance registry is documented"

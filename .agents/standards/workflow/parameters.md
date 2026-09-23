---
name: parameters
description: Optional parameters array for workflow meta blocks — the shared contract for clw CLI mapping and workflow-forge validation.
---

# meta.parameters Standard

> **Scope**: All Claude Workflow `.js` files in this library. Consumed by `clw` CLI mapping and workflow-forge validation mode.

## Rule

A workflow's `meta` block MAY declare a `parameters` array. The array is **OPTIONAL** — workflows without it remain valid and receive args as raw JSON.

When present, `parameters` defines the declared CLI interface for `clw --help` output and for type-coercion by the `clw` launcher.

## Parameter Field Shape

Each entry in the `parameters` array must conform to the following shape:

```json
{
  "name": "beadIds",
  "type": "list",
  "required": true,
  "help": "Comma-separated bead IDs to review independently"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | yes | CLI flag name in kebab-case (e.g. `bead-ids`, `strict`) |
| `type` | string | yes | One of: `string`, `list`, `bool`, `number` |
| `required` | boolean | yes | Whether the parameter must be supplied |
| `default` | any | only when `required: false` | Default value when not supplied |
| `help` | string | yes | One-line description shown in `clw --help` output |

## Type-Coercion Semantics

The `clw` CLI maps command-line arguments to the workflow `args` JSON object using these rules:

| Type | CLI input | Coerced to | Example |
|------|-----------|------------|---------|
| `string` | `--name value` | `"value"` (passed through as-is) | `--title "my workflow"` → `{"title": "my workflow"}` |
| `list` | `--ids a,b,c` | `["a","b","c"]` (comma-split) | `--beadIds clc-1,clc-2` → `{"beadIds": ["clc-1","clc-2"]}` |
| `bool` | `--strict` / `--no-strict` | `true` / `false` | `--strict` → `{"strict": true}` |
| `number` | `--limit 10` | `10` (parsed as float) | `--limit 5` → `{"limit": 5}` |

## Backward Compatibility

Workflows that do not declare a `parameters` array remain fully valid. They receive the raw args JSON as supplied by the caller. The `clw --help` output for such workflows shows "no declared parameters".

## JSON-Literal Constraint

The `meta` block **MUST** be a pure JSON-parseable literal — no JavaScript functions, no dynamic expressions, and no template literals inside `meta` (including `parameters` values). The meta block is parsed statically before the workflow runs.

This is **enforced** at authoring time and at deploy time by the workflow parse-gate (`skills/workflow-forge/scripts/check-workflow-parse.mjs` and the library installer's `_assert_workflow_native_parse`): a meta literal containing a template literal, a parenthesis (call / arrow / grouping), or a spread is rejected. Parentheses/braces/backticks *inside* a meta string value are content and are allowed.

Correct:
```js
const meta = {
  name: "bead-review",
  description: "Review beads in parallel",
  parameters: [
    { name: "beadIds", type: "list", required: true, help: "Comma-separated bead IDs" }
  ]
};
```

Incorrect (dynamic — forbidden):
```js
// FORBIDDEN: no functions, no template literals, no Date.now() inside meta
const meta = {
  name: "bead-review",
  parameters: [
    { name: "beadIds", type: "list", required: true, help: `IDs as of ${Date.now()}` }
  ]
};
```

## Slot Resolution (`meta.slots`)

A workflow MAY declare an optional `meta.slots` array — a list of route-profile slot
names it needs resolved before it runs (e.g. `['implementation', 'adversarial_review',
'verification', 'session_close']`). It is a generic launcher directive, not specific to
any one workflow.

```js
export const meta = {
  name: "bead-orchestrator",
  description: "...",
  parameters: [ /* ... */ ],
  slots: ["implementation", "adversarial_review", "verification", "session_close"],
};
```

A native workflow is inert — it cannot read `orchestrator-config.yml` or resolve
route-profile mappings itself, and native `agent()` only runs Claude subagent types
(not `codex-*` / `active-context` adapters). So when `meta.slots` is present the
launcher (`clw`) MUST, generically:

1. Resolve each listed slot via the active route profile's `full.<slot>` mapping
   (the `routeProfile` parameter selects the profile).
2. Inject the resolved, **native-runnable** targets as
   `args.slots[<slot>] = { agentType, model }` before dispatch.
3. Only inject native (`claude-agent`) targets; a slot that resolves to a non-native
   adapter (`codex-*` / `active-context`) is a projection and MUST NOT be passed to
   native execution (omit it or fail with a clear message).

Workflows that declare `meta.slots` read `args.slots[<slot>]` and SHOULD fail closed
if a required slot is absent (never guess a model). Workflows without `meta.slots` are
unaffected.

## Consumers

This standard is consumed by:

- **`clw` CLI** (`bin/clw` in meta-repo) — maps CLI flags to workflow args JSON using the `type` field for coercion, validates `required` fields, and (when `meta.slots` is declared) resolves route-profile slots into `args.slots` before dispatch.
- **workflow-forge validation mode** (`skills/workflow-forge/`) — checks that declared parameters conform to this schema as item 8 in the validation checklist, and runs the native parse-gate (which enforces the JSON-Literal Constraint).
- **workflow parse-gate** (`check-workflow-parse.mjs` + the installer's `_assert_workflow_native_parse`) — enforces the JSON-Literal Constraint at authoring and deploy time.

# Node

Bun replaces Node as the runtime and test runner in Cognovis TypeScript code.
New code uses `bun test`, not `node --test`, and runs on Bun. Node remains only
where a third-party tool requires it, and there it runs the latest LTS release
(`setup-node` with `node-version: lts/*`, a current `node:<lts>` image).

Every Node usage is a Bun migration candidate. The check reports each one with
status `node_usage` and reason `bun_migration_candidate`, and never fails on it.
A migration is its own work order. The reported usages are:

| Usage | Where |
|-------|-------|
| `node --test` suites | `package.json` scripts (kind `node-test-script`) and workflow `run:` commands (kind `node-test-run`) |
| Direct `node` invocations | `package.json` scripts such as `node dist/index.js` (kind `node-script`) |
| `setup-node` steps | CI workflows, with the `node-version` or `node-version-file` value |
| Node images | `FROM node:…`, Compose and workflow `image: node:…`, also with a templated tag (`node:${NODE_VERSION}`) |
| `engines.node` | `package.json` (kind `engines-node`) |
| Version files | `.nvmrc`, `.node-version`, `nodejs`/`node` in `.tool-versions` and `mise.toml` |

Existing `node --test` suites stay covered by the test-suite upkeep rules of
the `typescript` standard until they move to `bun test`.

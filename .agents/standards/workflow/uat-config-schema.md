---
domain: workflow
description: Resource-only project registry for Executive Pack agentic acceptance.
---

# Agentic Acceptance Resource Registry

Projects declare candidate user interfaces under `agentic_acceptance.resources`
in `.claude/uat-config.yml`. The configuration identifies real resources and their
safety boundaries. It does not contain scenarios, steps, operation sequences, or
expected results. The independent validator derives actions from live Bead AC/MoC
claims and current capability documentation.

The Executive Pack driver resolves environment references, binds every resource to
the final candidate SHA, signs the resolved registry with Pack-owner trust, and captures
the authority id in the acceptance request. Trust keys are caller inputs, never project
configuration or evidence fields. A project may retain unrelated legacy UAT configuration for an
independent release runner, but that material is not an Executive Pack acceptance
input and cannot qualify `agentic_acceptance` evidence.

## Configuration Shape

```yaml
agentic_acceptance:
  resources:
    - id: application-browser
      type: browser
      provenance:
        kind: candidate
        identity: application-web
        digest_env: APPLICATION_IMAGE_DIGEST
      credentials:
        mode: environment
        references: [DEMO_STAFF_USERNAME, DEMO_STAFF_PASSWORD]
      boundaries:
        origins: ["https://candidate.example"]

    - id: application-cli
      type: cli
      provenance:
        kind: candidate
        identity: application-cli
        digest_env: APPLICATION_BINARY_SHA256
      credentials:
        mode: none
        references: []
      boundaries:
        executable: application
        allowed_argv_prefixes:
          - [status]
          - [profile]
        cwd: "."

    - id: application-tui
      type: tui
      provenance:
        kind: candidate
        identity: application-cli
        digest_env: APPLICATION_BINARY_SHA256
      credentials:
        mode: none
        references: []
      boundaries:
        executable: application
        allowed_argv_prefixes:
          - [interactive]
        cwd: "."

    - id: application-api
      type: api
      provenance:
        kind: candidate
        identity: application-api
        digest_env: APPLICATION_IMAGE_DIGEST
      credentials:
        mode: environment
        references: [APPLICATION_API_TOKEN]
      boundaries:
        origins: ["https://candidate.example"]
        methods: [GET, POST]
        path_prefixes: ["/api/v1/"]

    - id: application-artifact
      type: artifact
      provenance:
        kind: candidate_projection
        identity: application-package
        digest_env: APPLICATION_PACKAGE_SHA256
      credentials:
        mode: none
        references: []
      boundaries:
        roots: [dist]
        read_only: true
```

## Resource Contract

Every resource requires:

| Field | Meaning |
| --- | --- |
| `id` | Unique stable resource identity within the project. |
| `type` | `browser`, `cli`, `tui`, `api`, or `artifact`. |
| `provenance.kind` | `candidate` or `candidate_projection`; stand-ins and mocks are invalid. |
| `provenance.identity` | Stable identity of the delivered surface. |
| `provenance.digest_env` | Name of the caller-provisioned environment variable containing its digest. |
| `credentials.mode` | `none`, `environment`, or `file_reference`. |
| `credentials.references` | Names of credential inputs. Values never enter configuration or evidence. |
| `boundaries` | Type-specific origins, argv prefixes, methods/paths, or read-only roots. |

The resolved request replaces `digest_env` with `provenance.sha256`, adds the
exact `candidate_sha`, and signs the complete resource list. Missing environment
inputs, wrong-candidate provenance, unsigned resources, duplicate ids, unknown
types, or incomplete boundaries block acceptance.

## Type-Specific Boundaries

- Browser origins restrict interactive `playwright-cli` navigation. They do not
  prescribe pages, clicks, assertions, or expected content.
- CLI and TUI prefixes are argv arrays, never shell command strings. The wrapper
  rejects shell separators and invokes the executable directly. TUI always uses a
  PTY. Their `cwd` is a built or installed runtime projection; a repository root
  containing source, tests, Beads, or Git metadata is rejected by the live canary.
- API origins, methods, and path prefixes bound real network requests. There is no
  mock or request-interception mode.
- Artifact roots are candidate-delivered or projected paths and are always read-only.

For authenticated actions, the validator gives the wrapper an allowed reference name,
not its value: `value_env` for browser fill, `stdin_env` for CLI/TUI stdin, or
`headers_from_env` for API header names. The wrapper resolves only names listed in the
signed credential boundary and redacts resolved values from captured output.

Forbidden registry keys include `step`, `steps`, `scenario`, `scenarios`, `action`,
`actions`, `operation_sequence`, `command_sequence`, `expected`,
`expected_result`, and `expected_results`, at any nesting depth.

## Claim and Documentation Boundary

Configuration is not the source of acceptance claims. The driver captures:

1. every live admitted Bead criterion with its ordinal, exact text, and MoC;
2. every current documented capability claim with a document digest and repeatable
   user-facing validation guidance.

Missing ordinals, duplicate claims, missing docs, changed text, changed document
digests, or post-capture drift invalidate the request. Documentation production
runs before acceptance and produces signed candidate-bound documentation evidence.
A repair invalidates both evidence providers: fresh documentation must be recorded
before the fresh acceptance dispatch.

## Browser Acceptance Is Not Test Automation

The validator explores the real browser using the bounded wrapper around
interactive `playwright-cli`. Executive Pack acceptance never authors or runs
Playwright specs, snapshot assertions, request mocks, or a frontend test suite.
Deterministic frontend automation, when a product later adopts it, remains a
separate quality gate and is not agentic acceptance evidence.

## Live Canary

The installed `ccore acceptance run` command is the live acceptance runtime. Run
`ccore acceptance run --help` for the authoritative interface. Default transport is
`codex-cli`. Use the `acpx` transport only with an explicit project `.acpxrc.json`.
If `ccore` is absent, stop; do not scan for or invoke skill-bundled Python files.
The caller supplies the exact authenticated transport, adapter/provider, model,
reasoning, candidate input JSON, candidate root, caller-owned
authority/registry/dispatch trust environment variables, and output path. The
registry key signs resource and documentation inputs.
The distinct dispatch key attests the exact request, report, terminal event digest,
route, model, session, and receipt. Pack state records only authority and key digests.
The canary creates a fresh source-free linked-worktree capsule, dispatches
`uat-validator` through either the native first-party route or an optional external
provider route, and validates its claim-complete report.

A caller-owned bounded surface broker remains outside the validator's model-command
sandbox. It holds the registry-verification authority, revalidates every chosen action,
and operates the real browser, CLI, PTY-TUI, API, or artifact surface. The validator sees
only a bounded filesystem mailbox and action receipts; it never receives registry HMAC
keys, raw credentials, or the interactive browser control plane. Native first-party
authentication uses the caller's existing ChatGPT/Codex login without copying an auth
file or requesting an API key. Browser screenshots are written only to a separate
ephemeral evidence root, never to the delivered candidate, CLI/TUI working directories,
or read-only artifact roots.

The sandbox uses the operational macOS runtime policy as its base and overlays
deny-precedence barriers for the target repository, all candidate paths outside the
resolved resource list, agent session/configuration roots, and credential stores. It
permits persistent writes only inside the capsule, relocates temporary and tool-cache
writes there, and removes ambient Node, Python, and shell code-injection variables before dispatch.
Only exact `--runtime-read-path` values can exempt a required adapter file or directory.
An exact configuration file also permits enumeration of its ancestor directories so a
real adapter config loader can discover it. This never grants sibling file contents:
credential files, sessions, history, logs, conversations, and other protected state
remain denied, and the protected adapter-state root itself cannot be exempted.

This attestation is local workflow-integrity evidence, not a security boundary against
the machine owner. Any process that can read the caller's trust environment or rewrite
the contract and state can forge it. Keep trust material outside implementer inputs and
never describe the resulting receipt as host-compromise-resistant.

External-provider adapter authentication/configuration is caller-provisioned with
repeatable exact `--runtime-read-path` values. Do not expose a complete home, source,
test, or session history directory. Native first-party authentication remains in the
host-owned Codex process and does not use `--runtime-read-path`. Product filesystem reads
are derived only from the signed CLI/TUI working directories and artifact roots; browser
and API access requires no source read.

The caller also supplies one persistent `--attempt-ledger` for the Pack. The canary
atomically appends reservations and terminal transitions. A product pass or product
failure consumes one of the candidate's three product-attempt ordinals. Route and
infrastructure failures are recorded but do not consume an ordinal, so the next dispatch
reuses the same ordinal. One unresolved reservation blocks concurrent reuse.

An operator may explicitly abandon unresolved infrastructure or route reservations with
`--recovery-manifest <path>`. Recovery is never implicit. The JSON document has this
shape:

```json
{
  "contract": "cognovis.agentic-acceptance-recovery-manifest.v1",
  "recoveries": [
    {
      "candidate_sha": "<candidate commit SHA>",
      "reservation_sha256": "<exact unresolved reservation digest>",
      "request_sha256": "<stored request digest>",
      "product_attempt_ordinal": 1,
      "failure_type": "infrastructure_failure",
      "evidence_sha256": "<driver failure evidence digest>",
      "operator_id": "<delivery-owner identity>"
    }
  ]
}
```

The complete batch is validated and candidate-bound before one atomic append. Only
`infrastructure_failure` and `route_failure` are recoverable. Missing or mismatched
candidate, exact reservation, request, ordinal, evidence, or operator fields, product
outcomes, duplicate recovery, and partially invalid batches fail closed without changing
ledger history.

The five resource types can be included in one resolved registry. Route,
infrastructure, product, and schema failures are typed and exit non-zero. None is
converted into a pass. A single candidate permits at most three product outcomes.

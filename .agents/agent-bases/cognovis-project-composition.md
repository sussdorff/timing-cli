---
name: cognovis-project-composition
version: "2026.08.21"
description: >-
  Project-local dependency bundle for Cognovis agent composition across supported
  Claude and Codex harnesses.
scope: project
harnesses: [claude-code, codex]
requires:
  - agent-base:claude-agent-base
  - agent-base:codex-agent-base
  - model-standard:fable
  - model-standard:gpt-5.6-luna
  - model-standard:gpt-5.6-sol
  - model-standard:haiku
  - model-standard:opus
  - model-standard:sonnet
---

# Cognovis Project Composition

This dependency-only base keeps every agent composition input inside the target
repository. Agents continue to select their own harness base and routed model
standard; this bundle only guarantees those inputs are installed.

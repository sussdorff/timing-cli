# Bead Hygiene Overlay — Dual-Source Test Project

> **Library defaults:** Universal rules are auto-loaded from the cognovis-core library default.
> This file contains only project-specific additions for the dual-source merge test.

## Pflichtfelder

- <!-- severity: critical -->Rollback plan required: every bead MUST include a section "## Rollback" describing how to revert the change if it causes a production issue. If no rollback is possible, write "Rollback: not possible — write a forward-fix bead instead."

## Anti-Patterns

- <!-- severity: major -->Hardcoded environment references: bead description or ACs reference a specific environment name (e.g. "auf staging testen", "in prod deployen") instead of abstracting by environment variable or deployment context.

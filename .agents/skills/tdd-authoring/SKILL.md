---
name: tdd-authoring
description: Author independent RED tests and tdd_evidence_v1 for one bead slice. Use tdd for method and implementation-loop for dispatch.
requires:
  - skill:tdd
requires_standards: [workflow, workflow/etl-development, dev-tools/tdd-real-fixture]
compatibility: {}
metadata: {}
---

# TDD Authoring

Cognovis contract for one RED slice. Load `tdd` for seams, anti-patterns, and
vertical slices. Do not rewrite that method here.

## Inputs

- Live bead, approved seams, declared test tree, and Given/Then pointers
  (adapter CLI `fixtures`, pinned IG, oracle, worked example).
- Changed paths for this slice (repo-relative or absolute inside the repo).

## Outputs

- Failing RED command, non-zero exit, and failure reason at the agreed seam.
- `tdd_evidence_v1` as in `references/tdd-evidence-v1.md`.

## Exclusions

- GREEN implementation, implementer test-tree edits, commit, push, Session Close.
- Computing Then the way the code would.

## Workflow

1. Agree seams. One vertical slice. Method: skill `tdd`.
2. Write the test only under the declared test tree. Each expected value names
   structured provenance in the test or docstring: fixture path + selector, IG
   canonical + element, oracle ledger ID, or worked-example pointer.
3. Resolve `verify_expected_sources.py` with
   `resolve_loop_skill.resolve_loop_script("verify_expected_sources.py")`.
   Fail with the probed paths if missing. Then
   `uv run python <resolved> verify --from-json <path-to-json> --repo-root . --test-tree <declared>`.
4. Call `tdd_loop_contract.classify_author_slice()` with `repo_root` and the
   declared test tree. Outside the tree is `contract_violation`, not RED.
5. Run the RED command. Record command, exit, reason, and provenance.

Harness sandboxes are workspace-wide. The classifier is the write bound.

## Do NOT

- Treat Pocock `tdd` as the evidence envelope or the test-tree classifier.
- Hardcode `skills/implementation-loop/scripts/...` as the only install path.

## Resources

| File | Purpose |
|------|---------|
| `references/tdd-evidence-v1.md` | Debrief envelope |
| `skill:tdd` | Seams, tautology, vertical slices |
| `implementation-loop` `verify_expected_sources.py` | Provenance VERIFY |
| `implementation-loop` `tdd_loop_contract.py` | Test-tree classifier |
| `implementation-loop` `resolve_loop_skill.py` | Installed skill-root probe |

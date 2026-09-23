---
name: implementation-loop
description: Implement one admitted hosted issue in its assigned worktree; the repository delivery owner handles admission and completion.
requires_standards: [executive-pack, workflow, dispatch/model-routing, review-governance, worktree-subagent-discipline]
requires:
  - agent:implementer
  - agent:tdd-test-author
  - agent:change-reviewer
  - skill:tdd-authoring
  - standard:executive-pack
  - standard:workflow
compatibility: {}
metadata: {}
action_boundary:
  risk_class: reversible-write
  effect_type: filesystem
  proposal_schema: standard://judge-layer/proposals/action-proposal.v1
  judge: agent://judge-default
  requires_mandate: false
---

# Implementation Loop

Execute one live hosted issue through the same repository delivery contract used by Solo and
Executive Pack modes. The invoking repository delivery owner never edits source. One
logical implementation owner remains responsible for all source and accepted repairs.
Its current writing session may be replaced only after the compact, clean committed
handoff defined by `executive-pack/references/compact-handoff.md`; the old session then
stops writing. The internal transition requires no human approval.

STATUS: BEHAVIORAL REVIEW POLICY. The initiating prompt owns the four-role paragraph
and review preset. `ccore agent` owns transport completion only; routing tables and
deterministic model-selection machinery do not participate.

## Shared implementation discipline

1. Read the live work order with `ccore tracker show`, plus repository
   instructions, applicable standards and ADRs. Derive
   the smallest approved public test seams from the Acceptance Criteria and MoC.
2. Work the seams RED first. Dispatch `tdd-test-author` once per Bead with every
   derived seam, in its own session (same family as the implementer is fine); it
   loads `tdd-authoring` and returns one `tdd_evidence_v1` covering all RED tests.
   Dispatch `implementer` to make them GREEN one vertical slice at a time
   without touching the declared test tree; the author then confirms the same
   commands in one closing turn. Do not dispatch a fresh author per slice.
   When TDD does not apply, state the reason in the same session and record
   focused evidence instead.
3. The implementation owner writes source and documentation, runs focused checks,
   and produces bead-labelled commits, including a clean handoff commit when a large
   bead needs a fresh session. It does not edit tests. The repository
   delivery owner sequences the work, assesses reviewer hypotheses against ground
   truth, and never repairs directly.
4. A provider failure or missing terminal answer returns control to the repository
   delivery owner as `review_infrastructure_unavailable`; it is never approval.

## TDD slice contract

Call `tdd_loop_contract.classify_author_slice()` on the author's changed paths
and `tdd_loop_contract.classify_implementer_slice()` on the implementer's.
Do NOT interpret the test-tree rule in prose. An author path outside the
declared test tree is `contract_violation`, not accepted RED. An implementer
path under the declared test tree is `contract_violation`, not GREEN. Call
`verify_expected_sources.verify_expected_values()` on every expected value the
author records. Tautological or relabeled Then values are rejected. Debrief
with `tdd_evidence_v1`: seams, slices, RED and GREEN commands, and the
independent source of every expected value.

RED/GREEN, focused MoC, and the bead commit remain behavior the sessions
perform and report. The two helpers classify contract violations only; they
are not a lifecycle state machine.

## Pack member

In `executive-pack` mode, final review belongs to the outer Pack workflow. After the
member implementation is ready, dispatch Reviewer 1 in a fresh context with the member
diff plus affected interactions, the live contract, relevant paths, and focused
evidence. Disable parent history inheritance; the listed paths seed inspection and do
not prevent the reviewer from following affected interactions elsewhere. Accepted
findings return to the logical implementation owner in its current
session. Once focused verification passes, advance without a full repair-confirmation
review; the final whole Pack perspectives observe the repair.

This loop is not the vehicle for post-review Pack repair convergence. Once the outer
Pack runs its final perspectives, accepted findings are cumulative closing bugfixes on
one existing candidate. Normal serial execution rotates once through the compact
committed handoff to a fresh repair session under the same logical owner; a Sub-Pack
keeps its fixed parent repair session. That one current repair implementer gets all
findings at once in the shared Pack worktree and owns its own tests and verification.
Do not re-enter this loop, dispatch `tdd-test-author`, or replay the member sequence.

## Simple Solo preset

Simple Solo uses Reviewer 1 for one complete review after implementation. Return
accepted findings to the same logical implementation owner and deliver the verified repair
without a full repair-confirmation review. Substantive disputes interrupt the delivery
owner; clean or Low/Nit-only output proceeds to focused MoC and commit.

## High-Assurance Solo preset

High-Assurance Solo uses the same repository delivery contract and implementation
owner. Reviewer 1 runs a complete adversarial pass, Reviewer 2 supplies a fresh
different-family critical perspective, and applicable security or project-specific
perspectives remain distinct. Consolidate accepted Medium-or-higher findings into one
implementation-owned repair lineage. A fresh session may continue it only through a
validated compact committed handoff. Do not insert redundant full reviews after repairs.
Interrupt only on disputed, contradictory, suspicious, or intent-mismatched findings.

## Completion

Declare implementation ready only once every derived seam has a recorded RED and a
recorded GREEN, or a stated non-TDD reason. Then rerun the focused Means of Compliance
named by the Bead and record one bead-labelled commit. Return TDD evidence, focused
verification, reviewer answers, repairs, and commit SHA to the repository delivery
owner. Review evidence remains private delivery evidence, not a Session Close input.

## Do not

- Create, switch, merge, remove, or share a worktree.
- Invoke Session Close, close an issue, push, inspect sibling Packs, or perform Topic Finalize.
- Let the repository delivery owner, a reviewer, or an evidence provider edit source.
- Re-enter this loop for post-review Pack repair convergence; those repairs go to one
  repair implementer holding every remaining finding at once.
- Reintroduce exact reviewer JSON, repair-confirmation choreography, or routing state.
- Reintroduce a state file or any other deterministic driver for RED/GREEN,
  focused MoC, or the bead commit. This loop is behavior, not a machine. The
  exception is test-tree and expected-source classification via
  `tdd_loop_contract.py` and `verify_expected_sources.py`.

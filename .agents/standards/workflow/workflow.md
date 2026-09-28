---
domain: workflow
description: The shared development workflow — hosted-issue intake and specification, review and verification discipline, engineering practice, and the cross-cutting rules that apply to every repository tracking work in hosted issues.
---

# Workflow Standards

> **Scope**: The end-to-end development workflow, from a raw request through a
> factory-ready work order, implementation, review, and closeout. Language-agnostic;
> applies to every repository that tracks work in hosted issues.

The orchestration itself is not described here. Authoring lives in the `intake`
skill, delivery from grilling to the merge decision and `session-retro` in the
`executive-pack` skill. This bundle holds the
standards those skills apply.

## Specification and Backlog

| File | Topic |
|------|-------|
| [issue-intake.md](issue-intake.md) | Hosted-issue body contract, library default rules plus the overlay format |
| [factory-ready.md](factory-ready.md) | The spec quality gate for autonomous execution |
| [triage-pattern.md](triage-pattern.md) | Routing raw input into keep, fold, weed, move, cluster |

## Review and Verification

| File | Topic |
|------|-------|
| [code-review.md](code-review.md) | Universal quality patterns a review looks for |
| [verification-discipline.md](verification-discipline.md) | Evidence over assertion; discharging Means of Compliance |
| [agent-quality-gates.md](agent-quality-gates.md) | The gates an agent must clear before reporting success |
| [test-quality.md](test-quality.md) | Universal testing principles |
| [tdd-discipline.md](tdd-discipline.md) | RED-GREEN-REFACTOR |

## Engineering Practice

| File | Topic |
|------|-------|
| [pragmatic-development.md](pragmatic-development.md) | Language-agnostic engineering principles |
| [systematic-debugging.md](systematic-debugging.md) | Root cause before fix |
| [git-best-practices.md](git-best-practices.md) | Branching, history, and worktree practice |
| [etl-development.md](etl-development.md) | Conventions for extract-transform-load work |
| [seed-data-parity.md](seed-data-parity.md) | Demo and seed data must match what live data looks like |

## Sessions and Feedback

| File | Topic |
|------|-------|
| [agent-session-capture.md](agent-session-capture.md) | What an agent records when a session closes |
| [production-feedback.md](production-feedback.md) | Signal classification and triage from production |
| [production-feedback-example.md](production-feedback-example.md) | A worked example of the feedback loop |
| [parameters.md](parameters.md) | The optional parameters array in workflow meta blocks |

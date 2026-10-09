# Scope-Creep Policy: Four-Tier Finding Dispatch

## Problem Statement

During issue implementation, reviewers and Codex adversarial checks surface findings that
were not part of the original issue's scope. Without a clear policy, agents tend to either:

- **Over-expand**: Fixing everything inline, turning a small issue into an unbounded refactor.
- **Over-defer**: Filing every observation as a new issue, creating orphaned follow-ups with
  no prose, no ACs, and no owner — notes masquerading as work items.

The four-tier policy eliminates ambiguity by giving every finding a deterministic dispatch action
based on measurable properties, with tier 2 (inline drive-by) as the default when ambiguous.

---

## Four-Tier Table

| Tier | Trigger | Action |
|------|---------|--------|
| **0 — Must inline** | Defect in THIS issue's diff; lint/type/test error in touched files; code that doesn't compile | **FIX INLINE** — non-negotiable |
| **1 — Should inline** | Called function has a bug making issue's behavior wrong; relied-on standard incomplete | **FIX INLINE** with scope expansion note |
| **2 — Default: inline drive-by** | Typo/formatting/dead code in touched files; stale comment; obvious <30 min cleanup | **DEFAULT INLINE**. Exception: >30 min OR >3 files outside diff → apply fit-first routing, then use `[DRIVE-BY]` only if no current/existing issue fits |
| **3 — Follow-up** | New bug class outside this issue's problem-space; refactor touching **>3 files OUTSIDE this issue's diff**; architectural decision needing an ADR | **APPLY FIT-FIRST ROUTING**. Expand current issue if it still fits; otherwise append/merge into an open issue; create `[DISCOVERED]` / `[ADR-NEEDED]` only with no-fit rationale |
| **4 — Note only** | Another repo's problem; trigger-less speculation ("might be nice someday" with no concrete driver) | **DO NOT FILE** — record in the landing note |

**Default tier when ambiguous: 2 (inline).**

---

## Fit-First Follow-Up Routing

Before creating any `[DISCOVERED]`, `[DRIVE-BY]`, or `[ADR-NEEDED]` issue, apply this routing
order. New issues are the last resort, not the default.

1. **Current issue expansion**
   Check whether the discovered work shares the same overarching intent, release unit,
   artifact or package, review path, UAT target, or acceptance evidence as the current issue.
   If yes, expand the current issue instead of splitting.
2. **Existing open issue append or merge**
   Search for same-repo candidates with `ccore tracker list --repo <owner/repo>` and the
   intake history helper (`issue_history.py "<title and goal>" --repo <owner/repo>`). Prefer
   appending to or merging into an existing issue when the intent, release artifact, version bump, publish action, review path, or UAT
   target matches.
3. **New issue only after no-fit proof**
   Create a new follow-up issue only after both checks fail. The new issue body MUST record:
   the discovered item, why the current issue does not fit, which candidate issue refs
   (`owner/repo#N`) were checked, and why none matched.

### Maximum-Useful-Size Principle

Prefer one larger issue over multiple tiny issues when the work still preserves one overarching
intent and one coherent review/UAT target. Split only when a shared review path breaks down,
ownership diverges, the release unit changes, or the work becomes too large for one autonomous
run.

---

## Scope Boundaries — When and What Counts as Inline

### The issue's scope window does not close at VERIFIED

A finding's tier is determined by its *content*, never by *which phase surfaced it*.
Cold review, Codex adversarial, and every post-verification check run INSIDE the
issue's scope window. A tier 0/1/2 finding surfaced after verification has
already returned VERIFIED is **still fixed inline** — VERIFIED is not a freeze line.

After applying a post-VERIFIED tier-2 fix, run a **targeted re-verification** covering
only the acceptance criteria whose files the fix touched (a focused re-check, not a
full re-run). Filing a tier-2 finding as a follow-up *because of when it was found* is
a policy violation, not a conservative choice.

### "Separate concern" is mechanical, not a judgement call

Tier 3's "separate concern" / "cross-cutting refactor" trigger is the most-abused
branch. Apply it mechanically:

- A refactor, helper extraction, or dedup whose duplicate sites are **all within the
  issue's own new or modified files** is **tier 2** — it serves the issue's own intent
  and is fixed inline. Extracting a shared loader from 5 scripts the issue just created
  is tier 2, not tier 3.
- A refactor is **tier 3** only if it touches **>3 files outside this issue's diff**
  (`git diff --name-only` membership is the test).
- "In scope" is judged against the issue's **stated Goal/title**, not against whether
  an individual acceptance criterion enumerated it. An issue titled "shared scripts"
  whose scripts each re-implement the same loader has an in-scope, in-intent
  improvement available — that is tier 2.

### Architectural decisions are filed, never evaporated

A finding that needs an architectural decision is **tier 3** — apply fit-first routing, and
only if no current/existing issue fits, create an `[ADR-NEEDED]` issue with the same no-fit
rationale and candidate-check record required for other follow-ups. It is NOT tier 4. Tier 4
("do not file") is reserved for another repo's problem and trigger-less speculation. An
ADR-worthy decision recorded only in a landing note is a lost decision.

---

## Classification Routine

> **Honest framing (clc-3jv retrospective; script retired in clc-rm0o):** The reviewing
> session applies this routine in prose by reading each finding and deciding the tier.
> There is **no runtime call** to a Python dispatcher, and no reference implementation
> ships any more.
>
> The pseudocode below is the specification, not a description of running code. It stays
> here because it pins the branch order — first match wins, no overlap, no unreachable
> branch, ambiguity falls through to tier 2.
>
> Wiring this to an algorithm would need an extractor that turns free text like
> `REGRESSION: file.py:42 — typo` into `caused_by_diff`, `estimated_loc`, and the rest —
> a second model round-trip per finding. Until something needs that, tier classification
> is a **prompt concern**, not an algorithm concern.

The orchestrator applies this routine to each finding before deciding dispatch action.
Order matters: the first matching condition wins.

```python
for finding in review_findings:
    if finding.caused_by_diff or finding.affects_issue_acs:
        tier = 0  # Must fix inline — defect caused by this issue's own changes
    elif finding.blocks_issue_close:
        tier = 1  # Should fix inline — dependency blocks issue completion
    elif (finding.estimated_loc < 30
          and finding.files_in_diff_scope
          and finding.estimated_minutes < 30):
        tier = 2  # Default inline drive-by — small, fast, in-scope
    elif finding.needs_adr:
        tier = 3  # Architectural decision — run fit-first, then [ADR-NEEDED] only if no issue fits
    elif finding.files_outside_diff_count > 3:
        tier = 3  # Genuinely cross-cutting — touches >3 files outside this issue's diff
    elif finding.is_separate_concern and finding.has_concrete_scope:
        tier = 3  # New problem space (is_separate_concern is mechanical — see Scope Boundaries)
    elif finding.is_observation and not finding.actionable_by_agent:
        tier = 4  # Note only — not actionable without human input
    else:
        tier = 2  # Default to inline when ambiguous
    dispatch_by_tier(tier, finding)
```

### Dispatch by Tier

| Tier | Action | Notes |
|------|--------|-------|
| 0 | Return the finding to the delivery's designated repair author immediately | Non-negotiable |
| 1 | Return the finding to the delivery's current repair author + add scope expansion note to issue | Document why scope grew |
| 2 | Fix inline (same repair pass and same repair author as tier 0/1) | Exception: if >30 min or >3 files outside diff, run fit-first routing first; use `[DRIVE-BY]` only when no existing issue fits |
| 3 | Run fit-first routing; create `[DISCOVERED]` / `[ADR-NEEDED]` only if both fit checks fail | Do NOT fix inline |
| 4 | Record in the landing note as "Observations (not filed)" | Do NOT file or fix |

---

## Validation Gates

These gates carry the policy; Gates 1 and 2 are scripted checks:

### Gate 1: Follow-up authoring (`issue-author-check.py`)

> **STATUS: policy.** AC/MoC completeness is the intake authoring check (`issue-author-check.py --body-file`) before
> `ccore tracker create`. Fit-first routing remains an orchestrator review contract; no
> claim-time gate enforces it.

Issues with restricted title prefixes (`[DISCOVERED]`, `[DRIVE-BY]`, `[ADR-NEEDED]`,
`[ENFORCER-*]`) MUST contain:

1. At least one `## Acceptance Criteria` or `## Means of Compliance` section in the body.
2. A fit-first routing record stating why the current issue did not fit, which candidate
   issue refs were checked, and why none matched.

**Why:** A `[DISCOVERED]`, `[DRIVE-BY]`, or `[ADR-NEEDED]` issue without ACs or no-fit rationale
is unfiled scope — it cannot be implemented, merged intelligently, or verified.

### Gate 2: Review Report Lint (`skills/review-conventions/scripts/contract_drift_lint.py`)

Contract Drift proposals in review reports MUST include a `(suggested-tier: N)` annotation.
The lint script detects:

1. Proposals missing `(suggested-tier: N)` → `POLICY_VIOLATION`
2. Auto-filed `ccore tracker create` calls in the report → `POLICY_VIOLATION`

Run via: `uv run python skills/review-conventions/scripts/contract_drift_lint.py < review_report.txt`

Exit 0 = clean. Exit 1 = violations found.

### Gate 3: Scope-Creep Soft Gate (delivery owner)

After verifying AKs, the delivery owner counts scope signals:
- `discovered_followups_filed`: count of `[DISCOVERED]` / `[DRIVE-BY]` / `[ADR-NEEDED]`
  issues filed during this session
- `inline_fixes_applied`: count of inline fix commits for review/Codex findings
  (counted as context, not as a trigger condition)

The gate fires when **`discovered_followups_filed >= 2`**. Two follow-ups per issue is
the backlog-treadmill threshold — at that point each filed follow-up must be
*justified*, not just counted. The old `AND inline_fixes_applied < 1` condition is
dropped: an issue can apply inline fixes AND still over-file, so the follow-up count
alone is the signal.

This is a **soft gate** — it does not block landing, but when it fires the orchestrator
MUST record, in the landing note, a one-line tier justification for EACH filed
follow-up, stating the mechanical reason it is not tier ≤2 (e.g. "tier 3: touches 7
files outside diff" or "tier 3: needs ADR"). A follow-up that cannot be given a clean
tier-≥3 justification was mis-tiered and must be fixed inline instead.

When a new issue is filed, the landing note must also record the fit-first routing decision:
the discovered item, current-issue fit result, candidate issue refs checked, append/merge
decision, and final action.

---

## Rationale: Why Default to Tier 2?

Tier 2 (inline drive-by) is the default because:

1. **Fixes compound.** A small typo or stale comment left untouched accumulates into technical
   debt. If it takes <30 min and is in the current diff scope, fixing it now is always cheaper.

2. **Follow-up issues have a filing cost.** Each `[DISCOVERED]` issue requires prose, ACs, MoC,
   a fit-first routing record, triage, and a future delivery. A 5-minute cleanup does not justify
   that overhead.

3. **Ambiguity should bias toward action.** When a reviewer cannot determine if a finding is
   in- or out-of-scope, treating it as tier 2 (fix inline) is the conservative choice that
   moves the codebase forward without filing orphaned issues.

4. **Useful size beats tiny shards.** When one review/UAT target still covers the work, a single
   larger issue is cheaper than several tiny issues with separate orchestration, review, and close
   cycles.

The threshold for upgrading from tier 2 to tier 3 is explicit: >30 min estimated effort
OR >3 files outside the diff scope. Below that threshold, fix inline.

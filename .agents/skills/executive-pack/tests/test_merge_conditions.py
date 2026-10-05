"""The merge gate requires a pr-agent review, not only a pr-agent classification."""

from __future__ import annotations

import re
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1] / "SKILL.md"
STANDARD = (
    Path(__file__).resolve().parents[3]
    / "standards"
    / "executive-pack"
    / "executive-pack.md"
)

REVIEW_MARKER = "## PR Reviewer Guide"
NOTICE_MARKER = "<!-- pr-agent-webhook:review-missing head=<sha> -->"


def _section(path: Path, heading: str) -> str:
    text = path.read_text(encoding="utf-8")
    start = text.index(f"\n{heading}\n")
    end = text.find("\n## ", start + len(heading) + 2)
    return text[start : end if end != -1 else len(text)]


def _bullets(section: str) -> list[str]:
    return [
        " ".join(item.split())
        for item in re.findall(r"^- (.*?)(?=^- |^\S|\Z)", section, re.M | re.S)
    ]


def test_step_7_requires_a_pr_agent_review_comment_as_its_own_condition() -> None:
    bullets = _bullets(_section(SKILL, "## 7. Merge decision"))
    review = [b for b in bullets if REVIEW_MARKER in b]
    assert len(review) == 1, "step 7 needs exactly one review-exists condition"
    condition = review[0]
    assert "cognovis-pr-agent" in condition
    assert "cognovis-atlas-pr-agent[bot]" in condition
    assert "classification" in condition, "must say a classification is not a review"
    assert "/review" in condition
    assert "missing pr-agent evidence" in condition


def test_step_7_answers_the_missing_review_notice_with_a_review_request() -> None:
    step_7 = " ".join(_section(SKILL, "## 7. Merge decision").split())
    assert NOTICE_MARKER in step_7
    notice = step_7[step_7.index(NOTICE_MARKER) :]
    assert "comments `/review`" in notice
    assert "once per notice" in notice
    assert "instead of merging" in notice
    assert "delivery request that invokes this skill authorizes" in notice
    assert "authorizes no other comment" in notice


def test_missing_review_notice_releases_once_a_later_review_exists() -> None:
    step_7 = " ".join(_section(SKILL, "## 7. Merge decision").split())
    notice = step_7[step_7.index(NOTICE_MARKER) :]
    assert (
        "holds the merge only while no pr-agent review comment was written or edited "
        "after it" in notice
    )
    assert "the notice no longer blocks" in notice
    assert "stays open for a human with the missing review as the reason" in notice


def test_pull_requests_without_a_work_order_keep_the_review_condition() -> None:
    section = _section(SKILL, "## Pull requests without a work order")
    still_holds = " ".join(section[section.index("Every other step 7 condition") :].split())
    assert "a pr-agent review comment exists on the pull request" in still_holds


def test_standard_boundaries_require_both_review_and_classification() -> None:
    bullets = _bullets(_section(STANDARD, "## Boundaries"))
    both = [
        b
        for b in bullets
        if "merge needs both" in b
        and "pr-agent review" in b
        and "classification of the current head" in b
    ]
    assert len(both) == 1

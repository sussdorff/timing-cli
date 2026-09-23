from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]


def test_regression_direct_review_prompt_is_complete_and_packet_launcher_is_gone() -> None:
    """Guard the incomplete packet contract that blocked the clc-2go8 review."""
    skill = (REPO_ROOT / "skills/bead-reviewer/SKILL.md").read_text(encoding="utf-8")
    agent = (REPO_ROOT / "agents/bead-spec-reviewer.md").read_text(encoding="utf-8")
    workflow = (REPO_ROOT / "workflows/bead-review.js").read_text(encoding="utf-8")

    assert "ccore agent" in skill
    assert "--permissions approve-reads" in skill
    assert "prepare_review_packet.py" not in skill
    assert "prepare_review_packet.py" not in agent
    assert "prepare_review_packet.py" not in workflow
    assert not (REPO_ROOT / "skills/bead-reviewer/scripts/prepare_review_packet.py").exists()
    assert not (REPO_ROOT / "skills/bead-reviewer/references/review-packet.schema.json").exists()

    for required_field in (
        '"bead_id"',
        '"profile"',
        '"reviewed_digest"',
        '"reviewer_sha"',
        '"contract_sha"',
        '"outcome"',
        '"unavailable_reason"',
        '"criteria"',
        '"findings"',
        '"recommended_change"',
    ):
        assert required_field in agent


def test_direct_reviewer_has_read_only_repository_capabilities() -> None:
    agent = (REPO_ROOT / "agents/bead-spec-reviewer.md").read_text(encoding="utf-8")

    assert "  - read_files" in agent
    assert "  - bash_read_only" in agent
    assert "  - inspect_git" in agent
    assert "Load the live Bead with `bd show" in agent
    assert "Never edit" in agent

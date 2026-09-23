from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]


def test_workflow_routes_through_manual_bead_reviewer_skill() -> None:
    content = (REPO_ROOT / "workflows" / "bead-review.js").read_text(encoding="utf-8")

    assert "SELF-HEAL" not in content
    assert "installed bead-reviewer skill" in content
    assert "prepare_review_packet.py" not in content
    assert "bd update" not in content
    assert "profile" in content
    assert '{ name: "targetRepo", type: "string", required: true' in content
    assert "target repository" in content
    assert 'enum: ["clean", "warnings", "blocked", "unavailable"]' in content
    assert "unavailable_reason" in content
    assert "bead review unavailable" in content


def test_skill_uses_direct_read_only_acpx_dispatch() -> None:
    content = (REPO_ROOT / "skills" / "bead-reviewer" / "SKILL.md").read_text(
        encoding="utf-8"
    )

    assert "ccore agent run" in content
    assert "compute_bead_content_sha.py" in content
    assert "--reviewer-agent-path" in content
    assert "contract_loader.py" in content
    assert "review_contract.py validate" in content
    assert "--permissions approve-reads" in content
    assert "prepare_review_packet.py" not in content
    assert "read-only" in content.lower()
    assert "model:" not in content
    assert len(content.splitlines()) < 120

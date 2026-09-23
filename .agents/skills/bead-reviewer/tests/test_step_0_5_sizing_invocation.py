from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]


def test_live_reviewer_has_no_sizing_step_or_classifier_dependency() -> None:
    content = (REPO_ROOT / "skills" / "bead-reviewer" / "SKILL.md").read_text(encoding="utf-8")

    assert "Step 0.5" not in content
    assert "classify_effort.py" not in content
    assert "effort" not in content.lower()
    assert "Profiles select criteria only" in content

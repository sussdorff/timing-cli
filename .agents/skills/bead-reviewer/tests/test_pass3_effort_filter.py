from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
HYGIENE = REPO_ROOT / "standards" / "workflow" / "bead-hygiene.md"
SKILL = REPO_ROOT / "skills" / "bead-reviewer" / "SKILL.md"
PARSER = REPO_ROOT / "skills" / "bead-reviewer" / "scripts" / "pass3_parser.py"


def test_effort_is_not_a_hygiene_or_review_axis() -> None:
    assert "<!-- effort:" not in HYGIENE.read_text(encoding="utf-8")
    assert "routed_effort" not in SKILL.read_text(encoding="utf-8")
    assert '"effort"' not in PARSER.read_text(encoding="utf-8")


def test_moc_applies_to_all_executable_spec_types() -> None:
    content = HYGIENE.read_text(encoding="utf-8")
    assert "<!-- types: feature,epic,task,bug -->MoC Table required:" in content
    assert "not a duration or size estimate" in content

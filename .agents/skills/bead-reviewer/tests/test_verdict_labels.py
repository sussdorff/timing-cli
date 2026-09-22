from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
BEAD_HYGIENE = REPO_ROOT / "standards" / "workflow" / "bead-hygiene.md"
SKILL = REPO_ROOT / "skills" / "bead-reviewer" / "SKILL.md"
GOLDEN_DIR = REPO_ROOT / "skills" / "bead-reviewer" / "tests" / "golden"


def test_promoted_rules_exist_in_shared_contract() -> None:
    content = BEAD_HYGIENE.read_text()

    for required_snippet in (
        "Clear Intent required:",
        "Outcome-Focused Acceptance Criteria required:",
        "## Intent block required:",
        "Cohesive Scope required:",
        "TITLE-PHASE:",
        "SCOPE-MULTI-CONCERN:",
    ):
        assert required_snippet in content, f"Shared contract is missing promoted rule: {required_snippet}"


def test_live_review_uses_typed_outcomes_instead_of_legacy_suffixes() -> None:
    skill_content = SKILL.read_text()

    assert "typed result" in skill_content
    assert "NEEDS_INTERACTIVE_WORK_CRITICAL_OVERLAY" not in skill_content
    assert "outcome" in (REPO_ROOT / "skills/bead-reviewer/references/review-contract.md").read_text()


def test_regression_fixtures_exist_for_type_and_moc_cases() -> None:
    fixture_dir = REPO_ROOT / "skills" / "bead-reviewer" / "tests" / "fixtures"

    for relative_path in (
        fixture_dir / "NLSpec-feature-missing.json",
        fixture_dir / "NLSpec-task-missing.json",
        fixture_dir / "MOC-chore-missing.json",
        GOLDEN_DIR / "NLSpec-feature-missing.md",
        GOLDEN_DIR / "NLSpec-task-missing.md",
        GOLDEN_DIR / "MOC-chore-missing.md",
        GOLDEN_DIR / "TITLE-PHASE-overlay.md",
    ):
        assert relative_path.exists(), f"Missing regression artifact: {relative_path}"

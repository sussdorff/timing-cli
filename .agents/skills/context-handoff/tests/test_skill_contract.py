from pathlib import Path

import yaml


SKILL_DIR = Path(__file__).parents[1]


def read_frontmatter(path: Path) -> dict[str, object]:
    contents = path.read_text()
    _, frontmatter, _ = contents.split("---", 2)
    return yaml.safe_load(frontmatter)


def test_skill_declares_routing_persistence_and_bootstrap_contracts() -> None:
    skill = (SKILL_DIR / "SKILL.md").read_text()
    frontmatter = read_frontmatter(SKILL_DIR / "SKILL.md")

    assert frontmatter["name"] == "context-handoff"
    assert frontmatter["action_boundary"] == {
        "risk_class": "external-side-effect",
        "effect_type": "network",
        "proposal_schema": "standard://judge-layer/proposals/action-proposal.v1",
        "judge": "agent://judge-default",
        "requires_mandate": True,
    }
    assert ".intake/context-handoff/<session-id>.md" in skill
    assert "Never select a Bead merely because it is claimed or in progress elsewhere" in skill
    assert "never substitute a timestamp or invented ID" in skill
    assert "Continuation Point" in skill
    assert "Do not create any other documentation file" in skill
    assert "bd note <id> --file <handoff-file>" in skill
    assert "append a clearly separated new `Context Handoff` section and preserve prior sections" in skill
    assert "Read <data.path> as context from the previous chat" in skill
    assert "Read the latest Context Handoff note on Bead <id> with bd show <id> --json" in skill
    assert "Call `/clear`, `/compact`" in skill
    assert "proceed only after `ALLOW`" in skill
    assert "worktree-local" in skill
    assert "uv run --no-project" in skill


def test_codex_metadata_keeps_the_skill_explicitly_invoked() -> None:
    metadata = yaml.safe_load((SKILL_DIR / "agents/openai.yaml").read_text())

    assert metadata["interface"]["default_prompt"].startswith("Use $context-handoff")
    assert metadata["policy"]["allow_implicit_invocation"] is False

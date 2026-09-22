"""Resolve implementation-loop scripts via canonical skill-root probe order."""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "resolve_loop_skill.py"


def _load():
    spec = importlib.util.spec_from_file_location("resolve_loop_skill", MODULE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_project_agents_skill_wins_over_marketplace_skills(tmp_path: Path) -> None:
    resolve = _load()
    agents = tmp_path / ".agents" / "skills" / "implementation-loop" / "scripts"
    marketplace = tmp_path / "skills" / "implementation-loop" / "scripts"
    agents.mkdir(parents=True)
    marketplace.mkdir(parents=True)
    (agents / "verify_expected_sources.py").write_text("# agents\n", encoding="utf-8")
    (marketplace / "verify_expected_sources.py").write_text("# marketplace\n", encoding="utf-8")
    found = resolve.resolve_loop_script(
        "verify_expected_sources.py", repo_root=tmp_path, home=tmp_path / "unused-home"
    )
    assert found == agents / "verify_expected_sources.py"


def test_missing_script_fails_with_probed_paths(tmp_path: Path) -> None:
    resolve = _load()
    try:
        resolve.resolve_loop_script(
            "verify_expected_sources.py", repo_root=tmp_path, home=tmp_path / "home"
        )
    except resolve.LoopSkillNotFound as exc:
        assert "probed" in str(exc).lower() or exc.probed_paths
        assert any(".agents/skills/implementation-loop" in path for path in exc.probed_paths)
        return
    raise AssertionError("expected LoopSkillNotFound")

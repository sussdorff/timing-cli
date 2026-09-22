from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "cognovis-beads.py"


def load_script():
    if not SCRIPT.is_file():
        pytest.fail(f"missing Cognovis Beads overlay provider: {SCRIPT}")
    spec = importlib.util.spec_from_file_location("cognovis_beads", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_context_is_sourced_from_the_cognovis_beads_skill() -> None:
    module = load_script()

    context = module.render_context()

    assert "# Cognovis Beads Overlay" in context
    assert "cognovis-beads.py" in context
    assert "bd dolt push --force" not in context

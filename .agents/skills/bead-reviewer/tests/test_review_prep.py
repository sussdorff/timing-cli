from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
MODULE = REPO_ROOT / "skills" / "bead-reviewer" / "scripts" / "review_prep.py"


def _module():
    spec = importlib.util.spec_from_file_location("review_prep", MODULE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_manual_request_returns_every_id_without_cache_decisions(tmp_path: Path) -> None:
    module = _module()

    result = module.review_prep(["clc-hit", "clc-miss"], tmp_path, profile="repository")

    assert result["skip"] == []
    assert result["review"] == [
        {"beadId": "clc-hit", "profile": "repository"},
        {"beadId": "clc-miss", "profile": "repository"},
    ]
    assert "packet" not in str(result).lower()
    assert "description" not in str(result).lower()


def test_legacy_force_flag_does_not_change_manual_review(tmp_path: Path) -> None:
    module = _module()

    result = module.review_prep(["clc-live", "clc-broken"], tmp_path, force=True)

    assert result["skip"] == []
    assert result["review"] == [
        {"beadId": "clc-live", "profile": "full"},
        {"beadId": "clc-broken", "profile": "full"},
    ]

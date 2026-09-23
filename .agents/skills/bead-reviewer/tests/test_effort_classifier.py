from __future__ import annotations

import importlib.util
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
AGENT = REPO_ROOT / "agents" / "effort-classifier.md"
SCRIPT = REPO_ROOT / "skills" / "executive-pack" / "scripts" / "classify_effort.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("classify_effort", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_agent_spec_declares_required_json_contract() -> None:
    content = AGENT.read_text(encoding="utf-8")

    assert "routed_effort" in content
    assert "routed_reason" in content
    assert "classifier" in content
    assert "version" in content
    assert "MUST NOT emit duration-language" in content
    assert "files" in content
    assert "surfaces" in content
    assert "tests" in content


def test_agent_spec_declares_determinism_guarantee() -> None:
    """AK-7: the classifier prompt header must state the cache determinism contract."""
    content = AGENT.read_text(encoding="utf-8")

    assert "Determinism Guarantee" in content
    assert "deterministic function of the input bead payload" in content
    assert "same input fields produce the same `routed_effort`" in content
    assert "stochastic" in content.lower() or "non-deterministic" in content.lower()


def test_validate_classifier_payload_sanitizes_duration_language() -> None:
    # CL-9ith: routed_reason is advisory prose; duration words are stripped
    # (not hard-failed) so a chatty LLM classifier can't abort phase0. The
    # non-prose fields still reject duration language. Mirrors the canonical
    # test in skills/executive-pack/tests/test_classify_effort.py.
    module = _load_module()

    valid = {
        "routed_effort": "medium",
        "routed_reason": "4 files, 2 surfaces, 3 tests touched",
        "classifier": "haiku-test",
        "version": "1",
    }
    assert module.validate_classifier_payload(valid) == valid

    sanitized = module.validate_classifier_payload(
        {
            "routed_effort": "small",
            "routed_reason": "about 2 hours for 1 file",
            "classifier": "haiku-test",
            "version": "1",
        }
    )
    assert sanitized["routed_effort"] == "small"
    assert "hours" not in sanitized["routed_reason"].lower()
    assert sanitized["routed_reason"]  # non-empty after stripping

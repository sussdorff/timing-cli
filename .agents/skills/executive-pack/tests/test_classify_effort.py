from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from unittest.mock import patch

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "classify_effort.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("classify_effort", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _result(stdout: str, *, returncode: int = 0, stderr: str = ""):
    return type(
        "CompletedProcess",
        (),
        {"stdout": stdout, "stderr": stderr, "returncode": returncode},
    )()


def test_writes_metadata_routing_and_prints_stdout_json(capsys, monkeypatch) -> None:
    module = _load_module()
    bead = [
        {
            "id": "clc-test",
            "title": "[ORCH] Route by derived effort",
            "description": "## Intent\nGoal: derive effort\nScope-In: wrapper\nScope-Out: migration",
            "acceptance_criteria": "- AK-1: metadata.routing updated",
            "issue_type": "task",
        }
    ]
    payload = {
        "routed_effort": "medium",
        "routed_reason": "4 files, 2 surfaces, 3 tests touched",
        "classifier": "haiku-test",
        "version": "1",
    }
    calls: list[list[str]] = []
    monkeypatch.setenv("EFFORT_CLASSIFIER_CMD", "classifier-bin --json")

    def fake_run(args, capture_output=True, text=True, check=False, input=None):
        calls.append(list(args))
        if args[:4] == ["bd", "show", "clc-test", "--json"]:
            return _result(json.dumps(bead))
        if args[:2] == ["classifier-bin", "--json"]:
            return _result(json.dumps(payload))
        if args[:3] == ["bd", "update", "clc-test"]:
            return _result("")
        raise AssertionError(f"unexpected command: {args}")

    with patch.object(module.subprocess, "run", side_effect=fake_run):
        assert module.main(["clc-test"]) == 0

    stdout = capsys.readouterr().out.strip()
    assert json.loads(stdout) == payload
    update_call = next(args for args in calls if args[:3] == ["bd", "update", "clc-test"])
    assert "--metadata" in update_call
    metadata_index = update_call.index("--metadata")
    metadata_json = json.loads(update_call[metadata_index + 1])
    assert metadata_json == {
        "routing": {
            "routed_effort": "medium",
            "routed_reason": "4 files, 2 surfaces, 3 tests touched",
            "classifier": "haiku-test",
            "version": "1",
            "input_hash": module.compute_input_hash(bead[0]),
            "cache_version": module.CACHE_VERSION,
        }
    }
    assert "--set-metadata" not in update_call


def test_parse_classifier_output_extracts_routing_from_codex_jsonl() -> None:
    """`codex exec --json` emits event objects, not the routing payload directly.

    The classifier's structured JSON lives inside the `item.text` of an
    `item.completed` event whose `item.type` is `agent_message`. The parser
    must dig the routing object out of that text and ignore turn.started /
    item.completed reasoning / turn.completed events.
    """
    module = _load_module()
    routing_payload = {
        "routed_effort": "medium",
        "routed_reason": "4 files, 2 surfaces, 3 tests touched",
        "classifier": "codex-test",
        "version": "1",
    }
    jsonl_stream = "\n".join(
        [
            json.dumps({"type": "thread.started", "thread_id": "t-1"}),
            json.dumps({"type": "turn.started"}),
            json.dumps(
                {
                    "type": "item.completed",
                    "item": {"id": "i_0", "type": "reasoning", "text": "thinking..."},
                }
            ),
            json.dumps(
                {
                    "type": "item.completed",
                    "item": {
                        "id": "i_1",
                        "type": "agent_message",
                        "text": json.dumps(routing_payload),
                    },
                }
            ),
            json.dumps({"type": "turn.completed", "usage": {"input_tokens": 1, "output_tokens": 2}}),
        ]
    )

    parsed = module.parse_classifier_output(jsonl_stream)
    assert parsed == routing_payload


def test_parse_classifier_output_extracts_routing_from_agent_message_with_prose() -> None:
    """Agent messages sometimes wrap the routing JSON in surrounding prose;
    the parser must locate the embedded JSON object inside item.text."""
    module = _load_module()
    routing_payload = {
        "routed_effort": "small",
        "routed_reason": "single-file change",
        "classifier": "codex-test",
        "version": "1",
    }
    wrapped = (
        "Here is the classification result:\n\n"
        f"{json.dumps(routing_payload)}\n\n"
        "End of message."
    )
    jsonl_stream = "\n".join(
        [
            json.dumps({"type": "turn.started"}),
            json.dumps(
                {
                    "type": "item.completed",
                    "item": {"id": "i_1", "type": "agent_message", "text": wrapped},
                }
            ),
            json.dumps({"type": "turn.completed"}),
        ]
    )

    parsed = module.parse_classifier_output(jsonl_stream)
    assert parsed == routing_payload


def test_parse_classifier_output_accepts_bare_json_object() -> None:
    """Direct JSON output (legacy classifiers / EFFORT_CLASSIFIER_CMD overrides
    that emit a bare JSON document) must still parse correctly."""
    module = _load_module()
    routing_payload = {
        "routed_effort": "large",
        "routed_reason": "multi-surface",
        "classifier": "haiku",
        "version": "1",
    }
    parsed = module.parse_classifier_output(json.dumps(routing_payload))
    assert parsed == routing_payload


def test_codex_jsonl_integration_writes_metadata(capsys, monkeypatch) -> None:
    """End-to-end: default `codex exec --json` style output flows through
    classify_effort.main() and lands in bd metadata correctly."""
    module = _load_module()
    bead = [
        {
            "id": "clc-jsonl",
            "title": "Route by derived effort",
            "description": "x",
            "acceptance_criteria": "",
            "issue_type": "task",
        }
    ]
    routing_payload = {
        "routed_effort": "medium",
        "routed_reason": "4 files, 2 surfaces, 3 tests touched",
        "classifier": "codex-test",
        "version": "1",
    }
    jsonl_stream = "\n".join(
        [
            json.dumps({"type": "turn.started"}),
            json.dumps(
                {
                    "type": "item.completed",
                    "item": {
                        "id": "i_1",
                        "type": "agent_message",
                        "text": json.dumps(routing_payload),
                    },
                }
            ),
            json.dumps({"type": "turn.completed"}),
        ]
    )

    calls: list[list[str]] = []
    # Force the default codex command path
    monkeypatch.delenv("EFFORT_CLASSIFIER_CMD", raising=False)

    def fake_run(args, capture_output=True, text=True, check=False, input=None):
        calls.append(list(args))
        if args[:4] == ["bd", "show", "clc-jsonl", "--json"]:
            return _result(json.dumps(bead))
        if args[:3] == ["codex", "exec", "--json"]:
            return _result(jsonl_stream)
        if args[:3] == ["bd", "update", "clc-jsonl"]:
            return _result("")
        raise AssertionError(f"unexpected command: {args}")

    with patch.object(module.subprocess, "run", side_effect=fake_run):
        assert module.main(["clc-jsonl"]) == 0

    stdout = capsys.readouterr().out.strip()
    assert json.loads(stdout) == routing_payload
    update_call = next(args for args in calls if args[:3] == ["bd", "update", "clc-jsonl"])
    metadata_index = update_call.index("--metadata")
    metadata_json = json.loads(update_call[metadata_index + 1])
    assert metadata_json == {
        "routing": {
            **routing_payload,
            "input_hash": module.compute_input_hash(bead[0]),
            "cache_version": module.CACHE_VERSION,
        }
    }


def test_duration_language_sanitized_not_rejected(monkeypatch) -> None:
    # CL-9ith: a classifier that puts duration words in routed_reason must NOT
    # hard-fail phase0. The reason is sanitized (duration words stripped) and
    # metadata is still written with the valid routed_effort.
    module = _load_module()
    bead = [{"id": "clc-test", "title": "Title", "description": "Desc", "acceptance_criteria": ""}]
    calls: list[list[str]] = []
    monkeypatch.setenv("EFFORT_CLASSIFIER_CMD", "classifier-bin --json")

    def fake_run(args, capture_output=True, text=True, check=False, input=None):
        calls.append(list(args))
        if args[:4] == ["bd", "show", "clc-test", "--json"]:
            return _result(json.dumps(bead))
        if args[:2] == ["classifier-bin", "--json"]:
            return _result(
                json.dumps(
                    {
                        "routed_effort": "small",
                        "routed_reason": "about 30 minutes for 1 file",
                        "classifier": "haiku-test",
                        "version": "1",
                    }
                )
            )
        if args[:3] == ["bd", "update", "clc-test"]:
            return _result("")
        raise AssertionError(f"unexpected command: {args}")

    with patch.object(module.subprocess, "run", side_effect=fake_run):
        rc = module.main(["clc-test"])

    assert not rc
    update_calls = [args for args in calls if args[:3] == ["bd", "update", "clc-test"]]
    assert update_calls, "metadata must still be written after sanitization"
    written = " ".join(update_calls[0]).lower()
    assert "minutes" not in written
    assert "small" in written


def test_validate_classifier_payload_sanitizes_duration_reason() -> None:
    # Unit: routed_reason duration words are stripped; routed_effort is preserved.
    module = _load_module()
    out = module.validate_classifier_payload(
        {
            "routed_effort": "small",
            "routed_reason": "2 files, ~3 hours of work, 1 test",
            "classifier": "haiku-test",
            "version": "1",
        }
    )
    assert out["routed_effort"] == "small"
    assert "hours" not in out["routed_reason"].lower()
    assert "files" in out["routed_reason"]


def test_validate_classifier_payload_still_rejects_invalid_effort() -> None:
    module = _load_module()
    with pytest.raises(ValueError, match="invalid routed_effort"):
        module.validate_classifier_payload(
            {
                "routed_effort": "enormous",
                "routed_reason": "scope only",
                "classifier": "haiku-test",
                "version": "1",
            }
        )


# ---------------------------------------------------------------------------
# Content-hash cache (skip re-classification when bead input unchanged)
# ---------------------------------------------------------------------------


def _bead_with_cached_routing(module, *, valid: bool = True, version_ok: bool = True):
    """Build a bead dict whose metadata.routing is a cache entry.

    valid=False  -> stored input_hash no longer matches the bead content.
    version_ok=False -> stored cache_version differs from CACHE_VERSION.
    """
    content = {
        "id": "clc-cache",
        "title": "Cached bead",
        "description": "stable description",
        "acceptance_criteria": "- AK-1: x",
        "issue_type": "task",
    }
    routing = {
        "routed_effort": "small",
        "routed_reason": "1 file, 1 surface, 1 test",
        "classifier": "haiku-cached",
        "version": "1",
        "input_hash": module.compute_input_hash(content) if valid else "stale-hash-0000",
        "cache_version": module.CACHE_VERSION if version_ok else module.CACHE_VERSION + 99,
    }
    return {**content, "metadata": {"routing": routing}}


def test_cache_hit_skips_classifier_and_metadata_write(capsys, monkeypatch) -> None:
    """A bead whose stored input_hash + cache_version match must NOT invoke
    the classifier and must NOT write metadata — only `bd show` runs."""
    module = _load_module()
    bead = _bead_with_cached_routing(module)
    monkeypatch.setenv("EFFORT_CLASSIFIER_CMD", "classifier-bin --json")
    calls: list[list[str]] = []

    def fake_run(args, capture_output=True, text=True, check=False, input=None):
        calls.append(list(args))
        if args[:4] == ["bd", "show", "clc-cache", "--json"]:
            return _result(json.dumps([bead]))
        raise AssertionError(f"cache hit must not run: {args}")

    with patch.object(module.subprocess, "run", side_effect=fake_run):
        assert module.main(["clc-cache"]) == 0

    stdout = capsys.readouterr().out.strip()
    assert json.loads(stdout) == {
        "routed_effort": "small",
        "routed_reason": "1 file, 1 surface, 1 test",
        "classifier": "haiku-cached",
        "version": "1",
    }
    assert calls == [["bd", "show", "clc-cache", "--json"]]


def test_cache_miss_on_content_change_invokes_classifier(monkeypatch) -> None:
    """A stored input_hash that no longer matches the bead content is a miss."""
    module = _load_module()
    bead = _bead_with_cached_routing(module, valid=False)
    fresh = {
        "routed_effort": "large",
        "routed_reason": "5 files, 3 surfaces, 4 tests",
        "classifier": "haiku-fresh",
        "version": "1",
    }
    monkeypatch.setenv("EFFORT_CLASSIFIER_CMD", "classifier-bin --json")
    calls: list[list[str]] = []

    def fake_run(args, capture_output=True, text=True, check=False, input=None):
        calls.append(list(args))
        if args[:4] == ["bd", "show", "clc-cache", "--json"]:
            return _result(json.dumps([bead]))
        if args[:2] == ["classifier-bin", "--json"]:
            return _result(json.dumps(fresh))
        if args[:3] == ["bd", "update", "clc-cache"]:
            return _result("")
        raise AssertionError(f"unexpected command: {args}")

    with patch.object(module.subprocess, "run", side_effect=fake_run):
        assert module.main(["clc-cache"]) == 0

    assert any(args[:2] == ["classifier-bin", "--json"] for args in calls)
    assert any(args[:3] == ["bd", "update", "clc-cache"] for args in calls)


def test_cache_miss_on_version_bump_invokes_classifier(monkeypatch) -> None:
    """A matching input_hash but a stale cache_version is a miss."""
    module = _load_module()
    bead = _bead_with_cached_routing(module, version_ok=False)
    fresh = {
        "routed_effort": "medium",
        "routed_reason": "3 files, 2 surfaces, 2 tests",
        "classifier": "haiku-fresh",
        "version": "1",
    }
    monkeypatch.setenv("EFFORT_CLASSIFIER_CMD", "classifier-bin --json")
    calls: list[list[str]] = []

    def fake_run(args, capture_output=True, text=True, check=False, input=None):
        calls.append(list(args))
        if args[:4] == ["bd", "show", "clc-cache", "--json"]:
            return _result(json.dumps([bead]))
        if args[:2] == ["classifier-bin", "--json"]:
            return _result(json.dumps(fresh))
        if args[:3] == ["bd", "update", "clc-cache"]:
            return _result("")
        raise AssertionError(f"unexpected command: {args}")

    with patch.object(module.subprocess, "run", side_effect=fake_run):
        assert module.main(["clc-cache"]) == 0

    assert any(args[:2] == ["classifier-bin", "--json"] for args in calls)


def test_force_bypasses_valid_cache(monkeypatch) -> None:
    """--force re-classifies even when the stored cache is valid."""
    module = _load_module()
    bead = _bead_with_cached_routing(module)  # valid cache entry
    fresh = {
        "routed_effort": "xl",
        "routed_reason": "8 files, 4 surfaces, 6 tests",
        "classifier": "haiku-fresh",
        "version": "1",
    }
    monkeypatch.setenv("EFFORT_CLASSIFIER_CMD", "classifier-bin --json")
    calls: list[list[str]] = []

    def fake_run(args, capture_output=True, text=True, check=False, input=None):
        calls.append(list(args))
        if args[:4] == ["bd", "show", "clc-cache", "--json"]:
            return _result(json.dumps([bead]))
        if args[:2] == ["classifier-bin", "--json"]:
            return _result(json.dumps(fresh))
        if args[:3] == ["bd", "update", "clc-cache"]:
            return _result("")
        raise AssertionError(f"unexpected command: {args}")

    with patch.object(module.subprocess, "run", side_effect=fake_run):
        assert module.main(["clc-cache", "--force"]) == 0

    assert any(args[:2] == ["classifier-bin", "--json"] for args in calls)
    assert any(args[:3] == ["bd", "update", "clc-cache"] for args in calls)


def test_compute_input_hash_ignores_metadata_routing(monkeypatch) -> None:
    """The hash must not change when only metadata.routing.* changes — that is
    what makes the cache stable across classify_effort's own writes."""
    module = _load_module()
    base = {
        "id": "clc-h",
        "title": "T",
        "description": "D",
        "acceptance_criteria": "A",
        "issue_type": "task",
    }
    with_routing = {
        **base,
        "metadata": {"routing": {"routed_effort": "large", "input_hash": "x"}},
    }
    assert module.compute_input_hash(base) == module.compute_input_hash(with_routing)


def test_load_agent_spec_returns_contract_body() -> None:
    """load_agent_spec finds the bundled spec and returns its full text."""
    module = _load_module()
    spec = module.load_agent_spec()
    assert "# Effort Classifier" in spec
    assert "routed_effort" in spec
    assert "name: effort-classifier" in spec


def test_build_prompt_embeds_spec_and_omits_path_reference() -> None:
    """The prompt must inline the agent contract verbatim and never instruct
    codex to "follow the agent contract in <path>" -- the path form is what
    triggered the unbounded `find /Users/<user>` home-directory scan."""
    module = _load_module()
    prompt = module.build_prompt(
        {
            "id": "clc-x",
            "title": "T",
            "issue_type": "task",
            "description": "D",
            "acceptance_criteria": "A",
        }
    )
    assert "=== BEGIN effort-classifier agent contract ===" in prompt
    assert "=== END effort-classifier agent contract ===" in prompt
    assert "# Effort Classifier" in prompt
    # The pre-fix prompt phrasing must not return. Both the literal trigger
    # and any absolute path to an effort-classifier .md/.toml file are banned.
    assert "Follow the agent contract in /" not in prompt
    assert "effort-classifier.md" not in prompt or "name: effort-classifier" in prompt
    assert "effort-classifier.toml" not in prompt


def test_bundled_spec_matches_marketplace_agent_when_both_present() -> None:
    """Drift guard: inside the cognovis-core checkout, the bundled copy of
    effort-classifier.md inside the executive-pack skill must stay byte-identical to
    the marketplace agent at agents/effort-classifier.md. The skill-bundled
    copy is what travels to consumers via `/library skill use beads`; the
    marketplace copy is the fleet agent. Both files have the same content;
    drift would mean codex classifies beads against one contract while the
    fleet documents another."""
    tests_dir = Path(__file__).resolve().parent
    bundled = tests_dir.parents[1] / "references" / "effort-classifier.md"
    marketplace = tests_dir.parents[3] / "agents" / "effort-classifier.md"
    if not marketplace.is_file():
        pytest.skip("marketplace agents/effort-classifier.md absent (standalone install)")
    assert bundled.is_file(), f"bundled spec missing at {bundled}"
    assert bundled.read_bytes() == marketplace.read_bytes(), (
        f"drift between {bundled} and {marketplace} -- keep them in sync"
    )

from __future__ import annotations

import ast
import importlib.util
import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest


_TESTS_DIR = Path(__file__).resolve().parent
_SKILL_ROOT = _TESTS_DIR.parent
_REPO_ROOT = _SKILL_ROOT.parents[1]

_CONTEXT_DISCOVERY_PATH = _SKILL_ROOT / "scripts" / "context_discovery.py"
_CONTEXT_PROVIDER_PATH = (
    _REPO_ROOT / "skills" / "context-discovery" / "scripts" / "context_provider.py"
)


def _install_project_provider(repo_root: Path, tree: str = "skills") -> Path:
    """Install the read-only provider as a repository-local test fixture."""
    destination = repo_root / tree / "context-discovery" / "scripts"
    destination.mkdir(parents=True, exist_ok=True)
    shutil.copy2(_CONTEXT_PROVIDER_PATH, destination / "context_provider.py")
    shutil.copy2(_SKILL_ROOT / "scripts" / "adr-context.py", destination / "adr-context.py")
    return destination / "context_provider.py"

def _bead_context_provider_arg() -> str:
    """Return the ``provider=`` literal a bead context bundle is built with.

    This used to be derived by parsing the deterministic loop state machine,
    which was the only other caller. That machine is gone (clc-rm0o), so the
    literal is pinned here and read back out of ``context_discovery.py``'s own
    source below -- the assertion that still earns its keep is that the script
    passes this value, not that two copies of it agree.
    """
    tree = ast.parse(_CONTEXT_DISCOVERY_PATH.read_text(encoding="utf-8"))
    for call in ast.walk(tree):
        if (
            isinstance(call, ast.Call)
            and isinstance(call.func, ast.Attribute)
            and call.func.attr == "build_context_bundle"
        ):
            for keyword in call.keywords:
                if keyword.arg == "provider" and isinstance(
                    keyword.value, ast.Constant
                ):
                    return str(keyword.value.value)
    raise AssertionError(
        "could not find the provider= argument in context_discovery.py's "
        "build_context_bundle call"
    )


def _load_module(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def context_discovery() -> Any:
    return _load_module(_CONTEXT_DISCOVERY_PATH, "context_discovery_under_test")


@pytest.fixture()
def context_provider() -> Any:
    return _load_module(_CONTEXT_PROVIDER_PATH, "context_provider_under_test")


def _write_adr(
    root: Path,
    *,
    adr_id: str = "ADR-057",
    selector: str = "src/service.py",
) -> Path:
    path = root / "docs" / "adr" / f"{adr_id}-binding.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"""---
id: {adr_id}
applies_to:
  - {selector}
decision_summary: "Service bindings remain explicit."
prohibits:
  - "Do not hide binding data."
---

# {adr_id}
""",
        encoding="utf-8",
    )
    return path


def _snapshot(*roots: Path) -> set[str]:
    files: set[str] = set()
    for root in roots:
        if not root.exists():
            continue
        for dirpath, _dirnames, filenames in os.walk(root):
            for filename in filenames:
                files.add(str(Path(dirpath) / filename))
    return files


# ---------------------------------------------------------------------------
# Path-scoped mode
# ---------------------------------------------------------------------------


def test_path_scoped_discovery_with_adr_corpus_returns_deterministic_manifest(
    tmp_path: Path, context_discovery: Any
) -> None:
    _install_project_provider(tmp_path)
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "service.py").write_text("def handle():\n    return True\n")
    _write_adr(tmp_path, adr_id="ADR-057", selector="src/service.py")

    candidate_paths = ["src/service.py"]
    first = context_discovery.discover_path_scoped(tmp_path, candidate_paths)
    second = context_discovery.discover_path_scoped(tmp_path, candidate_paths)

    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)
    assert first["mode"] == "path-scoped"
    assert first["candidate_surface"] == ["src/service.py"]

    adr_context = first["adr_context"]
    assert adr_context["status"] == "complete"
    assert adr_context["gaps"] == []
    manifest_ids = [entry["id"] for entry in adr_context["manifest"]]
    assert "ADR-057" in manifest_ids
    matched = next(entry for entry in adr_context["manifest"] if entry["id"] == "ADR-057")
    assert any(reason.startswith("path:") for reason in matched["match_reasons"])


def test_path_scoped_discovery_without_adr_corpus_returns_typed_gap_not_exception(
    tmp_path: Path, context_discovery: Any
) -> None:
    _install_project_provider(tmp_path)
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "service.py").write_text("def handle():\n    return True\n")

    result = context_discovery.discover_path_scoped(tmp_path, ["src/service.py"])

    adr_context = result["adr_context"]
    assert adr_context["status"] == "gap"
    assert adr_context["manifest"] == []
    assert len(adr_context["gaps"]) == 1
    gap = adr_context["gaps"][0]
    assert gap["code"] == "ADR_CORPUS_NOT_FOUND"
    assert gap["resolved"] is True


def test_path_scoped_discovery_via_cli_prints_one_json_object(
    tmp_path: Path, context_discovery: Any, capsys: pytest.CaptureFixture[str]
) -> None:
    _install_project_provider(tmp_path)
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "service.py").write_text("def handle():\n    return True\n")

    exit_code = context_discovery.main(
        [
            "path-scoped",
            "--repo-root",
            str(tmp_path),
            "--candidate-path",
            "src/service.py",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert captured.err == ""
    lines = [line for line in captured.out.splitlines() if line.strip()]
    assert len(lines) == 1
    payload = json.loads(lines[0])
    assert payload["mode"] == "path-scoped"


def test_path_scoped_discovery_via_stdin_request(
    tmp_path: Path, context_discovery: Any, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_project_provider(tmp_path)
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "service.py").write_text("def handle():\n    return True\n")

    import io

    request = json.dumps(
        {"candidate_paths": ["src/service.py"], "repo_root": str(tmp_path)}
    )
    monkeypatch.setattr("sys.stdin", io.StringIO(request))

    exit_code = context_discovery.main(["path-scoped", "--request-stdin"])
    captured = capsys.readouterr()

    assert exit_code == 0
    payload = json.loads(captured.out.strip())
    assert payload["candidate_surface"] == ["src/service.py"]


# ---------------------------------------------------------------------------
# Bead-scoped mode
# ---------------------------------------------------------------------------


def _fixture_bead() -> dict[str, Any]:
    return {
        "id": "clc-test",
        "title": "Test bead",
        "description": (
            "Implement order handling.\n\n"
            "## Context Pointers\n"
            "primary_files:\n"
            "  - src/service.py\n"
            "test_files:\n"
            "  - tests/test_service.py\n"
            "symbols:\n"
            "  - handle_order\n"
        ),
        "acceptance_criteria": "",
        "metadata": {},
    }


def test_bead_scoped_discovery_equals_direct_provider_call(
    tmp_path: Path, context_discovery: Any
) -> None:
    _install_project_provider(tmp_path)
    (tmp_path / "src").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / "src" / "service.py").write_text("def handle_order():\n    return True\n")
    (tmp_path / "tests" / "test_service.py").write_text(
        "def test_handle_order():\n    assert handle_order()\n"
    )

    bead = _fixture_bead()
    bead_json_path = tmp_path / "bead.json"
    bead_json_path.write_text(json.dumps(bead), encoding="utf-8")

    via_script = context_discovery.discover_bead_scoped(
        tmp_path,
        bead_id="",
        bead_json=bead_json_path,
        timeout=8,
    )
    expected_provider = _bead_context_provider_arg()
    assert expected_provider == "fallback"
    direct = context_discovery.load_context_provider(tmp_path).build_context_bundle(
        bead,
        tmp_path,
        provider=expected_provider,
        cbm_command="codebase-memory-mcp",
        timeout=8,
        allow_index=False,
    )

    assert json.dumps(via_script, sort_keys=True) == json.dumps(direct, sort_keys=True)


def test_load_bead_for_discovery_passes_repo_root_as_cwd_to_bd_show(
    tmp_path: Path, context_discovery: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``bd show`` must resolve against ``--repo-root``, not the process cwd.

    Regression test: without ``cwd=repo_root``, a bead-scoped request against
    a different repository than the one this script happens to be invoked
    from would silently query the wrong Beads database. `bd` itself is not
    exercised here (its resolution behavior is `bd`'s own concern); this only
    asserts that ``load_bead_for_discovery`` passes the caller-supplied
    ``repo_root`` as ``cwd``.
    """
    repo_root = tmp_path / "target-repo"
    other_cwd = tmp_path / "unrelated-process-cwd"
    repo_root.mkdir()
    other_cwd.mkdir()
    captured: dict[str, Any] = {}

    def fake_run(args: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        captured["args"] = args
        captured["cwd"] = kwargs.get("cwd")
        return subprocess.CompletedProcess(
            args=args, returncode=0, stdout=json.dumps(_fixture_bead()), stderr=""
        )

    monkeypatch.setattr(context_discovery.subprocess, "run", fake_run)
    monkeypatch.chdir(other_cwd)

    bead = context_discovery.load_bead_for_discovery("clc-test", None, 8, repo_root)

    assert captured["args"][:3] == ["bd", "show", "clc-test"]
    assert captured["cwd"] == repo_root
    assert captured["cwd"] != other_cwd
    assert bead["id"] == "clc-test"


def test_bead_scoped_discovery_via_cli_prints_one_json_object(
    tmp_path: Path, context_discovery: Any, capsys: pytest.CaptureFixture[str]
) -> None:
    _install_project_provider(tmp_path)
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "service.py").write_text("def handle_order():\n    return True\n")
    bead_json_path = tmp_path / "bead.json"
    bead_json_path.write_text(json.dumps(_fixture_bead()), encoding="utf-8")

    exit_code = context_discovery.main(
        [
            "bead-scoped",
            "--bead-json",
            str(bead_json_path),
            "--repo-root",
            str(tmp_path),
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert captured.err == ""
    lines = [line for line in captured.out.splitlines() if line.strip()]
    assert len(lines) == 1
    payload = json.loads(lines[0])
    assert "adr_context" in payload
    assert payload["provider"] in {"codebase-memory", "fallback"}


def test_provider_resolution_is_project_local_and_uses_canonical_tree_order(
    tmp_path: Path, context_discovery: Any
) -> None:
    agents = _install_project_provider(tmp_path, ".agents/skills")
    _install_project_provider(tmp_path, ".claude/skills")
    _install_project_provider(tmp_path, "skills")

    assert context_discovery.resolve_context_provider(tmp_path) == agents


def test_provider_resolution_rejects_global_runtime_override(
    tmp_path: Path, context_discovery: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_project_provider(tmp_path)
    monkeypatch.setenv("CONTEXT_DISCOVERY_RUNTIME_DIR", "/tmp/global-runtime")

    with pytest.raises(context_discovery.ContextDiscoveryError, match="project-local"):
        context_discovery.resolve_context_provider(tmp_path)


def test_provider_resolution_accepts_selected_project_runtime_override(
    tmp_path: Path, context_discovery: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    provider = _install_project_provider(tmp_path, ".claude/skills")
    monkeypatch.setenv("CONTEXT_DISCOVERY_RUNTIME_DIR", str(provider.parent.parent))

    assert context_discovery.resolve_context_provider(tmp_path) == provider


# ---------------------------------------------------------------------------
# Read-only invariant: no loop state or any other file is ever created
# ---------------------------------------------------------------------------


def test_neither_mode_writes_any_file(
    tmp_path: Path, context_discovery: Any
) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _install_project_provider(repo_root)
    (repo_root / "src").mkdir()
    (repo_root / "src" / "service.py").write_text("def handle_order():\n    return True\n")
    _write_adr(repo_root, adr_id="ADR-057", selector="src/service.py")

    state_dir = tmp_path / "loop-state"
    state_dir.mkdir()

    bead_json_path = tmp_path / "bead.json"
    bead_json_path.write_text(json.dumps(_fixture_bead()), encoding="utf-8")

    before = _snapshot(repo_root, state_dir)

    context_discovery.discover_path_scoped(repo_root, ["src/service.py"])
    context_discovery.discover_bead_scoped(
        repo_root, bead_id="", bead_json=bead_json_path, timeout=8
    )

    after = _snapshot(repo_root, state_dir)

    assert before == after
    assert list(state_dir.iterdir()) == []

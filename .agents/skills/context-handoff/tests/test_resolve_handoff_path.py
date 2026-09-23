from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "resolve_handoff_path.py"


def clean_harness_environment() -> dict[str, str]:
    environment = os.environ.copy()
    for name in (
        "CODEX_THREAD_ID",
        "CLAUDE_CODE_SESSION_ID",
        "CLAUDECODE",
        "CLAUDE_CODE_ENTRYPOINT",
        "CODEX_CI",
        "CODEX_CLI_PATH",
    ):
        environment.pop(name, None)
    return environment


def initialize_repo(path: Path, *, ignore_handoffs: bool = True) -> None:
    subprocess.run(
        ["git", "init", "-q", str(path)],
        check=True,
        capture_output=True,
        text=True,
    )
    if ignore_handoffs:
        (path / ".gitignore").write_text(".intake/context-handoff/\n")


def run_resolver(
    *args: str, cwd: Path, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["uv", "run", "--no-project", str(SCRIPT), *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )


def test_explicit_session_id_resolves_local_handoff_path(tmp_path: Path) -> None:
    initialize_repo(tmp_path)
    result = run_resolver(
        "--repo-root",
        str(tmp_path),
        "--session-id",
        "thr_abc-123",
        cwd=tmp_path,
    )

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload == {
        "status": "ok",
        "summary": "Resolved context handoff path",
        "data": {
            "session_id": "thr_abc-123",
            "source": "argument",
            "relative_path": ".intake/context-handoff/thr_abc-123.md",
            "path": str(tmp_path / ".intake/context-handoff/thr_abc-123.md"),
            "exists": False,
            "git_ignored": True,
            "worktree_local": False,
        },
        "errors": [],
        "next_steps": [],
    }


def test_codex_thread_id_is_used_when_argument_is_absent(tmp_path: Path) -> None:
    initialize_repo(tmp_path)
    environment = clean_harness_environment()
    environment["CODEX_THREAD_ID"] = "thr_from_codex"

    result = run_resolver(
        "--repo-root",
        str(tmp_path),
        cwd=tmp_path,
        env=environment,
    )

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["data"] == {
        "session_id": "thr_from_codex",
        "source": "CODEX_THREAD_ID",
        "relative_path": ".intake/context-handoff/thr_from_codex.md",
        "path": str(tmp_path / ".intake/context-handoff/thr_from_codex.md"),
        "exists": False,
        "git_ignored": True,
        "worktree_local": False,
    }


def test_claude_session_id_is_used_when_codex_id_is_absent(tmp_path: Path) -> None:
    initialize_repo(tmp_path)
    environment = clean_harness_environment()
    environment["CLAUDE_CODE_SESSION_ID"] = "claude-session-123"

    result = run_resolver(
        "--repo-root",
        str(tmp_path),
        cwd=tmp_path,
        env=environment,
    )

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["data"] == {
        "session_id": "claude-session-123",
        "source": "CLAUDE_CODE_SESSION_ID",
        "relative_path": ".intake/context-handoff/claude-session-123.md",
        "path": str(tmp_path / ".intake/context-handoff/claude-session-123.md"),
        "exists": False,
        "git_ignored": True,
        "worktree_local": False,
    }


def test_active_claude_harness_wins_over_inherited_codex_id(
    tmp_path: Path,
) -> None:
    initialize_repo(tmp_path)
    environment = clean_harness_environment()
    environment["CODEX_THREAD_ID"] = "codex-id"
    environment["CLAUDE_CODE_SESSION_ID"] = "claude-id"
    environment["CLAUDECODE"] = "1"

    explicit = run_resolver(
        "--repo-root",
        str(tmp_path),
        "--session-id",
        "explicit-id",
        cwd=tmp_path,
        env=environment,
    )
    claude = run_resolver(
        "--repo-root",
        str(tmp_path),
        cwd=tmp_path,
        env=environment,
    )

    assert json.loads(explicit.stdout)["data"]["source"] == "argument"
    assert json.loads(claude.stdout)["data"]["source"] == "CLAUDE_CODE_SESSION_ID"


def test_indeterminate_harness_with_two_ids_is_rejected(tmp_path: Path) -> None:
    initialize_repo(tmp_path)
    environment = clean_harness_environment()
    environment["CODEX_THREAD_ID"] = "codex-id"
    environment["CLAUDE_CODE_SESSION_ID"] = "claude-id"

    result = run_resolver(
        "--repo-root",
        str(tmp_path),
        cwd=tmp_path,
        env=environment,
    )

    assert result.returncode == 2
    assert json.loads(result.stdout)["errors"][0]["code"] == "SESSION_ID_AMBIGUOUS"


def test_existing_handoff_is_reported_without_modifying_it(tmp_path: Path) -> None:
    initialize_repo(tmp_path)
    handoff = tmp_path / ".intake/context-handoff/existing-id.md"
    handoff.parent.mkdir(parents=True)
    handoff.write_text("existing handoff\n")

    result = run_resolver(
        "--repo-root",
        str(tmp_path),
        "--session-id",
        "existing-id",
        cwd=tmp_path,
    )

    assert result.returncode == 0
    assert json.loads(result.stdout)["data"]["exists"] is True
    assert handoff.read_text() == "existing handoff\n"


def test_missing_canonical_session_id_fails_without_fallback(tmp_path: Path) -> None:
    initialize_repo(tmp_path)
    environment = clean_harness_environment()

    result = run_resolver(
        "--repo-root",
        str(tmp_path),
        cwd=tmp_path,
        env=environment,
    )

    assert result.returncode == 2
    assert json.loads(result.stdout) == {
        "status": "error",
        "summary": "Canonical harness session ID is unavailable",
        "data": {},
        "errors": [
            {
                "code": "SESSION_ID_UNAVAILABLE",
                "message": (
                    "Pass --session-id or expose the active harness's "
                    "CODEX_THREAD_ID or CLAUDE_CODE_SESSION_ID."
                ),
            }
        ],
        "next_steps": ["Obtain the exact session ID from the active harness."],
    }


def test_unsafe_session_id_is_rejected_before_path_construction(tmp_path: Path) -> None:
    initialize_repo(tmp_path)
    result = run_resolver(
        "--repo-root",
        str(tmp_path),
        "--session-id",
        "../another-session",
        cwd=tmp_path,
    )

    assert result.returncode == 2
    payload = json.loads(result.stdout)
    assert payload["status"] == "error"
    assert payload["errors"] == [
        {
            "code": "SESSION_ID_INVALID",
            "message": (
                "Session ID must match "
                "^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$."
            ),
        }
    ]


def test_session_id_length_boundary(tmp_path: Path) -> None:
    initialize_repo(tmp_path)
    accepted = "a" * 128
    rejected = "a" * 129

    accepted_result = run_resolver(
        "--repo-root",
        str(tmp_path),
        "--session-id",
        accepted,
        cwd=tmp_path,
    )
    rejected_result = run_resolver(
        "--repo-root",
        str(tmp_path),
        "--session-id",
        rejected,
        cwd=tmp_path,
    )

    assert accepted_result.returncode == 0
    assert json.loads(accepted_result.stdout)["data"]["session_id"] == accepted
    assert rejected_result.returncode == 2
    assert json.loads(rejected_result.stdout)["errors"][0]["code"] == "SESSION_ID_INVALID"


def test_repo_root_is_derived_consistently_from_nested_directories(
    tmp_path: Path,
) -> None:
    initialize_repo(tmp_path)
    first_cwd = tmp_path / "one"
    second_cwd = tmp_path / "two" / "nested"
    first_cwd.mkdir()
    second_cwd.mkdir(parents=True)

    first = run_resolver("--session-id", "same-id", cwd=first_cwd)
    second = run_resolver("--session-id", "same-id", cwd=second_cwd)

    assert first.returncode == 0
    assert second.returncode == 0
    assert json.loads(first.stdout)["data"]["path"] == json.loads(second.stdout)[
        "data"
    ]["path"]


def test_invalid_repo_root_is_rejected(tmp_path: Path) -> None:
    invalid_root = tmp_path / "missing"

    result = run_resolver(
        "--repo-root",
        str(invalid_root),
        "--session-id",
        "valid-id",
        cwd=tmp_path,
    )

    assert result.returncode == 2
    assert json.loads(result.stdout)["errors"][0]["code"] == "REPO_ROOT_INVALID"


def test_unignored_handoff_path_is_rejected(tmp_path: Path) -> None:
    initialize_repo(tmp_path, ignore_handoffs=False)

    result = run_resolver(
        "--repo-root",
        str(tmp_path),
        "--session-id",
        "valid-id",
        cwd=tmp_path,
    )

    assert result.returncode == 2
    payload = json.loads(result.stdout)
    assert payload["errors"][0]["code"] == "HANDOFF_PATH_NOT_IGNORED"
    assert payload["data"]["git_ignored"] is False

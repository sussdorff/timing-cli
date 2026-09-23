from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
from argparse import Namespace
from pathlib import Path

import pytest


SCRIPT = Path(__file__).parents[1] / "scripts" / "cognovis_bug_lifecycle.py"
SPEC = importlib.util.spec_from_file_location("cognovis_bug_lifecycle", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def command(
    *args: str, cwd: Path | None = None, check: bool = True
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=cwd, text=True, capture_output=True, check=check)


@pytest.fixture
def repository(tmp_path: Path) -> tuple[Path, Path]:
    remote = tmp_path / "remote.git"
    repo = tmp_path / "repo"
    command("git", "init", "--bare", str(remote))
    command("git", "init", "-b", "main", str(repo))
    command("git", "-C", str(repo), "config", "user.email", "test@example.com")
    command("git", "-C", str(repo), "config", "user.name", "Test User")
    (repo / "README.md").write_text("base\n")
    command("git", "-C", str(repo), "add", "README.md")
    command("git", "-C", str(repo), "commit", "-m", "initial")
    command("git", "-C", str(repo), "remote", "add", "origin", str(remote))
    command("git", "-C", str(repo), "push", "-u", "origin", "main")
    command("git", "-C", str(repo), "fetch", "origin")
    return repo, tmp_path / "worktrees"


def invoke(*args: str) -> subprocess.CompletedProcess[str]:
    return command("uv", "run", str(SCRIPT), *args, check=False)


def payload(result: subprocess.CompletedProcess[str]) -> dict[str, object]:
    return json.loads(result.stdout.strip().splitlines()[-1])


def test_close_routes_beads_push_through_serialized_sync(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    calls: list[tuple[str, ...]] = []

    monkeypatch.setattr(MODULE, "resolve_repo", lambda _path: repo)
    monkeypatch.setattr(MODULE, "state_path", lambda _repo, _bead: tmp_path / "absent")

    def fake_run(argv, **_kwargs):
        calls.append(tuple(argv))
        return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")

    monkeypatch.setattr(MODULE, "run", fake_run)

    MODULE.close_bead(
        Namespace(
            repo=str(repo),
            bead_id="bug-1",
            reason="done",
            push_beads=True,
        )
    )

    assert ("bd", "close", "bug-1", "--reason", "done") in calls
    assert (
        "ccore",
        "beads",
        "sync",
        "--repo",
        str(repo),
        "--operation-id",
        "gascity-close:bug-1",
    ) in calls
    assert not any(call[:3] == ("bd", "dolt", "push") for call in calls)


def test_prepare_creates_owned_branch_worktree(repository: tuple[Path, Path]) -> None:
    repo, worktrees = repository
    result = invoke(
        "prepare",
        "--repo",
        str(repo),
        "--bead-id",
        "bug-1",
        "--workspace-root",
        str(worktrees),
    )

    assert result.returncode == 0, result.stdout + result.stderr
    data = payload(result)["data"]
    assert data["branch"] == "bead-bug-1"
    assert Path(data["worktree"]).is_dir()
    assert (
        command(
            "git", "-C", data["worktree"], "branch", "--show-current"
        ).stdout.strip()
        == "bead-bug-1"
    )


def test_prepare_refuses_unowned_existing_path(repository: tuple[Path, Path]) -> None:
    repo, worktrees = repository
    target = worktrees / "bug-1"
    target.mkdir(parents=True)

    result = invoke(
        "prepare",
        "--repo",
        str(repo),
        "--bead-id",
        "bug-1",
        "--workspace-root",
        str(worktrees),
    )

    assert result.returncode == 1
    assert "Refusing to reuse unowned path" in payload(result)["errors"][0]


def test_prepare_fetches_latest_remote_base(repository: tuple[Path, Path]) -> None:
    repo, worktrees = repository
    other = repo.parent / "other"
    command("git", "clone", str(repo.parent / "remote.git"), str(other))
    command("git", "-C", str(other), "config", "user.email", "test@example.com")
    command("git", "-C", str(other), "config", "user.name", "Test User")
    (other / "remote.txt").write_text("latest\n")
    command("git", "-C", str(other), "add", "remote.txt")
    command("git", "-C", str(other), "commit", "-m", "advance remote")
    command("git", "-C", str(other), "push", "origin", "main")

    result = invoke(
        "prepare",
        "--repo",
        str(repo),
        "--bead-id",
        "bug-1",
        "--workspace-root",
        str(worktrees),
    )

    worktree = Path(payload(result)["data"]["worktree"])
    assert (worktree / "remote.txt").read_text() == "latest\n"


def test_integration_and_cleanup_preserve_dirty_canonical_checkout(
    repository: tuple[Path, Path],
) -> None:
    repo, worktrees = repository
    prepared = invoke(
        "prepare",
        "--repo",
        str(repo),
        "--bead-id",
        "bug-1",
        "--workspace-root",
        str(worktrees),
    )
    worktree = Path(payload(prepared)["data"]["worktree"])
    command("git", "-C", str(worktree), "config", "user.email", "test@example.com")
    command("git", "-C", str(worktree), "config", "user.name", "Test User")
    (worktree / "fix.txt").write_text("fixed\n")
    command("git", "-C", str(worktree), "add", "fix.txt")
    command("git", "-C", str(worktree), "commit", "-m", "fix bug")
    (repo / "local-notes.txt").write_text("must survive\n")
    review_report = worktrees / "bug-1-review.md"
    review_report.write_text("Status: CLEAN\n")

    integrated = invoke(
        "integrate",
        "--repo",
        str(repo),
        "--bead-id",
        "bug-1",
        "--review-report",
        str(review_report),
        "--verify-command",
        "test -f fix.txt",
        "--push",
    )
    assert integrated.returncode == 0, integrated.stdout + integrated.stderr
    assert (repo / "local-notes.txt").read_text() == "must survive\n"

    cleaned = invoke("cleanup", "--repo", str(repo), "--bead-id", "bug-1")
    assert cleaned.returncode == 0, cleaned.stdout + cleaned.stderr
    assert not worktree.exists()
    assert (repo / "local-notes.txt").read_text() == "must survive\n"


def test_cleanup_refuses_before_integration(repository: tuple[Path, Path]) -> None:
    repo, worktrees = repository
    invoke(
        "prepare",
        "--repo",
        str(repo),
        "--bead-id",
        "bug-1",
        "--workspace-root",
        str(worktrees),
    )

    result = invoke("cleanup", "--repo", str(repo), "--bead-id", "bug-1")

    assert result.returncode == 1
    assert "before a successful integration" in payload(result)["errors"][0]


def test_abort_removes_commitless_owned_worktree(repository: tuple[Path, Path]) -> None:
    repo, worktrees = repository
    prepared = invoke(
        "prepare",
        "--repo",
        str(repo),
        "--bead-id",
        "bug-1",
        "--workspace-root",
        str(worktrees),
    )
    worktree = Path(payload(prepared)["data"]["worktree"])

    result = invoke("abort", "--repo", str(repo), "--bead-id", "bug-1")

    assert result.returncode == 0, result.stdout + result.stderr
    assert not worktree.exists()
    assert (
        command(
            "git",
            "-C",
            str(repo),
            "show-ref",
            "--verify",
            "refs/heads/bead-bug-1",
            check=False,
        ).returncode
        != 0
    )


def test_merge_conflict_is_reported_and_integration_worktree_is_removed(
    repository: tuple[Path, Path],
) -> None:
    repo, worktrees = repository
    prepared = invoke(
        "prepare",
        "--repo",
        str(repo),
        "--bead-id",
        "bug-1",
        "--workspace-root",
        str(worktrees),
    )
    worktree = Path(payload(prepared)["data"]["worktree"])
    command("git", "-C", str(worktree), "config", "user.email", "test@example.com")
    command("git", "-C", str(worktree), "config", "user.name", "Test User")
    (worktree / "README.md").write_text("feature change\n")
    command("git", "-C", str(worktree), "add", "README.md")
    command("git", "-C", str(worktree), "commit", "-m", "feature change")

    (repo / "README.md").write_text("base change\n")
    command("git", "-C", str(repo), "add", "README.md")
    command("git", "-C", str(repo), "commit", "-m", "base change")
    command("git", "-C", str(repo), "push", "origin", "main")
    review_report = worktrees / "bug-1-review.md"
    review_report.write_text("Status: CLEAN\n")

    result = invoke(
        "integrate",
        "--repo",
        str(repo),
        "--bead-id",
        "bug-1",
        "--review-report",
        str(review_report),
        "--push",
    )

    assert result.returncode == 1
    assert "CONFLICT" in payload(result)["errors"][0]
    assert not (worktrees / ".bug-1-integration").exists()


def test_integration_refuses_without_clean_review(
    repository: tuple[Path, Path],
) -> None:
    repo, _ = repository
    report = repo.parent / "review.md"
    report.write_text("Status: FINDINGS\n")

    result = invoke(
        "integrate",
        "--repo",
        str(repo),
        "--bead-id",
        "bug-1",
        "--review-report",
        str(report),
        "--push",
    )

    assert result.returncode == 1
    assert "Review gate did not pass" in payload(result)["errors"][0]


def test_write_review_gate_creates_executable_wrapper(tmp_path: Path) -> None:
    report = tmp_path / "review report.md"
    report.write_text("Status: CLEAN\n")
    gate = tmp_path / "runtime" / "review-gate"

    result = invoke(
        "write-review-gate",
        "--lifecycle-script",
        str(SCRIPT),
        "--uv-bin",
        str(Path(shutil.which("uv") or "uv").resolve()),
        "--report",
        str(report),
        "--output",
        str(gate),
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert gate.is_file()
    assert gate.stat().st_mode & 0o100
    gate_result = command(str(gate), check=False)
    assert gate_result.returncode == 0, gate_result.stdout + gate_result.stderr


@pytest.mark.parametrize(
    ("content", "expected_code"),
    [("Status: CLEAN\n", 0), ("Status: FINDINGS\n", 1), ("no status\n", 1)],
)
def test_review_gate(tmp_path: Path, content: str, expected_code: int) -> None:
    report = tmp_path / "review.md"
    report.write_text(content)

    result = invoke("review-gate", "--report", str(report))

    assert result.returncode == expected_code

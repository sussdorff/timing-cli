from __future__ import annotations

import importlib.util
from pathlib import Path
import subprocess


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "agent_workspace_guard.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("agent_workspace_guard", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _self_managed_root(tmp_path: Path) -> Path:
    """The canonical root a `self` worktree must sit under, for this fixture."""
    return tmp_path / ".worktrees"


def _repo_with_worktree(tmp_path: Path) -> tuple[Path, Path]:
    main = tmp_path / "main"
    worktree = _self_managed_root(tmp_path) / "bead-worktree"
    main.mkdir()
    _git(main, "init", "-b", "main")
    _git(main, "config", "user.email", "test@example.com")
    _git(main, "config", "user.name", "Test User")
    (main / "README.md").write_text("base\n", encoding="utf-8")
    _git(main, "add", "README.md")
    _git(main, "commit", "-m", "base")
    _git(main, "worktree", "add", "-b", "worktree-bead-clc-k915", str(worktree))
    return main, worktree


def test_regression_doc_updater_accepts_only_the_active_linked_worktree(
    tmp_path: Path,
) -> None:
    """Guard repeated doc-changelog-updater writes into the shared main checkout."""
    module = _load_module()
    main, worktree = _repo_with_worktree(tmp_path)

    result = module.validate_workspace(
        invocation_dir=worktree,
        expected_workspace=worktree,
        require_linked_worktree=True,
        self_managed_root=_self_managed_root(tmp_path),
    )

    assert result["status"] == "ok"
    assert result["code"] == "WORKSPACE_VALID"
    assert result["workspace_root"] == str(worktree.resolve())
    assert result["branch"] == "worktree-bead-clc-k915"
    assert not (main / "CHANGELOG.md").exists()


def test_doc_updater_rejects_the_shared_main_checkout(tmp_path: Path) -> None:
    module = _load_module()
    main, _ = _repo_with_worktree(tmp_path)

    result = module.validate_workspace(
        invocation_dir=main,
        expected_workspace=main,
        require_linked_worktree=True,
    )

    assert result["status"] == "error"
    assert result["code"] == "MAIN_CHECKOUT_FORBIDDEN"


def test_doc_updater_rejects_expected_workspace_mismatch(tmp_path: Path) -> None:
    module = _load_module()
    main, worktree = _repo_with_worktree(tmp_path)

    result = module.validate_workspace(
        invocation_dir=worktree,
        expected_workspace=main,
        require_linked_worktree=True,
    )

    assert result["status"] == "error"
    assert result["code"] == "WORKSPACE_ROOT_MISMATCH"
    assert result["workspace_root"] == str(worktree.resolve())
    assert result["expected_workspace"] == str(main.resolve())


def test_doc_updater_rejects_branch_mismatch(tmp_path: Path) -> None:
    module = _load_module()
    _, worktree = _repo_with_worktree(tmp_path)

    result = module.validate_workspace(
        invocation_dir=worktree,
        expected_workspace=worktree,
        require_linked_worktree=True,
        expected_branch="different-branch",
    )

    assert result["status"] == "error"
    assert result["code"] == "BRANCH_MISMATCH"


def test_doc_updater_accepts_write_targets_inside_worktree(tmp_path: Path) -> None:
    module = _load_module()
    _, worktree = _repo_with_worktree(tmp_path)

    result = module.validate_workspace(
        invocation_dir=worktree,
        expected_workspace=worktree,
        require_linked_worktree=True,
        expected_branch="worktree-bead-clc-k915",
        targets=[worktree / "CHANGELOG.md", Path("docs/guide.md")],
        self_managed_root=_self_managed_root(tmp_path),
    )

    assert result["status"] == "ok"
    assert result["code"] == "WORKSPACE_VALID"
    assert result["targets"] == [
        str((worktree / "CHANGELOG.md").resolve()),
        str((worktree / "docs/guide.md").resolve()),
    ]


def test_doc_updater_rejects_write_target_in_main_checkout(tmp_path: Path) -> None:
    module = _load_module()
    main, worktree = _repo_with_worktree(tmp_path)

    result = module.validate_workspace(
        invocation_dir=worktree,
        expected_workspace=worktree,
        require_linked_worktree=True,
        targets=[main / "CHANGELOG.md"],
        self_managed_root=_self_managed_root(tmp_path),
    )

    assert result["status"] == "error"
    assert result["code"] == "TARGET_OUTSIDE_WORKSPACE"
    assert result["target"] == str((main / "CHANGELOG.md").resolve())


def test_guard_rejects_non_git_directory(tmp_path: Path) -> None:
    module = _load_module()

    result = module.validate_workspace(
        invocation_dir=tmp_path,
        expected_workspace=tmp_path,
        require_linked_worktree=True,
    )

    assert result["status"] == "error"
    assert result["code"] == "NOT_A_GIT_WORKSPACE"


def test_guard_rejects_detached_head(tmp_path: Path) -> None:
    module = _load_module()
    _, worktree = _repo_with_worktree(tmp_path)
    _git(worktree, "checkout", "--detach")

    result = module.validate_workspace(
        invocation_dir=worktree,
        expected_workspace=worktree,
        require_linked_worktree=True,
    )

    assert result["status"] == "error"
    assert result["code"] == "DETACHED_HEAD_FORBIDDEN"


def test_guard_can_explicitly_allow_main_checkout(tmp_path: Path) -> None:
    module = _load_module()
    main, _ = _repo_with_worktree(tmp_path)

    result = module.validate_workspace(
        invocation_dir=main,
        expected_workspace=main,
        require_linked_worktree=False,
    )

    assert result["status"] == "ok"
    assert result["code"] == "WORKSPACE_VALID"

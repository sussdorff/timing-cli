"""AC2: implementer test-tree edits are a contract violation, not GREEN."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "tdd_loop_contract.py"


def _load():
    spec = importlib.util.spec_from_file_location("tdd_loop_contract", MODULE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_implementer_test_file_edit_is_contract_violation_not_green() -> None:
    contract = _load()
    result = contract.classify_implementer_slice(
        changed_paths=["src/mapper.ts", "tests/unit/lab.test.ts"],
        test_tree="tests",
        green_exit=0,
    )
    assert result["status"] == "contract_violation"
    assert result["status"] != "green"
    assert "tests/unit/lab.test.ts" in result["paths"]


def test_implementer_source_only_edit_can_be_green() -> None:
    contract = _load()
    result = contract.classify_implementer_slice(
        changed_paths=["src/mapper.ts"],
        test_tree="tests",
        green_exit=0,
    )
    assert result["status"] == "green"


def test_author_paths_under_declared_test_tree_are_accepted() -> None:
    contract = _load()
    result = contract.classify_author_slice(
        changed_paths=["tests/unit/lab.test.ts", "tests/conftest.py"],
        test_tree="tests",
    )
    assert result["status"] == "red"
    assert result["status"] != "contract_violation"


def test_author_path_outside_test_tree_is_contract_violation() -> None:
    contract = _load()
    result = contract.classify_author_slice(
        changed_paths=["tests/unit/lab.test.ts", "src/mapper.ts"],
        test_tree="tests",
    )
    assert result["status"] == "contract_violation"
    assert result["status"] != "red"
    assert "src/mapper.ts" in result["paths"]


def test_cli_reports_violation_for_author_path_outside_test_tree() -> None:
    import subprocess

    result = subprocess.run(
        [
            "uv",
            "run",
            "python",
            str(MODULE),
            "classify-author",
            "--test-tree",
            "tests",
            "--changed-path",
            "src/mapper.ts",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0
    assert "contract_violation" in result.stdout


def test_author_dotdot_escape_is_contract_violation(tmp_path: Path) -> None:
    contract = _load()
    (tmp_path / "tests").mkdir()
    (tmp_path / "src").mkdir()
    result = contract.classify_author_slice(
        changed_paths=["tests/../src/mapper.ts"],
        test_tree="tests",
        repo_root=tmp_path,
    )
    assert result["status"] == "contract_violation"
    assert result["status"] != "red"


def test_implementer_dotdot_into_src_is_not_classified_as_test_tree(
    tmp_path: Path,
) -> None:
    contract = _load()
    (tmp_path / "tests").mkdir()
    (tmp_path / "src").mkdir()
    result = contract.classify_implementer_slice(
        changed_paths=["tests/../src/mapper.ts"],
        test_tree="tests",
        green_exit=0,
        repo_root=tmp_path,
    )
    assert result["status"] == "green"


def test_implementer_absolute_path_inside_test_tree_is_violation(tmp_path: Path) -> None:
    contract = _load()
    (tmp_path / "tests").mkdir()
    inside = tmp_path / "tests" / "lab.test.ts"
    inside.write_text("test\n", encoding="utf-8")
    result = contract.classify_implementer_slice(
        changed_paths=[str(inside)],
        test_tree="tests",
        green_exit=0,
        repo_root=tmp_path,
    )
    assert result["status"] == "contract_violation"
    assert result["status"] != "green"


def test_empty_test_tree_is_refused(tmp_path: Path) -> None:
    contract = _load()
    result = contract.classify_implementer_slice(
        changed_paths=["tests/foo.py"],
        test_tree="",
        green_exit=0,
        repo_root=tmp_path,
    )
    assert result["status"] == "invalid"
    assert result["status"] != "green"


def test_cli_reports_violation_for_implementer_test_edit(tmp_path: Path) -> None:
    import subprocess

    result = subprocess.run(
        [
            "uv",
            "run",
            "python",
            str(MODULE),
            "classify",
            "--test-tree",
            "tests",
            "--green-exit",
            "0",
            "--changed-path",
            "tests/foo.py",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0
    assert "contract_violation" in result.stdout

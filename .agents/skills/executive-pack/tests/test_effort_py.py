from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "effort.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("effort", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("exit_code", [0, 1])
def test_main_forwards_args_and_exit_code(monkeypatch, exit_code: int) -> None:
    module = _load_module()
    calls: list[list[str]] = []
    monkeypatch.setattr(module.sys, "argv", ["effort.py", "clc-test", "--force"])

    def fake_call(args):
        calls.append(list(args))
        return exit_code

    monkeypatch.setattr(module.subprocess, "call", fake_call)

    assert module.main() == exit_code
    assert calls == [
        [module.sys.executable, str(module._CLASSIFY), "clc-test", "--force"]
    ]

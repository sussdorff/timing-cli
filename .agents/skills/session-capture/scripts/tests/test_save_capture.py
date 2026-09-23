from __future__ import annotations

import importlib.util
from pathlib import Path
import subprocess
import sys


SCRIPT = Path(__file__).resolve().parents[1] / "save_capture.py"
SPEC = importlib.util.spec_from_file_location("save_capture", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def test_hostile_capture_text_is_passed_as_one_argv_value() -> None:
    text = 'result $(touch should-not-run) `uname` "quoted"'
    request = MODULE.CaptureRequest(
        text=text,
        project="library-core",
        title="Capture",
        harness="codex",
        session_id="session-1",
        memory_type="session_summary",
        producer="session-capture",
    )
    calls: list[list[str]] = []

    def fake_runner(argv: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append(argv)
        return subprocess.CompletedProcess(argv, 0, "mem-1\n", "")

    result = MODULE.save_capture(request, runner=fake_runner)

    assert result.returncode == 0
    assert calls == [[
        "ob", "save", text, "--type=session_summary", "--project=library-core",
        "--title=Capture", "--producer=session-capture",
        "--source-ref=agent-session:codex:session-1",
    ]]

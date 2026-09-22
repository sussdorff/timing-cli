#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.14"
# ///
"""Save caller-authored session capture text without shell interpolation."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import subprocess
from typing import Callable, Sequence


@dataclass(frozen=True)
class CaptureRequest:
    """Validated immutable input for one Open Brain capture record."""

    text: str
    project: str
    title: str
    harness: str
    session_id: str
    memory_type: str
    producer: str

    @property
    def source_ref(self) -> str:
        return f"agent-session:{self.harness}:{self.session_id}"


def build_ob_argv(request: CaptureRequest) -> list[str]:
    """Return the exact argv passed to ob; text remains one data argument."""
    return [
        "ob",
        "save",
        request.text,
        f"--type={request.memory_type}",
        f"--project={request.project}",
        f"--title={request.title}",
        f"--producer={request.producer}",
        f"--source-ref={request.source_ref}",
    ]


def save_capture(
    request: CaptureRequest,
    *,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> subprocess.CompletedProcess[str]:
    """Invoke ob directly with argv, never through a shell."""
    return runner(build_ob_argv(request), text=True, check=False)


def parse_request(argv: Sequence[str] | None = None) -> CaptureRequest:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-file", type=Path, required=True)
    parser.add_argument("--project", required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--harness", required=True)
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--type", dest="memory_type", default="session_summary")
    parser.add_argument("--producer", default="session-capture")
    args = parser.parse_args(argv)
    text = args.input_file.read_text(encoding="utf-8")
    values = (text, args.project, args.title, args.harness, args.session_id, args.memory_type, args.producer)
    if not all(value.strip() for value in values):
        parser.error("capture text and provenance fields must be non-empty")
    return CaptureRequest(
        text=text,
        project=args.project,
        title=args.title,
        harness=args.harness,
        session_id=args.session_id,
        memory_type=args.memory_type,
        producer=args.producer,
    )


def main(argv: Sequence[str] | None = None) -> int:
    request = parse_request(argv)
    result = save_capture(request)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())

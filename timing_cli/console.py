"""Canonical access to the CLI's stdout and stderr consoles."""

from __future__ import annotations

from typing import Any

from timing_cli import output


def __getattr__(name: str) -> Any:
    if name in {"console", "err_console"}:
        return getattr(output, name)
    raise AttributeError(name)

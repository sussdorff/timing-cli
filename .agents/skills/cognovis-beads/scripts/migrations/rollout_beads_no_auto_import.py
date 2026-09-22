#!/usr/bin/env python3
"""Compatibility wrapper for the Dolt source-of-truth rollout helper."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "jsonl-source-of-truth-rollout.py"
)


def _load_impl():
    spec = importlib.util.spec_from_file_location("jsonl_source_of_truth_rollout", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load rollout helper at {SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


_IMPL = _load_impl()
RolloutUpdate = _IMPL.RolloutUpdate
discover_configs = _IMPL.discover_configs


def ensure_no_auto_import(text: str) -> tuple[str, str, bool]:
    """Compatibility API for setting only no-auto-import: true."""

    updated, action, changed = _IMPL.ensure_bool_setting(
        text,
        key="no-auto-import",
        value=True,
        insert_comment=None,
    )
    prefix = "no-auto-import:"
    if action.startswith(prefix):
        action = action[len(prefix) :]
    return updated, action, changed


def run(paths, *, dry_run: bool):
    """Compatibility API that updates bd configs without JSONL cleanup."""

    return _IMPL.run(paths, dry_run=dry_run, cleanup_jsonl=False)


if __name__ == "__main__":
    raise SystemExit(_IMPL.main())

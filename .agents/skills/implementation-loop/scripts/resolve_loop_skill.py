#!/usr/bin/env python3
"""Resolve implementation-loop scripts via canonical skill-root probe order."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


SKILL_NAME = "implementation-loop"


class LoopSkillNotFound(FileNotFoundError):
    def __init__(self, message: str, probed_paths: list[str]) -> None:
        super().__init__(message)
        self.probed_paths = probed_paths


def probe_loop_skill_roots(*, repo_root: Path, home: Path) -> tuple[Path, ...]:
    repository = repo_root.resolve()
    user_home = home.expanduser().resolve()
    return (
        repository / ".agents" / "skills" / SKILL_NAME,
        repository / ".claude" / "skills" / SKILL_NAME,
        repository / "skills" / SKILL_NAME,
        user_home / ".agents" / "skills" / SKILL_NAME,
        user_home / ".claude" / "skills" / SKILL_NAME,
    )


def resolve_loop_script(
    script_name: str,
    *,
    repo_root: Path | None = None,
    home: Path | None = None,
) -> Path:
    roots = probe_loop_skill_roots(
        repo_root=repo_root or Path.cwd(),
        home=home or Path.home(),
    )
    probed = [str(root) for root in roots]
    for root in roots:
        candidate = root / "scripts" / script_name
        if candidate.is_file():
            return candidate
    raise LoopSkillNotFound(
        "implementation-loop script not found; probed: " + ", ".join(probed),
        probed_paths=probed,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("script_name")
    parser.add_argument("--repo-root", default=".")
    args = parser.parse_args(argv)
    try:
        found = resolve_loop_script(args.script_name, repo_root=Path(args.repo_root))
    except LoopSkillNotFound as exc:
        print(json.dumps({"status": "error", "probed_paths": exc.probed_paths}, indent=2))
        print(str(exc), file=sys.stderr)
        return 1
    print(found)
    return 0


if __name__ == "__main__":
    sys.exit(main())

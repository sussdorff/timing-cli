"""Regression guard: the retired Phase 5 / agy implementation pipeline stays gone.

The pipeline below was removed in clc-7qhr after its only entry point
(skills/beads/scripts/codex-impl.py) was deleted in 42daa716 and the live
implementation path moved to implementation-loop -> implementer over a
persistent ACPX session (ADR-0009). No skill, agent, wrapper, hook, or MCP
registry entry called these modules any more.

This test fails if a module comes back or if a tracked file starts referencing
one, which would leave a dangling import or documentation link. History stays
readable: CHANGELOG files record the pipeline's life and are excluded here, and
the code itself remains recoverable from git.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

_SCRIPTS_DIR = Path(__file__).resolve().parents[1]
_TESTS_DIR = Path(__file__).resolve().parent
_REPO_ROOT = Path(__file__).resolve().parents[4]

RETIRED_MODULES = (
    "agy-impl.py",
    "impl_commit_verify.py",
    "impl_schema.py",
    "implementation_artifacts.py",
    "p5_prompt_builders.py",
    "p5_state_machine.py",
    "terminal_report.py",
)

RETIRED_TESTS = (
    "test_agy_impl_py.py",
    "test_impl_schema_py.py",
    "test_implementation_artifacts.py",
    "test_p5_prompt_builders.py",
    "test_p5_state_machine.py",
)

# Module basenames without their suffix — the form an import or a doc link uses.
RETIRED_STEMS = tuple(name.removesuffix(".py") for name in RETIRED_MODULES)

# Consumer-facing identifiers that were removed alongside the modules. A caller
# names a script by its registry script_id rather than by module stem, so the
# guard has to know both spellings or it would miss a real reintroduction.
RETIRED_REGISTRY_IDS = ("beads.implementation-artifacts",)


def _reference_forms(stem: str) -> set[str]:
    """Every spelling a reference to one retired module can take."""
    return {stem, stem.replace("_", "-"), stem.replace("-", "_")}


RETIRED_TOKENS = frozenset(
    form for stem in RETIRED_STEMS for form in _reference_forms(stem)
) | frozenset(RETIRED_REGISTRY_IDS)


def retired_tokens_in(content: str) -> list[str]:
    """Return every retired reference token that appears in content."""
    return sorted(token for token in RETIRED_TOKENS if token in content)

# Frozen historical records are allowed to name the retired pipeline. A
# changelog entry and a completed run's evidence artifacts describe what
# happened; they are not links a reader can follow to a live file, and
# rewriting a past run's evidence would falsify it. This guard also excludes
# itself, since it must spell the names out in order to look for them.
_ALLOWED_REFERENCE_FILES = frozenset({Path(__file__).relative_to(_REPO_ROOT).as_posix()})
_ALLOWED_BASENAMES = frozenset({"CHANGELOG.md"})
_ALLOWED_PREFIXES = (".beads/runs/",)


def _tracked_files() -> list[str]:
    """Tracked files plus new, non-ignored ones, so the guard also holds pre-commit."""
    result = subprocess.run(
        [
            "git", "-C", str(_REPO_ROOT), "ls-files", "-z",
            "--cached", "--others", "--exclude-standard",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return [entry for entry in result.stdout.split("\0") if entry]


@pytest.mark.parametrize("module_name", RETIRED_MODULES)
def test_retired_module_is_absent(module_name: str) -> None:
    assert not (_SCRIPTS_DIR / module_name).exists(), (
        f"{module_name} is a retired Phase 5 pipeline module and must stay removed"
    )


@pytest.mark.parametrize("test_name", RETIRED_TESTS)
def test_retired_pipeline_test_is_absent(test_name: str) -> None:
    assert not (_TESTS_DIR / test_name).exists(), (
        f"{test_name} tests a retired module and must stay removed"
    )


def test_no_tracked_file_references_a_retired_module() -> None:
    """No dangling import or documentation link to a removed module (AC1)."""
    offenders: dict[str, list[str]] = {}
    for relative_path in _tracked_files():
        path = Path(relative_path)
        if relative_path in _ALLOWED_REFERENCE_FILES or path.name in _ALLOWED_BASENAMES:
            continue
        if relative_path.startswith(_ALLOWED_PREFIXES):
            continue
        absolute = _REPO_ROOT / path
        if not absolute.is_file():
            continue
        try:
            content = absolute.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        hits = retired_tokens_in(content)
        if hits:
            offenders[relative_path] = hits

    assert not offenders, (
        "tracked files still reference retired Phase 5 pipeline modules: "
        + "; ".join(f"{path} -> {sorted(names)}" for path, names in sorted(offenders.items()))
    )


@pytest.mark.parametrize(
    "token",
    [
        # Python import / module-path spelling.
        "implementation_artifacts",
        "p5_prompt_builders",
        # The retired MCP registry identifier and its bare hyphenated form. A
        # consumer names the script by script_id, not by module stem, so a
        # guard that only knows underscores would miss a real reintroduction.
        "beads.implementation-artifacts",
        "implementation-artifacts",
        "p5-state-machine",
        # Underscore spelling of the hyphen-stemmed module agy-impl.py, the
        # form a Python import of a reintroduced module would use.
        "agy_impl",
    ],
)
def test_guard_matches_every_retired_reference_form(token: str) -> None:
    assert retired_tokens_in(f"see {token} for details"), (
        f"the guard does not recognize {token!r} as a retired reference"
    )


def test_guard_ignores_unrelated_content() -> None:
    """The guard must not fire on the surviving module or ordinary prose."""
    assert not retired_tokens_in(
        "prompt_envelope.py wraps untrusted bead-tracker fields before interpolation"
    )


def test_envelope_helper_survived_the_removal() -> None:
    """wrap_untrusted_field must outlive its retired host module (AC2)."""
    assert (_SCRIPTS_DIR / "prompt_envelope.py").exists(), (
        "prompt_envelope.py is the live home for wrap_untrusted_field; "
        "standards/security/content-isolation.md cites it"
    )

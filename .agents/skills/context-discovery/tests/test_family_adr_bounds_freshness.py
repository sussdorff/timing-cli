"""Regression/MoC coverage for clc-apby AC3: bounds and freshness across corpora.

These are NOT RED tests. Slice-1 already made the manifest bound and the ADR
corpus digest span every resolved corpus, so these pass on arrival. They exist
as the Means of Compliance evidence for AC3 row 3 and lock two properties that
would otherwise regress silently back to local-only behavior:

- the bound is applied to the *combined* local plus family applicable set, and
  omitted applicable records stay a typed ``ADR_MANIFEST_TRUNCATED`` gap;
- ``freshness.adr_corpus_digest`` and ``freshness.context_digest`` change when
  either the local or the governing family corpus changes.

Fixtures are generated in ``tmp_path`` (bound) or copied from the committed FHIR
sibling layout (freshness). No machine or home path appears in either.
"""

from __future__ import annotations

import importlib.util
import shutil
from pathlib import Path
from typing import Any

import pytest


_TESTS_DIR = Path(__file__).resolve().parent
_SKILL_ROOT = _TESTS_DIR.parent
_SCRIPTS_DIR = _SKILL_ROOT / "scripts"
_FIXTURE_ROOT = _TESTS_DIR / "fixtures" / "family_adr_discovery"

_CANDIDATE_PATH = "src/client/canonical_client.py"
_CANDIDATE_BODY = "def build_client():\n    return None\n"
_ADR_SELECTOR = "src/client"


def _load_module(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def context_provider() -> Any:
    return _load_module(
        _SCRIPTS_DIR / "context_provider.py", "context_provider_bounds_under_test"
    )


def _bead() -> dict[str, Any]:
    return {
        "id": "clc-apby-fixture",
        "title": "Family ADR bounds and freshness fixture",
        "description": "",
        "acceptance_criteria": "",
        "metadata": {},
    }


def _write_generated_adr(adr_dir: Path, adr_id: str) -> None:
    adr_dir.mkdir(parents=True, exist_ok=True)
    (adr_dir / f"{adr_id}-generated.md").write_text(
        f"""---
id: {adr_id}
status: accepted
applies_to:
  - {_ADR_SELECTOR}
decision_summary: "Generated decision {adr_id}."
prohibits:
  - "Do not break {adr_id}."
---

# {adr_id}
""",
        encoding="utf-8",
    )


def _generate_two_corpus_repository(tmp_path: Path, *, per_corpus: int) -> Path:
    """Generate a child repository and its governing corpus, each with N ADRs."""
    repo_root = tmp_path / "generated-child"
    candidate = repo_root / _CANDIDATE_PATH
    candidate.parent.mkdir(parents=True)
    candidate.write_text(_CANDIDATE_BODY, encoding="utf-8")
    (repo_root / ".adr-governance.json").write_text(
        '{\n'
        '  "schema_version": 1,\n'
        '  "governing_corpora": [\n'
        '    {"corpus": "generated-family", "workspace_path": "../generated-family"}\n'
        '  ]\n'
        '}\n',
        encoding="utf-8",
    )
    family_root = tmp_path / "generated-family"
    for index in range(per_corpus):
        _write_generated_adr(repo_root / "docs" / "adr", f"ADR-L{index:03d}")
        _write_generated_adr(family_root / "docs" / "adr", f"ADR-F{index:03d}")
    return repo_root


def _materialize_fhir_sibling_layout(tmp_path: Path) -> Path:
    """Copy the committed slice-1 FHIR child and family repositories."""
    repo_root = tmp_path / "fhir-sdk"
    shutil.copytree(_FIXTURE_ROOT / "fhir-sdk", repo_root)
    shutil.copytree(_FIXTURE_ROOT / "fhir-management", tmp_path / "fhir-management")
    candidate = repo_root / _CANDIDATE_PATH
    candidate.parent.mkdir(parents=True, exist_ok=True)
    candidate.write_text(_CANDIDATE_BODY, encoding="utf-8")
    return repo_root


def test_combined_local_and_family_set_stays_bounded_and_reports_omissions(
    tmp_path: Path, context_provider: Any
) -> None:
    limit = context_provider.ADR_MANIFEST_LIMIT
    per_corpus = limit // 2 + 8
    discovered_count = per_corpus * 2
    assert discovered_count > limit

    repo_root = _generate_two_corpus_repository(tmp_path, per_corpus=per_corpus)
    context = context_provider.build_adr_context(_bead(), repo_root, [_CANDIDATE_PATH])

    assert context["status"] == "gap"
    assert len(context["manifest"]) == limit

    truncations = [
        gap for gap in context["gaps"] if gap["code"] == "ADR_MANIFEST_TRUNCATED"
    ]
    assert len(truncations) == 1
    gap = truncations[0]
    assert gap["resolved"] is False
    assert gap["limit"] == limit
    assert gap["discovered_count"] == discovered_count
    assert gap["omitted_count"] == discovered_count - limit

    # The bound ranks one combined set, so both corpora reach the manifest.
    origins = {entry["origin"] for entry in context["manifest"]}
    assert origins == {"local", "family"}


@pytest.mark.parametrize(
    ("edited_corpus", "adr_path"),
    [
        ("family", "../fhir-management/docs/adr/ADR-009-canonical-fhir-client.md"),
        ("local", "docs/adr/ADR-101-local-client-wiring.md"),
    ],
)
def test_freshness_digests_change_when_either_corpus_changes(
    tmp_path: Path, context_provider: Any, edited_corpus: str, adr_path: str
) -> None:
    repo_root = _materialize_fhir_sibling_layout(tmp_path)

    before = context_provider.build_adr_context(
        _bead(), repo_root, [_CANDIDATE_PATH]
    )["freshness"]

    edited = (repo_root / adr_path).resolve()
    assert edited.is_file()
    edited.write_text(
        edited.read_text(encoding="utf-8") + f"\nAmended {edited_corpus} guidance.\n",
        encoding="utf-8",
    )

    after = context_provider.build_adr_context(
        _bead(), repo_root, [_CANDIDATE_PATH]
    )["freshness"]

    assert after["adr_corpus_digest"] != before["adr_corpus_digest"]
    assert after["context_digest"] != before["context_digest"]

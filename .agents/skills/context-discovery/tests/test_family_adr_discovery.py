"""RED specification for governing repository-family ADR discovery (clc-apby).

Slice ``family-local-discovery-fhir-and-polaris``. Today ``_adr_dir`` resolves
only ``<repo>/docs/adr``, so a child repository never sees the family decision
that governs it and manifest entries carry no origin or precedence at all.

Declared contract under specification
-------------------------------------
A repository declares governing ADR corpora in a project-local
``.adr-governance.json`` at its root, without any absolute machine path::

    {
      "schema_version": 1,
      "governing_corpora": [
        {"corpus": "fhir-management", "workspace_path": "../fhir-management"}
      ]
    }

``workspace_path`` is resolved relative to the declaring repository root and
``docs/adr`` under it is the corpus. Every selected ADR then carries explicit
``origin``, ``corpus`` and ``precedence`` fields:

===================  ==========  ==============  ============
corpus               origin      corpus token    precedence
===================  ==========  ==============  ============
``<repo>/docs/adr``  ``local``   ``local``       ``local``
declared corpus      ``family``  declared id     ``governing``
===================  ==========  ==============  ============

``path`` stays corpus-relative for both origins so no machine path leaks into
a manifest, and family selectors are matched against the declaring child
repository's candidate surface.

Independent expected-value provenance
-------------------------------------
Every literal below is read from a committed fixture file or from the bead,
never from provider output.

| expected value    | source_kind         | fixture path / pointer |
|-------------------|---------------------|------------------------|
| ``ADR-009``       | generated_fixture   | ``skills/context-discovery/tests/fixtures/family_adr_discovery/fhir-management/docs/adr/ADR-009-canonical-fhir-client.md`` selector ``frontmatter.id`` |
| ``ADR-101``       | generated_fixture   | ``skills/context-discovery/tests/fixtures/family_adr_discovery/fhir-sdk/docs/adr/ADR-101-local-client-wiring.md`` selector ``frontmatter.id`` |
| ``fhir-management`` | generated_fixture | ``skills/context-discovery/tests/fixtures/family_adr_discovery/fhir-sdk/.adr-governance.json`` selector ``governing_corpora[0].corpus`` |
| ``ADR-014``       | generated_fixture   | ``skills/context-discovery/tests/fixtures/family_adr_discovery/platform/docs/adr/ADR-014-polaris-client-access.md`` selector ``frontmatter.id`` |
| ``ADR-201``       | generated_fixture   | ``skills/context-discovery/tests/fixtures/family_adr_discovery/polaris-adapter-x/docs/adr/ADR-201-adapter-local-mapping.md`` selector ``frontmatter.id`` |
| ``platform``      | generated_fixture   | ``skills/context-discovery/tests/fixtures/family_adr_discovery/polaris-adapter-x/.adr-governance.json`` selector ``governing_corpora[0].corpus`` |
| ``family`` / ``governing`` / ``local`` | worked_example | bd show clc-apby -> Pre-Mortem: precedence explicit, governing family decision visible beside local |
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

_ORIGIN_FIELDS = ("id", "origin", "corpus", "precedence", "path")

_FHIR_EXPECTED_MANIFEST = [
    {
        "id": "ADR-009",
        "origin": "family",
        "corpus": "fhir-management",
        "precedence": "governing",
        "path": "docs/adr/ADR-009-canonical-fhir-client.md",
    },
    {
        "id": "ADR-101",
        "origin": "local",
        "corpus": "local",
        "precedence": "local",
        "path": "docs/adr/ADR-101-local-client-wiring.md",
    },
]

_POLARIS_EXPECTED_MANIFEST = [
    {
        "id": "ADR-014",
        "origin": "family",
        "corpus": "platform",
        "precedence": "governing",
        "path": "docs/adr/ADR-014-polaris-client-access.md",
    },
    {
        "id": "ADR-201",
        "origin": "local",
        "corpus": "local",
        "precedence": "local",
        "path": "docs/adr/ADR-201-adapter-local-mapping.md",
    },
]

_FIXTURES: dict[str, dict[str, Any]] = {
    "fhir-child": {
        "repository": "fhir-sdk",
        "family_repository": "fhir-management",
        "candidate_path": "src/client/canonical_client.py",
        "candidate_body": "def build_client():\n    return None\n",
        "expected_manifest": _FHIR_EXPECTED_MANIFEST,
    },
    "polaris-adapter": {
        "repository": "polaris-adapter-x",
        "family_repository": "platform",
        "candidate_path": "src/adapters/client_access.py",
        "candidate_body": "def read_access():\n    return None\n",
        "expected_manifest": _POLARIS_EXPECTED_MANIFEST,
    },
}


def _load_module(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def context_provider() -> Any:
    return _load_module(_SCRIPTS_DIR / "context_provider.py", "context_provider_family_under_test")


@pytest.fixture()
def context_discovery() -> Any:
    return _load_module(
        _SCRIPTS_DIR / "context_discovery.py", "context_discovery_family_under_test"
    )


def _materialize(tmp_path: Path, spec: dict[str, Any]) -> Path:
    """Copy the child and family fixture repositories into sibling temp paths."""
    repo_root = tmp_path / str(spec["repository"])
    shutil.copytree(_FIXTURE_ROOT / str(spec["repository"]), repo_root)
    shutil.copytree(
        _FIXTURE_ROOT / str(spec["family_repository"]),
        tmp_path / str(spec["family_repository"]),
    )
    candidate = repo_root / str(spec["candidate_path"])
    candidate.parent.mkdir(parents=True, exist_ok=True)
    candidate.write_text(str(spec["candidate_body"]), encoding="utf-8")
    return repo_root


def _install_project_provider(repo_root: Path) -> None:
    """Install the shared provider as the repository-local read-only caller target."""
    destination = repo_root / "skills" / "context-discovery" / "scripts"
    destination.mkdir(parents=True, exist_ok=True)
    shutil.copy2(_SCRIPTS_DIR / "context_provider.py", destination / "context_provider.py")
    shutil.copy2(_SCRIPTS_DIR / "adr-context.py", destination / "adr-context.py")


def _origins(manifest: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{field: entry.get(field) for field in _ORIGIN_FIELDS} for entry in manifest]


def _bead() -> dict[str, Any]:
    return {
        "id": "clc-apby-fixture",
        "title": "Family ADR discovery fixture",
        "description": "",
        "acceptance_criteria": "",
        "metadata": {},
    }


@pytest.mark.parametrize("fixture_name", sorted(_FIXTURES))
def test_build_adr_context_returns_local_and_governing_family_adrs(
    tmp_path: Path, context_provider: Any, fixture_name: str
) -> None:
    spec = _FIXTURES[fixture_name]
    repo_root = _materialize(tmp_path, spec)

    context = context_provider.build_adr_context(
        _bead(), repo_root, [str(spec["candidate_path"])]
    )

    assert context["status"] == "complete"
    assert _origins(context["manifest"]) == spec["expected_manifest"]


@pytest.mark.parametrize("fixture_name", sorted(_FIXTURES))
def test_path_scoped_discovery_returns_same_origins_and_precedence(
    tmp_path: Path, context_discovery: Any, context_provider: Any, fixture_name: str
) -> None:
    spec = _FIXTURES[fixture_name]
    repo_root = _materialize(tmp_path, spec)
    _install_project_provider(repo_root)

    discovered = context_discovery.discover_path_scoped(
        repo_root, [str(spec["candidate_path"])]
    )
    provided = context_provider.build_adr_context(
        context_discovery.synthetic_bead(), repo_root, [str(spec["candidate_path"])]
    )

    assert _origins(discovered["adr_context"]["manifest"]) == spec["expected_manifest"]
    assert _origins(discovered["adr_context"]["manifest"]) == _origins(provided["manifest"])

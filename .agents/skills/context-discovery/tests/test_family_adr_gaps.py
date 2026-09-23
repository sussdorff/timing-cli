"""RED specification for typed family-ADR gaps and conflicts (clc-apby, slice-2).

Slice-1 discovers a declared governing corpus. It stays silent in the two cases
this slice specifies: a declared corpus that does not resolve is skipped with no
gap, and two contradicting accepted decisions are both admitted with a
``complete`` status, leaving the consumer to guess which one wins.

Declared contract under specification
-------------------------------------
Both cases keep the established gap shape ``{code, resolved, ...}`` and a
non-``complete`` status.

``ADR_GOVERNING_CORPUS_MISSING`` — a ``.adr-governance.json`` entry names a
corpus whose ``<workspace_path>/docs/adr`` does not exist. It is distinct from
``ADR_CORPUS_NOT_FOUND``, which records the *accepted* absence of a repository's
own local corpus (``resolved: True``). A declared governing decision that cannot
be read is not acceptable absence, so this gap is ``resolved: False`` and names
the declared ``corpus`` and ``workspace_path`` a consumer must repair.

``ADR_DECISION_CONFLICT`` — two or more applicable ADRs with ``status:
accepted`` declare the same frontmatter ``decides`` topic in different corpora.
The topic key is what makes contradiction declarative rather than prose
guesswork. The gap is ``resolved: False``, names the topic, and lists every
conflicting side with its ``origin``, ``corpus`` and ``id``, sorted by
``(origin, corpus, id)``. Discovery order picks no winner: both sides stay in
the manifest with their own precedence token, and a record that is not
``accepted`` does not become a conflicting side.

Independent expected-value provenance
-------------------------------------
| expected value | source_kind | fixture path / pointer |
|----------------|-------------|------------------------|
| ``fhir-management`` | generated_fixture | ``skills/context-discovery/tests/fixtures/family_adr_discovery/fhir-sdk-missing-family/.adr-governance.json`` selector ``governing_corpora[0].corpus`` |
| ``../fhir-management-missing`` | generated_fixture | ``skills/context-discovery/tests/fixtures/family_adr_discovery/fhir-sdk-missing-family/.adr-governance.json`` selector ``governing_corpora[0].workspace_path`` |
| ``platform`` | generated_fixture | ``skills/context-discovery/tests/fixtures/family_adr_discovery/polaris-adapter-conflict/.adr-governance.json`` selector ``governing_corpora[0].corpus`` |
| ``polaris-client-access`` | generated_fixture | ``skills/context-discovery/tests/fixtures/family_adr_discovery/platform-conflict/docs/adr/ADR-021-platform-client-access.md`` selector ``frontmatter.decides`` |
| ``ADR-021`` | generated_fixture | ``skills/context-discovery/tests/fixtures/family_adr_discovery/platform-conflict/docs/adr/ADR-021-platform-client-access.md`` selector ``frontmatter.id`` |
| ``ADR-221`` | generated_fixture | ``skills/context-discovery/tests/fixtures/family_adr_discovery/polaris-adapter-conflict/docs/adr/ADR-221-direct-connection.md`` selector ``frontmatter.id`` |
| ``ADR_GOVERNING_CORPUS_MISSING`` / ``ADR_DECISION_CONFLICT`` / ``gap`` | worked_example | bd show clc-apby -> AC2: missing declared corpora and contradictory accepted ADRs are typed gaps, not discovery-order resolutions |
| ``family`` / ``local`` / ``governing`` | worked_example | bd show clc-apby -> Pre-Mortem: precedence explicit, governing family decision visible beside local |
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

_MISSING_FAMILY_GAP_CODE = "ADR_GOVERNING_CORPUS_MISSING"
_DECISION_CONFLICT_GAP_CODE = "ADR_DECISION_CONFLICT"

_FIXTURES: dict[str, dict[str, Any]] = {
    "missing-family": {
        "repository": "fhir-sdk-missing-family",
        "family_repository": None,
        "candidate_path": "src/client/canonical_client.py",
        "candidate_body": "def build_client():\n    return None\n",
        "expected_status": "gap",
        "expected_gap_code": _MISSING_FAMILY_GAP_CODE,
    },
    "decision-conflict": {
        "repository": "polaris-adapter-conflict",
        "family_repository": "platform-conflict",
        "candidate_path": "src/adapters/client_access.py",
        "candidate_body": "def read_access():\n    return None\n",
        "expected_status": "gap",
        "expected_gap_code": _DECISION_CONFLICT_GAP_CODE,
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
    return _load_module(_SCRIPTS_DIR / "context_provider.py", "context_provider_gaps_under_test")


@pytest.fixture()
def context_discovery() -> Any:
    return _load_module(
        _SCRIPTS_DIR / "context_discovery.py", "context_discovery_gaps_under_test"
    )


def _materialize(tmp_path: Path, spec: dict[str, Any]) -> Path:
    """Copy the child repository and, when the fixture has one, its family repository."""
    repo_root = tmp_path / str(spec["repository"])
    shutil.copytree(_FIXTURE_ROOT / str(spec["repository"]), repo_root)
    family = spec["family_repository"]
    if family is not None:
        shutil.copytree(_FIXTURE_ROOT / str(family), tmp_path / str(family))
    candidate = repo_root / str(spec["candidate_path"])
    candidate.parent.mkdir(parents=True, exist_ok=True)
    candidate.write_text(str(spec["candidate_body"]), encoding="utf-8")
    return repo_root


def _install_project_provider(repo_root: Path) -> None:
    destination = repo_root / "skills" / "context-discovery" / "scripts"
    destination.mkdir(parents=True, exist_ok=True)
    shutil.copy2(_SCRIPTS_DIR / "context_provider.py", destination / "context_provider.py")
    shutil.copy2(_SCRIPTS_DIR / "adr-context.py", destination / "adr-context.py")


def _gap(gaps: list[dict[str, Any]], code: str) -> dict[str, Any]:
    matching = [gap for gap in gaps if gap.get("code") == code]
    assert len(matching) == 1, f"expected exactly one {code} gap, got {gaps}"
    return matching[0]


def _bead() -> dict[str, Any]:
    return {
        "id": "clc-apby-fixture",
        "title": "Family ADR gap fixture",
        "description": "",
        "acceptance_criteria": "",
        "metadata": {},
    }


def test_missing_declared_governing_corpus_is_a_typed_unresolved_gap(
    tmp_path: Path, context_provider: Any
) -> None:
    spec = _FIXTURES["missing-family"]
    repo_root = _materialize(tmp_path, spec)

    context = context_provider.build_adr_context(
        _bead(), repo_root, [str(spec["candidate_path"])]
    )

    assert context["status"] == "gap"
    gap = _gap(context["gaps"], _MISSING_FAMILY_GAP_CODE)
    assert gap["resolved"] is False
    assert gap["corpus"] == "fhir-management"
    assert gap["workspace_path"] == "../fhir-management-missing"


def test_contradicting_accepted_decisions_are_a_typed_conflict_without_a_winner(
    tmp_path: Path, context_provider: Any
) -> None:
    spec = _FIXTURES["decision-conflict"]
    repo_root = _materialize(tmp_path, spec)

    context = context_provider.build_adr_context(
        _bead(), repo_root, [str(spec["candidate_path"])]
    )

    assert context["status"] == "gap"
    gap = _gap(context["gaps"], _DECISION_CONFLICT_GAP_CODE)
    assert gap["resolved"] is False
    assert gap["topic"] == "polaris-client-access"
    assert gap["conflicts"] == [
        {"origin": "family", "corpus": "platform", "id": "ADR-021"},
        {"origin": "local", "corpus": "local", "id": "ADR-221"},
    ]

    # Neither side is dropped and neither is marked the winner: both keep their
    # own precedence token in the manifest.
    entries = {entry["id"]: entry for entry in context["manifest"]}
    assert entries["ADR-021"]["precedence"] == "governing"
    assert entries["ADR-221"]["precedence"] == "local"


@pytest.mark.parametrize("fixture_name", sorted(_FIXTURES))
def test_path_scoped_discovery_reports_the_same_typed_gaps(
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

    adr_context = discovered["adr_context"]
    assert adr_context["status"] == spec["expected_status"]
    assert [gap["code"] for gap in adr_context["gaps"]] == [
        gap["code"] for gap in provided["gaps"]
    ]
    assert adr_context["gaps"] == provided["gaps"]
    assert _gap(adr_context["gaps"], str(spec["expected_gap_code"]))["resolved"] is False

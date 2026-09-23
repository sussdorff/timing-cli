"""RED specification for clc-apby reviewer findings 1-3: governance hardening.

Three ways the current provider reports a false-clean result. Probed against
the implementation before authoring: finding 1 yields only
``ADR_MANIFEST_TRUNCATED``, and findings 2 and 3 both yield ``complete`` with
no gaps at all.

Declared contract under specification
-------------------------------------
**Finding 1 — conflict detection spans the full applicable set.** Conflicts are
currently computed from the truncated selected set, so a contradiction whose
sides rank below ``ADR_MANIFEST_LIMIT`` disappears behind the truncation gap.
An accepted-decision conflict in the *full* applicable set must still produce
``ADR_DECISION_CONFLICT`` beside ``ADR_MANIFEST_TRUNCATED``, even when neither
side reaches the manifest.

**Finding 2 — one corpus identity may not name two roots.** Two
``governing_corpora`` entries that reuse a ``corpus`` identity for different
``workspace_path`` roots are currently both admitted under that one name, which
also defeats the cross-corpus conflict check, because that check compares
corpus identities. The result is a false ``complete``. A reused identity is a
declaration defect, reported as an unresolved
``ADR_GOVERNING_CORPUS_IDENTITY_COLLISION`` gap naming the duplicate identity
and the colliding roots.

**Finding 3 — a malformed declaration fails closed.** Invalid JSON, an
unsupported ``schema_version`` and an absolute ``workspace_path`` are currently
discarded silently, so a repository that declares governance receives none and
still reports ``complete``. Each is an unresolved
``ADR_GOVERNING_DECLARATION_INVALID`` gap, and the absolute-path case names the
rejected value. An *absent* declaration keeps meaning local-only discovery with
no new gap; that control is already locked by
``test_adr_manifest_uses_complete_candidate_surface_and_is_bounded``, which has
no declaration and asserts ``complete``, so it is not re-authored here.

Independent expected-value provenance
-------------------------------------
Fixtures are generated in ``tmp_path`` by this module, so a generated value's
provenance is the module constant that writes it.

| expected value | source_kind | fixture path / pointer |
|----------------|-------------|------------------------|
| ``ADR_DECISION_CONFLICT`` beside truncation | worked_example | clc-apby reviewer finding 1 (High): conflict detection must run on the full applicable set, not the truncated manifest |
| ``ADR_GOVERNING_CORPUS_IDENTITY_COLLISION`` | worked_example | clc-apby reviewer finding 2 (High): one corpus identity at two roots must not silently merge |
| ``ADR_GOVERNING_DECLARATION_INVALID`` | worked_example | clc-apby reviewer finding 3 (Medium): a malformed governance declaration must fail closed as a typed gap |
| ``gap`` status and ``resolved: False`` | worked_example | bd show clc-apby -> AC2: missing declared corpora and contradictory accepted ADRs are typed gaps, not discovery-order resolutions |
| ``conflict-topic`` | generated_fixture | ``skills/context-discovery/tests/test_family_adr_governance_hardening.py`` selector ``_CONFLICT_TOPIC`` |
| ``ADR-W900`` / ``ADR-W901`` | generated_fixture | ``skills/context-discovery/tests/test_family_adr_governance_hardening.py`` selector ``_LOCAL_CONFLICT_ID`` / ``_FAMILY_CONFLICT_ID`` |
| ``governing-family`` | generated_fixture | ``skills/context-discovery/tests/test_family_adr_governance_hardening.py`` selector ``_FAMILY_CORPUS`` |
| ``shared-identity`` | generated_fixture | ``skills/context-discovery/tests/test_family_adr_governance_hardening.py`` selector ``_DUPLICATE_IDENTITY`` |
| ``/nonexistent/governing-corpus`` | generated_fixture | ``skills/context-discovery/tests/test_family_adr_governance_hardening.py`` selector ``_ABSOLUTE_WORKSPACE_PATH`` |
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any

import pytest


_TESTS_DIR = Path(__file__).resolve().parent
_SKILL_ROOT = _TESTS_DIR.parent
_SCRIPTS_DIR = _SKILL_ROOT / "scripts"

_CANDIDATE_PATH = "src/client/canonical_client.py"
_CANDIDATE_BODY = "def build_client():\n    return None\n"
_ADR_SELECTOR = "src/client"

_CONFLICT_TOPIC = "conflict-topic"
_LOCAL_CONFLICT_ID = "ADR-W900"
_FAMILY_CONFLICT_ID = "ADR-W901"
_FAMILY_CORPUS = "governing-family"

_DUPLICATE_IDENTITY = "shared-identity"
_DUPLICATE_WORKSPACE_PATHS = ["../governing-root-a", "../governing-root-b"]

_ABSOLUTE_WORKSPACE_PATH = "/nonexistent/governing-corpus"

_CONFLICT_GAP_CODE = "ADR_DECISION_CONFLICT"
_TRUNCATION_GAP_CODE = "ADR_MANIFEST_TRUNCATED"
_IDENTITY_COLLISION_GAP_CODE = "ADR_GOVERNING_CORPUS_IDENTITY_COLLISION"
_DECLARATION_INVALID_GAP_CODE = "ADR_GOVERNING_DECLARATION_INVALID"
_UNSAFE_CORPUS_GAP_CODE = "ADR_GOVERNING_CORPUS_OUTSIDE_ROOT"
_UNSAFE_LOCAL_CORPUS_GAP_CODE = "ADR_CORPUS_OUTSIDE_ROOT"


def _load_module(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def context_provider() -> Any:
    return _load_module(
        _SCRIPTS_DIR / "context_provider.py", "context_provider_hardening_under_test"
    )


def _bead() -> dict[str, Any]:
    return {
        "id": "clc-apby-fixture",
        "title": "Governance hardening fixture",
        "description": "",
        "acceptance_criteria": "",
        "metadata": {},
    }


def _write_adr(
    adr_dir: Path,
    adr_id: str,
    *,
    prohibits: bool = True,
    decides: str | None = None,
    status: str = "accepted",
) -> None:
    adr_dir.mkdir(parents=True, exist_ok=True)
    prohibit_block = f'prohibits:\n  - "Do not break {adr_id}."\n' if prohibits else ""
    decides_block = f"decides: {decides}\n" if decides else ""
    (adr_dir / f"{adr_id}-generated.md").write_text(
        f"""---
id: {adr_id}
status: {status}
{decides_block}applies_to:
  - {_ADR_SELECTOR}
decision_summary: "Generated decision {adr_id}."
{prohibit_block}---

# {adr_id}
""",
        encoding="utf-8",
    )


def _child_repository(tmp_path: Path, declaration: str) -> Path:
    """Create a child repository carrying one verbatim governance declaration."""
    repo_root = tmp_path / "generated-child"
    candidate = repo_root / _CANDIDATE_PATH
    candidate.parent.mkdir(parents=True)
    candidate.write_text(_CANDIDATE_BODY, encoding="utf-8")
    (repo_root / ".adr-governance.json").write_text(declaration, encoding="utf-8")
    return repo_root


def _declaration(entries: list[dict[str, str]]) -> str:
    return json.dumps({"schema_version": 1, "governing_corpora": entries}, indent=2)


def _gap(gaps: list[dict[str, Any]], code: str) -> dict[str, Any]:
    matching = [gap for gap in gaps if gap.get("code") == code]
    assert len(matching) == 1, f"expected exactly one {code} gap, got {gaps}"
    return matching[0]


def test_conflict_in_full_applicable_set_survives_manifest_truncation(
    tmp_path: Path, context_provider: Any
) -> None:
    limit = context_provider.ADR_MANIFEST_LIMIT
    repo_root = _child_repository(
        tmp_path,
        _declaration(
            [{"corpus": _FAMILY_CORPUS, "workspace_path": "../governing-family"}]
        ),
    )
    local_adr_dir = repo_root / "docs" / "adr"
    family_adr_dir = tmp_path / "governing-family" / "docs" / "adr"

    # Constraint-bearing filler outranks the conflicting pair, which carries no
    # prohibitions, so truncation drops both sides of the conflict.
    for index in range(limit // 2):
        _write_adr(local_adr_dir, f"ADR-L{index:03d}")
        _write_adr(family_adr_dir, f"ADR-F{index:03d}")
    _write_adr(
        local_adr_dir, _LOCAL_CONFLICT_ID, prohibits=False, decides=_CONFLICT_TOPIC
    )
    _write_adr(
        family_adr_dir, _FAMILY_CONFLICT_ID, prohibits=False, decides=_CONFLICT_TOPIC
    )

    context = context_provider.build_adr_context(
        _bead(), repo_root, [_CANDIDATE_PATH]
    )

    assert context["status"] == "gap"
    assert len(context["manifest"]) == limit
    manifest_ids = {entry["id"] for entry in context["manifest"]}
    assert _LOCAL_CONFLICT_ID not in manifest_ids
    assert _FAMILY_CONFLICT_ID not in manifest_ids

    truncation = _gap(context["gaps"], _TRUNCATION_GAP_CODE)
    assert truncation["omitted_count"] == truncation["discovered_count"] - limit

    conflict = _gap(context["gaps"], _CONFLICT_GAP_CODE)
    assert conflict["resolved"] is False
    assert conflict["topic"] == _CONFLICT_TOPIC
    assert conflict["conflicts"] == [
        {"origin": "family", "corpus": _FAMILY_CORPUS, "id": _FAMILY_CONFLICT_ID},
        {"origin": "local", "corpus": "local", "id": _LOCAL_CONFLICT_ID},
    ]


def test_duplicate_governing_corpus_identity_is_a_typed_collision_gap(
    tmp_path: Path, context_provider: Any
) -> None:
    repo_root = _child_repository(
        tmp_path,
        _declaration(
            [
                {"corpus": _DUPLICATE_IDENTITY, "workspace_path": path}
                for path in _DUPLICATE_WORKSPACE_PATHS
            ]
        ),
    )
    _write_adr(repo_root / "docs" / "adr", "ADR-L001")
    for index, workspace_path in enumerate(_DUPLICATE_WORKSPACE_PATHS):
        corpus_root = (repo_root / workspace_path).resolve()
        _write_adr(
            corpus_root / "docs" / "adr",
            f"ADR-D{index:03d}",
            decides=_CONFLICT_TOPIC,
        )

    context = context_provider.build_adr_context(
        _bead(), repo_root, [_CANDIDATE_PATH]
    )

    assert context["status"] == "gap"
    gap = _gap(context["gaps"], _IDENTITY_COLLISION_GAP_CODE)
    assert gap["resolved"] is False
    assert gap["corpus"] == _DUPLICATE_IDENTITY
    assert gap["workspace_paths"] == sorted(_DUPLICATE_WORKSPACE_PATHS)


def test_direct_family_sibling_governing_corpus_remains_valid(
    tmp_path: Path, context_provider: Any
) -> None:
    family_root = tmp_path / "family-root"
    repo_root = family_root / "declaring-repository"
    candidate = repo_root / _CANDIDATE_PATH
    candidate.parent.mkdir(parents=True)
    candidate.write_text(_CANDIDATE_BODY, encoding="utf-8")
    _write_adr(family_root / "governing-sibling" / "docs" / "adr", "ADR-S001")
    (repo_root / ".adr-governance.json").write_text(
        _declaration(
            [{"corpus": "governing-sibling", "workspace_path": "../governing-sibling"}]
        ),
        encoding="utf-8",
    )

    context = context_provider.build_adr_context(
        _bead(), repo_root, [_CANDIDATE_PATH]
    )

    assert context["status"] == "complete"
    assert {entry["id"] for entry in context["manifest"]} == {"ADR-S001"}
    assert context["manifest"][0]["corpus"] == "governing-sibling"


def test_governing_corpus_rejects_docs_adr_symlink_escape(
    tmp_path: Path, context_provider: Any
) -> None:
    family_root = tmp_path / "family-root"
    repo_root = family_root / "declaring-repository"
    candidate = repo_root / _CANDIDATE_PATH
    candidate.parent.mkdir(parents=True)
    candidate.write_text(_CANDIDATE_BODY, encoding="utf-8")

    corpus_root = family_root / "governing-sibling"
    outside_adr_dir = tmp_path / "outside-family" / "docs" / "adr"
    _write_adr(outside_adr_dir, "ADR-O002")
    (corpus_root / "docs").mkdir(parents=True)
    (corpus_root / "docs" / "adr").symlink_to(
        outside_adr_dir, target_is_directory=True
    )
    (repo_root / ".adr-governance.json").write_text(
        _declaration(
            [{"corpus": "governing-sibling", "workspace_path": "../governing-sibling"}]
        ),
        encoding="utf-8",
    )

    context = context_provider.build_adr_context(
        _bead(), repo_root, [_CANDIDATE_PATH]
    )

    assert context["status"] == "gap"
    gap = _gap(context["gaps"], _UNSAFE_CORPUS_GAP_CODE)
    assert gap["resolved"] is False
    assert gap["corpus"] == "governing-sibling"
    assert gap["workspace_path"] == "../governing-sibling"
    assert all(entry["id"] != "ADR-O002" for entry in context["manifest"])


def test_governing_corpus_rejects_adr_markdown_symlink_escape(
    tmp_path: Path, context_provider: Any
) -> None:
    family_root = tmp_path / "family-root"
    repo_root = family_root / "declaring-repository"
    candidate = repo_root / _CANDIDATE_PATH
    candidate.parent.mkdir(parents=True)
    candidate.write_text(_CANDIDATE_BODY, encoding="utf-8")

    corpus_root = family_root / "governing-sibling"
    adr_dir = corpus_root / "docs" / "adr"
    adr_dir.mkdir(parents=True)
    external_adr = tmp_path / "outside-family" / "external-adr.md"
    external_adr.parent.mkdir(parents=True)
    external_adr.write_text(
        """---
id: ADR-EXTERNAL
status: accepted
applies_to:
  - src/client
decision_summary: EXTERNAL_CONTENT_MUST_NOT_LEAK
---

# External ADR
""",
        encoding="utf-8",
    )
    (adr_dir / "external-adr.md").symlink_to(external_adr)
    (repo_root / ".adr-governance.json").write_text(
        _declaration(
            [{"corpus": "governing-sibling", "workspace_path": "../governing-sibling"}]
        ),
        encoding="utf-8",
    )

    context = context_provider.build_adr_context(
        _bead(), repo_root, [_CANDIDATE_PATH]
    )
    rendered_context = json.dumps(context)

    assert context["status"] == "gap"
    gap = _gap(context["gaps"], _UNSAFE_CORPUS_GAP_CODE)
    assert gap["resolved"] is False
    assert gap["corpus"] == "governing-sibling"
    assert gap["workspace_path"] == "../governing-sibling"
    assert "ADR-EXTERNAL" not in rendered_context
    assert "EXTERNAL_CONTENT_MUST_NOT_LEAK" not in rendered_context
    assert str(external_adr) not in rendered_context


def test_local_corpus_rejects_adr_markdown_symlink_escape(
    tmp_path: Path, context_provider: Any
) -> None:
    repo_root = _child_repository(tmp_path, _declaration([]))
    adr_dir = repo_root / "docs" / "adr"
    adr_dir.mkdir(parents=True)
    external_adr = tmp_path / "outside-family" / "external-adr.md"
    external_adr.parent.mkdir(parents=True)
    external_adr.write_text(
        """---
id: ADR-LOCAL-EXTERNAL
status: accepted
applies_to:
  - src/client
decision_summary: LOCAL_EXTERNAL_CONTENT_MUST_NOT_LEAK
---

# External local ADR
""",
        encoding="utf-8",
    )
    (adr_dir / "external-adr.md").symlink_to(external_adr)

    context = context_provider.build_adr_context(
        _bead(), repo_root, [_CANDIDATE_PATH]
    )
    rendered_context = json.dumps(context)

    assert context["status"] == "gap"
    gap = _gap(context["gaps"], _UNSAFE_LOCAL_CORPUS_GAP_CODE)
    assert gap["resolved"] is False
    assert "ADR-LOCAL-EXTERNAL" not in rendered_context
    assert "LOCAL_EXTERNAL_CONTENT_MUST_NOT_LEAK" not in rendered_context
    assert str(external_adr) not in rendered_context


@pytest.mark.parametrize(
    ("case", "workspace_path", "uses_symlink"),
    [
        ("parent-traversal", "../../outside-family", False),
        ("sibling-symlink-escape", "../sibling-link", True),
    ],
)
def test_governing_corpus_must_resolve_to_direct_family_sibling(
    tmp_path: Path,
    context_provider: Any,
    case: str,
    workspace_path: str,
    uses_symlink: bool,
) -> None:
    family_root = tmp_path / "family-root"
    repo_root = family_root / "declaring-repository"
    candidate = repo_root / _CANDIDATE_PATH
    candidate.parent.mkdir(parents=True)
    candidate.write_text(_CANDIDATE_BODY, encoding="utf-8")

    outside = tmp_path / "outside-family"
    _write_adr(outside / "docs" / "adr", "ADR-O001")
    if uses_symlink:
        (family_root / "sibling-link").symlink_to(outside, target_is_directory=True)

    (repo_root / ".adr-governance.json").write_text(
        _declaration([{"corpus": "outside", "workspace_path": workspace_path}]),
        encoding="utf-8",
    )

    context = context_provider.build_adr_context(
        _bead(), repo_root, [_CANDIDATE_PATH]
    )

    assert context["status"] == "gap", case
    gap = _gap(context["gaps"], _DECLARATION_INVALID_GAP_CODE)
    assert gap["resolved"] is False
    assert gap["reason"] == "workspace_path_is_not_direct_sibling"
    assert gap["corpus"] == "outside"
    assert gap["workspace_path"] == workspace_path
    assert all(entry["corpus"] != "outside" for entry in context["manifest"])


@pytest.mark.parametrize(
    ("case", "declaration", "expected_fields"),
    [
        ("invalid-json", '{"schema_version": 1, "governing_corpora": [', {}),
        (
            "unsupported-schema",
            json.dumps(
                {
                    "schema_version": 99,
                    "governing_corpora": [
                        {"corpus": "governing-family", "workspace_path": "../governing-family"}
                    ],
                }
            ),
            {},
        ),
        (
            "absolute-workspace-path",
            json.dumps(
                {
                    "schema_version": 1,
                    "governing_corpora": [
                        {"corpus": "governing-family", "workspace_path": _ABSOLUTE_WORKSPACE_PATH}
                    ],
                }
            ),
            {"workspace_path": _ABSOLUTE_WORKSPACE_PATH},
        ),
    ],
    ids=["invalid-json", "unsupported-schema", "absolute-workspace-path"],
)
def test_malformed_governance_declaration_is_a_typed_unresolved_gap(
    tmp_path: Path,
    context_provider: Any,
    case: str,
    declaration: str,
    expected_fields: dict[str, str],
) -> None:
    repo_root = _child_repository(tmp_path, declaration)
    _write_adr(repo_root / "docs" / "adr", "ADR-L001")

    context = context_provider.build_adr_context(
        _bead(), repo_root, [_CANDIDATE_PATH]
    )

    assert context["status"] == "gap"
    gap = _gap(context["gaps"], _DECLARATION_INVALID_GAP_CODE)
    assert gap["resolved"] is False
    for field, value in expected_fields.items():
        assert gap[field] == value

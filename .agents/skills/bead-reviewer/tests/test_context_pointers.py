"""
Tests for Context Pointers parsing and review behavior.

Covers:
- Valid pointers parse to a CLEAN review
- Nonexistent pointer paths produce warning findings
- Factory-ready markers require a Context Pointers block
- Non-factory beads without pointers receive an advisory only
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
from textwrap import dedent


REPO_ROOT = Path(__file__).resolve().parents[3]
HELPER_SCRIPT = (
    REPO_ROOT / "skills" / "bead-reviewer" / "scripts" / "context_pointers.py"
)

VALID_DESCRIPTION = """## Goal

Keep Phase 1 context gathering deterministic.

## Context Pointers
primary_files:
  - agents/bead-implementer.md
  agents/bead-change-reviewer.md
  - skills/bead-reviewer/SKILL.md
test_files:
  tests/test_bead_reviewer_cache_gate.py
  - skills/bead-reviewer/tests/test_context_pointers.py
symbols:
  - bead_reviewer_gate
  review_context_pointers
  - parse_context_pointers_block
  Context Pointers
memory_search: "context pointers factory ready"

## Notes

These pointers should be treated as the canonical context list.
"""


def _load_module():
    spec = importlib.util.spec_from_file_location("context_pointers", HELPER_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _make_bead(
    description: str,
    *,
    labels: list[str] | None = None,
    metadata: dict | None = None,
) -> dict:
    return {
        "id": "clc-erb-test",
        "title": "Context pointers test bead",
        "description": description,
        "labels": labels or [],
        "metadata": metadata or {},
    }


class TestContextPointersReview:
    """Unit tests for the deterministic Context Pointers helper."""

    def test_valid_pointers_parse_to_clean(self) -> None:
        assert HELPER_SCRIPT.exists(), (
            "skills/bead-reviewer/scripts/context_pointers.py must exist "
            f"at {HELPER_SCRIPT}"
        )
        mod = _load_module()

        parsed = mod.parse_context_pointers_block(VALID_DESCRIPTION)
        review = mod.review_context_pointers(
            _make_bead(VALID_DESCRIPTION),
            repo_root=REPO_ROOT,
        )

        assert parsed is not None
        assert parsed["primary_files"] == [
            "agents/bead-implementer.md",
            "agents/bead-change-reviewer.md",
            "skills/bead-reviewer/SKILL.md",
        ]
        assert parsed["test_files"] == [
            "tests/test_bead_reviewer_cache_gate.py",
            "skills/bead-reviewer/tests/test_context_pointers.py",
        ]
        assert parsed["symbols"] == [
            "bead_reviewer_gate",
            "review_context_pointers",
            "parse_context_pointers_block",
            "Context Pointers",
        ]
        assert parsed["memory_search"] == "context pointers factory ready"
        assert review["verdict"] == "CLEAN"
        assert review["pointers"] == parsed
        assert review["findings"] == []

    def test_nonexistent_path_produces_warning_finding(self) -> None:
        mod = _load_module()
        description = VALID_DESCRIPTION.replace(
            "agents/bead-change-reviewer.md",
            "agents/does-not-exist.md",
        )

        review = mod.review_context_pointers(
            _make_bead(description),
            repo_root=REPO_ROOT,
        )

        assert review["verdict"] == "FINDING"
        assert any(
            finding["code"] == "CONTEXT_POINTER_PATH_NOT_FOUND"
            and finding["path"] == "agents/does-not-exist.md"
            and finding["severity"] == "warning"
            for finding in review["findings"]
        )

    def test_parser_ignores_non_indented_prose_inside_block(self) -> None:
        mod = _load_module()
        description = """## Goal

Keep Phase 1 context gathering deterministic.

## Context Pointers
primary_files:
  - agents/bead-implementer.md
This explanatory sentence is not a list item.
test_files:
  - skills/bead-reviewer/tests/test_context_pointers.py
symbols:
  - review_context_pointers
memory_search: "context pointers prose guard"

## Notes

Context collection should not treat prose as a file path.
"""

        parsed = mod.parse_context_pointers_block(description)
        review = mod.review_context_pointers(
            _make_bead(description),
            repo_root=REPO_ROOT,
        )

        assert parsed is not None
        assert parsed["primary_files"] == ["agents/bead-implementer.md"]
        assert review["verdict"] == "CLEAN"
        assert review["findings"] == []

    def test_factory_ready_without_pointers_blocks(self) -> None:
        mod = _load_module()
        bead_without_pointers = _make_bead("## Goal\n\nNo context pointers yet.")
        label_review = mod.review_context_pointers(
            _make_bead(
                bead_without_pointers["description"],
                labels=["factory:ready"],
            ),
            repo_root=REPO_ROOT,
        )
        metadata_review = mod.review_context_pointers(
            _make_bead(
                bead_without_pointers["description"],
                metadata={"factory_ready": True},
            ),
            repo_root=REPO_ROOT,
        )

        assert label_review["verdict"] == "BLOCKING"
        assert metadata_review["verdict"] == "BLOCKING"
        assert label_review["pointers"] is None
        assert metadata_review["pointers"] is None
        assert all(
            finding["code"] == "MISSING_CONTEXT_POINTERS"
            for finding in label_review["findings"] + metadata_review["findings"]
        )

    def test_non_factory_bead_without_pointers_is_advisory(self) -> None:
        mod = _load_module()

        review = mod.review_context_pointers(
            _make_bead("## Goal\n\nNo context pointers yet."),
            repo_root=REPO_ROOT,
        )

        assert review["verdict"] == "ADVISORY"
        assert review["pointers"] is None
        assert review["findings"] == [
            {
                "code": "MISSING_CONTEXT_POINTERS",
                "severity": "advisory",
                "message": (
                    "No `## Context Pointers` block found; fall back to dynamic "
                    "context discovery."
                ),
            }
        ]

    def test_absolute_path_rejected_as_invalid(self, tmp_path: Path) -> None:
        """Absolute paths are not valid repo-relative pointers — must produce a warning."""
        mod = _load_module()
        description = dedent(
            """\
            ## Context Pointers
            primary_files:
              - /etc/passwd
            """
        )
        result = mod.review_context_pointers(
            _make_bead(description),
            repo_root=str(tmp_path),
        )
        # Block is found (was parsed), but absolute path is rejected as invalid
        assert result["verdict"] in ("FINDING", "CLEAN"), f"Unexpected verdict: {result['verdict']}"
        # /etc/passwd resolves outside the tmp_path repo root — must warn
        assert any(
            f["code"] == "CONTEXT_POINTER_PATH_NOT_FOUND"
            for f in result["findings"]
        ), f"Expected CONTEXT_POINTER_PATH_NOT_FOUND for absolute path, got: {result['findings']}"
        # Absolute path must NOT appear in sanitized pointers
        assert "/etc/passwd" not in (result["pointers"] or {}).get("primary_files", [])

    def test_path_traversal_escape_rejected(self, tmp_path: Path) -> None:
        """Relative paths that escape the repo root via ../ must be rejected."""
        mod = _load_module()
        description = dedent(
            """\
            ## Context Pointers
            primary_files:
              - ../sibling-repo/secret.txt
            """
        )
        result = mod.review_context_pointers(
            _make_bead(description),
            repo_root=str(tmp_path),
        )
        assert result["verdict"] == "FINDING", (
            f"Traversal path should produce FINDING, got {result['verdict']}"
        )
        assert any(
            f["code"] == "CONTEXT_POINTER_PATH_ESCAPE"
            for f in result["findings"]
        ), f"Expected CONTEXT_POINTER_PATH_ESCAPE finding, got: {result['findings']}"
        # Escape path must NOT appear in sanitized pointers
        assert "../sibling-repo/secret.txt" not in (result["pointers"] or {}).get(
            "primary_files", []
        )

    def test_safe_nonexistent_path_included_in_sanitized_pointers(self, tmp_path: Path) -> None:
        """Paths that are within the repo but don't exist yet stay in sanitized pointers."""
        mod = _load_module()
        description = dedent(
            """\
            ## Context Pointers
            primary_files:
              - src/to-be-created.py
            """
        )
        result = mod.review_context_pointers(
            _make_bead(description),
            repo_root=str(tmp_path),
        )
        # Warning finding for missing file
        assert any(
            f["code"] == "CONTEXT_POINTER_PATH_NOT_FOUND"
            for f in result["findings"]
        )
        # But the path IS in sanitized pointers (safe, just not yet present)
        assert "src/to-be-created.py" in (result["pointers"] or {}).get("primary_files", [])

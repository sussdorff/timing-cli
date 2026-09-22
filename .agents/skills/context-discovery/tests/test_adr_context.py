"""
Tests for CCP-2n67: adr-context.py discover/inject/verify modes.

Verifies:
1. discover correctly filters ADRs based on applies_to globs and changed paths
2. inject produces a markdown block ≤ 2KB per ADR (Decision + Prohibitions + path)
3. verify re-discovers from diff and ignores caller-supplied provenance
4. All modes emit execution-result envelope where applicable
5. parse_adr_frontmatter correctly parses required fields
"""
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Import the script module directly (PEP 723 scripts are importable if we
# add the directory to sys.path and strip the shebang/PEP-723 metadata)
# ---------------------------------------------------------------------------

SKILL_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = SKILL_ROOT.parents[1]
SCRIPT_PATH = SKILL_ROOT / "scripts" / "adr-context.py"
FIXTURES_DIR = REPO_ROOT / "tests" / "fixtures" / "adr_context"


def _load_adr_context():
    """Load adr-context.py as a module, stripping PEP-723 header lines.

    pyyaml must be installed in the test environment (e.g. via `uv run pytest`
    which resolves the PEP-723 dependencies, or by listing pyyaml as a dev
    dependency). If pyyaml is missing this will raise ImportError with a clear
    message — do not probe hardcoded site-packages paths.
    """
    import yaml as _yaml_mod  # noqa: PLC0415

    source = SCRIPT_PATH.read_text()
    # Strip shebang + PEP-723 inline script metadata block so Python can parse it
    lines = source.splitlines()
    filtered: list[str] = []
    in_meta = False
    for line in lines:
        if line.startswith("#!"):
            filtered.append("")
            continue
        if line.strip() == "# /// script":
            in_meta = True
            filtered.append("")
            continue
        if in_meta:
            filtered.append("")
            if line.strip() == "# ///":
                in_meta = False
            continue
        filtered.append(line)
    cleaned = "\n".join(filtered)
    # Build a minimal module namespace with yaml pre-injected
    module_ns: dict = {"__name__": "adr_context", "__file__": str(SCRIPT_PATH), "yaml": _yaml_mod}
    exec(compile(cleaned, str(SCRIPT_PATH), "exec"), module_ns)  # noqa: S102
    # Wrap dict as a simple namespace object so attribute access works
    import types  # noqa: PLC0415
    module = types.SimpleNamespace(**module_ns)
    return module


@pytest.fixture(scope="module")
def adr_mod():
    return _load_adr_context()


@pytest.fixture()
def tmp_adr_dir(tmp_path: Path) -> Path:
    """Copy fixture ADRs into a temporary directory."""
    import shutil
    dest = tmp_path / "adr"
    dest.mkdir()
    for f in FIXTURES_DIR.glob("*.md"):
        shutil.copy(f, dest / f.name)
    return dest


# ---------------------------------------------------------------------------
# TestParseFrontmatter
# ---------------------------------------------------------------------------


class TestParseFrontmatter:
    def test_parses_required_fields(self, adr_mod, tmp_adr_dir: Path):
        adr_file = tmp_adr_dir / "adr_alpha.md"
        result = adr_mod.parse_adr_frontmatter(adr_file)
        assert result["id"] == "ADR-alpha"
        assert result["decision_summary"] == (
            "All subprocess invocations must go through CommandRunner to enable testing and auditing."
        )
        assert "scripts/*.py" in result["applies_to"]
        assert "core/**/*.py" in result["applies_to"]
        assert any("CommandRunner" in p for p in result["prohibits"])
        assert result["path"] == str(adr_file)

    def test_returns_none_for_no_frontmatter(self, adr_mod, tmp_path: Path):
        f = tmp_path / "no_frontmatter.md"
        f.write_text("# Plain markdown\nNo YAML here.\n")
        result = adr_mod.parse_adr_frontmatter(f)
        assert result is None

    def test_derives_numeric_id_from_canonical_filename(self, adr_mod, tmp_path: Path):
        """Polaris ADRs identify the contract in YAML and the ADR in the filename."""
        f = tmp_path / "ADR-046-capability-catalog.md"
        f.write_text(
            """---
status: accepted
contract: capability-catalog
applies_to: [packages]
prohibits:
  - "No decorative capability declarations"
decision_summary: "Capabilities are executable registry projections."
---

# ADR-046
""",
            encoding="utf-8",
        )

        result = adr_mod.parse_adr_frontmatter(f)

        assert result is not None
        assert result["id"] == "ADR-046"
        assert result["contract"] == "capability-catalog"
        assert result["prohibits"] == ["No decorative capability declarations"]

    def test_explicit_id_takes_precedence_over_filename(self, adr_mod, tmp_path: Path):
        f = tmp_path / "adr-capability-catalog.md"
        f.write_text(
            """---
id: ADR-explicit
contract: capability-catalog
---
""",
            encoding="utf-8",
        )

        result = adr_mod.parse_adr_frontmatter(f)

        assert result is not None
        assert result["id"] == "ADR-explicit"

    def test_contract_slug_precedes_non_numeric_filename(self, adr_mod, tmp_path: Path):
        f = tmp_path / "adr-draft-name.md"
        f.write_text(
            """---
contract: capability-catalog
---
""",
            encoding="utf-8",
        )

        result = adr_mod.parse_adr_frontmatter(f)

        assert result is not None
        assert result["id"] == "adr-capability-catalog"

    def test_contract_with_adr_prefix_is_not_double_prefixed(self, adr_mod, tmp_path: Path):
        f = tmp_path / "adr-draft-name.md"
        f.write_text("---\ncontract: adr-capability-catalog\n---\n", encoding="utf-8")

        result = adr_mod.parse_adr_frontmatter(f)

        assert result is not None
        assert result["id"] == "adr-capability-catalog"

    def test_falls_back_to_canonical_non_numeric_filename(self, adr_mod, tmp_path: Path):
        f = tmp_path / "adr-billing-conformance-boundary.md"
        f.write_text("---\nstatus: proposed\n---\n", encoding="utf-8")

        result = adr_mod.parse_adr_frontmatter(f)

        assert result is not None
        assert result["id"] == "adr-billing-conformance-boundary"

    @pytest.mark.parametrize(
        "filename",
        ["capability-catalog.md", "notes-for-ADR-046.md", "ADR-capability-catalog.md"],
    )
    def test_missing_identity_sources_fail_closed(
        self,
        adr_mod,
        tmp_path: Path,
        filename: str,
    ):
        f = tmp_path / filename
        f.write_text("---\nstatus: accepted\n---\n", encoding="utf-8")

        assert adr_mod.parse_adr_frontmatter(f) is None

    @pytest.mark.parametrize(
        "invalid_contract",
        ["Capability-Catalog", "capability_catalog", '" capability-catalog"', '""', "[]"],
    )
    def test_invalid_contract_fails_closed(
        self,
        adr_mod,
        tmp_path: Path,
        invalid_contract: str,
    ):
        f = tmp_path / "adr-capability-catalog.md"
        f.write_text(f"---\ncontract: {invalid_contract}\n---\n", encoding="utf-8")

        assert adr_mod.parse_adr_frontmatter(f) is None

    def test_malformed_frontmatter_still_fails_closed(self, adr_mod, tmp_path: Path):
        f = tmp_path / "ADR-046-capability-catalog.md"
        f.write_text("---\ncontract: [unterminated\n---\n", encoding="utf-8")

        assert adr_mod.parse_adr_frontmatter(f) is None

    @pytest.mark.parametrize("yaml_root", ["- contract", "capability-catalog"])
    def test_non_mapping_frontmatter_fails_closed(
        self,
        adr_mod,
        tmp_path: Path,
        yaml_root: str,
    ):
        f = tmp_path / "ADR-046-capability-catalog.md"
        f.write_text(f"---\n{yaml_root}\n---\n", encoding="utf-8")

        assert adr_mod.parse_adr_frontmatter(f) is None

    @pytest.mark.parametrize("invalid_id", ['""', "[]", "42", "null"])
    def test_invalid_explicit_id_does_not_fall_back_to_filename(
        self,
        adr_mod,
        tmp_path: Path,
        invalid_id: str,
    ):
        f = tmp_path / "ADR-046-capability-catalog.md"
        f.write_text(
            f"---\nid: {invalid_id}\ncontract: capability-catalog\n---\n",
            encoding="utf-8",
        )

        assert adr_mod.parse_adr_frontmatter(f) is None

    def test_duplicate_contract_identities_fail_loudly(self, adr_mod, tmp_path: Path):
        adr_dir = tmp_path / "adr"
        adr_dir.mkdir()
        for filename in ("adr-first.md", "adr-second.md"):
            (adr_dir / filename).write_text(
                "---\ncontract: conformance-axis-modules\n---\n",
                encoding="utf-8",
            )

        with pytest.raises(adr_mod.AdrIdentityCollisionError, match="adr-conformance-axis-modules"):
            adr_mod._load_adrs(adr_dir)

    def test_duplicate_normalized_contract_forms_fail_loudly(self, adr_mod, tmp_path: Path):
        adr_dir = tmp_path / "adr"
        adr_dir.mkdir()
        (adr_dir / "adr-first.md").write_text(
            "---\ncontract: conformance-axis-modules\n---\n",
            encoding="utf-8",
        )
        (adr_dir / "adr-second.md").write_text(
            "---\ncontract: adr-conformance-axis-modules\n---\n",
            encoding="utf-8",
        )

        with pytest.raises(adr_mod.AdrIdentityCollisionError):
            adr_mod._load_adrs(adr_dir)


# ---------------------------------------------------------------------------
# TestDiscoverAdrs
# ---------------------------------------------------------------------------


class TestDiscoverAdrs:
    @pytest.mark.parametrize(
        "selector",
        [
            "packages/pvs-x-isynet",
            "packages/pvs-x-isynet/",
            "packages/pvs-x-isynet/**",
        ],
    )
    def test_package_directory_and_glob_selectors_match_descendants(
        self, adr_mod, tmp_path: Path, selector: str
    ):
        adr_dir = tmp_path / "adr"
        adr_dir.mkdir()
        (adr_dir / "ADR-057-production-data.md").write_text(
            f"""---
id: ADR-057
applies_to:
  - {selector}
decision_summary: "Production bindings remain explicit."
prohibits:
  - "Do not hide binding data."
---
""",
            encoding="utf-8",
        )

        results = adr_mod.discover_adrs(
            adr_dir=adr_dir,
            changed_paths=[
                "packages/pvs-x-isynet/src/mappers/schein-mapper.ts"
            ],
            bead_description_override=None,
        )

        assert [result["id"] for result in results] == ["ADR-057"]
        assert results[0]["match_reasons"] == [f"path:{selector}"]

    def test_regression_blank_package_selector_matches_workspace_package(
        self, adr_mod, tmp_path: Path
    ):
        """clc-u883: documented blank selectors like `pvs-x-isynet` must match
        descendants of the real `packages/<selector>` workspace directory, while
        avoiding basename heuristics for unrelated paths.
        """
        repo_root = tmp_path
        package_dir = repo_root / "packages" / "pvs-x-isynet"
        package_dir.mkdir(parents=True)
        adr_dir = repo_root / "docs" / "adr"
        adr_dir.mkdir(parents=True)
        (adr_dir / "ADR-057-production-data.md").write_text(
            """---
id: ADR-057
applies_to:
  - pvs-x-isynet
decision_summary: "Production bindings remain explicit."
prohibits:
  - "Do not hide binding data."
---
""",
            encoding="utf-8",
        )

        candidate = "packages/pvs-x-isynet/src/mappers/schein-mapper.ts"
        results = adr_mod.discover_adrs(
            adr_dir=adr_dir,
            changed_paths=[candidate],
            bead_description_override=None,
        )
        assert [result["id"] for result in results] == ["ADR-057"]
        assert results[0]["match_reasons"] == ["path:pvs-x-isynet"]

        # Explicit directory and glob controls remain intact beside blank tokens.
        for selector in (
            "packages/pvs-x-isynet",
            "packages/pvs-x-isynet/**",
        ):
            assert adr_mod._matches_glob(
                candidate, selector, repo_root=repo_root
            ) is True

        # Missing workspace package must not invent a match.
        assert (
            adr_mod._matches_glob(
                "packages/missing-pkg/src/file.ts",
                "missing-pkg",
                repo_root=repo_root,
            )
            is False
        )
        # Basename heuristic must not match unrelated trees.
        assert (
            adr_mod._matches_glob(
                "vendor/pvs-x-isynet/src/file.ts",
                "pvs-x-isynet",
                repo_root=repo_root,
            )
            is False
        )

    def test_returns_matching_adr_by_glob(self, adr_mod, tmp_adr_dir: Path):
        """Changed path scripts/foo.py matches only ADR-alpha (scripts/*.py)."""
        results = adr_mod.discover_adrs(
            adr_dir=tmp_adr_dir,
            changed_paths=["scripts/foo.py"],
            bead_description_override=None,
        )
        ids = [r["id"] for r in results]
        assert "ADR-alpha" in ids
        assert "ADR-beta" not in ids
        assert "ADR-gamma" not in ids

    def test_no_match_returns_empty(self, adr_mod, tmp_adr_dir: Path):
        """Changed path that matches no ADR applies_to glob returns empty list."""
        results = adr_mod.discover_adrs(
            adr_dir=tmp_adr_dir,
            changed_paths=["unrelated/file.ts"],
            bead_description_override=None,
        )
        assert results == []

    def test_text_match_from_bead_description(self, adr_mod, tmp_adr_dir: Path):
        """Bead description containing 'ADR-alpha' includes that ADR even without path match."""
        results = adr_mod.discover_adrs(
            adr_dir=tmp_adr_dir,
            changed_paths=["unrelated/file.ts"],
            bead_description_override="This bead relates to ADR-alpha compliance.",
        )
        ids = [r["id"] for r in results]
        assert "ADR-alpha" in ids
        assert "ADR-beta" not in ids

    def test_text_matches_id_derived_from_filename(self, adr_mod, tmp_path: Path):
        adr_dir = tmp_path / "adr"
        adr_dir.mkdir()
        (adr_dir / "ADR-046-capability-catalog.md").write_text(
            """---
status: accepted
contract: capability-catalog
applies_to: []
prohibits:
  - "No decorative capability declarations"
decision_summary: "Capabilities are executable registry projections."
---
""",
            encoding="utf-8",
        )

        results = adr_mod.discover_adrs(
            adr_dir=adr_dir,
            changed_paths=[],
            bead_description_override="Implementation must conform to ADR-046.",
        )

        assert [result["id"] for result in results] == ["ADR-046"]

    def test_discovers_both_non_numeric_contract_adrs_by_text(self, adr_mod, tmp_path: Path):
        adr_dir = tmp_path / "adr"
        adr_dir.mkdir()
        contracts = {
            "adr-conformance-axis-modules.md": "conformance-axis-modules",
            "adr-billing-conformance-boundary.md": "billing-conformance-boundary",
        }
        for filename, contract in contracts.items():
            (adr_dir / filename).write_text(
                f"""---
contract: {contract}
applies_to: [packages/**]
decision_summary: "{contract} decision"
prohibits:
  - "No violation of {contract}"
---
""",
                encoding="utf-8",
            )

        results = adr_mod.discover_adrs(
            adr_dir=adr_dir,
            changed_paths=[],
            bead_description_override=(
                "Follow adr-conformance-axis-modules and adr-billing-conformance-boundary."
            ),
        )

        assert [result["id"] for result in results] == [
            "adr-billing-conformance-boundary",
            "adr-conformance-axis-modules",
        ]

    def test_deduplicates_path_and_text_match(self, adr_mod, tmp_adr_dir: Path):
        """ADR matched by both path and text appears only once."""
        results = adr_mod.discover_adrs(
            adr_dir=tmp_adr_dir,
            changed_paths=["scripts/foo.py"],
            bead_description_override="References ADR-alpha again.",
        )
        ids = [r["id"] for r in results]
        assert ids.count("ADR-alpha") == 1

    def test_match_reason_path(self, adr_mod, tmp_adr_dir: Path):
        """Path-matched ADR has match_reason containing 'path'."""
        results = adr_mod.discover_adrs(
            adr_dir=tmp_adr_dir,
            changed_paths=["scripts/foo.py"],
            bead_description_override=None,
        )
        assert any("path" in r["match_reason"] for r in results)

    def test_match_reason_text(self, adr_mod, tmp_adr_dir: Path):
        """Text-matched ADR has match_reason containing 'text'."""
        results = adr_mod.discover_adrs(
            adr_dir=tmp_adr_dir,
            changed_paths=[],
            bead_description_override="ADR-beta is important",
        )
        beta = next((r for r in results if r["id"] == "ADR-beta"), None)
        assert beta is not None
        assert "text" in beta["match_reason"]

    def test_glob_matches_direct_children_for_double_star(self, adr_mod, tmp_adr_dir: Path):
        """Regression: ADR-alpha applies_to=['core/**/*.py'] must match core/foo.py.

        Previously _matches_glob delegated to PurePosixPath.match, which in
        Python 3.12 only matches `**` against exactly one segment — so direct
        children like `core/foo.py` and deeply nested children like
        `core/a/b/foo.py` were both skipped, missing real ADR violations.
        """
        # Direct child (zero `**` segments)
        results = adr_mod.discover_adrs(
            adr_dir=tmp_adr_dir,
            changed_paths=["core/foo.py"],
            bead_description_override=None,
        )
        ids = [r["id"] for r in results]
        assert "ADR-alpha" in ids, (
            "ADR-alpha (applies_to: core/**/*.py) must match direct child core/foo.py"
        )
        # Multi-segment child (2+ `**` segments)
        results_deep = adr_mod.discover_adrs(
            adr_dir=tmp_adr_dir,
            changed_paths=["core/a/b/foo.py"],
            bead_description_override=None,
        )
        ids_deep = [r["id"] for r in results_deep]
        assert "ADR-alpha" in ids_deep, (
            "ADR-alpha (applies_to: core/**/*.py) must match deeply nested core/a/b/foo.py"
        )

    def test_loads_adrs_recursively(self, adr_mod, tmp_path: Path):
        """Regression: _load_adrs must walk subdirectories (rglob, not glob)."""
        nested = tmp_path / "adr" / "subdir"
        nested.mkdir(parents=True)
        # Copy fixture into a nested directory
        import shutil
        shutil.copy(FIXTURES_DIR / "adr_alpha.md", nested / "adr_alpha.md")
        results = adr_mod.discover_adrs(
            adr_dir=tmp_path / "adr",
            changed_paths=["scripts/foo.py"],
            bead_description_override=None,
        )
        ids = [r["id"] for r in results]
        assert "ADR-alpha" in ids, "ADR in subdirectory must be discovered (recursive load)"

    def test_envelope_structure(self, adr_mod, tmp_adr_dir: Path):
        """discover_adrs_envelope emits valid execution-result envelope."""
        envelope = adr_mod.discover_adrs_envelope(
            adr_dir=tmp_adr_dir,
            changed_paths=["scripts/foo.py"],
            bead_description_override=None,
        )
        assert envelope["status"] in ("ok", "warning", "error")
        assert "summary" in envelope
        assert "data" in envelope
        assert "adrs_in_scope" in envelope["data"]
        assert "errors" in envelope
        assert "next_steps" in envelope
        assert "open_items" in envelope
        assert "meta" in envelope
        assert envelope["meta"]["producer"] == "adr-context.py"


# ---------------------------------------------------------------------------
# TestInjectAdrs
# ---------------------------------------------------------------------------


class TestInjectAdrs:
    def test_produces_markdown_block(self, adr_mod, tmp_adr_dir: Path):
        envelope = adr_mod.inject_adrs_envelope(
            adr_dir=tmp_adr_dir,
            changed_paths=["scripts/foo.py"],
            bead_description_override=None,
        )
        md = envelope["data"]["markdown"]
        assert "## ADR Constraints" in md
        assert "ADR-alpha" in md

    def test_each_adr_under_2kb(self, adr_mod, tmp_adr_dir: Path):
        """Each individual ADR block in the injected markdown must be ≤ 2048 chars."""
        envelope = adr_mod.inject_adrs_envelope(
            adr_dir=tmp_adr_dir,
            changed_paths=["scripts/foo.py", "docs/something.md"],
            bead_description_override=None,
        )
        md: str = envelope["data"]["markdown"]
        # Split on ADR headings and check each section
        import re
        sections = re.split(r"(?=### ADR-)", md)
        for section in sections:
            if section.startswith("### ADR-"):
                assert len(section) <= 2048, f"ADR block too long ({len(section)} chars)"

    def test_empty_when_no_match(self, adr_mod, tmp_adr_dir: Path):
        """No ADRs in scope → message saying no ADRs."""
        envelope = adr_mod.inject_adrs_envelope(
            adr_dir=tmp_adr_dir,
            changed_paths=["unrelated/file.ts"],
            bead_description_override=None,
        )
        md: str = envelope["data"]["markdown"]
        assert "No ADRs in scope" in md

    def test_includes_prohibitions(self, adr_mod, tmp_adr_dir: Path):
        envelope = adr_mod.inject_adrs_envelope(
            adr_dir=tmp_adr_dir,
            changed_paths=["scripts/foo.py"],
            bead_description_override=None,
        )
        md: str = envelope["data"]["markdown"]
        assert "CommandRunner" in md

    def test_includes_prohibitions_for_filename_derived_id(self, adr_mod, tmp_path: Path):
        adr_dir = tmp_path / "adr"
        adr_dir.mkdir()
        adr_path = adr_dir / "ADR-046-capability-catalog.md"
        adr_path.write_text(
            """---
status: accepted
contract: capability-catalog
applies_to: [packages/**]
prohibits:
  - "No decorative capability declarations"
decision_summary: "Capabilities are executable registry projections."
---
""",
            encoding="utf-8",
        )

        envelope = adr_mod.inject_adrs_envelope(
            adr_dir=adr_dir,
            changed_paths=["packages/adapter/src/registry.ts"],
            bead_description_override=None,
        )

        assert envelope["status"] == "ok"
        assert "### ADR-046" in envelope["data"]["markdown"]
        assert "No decorative capability declarations" in envelope["data"]["markdown"]
        assert str(adr_path) in envelope["data"]["markdown"]

    def test_injects_contract_derived_conformance_axis_prohibitions(
        self,
        adr_mod,
        tmp_path: Path,
    ):
        adr_dir = tmp_path / "adr"
        adr_dir.mkdir()
        (adr_dir / "adr-conformance-axis-modules.md").write_text(
            """---
contract: conformance-axis-modules
applies_to: [packages/billing-conformance/**]
decision_summary: "Axis modules own conformance evaluation."
prohibits:
  - "regime-specific conformance evaluation outside axis modules"
---
""",
            encoding="utf-8",
        )

        envelope = adr_mod.inject_adrs_envelope(
            adr_dir=adr_dir,
            changed_paths=["packages/billing-conformance/src/evaluate.ts"],
            bead_description_override=None,
        )

        markdown = envelope["data"]["markdown"]
        assert "### adr-conformance-axis-modules" in markdown
        assert "regime-specific conformance evaluation outside axis modules" in markdown

    def test_envelope_ok_status(self, adr_mod, tmp_adr_dir: Path):
        envelope = adr_mod.inject_adrs_envelope(
            adr_dir=tmp_adr_dir,
            changed_paths=["scripts/foo.py"],
            bead_description_override=None,
        )
        assert envelope["status"] == "ok"


# ---------------------------------------------------------------------------
# TestVerifyAdrs
# ---------------------------------------------------------------------------


class TestVerifyAdrs:
    def test_verified_when_no_violations(self, adr_mod, tmp_adr_dir: Path):
        """Diff that doesn't contain prohibited patterns → VERIFIED."""
        diff_text = "--- a/scripts/foo.py\n+++ b/scripts/foo.py\n@@ -1 +1 @@\n+x = 1\n"
        envelope = adr_mod.verify_adrs_envelope(
            adr_dir=tmp_adr_dir,
            changed_paths=["scripts/foo.py"],
            diff_text=diff_text,
            bead_description_override=None,
        )
        assert envelope["data"]["verdict"] == "VERIFIED"
        assert envelope["data"]["violations"] == []

    def test_disputed_when_violation_found(self, adr_mod, tmp_adr_dir: Path):
        """Diff containing prohibited text → DISPUTED with violation entry."""
        diff_text = (
            "--- a/scripts/foo.py\n+++ b/scripts/foo.py\n"
            "@@ -1 +1 @@\n"
            "+import subprocess\n"
            "+subprocess.run(['ls'])  # No direct subprocess calls without CommandRunner\n"
        )
        envelope = adr_mod.verify_adrs_envelope(
            adr_dir=tmp_adr_dir,
            changed_paths=["scripts/foo.py"],
            diff_text=diff_text,
            bead_description_override=None,
        )
        assert envelope["data"]["verdict"] == "DISPUTED"
        assert len(envelope["data"]["violations"]) >= 1
        violation = envelope["data"]["violations"][0]
        assert violation["adr"] == "ADR-alpha"
        assert violation["fixability"] == "human"

    def test_rediscovers_from_diff_ignoring_caller_scope(self, adr_mod, tmp_adr_dir: Path):
        """Caller passes empty adrs_in_scope but diff touches scripts/foo.py → ADR-alpha discovered."""
        diff_text = "--- a/scripts/foo.py\n+++ b/scripts/foo.py\n@@ -1 +1 @@\n+x = 1\n"
        envelope = adr_mod.verify_adrs_envelope(
            adr_dir=tmp_adr_dir,
            changed_paths=["scripts/foo.py"],  # from diff, not from caller-provided scope
            diff_text=diff_text,
            bead_description_override=None,
        )
        discovered_ids = [a["id"] for a in envelope["data"]["discovered_adrs"]]
        assert "ADR-alpha" in discovered_ids

    def test_disputed_for_fresh_adr_discovered_from_diff(self, adr_mod, tmp_adr_dir: Path):
        """A newly relevant ADR must still dispute the diff even if caller provenance was empty."""
        fresh_adr = tmp_adr_dir / "adr_fresh.md"
        fresh_adr.write_text(
            """---
id: ADR-fresh
status: accepted
date: 2026-05-02
contract: subprocess-policy
applies_to:
  - scripts/*.py
prohibits:
  - Do not add direct subprocess.run without CommandRunner
decision_summary: "Subprocess calls must route through CommandRunner."
---

# ADR-fresh
""",
            encoding="utf-8",
        )
        diff_text = (
            "--- a/scripts/foo.py\n+++ b/scripts/foo.py\n"
            "@@ -1 +1 @@\n"
            "+subprocess.run(['ls'])  # Do not add direct subprocess.run without CommandRunner\n"
        )
        envelope = adr_mod.verify_adrs_envelope(
            adr_dir=tmp_adr_dir,
            changed_paths=["scripts/foo.py"],
            diff_text=diff_text,
            bead_description_override=None,
        )
        assert envelope["data"]["verdict"] == "DISPUTED"
        violation = next(v for v in envelope["data"]["violations"] if v["adr"] == "ADR-fresh")
        assert violation["fixability"] == "human"

    def test_verifies_both_non_numeric_contract_adrs(self, adr_mod, tmp_path: Path):
        adr_dir = tmp_path / "adr"
        adr_dir.mkdir()
        for filename, contract in (
            ("adr-conformance-axis-modules.md", "conformance-axis-modules"),
            ("adr-billing-conformance-boundary.md", "billing-conformance-boundary"),
        ):
            (adr_dir / filename).write_text(
                f"""---
contract: {contract}
applies_to: [packages/**]
decision_summary: "{contract} decision"
prohibits:
  - "No violation of {contract}"
---
""",
                encoding="utf-8",
            )

        envelope = adr_mod.verify_adrs_envelope(
            adr_dir=adr_dir,
            changed_paths=["packages/billing-conformance/src/evaluate.ts"],
            diff_text=(
                "diff --git a/packages/billing-conformance/src/evaluate.ts "
                "b/packages/billing-conformance/src/evaluate.ts\n+x = 1\n"
            ),
            bead_description_override=None,
        )

        assert envelope["data"]["verdict"] == "VERIFIED"
        assert [adr["id"] for adr in envelope["data"]["discovered_adrs"]] == [
            "adr-billing-conformance-boundary",
            "adr-conformance-axis-modules",
        ]

    def test_adr_definition_does_not_violate_its_own_prohibition(
        self,
        adr_mod,
        tmp_path: Path,
        monkeypatch,
    ):
        monkeypatch.chdir(tmp_path)
        adr_dir = tmp_path / "docs" / "adr"
        adr_dir.mkdir(parents=True)
        (adr_dir / "ADR-046-capability-catalog.md").write_text(
            """---
contract: capability-catalog
applies_to: [docs/adr/**, packages/**]
prohibits:
  - "No decorative capability declarations"
decision_summary: "Capabilities are executable registry projections."
---
""",
            encoding="utf-8",
        )
        diff_text = (
            "diff --git a/docs/adr/ADR-046-capability-catalog.md "
            "b/docs/adr/ADR-046-capability-catalog.md\n"
            "--- a/docs/adr/ADR-046-capability-catalog.md\n"
            "+++ b/docs/adr/ADR-046-capability-catalog.md\n"
            "@@ -1 +1 @@\n"
            "+  - No decorative capability declarations\n"
        )

        envelope = adr_mod.verify_adrs_envelope(
            adr_dir=adr_dir,
            changed_paths=["docs/adr/ADR-046-capability-catalog.md"],
            diff_text=diff_text,
            bead_description_override=None,
        )

        assert envelope["data"]["verdict"] == "VERIFIED"
        assert [adr["id"] for adr in envelope["data"]["discovered_adrs"]] == ["ADR-046"]

    def test_other_file_still_proves_violation_when_adr_changes(self, adr_mod, tmp_path: Path):
        adr_dir = tmp_path / "docs" / "adr"
        adr_dir.mkdir(parents=True)
        (adr_dir / "ADR-046-capability-catalog.md").write_text(
            """---
contract: capability-catalog
applies_to: [docs/adr/**, packages/**]
prohibits:
  - "No decorative capability declarations"
decision_summary: "Capabilities are executable registry projections."
---
""",
            encoding="utf-8",
        )
        diff_text = (
            "diff --git a/docs/adr/ADR-046-capability-catalog.md "
            "b/docs/adr/ADR-046-capability-catalog.md\n"
            "+  - No decorative capability declarations\n"
            "diff --git a/packages/adapter/registry.ts b/packages/adapter/registry.ts\n"
            "+// No decorative capability declarations\n"
        )

        envelope = adr_mod.verify_adrs_envelope(
            adr_dir=adr_dir,
            changed_paths=[
                "docs/adr/ADR-046-capability-catalog.md",
                "packages/adapter/registry.ts",
            ],
            diff_text=diff_text,
            bead_description_override=None,
        )

        assert envelope["data"]["verdict"] == "DISPUTED"
        assert envelope["data"]["violations"][0]["adr"] == "ADR-046"

    def test_same_adr_filename_in_other_directory_remains_evidence(
        self,
        adr_mod,
        tmp_path: Path,
        monkeypatch,
    ):
        monkeypatch.chdir(tmp_path)
        adr_dir = Path("docs") / "adr"
        adr_dir.mkdir(parents=True)
        (adr_dir / "ADR-046-capability-catalog.md").write_text(
            """---
contract: capability-catalog
applies_to: [docs/adr/**, evidence/**]
prohibits:
  - "No decorative capability declarations"
decision_summary: "Capabilities are executable registry projections."
---
""",
            encoding="utf-8",
        )
        diff_text = (
            "diff --git a/docs/adr/ADR-046-capability-catalog.md "
            "b/docs/adr/ADR-046-capability-catalog.md\n"
            "+  - No decorative capability declarations\n"
            "diff --git a/evidence/ADR-046-capability-catalog.md "
            "b/evidence/ADR-046-capability-catalog.md\n"
            "+No decorative capability declarations\n"
        )

        envelope = adr_mod.verify_adrs_envelope(
            adr_dir=adr_dir,
            changed_paths=[
                "docs/adr/ADR-046-capability-catalog.md",
                "evidence/ADR-046-capability-catalog.md",
            ],
            diff_text=diff_text,
            bead_description_override=None,
        )

        assert envelope["data"]["verdict"] == "DISPUTED"
        assert envelope["data"]["violations"][0]["adr"] == "ADR-046"

    def test_discovered_adrs_structure(self, adr_mod, tmp_adr_dir: Path):
        """Each discovered_adrs entry has id, path, decision_summary."""
        diff_text = "--- a/scripts/foo.py\n+++ b/scripts/foo.py\n@@ -1 +1 @@\n+x = 1\n"
        envelope = adr_mod.verify_adrs_envelope(
            adr_dir=tmp_adr_dir,
            changed_paths=["scripts/foo.py"],
            diff_text=diff_text,
            bead_description_override=None,
        )
        for entry in envelope["data"]["discovered_adrs"]:
            assert "id" in entry
            assert "path" in entry
            assert "decision_summary" in entry

    def test_envelope_status_ok_for_verified(self, adr_mod, tmp_adr_dir: Path):
        diff_text = "--- a/scripts/foo.py\n+++ b/scripts/foo.py\n@@ -1 +1 @@\n+x = 1\n"
        envelope = adr_mod.verify_adrs_envelope(
            adr_dir=tmp_adr_dir,
            changed_paths=["scripts/foo.py"],
            diff_text=diff_text,
            bead_description_override=None,
        )
        assert envelope["status"] == "ok"

    def test_envelope_status_warning_for_disputed(self, adr_mod, tmp_adr_dir: Path):
        diff_text = (
            "--- a/scripts/foo.py\n+++ b/scripts/foo.py\n"
            "@@ -1 +1 @@\n"
            "+subprocess.run(['ls'])  # No direct subprocess calls without CommandRunner\n"
        )
        envelope = adr_mod.verify_adrs_envelope(
            adr_dir=tmp_adr_dir,
            changed_paths=["scripts/foo.py"],
            diff_text=diff_text,
            bead_description_override=None,
        )
        assert envelope["status"] == "warning"

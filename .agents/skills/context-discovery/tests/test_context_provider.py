from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
from typing import Any


_SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
_CONTEXT_PROVIDER = _SCRIPTS_DIR / "context_provider.py"


def _load_context_provider_module():
    spec = importlib.util.spec_from_file_location("context_provider", _CONTEXT_PROVIDER)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _bead(description: str, *, title: str = "Test bead") -> dict[str, Any]:
    return {
        "id": "clc-test",
        "title": title,
        "description": description,
        "acceptance_criteria": "",
        "metadata": {},
    }


def _write_adr(
    root: Path,
    *,
    adr_id: str = "ADR-057",
    selector: str = "packages/pvs-x-isynet",
    filename: str | None = None,
    prohibits: list[str] | None = None,
    decision_summary: str = "Production bindings remain explicit.",
) -> Path:
    path = root / "docs" / "adr" / (filename or f"{adr_id}-binding.md")
    path.parent.mkdir(parents=True, exist_ok=True)
    if prohibits is None:
        prohibit_yaml = 'prohibits:\n  - "Do not hide binding data."\n'
    elif prohibits:
        items = "\n".join(f'  - "{item}"' for item in prohibits)
        prohibit_yaml = f"prohibits:\n{items}\n"
    else:
        prohibit_yaml = "prohibits: []\n"
    path.write_text(
        f"""---
id: {adr_id}
applies_to:
  - {selector}
decision_summary: "{decision_summary}"
{prohibit_yaml}---

# {adr_id}
""",
        encoding="utf-8",
    )
    return path


def test_fallback_uses_context_pointers_as_seed(tmp_path: Path) -> None:
    module = _load_context_provider_module()
    (tmp_path / "src").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / "src" / "service.ts").write_text("export function handleOrder() {}\n")
    (tmp_path / "tests" / "service.test.ts").write_text("test('service', () => {})\n")

    bead = _bead(
        "Implement order handling.\n\n"
        "## Context Pointers\n"
        "primary_files:\n"
        "  - src/service.ts\n"
        "test_files:\n"
        "  - tests/service.test.ts\n"
        "symbols:\n"
        "  - handleOrder\n"
        'memory_search: "order handling context"\n'
    )

    bundle = module.build_context_bundle(
        bead,
        tmp_path,
        provider="fallback",
        cbm_command="codebase-memory-mcp",
        timeout=1,
        allow_index=False,
    )

    assert bundle["provider"] == "fallback"
    assert bundle["primary_files"] == ["src/service.ts"]
    assert bundle["test_files"] == ["tests/service.test.ts"]
    assert bundle["symbols"][0]["name"] == "handleOrder"
    assert bundle["memory_search"] == "order handling context"
    assert bundle["diagnostics"]["context_pointers_present"] is True


def test_adr_manifest_uses_complete_candidate_surface_and_is_bounded(
    tmp_path: Path,
) -> None:
    module = _load_context_provider_module()
    implementation_path = (
        tmp_path
        / "packages"
        / "pvs-x-isynet"
        / "src"
        / "mappers"
        / "schein-mapper.ts"
    )
    implementation_path.parent.mkdir(parents=True)
    implementation_path.write_text("export const mapSchein = () => true;\n")
    _write_adr(tmp_path)
    bead = _bead(
        "Update the production binding mapper.\n\n"
        "## Context Pointers\n"
        "primary_files:\n"
        "  - packages/pvs-x-isynet/src/mappers/schein-mapper.ts\n"
    )

    first = module.build_context_bundle(
        bead,
        tmp_path,
        provider="fallback",
        cbm_command="codebase-memory-mcp",
        timeout=1,
        allow_index=False,
    )
    second = module.build_context_bundle(
        bead,
        tmp_path,
        provider="fallback",
        cbm_command="codebase-memory-mcp",
        timeout=1,
        allow_index=False,
    )

    context = first["adr_context"]
    assert context["status"] == "complete"
    assert context["candidate_surface_count"] == 1
    # Repository-local corpus tokens, provenance:
    # bd show clc-apby -> Pre-Mortem: precedence explicit, governing family decision visible beside local
    assert context["manifest"] == [
        {
            "id": "ADR-057",
            "path": "docs/adr/ADR-057-binding.md",
            "origin": "local",
            "corpus": "local",
            "precedence": "local",
            "match_reasons": ["path:packages/pvs-x-isynet"],
            "decision_summary": "Production bindings remain explicit.",
            "prohibitions": ["Do not hide binding data."],
            "read_pointers": [
                {"path": "docs/adr/ADR-057-binding.md", "section": "Decision"},
                {
                    "path": "docs/adr/ADR-057-binding.md",
                    "section": "Prohibitions",
                },
            ],
        }
    ]
    assert context["freshness"] == second["adr_context"]["freshness"]
    assert "body" not in context["manifest"][0]


def test_scalar_applies_to_and_prohibits_admit_complete_sentence(
    tmp_path: Path,
) -> None:
    """clc-no2n CUM-01: contract-legal scalar lists must not drop or shard."""
    module = _load_context_provider_module()
    implementation_path = (
        tmp_path
        / "packages"
        / "pvs-x-isynet"
        / "src"
        / "mappers"
        / "schein-mapper.ts"
    )
    implementation_path.parent.mkdir(parents=True)
    implementation_path.write_text("export const mapSchein = () => true;\n")
    prohibition = "Do not hide binding data in mapper constructors."
    adr_path = tmp_path / "docs" / "adr" / "ADR-058-scalar.md"
    adr_path.parent.mkdir(parents=True, exist_ok=True)
    adr_path.write_text(
        "---\n"
        "id: ADR-058\n"
        "applies_to: pvs-x-isynet\n"
        f'prohibits: "{prohibition}"\n'
        'decision_summary: "Scalar selectors remain valid."\n'
        "---\n\n"
        "# ADR-058\n",
        encoding="utf-8",
    )
    bead = _bead(
        "Update the production binding mapper.\n\n"
        "## Context Pointers\n"
        "primary_files:\n"
        "  - packages/pvs-x-isynet/src/mappers/schein-mapper.ts\n"
    )

    bundle = module.build_context_bundle(
        bead,
        tmp_path,
        provider="fallback",
        cbm_command="codebase-memory-mcp",
        timeout=1,
        allow_index=False,
    )

    context = bundle["adr_context"]
    assert context["status"] == "complete"
    assert context["manifest"]
    entry = next(item for item in context["manifest"] if item["id"] == "ADR-058")
    assert prohibition in entry["prohibitions"]
    assert entry["prohibitions"] == [prohibition]
    assert not any(len(item) == 1 for item in entry["prohibitions"])


def test_adr_context_freshness_invalidates_all_bound_inputs(tmp_path: Path) -> None:
    module = _load_context_provider_module()
    source = tmp_path / "src" / "service.py"
    source.parent.mkdir()
    source.write_text("def run():\n    return True\n")
    adr = _write_adr(tmp_path, selector="src")
    bead = _bead(
        "Update src/service.py.\n\n"
        "## Context Pointers\nprimary_files:\n  - src/service.py\n"
    )
    bundle = module.build_context_bundle(
        bead,
        tmp_path,
        provider="fallback",
        cbm_command="codebase-memory-mcp",
        timeout=1,
        allow_index=False,
    )
    context = bundle["adr_context"]
    surface = bundle["candidate_files"] + bundle["candidate_test_files"]

    assert module.validate_adr_context(
        context, bead=bead, repo_root=tmp_path, candidate_surface=surface
    ) == []
    other_root = tmp_path / "other-worktree"
    other_root.mkdir()
    assert any(
        "repository_digest" in error
        for error in module.validate_adr_context(
            context,
            bead=bead,
            repo_root=other_root,
            candidate_surface=surface,
        )
    )
    changed_bead = dict(bead, title="Changed")
    assert any(
        "bead_digest" in error
        for error in module.validate_adr_context(
            context,
            bead=changed_bead,
            repo_root=tmp_path,
            candidate_surface=surface,
        )
    )
    source.write_text("def run():\n    return False\n")
    assert any(
        "scope_digest" in error
        for error in module.validate_adr_context(
            context, bead=bead, repo_root=tmp_path, candidate_surface=surface
        )
    )
    source.write_text("def run():\n    return True\n")
    adr.write_text(adr.read_text() + "\nAmended guidance.\n")
    assert any(
        "adr_corpus_digest" in error
        for error in module.validate_adr_context(
            context, bead=bead, repo_root=tmp_path, candidate_surface=surface
        )
    )


def test_bundle_validation_rejects_self_consistent_narrowed_surface(
    tmp_path: Path,
) -> None:
    module = _load_context_provider_module()
    source = tmp_path / "src" / "service.py"
    source.parent.mkdir()
    source.write_text("def handle_binding():\n    return True\n")
    _write_adr(tmp_path, selector="src")
    bead = _bead(
        "Update src/service.py.\n\n"
        "## Context Pointers\nprimary_files:\n  - src/service.py\n"
    )
    bundle = module.build_context_bundle(
        bead,
        tmp_path,
        provider="fallback",
        cbm_command="codebase-memory-mcp",
        timeout=1,
        allow_index=False,
    )
    narrowed = {
        **bundle,
        "candidate_files": [],
        "candidate_test_files": [],
        "adr_context": module.build_adr_context(bead, tmp_path, []),
    }

    errors = module.validate_context_bundle(
        narrowed, bead=bead, repo_root=tmp_path, timeout=1
    )

    assert any("independent current discovery" in error for error in errors)


def test_manifest_overflow_is_bounded_traceable_and_blocking(
    tmp_path: Path,
) -> None:
    module = _load_context_provider_module()
    source = tmp_path / "src" / "service.py"
    source.parent.mkdir()
    source.write_text("def handle_binding():\n    return True\n")
    bead = _bead(
        "Update src/service.py.\n\n"
        "## Context Pointers\nprimary_files:\n  - src/service.py\n"
    )
    for index in range(module.ADR_MANIFEST_LIMIT + 1):
        _write_adr(tmp_path, adr_id=f"ADR-{index:03d}", selector="src")

    bundle = module.build_context_bundle(
        bead,
        tmp_path,
        provider="fallback",
        cbm_command="codebase-memory-mcp",
        timeout=1,
        allow_index=False,
    )

    context = bundle["adr_context"]
    assert len(context["manifest"]) == module.ADR_MANIFEST_LIMIT
    assert context["status"] == "gap"
    gap = context["gaps"][0]
    assert gap["code"] == "ADR_MANIFEST_TRUNCATED"
    assert gap["resolved"] is False
    assert gap["omitted_count"] == 1
    assert len(gap["discovery_digest"]) == 64
    assert gap["resolution"]["admission"] == "blocked_until_manifest_fits_bound"
    assert any(
        "unresolved" in error
        for error in module.validate_context_bundle(
            bundle, bead=bead, repo_root=tmp_path, timeout=1
        )
    )


def test_constraint_adrs_survive_positional_filename_overflow(
    tmp_path: Path,
) -> None:
    """Prohibits beyond the rglob/filename slice must still enter the bound."""
    module = _load_context_provider_module()
    source = tmp_path / "src" / "service.py"
    source.parent.mkdir()
    source.write_text("def handle_binding():\n    return True\n")
    bead = _bead(
        "Update src/service.py.\n\n"
        "## Context Pointers\nprimary_files:\n  - src/service.py\n"
    )
    for index in range(module.ADR_MANIFEST_LIMIT):
        _write_adr(
            tmp_path,
            adr_id=f"ADR-INFO-{index:03d}",
            selector="src",
            filename=f"aaa-info-{index:03d}.md",
            prohibits=[],
        )
    constraint_ids = ["ADR-KEEP-1", "ADR-KEEP-2"]
    for name, adr_id in enumerate(constraint_ids, start=1):
        _write_adr(
            tmp_path,
            adr_id=adr_id,
            selector="src",
            filename=f"zzz-constraint-{name:02d}.md",
            prohibits=[f"Do not drop constraint {adr_id}."],
        )

    bundle = module.build_context_bundle(
        bead,
        tmp_path,
        provider="fallback",
        cbm_command="codebase-memory-mcp",
        timeout=1,
        allow_index=False,
    )
    context = bundle["adr_context"]
    manifest_ids = {item["id"] for item in context["manifest"]}
    assert len(context["manifest"]) == module.ADR_MANIFEST_LIMIT
    assert manifest_ids.issuperset(constraint_ids)
    for item in context["manifest"]:
        if item["id"] in constraint_ids:
            assert item["prohibitions"]
    assert context["status"] == "gap"
    gap = next(
        item for item in context["gaps"] if item.get("code") == "ADR_MANIFEST_TRUNCATED"
    )
    assert gap["resolved"] is False
    assert gap["omitted_count"] == 2
    assert gap["resolution"]["admission"] == "blocked_until_manifest_fits_bound"
    action = str(gap["resolution"].get("action") or "")
    assert action
    assert "split_implementation_scope" in action or "narrow_adr_selectors" in action


def test_large_package_constraints_survive_filename_order(
    tmp_path: Path,
) -> None:
    """Dozens of same-selector ADRs: constraints survive reverse-name placement."""
    module = _load_context_provider_module()
    package_file = (
        tmp_path / "packages" / "pvs-x-isynet" / "src" / "mappers" / "schein-mapper.ts"
    )
    package_file.parent.mkdir(parents=True)
    package_file.write_text("export const mapSchein = () => null;\n")
    bead = _bead(
        "Update packages/pvs-x-isynet/src/mappers/schein-mapper.ts.\n\n"
        "## Context Pointers\n"
        "primary_files:\n"
        "  - packages/pvs-x-isynet/src/mappers/schein-mapper.ts\n"
    )
    informational_count = 70
    for index in range(informational_count):
        _write_adr(
            tmp_path,
            adr_id=f"ADR-INFO-{index:03d}",
            selector="pvs-x-isynet",
            filename=f"n{index:03d}-info.md",
            prohibits=[],
        )
    constraint_files = {
        "ADR-KEEP-AAA": "000-constraint.md",
        "ADR-KEEP-MID": "mmm-constraint.md",
        "ADR-KEEP-ZZZ": "zzz-constraint.md",
        "ADR-KEEP-REV": "999-constraint.md",
    }
    for adr_id, filename in constraint_files.items():
        _write_adr(
            tmp_path,
            adr_id=adr_id,
            selector="pvs-x-isynet",
            filename=filename,
            prohibits=[f"Do not violate {adr_id}."],
        )

    bundle = module.build_context_bundle(
        bead,
        tmp_path,
        provider="fallback",
        cbm_command="codebase-memory-mcp",
        timeout=1,
        allow_index=False,
    )
    context = bundle["adr_context"]
    manifest_ids = {item["id"] for item in context["manifest"]}
    assert len(context["manifest"]) == module.ADR_MANIFEST_LIMIT
    assert manifest_ids.issuperset(constraint_files)
    assert context["status"] == "gap"
    gap = next(
        item for item in context["gaps"] if item.get("code") == "ADR_MANIFEST_TRUNCATED"
    )
    assert gap["resolved"] is False
    assert str(gap["resolution"].get("action") or "")


def test_regression_package_scoped_manifest_fits_observed_polaris_set(
    tmp_path: Path,
) -> None:
    """clc-u883: observed Polaris package scope (42 blank-selector ADRs) must
    admit without ADR_MANIFEST_TRUNCATED under the finite 64-entry bound.
    """
    module = _load_context_provider_module()
    assert module.ADR_MANIFEST_LIMIT == 64

    package_file = (
        tmp_path / "packages" / "pvs-x-isynet" / "src" / "mappers" / "schein-mapper.ts"
    )
    package_file.parent.mkdir(parents=True)
    package_file.write_text("export const mapSchein = () => null;\n")
    bead = _bead(
        "Update packages/pvs-x-isynet/src/mappers/schein-mapper.ts.\n\n"
        "## Context Pointers\n"
        "primary_files:\n"
        "  - packages/pvs-x-isynet/src/mappers/schein-mapper.ts\n"
    )
    observed_count = 42
    for index in range(observed_count):
        _write_adr(tmp_path, adr_id=f"ADR-{index:03d}", selector="pvs-x-isynet")

    bundle = module.build_context_bundle(
        bead,
        tmp_path,
        provider="fallback",
        cbm_command="codebase-memory-mcp",
        timeout=1,
        allow_index=False,
    )

    context = bundle["adr_context"]
    assert context["status"] == "complete"
    assert len(context["manifest"]) == observed_count
    assert all(gap.get("code") != "ADR_MANIFEST_TRUNCATED" for gap in context["gaps"])
    assert (
        module.validate_context_bundle(
            bundle, bead=bead, repo_root=tmp_path, timeout=1
        )
        == []
    )


def test_identity_collision_is_traceable_and_blocking(tmp_path: Path) -> None:
    module = _load_context_provider_module()
    source = tmp_path / "src" / "service.py"
    source.parent.mkdir()
    source.write_text("def handle_binding():\n    return True\n")
    bead = _bead(
        "Update src/service.py.\n\n"
        "## Context Pointers\nprimary_files:\n  - src/service.py\n"
    )
    _write_adr(tmp_path, adr_id="ADR-057", selector="src")
    collision = tmp_path / "docs" / "adr" / "ADR-057-other.md"
    collision.write_text(
        """---
id: ADR-057
applies_to: [src]
decision_summary: "Conflicting identity."
---
""",
        encoding="utf-8",
    )

    bundle = module.build_context_bundle(
        bead,
        tmp_path,
        provider="fallback",
        cbm_command="codebase-memory-mcp",
        timeout=1,
        allow_index=False,
    )

    gap = bundle["adr_context"]["gaps"][0]
    assert gap["code"] == "ADR_DISCOVERY_FAILED"
    assert gap["resolved"] is False
    assert gap["error_type"] == "AdrIdentityCollisionError"
    assert len(gap["failure_digest"]) == 64
    assert gap["resolution"]["admission"] == "blocked_until_discovery_succeeds"


def test_provider_uses_pep723_selector_without_project_pyyaml(
    tmp_path: Path,
) -> None:
    source = tmp_path / "src" / "service.py"
    source.parent.mkdir()
    source.write_text("def handle_binding():\n    return True\n")
    _write_adr(tmp_path, selector="src")
    bead_path = tmp_path / "bead.json"
    bead_path.write_text(
        json.dumps(
            _bead(
                "Update src/service.py.\n\n"
                "## Context Pointers\nprimary_files:\n  - src/service.py\n"
            )
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            "uv",
            "run",
            "--isolated",
            "--no-project",
            "python",
            str(_CONTEXT_PROVIDER),
            "--bead-json",
            str(bead_path),
            "--repo-root",
            str(tmp_path),
            "--provider",
            "fallback",
        ],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    output = json.loads(result.stdout)
    assert [item["id"] for item in output["adr_context"]["manifest"]] == ["ADR-057"]


def test_auto_provider_falls_back_when_codebase_memory_missing(tmp_path: Path) -> None:
    module = _load_context_provider_module()
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "orders.py").write_text("def process_order():\n    pass\n")
    bead = _bead(
        "Update src/orders.py and verify `process_order`. Related bead clc-123."
    )

    bundle = module.build_context_bundle(
        bead,
        tmp_path,
        provider="auto",
        cbm_command="codebase-memory-mcp",
        timeout=1,
        allow_index=False,
        executable_resolver=lambda _command: None,
    )

    assert bundle["provider"] == "fallback"
    assert bundle["provider_status"] == "unavailable"
    assert bundle["primary_files"] == ["src/orders.py"]
    assert [symbol["name"] for symbol in bundle["symbols"]] == ["process_order"]
    assert bundle["related_beads"] == ["clc-123"]
    assert bundle["confidence"] == "medium"


def test_symbol_extraction_splits_comma_symbols_and_keeps_action_keys() -> None:
    module = _load_context_provider_module()

    symbols = module.extract_seed_symbols(
        "`v3Evaluator, V3FactCatalog, HttpPvsRuleAdapter, account-exists, create-hzv-account`"
    )

    assert "v3Evaluator" in symbols
    assert "V3FactCatalog" in symbols
    assert "HttpPvsRuleAdapter" in symbols
    assert "account-exists" in symbols
    assert "create-hzv-account" in symbols


def test_context_pointer_symbols_are_split_before_search(tmp_path: Path) -> None:
    module = _load_context_provider_module()
    bead = _bead(
        "Implement HZV account action.\n\n"
        "## Context Pointers\n"
        "symbols:\n"
        "  - v3Evaluator, V3FactCatalog, create-hzv-account\n"
    )

    seed = module.seed_from_bead(bead, tmp_path)

    assert "v3Evaluator" in seed["symbols"]
    assert "V3FactCatalog" in seed["symbols"]
    assert "create-hzv-account" in seed["symbols"]


class FakeCodebaseMemory:
    def __call__(
        self, args: list[str], timeout: int
    ) -> subprocess.CompletedProcess[str]:
        assert timeout == 1
        if "--raw" in args:
            tool = args[args.index("--raw") + 1]
            payload_index = args.index("--raw") + 2
        else:
            tool = args[2]
            payload_index = 3
        payload = json.loads(args[payload_index]) if len(args) > payload_index else {}

        if tool == "list_projects":
            output = {"results": [{"name": "repo", "repo_path": "/unused"}]}
        elif tool == "search_graph" and payload.get("label") == "Route":
            output = {"results": [{"path": "/orders", "method": "GET"}]}
        elif tool == "search_graph":
            output = {
                "results": [
                    {
                        "name": "ProcessOrder",
                        "file": "src/orders.ts",
                        "line": 12,
                        "label": "Function",
                        "qualified_name": "repo.src.orders.ProcessOrder",
                    }
                ]
            }
        elif tool == "trace_path":
            output = {"paths": [{"from": "Controller", "to": "ProcessOrder"}]}
        else:
            output = {}
        return subprocess.CompletedProcess(args, 0, json.dumps(output), "")


def test_codebase_memory_results_are_normalized(tmp_path: Path) -> None:
    module = _load_context_provider_module()
    bead = _bead(
        "Touch the API route in `ProcessOrder()` and update the HTTP controller."
    )

    bundle = module.build_context_bundle(
        bead,
        tmp_path,
        provider="codebase-memory",
        cbm_command="codebase-memory-mcp",
        timeout=1,
        allow_index=False,
        command_runner=FakeCodebaseMemory(),
        executable_resolver=lambda _command: "/bin/codebase-memory-mcp",
    )

    assert bundle["provider"] == "codebase-memory"
    assert bundle["provider_status"] == "ok"
    assert "src/orders.ts" in bundle["primary_files"]
    assert bundle["symbols"][0] == {
        "name": "ProcessOrder",
        "file": "src/orders.ts",
        "line": 12,
        "kind": "Function",
        "qualified_name": "repo.src.orders.ProcessOrder",
        "source": "codebase-memory",
    }
    assert bundle["call_paths"][0]["symbol"] == "ProcessOrder"
    assert bundle["routes"] == [{"path": "/orders", "method": "GET"}]
    assert bundle["confidence"] == "medium"


class FakeCodebaseMemoryWithCodeSearch:
    def __call__(
        self, args: list[str], timeout: int
    ) -> subprocess.CompletedProcess[str]:
        if "--raw" in args:
            tool = args[args.index("--raw") + 1]
            payload_index = args.index("--raw") + 2
        else:
            tool = args[2]
            payload_index = 3
        payload = json.loads(args[payload_index]) if len(args) > payload_index else {}

        if tool == "list_projects":
            output = {"projects": [{"name": "repo", "root_path": str(Path.cwd())}]}
        elif tool == "search_graph":
            output = {"results": []}
        elif tool == "search_code" and payload.get("pattern") == "INSTALL_MANIFEST":
            output = {
                "results": [
                    {
                        "node": "INSTALL_MANIFEST",
                        "qualified_name": "repo.packages.install_pvs.manifest.INSTALL_MANIFEST",
                        "label": "Variable",
                        "file": "packages/install-pvs/src/manifest.ts",
                        "start_line": 33,
                    },
                    {
                        "node": "packages/install-pvs/src/__tests__/manifest.test.ts",
                        "qualified_name": "repo.packages.install_pvs.tests.manifest_test",
                        "label": "Module",
                        "file": "packages/install-pvs/src/__tests__/manifest.test.ts",
                        "start_line": 1,
                    },
                ]
            }
        elif tool == "trace_path":
            output = {"paths": []}
        else:
            output = {}
        return subprocess.CompletedProcess(args, 0, json.dumps(output), "")


def test_codebase_memory_search_code_enriches_sparse_graph_results(tmp_path: Path) -> None:
    module = _load_context_provider_module()
    bead = _bead(
        "Update packages/install-pvs/src/manifest.ts and `INSTALL_MANIFEST`."
    )

    bundle = module.build_context_bundle(
        bead,
        tmp_path,
        provider="codebase-memory",
        cbm_command="codebase-memory-mcp",
        timeout=1,
        allow_index=False,
        command_runner=FakeCodebaseMemoryWithCodeSearch(),
        executable_resolver=lambda _command: "/bin/codebase-memory-mcp",
    )

    assert "packages/install-pvs/src/manifest.ts" in bundle["primary_files"]
    assert "packages/install-pvs/src/__tests__/manifest.test.ts" in bundle["test_files"]
    assert any(
        symbol["name"] == "INSTALL_MANIFEST"
        and symbol["source"] == "codebase-memory"
        for symbol in bundle["symbols"]
    )
    assert bundle["confidence"] == "high"


class FakeNoisyCodebaseMemory:
    def __call__(
        self, args: list[str], timeout: int
    ) -> subprocess.CompletedProcess[str]:
        if "--raw" in args:
            tool = args[args.index("--raw") + 1]
            payload_index = args.index("--raw") + 2
        else:
            tool = args[2]
            payload_index = 3
        payload = json.loads(args[payload_index]) if len(args) > payload_index else {}

        if tool == "list_projects":
            output = {"projects": [{"name": "repo", "root_path": str(Path.cwd())}]}
        elif tool in {"search_graph", "search_code"}:
            pattern = payload.get("name_pattern") or payload.get("pattern") or ""
            if "Violation" in pattern or "violation" in pattern:
                output = {
                    "results": [
                        {
                            "name": "Violation",
                            "file": "src/lib/billing/validation-types.ts",
                            "label": "Interface",
                        },
                        {
                            "name": "BlockedProposalViolation",
                            "file": "frontend/lib/api/proposals.ts",
                            "label": "Interface",
                        },
                    ]
                }
            else:
                output = {"results": []}
        elif tool == "trace_path":
            output = {"paths": []}
        else:
            output = {}
        return subprocess.CompletedProcess(args, 0, json.dumps(output), "")


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def test_exact_enrichment_finds_mira_hzv_accept_writeback_path(tmp_path: Path) -> None:
    module = _load_context_provider_module()
    _write(
        tmp_path / "src/lib/billing/engine/v3-evaluator.ts",
        "export const action = { key: 'create-hzv-account' }\n",
    )
    _write(
        tmp_path / "src/lib/auto-hzv-schein.ts",
        "export async function ensureScheine() {}\nexport async function rebookChargeItemsToHzv() {}\n",
    )
    _write(
        tmp_path / "src/lib/billing/hzv-schein-umbuchung-executor.ts",
        "import { ensureScheine } from '../auto-hzv-schein'\nexport async function executeHzvScheinUmbuchung() {}\n",
    )
    _write(
        tmp_path / "src/lib/billing/action-registry.ts",
        "export const PROPOSAL_TYPE_ACTION_KIND = { 'hzv-schein-umbuchung': 'hzv-schein-umbuchung' }\n"
        "export async function dispatchAccept() {}\n",
    )
    _write(
        tmp_path / "src/lib/approval-service.ts",
        "import { dispatchAccept } from './billing/action-registry'\n"
        "await dispatchAccept(proposal.proposalType, id, finalPayload, context)\n",
    )

    bead = _bead(
        "MIRA bead mira-alln0 adds account-exists and create-hzv-account action support. "
        "Accepted proposals must route through proposal_type to the existing executor, "
        "not a duplicate stub.\n\n"
        "## Context Pointers\n"
        "primary_files:\n"
        "  - src/lib/billing/engine/v3-evaluator.ts\n"
        "symbols:\n"
        "  - v3Evaluator, V3FactCatalog, create-hzv-account\n"
    )

    bundle = module.build_context_bundle(
        bead,
        tmp_path,
        provider="codebase-memory",
        cbm_command="codebase-memory-mcp",
        timeout=1,
        allow_index=False,
        command_runner=FakeNoisyCodebaseMemory(),
        executable_resolver=lambda _command: "/bin/codebase-memory-mcp",
    )

    assert "src/lib/auto-hzv-schein.ts" in bundle["primary_files"]
    assert "src/lib/billing/hzv-schein-umbuchung-executor.ts" in bundle["primary_files"]
    assert "src/lib/billing/action-registry.ts" in bundle["primary_files"]
    assert "src/lib/approval-service.ts" in bundle["primary_files"]
    assert "create-hzv-account" in bundle["diagnostics"]["exact_search_tokens"]
    assert "ensureScheine" in bundle["diagnostics"]["exact_search_tokens"]
    assert bundle["confidence"] == "high"


def test_fix_clc_ibuw_broad_exact_results_use_focused_surface(tmp_path: Path) -> None:
    # Guards against broad exact-search hits being promoted to high-confidence context.
    module = _load_context_provider_module()
    _write(
        tmp_path / "src/critical-entrypoint.ts",
        "export function handleHzvAction() {}\n",
    )
    for index in range(60):
        _write(
            tmp_path / f"src/lib/billing/generated/action-{index}.ts",
            "export const kind = 'create-hzv-account'\n",
        )

    bead = _bead(
        "Wire accepted create-hzv-account proposals without overfeeding broad matches.\n\n"
        "## Context Pointers\n"
        "primary_files:\n"
        "  - src/critical-entrypoint.ts\n"
        "symbols:\n"
        "  - create-hzv-account\n"
    )

    bundle = module.build_context_bundle(
        bead,
        tmp_path,
        provider="fallback",
        cbm_command="codebase-memory-mcp",
        timeout=1,
        allow_index=False,
    )

    assert bundle["primary_files"] == bundle["focus_files"]
    assert len(bundle["focus_files"]) <= module.FOCUS_PRIMARY_LIMIT
    assert len(bundle["focus_files"]) + len(bundle["focus_test_files"]) <= (
        module.FOCUS_TOTAL_LIMIT
    )
    assert len(bundle["candidate_files"]) > len(bundle["focus_files"])
    assert "src/critical-entrypoint.ts" in bundle["focus_files"]
    assert any(
        path not in bundle["focus_files"] for path in bundle["candidate_files"]
    )
    assert "exact search hit cap" in bundle["breadth_reason"]
    assert bundle["slice_recommended"] is False
    signals = bundle.get("breadth_signals") or []
    assert "explicit_anchors" in signals
    assert "exact_search_fallback" in signals
    assert "hit_cap_overflow" in signals
    assert bundle["diagnostics"]["breadth_signals"] == signals
    assert bundle["breadth_assessment"] in {"focused", "moderate"}
    assert bundle["breadth_assessment"] != "broad"
    assert bundle["confidence"] != "high"
    assert bundle["diagnostics"]["exact_search_hit_cap"] is True
    assert bundle["diagnostics"]["exact_search_raw_files"] > module.EXACT_SEARCH_LIMIT
    assert bundle["diagnostics"]["focus_primary_files"] == len(bundle["focus_files"])
    assert bundle["diagnostics"]["candidate_primary_files"] == len(
        bundle["candidate_files"]
    )


def test_narrow_coherent_anchors_do_not_slice_on_fallback_volume(
    tmp_path: Path,
) -> None:
    """clc-e04l: <20 coherent Context Pointer files are the real surface."""
    module = _load_context_provider_module()
    anchors = [
        "src/service.ts",
        "src/mapper.ts",
        "tests/service.test.ts",
    ]
    for path in anchors:
        _write(tmp_path / path, "export const createHzvAccount = () => null;\n")
    for index in range(55):
        _write(
            tmp_path / f"src/generated/token-{index}.ts",
            "export const kind = 'createHzvAccount'\n",
        )
    bead = _bead(
        "Tighten the mapper without slicing the whole generated token tree.\n\n"
        "## Context Pointers\n"
        "primary_files:\n"
        "  - src/service.ts\n"
        "  - src/mapper.ts\n"
        "test_files:\n"
        "  - tests/service.test.ts\n"
        "symbols:\n"
        "  - createHzvAccount\n"
    )

    bundle = module.build_context_bundle(
        bead,
        tmp_path,
        provider="fallback",
        cbm_command="codebase-memory-mcp",
        timeout=1,
        allow_index=False,
    )

    assert bundle["diagnostics"]["seed_primary_files"] + bundle["diagnostics"][
        "seed_test_files"
    ] < 20
    assert bundle["slice_recommended"] is False
    signals = bundle["breadth_signals"]
    assert "explicit_anchors" in signals
    assert "exact_search_fallback" in signals
    assert "hit_cap_overflow" in signals or "candidate_volume" in signals
    assert bundle["breadth_assessment"] in {"focused", "moderate"}
    assert bundle["breadth_assessment"] != "broad"
    assert all(anchor in bundle["candidate_files"] or anchor in bundle["candidate_test_files"] for anchor in anchors)
    assert bundle["primary_files"] == bundle["focus_files"]


def test_independent_package_roots_still_slice_on_fallback_volume(
    tmp_path: Path,
) -> None:
    """Two packages/<name> roots remain independent concerns (clc-e04l R1-01)."""
    module = _load_context_provider_module()
    anchors = [
        "packages/billing/src/engine.ts",
        "packages/auth/src/session.ts",
    ]
    for path in anchors:
        _write(tmp_path / path, "export const sharedToken = () => null;\n")
    for index in range(55):
        _write(
            tmp_path / f"src/generated/token-{index}.ts",
            "export const kind = 'sharedToken'\n",
        )
    bead = _bead(
        "Touch billing and auth together.\n\n"
        "## Context Pointers\n"
        "primary_files:\n"
        "  - packages/billing/src/engine.ts\n"
        "  - packages/auth/src/session.ts\n"
        "symbols:\n"
        "  - sharedToken\n"
    )

    bundle = module.build_context_bundle(
        bead,
        tmp_path,
        provider="fallback",
        cbm_command="codebase-memory-mcp",
        timeout=1,
        allow_index=False,
    )

    assert bundle["slice_recommended"] is True
    assert "independent_concerns" in bundle["breadth_signals"]
    assert "explicit_anchors" in bundle["breadth_signals"]
    assert "hit_cap_overflow" in bundle["breadth_signals"] or "candidate_volume" in bundle[
        "breadth_signals"
    ]


def test_layered_src_tests_feature_does_not_slice_on_fallback_volume(
    tmp_path: Path,
) -> None:
    """One feature across src/api, src/domain, tests/unit is one concern."""
    module = _load_context_provider_module()
    anchors = [
        "src/api/handler.ts",
        "src/domain/model.ts",
        "tests/unit/handler.test.ts",
    ]
    for path in anchors:
        _write(tmp_path / path, "export const layeredToken = () => null;\n")
    for index in range(55):
        _write(
            tmp_path / f"src/generated/token-{index}.ts",
            "export const kind = 'layeredToken'\n",
        )
    bead = _bead(
        "Adjust one vertical feature without slicing generated noise.\n\n"
        "## Context Pointers\n"
        "primary_files:\n"
        "  - src/api/handler.ts\n"
        "  - src/domain/model.ts\n"
        "test_files:\n"
        "  - tests/unit/handler.test.ts\n"
        "symbols:\n"
        "  - layeredToken\n"
    )

    bundle = module.build_context_bundle(
        bead,
        tmp_path,
        provider="fallback",
        cbm_command="codebase-memory-mcp",
        timeout=1,
        allow_index=False,
    )

    assert bundle["diagnostics"]["seed_primary_files"] + bundle["diagnostics"][
        "seed_test_files"
    ] < 20
    assert bundle["slice_recommended"] is False
    signals = bundle["breadth_signals"]
    assert "explicit_anchors" in signals
    assert "exact_search_fallback" in signals
    assert "hit_cap_overflow" in signals or "candidate_volume" in signals
    assert "independent_concerns" not in signals
    assert bundle["breadth_assessment"] in {"focused", "moderate"}
    assert bundle["breadth_assessment"] != "broad"


def test_root_changelog_does_not_split_src_tests_concern(
    tmp_path: Path,
) -> None:
    """Repository-root CHANGELOG.md is repo-wide, not a second concern."""
    module = _load_context_provider_module()
    anchors = [
        "src/service.ts",
        "tests/service.test.ts",
        "CHANGELOG.md",
    ]
    for path in anchors:
        _write(tmp_path / path, "export const rootToken = () => null;\n")
    for index in range(55):
        _write(
            tmp_path / f"src/generated/token-{index}.ts",
            "export const kind = 'rootToken'\n",
        )
    bead = _bead(
        "Update the service and note it in the changelog.\n\n"
        "## Context Pointers\n"
        "primary_files:\n"
        "  - src/service.ts\n"
        "  - CHANGELOG.md\n"
        "test_files:\n"
        "  - tests/service.test.ts\n"
        "symbols:\n"
        "  - rootToken\n"
    )

    bundle = module.build_context_bundle(
        bead,
        tmp_path,
        provider="fallback",
        cbm_command="codebase-memory-mcp",
        timeout=1,
        allow_index=False,
    )

    assert bundle["diagnostics"]["seed_primary_files"] + bundle["diagnostics"][
        "seed_test_files"
    ] < 20
    assert bundle["slice_recommended"] is False
    assert "independent_concerns" not in bundle["breadth_signals"]
    assert bundle["breadth_assessment"] != "broad"


def test_noisy_graph_matches_do_not_create_high_confidence(tmp_path: Path) -> None:
    module = _load_context_provider_module()
    bead = _bead("Fix generic `Violation` handling without source pointers.")

    bundle = module.build_context_bundle(
        bead,
        tmp_path,
        provider="codebase-memory",
        cbm_command="codebase-memory-mcp",
        timeout=1,
        allow_index=False,
        command_runner=FakeNoisyCodebaseMemory(),
        executable_resolver=lambda _command: "/bin/codebase-memory-mcp",
    )

    assert bundle["confidence"] != "high"


def test_codebase_memory_project_name_uses_root_path(tmp_path: Path) -> None:
    module = _load_context_provider_module()
    payload = {
        "projects": [
            {
                "name": "Users-malte-code-library-cognovis-core",
                "root_path": str(tmp_path),
            }
        ]
    }

    project, diagnostics = module.discover_cbm_project(
        "/bin/codebase-memory-mcp",
        tmp_path,
        timeout=1,
        command_runner=lambda _args, _timeout: subprocess.CompletedProcess(
            _args, 0, json.dumps(payload), ""
        ),
    )

    assert project == "Users-malte-code-library-cognovis-core"
    assert diagnostics == []

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
MODULE = REPO_ROOT / "skills" / "bead-reviewer" / "scripts" / "contract_loader.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("contract_loader", MODULE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _contract(rule_id: str, text: str) -> str:
    return (
        "# Bead Hygiene Standard\n\n"
        "## Pflichtfelder\n\n"
        f"- <!-- rule-id: {rule_id} --><!-- severity: critical -->{text}\n\n"
        "## Anti-Patterns\n\n"
    )


def _delta(rule_id: str, text: str) -> str:
    return (
        "# Project Bead Hygiene Delta\n\n"
        "## Pflichtfelder\n\n"
        f"- <!-- rule-id: {rule_id} --><!-- severity: critical -->{text}\n\n"
        "## Anti-Patterns\n\n"
    )


def test_resolver_merges_baseline_and_target_delta_with_provenance(tmp_path: Path) -> None:
    module = _load_module()
    baseline = tmp_path / "installed" / "bead-hygiene.md"
    target = tmp_path / "target"
    overlay = target / ".agents" / "standards" / "bead-hygiene.md"
    baseline.parent.mkdir(parents=True)
    overlay.parent.mkdir(parents=True)
    baseline.write_text(_contract("BASE-INTENT", "Intent is required."), encoding="utf-8")
    overlay.write_text(_delta("PROJECT-TRACE", "Trace evidence is required."), encoding="utf-8")

    result = module.resolve_contract(repo_root=target, baseline_path=baseline)

    assert result["status"] == "ok"
    assert [rule["rule_id"] for rule in result["rules"]] == ["BASE-INTENT", "PROJECT-TRACE"]
    assert [rule["provenance"] for rule in result["rules"]] == ["baseline", "project-delta"]
    assert result["sources"][0]["sha256"]
    assert result["sources"][1]["sha256"]


def test_resolver_deduplicates_identical_rule_and_blocks_conflict(tmp_path: Path) -> None:
    module = _load_module()
    baseline = tmp_path / "baseline.md"
    target = tmp_path / "target"
    overlay = target / ".agents" / "standards" / "bead-hygiene.md"
    overlay.parent.mkdir(parents=True)
    baseline.write_text(_contract("SHARED", "Intent is required."), encoding="utf-8")
    overlay.write_text(_delta("SHARED", "Intent is required."), encoding="utf-8")

    same = module.resolve_contract(repo_root=target, baseline_path=baseline)
    assert same["status"] == "ok"
    assert len(same["rules"]) == 1

    overlay.write_text(_delta("SHARED", "A different requirement."), encoding="utf-8")
    conflict = module.resolve_contract(repo_root=target, baseline_path=baseline)

    assert conflict["status"] == "conflict"
    assert conflict["diagnostics"][0]["code"] == "CONTRACT-RULE-CONFLICT"


def test_resolver_reports_optional_delta_and_missing_baseline(tmp_path: Path) -> None:
    module = _load_module()
    target = tmp_path / "target"
    target.mkdir()
    baseline = tmp_path / "baseline.md"
    baseline.write_text(_contract("BASE", "Intent is required."), encoding="utf-8")

    without_delta = module.resolve_contract(repo_root=target, baseline_path=baseline)
    assert without_delta["status"] == "ok"
    assert without_delta["sources"][1]["status"] == "not-found-optional"

    missing = module.resolve_contract(repo_root=target, baseline_path=tmp_path / "missing.md")
    assert missing["status"] == "configuration-error"
    assert missing["diagnostics"][0]["code"] == "CONTRACT-BASELINE-MISSING"


def test_legacy_rules_receive_stable_ids_and_migration_warning(tmp_path: Path) -> None:
    module = _load_module()
    baseline = tmp_path / "baseline.md"
    target = tmp_path / "target"
    target.mkdir()
    baseline.write_text(
        "# Bead Hygiene Standard\n\n## Pflichtfelder\n\n- Intent is required.\n",
        encoding="utf-8",
    )

    first = module.resolve_contract(repo_root=target, baseline_path=baseline)
    second = module.resolve_contract(repo_root=target, baseline_path=baseline)

    assert first["rules"][0]["rule_id"].startswith("LEGACY-")
    assert first["rules"][0]["rule_id"] == second["rules"][0]["rule_id"]
    assert any(item["code"] == "CONTRACT-RULE-ID-MISSING" for item in first["diagnostics"])


def test_project_full_copy_is_rejected(tmp_path: Path) -> None:
    module = _load_module()
    baseline = tmp_path / "baseline.md"
    target = tmp_path / "target"
    overlay = target / ".agents" / "standards" / "bead-hygiene.md"
    overlay.parent.mkdir(parents=True)
    content = _contract("BASE", "Intent is required.")
    baseline.write_text(content, encoding="utf-8")
    overlay.write_text(content, encoding="utf-8")

    result = module.resolve_contract(repo_root=target, baseline_path=baseline)

    assert result["status"] == "conflict"
    assert any(item["code"] == "OVERLAY-FULL-COPY" for item in result["diagnostics"])


def _delta_with_family(rule_text: str, allowed_values: list[str]) -> str:
    values = ",".join(f'"{value}"' for value in allowed_values)
    return (
        _delta("PROJECT", rule_text)
        + "\n```bead-label-families\n"
        + '{"families":[{"id":"ui","prefix":"ui:",'
        + f'"cardinality":"0..1","allowed_values":[{values}]'
        + "}]}\n```\n"
    )


def test_contract_sha_changes_for_rule_or_label_family_semantics(tmp_path: Path) -> None:
    module = _load_module()
    baseline = tmp_path / "baseline.md"
    target = tmp_path / "target"
    overlay = target / ".agents" / "standards" / "bead-hygiene.md"
    overlay.parent.mkdir(parents=True)
    baseline.write_text(_contract("BASE", "Intent is required."), encoding="utf-8")
    overlay.write_text(
        _delta_with_family("Trace evidence is required.", ["existing", "new"]),
        encoding="utf-8",
    )

    first = module.resolve_contract(repo_root=target, baseline_path=baseline)
    overlay.write_text(
        _delta_with_family("Different trace evidence is required.", ["existing", "new"]),
        encoding="utf-8",
    )
    changed_rule = module.resolve_contract(repo_root=target, baseline_path=baseline)

    assert first["contract_sha"] != changed_rule["contract_sha"]


def test_contract_sha_ignores_paths_diagnostics_and_set_order(tmp_path: Path) -> None:
    module = _load_module()
    baseline_a = tmp_path / "a" / "baseline.md"
    baseline_b = tmp_path / "b" / "baseline.md"
    target_a = tmp_path / "target-a"
    target_b = tmp_path / "target-b"
    for baseline in (baseline_a, baseline_b):
        baseline.parent.mkdir(parents=True)
        baseline.write_text(_contract("BASE", "Intent is required."), encoding="utf-8")
    for target, values in (
        (target_a, ["new", "existing"]),
        (target_b, ["existing", "new"]),
    ):
        overlay = target / ".agents" / "standards" / "bead-hygiene.md"
        overlay.parent.mkdir(parents=True)
        overlay.write_text(
            _delta_with_family("Trace evidence is required.", values),
            encoding="utf-8",
        )

    first = module.resolve_contract(repo_root=target_a, baseline_path=baseline_a)
    second = module.resolve_contract(repo_root=target_b, baseline_path=baseline_b)
    second["diagnostics"].append({"code": "IGNORED", "message": "not semantic"})

    assert first["contract_sha"] == second["contract_sha"]
    assert module.compute_contract_sha(second) == first["contract_sha"]

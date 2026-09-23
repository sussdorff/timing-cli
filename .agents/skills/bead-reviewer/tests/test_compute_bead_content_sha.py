from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_DIR = REPO_ROOT / "skills" / "bead-reviewer" / "scripts"
SCRIPT = SCRIPT_DIR / "compute_bead_content_sha.py"
sys.path.insert(0, str(SCRIPT_DIR))

import compute_bead_content_sha as sha_mod  # noqa: E402
from compute_bead_content_sha import compute_content_sha, compute_reviewer_sha  # noqa: E402


def _bead() -> dict:
    return {
        "title": "[ORCH] Canonical intent block",
        "description": "## Intent\nGoal: route by derived effort",
        "acceptance_criteria": "- AK-1: routed effort stored",
        "issue_type": "task",
        "parent": "clc-parent",
        "labels": ["pillar:workflow", "ui:existing-surface"],
        "dependencies": [
            {"id": "clc-b", "dependency_type": "depends_on"},
            {"id": "clc-a", "dependency_type": "depends_on"},
            {"id": "clc-note", "dependency_type": "discovered-from"},
        ],
        "metadata": {
            "intent": "legacy intent",
            "contracts": "legacy contracts",
            "constraints": "legacy constraints",
            "effort": "medium",
            "routing": {
                "routed_effort": "small",
                "routed_reason": "1 file, 1 test",
                "classifier": "haiku-test",
                "version": "1",
            },
            "review": {"content_sha": "old", "reviewer_sha": "old"},
        },
        "priority": 2,
        "status": "open",
    }


def test_live_bead_loader_binds_bd_to_explicit_repository(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured = {}

    def fake_run(*args, **kwargs):
        captured["argv"] = args[0]
        captured["cwd"] = kwargs["cwd"]
        return SimpleNamespace(returncode=0, stdout=json.dumps([_bead()]), stderr="")

    monkeypatch.setattr(sha_mod.subprocess, "run", fake_run)

    bead = sha_mod.load_live_bead("clc-demo", tmp_path)

    assert captured["argv"] == ["bd", "show", "clc-demo", "--json"]
    assert captured["cwd"] == tmp_path.resolve()
    assert bead["title"] == _bead()["title"]


def test_live_bead_loader_honors_reviewer_read_only_mode(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured = {}

    def fake_run(*args, **kwargs):
        captured["argv"] = args[0]
        return SimpleNamespace(returncode=0, stdout=json.dumps([_bead()]), stderr="")

    monkeypatch.setenv("BEAD_REVIEWER_BD_READONLY", "1")
    monkeypatch.setattr(sha_mod.subprocess, "run", fake_run)

    sha_mod.load_live_bead("clc-demo", tmp_path)

    assert captured["argv"] == [
        "bd",
        "--readonly",
        "--sandbox",
        "show",
        "clc-demo",
        "--json",
    ]


def test_legacy_metadata_fields_do_not_change_hash() -> None:
    bead = _bead()
    baseline = compute_content_sha(bead)

    for field, value in (
        ("intent", "different intent"),
        ("contracts", "different contracts"),
        ("constraints", "different constraints"),
        ("effort", "xl"),
    ):
        candidate = _bead()
        candidate["metadata"][field] = value
        assert compute_content_sha(candidate) == baseline


def test_routing_metadata_is_explicitly_excluded() -> None:
    bead = _bead()
    baseline = compute_content_sha(bead)

    candidate = _bead()
    candidate["metadata"]["routing"] = {
        "routed_effort": "extra-large",
        "routed_reason": "7 files, 4 tests, 3 surfaces",
        "classifier": "haiku-prod",
        "version": "2",
    }

    assert compute_content_sha(candidate) == baseline


def test_hash_changes_when_canonical_content_changes() -> None:
    bead = _bead()
    baseline = compute_content_sha(bead)

    changed = _bead()
    changed["description"] = "## Intent\nGoal: route by derived effort\nScope-In: update phase0"

    assert compute_content_sha(changed) != baseline


def test_hash_uses_issue_type_and_sorted_blockers() -> None:
    bead = _bead()
    baseline = compute_content_sha(bead)

    reordered = _bead()
    reordered["dependencies"] = list(reversed(reordered["dependencies"]))
    assert compute_content_sha(reordered) == baseline

    changed_type = _bead()
    changed_type["issue_type"] = "feature"
    assert compute_content_sha(changed_type) != baseline


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("title", "A different outcome"),
        ("description", "A different body"),
        ("acceptance_criteria", "A different criterion"),
        ("issue_type", "feature"),
        ("parent", "clc-other-parent"),
    ],
)
def test_hash_changes_for_every_review_owned_field(field: str, value: object) -> None:
    baseline = compute_content_sha(_bead())
    changed = _bead()
    changed[field] = value

    assert compute_content_sha(changed) != baseline


def test_hash_uses_sorted_labels_and_all_outgoing_relationships() -> None:
    baseline = _bead()
    reordered = _bead()
    reordered["labels"] = list(reversed(reordered["labels"]))
    reordered["dependencies"] = list(reversed(reordered["dependencies"]))

    families = [{"prefix": "pillar:"}, {"prefix": "ui:"}]
    assert compute_content_sha(
        reordered, label_families=families
    ) == compute_content_sha(baseline, label_families=families)

    changed_provenance = _bead()
    changed_provenance["dependencies"][-1] = {
        "id": "clc-other-origin",
        "dependency_type": "discovered-from",
    }
    assert compute_content_sha(changed_provenance) != compute_content_sha(baseline)


def test_hash_includes_only_declared_label_family_prefixes() -> None:
    families = [
        {"id": "pillar", "prefix": "pillar:"},
        {"id": "ui", "prefix": "ui:"},
    ]
    baseline = _bead()
    changed = _bead()
    changed["labels"] = [
        "pillar:workflow",
        "ui:existing-surface",
        "session:pilot",
        "claim:reviewed",
        "status:triaged",
    ]

    assert compute_content_sha(changed, label_families=families) == (
        compute_content_sha(baseline, label_families=families)
    )


def test_operational_labels_do_not_change_hash() -> None:
    baseline = _bead()
    changed = _bead()
    changed["labels"] = [
        *baseline["labels"],
        "session:pilot",
        "claim:reviewed",
        "status:triaged",
    ]

    assert compute_content_sha(changed, label_families=[]) == (
        compute_content_sha(baseline, label_families=[])
    )


def test_declared_semantic_label_changes_hash_and_order_does_not() -> None:
    families = [
        {"id": "pillar", "prefix": "pillar:"},
        {"id": "ui", "prefix": "ui:"},
    ]
    baseline = _bead()
    reordered = _bead()
    reordered["labels"] = list(reversed(reordered["labels"]))
    changed = _bead()
    changed["labels"] = ["pillar:workflow", "ui:design-needed"]

    assert compute_content_sha(reordered, label_families=families) == (
        compute_content_sha(baseline, label_families=families)
    )
    assert compute_content_sha(changed, label_families=families) != (
        compute_content_sha(baseline, label_families=families)
    )


def test_hash_accepts_parent_object_and_excludes_incoming_relationships() -> None:
    canonical = _bead()
    canonical["parent"] = {"id": "clc-parent", "title": "Parent"}
    incoming_changed = _bead()
    incoming_changed["dependents"] = [{"id": "clc-child", "status": "open"}]
    incoming_changed["children"] = [{"id": "clc-child", "status": "open"}]

    assert compute_content_sha(canonical) == compute_content_sha(_bead())
    assert compute_content_sha(incoming_changed) == compute_content_sha(_bead())


@pytest.mark.parametrize("field", ["priority", "status", "assignee", "updated_at"])
def test_operational_fields_do_not_change_hash(field: str) -> None:
    baseline = compute_content_sha(_bead())
    changed = _bead()
    changed[field] = "changed"

    assert compute_content_sha(changed) == baseline


def test_cli_accepts_raw_control_chars_in_strings(tmp_path: Path) -> None:
    """Regression: bd show --json can emit JSON with raw tabs/newlines inside
    string values (when a bead description embeds code blocks). The CLI must
    parse such payloads instead of failing with json.JSONDecodeError.
    """
    payload = (
        '[{"id": "clc-x",'
        ' "title": "raw-ctrl",'
        # raw tab + raw newline inside the description string — illegal under
        # strict JSON, but produced by bd in the wild.
        ' "description": "code:\tline1\nline2",'
        ' "acceptance_criteria": "",'
        ' "issue_type": "task",'
        ' "dependencies": []}]'
    )

    # Sanity: this is exactly the payload shape that strict json rejects.
    try:
        json.loads(payload)
    except json.JSONDecodeError:
        pass
    else:
        raise AssertionError(
            "test fixture must contain raw control chars that strict json rejects"
        )

    result = subprocess.run(
        [sys.executable, str(SCRIPT)],
        input=payload,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, (
        f"CLI failed on payload with raw control chars: stderr={result.stderr!r}"
    )
    out = json.loads(result.stdout)
    assert "content_sha" in out and len(out["content_sha"]) == 64
    assert "reviewer_sha" in out


def test_cli_filters_labels_through_the_resolved_contract(tmp_path: Path) -> None:
    overlay = tmp_path / ".agents" / "standards" / "bead-hygiene.md"
    overlay.parent.mkdir(parents=True)
    overlay.write_text(
        """
```bead-label-families
{"families":[{"id":"ui","prefix":"ui:","cardinality":"0..1"}]}
```
""".strip(),
        encoding="utf-8",
    )
    baseline = _bead()
    baseline["labels"] = ["ui:existing-surface"]
    operational = {**baseline, "labels": [*baseline["labels"], "session:pilot"]}
    semantic = {**baseline, "labels": ["ui:design-needed"]}

    def cli_sha(bead: dict) -> str:
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--repo-root",
                str(tmp_path),
                "--bead-json",
                json.dumps(bead),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, result.stderr
        return json.loads(result.stdout)["content_sha"]

    assert cli_sha(operational) == cli_sha(baseline)
    assert cli_sha(semantic) != cli_sha(baseline)


def test_content_sha_docstring_explains_routing_exclusion() -> None:
    doc = compute_content_sha.__doc__ or ""

    assert "execution routes are not inputs to specification review" in doc


def test_reviewer_sha_is_deterministic() -> None:
    sha1 = compute_reviewer_sha()
    sha2 = compute_reviewer_sha()

    if sha1 == "unknown":
        pytest.skip("SKILL.md not found; cannot test reviewer_sha determinism")

    assert sha1 == sha2
    assert len(sha1) == 64


def _write_reviewer_tree(
    root: Path,
    *,
    skill: str = "skill v1",
    reference: str = "review contract v1",
    result_contract: str = "result contract v1",
    contract_loader: str = "loader v1",
    finding_registry: str = "registry v1",
    finding_rules: str = "finding rules v1",
    agent_prompt: str = "agent prompt v1",
) -> Path:
    skill_path = root / "skills" / "bead-reviewer" / "SKILL.md"
    reference_path = root / "skills" / "bead-reviewer" / "references" / "review-contract.md"
    result_contract_path = root / "skills" / "bead-reviewer" / "scripts" / "review_contract.py"
    contract_loader_path = root / "skills" / "bead-reviewer" / "scripts" / "contract_loader.py"
    finding_registry_path = root / "skills" / "bead-reviewer" / "references" / "finding-rule-registry.json"
    finding_rules_path = root / "skills" / "bead-reviewer" / "scripts" / "finding_rules.py"
    agent_path = root / "agents" / "bead-spec-reviewer.md"
    module_path = root / "skills" / "bead-reviewer" / "scripts" / "compute_bead_content_sha.py"

    skill_path.parent.mkdir(parents=True)
    reference_path.parent.mkdir(parents=True)
    module_path.parent.mkdir(parents=True)
    agent_path.parent.mkdir(parents=True)

    skill_path.write_text(skill, encoding="utf-8")
    reference_path.write_text(reference, encoding="utf-8")
    result_contract_path.write_text(result_contract, encoding="utf-8")
    contract_loader_path.write_text(contract_loader, encoding="utf-8")
    finding_registry_path.write_text(finding_registry, encoding="utf-8")
    finding_rules_path.write_text(finding_rules, encoding="utf-8")
    agent_path.write_text(agent_prompt, encoding="utf-8")
    return module_path


def test_reviewer_sha_changes_when_review_contract_changes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module_path = _write_reviewer_tree(tmp_path)
    monkeypatch.setattr(sha_mod, "__file__", str(module_path))

    baseline = sha_mod.compute_reviewer_sha()
    (tmp_path / "skills" / "bead-reviewer" / "references" / "review-contract.md").write_text(
        "review contract v2",
        encoding="utf-8",
    )

    assert sha_mod.compute_reviewer_sha() != baseline


def test_reviewer_sha_changes_when_result_contract_changes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module_path = _write_reviewer_tree(tmp_path)
    monkeypatch.setattr(sha_mod, "__file__", str(module_path))

    baseline = sha_mod.compute_reviewer_sha()
    (tmp_path / "skills" / "bead-reviewer" / "scripts" / "review_contract.py").write_text(
        "result contract v2",
        encoding="utf-8",
    )

    assert sha_mod.compute_reviewer_sha() != baseline


def test_reviewer_sha_changes_when_contract_loader_changes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module_path = _write_reviewer_tree(tmp_path)
    monkeypatch.setattr(sha_mod, "__file__", str(module_path))

    baseline = sha_mod.compute_reviewer_sha()
    (
        tmp_path / "skills" / "bead-reviewer" / "scripts" / "contract_loader.py"
    ).write_text(
        "loader v2",
        encoding="utf-8",
    )

    assert sha_mod.compute_reviewer_sha() != baseline


@pytest.mark.parametrize(
    ("relative_path", "replacement"),
    [
        (("references", "finding-rule-registry.json"), "registry v2"),
        (("scripts", "finding_rules.py"), "finding rules v2"),
    ],
)
def test_reviewer_sha_changes_when_finding_taxonomy_changes(
    relative_path: tuple[str, str],
    replacement: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module_path = _write_reviewer_tree(tmp_path)
    monkeypatch.setattr(sha_mod, "__file__", str(module_path))

    baseline = sha_mod.compute_reviewer_sha()
    (tmp_path / "skills" / "bead-reviewer" / Path(*relative_path)).write_text(
        replacement,
        encoding="utf-8",
    )

    assert sha_mod.compute_reviewer_sha() != baseline


def test_reviewer_sha_changes_when_agent_prompt_changes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module_path = _write_reviewer_tree(tmp_path)
    monkeypatch.setattr(sha_mod, "__file__", str(module_path))
    baseline = sha_mod.compute_reviewer_sha()

    (tmp_path / "agents" / "bead-spec-reviewer.md").write_text(
        "agent prompt v2", encoding="utf-8"
    )

    assert sha_mod.compute_reviewer_sha() != baseline


def test_reviewer_sha_uses_empty_components_when_contract_sources_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module_path = _write_reviewer_tree(tmp_path)
    monkeypatch.setattr(sha_mod, "__file__", str(module_path))

    baseline = sha_mod.compute_reviewer_sha()
    (tmp_path / "skills" / "bead-reviewer" / "references" / "review-contract.md").unlink()
    (tmp_path / "skills" / "bead-reviewer" / "scripts" / "review_contract.py").unlink()
    (tmp_path / "skills" / "bead-reviewer" / "scripts" / "contract_loader.py").unlink()
    (tmp_path / "skills" / "bead-reviewer" / "references" / "finding-rule-registry.json").unlink()
    (tmp_path / "skills" / "bead-reviewer" / "scripts" / "finding_rules.py").unlink()

    missing_source_sha = sha_mod.compute_reviewer_sha()

    assert missing_source_sha != "unknown"
    assert len(missing_source_sha) == 64
    assert missing_source_sha != baseline

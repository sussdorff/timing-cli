from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
DECISION_BRIEF = ROOT / "standards" / "judge-layer" / "decision-brief.md"
STOP_TAXONOMY = ROOT / "standards" / "judge-layer" / "stop-taxonomy.md"
DECISION_GATE = ROOT / "standards" / "judge-layer" / "decision-gate.md"
MANDATE_SCHEMA = ROOT / "standards" / "judge-layer" / "mandate-schema.md"


RISK_CLASSES = {
    "read-only",
    "reversible-write",
    "external-side-effect",
    "high-risk",
}
JUDGE_OUTCOMES = {"ALLOW", "BLOCK", "REVISE", "ESCALATE"}
GATE_FIELDS = {
    "decision owner",
    "allowed outcomes",
    "trigger timing",
    "minimum evidence plan",
    "operational do-nothing/default outcome",
    "delivery consequence",
    "overrideability",
    "sequencing constraints",
}
MANDATE_REQUIRED_FIELDS = {
    "scope",
    "limits",
    "evidence_refs",
    "granted_at",
    "granted_by",
    "expires_at",
    "supersedes",
}


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _field_names_from_required_table(markdown: str) -> set[str]:
    fields: set[str] = set()
    in_required = False
    for line in markdown.splitlines():
        if line.startswith("## "):
            in_required = line.strip() == "## Required Fields"
            continue
        if not in_required or not line.startswith("| `"):
            continue
        field = line.split("|", 2)[1].strip().strip("`").lower()
        fields.add(field)
    return fields


def test_decision_brief_contract_has_manager_view_and_evidence_appendix() -> None:
    text = _read(DECISION_BRIEF)

    assert "Contract URI: `standard://judge-layer/decision-brief.v1`" in text
    assert "## Compact Manager View" in text
    assert "## Evidence Appendix" in text
    assert "deterministic structural validation" in text.lower()
    assert "does not prove truth" in text.lower()


def test_stop_taxonomy_crosswalks_existing_judge_layer_contracts() -> None:
    text = _read(STOP_TAXONOMY)

    for risk_class in RISK_CLASSES:
        assert f"`{risk_class}`" in text
    for outcome in JUDGE_OUTCOMES:
        assert f"`{outcome}`" in text
    assert "risk upgrades are unilateral" in text.lower()
    assert "downgrades require independent concurrence" in text.lower()
    assert "delivery pressure never lowers the operational-risk bar" in text.lower()
    assert "deterministic predicates establish bounds" in text.lower()


def test_decision_gate_contract_uses_judge_outcomes_and_mandate_reference() -> None:
    text = _read(DECISION_GATE)
    fields = _field_names_from_required_table(text)

    assert GATE_FIELDS <= fields
    assert not fields & MANDATE_REQUIRED_FIELDS
    for outcome in JUDGE_OUTCOMES:
        assert f"`{outcome}`" in text
    assert "standard://judge-layer/mandates/mandate.v1" in text
    assert "mandate-schema.md" in text
    assert "no inline authorization fields" in text.lower()
    assert "outside ordinary outcome acceptance criteria" in text.lower()
    assert "clc-h4nm" in text
    assert "non-blocking" in text.lower()


def test_decision_gate_field_set_is_disjoint_from_mandate_required_fields() -> None:
    gate_text = _read(DECISION_GATE)
    mandate_text = _read(MANDATE_SCHEMA)
    gate_fields = _field_names_from_required_table(gate_text)
    mandate_fields = _field_names_from_required_table(mandate_text)

    assert MANDATE_REQUIRED_FIELDS <= mandate_fields
    assert not gate_fields & MANDATE_REQUIRED_FIELDS
    assert "mandate-schema.md" in gate_text


def test_no_typed_decision_gate_bead_schema_field_is_introduced() -> None:
    assert not (ROOT / "mcp-servers").exists()

    scanned_files = [ROOT / "scripts" / "bead-author-check.py"]

    for path in scanned_files:
        assert "metadata.decision_gates" not in _read(path)

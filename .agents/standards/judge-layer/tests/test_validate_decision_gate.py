import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "standards" / "judge-layer" / "scripts" / "validate_decision_gate.py"


def valid_document() -> str:
    return """# Release Decision

## Decision Brief

### Compact Manager View

Decision required: Choose whether to proceed with the deployment.
Recommended default: BLOCK until rollback evidence exists.
Operational risk: external-side-effect.
Operational do-nothing/default outcome: Do not deploy.
Delivery consequence: Delivery slips one day.
Decision needed by: 2026-07-14T18:00:00Z.

### Evidence Appendix

Evidence appendix references: tests/release/rollback.test.ts.
Blast radius: One deployment environment.
Rollback path: Revert the deployment tag.
Alternatives considered: Wait for the next window.

## Human Decision Gate

Decision owner: Release manager.
Approval class: production-change.
Allowed outcomes: ALLOW, BLOCK, REVISE, ESCALATE.
Trigger timing: Before deployment.
Minimum evidence plan: Run rollback smoke test and deployment dry run.
Operational do-nothing/default outcome: Keep the current release in place.
Delivery consequence: Delivery waits for the next window.
Overrideability: Not overrideable by the implementation agent.
Sequencing constraints: Evidence must be gathered before the gate is presented.
"""


def run_validator(text: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "-"],
        input=text,
        capture_output=True,
        text=True,
        check=False,
    )


def test_valid_decision_brief_and_gate_pass() -> None:
    result = run_validator(valid_document())

    assert result.returncode == 0, result.stdout + result.stderr
    data = json.loads(result.stdout)
    assert data["status"] == "ok"
    assert data["data"]["decision_brief"] is True
    assert data["data"]["human_decision_gate"] is True


def test_missing_decision_gate_field_fails() -> None:
    payload = valid_document().replace(
        "Minimum evidence plan: Run rollback smoke test and deployment dry run.\n",
        "",
    )

    result = run_validator(payload)

    assert result.returncode == 1
    data = json.loads(result.stdout)
    assert data["status"] == "error"
    assert any("Minimum evidence plan" in error for error in data["errors"])


def test_invalid_allowed_outcome_fails_without_semantic_risk_judgment() -> None:
    payload = valid_document().replace(
        "Allowed outcomes: ALLOW, BLOCK, REVISE, ESCALATE.",
        "Allowed outcomes: approve, reject.",
    )

    result = run_validator(payload)

    assert result.returncode == 1
    data = json.loads(result.stdout)
    assert any("Allowed outcomes" in error for error in data["errors"])
    assert not any("false urgency" in error.lower() for error in data["errors"])
    assert not any("residual risk" in error.lower() for error in data["errors"])


def test_mandate_field_names_are_rejected_as_gate_fields() -> None:
    payload = valid_document().replace(
        "Sequencing constraints: Evidence must be gathered before the gate is presented.\n",
        "Sequencing constraints: Evidence must be gathered before the gate is presented.\n"
        "scope: release deployment.\n",
    )

    result = run_validator(payload)

    assert result.returncode == 1
    data = json.loads(result.stdout)
    assert any("Mandate" in error and "scope" in error for error in data["errors"])


def test_gate_without_approval_class_fails() -> None:
    payload = valid_document().replace("Approval class: production-change.\n", "")

    result = run_validator(payload)

    assert result.returncode == 1
    errors = json.loads(result.stdout)["errors"]
    assert any("Approval class" in error for error in errors)


def test_gate_for_internal_work_fails() -> None:
    payload = valid_document().replace(
        "Approval class: production-change.", "Approval class: secret-creation."
    )

    result = run_validator(payload)

    assert result.returncode == 1
    errors = json.loads(result.stdout)["errors"]
    assert any("production-change, customer-message" in error for error in errors)


def test_customer_message_gate_passes() -> None:
    payload = valid_document().replace(
        "Approval class: production-change.", "Approval class: customer-message."
    )

    result = run_validator(payload)

    assert result.returncode == 0, result.stdout


def test_punctuation_only_approval_class_fails() -> None:
    for value in (".", "`", "...", " . "):
        payload = valid_document().replace(
            "Approval class: production-change.", f"Approval class: {value}"
        )
        result = run_validator(payload)
        assert result.returncode == 1, value


def test_second_gate_fails() -> None:
    second = valid_document().split("## Human Decision Gate", 1)[1].replace(
        "Approval class: production-change.", "Approval class: customer-message."
    )
    payload = valid_document() + "\n## Human Decision Gate" + second

    result = run_validator(payload)

    assert result.returncode == 1
    errors = json.loads(result.stdout)["errors"]
    assert any("one ## Human Decision Gate" in error for error in errors)


def test_second_gate_with_variant_heading_fails() -> None:
    body = valid_document().split("## Human Decision Gate", 1)[1]
    for heading in ["## Human Decision Gate 2", "## Human Decision Gate (stage 2)", "## Human Decision Gate: customer message", "## human decision gate"]:
        result = run_validator(valid_document() + "\n" + heading + body)
        assert result.returncode == 1, heading

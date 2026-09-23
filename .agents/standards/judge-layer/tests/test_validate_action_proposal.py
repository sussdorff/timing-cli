import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "standards" / "judge-layer" / "scripts" / "validate_action_proposal.py"


def valid_proposal():
    return {
        "proposal_id": "p-valid",
        "actor_ref": "skill://mail-send",
        "risk_class": "external-side-effect",
        "effect_type": "messaging",
        "intended_action": {
            "verb": "send",
            "target": "email",
            "arguments": {"to": "customer@example.com"},
        },
        "reason": "User approved sending the message.",
        "evidence_refs": [{"ref": "conversation://current/user-approval", "label": "observed"}],
        "authorization": {"mandate_ref": "mandate://mail/customer"},
        "expected_consequence": "Customer receives the approved message.",
        "rollback_path": "Send a correction email.",
    }


def run_validator(payload):
    return subprocess.run(
        [sys.executable, str(SCRIPT), "-"],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        check=False,
    )


def test_valid_action_proposal_passes():
    result = run_validator(valid_proposal())

    assert result.returncode == 0, result.stdout + result.stderr
    data = json.loads(result.stdout)
    assert data["status"] == "ok"
    assert data["data"]["proposal_id"] == "p-valid"


def test_missing_required_field_fails():
    payload = valid_proposal()
    payload.pop("intended_action")

    result = run_validator(payload)

    assert result.returncode == 1
    data = json.loads(result.stdout)
    assert data["status"] == "error"
    assert any("intended_action" in error for error in data["errors"])


def test_bad_enum_and_bad_provenance_label_fail():
    payload = valid_proposal()
    payload["risk_class"] = "side-effect"
    payload["evidence_refs"][0]["label"] = "trusted"

    result = run_validator(payload)

    assert result.returncode == 1
    data = json.loads(result.stdout)
    assert any("risk_class" in error for error in data["errors"])
    assert any("provenance label" in error for error in data["errors"])

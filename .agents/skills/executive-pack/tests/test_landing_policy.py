"""Table-driven contract for the single landing-policy resolver.

Every default, every elevation source, and every fail-closed refusal is decided
here and nowhere else. A caller that restates the matrix in prose is a second
contract that can disagree with this one, so `tests/test_executive_pack_workflow.py`
pins that no caller does.
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "skills" / "executive-pack" / "scripts" / "landing_policy.py"
requires_ccore = pytest.mark.skipif(
    shutil.which("ccore") is None,
    reason="ccore is not installed; run `uv tool install cognovis-core-tools`",
)


def _module():
    spec = importlib.util.spec_from_file_location("landing_policy", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )


@pytest.mark.parametrize(
    ("delivery_mode", "bead_type", "review_risk", "expected"),
    [
        ("solo", "bug", "none", "direct"),
        ("solo", "feature", "none", "pr-auto"),
        ("solo", "task", "none", "pr-auto"),
        ("solo", "chore", "none", "pr-auto"),
        ("solo", "epic", "none", "pr-auto"),
        ("executive-pack", "bug", "none", "pr-review"),
        ("executive-pack", "feature", "none", "pr-review"),
    ],
)
def test_defaults_follow_delivery_mode_and_bead_type(
    delivery_mode: str, bead_type: str, review_risk: str, expected: str
) -> None:
    module = _module()

    result = module.resolve(
        delivery_mode=delivery_mode, bead_type=bead_type, review_risk=review_risk
    )

    assert result["policy"] == expected
    assert result["baseline"] == expected
    assert result["status"] == "ok"


@pytest.mark.parametrize("risk", ["payment", "pii", "auth", "compliance"])
def test_security_sensitive_risk_always_resolves_to_pr_review(risk: str) -> None:
    module = _module()

    result = module.resolve(delivery_mode="solo", bead_type="bug", review_risk=risk)

    assert result["policy"] == "pr-review"
    assert [item["source"] for item in result["elevations"]] == ["review_risk"]
    assert result["elevations"][0]["from"] == "direct"
    assert result["elevations"][0]["to"] == "pr-review"


@pytest.mark.parametrize(
    ("source", "value", "expected"),
    [
        ("repository_policy", "pr-auto", "pr-auto"),
        ("repository_policy", "pr-review", "pr-review"),
        ("branch_protection", True, "pr-auto"),
        ("override", "pr-auto", "pr-auto"),
        ("override", "pr-review", "pr-review"),
    ],
)
def test_every_elevation_source_raises_a_low_risk_solo_bug(
    source: str, value: object, expected: str
) -> None:
    module = _module()

    result = module.resolve(
        delivery_mode="solo",
        bead_type="bug",
        review_risk="none",
        **{source: value},
    )

    assert result["baseline"] == "direct"
    assert result["policy"] == expected
    assert [item["source"] for item in result["elevations"]] == [source]


def test_elevations_are_recorded_in_monotonic_order() -> None:
    module = _module()

    result = module.resolve(
        delivery_mode="solo",
        bead_type="bug",
        review_risk="auth",
        branch_protection=True,
    )

    assert result["policy"] == "pr-review"
    steps = [(item["from"], item["to"]) for item in result["elevations"]]
    assert steps == [("direct", "pr-auto"), ("pr-auto", "pr-review")]
    assert [item["source"] for item in result["elevations"]] == [
        "branch_protection",
        "review_risk",
    ]


@pytest.mark.parametrize(
    ("repository_policy", "expected"),
    [("direct", "pr-review"), ("pr-auto", "pr-review")],
)
def test_a_lower_repository_policy_never_lowers_the_resolved_policy(
    repository_policy: str, expected: str
) -> None:
    module = _module()

    result = module.resolve(
        delivery_mode="executive-pack",
        bead_type="feature",
        review_risk="none",
        repository_policy=repository_policy,
    )

    assert result["policy"] == expected
    assert result["ignored_inputs"] == [
        {
            "source": "repository_policy",
            "value": repository_policy,
            "disposition": "already_satisfied",
            "reason": "the resolved policy already meets this floor",
        }
    ]


def test_an_input_the_policy_already_satisfies_is_not_recorded_as_refused() -> None:
    """Two different facts deserve two different words.

    Payment risk on an already-`pr-review` delivery asked for nothing it did
    not get. Filing it under the same downgrade-refusal reason as a genuine
    lower input makes the audit record read as if the risk had been overruled.
    """
    module = _module()

    result = module.resolve(
        delivery_mode="executive-pack",
        bead_type="feature",
        review_risk="payment",
        branch_protection=True,
    )

    assert result["policy"] == "pr-review"
    dispositions = {
        item["source"]: item["disposition"] for item in result["ignored_inputs"]
    }
    assert dispositions == {
        "branch_protection": "already_satisfied",
        "review_risk": "already_satisfied",
    }
    for item in result["ignored_inputs"]:
        assert "never lowered" not in item["reason"]


def test_an_ignored_input_records_what_the_caller_passed() -> None:
    module = _module()

    result = module.resolve(
        delivery_mode="executive-pack",
        bead_type="feature",
        review_risk="payment",
        branch_protection=True,
    )

    assert result["policy"] == "pr-review"
    assert {item["source"]: item["value"] for item in result["ignored_inputs"]} == {
        "branch_protection": True,
        "review_risk": "payment",
    }


def test_an_explicit_lower_override_is_refused_instead_of_silently_dropped() -> None:
    module = _module()

    with pytest.raises(module.LandingPolicyError) as excinfo:
        module.resolve(
            delivery_mode="solo",
            bead_type="feature",
            review_risk="payment",
            override="direct",
        )

    error = excinfo.value
    assert error.code == "LANDING_POLICY_DOWNGRADE_REFUSED"
    assert error.details["resolved_policy"] == "pr-review"
    assert error.details["override"] == "direct"
    assert error.remedy


@pytest.mark.parametrize(
    ("kwargs", "code"),
    [
        ({"review_risk": None}, "REVIEW_RISK_MISSING"),
        ({"review_risk": ""}, "REVIEW_RISK_MISSING"),
        ({"review_risk": "medium"}, "REVIEW_RISK_UNKNOWN"),
        ({"delivery_mode": "topic"}, "DELIVERY_MODE_UNKNOWN"),
        ({"bead_type": ""}, "BEAD_TYPE_MISSING"),
        ({"bead_type": "spike"}, "BEAD_TYPE_UNKNOWN"),
        ({"repository_policy": "merge"}, "REPOSITORY_POLICY_UNKNOWN"),
        ({"override": "ship-it"}, "OVERRIDE_UNKNOWN"),
    ],
)
def test_unusable_input_fails_closed_before_dispatch(
    kwargs: dict[str, object], code: str
) -> None:
    module = _module()
    request = {
        "delivery_mode": "solo",
        "bead_type": "feature",
        "review_risk": "none",
        **kwargs,
    }

    with pytest.raises(module.LandingPolicyError) as excinfo:
        module.resolve(**request)

    assert excinfo.value.code == code
    assert excinfo.value.remedy


@pytest.mark.parametrize(
    ("policy", "publish_tail", "publication_status", "terminal_tail"),
    [
        ("direct", ["--delivery", "merge"], "completed", None),
        (
            "pr-auto",
            ["--delivery", "pr", "--merge-authority", "agent_bot"],
            "completed",
            None,
        ),
        (
            "pr-review",
            ["--delivery", "pr", "--merge-authority", "human"],
            "review_pending",
            ["complete-pr", "--session-id", "<session-id>"],
        ),
    ],
)
def test_each_policy_maps_to_released_ccore_commands(
    policy: str,
    publish_tail: list[str],
    publication_status: str,
    terminal_tail: list[str] | None,
) -> None:
    module = _module()

    commands = module.commands(policy)

    assert commands["publish"][:3] == ["ccore", "session-close", "run"]
    assert commands["publish"][-len(publish_tail) :] == publish_tail
    assert commands["publication_status"] == publication_status
    if terminal_tail is None:
        assert commands["terminal"] is None
    else:
        assert commands["terminal"][:2] == ["ccore", "session-close"]
        assert commands["terminal"][2:] == terminal_tail
    assert commands["terminal_status"] == "completed"


def test_pr_policies_declare_who_authorizes_the_merge() -> None:
    module = _module()

    assert module.commands("pr-auto")["merge_authority"] == "agent_bot"
    assert module.commands("pr-review")["merge_authority"] == "human"
    assert module.commands("direct")["merge_authority"] == "session_close_merge"


def test_a_known_session_id_is_substituted_into_the_human_review_resume() -> None:
    module = _module()

    commands = module.commands("pr-review", session_id="sc-2026-08-23-abcd")

    assert "--session-id" in commands["terminal"]
    index = commands["terminal"].index("--session-id")
    assert commands["terminal"][index + 1] == "sc-2026-08-23-abcd"
    assert commands["placeholders"] == []


def test_an_unknown_human_review_session_id_leaves_a_declared_placeholder() -> None:
    module = _module()

    commands = module.commands("pr-review")

    assert commands["placeholders"] == ["<session-id>"]


def test_the_direct_policy_needs_no_session_identity() -> None:
    module = _module()

    assert module.commands("direct", session_id="sc-1")["terminal"] is None
    assert module.commands("direct")["placeholders"] == []


def test_resolve_threads_the_session_id_into_its_command_plan() -> None:
    module = _module()

    result = module.resolve(
        delivery_mode="executive-pack",
        bead_type="feature",
        review_risk="none",
        session_id="sc-77",
    )

    assert result["inputs"]["session_id"] == "sc-77"
    assert "sc-77" in result["commands"]["terminal"]


@requires_ccore
def test_the_emitted_human_review_resume_satisfies_the_real_cli() -> None:
    """The plan must be executable, not merely plausible.

    `--session-id` is a required argument of the released `complete-pr`. A plan
    that omits it produces a command the CLI rejects before it does any work.
    """
    module = _module()
    terminal = module.commands("pr-review", session_id="sc-probe")

    assert "--session-id" in terminal["terminal"]

    without_identity = [
        token
        for index, token in enumerate(terminal["terminal"])
        if token != "--session-id" and terminal["terminal"][index - 1] != "--session-id"
    ]
    rejected = subprocess.run(
        [*without_identity, "--help-does-not-matter"],
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )

    assert rejected.returncode != 0
    assert "--session-id" in rejected.stderr


@requires_ccore
def test_pr_publication_plans_supply_the_authority_required_by_ccore() -> None:
    help_result = subprocess.run(
        ["ccore", "session-close", "run", "--help"],
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )
    assert help_result.returncode == 0
    assert "--merge-authority {human,agent_bot}" in help_result.stdout

    module = _module()
    assert module.commands("pr-auto")["publish"][-2:] == [
        "--merge-authority",
        "agent_bot",
    ]
    assert module.commands("pr-review")["publish"][-2:] == [
        "--merge-authority",
        "human",
    ]


def test_a_body_classification_cannot_be_silently_overridden() -> None:
    """A durable classification outranks a flag that disagrees with it.

    Letting `--review-risk none` win over a body that says `auth` would lower an
    already recorded policy through the back door -- exactly what the monotonic
    rule forbids everywhere else.
    """
    module = _module()

    with pytest.raises(module.LandingPolicyError) as excinfo:
        module.resolve_review_risk(
            review_risk="none", description="Review-Risk: auth\n"
        )

    error = excinfo.value
    assert error.code == "REVIEW_RISK_CONFLICTING"
    assert error.details["declared"] == "none"
    assert error.details["recorded"] == "auth"


def test_agreeing_sources_resolve_to_the_one_classification() -> None:
    module = _module()

    assert (
        module.resolve_review_risk(
            review_risk="auth", description="Review-Risk: auth\n"
        )
        == "auth"
    )


def test_either_source_alone_satisfies_the_python_api() -> None:
    """The Python API stays flexible; the agent-facing CLI is the gate.

    A caller inside this repository may already hold the classification. An
    agent at a shell must not be able to assert one the bead body never
    recorded, which `test_cli_requires_the_bead_body` pins.
    """
    module = _module()

    assert module.resolve_review_risk(review_risk="pii") == "pii"
    assert module.resolve_review_risk(description="Review-Risk: pii\n") == "pii"


def test_cli_requires_the_bead_body_so_a_flag_cannot_stand_alone() -> None:
    result = _run(
        "resolve",
        "--delivery-mode",
        "solo",
        "--bead-type",
        "bug",
        "--review-risk",
        "none",
    )

    assert result.returncode == 2
    payload = json.loads(result.stdout)
    assert payload["code"] == "BEAD_BODY_REQUIRED"
    assert "--bead-body-file" in payload["remedy"]


def test_cli_accepts_a_flag_that_agrees_with_the_body(tmp_path: Path) -> None:
    body = tmp_path / "body.md"
    body.write_text("## Intent\n\nReview-Risk: none\n", encoding="utf-8")

    result = _run(
        "resolve",
        "--delivery-mode",
        "solo",
        "--bead-type",
        "bug",
        "--bead-body-file",
        str(body),
        "--review-risk",
        "none",
    )

    assert result.returncode == 0, result.stdout
    assert json.loads(result.stdout)["policy"] == "direct"


def test_no_source_at_all_still_fails_closed() -> None:
    module = _module()

    with pytest.raises(module.LandingPolicyError) as excinfo:
        module.resolve_review_risk()

    assert excinfo.value.code == "REVIEW_RISK_MISSING"


def test_cli_refuses_a_flag_that_contradicts_the_bead_body(tmp_path: Path) -> None:
    body = tmp_path / "body.md"
    body.write_text("## Intent\n\nReview-Risk: auth\n", encoding="utf-8")

    result = _run(
        "resolve",
        "--delivery-mode",
        "solo",
        "--bead-type",
        "bug",
        "--bead-body-file",
        str(body),
        "--review-risk",
        "none",
    )

    assert result.returncode == 2
    payload = json.loads(result.stdout)
    assert payload["code"] == "REVIEW_RISK_CONFLICTING"
    assert payload["details"]["recorded"] == "auth"


def test_exactly_one_review_risk_line_is_read_from_the_bead_body() -> None:
    module = _module()

    body = (
        "## Intent\n\n"
        "Goal: Ship the thing.\n"
        "Review-Risk: pii\n"
        "Scope-In: One surface.\n"
    )

    assert module.review_risk_from_body(body) == "pii"


@pytest.mark.parametrize(
    "line",
    [
        "Review-Risk: PII",
        "- Review-Risk: pii",
        "**Review-Risk**: pii",
        "- **Review-Risk:** pii",
    ],
)
def test_the_review_risk_field_tolerates_ordinary_bead_formatting(line: str) -> None:
    module = _module()

    assert module.review_risk_from_body(f"## Intent\n\n{line}\n") == "pii"


@pytest.mark.parametrize(
    ("body", "code"),
    [
        ("## Intent\n\nGoal: Ship the thing.\n", "REVIEW_RISK_MISSING"),
        ("Review-Risk: medium\n", "REVIEW_RISK_UNKNOWN"),
        ("Review-Risk: none\nReview-Risk: auth\n", "REVIEW_RISK_CONFLICTING"),
        ("Review-Risk: none\nReview-Risk: none\n", "REVIEW_RISK_CONFLICTING"),
        ("Review-Risk:\n", "REVIEW_RISK_MISSING"),
    ],
)
def test_an_unusable_body_classification_fails_closed(body: str, code: str) -> None:
    module = _module()

    with pytest.raises(module.LandingPolicyError) as excinfo:
        module.review_risk_from_body(body)

    assert excinfo.value.code == code


def test_a_fenced_example_is_not_a_classification() -> None:
    module = _module()

    body = (
        "## Intent\n\n"
        "Review-Risk: none\n\n"
        "```text\n"
        "Review-Risk: payment\n"
        "```\n"
    )

    assert module.review_risk_from_body(body) == "none"


def test_cli_resolves_and_emits_the_command_plan(tmp_path: Path) -> None:
    body = tmp_path / "body.md"
    body.write_text("## Intent\n\nReview-Risk: none\n", encoding="utf-8")

    result = _run(
        "resolve",
        "--delivery-mode",
        "solo",
        "--bead-type",
        "bug",
        "--bead-body-file",
        str(body),
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["contract"] == "cognovis.landing-policy.v1"
    assert payload["policy"] == "direct"
    assert payload["commands"]["publish"][-2:] == ["--delivery", "merge"]


def test_cli_reads_the_classification_from_a_bead_body_file(tmp_path: Path) -> None:
    body = tmp_path / "body.md"
    body.write_text("## Intent\n\nReview-Risk: compliance\n", encoding="utf-8")

    result = _run(
        "resolve",
        "--delivery-mode",
        "solo",
        "--bead-type",
        "bug",
        "--bead-body-file",
        str(body),
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["inputs"]["review_risk"] == "compliance"
    assert payload["policy"] == "pr-review"


def test_cli_refuses_an_unclassified_bead_with_an_actionable_typed_result(
    tmp_path: Path,
) -> None:
    body = tmp_path / "body.md"
    body.write_text("## Intent\n\nGoal: Ship the thing.\n", encoding="utf-8")

    result = _run(
        "resolve",
        "--delivery-mode",
        "solo",
        "--bead-type",
        "feature",
        "--bead-body-file",
        str(body),
    )

    assert result.returncode == 2
    payload = json.loads(result.stdout)
    assert payload["status"] == "error"
    assert payload["code"] == "REVIEW_RISK_MISSING"
    assert "Review-Risk" in payload["remedy"]
    assert "Traceback" not in result.stderr


def test_cli_reports_the_review_risk_of_a_body_on_its_own() -> None:
    result = _run("review-risk", "--body", "Review-Risk: auth")

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["review_risk"] == "auth"

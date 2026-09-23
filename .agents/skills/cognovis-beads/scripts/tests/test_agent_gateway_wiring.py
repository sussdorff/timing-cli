"""Dispatch wiring: all cross-model work goes through `ccore agent` (ADR-0009/0010).

The retired `agent_session_*` gateway, the `agents/codex.md` relay, and the
slot/route resolution layer are gone. The installed `ccore` transport is the only
dispatch surface; compatibility redirects carry no dispatch policy of their own,
and the acpx-dispatch skill carries policy only.
"""

from __future__ import annotations

from pathlib import Path


_REPO_ROOT = Path(__file__).resolve().parents[4]
_SCRIPTS = _REPO_ROOT / "skills" / "cognovis-beads" / "scripts"


# clc-i19u: the transport skill is served from `cognovis/ccore` beside the command
# it documents, so this repository holds no copy to read. What stays checkable here
# is the caller side: the sources that dispatch must route through the installed
# command and must not grow their own routing or review-family policy.
_DISPATCH_SKILL = _REPO_ROOT / "skills" / "acpx-dispatch"


def test_this_repository_holds_no_second_copy_of_the_transport_skill() -> None:
    assert not _DISPATCH_SKILL.exists()


def test_review_family_rule_lives_in_the_standard_not_the_caller() -> None:
    """The opposite-family rule is caller policy; the dispatching sources stay ignorant.

    It used to be a table plus an ``enforce_opposite_family`` call in the
    deterministic loop state machine. That machine was retired with the
    single-bead loop's scripts (clc-rm0o), so the remaining guarantee is
    one-sided: no dispatching source decides reviewer family, and the injected
    routing standard does.
    """
    routing = (
        _REPO_ROOT / "standards" / "dispatch" / "model-routing.md"
    ).read_text(encoding="utf-8")

    for source in (
        "skills/executive-pack/SKILL.md",
        "skills/implementation-loop/SKILL.md",
        "skills/cognovis-beads/SKILL.md",
    ):
        content = (_REPO_ROOT / source).read_text(encoding="utf-8")
        for relocated in (
            "enforce_review_family",
            "AGENT_FAMILY",
            "LEAD_FAMILY_ALIASES",
            "REVIEW_AGENT_FAMILIES",
            "review_gate_validate",
        ):
            assert relocated not in content, f"{source} still carries {relocated}"

    assert "family" in routing.lower()


def test_retired_routing_layer_is_absent() -> None:
    for relative in (
        "skills/cognovis-beads/scripts/resolve_slot_dispatch.py",
        "skills/cognovis-beads/scripts/resolve_quick_fix_models.py",
        "skills/cognovis-beads/lib/orchestrator/route_profiles.py",
        "skills/cognovis-beads/lib/orchestrator/routing.py",
        "skills/adversarial-review/scripts/resolve_dispatch.py",
        "skills/adversarial-review/scripts/run_codex_review.py",
        "scripts/resolve_tier_models.py",
    ):
        assert not (_REPO_ROOT / relative).exists(), relative


def test_routing_preference_is_a_standard() -> None:
    standard = _REPO_ROOT / "standards" / "dispatch" / "model-routing.md"
    assert standard.exists()
    content = standard.read_text(encoding="utf-8")
    assert "STATUS: BEHAVIORAL POLICY" in content
    assert "Transport proves session execution, not semantic role compliance" in content
    assert "no JSON role payload, route resolver, profile registry" in content


def test_retired_provider_wrappers_are_absent() -> None:
    for name in (
        "codex-impl.py",
        "claude-impl.py",
        "cursor-impl.py",
        "codex-exec.py",
        "claude-exec.py",
    ):
        assert not (_SCRIPTS / name).exists()


def test_cohesive_compatibility_orchestrator_has_no_dispatch_policy() -> None:
    content = (_REPO_ROOT / "skills" / "cohesive-bead-chain" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    assert "Load `executive-pack` in this current session" in content
    assert "acpx" not in content
    assert "agent_session_start" not in content
    assert "agent_session_continue" not in content


def test_no_agent_carries_the_retired_gateway_dispatch_policy() -> None:
    """clc-d8ol retired the compat redirects; nothing may reintroduce the gateway."""
    for source in sorted((_REPO_ROOT / "agents").glob("*.md")):
        content = source.read_text(encoding="utf-8")
        assert "agent_session_start" not in content, source
        assert "agent_session_continue" not in content, source


def test_codex_relay_agent_is_retired() -> None:
    # agents/codex.md (the agent_session_* / codex-exec relay) is gone; acpx is
    # the dispatcher. The review result contract now travels with the runner as
    # an opt-in output contract, not with a provider-named relay.
    assert not (_REPO_ROOT / "agents" / "codex.md").exists()
    # ADR-0009 moved the gated-review contract off the transport and onto the
    # caller. clc-rm0o then retired the caller-side `review_gate_v1` machinery
    # with the rest of the single-bead loop's scripts: the per-bead reviewer now
    # returns a human-readable verdict. Neither side may grow it back.
    assert not (_DISPATCH_SKILL / "scripts" / "review_contract.py").exists()
    loop_scripts = _REPO_ROOT / "skills" / "implementation-loop" / "scripts"
    assert not (loop_scripts / "review_contract.py").exists()
    assert not (loop_scripts / "loop_state.py").exists()
    assert "review_gate_v1" not in (
        _REPO_ROOT / "skills" / "implementation-loop" / "SKILL.md"
    ).read_text(encoding="utf-8")

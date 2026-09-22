#!/usr/bin/env python3
"""Tests for live private-network requirement detection."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path


_SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
_CHECK_SCRIPT = _SCRIPTS_DIR / "check_live_network_requirement.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("check_live_network_requirement", _CHECK_SCRIPT)
    assert spec is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


def test_explicit_live_network_label_requests_network_access_not_danger_full_access() -> None:
    """bead clc-27sn: live-network beads get an explicit network-access capability
    layered on the always-confined workspace-write sandbox, never danger-full-access
    (which the implementer role resolver now categorically rejects)."""
    mod = _load_module()
    result = mod.detect_live_network_requirement({
        "labels": ["needs:live-network"],
        "description": "Run integration tests against a private endpoint.",
    })

    assert result["live_network_required"] is True
    assert result["recommended_codex_sandbox_mode"] == "workspace-write"
    assert result["recommended_network_access"] is True
    assert "label:needs:live-network" in result["matched_signals"]


def test_provider_specific_vpn_label_requests_network_access_not_danger_full_access() -> None:
    mod = _load_module()
    result = mod.detect_live_network_requirement({
        "labels": ["vpn:provider-a"],
        "description": "Run integration tests against private source data.",
    })

    assert result["live_network_required"] is True
    assert result["recommended_codex_sandbox_mode"] == "workspace-write"
    assert result["recommended_network_access"] is True
    assert "label:vpn:provider-a" in result["matched_signals"]


def test_private_ip_requests_network_access_not_danger_full_access() -> None:
    mod = _load_module()
    result = mod.detect_live_network_requirement([{
        "description": "Run the MSSQL probe against 192.168.10.10:1433.",  # customer-guard: allow-address
        "labels": [],
    }])

    assert result["live_network_required"] is True
    assert result["recommended_codex_sandbox_mode"] == "workspace-write"
    assert result["recommended_network_access"] is True
    assert "private-ip:192.168.10.10" in result["matched_signals"]  # customer-guard: allow-address
    assert result["tcp_endpoints"] == ["192.168.10.10:1433"]  # customer-guard: allow-address


def test_clean_bead_keeps_workspace_write() -> None:
    mod = _load_module()
    result = mod.detect_live_network_requirement({
        "description": "Add unit tests for local parser behavior.",
        "labels": ["surface:api"],
    })

    assert result == {
        "live_network_required": False,
        "matched_signals": [],
        "tcp_endpoints": [],
        "recommended_codex_sandbox_mode": "workspace-write",
        "recommended_network_access": False,
    }


def test_cli_rejects_invalid_json() -> None:
    result = subprocess.run(
        [sys.executable, str(_CHECK_SCRIPT)],
        input="{invalid",
        capture_output=True,
        text=True,
    )

    assert result.returncode == 2
    assert "LIVE_NETWORK_CHECK_ERROR" in result.stderr


def test_cli_outputs_json() -> None:
    payload = [{"labels": ["network:vpn"], "description": "Live data check"}]
    result = subprocess.run(
        [sys.executable, str(_CHECK_SCRIPT)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        check=True,
    )

    parsed = json.loads(result.stdout)
    assert parsed["live_network_required"] is True
    assert parsed["recommended_codex_sandbox_mode"] == "workspace-write"
    assert parsed["recommended_network_access"] is True

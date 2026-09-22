#!/usr/bin/env python3
"""Detect whether a bead requires live private-network access.

The detector is intentionally conservative. It does not know provider names or
VPN profiles; it only recognizes explicit live-network labels, private network
endpoints, and common English phrases for live/private/original-data evidence.
"""

from __future__ import annotations

import json
import re
import sys
from typing import Any


DEFAULT_SANDBOX_MODE = "workspace-write"
# NOTE (bead clc-27sn): the implementer role resolver now categorically rejects
# danger-full-access (dangerous_sandbox_denied) -- it disabled Codex's filesystem
# sandbox entirely, defeating the "write only inside the assigned bead worktree"
# guarantee. Live-network beads no longer get a different SANDBOX MODE; they get an
# explicit, narrower NETWORK ACCESS capability layered on top of the always-confined
# workspace-write mode (Codex's own `sandbox_workspace_write.network_access` config
# key), so the worktree confinement holds regardless of network requirements.

EXPLICIT_LABELS = frozenset({
    "needs:live-network",
    "requires:live-network",
    "network:live",
    "network:private-data",
    "network:vpn",
})
EXPLICIT_LABEL_PREFIXES = ("vpn:",)

TEXT_PATTERNS = (
    re.compile(r"\blive[- ]network\b", re.IGNORECASE),
    re.compile(r"\blive[- ]data\b", re.IGNORECASE),
    re.compile(r"\boriginal[- ]data\b", re.IGNORECASE),
    re.compile(r"\bprivate[- ]data\b", re.IGNORECASE),
    re.compile(r"\bvpn\b", re.IGNORECASE),
    re.compile(r"\bmssql\b", re.IGNORECASE),
    re.compile(r"\bsql[- ]server\b", re.IGNORECASE),
)

PRIVATE_IPV4_PATTERN = re.compile(
    r"\b("
    r"10(?:\.\d{1,3}){3}|"
    r"192\.168(?:\.\d{1,3}){2}|"
    r"172\.(?:1[6-9]|2\d|3[0-1])(?:\.\d{1,3}){2}"
    r")\b"
)
PRIVATE_TCP_ENDPOINT_PATTERN = re.compile(
    r"\b("
    r"(?:10(?:\.\d{1,3}){3}|"
    r"192\.168(?:\.\d{1,3}){2}|"
    r"172\.(?:1[6-9]|2\d|3[0-1])(?:\.\d{1,3}){2})"
    r"):(\d{1,5})\b"
)


def extract_bead(payload: Any) -> dict[str, Any]:
    """Return the first work-order dict from tracker or Beads JSON."""
    if isinstance(payload, list):
        return payload[0] if payload and isinstance(payload[0], dict) else {}
    if isinstance(payload, dict):
        return payload
    return {}


def _stringify(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (list, tuple, set)):
        return "\n".join(_stringify(item) for item in value)
    if isinstance(value, dict):
        return "\n".join(f"{key}: {_stringify(val)}" for key, val in value.items())
    return str(value)


def detect_live_network_requirement(payload: Any) -> dict[str, Any]:
    """Return a stable detection result for a work-order JSON payload."""
    bead = extract_bead(payload)
    labels = [
        label
        for label in (bead.get("labels") or [])
        if isinstance(label, str)
    ]
    label_matches = sorted(
        label
        for label in set(labels)
        if label in EXPLICIT_LABELS
        or any(label.startswith(prefix) for prefix in EXPLICIT_LABEL_PREFIXES)
    )

    text_fields = [
        bead.get("title"),
        bead.get("description"),
        bead.get("acceptance_criteria"),
        bead.get("notes"),
        bead.get("design"),
    ]
    text = "\n".join(_stringify(field) for field in text_fields)

    text_matches = [
        pattern.pattern
        for pattern in TEXT_PATTERNS
        if pattern.search(text)
    ]
    private_ips = sorted(set(PRIVATE_IPV4_PATTERN.findall(text)))
    tcp_endpoints = sorted(
        set(
            f"{host}:{port}"
            for host, port in PRIVATE_TCP_ENDPOINT_PATTERN.findall(text)
            if 0 < int(port) <= 65535
        )
    )

    matched_signals = []
    matched_signals.extend(f"label:{label}" for label in label_matches)
    matched_signals.extend(f"text:{pattern}" for pattern in text_matches)
    matched_signals.extend(f"private-ip:{ip}" for ip in private_ips)

    live_network_required = bool(matched_signals)
    return {
        "live_network_required": live_network_required,
        "matched_signals": matched_signals,
        "tcp_endpoints": tcp_endpoints,
        # Always workspace-write: worktree filesystem confinement is unconditional and
        # does not vary with network requirements. See the module-level NOTE above.
        "recommended_codex_sandbox_mode": DEFAULT_SANDBOX_MODE,
        # Separate, narrower capability: whether the implementer needs live network
        # access layered on top of the (always-confined) workspace-write sandbox.
        "recommended_network_access": live_network_required,
    }


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError as exc:
        print(f"LIVE_NETWORK_CHECK_ERROR: invalid JSON on stdin: {exc}", file=sys.stderr)
        return 2

    print(json.dumps(detect_live_network_requirement(payload), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

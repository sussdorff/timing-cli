#!/usr/bin/env -S uv run --quiet --script
# /// script
# dependencies = [
#   "pyyaml>=6.0",
# ]
# ///
"""
Review Quality Signals Runner.

Orchestrates all registered quality signal providers and returns their
envelopes as defined in standards/orchestrator/review-quality-signals.md.

Beads:
  clc-der    initial executable runner (file mode, schema-v3 parser, fallow adapter)
  followup   diff_range threading, registry, self-validation, item-schema validation,
             orchestrator-config overlay, run_id metrics integration,
             distinguishable contract-drift NOT_IMPLEMENTED state

Usage:
    uv run $BEAD_REVIEWER_RUNTIME/scripts/review_quality_signals_runner.py \\
        --repo-root <path> \\
        [--diff-range <range>] \\
        [--enabled fallow,contract-drift] \\
        [--run-id <uuid>]

Outputs a JSON array of provider envelopes to stdout.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


# ---------------------------------------------------------------------------
# Provider Envelope
# ---------------------------------------------------------------------------


@dataclass
class ProviderEnvelope:
    """Output envelope for a single quality signal provider.

    Matches the schema in standards/orchestrator/review-quality-signals.md.
    """

    provider: str
    status: str  # "ok" | "skipped"
    skipped_reason: str | None
    blocking_findings: list[dict[str, Any]]
    advisory_signals: list[dict[str, Any]]


VALID_STATUSES = {"ok", "skipped"}

# Marker prefix used in skipped_reason to distinguish "tool integration not
# implemented yet" from "tool absent / config missing". Consumers can grep
# for this prefix to surface a warning that a declared provider is a stub.
NOT_IMPLEMENTED_MARKER = "[provider-not-implemented]"


# ---------------------------------------------------------------------------
# Envelope Validator
# ---------------------------------------------------------------------------


_REQUIRED_FINDING_KEYS = {"finding_id", "description"}
_REQUIRED_SIGNAL_KEYS = {"signal_id", "description"}


def _validate_finding_item(item: Any, kind: str, required: set[str]) -> None:
    if not isinstance(item, dict):
        raise ValueError(
            f"{kind} item must be a dict, got {type(item).__name__}: {item!r}"
        )
    missing = required - item.keys()
    if missing:
        raise ValueError(
            f"{kind} item missing required keys {sorted(missing)!r}: {item!r}"
        )


def validate_envelope(data: dict[str, Any]) -> ProviderEnvelope:
    """Validate a raw dict against the provider envelope schema.

    Raises ValueError on:
    - Missing required envelope fields (provider, status, skipped_reason,
      blocking_findings, advisory_signals). All five keys MUST be present;
      ``skipped_reason`` may be ``None`` for status="ok".
    - Invalid status value (must be "ok" or "skipped").
    - Skipped invariant violation: when status="skipped", skipped_reason must
      be non-empty and both finding lists must be empty.
    - Item schema violation: each entry in blocking_findings must have
      finding_id+description; each entry in advisory_signals must have
      signal_id+description.
    """
    required_fields = (
        "provider",
        "status",
        "skipped_reason",
        "blocking_findings",
        "advisory_signals",
    )
    missing = [f for f in required_fields if f not in data]
    if missing:
        raise ValueError(f"Provider envelope missing required fields: {missing!r}")

    status = data["status"]
    if status not in VALID_STATUSES:
        raise ValueError(
            f"Invalid provider envelope status {status!r}. Must be one of: {VALID_STATUSES}"
        )

    blocking = data["blocking_findings"]
    advisory = data["advisory_signals"]
    if not isinstance(blocking, list):
        raise ValueError(
            f"blocking_findings must be a list, got {type(blocking).__name__}"
        )
    if not isinstance(advisory, list):
        raise ValueError(
            f"advisory_signals must be a list, got {type(advisory).__name__}"
        )

    if status == "skipped":
        if not data.get("skipped_reason"):
            raise ValueError(
                "status='skipped' requires a non-empty skipped_reason"
            )
        if blocking:
            raise ValueError(
                "Skipped invariant violated: status='skipped' but blocking_findings is non-empty. "
                "A skipped provider cannot produce findings."
            )
        if advisory:
            raise ValueError(
                "Skipped invariant violated: status='skipped' but advisory_signals is non-empty. "
                "A skipped provider cannot produce findings."
            )
    else:
        # status == "ok": validate every finding/signal item shape
        for item in blocking:
            _validate_finding_item(item, "blocking_findings", _REQUIRED_FINDING_KEYS)
        for item in advisory:
            _validate_finding_item(item, "advisory_signals", _REQUIRED_SIGNAL_KEYS)

    return ProviderEnvelope(
        provider=data["provider"],
        status=data["status"],
        skipped_reason=data.get("skipped_reason"),
        blocking_findings=blocking,
        advisory_signals=advisory,
    )


# ---------------------------------------------------------------------------
# Fallow Adapter (schema-v3)
# ---------------------------------------------------------------------------


def _fallow_skipped(reason: str) -> ProviderEnvelope:
    return ProviderEnvelope(
        provider="fallow",
        status="skipped",
        skipped_reason=reason,
        blocking_findings=[],
        advisory_signals=[],
    )


def _parse_fallow_schema_v3(raw_output: str) -> tuple[list[dict], list[dict]]:
    """Parse fallow schema-v3 JSON output into (blocking_findings, advisory_signals).

    Schema-v3 format:
    {
        "version": 3,
        "findings": [
            {
                "type": "dead-code | duplication | complexity",
                "severity": "advisory | blocking",
                "message": "...",
                "file": "...",
                "line": 42
            }
        ]
    }
    """
    data = json.loads(raw_output)

    # Validate top-level shape before iterating — degrade gracefully on
    # malformed structure (e.g. findings as a string, or non-dict root).
    if not isinstance(data, dict):
        raise ValueError(
            f"fallow output top-level must be an object, got {type(data).__name__}"
        )

    findings = data.get("findings", [])
    if not isinstance(findings, list):
        raise ValueError(
            f"fallow 'findings' must be a list, got {type(findings).__name__}"
        )

    blocking_findings: list[dict] = []
    advisory_signals: list[dict] = []

    for f in findings:
        if not isinstance(f, dict):
            continue
        severity = f.get("severity", "advisory")
        finding_type = f.get("type", "unknown")
        message = f.get("message", "")
        file_path = f.get("file")
        line = f.get("line")

        if severity == "blocking":
            blocking_findings.append(
                {
                    "finding_id": f"fallow/{finding_type}",
                    "description": message,
                    "file": file_path,
                    "line": line,
                    "severity": "blocking",
                }
            )
        else:
            advisory_signals.append(
                {
                    "signal_id": f"fallow/{finding_type}",
                    "description": message,
                    "file": file_path,
                    "line": line,
                }
            )

    return blocking_findings, advisory_signals


def run_fallow_provider(
    repo_root: str | Path,
    timeout: int = 30,
    diff_range: str | None = None,
    _bin_dir_for_tests: str | Path | None = None,
) -> ProviderEnvelope:
    """Run the fallow quality signal provider.

    Steps:
    1. Config probe: check for .fallowrc.json in repo_root.
       If absent → return skipped envelope.
    2. Run fallow binary. CLI:
         fallow --json [--diff-range <range>] <repo_root>
       If not on PATH → skipped. Non-zero exit → skipped with code in reason.
       Timeout → skipped.
    3. Parse schema-v3 JSON output into blocking_findings/advisory_signals.

    Args:
        repo_root: Repository root directory to audit.
        timeout: Subprocess timeout in seconds.
        diff_range: Optional git diff range (e.g. "abc123...HEAD"). Threaded
                    into the fallow CLI as ``--diff-range`` so the audit is
                    diff-scoped (per standards/orchestrator/review-quality-signals.md).
        _bin_dir_for_tests: Test seam — prepends a directory to PATH so tests
                            can inject mock binaries. Production callers MUST
                            leave this as None; the leading underscore marks
                            it as not part of the stable API.
    """
    repo_root = Path(repo_root)
    config_file = repo_root / ".fallowrc.json"

    if not config_file.exists():
        return _fallow_skipped(
            ".fallowrc.json not found — fallow audit skipped"
        )

    # Build environment for subprocess (inject test bin dir into PATH if given)
    env = os.environ.copy()
    if _bin_dir_for_tests is not None:
        env["PATH"] = str(_bin_dir_for_tests) + os.pathsep + env.get("PATH", "")

    cmd: list[str] = ["fallow", "--json"]
    if diff_range:
        cmd.extend(["--diff-range", diff_range])
    cmd.append(str(repo_root))

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(repo_root),
            env=env,
        )
    except subprocess.TimeoutExpired:
        return _fallow_skipped(f"fallow timed out after {timeout}s")
    except FileNotFoundError:
        return _fallow_skipped("tool 'fallow' not found on PATH")

    if result.returncode != 0:
        stderr_excerpt = result.stderr.strip()[:200] if result.stderr else ""
        reason = f"fallow exited with code {result.returncode}"
        if stderr_excerpt:
            reason += f": {stderr_excerpt}"
        return _fallow_skipped(reason)

    try:
        blocking_findings, advisory_signals = _parse_fallow_schema_v3(result.stdout)
    except (ValueError, KeyError, TypeError) as exc:
        # ValueError covers JSONDecodeError (subclass) and our top-level shape
        # validation; KeyError/TypeError defend against unexpected access paths.
        return _fallow_skipped(f"fallow output parse error: {exc}")

    return ProviderEnvelope(
        provider="fallow",
        status="ok",
        skipped_reason=None,
        blocking_findings=blocking_findings,
        advisory_signals=advisory_signals,
    )


# ---------------------------------------------------------------------------
# Contract-Drift Adapter
# ---------------------------------------------------------------------------


def run_contract_drift_provider(
    repo_root: str | Path,
    timeout: int = 30,
    diff_range: str | None = None,
) -> ProviderEnvelope:
    """Run the contract-drift quality signal provider.

    Config probe: check for .contract-drift.yml in repo_root.
    - Config absent → skipped, reason cites the missing file.
    - Config present → skipped with NOT_IMPLEMENTED_MARKER in the reason so
      callers can distinguish "tool integration not implemented" from
      "tool absent". The marker keeps the stub state observable in any
      review report — consumers can grep for it and surface a warning.
    """
    _ = (timeout, diff_range)  # accepted for signature symmetry; not yet consumed
    repo_root = Path(repo_root)
    config_file = repo_root / ".contract-drift.yml"

    if not config_file.exists():
        return ProviderEnvelope(
            provider="contract-drift",
            status="skipped",
            skipped_reason=".contract-drift.yml not found — contract-drift audit skipped",
            blocking_findings=[],
            advisory_signals=[],
        )

    return ProviderEnvelope(
        provider="contract-drift",
        status="skipped",
        skipped_reason=(
            f"{NOT_IMPLEMENTED_MARKER} .contract-drift.yml present but tool "
            "integration is not yet implemented in this runner version. "
            "File a follow-up bead to wire up contract-drift tooling."
        ),
        blocking_findings=[],
        advisory_signals=[],
    )


# ---------------------------------------------------------------------------
# Provider Registry
# ---------------------------------------------------------------------------


# Provider callable signature: (repo_root, timeout, diff_range) -> ProviderEnvelope
ProviderCallable = Callable[..., ProviderEnvelope]

REGISTERED_PROVIDERS: dict[str, ProviderCallable] = {
    "fallow": run_fallow_provider,
    "contract-drift": run_contract_drift_provider,
}


# ---------------------------------------------------------------------------
# Orchestrator-config overlay
# ---------------------------------------------------------------------------


def _load_disabled_providers(repo_root: Path) -> set[str]:
    """Read .agents/orchestrator-config.yml and return the disabled provider set.

    Looks under top-level ``quality_signals.disabled`` (a list of provider IDs).
    Returns an empty set when the file or section is absent or unparsable —
    config issues degrade silently and never enable a provider that was
    explicitly disabled.
    """
    config_path = repo_root / ".agents" / "orchestrator-config.yml"
    if not config_path.exists():
        return set()

    try:
        import yaml  # type: ignore[import-not-found]
    except ImportError:
        return set()

    try:
        with config_path.open() as f:
            data = yaml.safe_load(f) or {}
    except (OSError, yaml.YAMLError):
        return set()

    if not isinstance(data, dict):
        return set()
    qs = data.get("quality_signals")
    if not isinstance(qs, dict):
        return set()
    disabled = qs.get("disabled", [])
    if not isinstance(disabled, list):
        return set()
    return {str(p) for p in disabled if isinstance(p, str)}


# ---------------------------------------------------------------------------
# Orchestrator: run all registered providers
# ---------------------------------------------------------------------------


def _envelope_to_dict(env: ProviderEnvelope) -> dict:
    return {
        "provider": env.provider,
        "status": env.status,
        "skipped_reason": env.skipped_reason,
        "blocking_findings": env.blocking_findings,
        "advisory_signals": env.advisory_signals,
    }


def run_providers(
    repo_root: str | Path,
    diff_range: str | None = None,
    timeout: int = 30,
    enabled: list[str] | None = None,
) -> list[ProviderEnvelope]:
    """Run registered quality signal providers and return their envelopes.

    Args:
        repo_root: Repository root directory.
        diff_range: Optional git diff range (e.g. "abc123...HEAD"). Threaded
                    through to providers that support diff-scoped analysis.
        timeout: Per-provider subprocess timeout in seconds.
        enabled: Optional explicit allowlist of provider IDs. If None, all
                 REGISTERED_PROVIDERS are eligible. The orchestrator-config
                 ``quality_signals.disabled`` overlay is applied on top.

    Returns:
        List of ProviderEnvelope, one per provider that was actually run.
        Each envelope is fail-fast validated against the schema before return,
        so consumer code can trust the envelopes are well-formed.
    """
    repo_root = Path(repo_root)
    disabled = _load_disabled_providers(repo_root)

    if enabled is None:
        ids = list(REGISTERED_PROVIDERS.keys())
    else:
        ids = [p for p in enabled if p in REGISTERED_PROVIDERS]

    envelopes: list[ProviderEnvelope] = []
    for provider_id in ids:
        if provider_id in disabled:
            envelopes.append(
                ProviderEnvelope(
                    provider=provider_id,
                    status="skipped",
                    skipped_reason=(
                        f"provider '{provider_id}' disabled via "
                        ".agents/orchestrator-config.yml quality_signals.disabled"
                    ),
                    blocking_findings=[],
                    advisory_signals=[],
                )
            )
            continue
        fn = REGISTERED_PROVIDERS[provider_id]
        envelopes.append(
            fn(repo_root=repo_root, timeout=timeout, diff_range=diff_range)
        )

    # Self-validation: every envelope this runner emits must round-trip cleanly
    # through validate_envelope. A future provider author who returns a malformed
    # envelope will be caught here, at the runner boundary, instead of at the
    # consumer (review-agent) downstream.
    return [validate_envelope(_envelope_to_dict(e)) for e in envelopes]


# ---------------------------------------------------------------------------
# Metrics integration (best-effort, opt-in via --run-id)
# ---------------------------------------------------------------------------


def _metrics_runtime_candidates(repo_root: Path) -> list[Path]:
    """Return only project-local metrics runtimes in the documented precedence order."""
    return [
        repo_root / ".agents/skills/bead-metrics/scripts",
        repo_root / ".claude/skills/bead-metrics/scripts",
        repo_root / "skills/bead-metrics/scripts",
        Path(__file__).resolve().parents[2] / "bead-metrics" / "scripts",
    ]


def _log_metrics(run_id: str | None, exit_code: int, repo_root: Path | None = None) -> None:
    """Best-effort log of this runner invocation to the beads metrics DB.

    Silently no-ops when:
    - run_id is None (caller did not opt in)
    - the metrics module cannot be imported (e.g. bead-metrics is not installed)
    - the DB write fails for any reason
    """
    if not run_id:
        return
    try:
        for candidate in _metrics_runtime_candidates(repo_root or Path.cwd()):
            if (candidate / "metrics.py").exists():
                sys.path.insert(0, str(candidate))
                break
        from metrics import insert_agent_call  # type: ignore[import-not-found]

        insert_agent_call(
            run_id=run_id,
            bead_id=os.environ.get("BEAD_ID", ""),
            phase_label="phase-e-quality-signals",
            agent_label="review-quality-signals-runner",
            model="n/a",
            iteration=1,
            input_tokens=0,
            cached_input_tokens=0,
            output_tokens=0,
            reasoning_output_tokens=0,
            total_tokens=0,
            duration_ms=0,
            exit_code=exit_code,
        )
    except Exception:
        # Metrics is best-effort; never fail the runner because of telemetry.
        pass


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="Run all registered review quality signal providers."
    )
    parser.add_argument(
        "--repo-root",
        default=".",
        help="Repository root directory (default: current directory)",
    )
    parser.add_argument(
        "--diff-range",
        default=None,
        help="Git diff range for diff-scoped analysis (e.g. abc123...HEAD)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=30,
        help="Per-provider timeout in seconds (default: 30)",
    )
    parser.add_argument(
        "--enabled",
        default=None,
        help=(
            "Comma-separated allowlist of provider IDs to run "
            "(default: all REGISTERED_PROVIDERS). "
            "Disabled providers from orchestrator-config.yml are still excluded."
        ),
    )
    parser.add_argument(
        "--run-id",
        default=os.environ.get("CCP_ORCHESTRATOR_RUN_ID"),
        help=(
            "Beads metrics run_id. If provided (or CCP_ORCHESTRATOR_RUN_ID env var "
            "is set), this invocation is logged via insert_agent_call() under "
            "phase_label='phase-e-quality-signals'. Best-effort: no-op on import failure."
        ),
    )
    args = parser.parse_args()

    enabled = None
    if args.enabled:
        enabled = [p.strip() for p in args.enabled.split(",") if p.strip()]

    repo_root = Path(args.repo_root).resolve()
    exit_code = 0
    try:
        envelopes = run_providers(
            repo_root=repo_root,
            diff_range=args.diff_range,
            timeout=args.timeout,
            enabled=enabled,
        )
        output = [_envelope_to_dict(e) for e in envelopes]
        print(json.dumps(output, indent=2))
    except Exception as exc:
        exit_code = 1
        print(f"error: {exc}", file=sys.stderr)

    _log_metrics(args.run_id, exit_code, repo_root)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())

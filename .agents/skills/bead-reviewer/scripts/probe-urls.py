#!/usr/bin/env python3
"""
probe-urls.py — Extract URLs from a git diff and probe each one with curl.

Used by the review-agent's `B4. External Resource Verification` check to detect
fabricated external resources (URLs, S3 paths, CDN refs, etc.) introduced by an
implementer subagent. Plausible structure is not evidence of existence — only an
HTTP probe can tell a real URL from a hallucinated one.

Output conforms to core/contracts/execution-result.schema.json:
  status: "ok" (all URLs resolve or none found)
        | "warning" (some URLs sampled but not all probed; or transient failures)
        | "error" (one or more URLs returned 4xx/5xx, DNS failure, or TLS failure)
  data.findings: list of {url, http_code, file_hint, classification}
  data.skipped: list of {url, reason}  # license/comment/localhost/example/etc.

Usage:
  uv run python probe-urls.py --diff-range <pre-sha>...HEAD [--max-probe 30] [--timeout 10]

Exit codes:
  0 — clean (all URLs resolved, or none introduced)
  1 — at least one finding (suspected fabricated URL)
  2 — script error (no diff, git failure)
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import subprocess
import sys
from typing import Any

_SCHEMA_PATH = "core/contracts/execution-result.schema.json"
_PRODUCER = "probe-urls.py"
_CONTRACT_VERSION = "1"

# URL pattern: matches http(s)://... up to a quote, whitespace, or common terminator
_URL_RE = re.compile(r"https?://[^\s\"'`<>)\\]+")

# Trailing junk we should strip from extracted URLs (markdown / punctuation)
_TRAILING_JUNK = ".,;:!?)]}>'\""

# Hosts / patterns we always skip (false-positive sources)
_SKIP_HOST_SUFFIXES = (
    "apache.org",
    "gnu.org",
    "mozilla.org",
    "opensource.org",
    "creativecommons.org",
    "spdx.org",
    "example.com",
    "example.org",
    "example.net",
    "localhost",
    "127.0.0.1",
    "0.0.0.0",
)

# Schemes / hostnames where probing makes no sense
_SKIP_SCHEMES = ("http://localhost", "https://localhost", "http://127.", "http://0.0.0.0")


def _now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _envelope(
    status: str,
    summary: str,
    data: dict[str, Any],
    errors: list[dict[str, Any]] | None = None,
    next_steps: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "status": status,
        "summary": summary,
        "data": data,
        "errors": errors or [],
        "next_steps": next_steps or [],
        "open_items": [],
        "meta": {
            "contract_version": _CONTRACT_VERSION,
            "producer": _PRODUCER,
            "generated_at": _now_iso(),
            "schema": _SCHEMA_PATH,
        },
    }


def _strip_trailing_junk(url: str) -> str:
    while url and url[-1] in _TRAILING_JUNK:
        url = url[:-1]
    return url


def _should_skip(url: str) -> str | None:
    """Return a skip-reason string if the URL is a known false-positive, else None."""
    lowered = url.lower()
    for prefix in _SKIP_SCHEMES:
        if lowered.startswith(prefix):
            return "localhost / test infrastructure"
    # Strip scheme then check host suffix
    host = lowered.split("://", 1)[-1].split("/", 1)[0].split(":", 1)[0]
    for suffix in _SKIP_HOST_SUFFIXES:
        if host == suffix or host.endswith("." + suffix):
            return f"placeholder/license host ({suffix})"
    return None


def _extract_added_urls(diff_range: str) -> list[tuple[str, str]]:
    """
    Parse `git diff <range>` and return a list of (url, file_hint) pairs from
    *added* lines only (those starting with '+', excluding the '+++' header).

    file_hint is the most recent `+++ b/<path>` seen before the line.
    """
    try:
        out = subprocess.check_output(
            ["git", "diff", diff_range],
            stderr=subprocess.STDOUT,
            text=True,
            timeout=60,
        )
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(f"git diff failed: {exc.output}") from exc
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("git diff timed out") from exc

    current_file = "<unknown>"
    found: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()

    for line in out.splitlines():
        if line.startswith("+++ b/"):
            current_file = line[len("+++ b/"):]
            continue
        if line.startswith("+++") or line.startswith("---"):
            continue
        if not line.startswith("+"):
            continue
        # Added line — extract URLs
        for match in _URL_RE.findall(line[1:]):
            url = _strip_trailing_junk(match)
            if not url:
                continue
            key = (url, current_file)
            if key in seen:
                continue
            seen.add(key)
            found.append(key)

    return found


def _probe(url: str, timeout: int) -> str:
    """
    Probe a URL with HEAD; on 405/000 retry with a single-byte ranged GET.
    Returns the HTTP code as a string ("200", "404", ...) or "000" if curl
    could not get a response at all (DNS failure, TLS failure, refused).
    """
    base = ["curl", "-sI", "-o", "/dev/null", "-w", "%{http_code}", "--max-time", str(timeout)]
    try:
        code = subprocess.check_output(
            base + [url],
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=timeout + 5,
        ).strip()
    except subprocess.CalledProcessError as exc:
        # Non-zero exit = DNS / TLS / connection problem; output may still hold "000"
        code = (exc.output or "000").strip()
    except subprocess.TimeoutExpired:
        return "000"

    if code in ("405", "000"):
        # Server rejects HEAD or returned nothing — try ranged GET (1 byte)
        get = ["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}", "--max-time", str(timeout), "-r", "0-0"]
        try:
            code = subprocess.check_output(
                get + [url],
                stderr=subprocess.DEVNULL,
                text=True,
                timeout=timeout + 5,
            ).strip()
        except subprocess.CalledProcessError as exc:
            code = (exc.output or "000").strip()
        except subprocess.TimeoutExpired:
            return "000"

    return code or "000"


def _classify(code: str) -> str:
    """Classify an HTTP code into ok / transient / fail / unreachable."""
    if code == "000":
        return "unreachable"
    try:
        n = int(code)
    except ValueError:
        return "unreachable"
    if 200 <= n < 400:
        return "ok"
    if n in (429, 503):
        return "transient"
    return "fail"


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--diff-range", required=True, help="Git diff range, e.g. abc1234...HEAD (THREE dots)")
    p.add_argument("--max-probe", type=int, default=30, help="Max distinct URLs to probe")
    p.add_argument("--timeout", type=int, default=10, help="Per-URL curl timeout in seconds")
    args = p.parse_args()

    if ".." not in args.diff_range:
        env = _envelope(
            "error",
            "diff-range must be a git range like abc...HEAD",
            {"findings": [], "skipped": [], "probed": 0},
            errors=[{"code": "BAD_RANGE", "message": "diff-range missing '..' or '...'", "retryable": False}],
        )
        print(json.dumps(env, ensure_ascii=False))
        return 2

    try:
        candidates = _extract_added_urls(args.diff_range)
    except RuntimeError as exc:
        env = _envelope(
            "error",
            "git diff failed",
            {"findings": [], "skipped": [], "probed": 0},
            errors=[{"code": "GIT_DIFF_FAILED", "message": str(exc), "retryable": True}],
        )
        print(json.dumps(env, ensure_ascii=False))
        return 2

    skipped: list[dict[str, str]] = []
    to_probe: list[tuple[str, str]] = []

    for url, file_hint in candidates:
        reason = _should_skip(url)
        if reason:
            skipped.append({"url": url, "file_hint": file_hint, "reason": reason})
        else:
            to_probe.append((url, file_hint))

    not_probed: list[dict[str, str]] = []
    if len(to_probe) > args.max_probe:
        not_probed = [
            {"url": u, "file_hint": f, "reason": f"sampling cap reached (--max-probe={args.max_probe})"}
            for u, f in to_probe[args.max_probe:]
        ]
        to_probe = to_probe[: args.max_probe]

    findings: list[dict[str, Any]] = []
    ok_count = 0
    transient_count = 0

    for url, file_hint in to_probe:
        code = _probe(url, args.timeout)
        cls = _classify(code)
        if cls == "ok":
            ok_count += 1
            continue
        if cls == "transient":
            transient_count += 1
            findings.append(
                {
                    "url": url,
                    "file_hint": file_hint,
                    "http_code": code,
                    "classification": "transient",
                    "severity": "advisory",
                }
            )
            continue
        # fail / unreachable
        findings.append(
            {
                "url": url,
                "file_hint": file_hint,
                "http_code": code,
                "classification": cls,
                "severity": "blocking",
            }
        )

    blocking_findings = [f for f in findings if f.get("severity") == "blocking"]

    if blocking_findings:
        status = "error"
        summary = (
            f"{len(blocking_findings)} URL(s) failed to resolve "
            f"(suspected fabrication); {ok_count} probed clean, {len(skipped)} skipped"
        )
        next_steps = [
            {
                "id": "review-fix",
                "summary": "Flag each blocking URL as [EXTERNAL-RESOURCE] FIX in the review report",
                "priority": "now",
                "automatable": False,
            }
        ]
        exit_code = 1
    elif not_probed or transient_count:
        status = "warning"
        bits = []
        if not_probed:
            bits.append(f"{len(not_probed)} URL(s) over sampling cap not probed")
        if transient_count:
            bits.append(f"{transient_count} transient (429/503)")
        summary = "URL probe completed with caveats: " + "; ".join(bits)
        next_steps = []
        if not_probed:
            next_steps.append(
                {
                    "id": "manual-spotcheck",
                    "summary": "Manually spot-check URLs that exceeded sampling cap",
                    "priority": "soon",
                    "automatable": False,
                }
            )
        exit_code = 0
    else:
        status = "ok"
        summary = f"All {ok_count} probed URL(s) resolve cleanly ({len(skipped)} skipped as known-safe)"
        next_steps = []
        exit_code = 0

    data = {
        "diff_range": args.diff_range,
        "candidates_total": len(candidates),
        "probed": len(to_probe),
        "skipped": skipped,
        "not_probed": not_probed,
        "findings": findings,
        "ok_count": ok_count,
    }

    env = _envelope(status, summary, data, next_steps=next_steps)
    print(json.dumps(env, ensure_ascii=False, indent=2))
    return exit_code


if __name__ == "__main__":
    sys.exit(main())

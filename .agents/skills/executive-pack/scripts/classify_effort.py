#!/usr/bin/env python3
"""Derive routed effort for a bead and persist it via bd metadata."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shlex
import subprocess
import sys
import tomllib
from pathlib import Path
from typing import Any


VALID_ROUTED_EFFORTS = frozenset(
    {"micro", "small", "medium", "large", "xl", "extra-large"}
)

# Bumped when the classification logic (prompt, parsing, classifier choice)
# changes in a way that invalidates previously cached results. A stored
# classification whose cache_version differs from this is treated as a miss.
CACHE_VERSION = 1
DURATION_LANGUAGE_RE = re.compile(
    r"\b(?:minutes?|hours?|days?|weeks?|minute|stunde|stunden|tag|tage|woche|wochen)\b",
    re.IGNORECASE,
)
SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[2]
# The agent contract is read and embedded verbatim into the classifier prompt
# (see load_agent_spec / build_prompt). It is never passed to codex as a path:
# doing so made codex treat "effort-classifier" as an unresolved agent name and
# fall back to an unbounded `find /Users/<user> -path '*/effort-classifier.md'
# -o -path '*/effort-classifier.toml'` home-directory scan — one CPU-thrashing
# walk per parallel bead in a wave.
#
# Probed in order: skill-local references/ (bundled with executive-pack, so
# the contract always travels with the skill no matter what install scope it
# lands in), then the cognovis-core marketplace source layout (used when this
# script runs inside the marketplace checkout itself). A drift-guard test
# asserts the two copies stay byte-identical when both are present.
AGENT_SPEC_CANDIDATES: tuple[Path, ...] = (
    SCRIPT_DIR.parent / "references" / "effort-classifier.md",
    REPO_ROOT / "agents" / "effort-classifier.md",
)


def run_command(args: list[str], *, input_text: str | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        args,
        capture_output=True,
        text=True,
        input=input_text,
    )


def _registry_path() -> Path:
    override = os.environ.get("COGNOVIS_BEADS_REGISTRY")
    if override:
        return Path(override).expanduser()
    base = os.environ.get("XDG_CONFIG_HOME") or (Path.home() / ".config")
    return Path(base).expanduser() / "cognovis" / "beads-repos.toml"


def _issue_tracker_name(repo_root: str | Path | None = None) -> str | None:
    """Return github/forgejo when the checkout's registry entry names a tracker."""
    try:
        loaded = tomllib.loads(_registry_path().read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return None
    checkout = Path(repo_root or Path.cwd()).expanduser().resolve()
    for entry in loaded.get("repository", []):
        raw = entry.get("path")
        if not raw:
            continue
        try:
            entry_path = Path(str(raw)).expanduser().resolve()
        except OSError:
            continue
        if entry_path != checkout:
            continue
        name = str(entry.get("tracker") or "").strip()
        if name in {"github", "forgejo"}:
            return name
        return None
    return None


def load_bead(bead_id: str) -> dict[str, Any]:
    tracker = _issue_tracker_name(Path.cwd())
    if not tracker:
        result = run_command(["bd", "show", bead_id, "--json"])
        if result.returncode != 0:
            raise RuntimeError(f"bd show failed for {bead_id}: {result.stderr.strip()}")
        payload = json.loads(result.stdout)
        if isinstance(payload, list) and payload:
            return payload[0]
        if isinstance(payload, dict):
            return payload
        raise RuntimeError(f"bd show returned no bead for {bead_id}")
    result = run_command(["ccore", "tracker", "show", bead_id])
    if result.returncode != 0:
        raise RuntimeError(f"ccore tracker show failed for {bead_id}: {result.stderr.strip()}")
    payload = json.loads(result.stdout)
    data = payload.get("data") if isinstance(payload, dict) and isinstance(payload.get("data"), dict) else payload
    if not isinstance(data, dict):
        raise RuntimeError(f"ccore tracker show returned no issue for {bead_id}")
    issue = dict(data)
    issue.setdefault("id", bead_id)
    issue.setdefault("description", issue.get("body") or "")
    return issue


def resolve_classifier_command() -> list[str]:
    override = os.environ.get("EFFORT_CLASSIFIER_CMD", "").strip()
    if override:
        return shlex.split(override)
    # read-only sandbox: effort classification only reads the bead (via stdin)
    # and the effort-classifier.md spec — it never writes files. Persistence
    # of the result is a separate subprocess in this script, outside
    # the classifier sandbox.
    return ["codex", "exec", "--json", "--sandbox", "read-only"]


def _classifier_input_payload(bead: dict[str, Any]) -> dict[str, str]:
    """The bead fields that feed the classifier — the cache-key input.

    metadata.routing.* is deliberately excluded so the hash stays stable
    across classify_effort's own metadata writes (the self-update trap).
    """
    return {
        "id": bead.get("id") or "",
        "title": bead.get("title") or "",
        "issue_type": bead.get("issue_type") or bead.get("type") or "",
        "description": bead.get("description") or "",
        "acceptance_criteria": bead.get("acceptance_criteria") or "",
    }


def load_agent_spec() -> str:
    """Return the effort-classifier agent contract text.

    Probes AGENT_SPEC_CANDIDATES in order (skill-local first, then the
    marketplace source layout). Fails loudly listing every probed path rather
    than letting the classifier run against a path codex would have to hunt
    for.
    """
    for path in AGENT_SPEC_CANDIDATES:
        try:
            return path.read_text(encoding="utf-8")
        except OSError:
            continue
    probed = ", ".join(str(p) for p in AGENT_SPEC_CANDIDATES)
    raise RuntimeError(
        f"effort-classifier agent spec not found; probed: {probed}"
    )


def build_prompt(bead: dict[str, Any]) -> str:
    payload = _classifier_input_payload(bead)
    spec = load_agent_spec()
    return (
        "Act as the effort-classifier agent. Follow the agent contract "
        "embedded below exactly. The full contract is inline — do NOT search "
        "the filesystem for an agent definition file.\n\n"
        "=== BEGIN effort-classifier agent contract ===\n"
        f"{spec}\n"
        "=== END effort-classifier agent contract ===\n\n"
        "Return JSON only. Do NOT use duration words (minutes, hours, days, "
        "weeks) anywhere in routed_reason — describe scope only (files, surfaces, "
        "tests, integrations).\n\n"
        f"{json.dumps(payload, ensure_ascii=True, indent=2)}\n"
    )


def compute_input_hash(bead: dict[str, Any]) -> str:
    """SHA-256 of the classifier input fields.

    Machine-independent: hashes only the bead content (no paths or other
    machine-specific data), so a hash computed on one machine matches the
    same bead on another — the cache travels via Dolt with the bead.
    """
    canonical = json.dumps(
        _classifier_input_payload(bead), ensure_ascii=True, sort_keys=True
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def read_cached_routing(bead: dict[str, Any], input_hash: str) -> dict[str, str] | None:
    """Return a still-valid cached routing payload, or None on a cache miss.

    A cache hit requires: stored input_hash matches the current bead content,
    stored cache_version matches CACHE_VERSION, and the stored routed_effort
    is a well-formed value.
    """
    metadata = bead.get("metadata")
    if not isinstance(metadata, dict):
        return None
    routing = metadata.get("routing")
    if not isinstance(routing, dict):
        return None
    if routing.get("input_hash") != input_hash:
        return None
    if routing.get("cache_version") != CACHE_VERSION:
        return None
    effort = str(routing.get("routed_effort") or "").strip().lower()
    if effort not in VALID_ROUTED_EFFORTS:
        return None
    return {
        "routed_effort": effort,
        "routed_reason": str(routing.get("routed_reason") or ""),
        "classifier": str(routing.get("classifier") or ""),
        "version": str(routing.get("version") or ""),
    }


def _extract_codex_agent_messages(text: str) -> list[str]:
    """Extract assistant agent_message text from codex JSONL event stream.

    `codex exec --json` emits one JSON event object per line, e.g.:
      {"type":"turn.started", ...}
      {"type":"item.completed","item":{"type":"agent_message","text":"..."}}
      {"type":"turn.completed", ...}

    The classifier's structured JSON payload lives inside the `item.text` of
    `item.completed` events whose `item.type` is `agent_message`. Return them
    in order; callers will try them last-first when looking for the routing
    JSON object.
    """
    messages: list[str] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict):
            continue
        if event.get("type") != "item.completed":
            continue
        item = event.get("item") or {}
        if not isinstance(item, dict):
            continue
        if item.get("type") != "agent_message":
            continue
        msg = item.get("text")
        if isinstance(msg, str) and msg.strip():
            messages.append(msg)
    return messages


def _find_routing_object(text: str) -> dict[str, Any] | None:
    """Locate the routed-effort JSON object embedded in arbitrary text.

    Scans for `{...}` substrings (balanced braces) and returns the last one
    that parses as a JSON object containing a `routed_effort` key. This lets
    classifier output include surrounding prose without breaking the parser.
    """
    candidates: list[dict[str, Any]] = []
    depth = 0
    start = -1
    for idx, ch in enumerate(text):
        if ch == "{":
            if depth == 0:
                start = idx
            depth += 1
        elif ch == "}":
            if depth > 0:
                depth -= 1
                if depth == 0 and start >= 0:
                    snippet = text[start : idx + 1]
                    try:
                        parsed = json.loads(snippet)
                    except json.JSONDecodeError:
                        start = -1
                        continue
                    if isinstance(parsed, dict) and "routed_effort" in parsed:
                        candidates.append(parsed)
                    start = -1
    return candidates[-1] if candidates else None


def parse_classifier_output(stdout: str) -> dict[str, Any]:
    text = stdout.strip()
    if not text:
        raise ValueError("classifier returned empty output")

    # Preferred path: direct JSON object (legacy single-line classifiers,
    # `EFFORT_CLASSIFIER_CMD` overrides that emit a bare JSON document).
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict) and "routed_effort" in parsed:
            return parsed
    except json.JSONDecodeError:
        pass

    # JSONL path: `codex exec --json` emits event objects, one per line. The
    # routing payload lives inside agent_message item.text — extract those
    # messages and search them (last-message-first) for the routing object.
    agent_messages = _extract_codex_agent_messages(text)
    for msg in reversed(agent_messages):
        # Try the message as a whole first…
        try:
            parsed = json.loads(msg.strip())
        except json.JSONDecodeError:
            parsed = None
        if isinstance(parsed, dict) and "routed_effort" in parsed:
            return parsed
        # …then look for an embedded JSON object inside surrounding prose.
        embedded = _find_routing_object(msg)
        if embedded is not None:
            return embedded

    # Last-resort fallback: scan any line that parses as a routing-object JSON
    # dict (covers classifiers that emit raw JSON lines without codex event
    # wrappers).
    for candidate in reversed([line.strip() for line in text.splitlines() if line.strip()]):
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict) and "routed_effort" in parsed:
            return parsed

    raise ValueError("classifier output did not contain a routed_effort JSON object")


def _strip_duration_language(text: str) -> str:
    """Remove forbidden duration words from advisory prose and tidy whitespace.

    routed_reason is free-text the classifier occasionally contaminates with
    duration words (minutes/hours/days/weeks, incl. German). Stripping them keeps
    stored metadata duration-language-free without failing the run (CL-9ith); the
    routed_effort decision is unaffected.
    """
    cleaned = DURATION_LANGUAGE_RE.sub("", text)
    cleaned = re.sub(r"\s{2,}", " ", cleaned)
    cleaned = re.sub(r"\s+([,.;:])", r"\1", cleaned)
    return cleaned.strip(" ,;:-")


def validate_classifier_payload(payload: dict[str, Any]) -> dict[str, str]:
    required = {"routed_effort", "routed_reason", "classifier", "version"}
    missing = sorted(required - payload.keys())
    if missing:
        raise ValueError(f"classifier payload missing keys: {', '.join(missing)}")

    normalized = {key: str(payload.get(key) or "").strip() for key in required}
    routed_effort = normalized["routed_effort"].lower()
    if routed_effort not in VALID_ROUTED_EFFORTS:
        raise ValueError(f"invalid routed_effort: {normalized['routed_effort']}")
    normalized["routed_effort"] = routed_effort

    if not all(normalized.values()):
        raise ValueError("classifier payload values must be non-empty strings")
    # routed_reason is advisory prose the classifier sometimes contaminates with
    # forbidden duration words (CL-9ith). routed_effort is the actual decision and
    # is strictly validated above, so sanitize the reason instead of hard-failing
    # the whole phase0 — keeps stored metadata duration-language-free without
    # throwing away a valid sizing.
    normalized["routed_reason"] = _strip_duration_language(normalized["routed_reason"])
    if not normalized["routed_reason"]:
        normalized["routed_reason"] = f"routed to {routed_effort} by effort classifier"
    # The non-prose fields must never contain duration language.
    for key in ("routed_effort", "classifier", "version"):
        if DURATION_LANGUAGE_RE.search(normalized[key]):
            raise ValueError(f"duration language is forbidden in classifier field {key!r}")
    return normalized


def invoke_classifier(bead: dict[str, Any]) -> dict[str, str]:
    result = run_command(resolve_classifier_command(), input_text=build_prompt(bead))
    if result.returncode != 0:
        raise RuntimeError(f"classifier command failed: {result.stderr.strip()}")
    return validate_classifier_payload(parse_classifier_output(result.stdout))


def write_routing_metadata(
    bead_id: str, payload: dict[str, str], input_hash: str
) -> None:
    routing_payload = {
        "routing": {
            "routed_effort": payload["routed_effort"],
            "routed_reason": payload["routed_reason"],
            "classifier": payload["classifier"],
            "version": payload["version"],
            "input_hash": input_hash,
            "cache_version": CACHE_VERSION,
        }
    }
    tracker = _issue_tracker_name(Path.cwd())
    if not tracker:
        args = [
            "bd",
            "update",
            bead_id,
            "--metadata",
            json.dumps(routing_payload),
        ]
        result = run_command(args)
        if result.returncode != 0:
            raise RuntimeError(f"bd update failed for {bead_id}: {result.stderr.strip()}")
        return
    note = json.dumps({"routing": routing_payload["routing"]}, sort_keys=True)
    result = run_command(["ccore", "tracker", "comment", bead_id, "--body", note])
    if result.returncode != 0:
        raise RuntimeError(
            f"ccore tracker comment failed for {bead_id}: {result.stderr.strip()}"
        )


def classify_effort(bead_id: str, *, force: bool = False) -> dict[str, str]:
    bead = load_bead(bead_id)
    input_hash = compute_input_hash(bead)

    if not force:
        cached = read_cached_routing(bead, input_hash)
        if cached is not None:
            print(
                f"classify_effort: cache hit for {bead_id} "
                f"(input unchanged, cache_version={CACHE_VERSION}) — "
                "skipping classifier",
                file=sys.stderr,
            )
            return cached

    payload = invoke_classifier(bead)
    write_routing_metadata(bead_id, payload, input_hash)
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Classify derived effort for a bead.")
    parser.add_argument("bead_id")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-classify even when a valid cached classification exists.",
    )
    args = parser.parse_args(argv)

    payload = classify_effort(args.bead_id, force=args.force)
    print(json.dumps(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

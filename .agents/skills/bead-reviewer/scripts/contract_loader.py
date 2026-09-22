#!/usr/bin/env python3
"""Resolve the shared bead-hygiene baseline and target-repository delta."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from pass3_parser import parse_overlay_rules  # noqa: E402


PROJECT_DELTA = Path(".agents/standards/bead-hygiene.md")
INSTALLED_BASELINE = Path.home() / ".agents/standards/workflow/bead-hygiene.md"
SOURCE_BASELINE = Path(__file__).resolve().parents[3] / "standards/workflow/bead-hygiene.md"
LABEL_FAMILIES_RE = re.compile(r"```bead-label-families\s*(?P<payload>.*?)```", re.DOTALL)


def _digest(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _semantic_contract(
    rules: list[dict[str, Any]],
    label_families: list[dict[str, Any]],
) -> dict[str, Any]:
    """Normalize only review semantics, excluding provenance and diagnostics."""
    semantic_rules = sorted(
        (
            {
                key: (
                    sorted({str(item) for item in rule.get(key, [])})
                    if key == "types" and isinstance(rule.get(key), list)
                    else rule.get(key)
                )
                for key in ("rule_id", "severity", "origin", "types", "text")
                if rule.get(key) is not None
            }
            for rule in rules
        ),
        key=lambda item: (
            str(item.get("rule_id") or ""),
            json.dumps(item, sort_keys=True, separators=(",", ":")),
        ),
    )
    semantic_families: list[dict[str, Any]] = []
    seen: set[str] = set()
    for family in label_families:
        normalized = {
            key: (
                sorted({str(item) for item in value})
                if isinstance(value, list)
                else value
            )
            for key, value in family.items()
        }
        serialized = json.dumps(normalized, sort_keys=True, separators=(",", ":"))
        if serialized not in seen:
            seen.add(serialized)
            semantic_families.append(normalized)
    semantic_families.sort(
        key=lambda item: json.dumps(item, sort_keys=True, separators=(",", ":"))
    )
    return {"rules": semantic_rules, "label_families": semantic_families}


def compute_contract_sha(
    rules: list[dict[str, Any]] | dict[str, Any],
    label_families: list[dict[str, Any]] | None = None,
) -> str:
    """Hash the fully resolved semantic rule and label-family contract once."""
    if isinstance(rules, dict):
        resolved = rules
        rules = resolved.get("rules", [])
        label_families = resolved.get("label_families", [])
    payload = json.dumps(
        _semantic_contract(rules, label_families or []),
        sort_keys=True,
        separators=(",", ":"),
    )
    return _digest(payload)


def _baseline_path() -> Path:
    return SOURCE_BASELINE if SOURCE_BASELINE.is_file() else INSTALLED_BASELINE


def _source(path: Path, role: str, *, optional: bool = False) -> dict[str, Any]:
    if not path.is_file():
        return {
            "role": role,
            "path": str(path),
            "status": "not-found-optional" if optional else "missing",
            "sha256": None,
            "rule_count": 0,
            "label_family_count": 0,
        }
    content = path.read_text(encoding="utf-8")
    return {
        "role": role,
        "path": str(path),
        "status": "loaded",
        "sha256": _digest(content),
        "rule_count": 0,
        "label_family_count": 0,
        "content": content,
    }


def _parse_label_families(content: str, path: Path) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    match = LABEL_FAMILIES_RE.search(content)
    if match is None:
        return [], []
    try:
        payload = json.loads(match.group("payload"))
    except json.JSONDecodeError as exc:
        return [], [{
            "code": "CONTRACT-LABEL-FAMILY-PARSE",
            "message": f"Invalid bead-label-families JSON in {path}: {exc}",
        }]
    families = payload.get("families", []) if isinstance(payload, dict) else []
    if not isinstance(families, list):
        return [], [{
            "code": "CONTRACT-LABEL-FAMILY-PARSE",
            "message": f"bead-label-families in {path} must contain a families list",
        }]
    return families, []


def _rules_for(source: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    if source["status"] != "loaded":
        return [], []
    rules = parse_overlay_rules(source["content"])
    diagnostics: list[dict[str, str]] = []
    for rule in rules:
        rule_id = rule.get("rule_id")
        if not rule_id:
            rule_id = f"LEGACY-{_digest(rule['text'])[:12].upper()}"
            diagnostics.append({
                "code": "CONTRACT-RULE-ID-MISSING",
                "message": f"{source['path']} contains a rule without an explicit rule-id: {rule_id}",
            })
        rule["rule_id"] = rule_id
        rule["provenance"] = source["role"]
        rule["source_path"] = source["path"]
        rule["content_sha256"] = _digest(rule["text"])
    source["rule_count"] = len(rules)
    families, family_diagnostics = _parse_label_families(source["content"], Path(source["path"]))
    source["label_family_count"] = len(families)
    source["label_families"] = families
    diagnostics.extend(family_diagnostics)
    return rules, diagnostics


def resolve_contract(
    *,
    repo_root: str | Path,
    baseline_path: str | Path | None = None,
) -> dict[str, Any]:
    """Return a provenance-preserving baseline plus project-delta contract."""
    root = Path(repo_root).expanduser().resolve()
    baseline = Path(baseline_path).expanduser().resolve() if baseline_path else _baseline_path()
    sources = [
        _source(baseline, "baseline"),
        _source(root / PROJECT_DELTA, "project-delta", optional=True),
    ]
    diagnostics: list[dict[str, str]] = []
    if sources[0]["status"] == "missing":
        diagnostics.append({
            "code": "CONTRACT-BASELINE-MISSING",
            "message": f"Bead-hygiene baseline not found: {baseline}",
        })
        return _result("configuration-error", root, sources, [], [], diagnostics)

    parsed: list[list[dict[str, Any]]] = []
    for source in sources:
        rules, parse_diagnostics = _rules_for(source)
        parsed.append(rules)
        diagnostics.extend(parse_diagnostics)

    if (
        sources[1]["status"] == "loaded"
        and sources[0]["sha256"] == sources[1]["sha256"]
    ):
        diagnostics.append({
            "code": "OVERLAY-FULL-COPY",
            "message": "Project bead-hygiene is a full copy of the baseline; retain only project additions.",
        })

    merged: list[dict[str, Any]] = []
    by_id: dict[str, dict[str, Any]] = {}
    for rule in [*parsed[0], *parsed[1]]:
        existing = by_id.get(rule["rule_id"])
        if existing is None:
            by_id[rule["rule_id"]] = rule
            merged.append(rule)
            continue
        if existing["content_sha256"] != rule["content_sha256"]:
            diagnostics.append({
                "code": "CONTRACT-RULE-CONFLICT",
                "message": (
                    f"Rule {rule['rule_id']} differs between "
                    f"{existing['source_path']} and {rule['source_path']}"
                ),
            })

    families = [
        family
        for source in sources
        for family in source.get("label_families", [])
    ]
    blocking = {"CONTRACT-RULE-CONFLICT", "OVERLAY-FULL-COPY", "CONTRACT-LABEL-FAMILY-PARSE"}
    status = "conflict" if any(item["code"] in blocking for item in diagnostics) else "ok"
    return _result(status, root, sources, merged, families, diagnostics)


def _result(
    status: str,
    repo_root: Path,
    sources: list[dict[str, Any]],
    rules: list[dict[str, Any]],
    label_families: list[dict[str, Any]],
    diagnostics: list[dict[str, str]],
) -> dict[str, Any]:
    public_sources = [
        {key: value for key, value in source.items() if key not in {"content", "label_families"}}
        for source in sources
    ]
    return {
        "status": status,
        "repo_root": str(repo_root),
        "sources": public_sources,
        "rules": rules,
        "label_families": label_families,
        "contract_sha": compute_contract_sha(rules, label_families),
        "diagnostics": diagnostics,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--baseline")
    args = parser.parse_args()
    result = resolve_contract(repo_root=args.repo_root, baseline_path=args.baseline)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "ok" else 2


if __name__ == "__main__":
    raise SystemExit(main())

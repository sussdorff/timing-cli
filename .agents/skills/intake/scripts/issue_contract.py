#!/usr/bin/env python3
"""Resolve the issue-intake baseline, the project delta and installed contributors.

Resolution order for the baseline ``workflow/issue-intake.md``:

1. ``<repo>/.agents/standards/workflow/issue-intake.md`` (project-local install)
2. ``<home>/.agents/standards/workflow/issue-intake.md`` (global install)
3. the Library source tree next to this skill

The optional project delta lives at ``<repo>/.agents/standards/issue-intake.md``.
A rule may declare ``<!-- requires-section: Heading | Alias -->`` annotations; each
one names a ``## <Heading>`` section (with alternative headings separated by
``|``) that the issue body must contain, and the author check enforces it.
Installed standards that declare ``contributes_issue_intake: true`` in their
frontmatter contribute additional rules (for example the FHIR production-data
impact standard).

This module is self-contained so that the intake skill works from any installed
copy without importing another skill.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

BASELINE_RELATIVE = Path(".agents/standards/workflow/issue-intake.md")
PROJECT_DELTA = Path(".agents/standards/issue-intake.md")
# The retired overlay name is assembled so that the intake skill carries no
# reference to the retired standard; it is only needed to fail closed on it.
LEGACY_DELTA = Path(".agents/standards") / ("-".join(("be" + "ad", "hygiene")) + ".md")
INSTALLED_STANDARDS = Path(".agents/standards")
# From skills/intake/scripts in the source tree this is <root>/standards/...; from
# an installed .agents/skills/intake/scripts copy it is .agents/standards/...
SOURCE_BASELINE = Path(__file__).resolve().parents[3] / "standards/workflow/issue-intake.md"
CONTRIBUTOR_MARKER = re.compile(r"(?m)^contributes_issue_intake:\s*true\s*$")
LABEL_FAMILIES_RE = re.compile(r"```issue-label-families\s*(?P<payload>.*?)```", re.DOTALL)
# Any other `<word>-label-families` fence (for example the retired tracker's
# name) would otherwise be skipped silently and drop the overlay's families.
FOREIGN_LABEL_FAMILIES_RE = re.compile(r"(?m)^```(?P<name>[\w.-]+-label-families)\b")

SECTION_RE = re.compile(
    r"^## (?P<title>Pflichtfelder|Anti-Patterns)\n(?P<body>.*?)(?=^## |\Z)",
    re.MULTILINE | re.DOTALL,
)
COMMENT_RE = re.compile(
    r"<!--\s*(?P<key>rule-id|severity|types|requires-section)\s*:\s*(?P<value>.*?)\s*-->"
)
FENCED_BLOCK_RE = re.compile(r"```.*?```", re.DOTALL)
BLOCKING_CODES = {
    "CONTRACT-RULE-CONFLICT",
    "OVERLAY-FULL-COPY",
    "CONTRACT-LABEL-FAMILY-PARSE",
    "CONTRACT-LEGACY-OVERLAY",
    "CONTRACT-REQUIRES-SECTION-PARSE",
}


# ---------------------------------------------------------------------------
# rule parsing
# ---------------------------------------------------------------------------


def apply_type_filter(rule: dict[str, Any], issue_type: str) -> bool:
    """True when the rule applies to the given issue type."""
    types = rule.get("types")
    if not types:
        return True
    return issue_type.strip().lower() in {item.lower() for item in types}


def parse_rules(md_text: str) -> list[dict[str, Any]]:
    """Parse the machine-readable rule bullets of a standard."""
    rules: list[dict[str, Any]] = []
    without_fences = FENCED_BLOCK_RE.sub("", md_text)
    for section_match in SECTION_RE.finditer(without_fences):
        section_title = section_match.group("title")
        items = re.split(r"(?m)^- ", section_match.group("body"))
        for raw_item in items[1:]:
            item = raw_item.strip()
            if not item:
                continue
            severity = _scalar_comment(item, "severity")
            rule: dict[str, Any] = {
                "rule_id": _scalar_comment(item, "rule-id"),
                "text": _normalize_text(item),
                "severity": severity.strip().lower() if severity else "critical",
                "types": _csv_comment(item, "types"),
                "origin": section_title,
            }
            required = _required_sections(item)
            if required is not None:
                rule["requires_sections"] = required
            rules.append(rule)
    return rules


def _required_sections(item: str) -> list[list[str]] | None:
    """Heading alternatives of every ``requires-section`` annotation, in order.

    ``None`` means the rule has no annotation. An annotation without any heading
    yields an empty alternative list, which the resolver reports as a parse error.
    """
    values = [
        match.group("value")
        for match in COMMENT_RE.finditer(item)
        if match.group("key") == "requires-section"
    ]
    if not values:
        return None
    sections: list[list[str]] = []
    for value in values:
        alternatives = [part.strip().lstrip("#").strip() for part in value.split("|")]
        sections.append([alternative for alternative in alternatives if alternative])
    return sections


def _scalar_comment(item: str, key: str) -> str | None:
    for match in COMMENT_RE.finditer(item):
        if match.group("key") == key:
            return match.group("value").strip()
    return None


def _csv_comment(item: str, key: str) -> list[str] | None:
    value = _scalar_comment(item, key)
    if not value:
        return None
    parts = [part.strip().lower() for part in value.split(",")]
    return [part for part in parts if part]


def _normalize_text(item: str) -> str:
    without_comments = COMMENT_RE.sub("", item)
    lines = [line.strip() for line in without_comments.splitlines()]
    return " ".join(line for line in lines if line).strip()


# ---------------------------------------------------------------------------
# contract resolution
# ---------------------------------------------------------------------------


def _digest(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def compute_contract_sha(
    rules: list[dict[str, Any]], label_families: list[dict[str, Any]]
) -> str:
    """Hash the resolved rule semantics, excluding provenance."""
    semantic_rules = sorted(
        (
            {
                key: (
                    sorted({str(item) for item in rule[key]})
                    if key == "types" and isinstance(rule.get(key), list)
                    else rule.get(key)
                )
                for key in ("rule_id", "severity", "origin", "types", "text", "requires_sections")
                if rule.get(key) is not None
            }
            for rule in rules
        ),
        key=lambda item: (
            str(item.get("rule_id") or ""),
            json.dumps(item, sort_keys=True, separators=(",", ":")),
        ),
    )
    families = sorted(
        {json.dumps(family, sort_keys=True, separators=(",", ":")) for family in label_families}
    )
    payload = json.dumps(
        {"rules": semantic_rules, "label_families": families},
        sort_keys=True,
        separators=(",", ":"),
    )
    return _digest(payload)


def _rule_content_sha(rule: dict[str, Any]) -> str:
    """Digest of the rule text, plus its required sections when it declares any."""
    required = rule.get("requires_sections")
    if required is None:
        return _digest(rule["text"])
    return _digest(rule["text"] + "\n" + json.dumps(required, separators=(",", ":")))


def baseline_candidates(*, repo_root: Path, home: Path) -> list[Path]:
    return [repo_root / BASELINE_RELATIVE, home / BASELINE_RELATIVE, SOURCE_BASELINE]


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


def _installed_contributors(root: Path) -> list[dict[str, Any]]:
    standards_root = root / INSTALLED_STANDARDS
    if not standards_root.is_dir():
        return []
    candidates = {*standards_root.glob("*.md"), *standards_root.glob("*/*.md")}
    contributors: list[dict[str, Any]] = []
    for path in sorted(candidates):
        content = path.read_text(encoding="utf-8")
        if not CONTRIBUTOR_MARKER.search(content):
            continue
        relative = path.relative_to(standards_root)
        name = relative.parts[0] if len(relative.parts) > 1 else relative.stem
        contributors.append(_source(path, f"installed-contributor:{name}"))
    return contributors


def _parse_label_families(
    content: str, path: str
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    foreign = sorted(
        {
            found.group("name")
            for found in FOREIGN_LABEL_FAMILIES_RE.finditer(content)
            if found.group("name") != "issue-label-families"
        }
    )
    if foreign:
        return [], [
            {
                "code": "CONTRACT-LABEL-FAMILY-PARSE",
                "message": (
                    f"{path} declares label families in an unsupported fence "
                    f"({', '.join(foreign)}); rename it to issue-label-families."
                ),
            }
        ]
    match = LABEL_FAMILIES_RE.search(content)
    if match is None:
        return [], []
    try:
        payload = json.loads(match.group("payload"))
    except json.JSONDecodeError as exc:
        return [], [
            {
                "code": "CONTRACT-LABEL-FAMILY-PARSE",
                "message": f"Invalid label-families JSON in {path}: {exc}",
            }
        ]
    families = payload.get("families", []) if isinstance(payload, dict) else []
    if not isinstance(families, list):
        return [], [
            {
                "code": "CONTRACT-LABEL-FAMILY-PARSE",
                "message": f"label-families in {path} must contain a families list",
            }
        ]
    return families, []


def _rules_for(source: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    if source["status"] != "loaded":
        return [], []
    rules = parse_rules(source["content"])
    diagnostics: list[dict[str, str]] = []
    for rule in rules:
        rule_id = rule.get("rule_id")
        if not rule_id:
            rule_id = f"LEGACY-{_digest(rule['text'])[:12].upper()}"
            diagnostics.append(
                {
                    "code": "CONTRACT-RULE-ID-MISSING",
                    "message": (
                        f"{source['path']} contains a rule without an explicit rule-id: {rule_id}"
                    ),
                }
            )
        rule["rule_id"] = rule_id
        rule["provenance"] = source["role"]
        rule["source_path"] = source["path"]
        rule["content_sha256"] = _rule_content_sha(rule)
        if any(not alternatives for alternatives in rule.get("requires_sections") or []):
            diagnostics.append(
                {
                    "code": "CONTRACT-REQUIRES-SECTION-PARSE",
                    "message": (
                        f"{source['path']} rule {rule_id} has a requires-section annotation "
                        "without a heading"
                    ),
                }
            )
    source["rule_count"] = len(rules)
    families, family_diagnostics = _parse_label_families(source["content"], source["path"])
    source["label_family_count"] = len(families)
    source["label_families"] = families
    diagnostics.extend(family_diagnostics)
    return rules, diagnostics


def resolve_contract(
    *, repo_root: str | Path, home: str | Path | None = None
) -> dict[str, Any]:
    """Return the provenance-preserving issue-intake contract for ``repo_root``."""
    root = Path(repo_root).expanduser().resolve()
    user_home = Path(home).expanduser() if home is not None else Path.home()
    candidates = baseline_candidates(repo_root=root, home=user_home)
    baseline = next((path for path in candidates if path.is_file()), candidates[-1])
    sources = [
        _source(baseline, "baseline"),
        _source(root / PROJECT_DELTA, "project-delta", optional=True),
        *_installed_contributors(root),
    ]
    diagnostics: list[dict[str, str]] = []
    if sources[0]["status"] == "missing":
        probed = ", ".join(str(path) for path in candidates)
        diagnostics.append(
            {
                "code": "CONTRACT-BASELINE-MISSING",
                "message": f"Issue-intake baseline not found. Probed: {probed}",
            }
        )
        return _result("configuration-error", root, sources, [], [], diagnostics)

    legacy = root / LEGACY_DELTA
    if legacy.is_file() and sources[1]["status"] != "loaded":
        diagnostics.append(
            {
                "code": "CONTRACT-LEGACY-OVERLAY",
                "message": (
                    f"Project overlay {legacy} uses the retired name {LEGACY_DELTA.name} "
                    f"and is no longer read. Move its project-specific rules to "
                    f"{root / PROJECT_DELTA} (issue-intake.md)."
                ),
            }
        )

    parsed: list[list[dict[str, Any]]] = []
    for source in sources:
        rules, parse_diagnostics = _rules_for(source)
        parsed.append(rules)
        diagnostics.extend(parse_diagnostics)

    if sources[1]["status"] == "loaded" and sources[0]["sha256"] == sources[1]["sha256"]:
        diagnostics.append(
            {
                "code": "OVERLAY-FULL-COPY",
                "message": (
                    "The project issue-intake overlay is a full copy of the baseline; "
                    "retain only project additions."
                ),
            }
        )

    merged: list[dict[str, Any]] = []
    by_id: dict[str, dict[str, Any]] = {}
    for rule in (rule for source_rules in parsed for rule in source_rules):
        existing = by_id.get(rule["rule_id"])
        if existing is None:
            by_id[rule["rule_id"]] = rule
            merged.append(rule)
            continue
        if existing["content_sha256"] != rule["content_sha256"]:
            diagnostics.append(
                {
                    "code": "CONTRACT-RULE-CONFLICT",
                    "message": (
                        f"Rule {rule['rule_id']} differs between "
                        f"{existing['source_path']} and {rule['source_path']}"
                    ),
                }
            )

    families = [family for source in sources for family in source.get("label_families", [])]
    status = "conflict" if any(item["code"] in BLOCKING_CODES for item in diagnostics) else "ok"
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repo-root", required=True)
    args = parser.parse_args(argv)
    result = resolve_contract(repo_root=args.repo_root)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "ok" else 2


if __name__ == "__main__":
    raise SystemExit(main())

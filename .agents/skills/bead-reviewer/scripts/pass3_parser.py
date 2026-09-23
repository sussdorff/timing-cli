from __future__ import annotations

import re
from typing import Any


SECTION_RE = re.compile(
    r"^## (?P<title>Pflichtfelder|Anti-Patterns)\n(?P<body>.*?)(?=^## |\Z)",
    re.MULTILINE | re.DOTALL,
)
COMMENT_RE = re.compile(r"<!--\s*(?P<key>rule-id|severity|types)\s*:\s*(?P<value>.*?)\s*-->")
FENCED_BLOCK_RE = re.compile(r"```.*?```", re.DOTALL)


def apply_severity_override(rule: dict[str, Any], declared: str) -> dict[str, Any]:
    updated = dict(rule)
    if declared:
        updated["severity"] = declared.strip().lower()
    return updated


def apply_type_filter(rule: dict[str, Any], bead_type: str) -> bool:
    types = rule.get("types")
    if not types:
        return True
    return bead_type.strip().lower() in {item.lower() for item in types}


def parse_overlay_rules(md_text: str) -> list[dict[str, Any]]:
    rules: list[dict[str, Any]] = []
    without_fences = FENCED_BLOCK_RE.sub("", md_text)
    for section_match in SECTION_RE.finditer(without_fences):
        section_title = section_match.group("title")
        body = section_match.group("body")
        items = re.split(r"(?m)^- ", body)
        for raw_item in items[1:]:
            item = raw_item.strip()
            if not item:
                continue
            rule = {
                "rule_id": _extract_scalar_comment(item, "rule-id"),
                "text": _normalize_text(item),
                "severity": "critical",
                "types": _extract_csv_comment(item, "types"),
                "origin": section_title,
            }
            severity = _extract_scalar_comment(item, "severity")
            if severity:
                rule = apply_severity_override(rule, severity)
            rules.append(rule)
    return rules


def _extract_scalar_comment(item: str, key: str) -> str | None:
    for match in COMMENT_RE.finditer(item):
        if match.group("key") == key:
            return match.group("value").strip()
    return None


def _extract_csv_comment(item: str, key: str) -> list[str] | None:
    value = _extract_scalar_comment(item, key)
    if not value:
        return None
    parts = [part.strip().lower() for part in value.split(",")]
    return [part for part in parts if part]


def _normalize_text(item: str) -> str:
    without_comments = COMMENT_RE.sub("", item)
    lines = [line.strip() for line in without_comments.splitlines()]
    return " ".join(line for line in lines if line).strip()

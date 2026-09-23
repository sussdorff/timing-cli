#!/usr/bin/env python3
"""Reject tautological expected values; require structured independent provenance."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from tdd_loop_contract import PathClassificationError, repo_relative_path  # noqa: E402

INDEPENDENT_SOURCE_KINDS = frozenset(
    {
        "generated_fixture",
        "ig_profile",
        "oracle",
        "worked_example",
        "source_value_profile",
    }
)
PROVENANCE_FIELDS = {
    "generated_fixture": ("fixture_path", "selector"),
    "ig_profile": ("ig_canonical", "element"),
    "oracle": ("oracle_ledger_id",),
    "worked_example": ("worked_example_pointer",),
    "source_value_profile": ("profile_path", "selector"),
}
TAUTOLOGICAL_KINDS = frozenset({"implementation", "computed_as_code", "tautological"})


def _is_tautological(entry: dict[str, Any]) -> bool:
    """A value is tautological when its declared source is the implementation.

    The check is structural on purpose: prose in ``source`` or ``derivation``
    is not pattern-matched, because a phrase list teaches authors to rephrase,
    not to cite. Independence is proven by the structured provenance fields
    an INDEPENDENT_SOURCE_KINDS entry must carry and the authored test must
    name (see ``_test_names_source_and_value``).
    """
    kind = str(entry.get("source_kind") or "").strip()
    return kind in TAUTOLOGICAL_KINDS


def _missing_provenance(entry: dict[str, Any], kind: str) -> list[str]:
    required = PROVENANCE_FIELDS.get(kind, ())
    return [field for field in required if not str(entry.get(field) or "").strip()]


def _contained_test_path(
    test_path: str, *, repo_root: Path, test_tree: str
) -> tuple[Path | None, str | None]:
    if not test_path.strip():
        return None, "test_path is required so provenance is bound to the authored test"
    try:
        tree = repo_relative_path(test_tree, repo_root)
        relative = repo_relative_path(test_path, repo_root)
    except PathClassificationError as exc:
        return None, f"test_path is outside the repository ({exc})"
    if relative != tree and tree not in relative.parents:
        return None, "test_path is outside the declared test tree"
    resolved = (repo_root.resolve() / relative).resolve()
    try:
        resolved.relative_to((repo_root.resolve() / tree).resolve())
    except ValueError:
        return None, "test_path is outside the declared test tree"
    if not resolved.is_file():
        return None, f"test_path does not exist: {test_path}"
    return resolved, None


def _test_names_source_and_value(
    entry: dict[str, Any], *, repo_root: Path, test_tree: str
) -> str | None:
    resolved, error = _contained_test_path(
        str(entry.get("test_path") or ""),
        repo_root=repo_root,
        test_tree=test_tree,
    )
    if error:
        return error
    assert resolved is not None
    body = resolved.read_text(encoding="utf-8")
    value = str(entry.get("value") or "")
    if value and value not in body:
        return "authored test does not contain the expected value"
    kind = str(entry.get("source_kind") or "").strip()
    tokens = [str(entry.get(field) or "").strip() for field in PROVENANCE_FIELDS.get(kind, ())]
    tokens.append(str(entry.get("source") or "").strip())
    missing = [token for token in tokens if token and token not in body]
    if missing:
        return "authored test/docstring does not name the independent source"
    return None


def verify_expected_values(
    entries: list[dict[str, Any]],
    *,
    repo_root: Path | None = None,
    test_tree: str | None = None,
) -> dict[str, Any]:
    sources: list[str] = []
    root = (repo_root or Path.cwd()).resolve()
    tree = str(test_tree or "").strip()
    needs_path = any(
        str(entry.get("source_kind") or "") not in TAUTOLOGICAL_KINDS
        and str(entry.get("source") or "").strip()
        for entry in entries
    )
    if needs_path:
        if not tree:
            return {
                "status": "rejected",
                "reason": "test_tree is required so test_path is contained",
                "sources": sources,
            }
        try:
            repo_relative_path(tree, root)
        except PathClassificationError as exc:
            return {"status": "rejected", "reason": str(exc), "sources": sources}
    for index, entry in enumerate(entries):
        source = str(entry.get("source") or "").strip()
        kind = str(entry.get("source_kind") or "").strip()
        name = str(entry.get("name") or f"expected[{index}]")
        if not source or not kind:
            return {
                "status": "rejected",
                "reason": f"{name}: expected value must name an independent source",
                "sources": sources,
            }
        if _is_tautological(entry) or kind not in INDEPENDENT_SOURCE_KINDS:
            return {
                "status": "rejected",
                "reason": f"{name}: tautological expected value (source must be independent of the implementation)",
                "sources": sources,
            }
        missing = _missing_provenance(entry, kind)
        if missing:
            return {
                "status": "rejected",
                "reason": f"{name}: missing structured provenance fields: {', '.join(missing)}",
                "sources": sources,
            }
        bound = _test_names_source_and_value(entry, repo_root=root, test_tree=tree)
        if bound:
            return {
                "status": "rejected",
                "reason": f"{name}: {bound}",
                "sources": sources,
            }
        sources.append(source)
    return {"status": "ok", "reason": "all expected values name independent sources", "sources": sources}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    verify = sub.add_parser("verify", help="Verify expected-value sources")
    verify.add_argument("--from-json", required=True)
    verify.add_argument("--repo-root", default=".")
    verify.add_argument("--test-tree", default="")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    payload = json.loads(Path(args.from_json).read_text(encoding="utf-8"))
    entries = payload.get("expected_values")
    if not isinstance(entries, list):
        print(json.dumps({"status": "rejected", "reason": "expected_values list required"}, indent=2))
        return 1
    result = verify_expected_values(
        entries,
        repo_root=Path(args.repo_root),
        test_tree=args.test_tree or payload.get("test_tree"),
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())

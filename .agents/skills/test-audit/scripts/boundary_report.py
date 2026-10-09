#!/usr/bin/env python3
"""Report tests that bypass a repository's declared test units.

Private helper of the test-audit skill. Stdlib only, Python 3.11+:

    uv run --no-project python <skill-root>/scripts/boundary_report.py \\
        --repo <path> [--declaration <path>] [--json]

The declaration is the JSON file the repository's AGENTS.md names (see the
"Declared test units" section of the workflow/test-quality standard):

    {"modules": [{"name", "dir", "entry"}],
     "ports": [{"name", "port", "contract",
                "adapters": [{"name", "path", "in_memory"?}]}],
     "aliases"?: {"<ts prefix>": "<repo-relative dir>"},
     "import_roots"?: ["<repo-relative dir>", ...]}

``import_roots`` are the Python roots absolute imports resolve against (default
the repository root and ``src``); ``""`` names the repository root. A relative
``--declaration`` path resolves against ``--repo``.

The helper never searches for a declaration. Without ``--declaration`` it
reports "no declared test units" and the audit runs unchanged.

Findings, grouped per declared module and port:

- ``boundary-bypass``: a test outside a module imports a module file other than
  its entry.
- ``internal-without-reason``: a test inside a module imports a module file other
  than its entry and has no ``test-boundary-exception: <reason>`` line. Tests with
  such a line are listed as ``stated_exceptions`` and are not findings.
- ``adapter-without-contract-run``: no contract run covers the adapter. A test
  file is a contract run for an adapter when it is or imports the contract suite
  and imports that adapter and no other adapter of the port. The declared
  contract file is scanned whatever its name.
- ``ambiguous-contract-run``: a test file imports the contract suite and several
  adapters of the port; it covers none of them.
- ``port-bypass``: a test file imports a file under a real (not in-memory)
  adapter and is neither the contract suite, a contract run for that adapter,
  nor a test inside the adapter's own path.
- ``port-without-in-memory-adapter``: no adapter declares ``"in_memory": true``.
  This is a finding, not a declaration error, so the rest of the report survives.

Declaration errors (exit 2): an unreadable or non-UTF-8 file, invalid or
non-object JSON, a missing or
non-string field, a path that is absolute, contains ``..`` or does not exist,
an entry outside its dir, duplicate module, port or adapter names, nested
module dirs, a port without adapters, a non-boolean ``in_memory``, an
``aliases`` value that is not a map of prefixes to existing directories, an
``import_roots`` value that is not a list of existing directories.

Specifiers the helper could not check are listed per test file as
``unchecked``: relative specifiers that did not resolve, alias-like TS
specifiers (``@/``, ``~/``, ``#``) no declared alias resolves, and Python
relative imports that did not resolve. Bare package names are ignored. A test
file that cannot be read or decoded as UTF-8 is listed as ``unreadable: ...``,
a Python test that does not parse as ``unparseable: ...``.

Exit codes: 0 when a report is produced (findings are report content, not a
process failure); 2 on a usage or declaration error.

Limits: imports are read statically. TS/JS relative specifiers (``import``,
``import type``, ``export ... from``, side-effect imports, ``import()``,
``require``, ``mock.module``, ``vi.mock``, ``jest.mock`` and their variants) and
Python ``import``/``from`` statements (absolute against the import roots, or
relative) are resolved; bare package specifiers, undeclared path aliases,
computed specifiers and string-based patches such as ``mock.patch("a.b")`` are
not, and commented-out imports still count. Every finding is a candidate the
auditor confirms by reading the test.
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

SCHEMA = "test-audit.boundary-report/v1"

SKIPPED_DIRS = frozenset(
    {"node_modules", ".git", ".venv", "dist", "build", ".agents", ".claude"}
)
TS_EXTENSIONS = (".ts", ".tsx", ".mts", ".cts", ".js", ".jsx", ".mjs", ".cjs")
SOURCE_EXTENSIONS = frozenset(TS_EXTENSIONS + (".py",))
TEST_DIRS = frozenset({"tests", "__tests__"})
DEFAULT_IMPORT_ROOTS = ("", "src")
ALIAS_LIKE_PREFIXES = ("@/", "~/", "#")

_TS_FROM = re.compile(
    r"\b(?:import|export)\s+(?:type\s+)?[^;'\"`]*?\bfrom\s*(['\"])([^'\"\n]+)\1"
)
_TS_SIDE_EFFECT = re.compile(r"\bimport\s*(['\"])([^'\"\n]+)\1")
_TS_CALL = re.compile(
    r"(?<![\w$])(?:import|require|mock\.module|vi\.mock|vi\.doMock|vi\.importActual"
    r"|jest\.mock|jest\.doMock|jest\.requireActual)\s*\(\s*(['\"`])([^'\"`\n]+)\1"
)


_EXCEPTION_REASON = re.compile(r"test-boundary-exception:[ \t]*(\S[^\n]*)")


class DeclarationError(Exception):
    """The declaration file is missing or invalid."""


@dataclass(frozen=True)
class Module:
    name: str
    dir: str
    entry: str


@dataclass(frozen=True)
class Adapter:
    name: str
    path: str
    in_memory: bool


@dataclass(frozen=True)
class Port:
    name: str
    port: str
    contract: str
    adapters: tuple[Adapter, ...]


@dataclass
class Declaration:
    modules: list[Module] = field(default_factory=list)
    ports: list[Port] = field(default_factory=list)
    aliases: dict[str, str] = field(default_factory=dict)
    import_roots: list[str] = field(default_factory=lambda: list(DEFAULT_IMPORT_ROOTS))


def load_declaration(repo: Path, path: Path) -> Declaration:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise DeclarationError(f"declaration not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise DeclarationError(f"declaration is not valid JSON: {exc}") from exc
    except (OSError, UnicodeError) as exc:
        raise DeclarationError(f"declaration {path} cannot be read: {exc}") from exc
    if not isinstance(raw, dict):
        raise DeclarationError("the declaration must be a JSON object")
    modules = [
        _module(repo, index, item)
        for index, item in enumerate(_list(raw, "modules", "declaration"))
    ]
    ports = [
        _port(repo, index, item)
        for index, item in enumerate(_list(raw, "ports", "declaration"))
    ]
    aliases = _aliases(repo, raw)
    import_roots = _import_roots(repo, raw)
    _unique([m.name for m in modules], "module")
    _unique([p.name for p in ports], "port")
    for outer in modules:
        for inner in modules:
            if outer is not inner and _within(PurePosixPath(inner.dir), outer.dir):
                raise DeclarationError(
                    f"module {inner.name!r} ({inner.dir}) is nested in module "
                    f"{outer.name!r} ({outer.dir})"
                )
    return Declaration(
        modules=modules, ports=ports, aliases=aliases, import_roots=import_roots
    )


def _directory(repo: Path, value: object, where: str) -> str:
    """Validate a repository-relative directory; "" names the repository root."""
    if not isinstance(value, str):
        raise DeclarationError(f"{where} must be a string")
    if value == "":
        return ""
    return _path(repo, {"dir": value}, "dir", where, "dir")


def _aliases(repo: Path, raw: dict) -> dict[str, str]:
    if "aliases" not in raw:
        return {}
    value = raw["aliases"]
    if not isinstance(value, dict):
        raise DeclarationError("declaration: 'aliases' must map prefixes to directories")
    aliases: dict[str, str] = {}
    for prefix, directory in value.items():
        if not prefix:
            raise DeclarationError("declaration: 'aliases' prefixes must be non-empty")
        aliases[prefix] = _directory(repo, directory, f"aliases[{prefix!r}]")
    return aliases


def _import_roots(repo: Path, raw: dict) -> list[str]:
    if "import_roots" not in raw:
        return list(DEFAULT_IMPORT_ROOTS)
    value = raw["import_roots"]
    if not isinstance(value, list):
        raise DeclarationError("declaration: 'import_roots' must be a list")
    return [
        _directory(repo, root, f"import_roots[{index}]")
        for index, root in enumerate(value)
    ]


def _list(raw: dict, key: str, where: str, *, required: bool = False) -> list:
    if key not in raw and not required:
        return []
    value = raw.get(key)
    if not isinstance(value, list):
        raise DeclarationError(f"{where}: {key!r} must be a list")
    return value


def _text(raw: object, key: str, where: str) -> str:
    if not isinstance(raw, dict):
        raise DeclarationError(f"{where} must be an object")
    value = raw.get(key)
    if not isinstance(value, str) or not value:
        raise DeclarationError(f"{where}: {key!r} must be a non-empty string")
    return value


def _path(repo: Path, raw: object, key: str, where: str, kind: str) -> str:
    value = _text(raw, key, where)
    posix = PurePosixPath(value)
    if "\\" in value or posix.is_absolute() or ".." in posix.parts:
        raise DeclarationError(
            f"{where}: {key!r} must be a repository-relative POSIX path, got {value!r}"
        )
    target = repo / value
    exists = {
        "file": target.is_file(),
        "dir": target.is_dir(),
        "any": target.exists(),
    }[kind]
    if not exists:
        noun = {"file": "file", "dir": "directory", "any": "path"}[kind]
        raise DeclarationError(f"{where}: {key!r} {noun} {value} does not exist")
    return str(posix)


def _unique(names: list[str], noun: str) -> None:
    seen: set[str] = set()
    for name in names:
        if name in seen:
            raise DeclarationError(f"duplicate {noun} name {name!r}")
        seen.add(name)


def _module(repo: Path, index: int, item: object) -> Module:
    where = f"modules[{index}]"
    name = _text(item, "name", where)
    where = f"module {name!r}"
    directory = _path(repo, item, "dir", where, "dir")
    entry = _path(repo, item, "entry", where, "file")
    if not _within(PurePosixPath(entry), directory):
        raise DeclarationError(f"{where}: entry {entry} lies outside dir {directory}")
    return Module(name=name, dir=directory, entry=entry)


def _port(repo: Path, index: int, item: object) -> Port:
    where = f"ports[{index}]"
    name = _text(item, "name", where)
    where = f"port {name!r}"
    port = _path(repo, item, "port", where, "file")
    contract = _path(repo, item, "contract", where, "file")
    raw_adapters = _list(item, "adapters", where, required=True)
    if not raw_adapters:
        raise DeclarationError(f"{where}: 'adapters' must name at least one adapter")
    adapters = []
    for position, adapter in enumerate(raw_adapters):
        adapter_where = f"{where} adapters[{position}]"
        adapter_name = _text(adapter, "name", adapter_where)
        in_memory = adapter.get("in_memory", False)
        if not isinstance(in_memory, bool):
            raise DeclarationError(f"{adapter_where}: 'in_memory' must be true or false")
        adapters.append(
            Adapter(
                name=adapter_name,
                path=_path(repo, adapter, "path", adapter_where, "any"),
                in_memory=in_memory,
            )
        )
    _unique([a.name for a in adapters], f"{where} adapter")
    return Port(name=name, port=port, contract=contract, adapters=tuple(adapters))


def is_test_file(relative: PurePosixPath) -> bool:
    name = relative.name
    if relative.suffix not in SOURCE_EXTENSIONS:
        return False
    if ".test." in name or ".spec." in name:
        return True
    if relative.suffix == ".py" and (name.startswith("test_") or name.endswith("_test.py")):
        return True
    return any(part in TEST_DIRS for part in relative.parts[:-1])


def find_test_files(repo: Path) -> list[PurePosixPath]:
    found: list[PurePosixPath] = []
    for current, dirs, files in os.walk(repo):
        dirs[:] = sorted(d for d in dirs if d not in SKIPPED_DIRS)
        for name in sorted(files):
            relative = PurePosixPath((Path(current) / name).relative_to(repo).as_posix())
            if is_test_file(relative):
                found.append(relative)
    return found


def _inside_repo(repo: Path, candidate: Path) -> PurePosixPath | None:
    try:
        return PurePosixPath(candidate.relative_to(repo).as_posix())
    except ValueError:
        return None


def _resolve_ts_base(repo: Path, base: Path) -> PurePosixPath | None:
    candidates = [base]
    candidates += [base.with_name(base.name + ext) for ext in TS_EXTENSIONS]
    if base.suffix in (".js", ".jsx", ".mjs", ".cjs"):
        stem = base.with_suffix("")
        candidates += [stem.with_name(stem.name + ext) for ext in TS_EXTENSIONS]
    candidates += [base / f"index{ext}" for ext in TS_EXTENSIONS]
    for candidate in candidates:
        if candidate.is_file():
            return _inside_repo(repo, candidate)
    return None


def _is_relative_specifier(specifier: str) -> bool:
    return specifier.startswith(("./", "../")) or specifier in (".", "..")


def _alias_target(aliases: dict[str, str], specifier: str) -> str | None:
    matches = [prefix for prefix in aliases if specifier.startswith(prefix)]
    if not matches:
        return None
    prefix = max(matches, key=len)
    rest = specifier[len(prefix) :].lstrip("/")
    return str(PurePosixPath(aliases[prefix] or ".", rest))


def resolve_ts(
    repo: Path, test: PurePosixPath, specifier: str, aliases: dict[str, str]
) -> tuple[PurePosixPath | None, bool]:
    """Resolve a TS/JS specifier; the flag says whether the helper could check it."""
    if _is_relative_specifier(specifier):
        base = Path(os.path.normpath(repo / test.parent / specifier))
    elif (aliased := _alias_target(aliases, specifier)) is not None:
        base = Path(os.path.normpath(repo / aliased))
    elif specifier.startswith(ALIAS_LIKE_PREFIXES):
        return None, False
    else:
        return None, True  # bare package specifier: outside the repository
    target = _resolve_ts_base(repo, base)
    return target, target is not None


def ts_specifiers(text: str) -> list[str]:
    found: list[tuple[int, str]] = []
    for pattern in (_TS_FROM, _TS_SIDE_EFFECT, _TS_CALL):
        found += [(match.start(), match.group(2)) for match in pattern.finditer(text)]
    return [specifier for _, specifier in sorted(found)]


def resolve_py_module(
    repo: Path, roots: list[Path], parts: list[str]
) -> PurePosixPath | None:
    for root in roots:
        base = root.joinpath(*parts)
        candidates = [base / "__init__.py"]
        if parts:
            candidates.insert(0, base.with_name(base.name + ".py"))
        for candidate in candidates:
            if candidate.is_file():
                return _inside_repo(repo, candidate)
    return None


def py_imports(
    repo: Path, test: PurePosixPath, text: str, import_roots: list[str]
) -> tuple[list[tuple[str, PurePosixPath]], list[str]]:
    try:
        tree = ast.parse(text)
    except SyntaxError as exc:
        return [], [f"unparseable: {exc.msg} (line {exc.lineno})"]
    absolute_roots = [repo / root if root else repo for root in import_roots]
    found: list[tuple[str, PurePosixPath]] = []
    unchecked: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                target = resolve_py_module(repo, absolute_roots, alias.name.split("."))
                if target is not None:
                    found.append((alias.name, target))
        elif isinstance(node, ast.ImportFrom):
            module_parts = node.module.split(".") if node.module else []
            roots = absolute_roots
            if node.level:
                anchor = (repo / test).parent
                for _ in range(node.level - 1):
                    anchor = anchor.parent
                roots = [anchor]
            source = "." * node.level + (node.module or "")
            for alias in node.names:
                # `from a import b` names submodule `a.b` when it exists, else `a`.
                target = None
                if alias.name != "*":
                    target = resolve_py_module(repo, roots, module_parts + [alias.name])
                if target is None:
                    target = resolve_py_module(repo, roots, module_parts)
                if target is not None:
                    found.append((f"from {source} import {alias.name}", target))
                elif node.level:
                    # A relative import names a repository file; an absolute one
                    # that does not resolve is taken to be a third-party package.
                    unchecked.append(source)
    return found, unchecked


def imported_files(
    repo: Path, test: PurePosixPath, declaration: Declaration
) -> tuple[list[tuple[str, PurePosixPath]], list[str]]:
    try:
        text = (repo / test).read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        return [], [f"unreadable: {exc}"]
    unchecked: list[str] = []
    if test.suffix == ".py":
        candidates, unchecked = py_imports(repo, test, text, declaration.import_roots)
    else:
        candidates = []
        for specifier in ts_specifiers(text):
            target, checked = resolve_ts(repo, test, specifier, declaration.aliases)
            if target is not None:
                candidates.append((specifier, target))
            elif not checked:
                unchecked.append(specifier)
    resolved: list[tuple[str, PurePosixPath]] = []
    for pair in candidates:
        if pair not in resolved:
            resolved.append(pair)
    return resolved, list(dict.fromkeys(unchecked))


def _within(path: PurePosixPath, directory: str) -> bool:
    return path.is_relative_to(PurePosixPath(directory))


def exception_reason(repo: Path, test: PurePosixPath) -> str | None:
    text = (repo / test).read_text(encoding="utf-8", errors="replace")
    match = _EXCEPTION_REASON.search(text)
    if match is None:
        return None
    reason = re.sub(r"\s*(?:\*/|-->)\s*$", "", match.group(1)).strip()
    return reason or None


def module_report(
    repo: Path, module: Module, imports: dict[PurePosixPath, list]
) -> dict:
    findings: list[dict] = []
    exceptions: list[dict] = []
    entry = PurePosixPath(module.entry)
    for test, targets in imports.items():
        inside = _within(test, module.dir)
        for specifier, target in targets:
            if target == entry or not _within(target, module.dir):
                continue
            record = {"test": str(test), "import": specifier, "target": str(target)}
            if not inside:
                findings.append({"kind": "boundary-bypass", **record})
                continue
            reason = exception_reason(repo, test)
            if reason is None:
                findings.append({"kind": "internal-without-reason", **record})
            else:
                exceptions.append({**record, "reason": reason})
    return {
        "name": module.name,
        "dir": module.dir,
        "entry": module.entry,
        "findings": findings,
        "stated_exceptions": exceptions,
    }


def port_report(port: Port, imports: dict[PurePosixPath, list]) -> dict:
    """Contract runs, ambiguous runs and bypasses of one declared port.

    A test file is a contract run for an adapter when it is or imports the
    contract suite and imports that adapter and no other adapter of the port.
    Importing the contract with several adapters is ambiguous and covers none.
    A test importing a real (not in-memory) adapter is a port bypass unless it
    is the contract suite, a contract run for that adapter, or lies inside the
    adapter's own path.
    """
    contract = PurePosixPath(port.contract)
    runs: dict[str, list[str]] = {adapter.name: [] for adapter in port.adapters}
    findings: list[dict] = []
    for test, targets in imports.items():
        files = {target for _, target in targets}
        hit = [a for a in port.adapters if any(_within(f, a.path) for f in files)]
        is_contract = test == contract
        if is_contract or contract in files:
            if len(hit) == 1:
                runs[hit[0].name].append(str(test))
            elif len(hit) > 1:
                findings.append(
                    {
                        "kind": "ambiguous-contract-run",
                        "test": str(test),
                        "adapters": [a.name for a in hit],
                    }
                )
        for adapter in hit:
            if adapter.in_memory or is_contract or _within(test, adapter.path):
                continue
            if str(test) in runs[adapter.name]:
                continue
            for specifier, target in targets:
                if _within(target, adapter.path):
                    findings.append(
                        {
                            "kind": "port-bypass",
                            "test": str(test),
                            "adapter": adapter.name,
                            "import": specifier,
                            "target": str(target),
                        }
                    )
    adapters: list[dict] = []
    for adapter in port.adapters:
        adapters.append(
            {
                "name": adapter.name,
                "path": adapter.path,
                "in_memory": adapter.in_memory,
                "contract_runs": runs[adapter.name],
            }
        )
        if not runs[adapter.name]:
            findings.append(
                {
                    "kind": "adapter-without-contract-run",
                    "adapter": adapter.name,
                    "path": adapter.path,
                }
            )
    if not any(adapter.in_memory for adapter in port.adapters):
        findings.append({"kind": "port-without-in-memory-adapter", "adapter": None})
    return {
        "name": port.name,
        "port": port.port,
        "contract": port.contract,
        "adapters": adapters,
        "findings": findings,
    }


def build_report(repo: Path, declaration_path: Path | None) -> dict:
    report: dict = {
        "schema": SCHEMA,
        "repo": str(repo),
        "declaration": None,
        "declared": False,
        "modules": [],
        "ports": [],
        "finding_count": 0,
        "unchecked": [],
        "unchecked_count": 0,
    }
    if declaration_path is None:
        return report
    if not declaration_path.is_absolute():
        declaration_path = repo / declaration_path
    declaration = load_declaration(repo, declaration_path)
    imports: dict[PurePosixPath, list] = {}
    scanned = find_test_files(repo)
    # A declared contract suite is scanned whatever its name, so the adapters it
    # registers itself against count as contract runs.
    for port in declaration.ports:
        contract = PurePosixPath(port.contract)
        if contract not in scanned:
            scanned.append(contract)
    for test in scanned:
        imports[test], unchecked = imported_files(repo, test, declaration)
        if unchecked:
            report["unchecked"].append({"test": str(test), "specifiers": unchecked})
    report["declaration"] = str(declaration_path)
    report["declared"] = True
    report["modules"] = [module_report(repo, m, imports) for m in declaration.modules]
    report["ports"] = [port_report(p, imports) for p in declaration.ports]
    report["finding_count"] = sum(
        len(unit["findings"]) for unit in report["modules"] + report["ports"]
    )
    report["unchecked_count"] = sum(
        len(entry["specifiers"]) for entry in report["unchecked"]
    )
    return report


def render_text(report: dict) -> str:
    if not report["declared"]:
        return "no declared test units: the audit runs unchanged"
    lines = [f"declared test units from {report['declaration']}"]
    for module in report["modules"]:
        lines.append(f"module {module['name']} (entry {module['entry']})")
        for finding in module["findings"]:
            lines.append(
                f"  {finding['kind']}: {finding['test']} imports {finding['target']}"
            )
        for exception in module["stated_exceptions"]:
            lines.append(
                f"  stated-exception: {exception['test']} imports {exception['target']}"
                f" ({exception['reason']})"
            )
        if not module["findings"] and not module["stated_exceptions"]:
            lines.append("  no findings")
    for port in report["ports"]:
        lines.append(f"port {port['name']} (contract {port['contract']})")
        for adapter in port["adapters"]:
            kind = "in-memory adapter" if adapter["in_memory"] else "adapter"
            runs = ", ".join(adapter["contract_runs"]) or "none"
            lines.append(f"  {kind} {adapter['name']}: contract runs {runs}")
        for finding in port["findings"]:
            if finding["kind"] == "port-bypass":
                subject = (
                    f"{finding['test']} imports {finding['target']}"
                    f" (adapter {finding['adapter']})"
                )
            elif finding["kind"] == "ambiguous-contract-run":
                subject = f"{finding['test']} imports adapters " + ", ".join(
                    finding["adapters"]
                )
            else:
                subject = finding["adapter"] or "no adapter declares in_memory: true"
            lines.append(f"  {finding['kind']}: {subject}")
    for entry in report["unchecked"]:
        lines.append(f"unchecked: {entry['test']}: {', '.join(entry['specifiers'])}")
    count = report["finding_count"]
    lines.append(f"{count} finding{'' if count == 1 else 's'}")
    unchecked = report["unchecked_count"]
    lines.append(f"{unchecked} unchecked specifier{'' if unchecked == 1 else 's'}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="boundary_report.py")
    parser.add_argument("--repo", required=True, type=Path)
    parser.add_argument("--declaration", type=Path)
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args(argv)

    repo = args.repo.resolve()
    try:
        report = build_report(repo, args.declaration)
    except DeclarationError as exc:
        print(f"boundary_report: invalid declaration: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(report, indent=2) if args.as_json else render_text(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())

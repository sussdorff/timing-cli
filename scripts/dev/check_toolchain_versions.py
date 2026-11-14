#!/usr/bin/env python3
"""Check that a repository builds with the latest released toolchains.

Rules (see the ``toolchains`` standard):

1. Bun: the latest release.
2. Node: reported as a Bun migration candidate, never failed.
3. Python: at least 3.14, and the latest patch of the minor line in use;
   uv: the latest release.
4. CI setup actions (setup-bun, setup-python, setup-uv, setup-node) request
   the latest tool version.
5. Stateful service images: the latest release within their own major line.

Each latest release is looked up at most once per run and only when an
explicit declaration needs it. Standard library only; runs with any python3.

Exit codes: 0 nothing outdated, 1 at least one outdated or unreadable
declaration, 2 typed lookup error (``<tool>_lookup_failed``) or usage error.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Callable, Dict, List, NamedTuple, Optional, Tuple

TIMEOUT_SECONDS = 10.0
PYTHON_MINIMUM = (3, 14)
MAX_TAG_PAGES = 10

NPM_BUN_URL = "https://registry.npmjs.org/bun/latest"
GITHUB_BUN_URL = "https://api.github.com/repos/oven-sh/bun/releases/latest"
PYPI_UV_URL = "https://pypi.org/pypi/uv/json"
GITHUB_UV_URL = "https://api.github.com/repos/astral-sh/uv/releases/latest"
EOL_PYTHON_URL = "https://endoflife.date/api/python/{minor}.json"
EOL_V1_PYTHON_URL = "https://endoflife.date/api/v1/products/python/releases/{minor}"
HUB_URL = "https://hub.docker.com/v2/repositories/"
QUAY_URL = "https://quay.io/api/v1/repository/"

SKIP_DIRS = {"node_modules", ".git", ".agents", ".claude", ".codex", "dist", "vendor"}
WORKFLOW_DIRS = (".github/workflows", ".forgejo/workflows", ".gitea/workflows")

OK = "ok"
OUTDATED = "outdated"
IMPLICIT = "implicit"
ERROR = "error"
NODE_USAGE = "node_usage"

Version = Tuple[int, int, int, Tuple[str, ...]]


class Verdict(NamedTuple):
    status: str
    detail: str
    reason: str = ""


class UsageError(Exception):
    """Invalid command line."""


class LookupFailed(Exception):
    """A remote lookup the run needs could not be completed.

    ``unreleased`` is true when every source answered and none names a
    release: each returned 404 or a payload without a non-prerelease version.
    A transport failure, timeout or other HTTP error leaves it false.
    """

    def __init__(self, code: str, message: str, unreleased: bool = False) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.unreleased = unreleased


class RangeError(ValueError):
    """Unparseable version range or specifier."""


class TomlError(ValueError):
    """A TOML file that is not valid TOML."""

    def __init__(self, message: str, line: int) -> None:
        super().__init__(message)
        self.line = line


def _origin(url: str) -> Tuple[str, str]:
    parts = urllib.parse.urlsplit(url)
    return parts.scheme.lower(), parts.netloc.lower()


class RedirectHandler(urllib.request.HTTPRedirectHandler):
    """Follow redirects, but send credentials only to the origin they were meant for.

    The stdlib handler copies every request header to the redirect target,
    whatever its host. A redirect that leaves the request's scheme and host
    (including the port) drops the Authorization header, so ``GITHUB_TOKEN``
    never reaches a host other than ``api.github.com``.
    """

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        new = super().redirect_request(req, fp, code, msg, headers, newurl)
        if new is not None and _origin(newurl) != _origin(req.full_url):
            for name in [k for k, _ in new.header_items() if k.lower() == "authorization"]:
                new.remove_header(name)
        return new


def fetch_json(url: str, timeout: float, headers: Optional[Dict[str, str]] = None) -> Any:
    """Fetch and decode one JSON document (the network boundary)."""
    request_headers = {"Accept": "application/json", "User-Agent": "check-toolchain-versions"}
    request_headers.update(headers or {})
    request = urllib.request.Request(url, headers=request_headers)
    opener = urllib.request.build_opener(RedirectHandler)
    with opener.open(request, timeout=timeout) as response:  # noqa: S310 - fixed https URLs
        return json.loads(response.read().decode("utf-8"))


# --------------------------------------------------------------------------
# Versions
# --------------------------------------------------------------------------

_SPEC_RE = re.compile(
    r"^v?(\d+)(?:\.(\d+|[xX*]))?(?:\.(\d+|[xX*]))?(?:-([0-9A-Za-z.-]+))?(?:\+[0-9A-Za-z.-]+)?$"
)

Spec = Tuple[Tuple[int, ...], Tuple[str, ...]]


def parse_spec(text: str) -> Optional[Spec]:
    """Parse a version or partial version into (components, prerelease).

    Components stop at the first missing or wildcard part: ``1.3`` and
    ``1.3.x`` both give ``(1, 3)``.
    """
    match = _SPEC_RE.match(text.strip())
    if not match:
        return None
    parts: List[int] = []
    for group in match.group(1, 2, 3):
        if group is None or group in ("x", "X", "*"):
            break
        parts.append(int(group))
    pre = tuple(match.group(4).split(".")) if match.group(4) else ()
    return tuple(parts), pre


def parse_release(text: str) -> Optional[Version]:
    """Parse a full x.y.z version; None if partial or unparseable."""
    spec = parse_spec(text)
    if spec is None or len(spec[0]) != 3:
        return None
    (major, minor, patch), pre = spec
    return (major, minor, patch, pre)


def _pre_key(pre: Tuple[str, ...]) -> Tuple[Any, ...]:
    # A release sorts after every prerelease of the same version.
    if not pre:
        return (1,)
    return (0,) + tuple((0, int(p), "") if p.isdigit() else (1, 0, p) for p in pre)


def version_key(version: Version) -> Tuple[Any, ...]:
    return (version[0], version[1], version[2], _pre_key(version[3]))


def format_version(version: Version) -> str:
    text = f"{version[0]}.{version[1]}.{version[2]}"
    return text + ("-" + ".".join(version[3]) if version[3] else "")


def spec_is_older(spec: Spec, latest: Version) -> bool:
    """Whether a (partial) version spec cannot reach the latest release.

    The spec is compared at its own precision: ``1`` is older only when the
    latest major differs, ``1.3`` only when the latest is outside 1.3.x.
    """
    components, pre = spec
    if not components:
        return False
    if len(components) == 3:
        return version_key((components[0], components[1], components[2], pre)) < version_key(latest)
    return components < latest[: len(components)]


def _is_expression(text: str) -> bool:
    return "${{" in text


# --------------------------------------------------------------------------
# npm semver ranges (engines.bun)
# --------------------------------------------------------------------------

_COMPARATOR_RE = re.compile(r"^(>=|<=|>|<|=|\^|~>?|)\s*(.+)$")
Predicate = Callable[[Tuple[Any, ...]], bool]


def _bound(components: Tuple[int, ...]) -> Tuple[Any, ...]:
    padded = tuple(components) + (0,) * (3 - len(components))
    return (padded[0], padded[1], padded[2], (0,))  # below every prerelease of that version


def _next_bound(components: Tuple[int, ...]) -> Tuple[Any, ...]:
    """Lowest version above every version matching the partial components."""
    parts = list(components)
    parts[-1] += 1
    return _bound(tuple(parts))


def _comparator(op: str, text: str) -> List[Predicate]:
    if text in ("*", "x", "X", ""):
        return []
    spec = parse_spec(text)
    if spec is None:
        raise RangeError(f"unparseable version {text!r}")
    comps, pre = spec
    if not comps:
        return []
    full = len(comps) == 3
    exact = version_key((comps[0], comps[1], comps[2], pre)) if full else None
    if op in ("", "="):
        if full:
            return [lambda v, e=exact: v == e]
        lo, hi = _bound(comps), _next_bound(comps)
        return [lambda v, lo=lo: v >= lo, lambda v, hi=hi: v < hi]
    if op == ">=":
        lo = exact if full else _bound(comps)
        return [lambda v, lo=lo: v >= lo]
    if op == ">":
        if full:
            return [lambda v, lo=exact: v > lo]
        return [lambda v, lo=_next_bound(comps): v >= lo]
    if op == "<":
        hi = exact if full else _bound(comps)
        return [lambda v, hi=hi: v < hi]
    if op == "<=":
        if full:
            return [lambda v, hi=exact: v <= hi]
        return [lambda v, hi=_next_bound(comps): v < hi]
    lo = exact if full else _bound(comps)
    if op.startswith("~"):
        hi = _next_bound(comps[:2] if len(comps) >= 2 else comps)
    else:  # caret: the first non-zero component stays fixed
        fixed = 0
        while fixed < len(comps) - 1 and comps[fixed] == 0:
            fixed += 1
        hi = _next_bound(comps[: fixed + 1])
    return [lambda v, lo=lo: v >= lo, lambda v, hi=hi: v < hi]


def range_satisfied(range_text: str, version: Version) -> bool:
    """Evaluate an npm semver range (common subset) against one version."""
    key = version_key(version)
    for alternative in range_text.split("||"):
        alternative = alternative.strip()
        hyphen = re.match(r"^(\S+)\s+-\s+(\S+)$", alternative)
        if hyphen:
            # "<=" on a partial upper bound already means "below the next partial version".
            predicates = _comparator(">=", hyphen.group(1)) + _comparator("<=", hyphen.group(2))
        else:
            predicates = []
            tokens = re.sub(r"(>=|<=|>|<|=|\^|~>?)\s+", r"\1", alternative).split()
            for token in tokens:
                match = _COMPARATOR_RE.match(token)
                if not match:
                    raise RangeError(f"unparseable comparator {token!r}")
                predicates += _comparator(match.group(1), match.group(2))
        if all(predicate(key) for predicate in predicates):
            return True
    return False


def range_is_any(range_text: str) -> bool:
    return all(part.strip() in ("", "*", "x", "X") for part in range_text.split("||"))


# --------------------------------------------------------------------------
# PEP 440 specifiers (requires-python, uv required-version)
# --------------------------------------------------------------------------

# Pre, post and dev suffixes are accepted and ignored for ordering: ">=3.14.0rc1" acts as ">=3.14.0".
_PEP_CLAUSE_RE = re.compile(
    r"^(~=|===|==|!=|<=|>=|<|>)?\s*v?(\d+(?:\.\d+)*)(?:(?:a|b|rc)\d+)?(?:\.post\d+)?(?:\.dev\d+)?(\.\*)?$"
)


def _pep_clauses(text: str) -> List[Tuple[str, Tuple[int, ...], bool]]:
    clauses = []
    for part in text.split(","):
        part = part.strip()
        if not part:
            continue
        match = _PEP_CLAUSE_RE.match(part)
        if not match:
            raise RangeError(f"unparseable specifier {part!r}")
        op = match.group(1) or "=="
        comps = tuple(int(x) for x in match.group(2).split("."))
        if op == "~=" and len(comps) < 2:
            raise RangeError(f"~= needs at least two components: {part!r}")
        clauses.append((op, comps, bool(match.group(3))))
    return clauses


def _pad(a: Tuple[int, ...], size: int) -> Tuple[int, ...]:
    return tuple(a) + (0,) * (size - len(a))


def _cmp(a: Tuple[int, ...], b: Tuple[int, ...]) -> int:
    size = max(len(a), len(b))
    pa, pb = _pad(a, size), _pad(b, size)
    return (pa > pb) - (pa < pb)


def pep440_admits(text: str, version: Tuple[int, ...]) -> bool:
    for op, comps, wildcard in _pep_clauses(text):
        if wildcard and op in ("==", "!="):
            match = _pad(version, len(comps))[: len(comps)] == comps
            if match != (op == "=="):
                return False
            continue
        order = _cmp(version, comps)
        admitted = {
            "==": order == 0,
            "===": order == 0,
            "!=": order != 0,
            ">=": order >= 0,
            "<=": order <= 0,
            ">": order > 0,
            "<": order < 0,
            "~=": order >= 0 and _pad(version, len(comps))[: len(comps) - 1] == comps[:-1],
        }[op]
        if not admitted:
            return False
    return True


def pep440_lower_bound(text: str) -> Optional[Tuple[int, ...]]:
    """Lowest version a specifier admits, or None when it has no lower bound."""
    lowers = [comps for op, comps, _ in _pep_clauses(text) if op in (">=", ">", "~=", "==", "===")]
    if not lowers:
        return None
    size = max(len(c) for c in lowers)
    return max(_pad(c, size) for c in lowers)


# --------------------------------------------------------------------------
# Images
# --------------------------------------------------------------------------


class ImageRef(NamedTuple):
    registry: str
    repo: str  # registry path, official Docker Hub images under library/
    name: str  # display name: postgres, oven/bun, quay.io/keycloak/keycloak
    tag: str
    digest: Optional[str]


def parse_image(ref: str) -> Optional[ImageRef]:
    ref = ref.strip().strip("'\"")
    if not ref or ref.startswith("#"):
        return None
    digest: Optional[str] = None
    if "@" in ref:
        ref, digest = ref.split("@", 1)
    first, _, rest = ref.partition("/")
    if rest and ("." in first or ":" in first or first == "localhost"):
        registry, path = first, rest
    else:
        registry, path = "docker.io", ref
    if registry in ("index.docker.io", "registry-1.docker.io"):
        registry = "docker.io"
    path, _, tag = path.partition(":")
    if registry == "docker.io":
        repo = path if "/" in path else f"library/{path}"
        name = repo[len("library/") :] if repo.startswith("library/") else repo
    else:
        repo = path
        name = f"{registry}/{path}"
    return ImageRef(registry, repo, name, tag, digest)


# A version part may carry a Python prerelease (3.14.0rc1) or the free-threaded marker (3.14t).
_TAG_VERSION_RE = re.compile(r"^(\d+(?:\.\d+){0,2}(?:(?:a|b|rc)\d+)?t?)(?:-(.+))?$")


def split_tag(tag: str) -> Tuple[Optional[str], Optional[str]]:
    """Split a tag into (version part, variant); version part None when floating."""
    match = _TAG_VERSION_RE.match(tag)
    if match:
        return match.group(1), match.group(2)
    if tag in ("", "latest"):
        return None, None
    if tag.startswith("latest-"):
        return None, tag[len("latest-") :]
    return None, tag


def variant_family(variant: Optional[str]) -> str:
    """Variant without its trailing OS release: alpine3.22 -> alpine."""
    return re.sub(r"[\d.]+$", "", variant or "")


class Scheme(NamedTuple):
    pattern: "re.Pattern[str]"  # named groups v1..vN for the version, ``variant`` for the suffix
    components: int  # number of version groups
    line: int  # leading components that form the major line
    line_join: str  # joins the line components in a tag: "16", "16-3"


# An optional numeric build suffix (keycloak:26.7.5-0) is part of the release, not a variant.
SEMVER = Scheme(
    re.compile(r"^(?P<v1>\d+)(?:\.(?P<v2>\d+))?(?:\.(?P<v3>\d+))?(?:-\d+)?(?:-(?P<variant>[A-Za-z][\w.-]*))?$"),
    3, 1, ".",
)
# Aidbox: CalVer YYMM release line, YYMM.N patch releases; -rc and channels are not releases.
CALVER = Scheme(re.compile(r"^(?P<v1>\d{4})(?:\.(?P<v2>\d+))?$"), 2, 1, ".")
# PostGIS: <postgres major>-<postgis major>.<postgis minor>[.<patch>][-variant]; the line is
# the Postgres major plus the PostGIS major, so neither major is ever demanded.
POSTGIS = Scheme(
    re.compile(
        r"^(?P<v1>\d+)-(?P<v2>\d+)(?:\.(?P<v3>\d+))?(?:\.(?P<v4>\d+))?(?:-(?P<variant>[A-Za-z][\w.-]*))?$"
    ),
    4, 2, "-",
)


class Stateful(NamedTuple):
    registry: str
    repo: str
    scheme: Scheme


STATEFUL: Dict[str, Stateful] = {
    "postgres": Stateful("docker.io", "library/postgres", SEMVER),
    "postgis/postgis": Stateful("docker.io", "postgis/postgis", POSTGIS),
    "healthsamurai/aidboxone": Stateful("docker.io", "healthsamurai/aidboxone", CALVER),
    "healthsamurai/aidboxdb": Stateful("docker.io", "healthsamurai/aidboxdb", SEMVER),
    "quay.io/keycloak/keycloak": Stateful("quay.io", "keycloak/keycloak", SEMVER),
    "keycloak/keycloak": Stateful("docker.io", "keycloak/keycloak", SEMVER),
    "redis": Stateful("docker.io", "library/redis", SEMVER),
    "valkey/valkey": Stateful("docker.io", "valkey/valkey", SEMVER),
    "mariadb": Stateful("docker.io", "library/mariadb", SEMVER),
    "mysql": Stateful("docker.io", "library/mysql", SEMVER),
    "mongo": Stateful("docker.io", "library/mongo", SEMVER),
}


def parse_stateful_tag(scheme: Scheme, tag: str) -> Optional[Tuple[Tuple[int, ...], str]]:
    """(version components, variant family) of a release tag, None when floating."""
    match = scheme.pattern.match(tag)
    if not match:
        return None
    groups = match.groupdict()
    comps: List[int] = []
    for index in range(1, scheme.components + 1):
        group = groups.get(f"v{index}")
        if group is None:
            break
        comps.append(int(group))
    return tuple(comps), variant_family(groups.get("variant"))


def line_text(scheme: Scheme, line: Tuple[int, ...]) -> str:
    return scheme.line_join.join(str(c) for c in line)


# --------------------------------------------------------------------------
# Lookups
# --------------------------------------------------------------------------


Candidates = List[Tuple[Tuple[int, ...], str]]


class Lookups:
    """Lazy remote lookups, each made at most once per run."""

    def __init__(self, overrides: Dict[str, str]) -> None:
        self.overrides = overrides
        self.resolved: Dict[str, str] = {}
        self._cache: Dict[str, Any] = {}

    def _once(self, key: str, compute: Callable[[], Any]) -> Any:
        if key not in self._cache:
            try:
                self._cache[key] = compute()
            except LookupFailed as exc:
                self._cache[key] = exc
        result = self._cache[key]
        if isinstance(result, LookupFailed):
            raise result
        return result

    def _release(self, key: str, compute: Callable[[], Version]) -> Version:
        def resolve() -> Version:
            if key in self.overrides:
                version = parse_release(self.overrides[key])
                assert version is not None  # validated by main()
            else:
                version = compute()
            self.resolved[key] = format_version(version)
            return version

        return self._once(key, resolve)

    def bun(self) -> Version:
        return self._release(
            "bun",
            lambda: _first_release(
                "bun_lookup_failed",
                [
                    (NPM_BUN_URL, None, lambda p: p.get("version")),
                    (GITHUB_BUN_URL, _github_headers(), _github_tag("bun-v")),
                ],
            ),
        )

    def uv(self) -> Version:
        return self._release(
            "uv",
            lambda: _first_release(
                "uv_lookup_failed",
                [
                    (PYPI_UV_URL, None, lambda p: (p.get("info") or {}).get("version")),
                    (GITHUB_UV_URL, _github_headers(), _github_tag("")),
                ],
            ),
        )

    def python(self, minor: Tuple[int, ...]) -> Version:
        line = f"{minor[0]}.{minor[1]}"

        def compute() -> Version:
            version = _first_release(
                "python_lookup_failed",
                [
                    (EOL_PYTHON_URL.format(minor=line), None, lambda p: p.get("latest")),
                    (
                        EOL_V1_PYTHON_URL.format(minor=line),
                        None,
                        lambda p: ((p.get("result") or {}).get("latest") or {}).get("name"),
                    ),
                ],
            )
            if version[:2] != tuple(minor[:2]):
                raise LookupFailed("python_lookup_failed", f"latest {format_version(version)} is not in {line}")
            return version

        return self._release(f"python{line}", compute)

    def line_candidates(self, name: str, image: Stateful, line: Tuple[int, ...], family: str) -> Candidates:
        """Release tags of one image line and variant family."""
        text = line_text(image.scheme, line)
        key = f"{name}:{text}" + (f"-{family}" if family else "")

        def compute() -> Candidates:
            if key in self.overrides:
                parsed = parse_stateful_tag(image.scheme, self.overrides[key])
                assert parsed is not None  # validated by main()
                found = [(parsed[0], self.overrides[key])]
            else:
                found = []
                for tag in _list_tags(image, f"{text}."):
                    parsed = parse_stateful_tag(image.scheme, tag)
                    if parsed and parsed[0][: len(line)] == line and parsed[1] == family:
                        found.append((parsed[0], tag))
                if not found:
                    raise LookupFailed("image_lookup_failed", f"no release tags found for {key}")
            self.resolved[key] = max(found)[1]
            return found

        return self._once(key, compute)

    def tag_digests(self, image: ImageRef) -> Optional[set]:
        """Current digests of an image tag; None when the registry is not supported."""
        if image.registry not in ("docker.io", "quay.io"):
            return None
        tag = image.tag or "latest"
        key = f"digest:{image.registry}/{image.repo}:{tag}"

        def compute() -> set:
            try:
                if image.registry == "docker.io":
                    payload = fetch_json(f"{HUB_URL}{image.repo}/tags/{tag}", TIMEOUT_SECONDS)
                    found = {payload.get("digest")} | {
                        item.get("digest") for item in payload.get("images") or [] if isinstance(item, dict)
                    }
                else:
                    query = urllib.parse.urlencode({"specificTag": tag, "onlyActiveTags": "true"})
                    payload = fetch_json(f"{QUAY_URL}{image.repo}/tag/?{query}", TIMEOUT_SECONDS)
                    found = {item.get("manifest_digest") for item in payload.get("tags") or []}
                found.discard(None)
                if not found:
                    raise ValueError("no digest in registry response")
                return found
            except Exception as exc:  # noqa: BLE001 - every failure is the typed error
                raise LookupFailed("digest_lookup_failed", f"{image.name}:{tag}: {exc}") from exc

        return self._once(key, compute)


def _github_headers() -> Dict[str, str]:
    headers = {"Accept": "application/vnd.github+json"}
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _github_tag(prefix: str) -> Callable[[Any], Optional[str]]:
    def extract(payload: Any) -> Optional[str]:
        if payload.get("prerelease"):
            return None
        tag = str(payload.get("tag_name", ""))
        return tag[len(prefix) :] if prefix and tag.startswith(prefix) else tag

    return extract


def _first_release(code: str, sources: List[Tuple[str, Optional[Dict[str, str]], Callable[[Any], Any]]]) -> Version:
    problems: List[str] = []
    unreleased = True
    for url, headers, extract in sources:
        try:
            payload = fetch_json(url, TIMEOUT_SECONDS, headers) if headers else fetch_json(url, TIMEOUT_SECONDS)
            text = extract(payload)
            version = parse_release(str(text)) if text is not None else None
            if version is not None and not version[3]:
                return version
            problems.append(f"{url}: no release version ({text!r})")
        except urllib.error.HTTPError as exc:
            unreleased = unreleased and exc.code == 404
            problems.append(f"{url}: {exc}")
        except Exception as exc:  # noqa: BLE001 - every transport failure falls back
            unreleased = False
            problems.append(f"{url}: {exc}")
    raise LookupFailed(code, "; ".join(problems), unreleased=bool(sources) and unreleased)


def _list_tags(image: Stateful, prefix: str) -> List[str]:
    """Tag names starting with prefix, bounded to MAX_TAG_PAGES pages."""
    names: List[str] = []
    complete = False
    try:
        if image.registry == "docker.io":
            url: Optional[str] = f"{HUB_URL}{image.repo}/tags?page_size=100&name={prefix}"
            pages = 0
            while url and pages < MAX_TAG_PAGES:
                payload = fetch_json(url, TIMEOUT_SECONDS)
                names += [item.get("name", "") for item in payload.get("results") or []]
                url = payload.get("next")
                pages += 1
            complete = not url
        else:
            for page in range(1, MAX_TAG_PAGES + 1):
                url = (
                    f"{QUAY_URL}{image.repo}/tag/?onlyActiveTags=true&limit=100"
                    f"&filter_tag_name=like:{prefix}&page={page}"
                )
                payload = fetch_json(url, TIMEOUT_SECONDS)
                names += [item.get("name", "") for item in payload.get("tags") or []]
                if not payload.get("has_additional"):
                    complete = True
                    break
    except Exception as exc:  # noqa: BLE001 - every failure is the typed error
        raise LookupFailed("image_lookup_failed", f"{image.registry}/{image.repo} tags {prefix}*: {exc}") from exc
    if not complete:
        # An incomplete listing may miss the latest release: never judge from it.
        raise LookupFailed(
            "image_lookup_failed",
            f"{image.registry}/{image.repo} tags {prefix}*: listing exceeds {MAX_TAG_PAGES} pages",
        )
    return [n for n in names if n.startswith(prefix)]


# --------------------------------------------------------------------------
# Verdicts
# --------------------------------------------------------------------------

NODE_DETAIL = "Node usage: migrate to Bun, or keep Node on the latest LTS where a third-party tool requires it"


class Judge:
    """Turns one declared value into a verdict, using lookups only when needed."""

    def __init__(self, lookups: Lookups) -> None:
        self.lookups = lookups

    # -- Bun ---------------------------------------------------------------

    def bun_spec(self, text: str) -> Verdict:
        text = text.strip()
        if text.lower() in ("latest", ""):
            return Verdict(OK, "tracks the latest Bun")
        if text.lower() == "canary":
            return Verdict(OK, "canary is newer than the latest Bun release")
        if _is_expression(text):
            return Verdict(IMPLICIT, "expression not evaluated; use bun-version: latest")
        spec = parse_spec(text)
        if spec is None:
            return Verdict(ERROR, f"cannot parse Bun version {text!r}", "unparseable")
        return self._against(spec, self.lookups.bun(), "Bun", text)

    def bun_range(self, text: str) -> Verdict:
        if range_is_any(text):
            return Verdict(OK, "accepts every Bun version")
        try:
            range_satisfied(text, (0, 0, 0, ()))  # syntax check before any lookup
        except RangeError as exc:
            return Verdict(ERROR, f"cannot parse range {text!r}: {exc}", "unparseable")
        latest = self.lookups.bun()
        if range_satisfied(text, latest):
            return Verdict(OK, f"admits the latest Bun {format_version(latest)}")
        return Verdict(
            OUTDATED, f"range {text!r} excludes the latest Bun {format_version(latest)}", "range_excludes_latest"
        )

    def bun_dependency(self, text: str) -> Verdict:
        """The npm ``bun`` package in a dependency map: its range must admit the latest Bun."""
        text = text.strip()
        if text.lower() in ("latest", "canary"):
            return Verdict(OK, f"dist-tag {text} follows the release")
        if re.match(r"^(?:npm|file|link|workspace|portal|git(?:\+\w+)?|github|https?):", text):
            return Verdict(IMPLICIT, f"{text!r} is not a version range")
        return self.bun_range(text)

    # -- uv ----------------------------------------------------------------

    def uv_spec(self, text: str) -> Verdict:
        text = text.strip()
        if text.lower() in ("latest", ""):
            return Verdict(OK, "tracks the latest uv")
        if _is_expression(text):
            return Verdict(IMPLICIT, "expression not evaluated; use version: latest")
        spec = parse_spec(text)
        if spec is None:
            if re.search(r"[<>=~!,]", text):  # setup-uv accepts PEP 440 specifiers
                return self.uv_required(text)
            return Verdict(ERROR, f"cannot parse uv version {text!r}", "unparseable")
        return self._against(spec, self.lookups.uv(), "uv", text)

    def uv_required(self, text: str) -> Verdict:
        try:
            if not _pep_clauses(text):
                return Verdict(OK, "accepts every uv version")
        except RangeError as exc:
            return Verdict(ERROR, f"cannot parse {text!r}: {exc}", "unparseable")
        latest = self.lookups.uv()
        if pep440_admits(text, latest[:3]):
            return Verdict(OK, f"admits the latest uv {format_version(latest)}")
        return Verdict(
            OUTDATED, f"{text!r} excludes the latest uv {format_version(latest)}", "range_excludes_latest"
        )

    # -- Python ------------------------------------------------------------

    def python_spec(self, text: str) -> Verdict:
        text = text.strip()
        if text.lower() in ("latest", ""):
            return Verdict(OK, "tracks the latest Python")
        if _is_expression(text):
            return Verdict(IMPLICIT, "expression not evaluated; name the Python minor line, e.g. '3.14'")
        if re.match(r"^(?:pypy|graalpy)", text.lower()):
            return Verdict(IMPLICIT, f"{text} is not CPython; the CPython version rules do not judge it")
        cleaned = re.sub(r"^(?:cpython-|python)", "", text)
        cleaned = re.sub(r"t$", "", cleaned)  # free-threaded build marker
        cleaned = re.sub(r"^(\d+(?:\.\d+)*)((?:a|b|rc)\d+)$", r"\1-\2", cleaned)  # 3.14.0rc1
        spec = parse_spec(cleaned)
        if spec is None:
            if re.search(r"[<>=~^|]|\s", cleaned):  # setup-python accepts semver ranges
                return self.python_range(cleaned)
            return Verdict(ERROR, f"cannot parse Python version {text!r}", "unparseable")
        comps = spec[0]
        minimum = ".".join(map(str, PYTHON_MINIMUM))
        if len(comps) >= 2 and comps[:2] < PYTHON_MINIMUM or len(comps) == 1 and comps[0] < PYTHON_MINIMUM[0]:
            return Verdict(OUTDATED, f"{text} is below the Python minimum {minimum}", "below_minimum")
        if len(comps) < 3:
            return Verdict(OK, f"{text} floats to the latest patch")
        return self._against(spec, self.lookups.python(comps[:2]), "Python", text)

    def python_range(self, text: str) -> Verdict:
        """A semver range: it must admit the latest patch of the newest minor line it admits."""
        try:
            range_satisfied(text, (0, 0, 0, ()))  # syntax check before any lookup
        except RangeError as exc:
            return Verdict(ERROR, f"cannot parse Python range {text!r}: {exc}", "unparseable")
        return self._newest_line(lambda version: range_satisfied(text, version + ((),)), repr(text))

    def _newest_line(self, admits: Callable[[Tuple[int, int, int]], bool], label: str) -> Verdict:
        """Judge a range against the latest patch of the newest released Python minor line it admits.

        A range that admits every Python 3 from the minimum on (every patch of
        every minor line the walk considers) takes whatever is released and
        needs no lookup. Otherwise the admitted lines are looked up from the
        lowest upwards; the first line without a release ends the walk, because
        Python minors are released in order, and the last released line is the
        one judged. A lookup that fails for any other reason stays an error.
        """
        major, minor = PYTHON_MINIMUM
        candidates = range(minor, minor + 20)
        if all(admits((major, m, p)) for m in candidates for p in range(100)):
            return Verdict(OK, f"{label} admits every Python from {major}.{minor} on")
        lines = [m for m in candidates if any(admits((major, m, p)) for p in range(100))]
        if not lines:
            if admits((major + 1, 0, 0)):
                return Verdict(OK, f"{label} admits a Python line newer than {major}")
            return Verdict(OUTDATED, f"{label} admits no Python {major}.{minor} or newer", "below_minimum")
        latest: Optional[Version] = None
        for line in lines:
            try:
                latest = self.lookups.python((major, line))
            except LookupFailed as exc:
                if not exc.unreleased:
                    raise
                if latest is None:
                    raise  # no admitted line has a release: the range cannot be judged
                break
        assert latest is not None
        if admits(latest[:3]):
            return Verdict(OK, f"admits the latest Python {format_version(latest)}")
        return Verdict(
            OUTDATED, f"{label} excludes the latest Python {format_version(latest)}", "range_excludes_latest"
        )

    def requires_python(self, text: str) -> Verdict:
        minimum = ".".join(map(str, PYTHON_MINIMUM))
        try:
            clauses = _pep_clauses(text)
            lower = pep440_lower_bound(text)
        except RangeError as exc:
            return Verdict(ERROR, f"cannot parse requires-python {text!r}: {exc}", "unparseable")
        if lower is None or _pad(lower, 2)[:2] < PYTHON_MINIMUM:
            return Verdict(OUTDATED, f"requires-python {text!r} admits Python below {minimum}", "below_minimum")
        if all(op in (">=", ">") for op, _, _ in clauses):
            return Verdict(OK, f"requires Python {minimum} or newer")
        # Upper bounds, exclusions and pins must still admit the latest patch of the newest line they admit.
        return self._newest_line(lambda version: pep440_admits(text, version), f"requires-python {text!r}")

    # -- shared ------------------------------------------------------------

    @staticmethod
    def _against(spec: Spec, latest: Version, tool: str, text: str) -> Verdict:
        if spec_is_older(spec, latest):
            return Verdict(
                OUTDATED, f"{text} is older than the latest {tool} {format_version(latest)}", "older_than_latest"
            )
        return Verdict(OK, f"matches the latest {tool} {format_version(latest)}")

    def digest(self, image: ImageRef) -> Verdict:
        """An image pinned by digest runs the digest: it must be the tag's current one."""
        digests = self.lookups.tag_digests(image)
        tag = image.tag or "latest"
        if digests is None:
            return Verdict(IMPLICIT, f"digest on {image.registry} not resolved; the tag is judged, the digest is not")
        if image.digest in digests:
            return Verdict(OK, f"digest is the current {image.name}:{tag}")
        return Verdict(
            OUTDATED, f"digest is not the current {image.name}:{tag}; rotate the base to its latest digest",
            "digest_not_latest",
        )

    # -- images ------------------------------------------------------------

    def image(self, image: ImageRef) -> Optional[Verdict]:
        if image.name == "node":
            return Verdict(NODE_USAGE, NODE_DETAIL, "bun_migration_candidate")
        tools = {"oven/bun": self.bun_spec, "python": self.python_spec, "ghcr.io/astral-sh/uv": self.uv_spec}
        if image.name not in tools and image.name not in STATEFUL:
            return None  # not an image this check judges, templated or not
        if _is_expression(image.tag):
            return Verdict(IMPLICIT, f"expression not evaluated in {image.name}:{image.tag}")
        if "$" in image.tag:
            return Verdict(ERROR, f"unresolved build argument in {image.name}:{image.tag}", "unparseable")
        if image.name in STATEFUL:
            return self._stateful_image(image, STATEFUL[image.name])
        return self._tool_image(image, tools[image.name])

    def _tool_image(self, image: ImageRef, judge: Callable[[str], Verdict]) -> Verdict:
        version_part, _ = split_tag(image.tag)
        if version_part is None:
            if image.tag[:1].isdigit():
                return Verdict(ERROR, f"cannot parse the version in {image.name}:{image.tag}", "unparseable")
            verdicts = [Verdict(OK, "floating tag follows the latest release")]
        else:
            verdicts = [judge(version_part)]
        if image.name == "ghcr.io/astral-sh/uv":
            embedded = re.search(r"(?:^|-)python(\d+(?:\.\d+){0,2}t?)(?:-|$)", image.tag)
            if embedded:
                verdicts.append(self.python_spec(embedded.group(1)))
        verdict = min(verdicts, key=lambda v: _SEVERITY[v.status])
        if verdict.status != OK or image.digest is None:
            return verdict
        return self.digest(image)

    def _stateful_image(self, image: ImageRef, stateful: Stateful) -> Verdict:
        scheme = stateful.scheme
        parsed = parse_stateful_tag(scheme, image.tag)
        if parsed is None or len(parsed[0]) < scheme.line:
            if image.digest is not None:
                return Verdict(IMPLICIT, "digest without a version line; pin a version tag next to the digest")
            if image.tag[:1].isdigit():
                return Verdict(
                    ERROR, f"cannot parse {image.name}:{image.tag} as a line or release tag", "unparseable"
                )
            return Verdict(
                OUTDATED,
                f"{image.name}:{image.tag or 'latest'} names no major line and can cross a major on the next "
                "pull; pin the line tag",
                "major_unpinned",
            )
        comps, family = parsed
        line = comps[: scheme.line]
        label_line = line_text(scheme, line)
        if len(comps) == scheme.line:
            if image.digest is None:
                return Verdict(OK, f"floating on the {label_line} line")
            return self.digest(image)
        candidates = [
            (c, tag)
            for c, tag in self.lookups.line_candidates(image.name, stateful, line, family)
            if len(c) >= len(comps)
        ]
        best, label = max(candidates, default=(comps, image.tag))
        if comps < best[: len(comps)]:
            return Verdict(
                OUTDATED, f"{image.tag} is older than the latest {label_line} line release {label}",
                "older_than_latest",
            )
        if image.digest is not None:
            return self.digest(image)
        return Verdict(OK, f"latest release of the {label_line} line")


_SEVERITY = {ERROR: 0, OUTDATED: 1, IMPLICIT: 2, NODE_USAGE: 3, OK: 4}


# --------------------------------------------------------------------------
# Scanners
# --------------------------------------------------------------------------


class Checker:
    def __init__(self, root: Path, lookups: Lookups) -> None:
        self.root = root
        self.lookups = lookups
        self.judge = Judge(lookups)
        self.declarations: List[Dict[str, Any]] = []
        self.errors: List[Dict[str, str]] = []

    def record(self, file: str, line: int, kind: str, value: str, decide: Callable[[], Optional[Verdict]]) -> None:
        try:
            verdict = decide()
        except LookupFailed as exc:
            if not any(e["code"] == exc.code and e["message"] == exc.message for e in self.errors):
                self.errors.append({"code": exc.code, "message": exc.message})
            verdict = Verdict(ERROR, exc.message, exc.code)
        if verdict is None:
            return
        entry: Dict[str, Any] = {
            "file": file,
            "line": line,
            "kind": kind,
            "value": value,
            "status": verdict.status,
            "detail": verdict.detail,
        }
        if verdict.reason:
            entry["reason"] = verdict.reason
        self.declarations.append(entry)

    def note(self, file: str, line: int, kind: str, value: str, status: str, detail: str, reason: str = "") -> None:
        self.record(file, line, kind, value, lambda: Verdict(status, detail, reason))

    def image(self, file: str, line: int, kind: str, ref: str) -> None:
        if ref.strip().startswith(("{", "[")):
            return  # a flow collection, read by the flow scanner
        image = parse_image(ref)
        if image is not None:
            self.record(file, line, kind, ref, lambda: self.judge.image(image))


def list_files(root: Path) -> List[str]:
    """Relative POSIX paths under root, git-listed when root is a work tree."""
    paths: Optional[List[str]] = None
    try:
        inside = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--is-inside-work-tree"],
            capture_output=True, text=True, check=False,
        )
        if inside.returncode == 0 and inside.stdout.strip() == "true":
            listed = subprocess.run(
                ["git", "-C", str(root), "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
                capture_output=True, text=True, check=True,
            )
            paths = sorted({p for p in listed.stdout.split("\0") if p})
    except (OSError, subprocess.CalledProcessError):
        paths = None
    if paths is None:
        paths = []
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
            for filename in sorted(filenames):
                paths.append(Path(dirpath, filename).relative_to(root).as_posix())
    return [p for p in paths if not (set(p.split("/")[:-1]) & SKIP_DIRS) and (root / p).is_file()]


def _strip_scalar(text: str) -> str:
    text = re.sub(r"\s+#.*$", "", text.strip())
    if len(text) >= 2 and text[0] == text[-1] and text[0] in "'\"":
        text = text[1:-1]
    return text.strip()


def _indent(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def _significant(line: str) -> bool:
    stripped = line.strip()
    return bool(stripped) and not stripped.startswith("#")


def _find_line(lines: List[str], needle: str, after: Optional[str] = None) -> int:
    started = after is None
    for index, line in enumerate(lines):
        if not started:
            started = after in line
            if not started:
                continue
        if needle in line:
            return index + 1
    return 1


# -- version files ---------------------------------------------------------


def _plain_versions(text: str) -> List[Tuple[int, str]]:
    found = []
    for index, line in enumerate(text.splitlines()):
        line = line.split("#", 1)[0].strip()
        if line:
            found.append((index + 1, line))
    return found


def _tool_versions(text: str) -> List[Tuple[int, str, List[str]]]:
    """(line, tool, versions) per .tool-versions entry; every listed version counts."""
    found = []
    for index, line in enumerate(text.splitlines()):
        parts = line.split("#", 1)[0].split()
        if len(parts) >= 2:
            found.append((index + 1, parts[0], parts[1:]))
    return found


def _load_toml(text: str) -> Optional[Dict[str, Any]]:
    """Parsed TOML, None without tomllib; TomlError when the text is not valid TOML."""
    try:
        import tomllib  # Python 3.11+
    except ImportError:  # pragma: no cover - older python3 falls back to a line scan
        return None
    try:
        return tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        raise TomlError(str(exc), getattr(exc, "lineno", None) or 1) from exc


def _toml_scan(text: str) -> Dict[Tuple[str, str], str]:
    """Line-scan fallback for simple ``key = "value"`` TOML entries per section."""
    found: Dict[Tuple[str, str], str] = {}
    section = ""
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("["):
            section = stripped.strip("[]").strip()
            continue
        match = re.match(r"^([\w.-]+)\s*=\s*['\"]([^'\"]*)['\"]", stripped)
        if match:
            found[(section, match.group(1))] = match.group(2)
    return found


def _mise_tools(text: str) -> Dict[str, List[str]]:
    """Tool -> every version a mise config lists for it."""
    data = _load_toml(text)
    if data is None:
        return {key: [value] for (section, key), value in _toml_scan(text).items() if section == "tools"}
    tools = data.get("tools") if isinstance(data, dict) else None
    result: Dict[str, List[str]] = {}
    for name, value in (tools or {}).items():
        values = value if isinstance(value, list) else [value]
        found = []
        for item in values:
            if isinstance(item, dict):
                item = item.get("version")
            if isinstance(item, (str, int, float)):
                found.append(str(item))
        if found:
            result[str(name)] = found
    return result


def _pyproject_values(text: str) -> Tuple[Optional[str], Optional[str]]:
    """(requires-python, [tool.uv] required-version) from a pyproject.toml."""
    data = _load_toml(text)
    if data is None:
        scanned = _toml_scan(text)
        return scanned.get(("project", "requires-python")), scanned.get(("tool.uv", "required-version"))
    project = data.get("project") or {}
    uv = (data.get("tool") or {}).get("uv") or {}
    requires = project.get("requires-python") if isinstance(project, dict) else None
    required = uv.get("required-version") if isinstance(uv, dict) else None
    return (
        requires if isinstance(requires, str) else None,
        required if isinstance(required, str) else None,
    )


_UV_REQUIREMENT_RE = re.compile(r"^\s*uv(?![\w.-])\s*(?:\[[^\]]*\])?\s*([^;#@]*)(@)?", re.IGNORECASE)


def _uv_requirement(requirement: str) -> Optional[str]:
    """The version specifier of a PEP 508 ``uv`` requirement ("" for any), None otherwise."""
    match = _UV_REQUIREMENT_RE.match(requirement)
    if not match or match.group(2):
        return None
    return match.group(1).strip()


def _pyproject_uv_requirement(text: str) -> Optional[str]:
    """A ``uv`` requirement from project dependencies, optional dependencies or dependency groups."""
    data = _load_toml(text) or {}
    project = data.get("project") if isinstance(data.get("project"), dict) else {}
    requirements: List[Any] = list(project.get("dependencies") or [])
    for group in (project.get("optional-dependencies") or {}).values():
        requirements += list(group or [])
    for group in (data.get("dependency-groups") or {}).values():
        requirements += list(group or [])
    uv = (data.get("tool") or {}).get("uv") or {}
    requirements += list(uv.get("dev-dependencies") or []) if isinstance(uv, dict) else []
    for requirement in requirements:
        if isinstance(requirement, str):
            spec = _uv_requirement(requirement)
            if spec is not None:
                return spec
    return None


def _requirements_uv(text: str) -> Optional[str]:
    """A ``uv`` requirement from a requirements file."""
    for line in text.splitlines():
        line = re.sub(r"(?:^|\s)#.*$", "", line).strip()
        if line and not line.startswith("-"):
            spec = _uv_requirement(line)
            if spec is not None:
                return spec
    return None


def _uv_toml_required(text: str) -> Optional[str]:
    data = _load_toml(text)
    if data is None:
        return _toml_scan(text).get(("", "required-version"))
    value = data.get("required-version")
    return value if isinstance(value, str) else None


def _package_manager_bun(text: str) -> Optional[str]:
    try:
        manager = json.loads(text).get("packageManager")
    except (ValueError, AttributeError):
        return None
    if isinstance(manager, str) and manager.startswith("bun@"):
        return manager[len("bun@") :].split("+", 1)[0]
    return None


TOOL_ALIASES = {"bun": "bun", "python": "python", "uv": "uv", "nodejs": "node", "node": "node"}


def _tool_verdict(judge: Judge, tool: str, value: str) -> Callable[[], Verdict]:
    if tool == "bun":
        return lambda: judge.bun_spec(value)
    if tool == "python":
        return lambda: judge.python_spec(value)
    if tool == "uv":
        return lambda: judge.uv_spec(value)
    return lambda: Verdict(NODE_USAGE, NODE_DETAIL, "bun_migration_candidate")


def scan_tool_versions(checker: Checker, rel: str, text: str) -> None:
    for line, name, values in _tool_versions(text):
        tool = TOOL_ALIASES.get(name)
        if tool:
            for value in values:
                checker.record(rel, line, "tool-versions", f"{name} {value}", _tool_verdict(checker.judge, tool, value))


def _toml_unparseable(checker: Checker, rel: str, kind: str, exc: TomlError) -> None:
    checker.note(rel, exc.line, kind, "", ERROR, f"invalid TOML: {exc}", "unparseable")


def scan_mise(checker: Checker, rel: str, text: str) -> None:
    lines = text.splitlines()
    try:
        tools = _mise_tools(text)
    except TomlError as exc:
        _toml_unparseable(checker, rel, "mise", exc)
        return
    for name, values in tools.items():
        tool = TOOL_ALIASES.get(name)
        if tool:
            line = next((i + 1 for i, l in enumerate(lines) if re.match(rf"^\s*['\"]?{re.escape(name)}['\"]?\s*=", l)), 1)
            for value in values:
                checker.record(rel, line, "mise", f"{name} = {value}", _tool_verdict(checker.judge, tool, value))


def scan_plain_file(kind: str, tool: str) -> Callable[[Checker, str, str], None]:
    def scan(checker: Checker, rel: str, text: str) -> None:
        for line, value in _plain_versions(text):
            checker.record(rel, line, kind, value, _tool_verdict(checker.judge, tool, value))

    return scan


DEPENDENCY_FIELDS = ("dependencies", "devDependencies", "optionalDependencies", "peerDependencies")


def scan_package_json(checker: Checker, rel: str, text: str) -> None:
    try:
        data = json.loads(text)
    except ValueError as exc:
        checker.note(rel, 1, "package.json", "", ERROR, f"invalid JSON: {exc}", "unparseable")
        return
    if not isinstance(data, dict):
        return
    lines = text.splitlines()
    judge = checker.judge
    manager = data.get("packageManager")
    if isinstance(manager, str) and manager.startswith("bun@"):
        version = manager[len("bun@") :].split("+", 1)[0]
        checker.record(rel, _find_line(lines, '"packageManager"'), "packageManager", manager, lambda: judge.bun_spec(version))
    engines = data.get("engines")
    if isinstance(engines, dict):
        if isinstance(engines.get("bun"), str):
            bun_range = engines["bun"]
            line = _find_line(lines, '"bun"', after='"engines"')
            checker.record(rel, line, "engines", bun_range, lambda: judge.bun_range(bun_range))
        if isinstance(engines.get("node"), str):
            line = _find_line(lines, '"node"', after='"engines"')
            checker.note(rel, line, "engines-node", engines["node"], NODE_USAGE, NODE_DETAIL, "bun_migration_candidate")
    for field in DEPENDENCY_FIELDS:
        deps = data.get(field)
        if isinstance(deps, dict) and isinstance(deps.get("bun"), str):
            spec = deps["bun"]
            line = _find_line(lines, '"bun"', after=f'"{field}"')
            checker.record(rel, line, "bun-dependency", f"{field}.bun: {spec}", lambda spec=spec: judge.bun_dependency(spec))
    scripts = data.get("scripts")
    if isinstance(scripts, dict):
        for name, command in scripts.items():
            if not isinstance(command, str):
                continue
            line = _find_line(lines, f'"{name}"', after='"scripts"')
            if _NODE_TEST_RE.search(command):
                checker.note(
                    rel, line, "node-test-script", f"{name}: {command}", NODE_USAGE,
                    "node --test suite: new code uses bun test", "bun_migration_candidate",
                )
            elif _NODE_COMMAND_RE.search(command):
                checker.note(
                    rel, line, "node-script", f"{name}: {command}", NODE_USAGE,
                    "script runs node directly: run it with bun", "bun_migration_candidate",
                )


_NODE_TEST_RE = re.compile(r"(?:^|[\s;&|(])node(?:\s+(?!--test\b)\S+)*\s+--test\b")
_NODE_COMMAND_RE = re.compile(r"(?:^|[\s;&|(])node(?=\s|$)")


def scan_pyproject(checker: Checker, rel: str, text: str) -> None:
    try:
        requires, required = _pyproject_values(text)
    except TomlError as exc:
        _toml_unparseable(checker, rel, "pyproject.toml", exc)
        return
    lines = text.splitlines()
    if requires is not None:
        checker.record(
            rel, _find_line(lines, "requires-python"), "requires-python", requires,
            lambda: checker.judge.requires_python(requires),
        )
    if required is not None:
        checker.record(
            rel, _find_line(lines, "required-version"), "uv-required-version", required,
            lambda: checker.judge.uv_required(required),
        )


def scan_uv_toml(checker: Checker, rel: str, text: str) -> None:
    try:
        required = _uv_toml_required(text)
    except TomlError as exc:
        _toml_unparseable(checker, rel, "uv.toml", exc)
        return
    if required is not None:
        checker.record(
            rel, _find_line(text.splitlines(), "required-version"), "uv-required-version", required,
            lambda: checker.judge.uv_required(required),
        )


# -- YAML flow collections ---------------------------------------------------


class _Flow:
    """Minimal single-line YAML flow parser: ``{a: b, c: [d, 'e']}``."""

    def __init__(self, text: str) -> None:
        self.text = text
        self.pos = 0

    def peek(self) -> str:
        return self.text[self.pos] if self.pos < len(self.text) else ""

    def skip(self) -> None:
        while self.peek() in (" ", "\t") and self.peek():
            self.pos += 1

    def value(self) -> Any:
        self.skip()
        char = self.peek()
        if char == "{":
            return self.mapping()
        if char == "[":
            return self.sequence()
        if char in ("'", '"'):
            return self.quoted()
        return self.plain()

    def mapping(self) -> Dict[str, Any]:
        self.pos += 1
        result: Dict[str, Any] = {}
        while True:
            self.skip()
            if self.peek() == "}":
                self.pos += 1
                return result
            key = self.quoted() if self.peek() in ("'", '"') else self.plain()
            self.skip()
            value = None
            if self.peek() == ":":
                self.pos += 1
                value = self.value()
            result[str(key)] = value
            self.skip()
            if self.peek() == ",":
                self.pos += 1
            elif self.peek() == "}":
                self.pos += 1
                return result
            else:
                raise ValueError("unterminated flow mapping")

    def sequence(self) -> List[Any]:
        self.pos += 1
        result: List[Any] = []
        while True:
            self.skip()
            if self.peek() == "]":
                self.pos += 1
                return result
            result.append(self.value())
            self.skip()
            if self.peek() == ",":
                self.pos += 1
            elif self.peek() == "]":
                self.pos += 1
                return result
            else:
                raise ValueError("unterminated flow sequence")

    def quoted(self) -> str:
        quote = self.peek()
        self.pos += 1
        out = []
        while self.pos < len(self.text):
            char = self.text[self.pos]
            if quote == "'" and char == "'" and self.text[self.pos + 1 : self.pos + 2] == "'":
                out.append("'")
                self.pos += 2
                continue
            if quote == '"' and char == "\\" and self.pos + 1 < len(self.text):
                out.append(self.text[self.pos + 1])
                self.pos += 2
                continue
            if char == quote:
                self.pos += 1
                return "".join(out)
            out.append(char)
            self.pos += 1
        raise ValueError("unterminated quoted scalar")

    def plain(self) -> str:
        start = self.pos
        while self.pos < len(self.text):
            char = self.text[self.pos]
            if char in ",]}":
                break
            if char == ":" and self.text[self.pos + 1 : self.pos + 2] in ("", " ", ",", "}", "]"):
                break
            if char == "#" and self.pos > start and self.text[self.pos - 1] == " ":
                break
            self.pos += 1
        return self.text[start : self.pos].strip()


_FLOW_LINE_RE = re.compile(r"^\s*(?:-\s+)?(?:(?:[\w.-]+|\"[^\"]*\"|'[^']*')\s*:\s+)?(\{.*)$")


def _flow_value(text: str) -> Any:
    return _Flow(text).value()


def _flow_on_line(line: str) -> Optional[Any]:
    """The flow mapping a line holds as a list item or mapping value, None otherwise."""
    match = _FLOW_LINE_RE.match(line)
    if not match:
        return None
    try:
        return _flow_value(match.group(1))
    except ValueError:
        return None


def _walk(value: Any):
    if isinstance(value, dict):
        yield value
        for item in value.values():
            yield from _walk(item)
    elif isinstance(value, list):
        for item in value:
            yield from _walk(item)


def _flow_settings(value: Any, line: int) -> Dict[str, Tuple[int, List[str]]]:
    settings: Dict[str, Tuple[int, List[str]]] = {}
    if isinstance(value, dict):
        for key, item in value.items():
            if isinstance(item, list):
                settings[key] = (line, [str(v) for v in item if v is not None])
            else:
                settings[key] = (line, [] if item is None else [str(item)])
    return settings


# -- workflows -------------------------------------------------------------

_USES_RE = re.compile(r"^(\s*)(-\s+)?uses:\s*(\S+)")
_SETUP_RE = re.compile(r"(?:^|/)setup-(bun|python|uv|node)@")
_IMAGE_LINE_RE = re.compile(r"^\s*(?:-\s+)?(?:image|container):\s*(\S.*)$")
_RUN_RE = re.compile(r"^\s*(?:-\s+)?run:\s*(.*)$")

# tool -> (version key, version-file key)
SETUP_KEYS = {
    "bun": ("bun-version", "bun-version-file"),
    "python": ("python-version", "python-version-file"),
    "uv": ("version", "version-file"),
    "node": ("node-version", "node-version-file"),
}


def _key_position(line: str) -> Tuple[int, str]:
    """Column and text of the mapping key on a line, looking past a list dash."""
    stripped = line.lstrip(" ")
    column = _indent(line)
    if stripped.startswith("- "):
        rest = stripped[2:]
        column += 2 + (len(rest) - len(rest.lstrip(" ")))
        stripped = rest.lstrip(" ")
    return column, stripped


def _step_with(lines: List[str], start: int, end: int, key_indent: int) -> Dict[str, Tuple[int, List[str]]]:
    """Return the ``with:`` keys of one step as {key: (line, values)}."""
    settings: Dict[str, Tuple[int, List[str]]] = {}
    for index in range(start, end):
        column, content = _key_position(lines[index])
        if column != key_indent:
            continue
        match = re.match(r"^with:\s*(.*)$", content)
        if not match:
            continue
        inline = match.group(1).strip()
        if inline.startswith("{"):
            try:
                return _flow_settings(_flow_value(inline), index + 1)
            except ValueError:
                return settings
        child_indent: Optional[int] = None
        current: Optional[str] = None
        for child in range(index + 1, end):
            child_line = lines[child]
            if not _significant(child_line):
                continue
            indent = _indent(child_line)
            if indent <= key_indent:
                break
            if child_indent is None:
                child_indent = indent
            if indent == child_indent:
                pair = re.match(r"^\s*(?:\"([^\"]+)\"|'([^']+)'|([\w-]+))\s*:\s*(.*)$", child_line)
                if not pair:
                    continue
                current = pair.group(1) or pair.group(2) or pair.group(3)
                raw = _strip_scalar(pair.group(4))
                if raw.startswith("["):
                    values = [_strip_scalar(v) for v in raw.strip("[]").split(",") if v.strip()]
                elif raw in ("", "|", "|-", ">", ">-"):
                    values = []
                else:
                    values = [raw]
                settings[current] = (child + 1, values)
            elif current is not None:
                # Block scalar or block sequence continuation.
                settings[current][1].append(_strip_scalar(re.sub(r"^\s*-\s*", "", child_line)))
        return settings
    return settings


def _run_commands(lines: List[str]) -> List[Tuple[int, str]]:
    """(line, command line) for every ``run:`` value, including block scalars."""
    commands: List[Tuple[int, str]] = []
    index = 0
    while index < len(lines):
        match = _RUN_RE.match(lines[index])
        if not match:
            index += 1
            continue
        column = _key_position(lines[index])[0]
        value = _strip_scalar(match.group(1))
        if re.match(r"^[|>][-+]?\d*$", value):
            index += 1
            while index < len(lines) and (not lines[index].strip() or _indent(lines[index]) > column):
                if lines[index].strip():
                    commands.append((index + 1, lines[index].strip()))
                index += 1
            continue
        commands.append((index + 1, value))
        index += 1
    return commands


def scan_workflow(checker: Checker, rel: str, text: str) -> None:
    lines = text.splitlines()
    for index, line in enumerate(lines):
        image = _IMAGE_LINE_RE.match(line)
        if image:
            checker.image(rel, index + 1, "workflow-image", _strip_scalar(image.group(1)))
        flow = _flow_on_line(line)
        if flow is not None:
            for mapping in _walk(flow):
                for key in ("image", "container"):
                    if isinstance(mapping.get(key), str):
                        checker.image(rel, index + 1, "workflow-image", mapping[key])
                uses = mapping.get("uses")
                flow_setup = _SETUP_RE.search(uses) if isinstance(uses, str) else None
                if flow_setup:
                    _judge_setup(
                        checker, rel, index + 1, flow_setup.group(1), _flow_settings(mapping.get("with"), index + 1)
                    )
        uses_match = _USES_RE.match(line)
        if not uses_match:
            continue
        setup = _SETUP_RE.search(_strip_scalar(uses_match.group(3)))
        if not setup:
            continue
        key_indent = len(uses_match.group(1)) + len(uses_match.group(2) or "")
        start = index
        if not uses_match.group(2):  # the step starts at its dash line, which may precede uses
            for back in range(index - 1, -1, -1):
                if _significant(lines[back]) and _indent(lines[back]) < key_indent:
                    start = back
                    break
        end = len(lines)
        for forward in range(index + 1, len(lines)):
            if _significant(lines[forward]) and _indent(lines[forward]) < key_indent:
                end = forward
                break
        _judge_setup(checker, rel, index + 1, setup.group(1), _step_with(lines, start, end, key_indent))
    for line_number, command in _run_commands(lines):
        if _NODE_TEST_RE.search(command):
            checker.note(
                rel, line_number, "node-test-run", command, NODE_USAGE,
                "node --test suite: new code uses bun test", "bun_migration_candidate",
            )


def _first(settings: Dict[str, Tuple[int, List[str]]], key: str) -> str:
    values = settings.get(key, (0, []))[1]
    return values[0] if values else ""


def _judge_setup(checker: Checker, rel: str, line: int, tool: str, settings: Dict[str, Tuple[int, List[str]]]) -> None:
    kind = f"setup-{tool}"
    version_key, file_key = SETUP_KEYS[tool]
    judge = checker.judge
    if tool == "node":
        shown = settings.get(version_key) or settings.get(file_key)
        key = version_key if version_key in settings else file_key
        value = f"{key}: {', '.join(shown[1])}" if shown else "(no node-version)"
        checker.note(rel, shown[0] if shown else line, kind, value, NODE_USAGE, NODE_DETAIL, "bun_migration_candidate")
        return
    if version_key in settings:
        value_line, values = settings[version_key]
        for value in values or [""]:
            if tool == "python" and value == "":
                checker.note(rel, value_line, kind, f"{version_key}:", IMPLICIT, "empty python-version")
                continue
            checker.record(rel, value_line, kind, f"{version_key}: {value}", _tool_verdict(judge, tool, value))
    elif file_key in settings:
        value_line, values = settings[file_key]
        target = values[0] if values else ""
        workdir = _first(settings, "working-directory") if tool == "uv" else ""
        checker.record(
            rel, value_line, kind, f"{file_key}: {target}",
            lambda: _version_file_verdict(checker, tool, target, workdir),
        )
    else:
        hint = {"bun": "bun-version: latest", "python": "python-version: '3.14' with check-latest: true", "uv": "version: latest"}[tool]
        checker.note(rel, line, kind, f"(no {version_key})", IMPLICIT, f"{kind} without {version_key}; set {hint}")
    if tool == "python" and (version_key in settings or file_key in settings):
        values = settings.get(version_key, (0, []))[1]
        pinned = bool(values) and all(parse_release(v) is not None for v in values)
        expressions = bool(values) and all(_is_expression(v) for v in values)
        if _first(settings, "check-latest").lower() != "true" and not pinned and not expressions:
            checker.note(
                rel, line, kind, "check-latest: (not true)", IMPLICIT,
                "setup-python without check-latest: true can use a cached older patch; set check-latest: true",
            )
    if tool == "uv":
        if "python-version" in settings:
            value_line, values = settings["python-version"]
            for value in values:
                checker.record(rel, value_line, kind, f"python-version: {value}", _tool_verdict(judge, "python", value))
        if _first(settings, "resolution-strategy").lower() == "lowest":
            checker.note(
                rel, settings["resolution-strategy"][0], kind, "resolution-strategy: lowest", OUTDATED,
                "resolution-strategy: lowest installs the oldest uv the version admits; remove it",
                "lowest_resolution",
            )


def _version_file_verdict(checker: Checker, tool: str, target: str, workdir: str = "") -> Verdict:
    """Evaluate the file a setup action's version-file input points at."""
    for value in (target, workdir):
        if _is_expression(value):
            return Verdict(IMPLICIT, f"expression not evaluated in {value}; the file it names is not judged")
    base = checker.root / workdir if workdir else checker.root
    path = base / target
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return Verdict(ERROR, f"cannot read {target}: {exc}", "unreadable")
    try:
        return _version_file_text_verdict(checker.judge, tool, target, path.name, text)
    except TomlError as exc:
        return Verdict(ERROR, f"cannot parse {target}: invalid TOML: {exc}", "unparseable")


def _version_file_text_verdict(judge: Judge, tool: str, target: str, name: str, text: str) -> Verdict:
    if name == ".tool-versions":
        found = next((v[0] for _, n, v in _tool_versions(text) if TOOL_ALIASES.get(n) == tool), None)
    elif _is_mise(name):
        values = _mise_tools(text).get(tool)
        found = values[0] if values else None
    elif name == "package.json" and tool == "bun":
        found = _package_manager_bun(text)
    elif name == "pyproject.toml" and tool == "python":
        requires = _pyproject_values(text)[0]
        return judge.requires_python(requires) if requires else Verdict(IMPLICIT, f"{target} has no requires-python")
    elif tool == "uv" and name in ("pyproject.toml", "uv.toml") or tool == "uv" and name.endswith(".txt"):
        if name == "pyproject.toml":
            required = _pyproject_values(text)[1]
            if required is None:
                required = _pyproject_uv_requirement(text)
        elif name == "uv.toml":
            required = _uv_toml_required(text)
        else:
            required = _requirements_uv(text)
        if required is None:
            return Verdict(IMPLICIT, f"{target} names no uv version")
        return judge.uv_required(required)
    else:
        plain = _plain_versions(text)
        found = plain[0][1] if plain else None
    if found is None:
        return Verdict(IMPLICIT, f"{target} names no {tool} version")
    return _tool_verdict(judge, tool, found)()


# -- containers ------------------------------------------------------------

_FROM_RE = re.compile(r"^\s*FROM\s+(?:--\S+\s+)*(\S+)", re.IGNORECASE)
_COPY_FROM_RE = re.compile(r"^\s*COPY\s+(?:--\S+\s+)*?--from=(\S+)", re.IGNORECASE)
_ARG_RE = re.compile(r"^\s*ARG\s+([A-Za-z_][A-Za-z0-9_]*)(?:=(\S*))?", re.IGNORECASE)


def _logical_lines(text: str) -> List[Tuple[int, str]]:
    """Dockerfile instructions with backslash continuations joined, numbered by their first line."""
    result: List[Tuple[int, str]] = []
    buffer = ""
    start: Optional[int] = None
    for index, raw in enumerate(text.splitlines()):
        if start is not None and raw.strip().startswith("#"):
            continue  # comment lines inside a continuation are dropped
        if start is None:
            start = index + 1
        stripped = raw.rstrip()
        if stripped.endswith("\\"):
            buffer += stripped[:-1] + " "
            continue
        result.append((start, buffer + raw))
        buffer, start = "", None
    if start is not None:
        result.append((start, buffer))
    return result


def scan_dockerfile(checker: Checker, rel: str, text: str) -> None:
    # ARGs before the first FROM are global and the only ones FROM lines see; an ARG after a
    # FROM is local to its stage, and a bare ARG there takes over the global default.
    global_args: Dict[str, str] = {}
    stage_args: Optional[Dict[str, str]] = None
    for number, line in _logical_lines(text):
        arg = _ARG_RE.match(line)
        if arg:
            name, default = arg.group(1), arg.group(2)
            if stage_args is None:
                if default is not None:
                    global_args[name] = _strip_scalar(default)
            elif default is not None:
                stage_args[name] = _strip_scalar(default)
            elif name in global_args:
                stage_args[name] = global_args[name]
            continue
        match = _FROM_RE.match(line)
        if match:
            checker.image(rel, number, "dockerfile", _substitute(match.group(1), global_args))
            stage_args = {}
            continue
        match = _COPY_FROM_RE.match(line)
        if match:
            checker.image(rel, number, "dockerfile", _substitute(match.group(1), stage_args or {}))


_VARIABLE_RE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)(?:(:?-)([^}]*))?\}|\$([A-Za-z_][A-Za-z0-9_]*)")


def _substitute(ref: str, args: Dict[str, str]) -> str:
    """Expand $NAME, ${NAME}, ${NAME:-default} and ${NAME-default}; unknown plain names stay."""

    def replace(match: "re.Match[str]") -> str:
        if match.group(4):
            return args.get(match.group(4), match.group(0))
        name, operator, default = match.group(1), match.group(2), match.group(3)
        value = args.get(name)
        if operator is None:
            return value if value is not None else match.group(0)
        if operator == ":-":
            return value if value else default
        return value if value is not None else default

    return _VARIABLE_RE.sub(replace, ref)


_COMPOSE_IMAGE_RE = re.compile(r"^\s*(?:-\s+)?image:\s*(\S.*)$")


def scan_compose(checker: Checker, rel: str, text: str) -> None:
    # Variables take their inline default; .env files and the shell environment are not read.
    for index, line in enumerate(text.splitlines()):
        match = _COMPOSE_IMAGE_RE.match(line)
        if match:
            checker.image(rel, index + 1, "compose", _substitute(_strip_scalar(match.group(1)), {}))
        flow = _flow_on_line(line)
        if flow is not None:
            for mapping in _walk(flow):
                if isinstance(mapping.get("image"), str):
                    checker.image(rel, index + 1, "compose", _substitute(mapping["image"], {}))


ACTION_DIRS = (".github/actions", ".forgejo/actions", ".gitea/actions")


def _under(rel: str, dirs: Tuple[str, ...]) -> bool:
    return any(rel.startswith(d + "/") or f"/{d}/" in rel for d in dirs)


def _is_workflow(rel: str) -> bool:
    if rel.endswith((".yml", ".yaml")) and _under(rel, WORKFLOW_DIRS):
        return True
    return rel.rsplit("/", 1)[-1] in ("action.yml", "action.yaml") and _under(rel, ACTION_DIRS)


def _is_dockerfile(name: str) -> bool:
    return name.startswith(("Dockerfile", "Containerfile")) or name.endswith((".Dockerfile", ".dockerfile"))


def _is_compose(name: str) -> bool:
    return bool(re.match(r"^(docker-)?compose[\w.-]*\.ya?ml$", name))


def _is_mise(rel: str) -> bool:
    """mise.toml, .mise.toml, mise.local.toml, mise.<env>.toml and .config/mise/config.toml."""
    name = rel.rsplit("/", 1)[-1]
    if re.match(r"^\.?mise(?:\.[\w-]+)*\.toml$", name):
        return True
    return bool(re.search(r"(?:^|/)(?:\.config/mise|\.mise)/config(?:\.[\w-]+)*\.toml$", rel))


FILE_SCANNERS: Dict[str, Callable[[Checker, str, str], None]] = {
    "package.json": scan_package_json,
    ".bun-version": scan_plain_file("bun-version-file", "bun"),
    ".python-version": scan_plain_file("python-version-file", "python"),
    ".nvmrc": scan_plain_file("node-version-file", "node"),
    ".node-version": scan_plain_file("node-version-file", "node"),
    ".tool-versions": scan_tool_versions,
    "pyproject.toml": scan_pyproject,
    "uv.toml": scan_uv_toml,
}


def scan(checker: Checker) -> None:
    for rel in list_files(checker.root):
        name = rel.rsplit("/", 1)[-1]
        scanner: Optional[Callable[[Checker, str, str], None]]
        if _is_workflow(rel):
            scanner = scan_workflow
        elif _is_dockerfile(name):
            scanner = scan_dockerfile
        elif _is_compose(name):
            scanner = scan_compose
        elif _is_mise(rel):
            scanner = scan_mise
        else:
            scanner = FILE_SCANNERS.get(name)
        if scanner is None:
            continue
        try:
            text = (checker.root / rel).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            checker.note(rel, 1, "file", "", ERROR, f"cannot read: {exc}", "unreadable")
            continue
        scanner(checker, rel, text)


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> None:  # type: ignore[override]
        raise UsageError(message)


def _emit(envelope: Dict[str, Any]) -> None:
    json.dump(envelope, sys.stdout, indent=2)
    sys.stdout.write("\n")


def parse_overrides(latest: Optional[str], pairs: List[str]) -> Dict[str, str]:
    overrides: Dict[str, str] = {}
    if latest is not None:
        pairs = [f"bun={latest}"] + pairs
    for pair in pairs:
        key, sep, value = pair.partition("=")
        key, value = key.strip(), value.strip()
        if not sep or not key or not value:
            raise UsageError(f"--latest-version needs KEY=VERSION, got {pair!r}")
        python = re.match(r"^python(\d+)\.(\d+)$", key)
        if key in ("bun", "uv") or python:
            version = parse_release(value)
            if version is None or version[3]:
                raise UsageError(f"{key} needs a full x.y.z release version, got {value!r}")
            if python and version[:2] != (int(python.group(1)), int(python.group(2))):
                raise UsageError(f"{key} override {value!r} is not in that minor line")
        else:
            name, _, line = key.rpartition(":")
            line_match = re.match(r"^(\d+(?:-\d+)?)(?:-[A-Za-z]\w*)?$", line)
            if name not in STATEFUL or not line_match:
                raise UsageError(
                    f"unknown override key {key!r}; use bun, uv, python3.N or <image>:<line>[-<variant>]"
                )
            scheme = STATEFUL[name].scheme
            parsed = parse_stateful_tag(scheme, value)
            if parsed is None or line_text(scheme, parsed[0][: scheme.line]) != line_match.group(1):
                raise UsageError(f"{key} override {value!r} is not a release tag of that line")
        overrides[key] = value
    return overrides


def main(argv: Optional[List[str]] = None) -> int:
    parser = _Parser(description="Fail on toolchain declarations older than their latest release.")
    parser.add_argument("--root", default=".", help="repository root to scan (default: current directory)")
    parser.add_argument("--latest", help="latest Bun version; same as --latest-version bun=X.Y.Z")
    parser.add_argument(
        "--latest-version", action="append", default=[], metavar="KEY=VERSION",
        help="skip one lookup: bun=, uv=, python3.N=, or <image>:<line>[-<variant>]=<tag> (repeatable)",
    )
    try:
        args = parser.parse_args(argv)
        root = Path(args.root).resolve()
        if not root.is_dir():
            raise UsageError(f"--root is not a directory: {args.root}")
        overrides = parse_overrides(args.latest, args.latest_version)
    except UsageError as exc:
        _emit({
            "status": "error",
            "summary": f"usage error: {exc}",
            "data": {"latest": {}, "declarations": []},
            "errors": [{"code": "usage", "message": str(exc)}],
            "next_steps": ["Run check_toolchain_versions.py --help."],
        })
        return 2

    checker = Checker(root, Lookups(overrides))
    scan(checker)
    declarations = checker.declarations
    data = {"root": str(root), "latest": dict(checker.lookups.resolved), "declarations": declarations}

    def count(status: str) -> int:
        return sum(1 for d in declarations if d["status"] == status)

    outdated = count(OUTDATED)
    broken = sum(1 for d in declarations if d["status"] == ERROR and not d.get("reason", "").endswith("_lookup_failed"))
    notes, node = count(IMPLICIT), count(NODE_USAGE)
    next_steps: List[str] = []
    if checker.errors:
        status, code = "error", 2
        summary = "lookup failed while explicit declarations need it: " + ", ".join(
            sorted({e["code"] for e in checker.errors})
        )
        next_steps.append("Retry with network access, or pass --latest-version KEY=VERSION for the failed lookup.")
    elif outdated or broken:
        status, code = "failed", 1
        summary = f"{outdated} outdated and {broken} unreadable toolchain declaration(s)"
        next_steps.append("Move each outdated declaration to its latest release (see the toolchains standard).")
    else:
        status, code = "ok", 0
        summary = f"{len(declarations)} toolchain declaration(s) checked, none outdated"
    if node:
        summary += f"; {node} Node usage(s) reported"
        next_steps.append("Migrate the listed Node usages to Bun, or keep Node on the latest LTS where a third-party tool requires it.")
    if notes:
        next_steps.append("Set bun-version: latest, version: latest or an explicit python-version on setup steps that omit it.")
    _emit({"status": status, "summary": summary, "data": data, "errors": checker.errors, "next_steps": next_steps})
    return code


if __name__ == "__main__":
    sys.exit(main())

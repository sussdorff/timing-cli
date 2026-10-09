"""Behaviour of the toolchain-currency check at its CLI seam.

The network boundary ``fetch_json`` is replaced by a fake that maps URLs to
payloads, so no test reaches the network.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check_toolchain_versions.py"

NPM_URL = "https://registry.npmjs.org/bun/latest"
GITHUB_URL = "https://api.github.com/repos/oven-sh/bun/releases/latest"
HUB_TAG_URL = "https://hub.docker.com/v2/repositories/oven/bun/tags/"
HUB = "https://hub.docker.com/v2/repositories/"

# Real case: the digest behind oven/bun:1 when it was Bun 1.3.14.
OLD_DIGEST = "sha256:e10577f0db68676a7024391c6e5cb4b879ebd17188ab750cf10024a6d700e5c4"
LATEST_INDEX_DIGEST = "sha256:" + "a" * 64
LATEST_AMD64_DIGEST = "sha256:" + "b" * 64


@pytest.fixture
def checker():
    spec = importlib.util.spec_from_file_location("check_toolchain_versions", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    yield module
    sys.modules.pop(spec.name, None)


class FakeNet:
    """URL -> payload map; a missing URL or an exception value fails the fetch."""

    def __init__(self, responses: dict | None = None) -> None:
        self.responses = responses or {}
        self.calls: list[str] = []
        self.headers: list[dict] = []

    def __call__(self, url, timeout, headers=None):
        self.calls.append(url)
        self.headers.append(dict(headers or {}))
        value = self.responses.get(url)
        if value is None:
            raise OSError(f"unreachable: {url}")
        if isinstance(value, Exception):
            raise value
        return value


def npm_latest(version: str = "1.4.2") -> dict:
    return {NPM_URL: {"name": "bun", "version": version}}


def write(root: Path, rel: str, text: str) -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def run(checker, monkeypatch, capsys, root: Path, net: FakeNet, *extra: str):
    monkeypatch.setattr(checker, "fetch_json", net)
    code = checker.main(["--root", str(root), *extra])
    envelope = json.loads(capsys.readouterr().out)
    return code, envelope


def statuses(envelope: dict) -> list[tuple[str, str]]:
    return [(d["kind"], d["status"]) for d in envelope["data"]["declarations"]]


WORKFLOW_LATEST = """\
name: ci
on: [push]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: oven-sh/setup-bun@v2
        with:
          bun-version: latest
      - run: bun test
"""


def test_repository_following_the_rule_passes(checker, monkeypatch, capsys, tmp_path):
    write(tmp_path, ".github/workflows/ci.yml", WORKFLOW_LATEST)
    write(tmp_path, "package.json", json.dumps({"name": "x", "engines": {"bun": ">=1.1"}}))
    write(tmp_path, "Dockerfile", "FROM oven/bun:latest AS build\nFROM oven/bun:1-alpine\n")
    write(tmp_path, "compose.yml", "services:\n  app:\n    image: oven/bun:1\n")

    code, envelope = run(checker, monkeypatch, capsys, tmp_path, FakeNet(npm_latest()))

    assert code == 0
    assert envelope["status"] == "ok"
    assert set(envelope) == {"status", "summary", "data", "errors", "next_steps"}
    assert envelope["data"]["latest"] == {"bun": "1.4.2"}
    found = statuses(envelope)
    assert ("setup-bun", "ok") in found
    assert ("engines", "ok") in found
    assert all(status == "ok" for _, status in found)
    assert len(found) == 5


def setup_bun_workflow(with_block: str) -> str:
    return (
        "jobs:\n"
        "  test:\n"
        "    steps:\n"
        "      - name: Setup Bun\n"
        "        uses: https://code.forgejo.org/oven-sh/setup-bun@0c5077e51419868618aeaa5fe8019c62421857d6 # v2\n"
        + with_block
        + "      - run: bun test\n"
    )


@pytest.mark.parametrize(
    ("files", "kind"),
    [
        (
            {".github/workflows/ci.yml": setup_bun_workflow("        with:\n          bun-version: 1.3.14\n")},
            "setup-bun",
        ),
        (
            {".forgejo/workflows/ci.yaml": setup_bun_workflow("        with:\n          bun-version: \"1.3\"\n")},
            "setup-bun",
        ),
        (
            {
                ".forgejo/workflows/ci.yml": setup_bun_workflow(
                    "        with:\n          bun-version-file: .bun-version\n"
                ),
                ".bun-version": "1.3.14\n",
            },
            "setup-bun",
        ),
        ({"package.json": json.dumps({"packageManager": "bun@1.3.14+sha512.abc"})}, "packageManager"),
        ({"apps/web/package.json": json.dumps({"engines": {"bun": "~1.3.0"}})}, "engines"),
        ({".bun-version": "1.3.14\n"}, "bun-version-file"),
        ({".tool-versions": "nodejs 22.1.0\nbun 1.3.14\n"}, "tool-versions"),
        ({"mise.toml": "[tools]\nbun = \"1.3.14\"\n"}, "mise"),
    ],
)
def test_older_explicit_declaration_fails(checker, monkeypatch, capsys, tmp_path, files, kind):
    for rel, text in files.items():
        write(tmp_path, rel, text)

    code, envelope = run(checker, monkeypatch, capsys, tmp_path, FakeNet(npm_latest()))

    assert code == 1
    assert envelope["status"] == "failed"
    assert (kind, "outdated") in statuses(envelope)


def test_version_file_on_latest_passes(checker, monkeypatch, capsys, tmp_path):
    write(tmp_path, ".github/workflows/ci.yml", setup_bun_workflow("        with:\n          bun-version-file: .bun-version\n"))
    write(tmp_path, ".bun-version", "1.4.2\n")
    write(tmp_path, ".tool-versions", "bun latest\n")
    write(tmp_path, ".mise.toml", "[tools]\nbun = \"latest\"\n")

    code, envelope = run(checker, monkeypatch, capsys, tmp_path, FakeNet(npm_latest()))

    assert code == 0, envelope
    assert all(status == "ok" for _, status in statuses(envelope))


def test_setup_bun_without_version_is_a_note_not_a_failure(checker, monkeypatch, capsys, tmp_path):
    write(tmp_path, ".github/workflows/ci.yml", setup_bun_workflow(""))
    net = FakeNet(npm_latest())

    code, envelope = run(checker, monkeypatch, capsys, tmp_path, net)

    assert code == 0
    assert statuses(envelope) == [("setup-bun", "implicit")]
    assert any("bun-version: latest" in step for step in envelope["next_steps"])
    assert net.calls == []


def test_unparseable_engines_range_is_an_error_entry(checker, monkeypatch, capsys, tmp_path):
    write(tmp_path, "package.json", json.dumps({"engines": {"bun": ">=banana"}}))

    code, envelope = run(checker, monkeypatch, capsys, tmp_path, FakeNet(npm_latest()))

    assert code == 1
    assert statuses(envelope) == [("engines", "error")]


@pytest.mark.parametrize(
    ("rel", "text", "kind"),
    [
        ("Dockerfile", "FROM oven/bun:1.3.14-alpine AS build\nRUN bun install\n", "dockerfile"),
        (
            "docker/release.Dockerfile",
            "ARG BUN_IMAGE=docker.io/oven/bun:1.3.14\nFROM --platform=$BUILDPLATFORM ${BUN_IMAGE} AS base\n",
            "dockerfile",
        ),
        ("Containerfile", "ARG BUN_TAG=1.3\nFROM oven/bun:$BUN_TAG\n", "dockerfile"),
        ("compose.yml", "services:\n  app:\n    image: \"oven/bun:1.2\"\n", "compose"),
        ("deploy/docker-compose.dev.yaml", "services:\n  app:\n    image: oven/bun:0-slim\n", "compose"),
        (
            ".github/workflows/ci.yml",
            "jobs:\n  test:\n    container:\n      image: oven/bun:1.3.14\n    steps:\n      - run: bun test\n",
            "workflow-image",
        ),
    ],
)
def test_older_image_tag_fails(checker, monkeypatch, capsys, tmp_path, rel, text, kind):
    write(tmp_path, rel, text)

    code, envelope = run(checker, monkeypatch, capsys, tmp_path, FakeNet(npm_latest()))

    assert code == 1, envelope
    assert (kind, "outdated") in statuses(envelope)


def test_current_version_tags_and_other_images_pass(checker, monkeypatch, capsys, tmp_path):
    write(
        tmp_path,
        "Dockerfile",
        "FROM oven/bun:1.4.2-alpine AS build\nFROM oven/bun:1.4\nFROM node:20\nFROM build AS final\n",
    )

    code, envelope = run(checker, monkeypatch, capsys, tmp_path, FakeNet(npm_latest()))

    assert code == 0, envelope
    assert statuses(envelope) == [("dockerfile", "ok"), ("dockerfile", "ok"), ("dockerfile", "node_usage")]


def hub_tag(tag: str) -> dict:
    return {
        HUB_TAG_URL + tag: {
            "name": tag,
            "digest": LATEST_INDEX_DIGEST,
            "images": [{"architecture": "amd64", "digest": LATEST_AMD64_DIGEST}],
        }
    }


def test_floating_tag_digest_of_an_older_bun_fails(checker, monkeypatch, capsys, tmp_path):
    write(tmp_path, "infrastructure/gateway/Dockerfile", f"FROM oven/bun:1@{OLD_DIGEST}\n")
    net = FakeNet({**npm_latest(), **hub_tag("1")})

    code, envelope = run(checker, monkeypatch, capsys, tmp_path, net)

    assert code == 1
    [entry] = envelope["data"]["declarations"]
    assert entry["status"] == "outdated"
    assert entry["reason"] == "digest_not_latest"
    assert HUB_TAG_URL + "1" in net.calls


@pytest.mark.parametrize("digest", [LATEST_INDEX_DIGEST, LATEST_AMD64_DIGEST])
def test_floating_tag_digest_of_the_latest_bun_passes(checker, monkeypatch, capsys, tmp_path, digest):
    write(tmp_path, "Dockerfile", f"FROM oven/bun:1-slim@{digest}\nFROM oven/bun@{digest} AS second\n")
    net = FakeNet({**npm_latest(), **hub_tag("1-slim"), **hub_tag("latest")})

    code, envelope = run(checker, monkeypatch, capsys, tmp_path, net)

    assert code == 0, envelope
    assert statuses(envelope) == [("dockerfile", "ok"), ("dockerfile", "ok")]
    assert net.calls.count(HUB_TAG_URL + "1-slim") == 1


def test_full_version_tag_with_digest_is_judged_by_its_tag(checker, monkeypatch, capsys, tmp_path):
    write(tmp_path, "Dockerfile", f"FROM oven/bun:1.3.14@{OLD_DIGEST}\n")
    net = FakeNet(npm_latest())

    code, envelope = run(checker, monkeypatch, capsys, tmp_path, net)

    assert code == 1
    assert statuses(envelope) == [("dockerfile", "outdated")]
    assert not any(url.startswith(HUB_TAG_URL) for url in net.calls)


def test_lookup_failure_with_explicit_declaration_is_a_typed_error(checker, monkeypatch, capsys, tmp_path):
    write(tmp_path, ".bun-version", "1.3.14\n")

    code, envelope = run(checker, monkeypatch, capsys, tmp_path, FakeNet({}))

    assert code == 2
    assert envelope["status"] == "error"
    assert [e["code"] for e in envelope["errors"]] == ["bun_lookup_failed"]
    assert envelope["data"]["latest"] == {}


def test_digest_lookup_failure_is_a_typed_error(checker, monkeypatch, capsys, tmp_path):
    write(tmp_path, "Dockerfile", f"FROM oven/bun:1@{OLD_DIGEST}\n")

    code, envelope = run(checker, monkeypatch, capsys, tmp_path, FakeNet(npm_latest()))

    assert code == 2
    assert [e["code"] for e in envelope["errors"]] == ["digest_lookup_failed"]


def test_no_explicit_declaration_never_looks_up_latest(checker, monkeypatch, capsys, tmp_path):
    write(tmp_path, ".github/workflows/ci.yml", WORKFLOW_LATEST)
    write(tmp_path, "Dockerfile", "FROM oven/bun:alpine\n")
    write(tmp_path, "package.json", json.dumps({"engines": {"bun": "*"}, "packageManager": "npm@10.0.0"}))
    net = FakeNet({})

    code, envelope = run(checker, monkeypatch, capsys, tmp_path, net)

    assert code == 0
    assert envelope["status"] == "ok"
    assert envelope["data"]["latest"] == {}
    assert net.calls == []


def test_latest_is_looked_up_once_per_run(checker, monkeypatch, capsys, tmp_path):
    write(tmp_path, ".bun-version", "1.4.2\n")
    write(tmp_path, ".tool-versions", "bun 1.4.2\n")
    write(tmp_path, "package.json", json.dumps({"packageManager": "bun@1.4.2", "engines": {"bun": "^1.4.0"}}))
    net = FakeNet(npm_latest())

    code, _ = run(checker, monkeypatch, capsys, tmp_path, net)

    assert code == 0
    assert net.calls == [NPM_URL]


def test_failed_lookup_is_not_retried_within_a_run(checker, monkeypatch, capsys, tmp_path):
    write(tmp_path, ".bun-version", "1.4.2\n")
    write(tmp_path, ".tool-versions", "bun 1.4.2\n")
    net = FakeNet({})

    code, _ = run(checker, monkeypatch, capsys, tmp_path, net)

    assert code == 2
    assert net.calls == [NPM_URL, GITHUB_URL]


def test_github_release_is_the_fallback_when_npm_fails(checker, monkeypatch, capsys, tmp_path):
    write(tmp_path, ".bun-version", "1.3.14\n")
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")
    net = FakeNet({NPM_URL: OSError("timed out"), GITHUB_URL: {"tag_name": "bun-v1.4.2", "prerelease": False}})

    code, envelope = run(checker, monkeypatch, capsys, tmp_path, net)

    assert code == 1
    assert envelope["data"]["latest"] == {"bun": "1.4.2"}
    assert net.headers[1].get("Authorization") == "Bearer test-token"


def test_latest_option_skips_the_lookup(checker, monkeypatch, capsys, tmp_path):
    write(tmp_path, ".bun-version", "1.4.2\n")
    net = FakeNet({})

    code, envelope = run(checker, monkeypatch, capsys, tmp_path, net, "--latest", "1.4.3")

    assert code == 1
    assert envelope["data"]["latest"] == {"bun": "1.4.3"}
    assert net.calls == []


def test_invalid_latest_option_is_a_usage_error(checker, monkeypatch, capsys, tmp_path):
    code, envelope = run(checker, monkeypatch, capsys, tmp_path, FakeNet({}), "--latest", "soon")

    assert code == 2
    assert [e["code"] for e in envelope["errors"]] == ["usage"]


def test_git_work_tree_scans_tracked_files_and_skips_installed_copies(checker, monkeypatch, capsys, tmp_path):
    import subprocess

    write(tmp_path, ".bun-version", "1.4.2\n")
    write(tmp_path, "node_modules/pkg/package.json", json.dumps({"packageManager": "bun@1.0.0"}))
    write(tmp_path, ".agents/standards/x/.bun-version", "1.0.0\n")
    write(tmp_path, "ignored/.bun-version", "1.0.0\n")
    write(tmp_path, ".gitignore", "ignored/\n")
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "add", "-f", ".bun-version", ".gitignore"], check=True)

    code, envelope = run(checker, monkeypatch, capsys, tmp_path, FakeNet(npm_latest()))

    assert code == 0, envelope
    assert [d["file"] for d in envelope["data"]["declarations"]] == [".bun-version"]


# --------------------------------------------------------------------------
# Rule 2: Node usages are reported, never failed
# --------------------------------------------------------------------------


def test_node_usages_are_reported_without_failing(checker, monkeypatch, capsys, tmp_path):
    write(
        tmp_path,
        "package.json",
        json.dumps({"scripts": {"test": "node --import tsx --test test/*.test.ts", "build": "tsc"}, "engines": {"node": ">=20"}}),
    )
    write(tmp_path, ".nvmrc", "22\n")
    write(tmp_path, "tools/.node-version", "22.1.0\n")
    write(
        tmp_path,
        ".github/workflows/ci.yml",
        "jobs:\n  t:\n    steps:\n      - uses: actions/setup-node@v4\n        with:\n          node-version: 22\n",
    )
    write(tmp_path, "Dockerfile", "FROM node:22-alpine\n")
    write(tmp_path, "compose.yaml", "services:\n  web:\n    image: docker.io/library/node:20\n")
    net = FakeNet({})

    code, envelope = run(checker, monkeypatch, capsys, tmp_path, net)

    assert code == 0, envelope
    assert envelope["status"] == "ok"
    assert net.calls == []
    usages = {kind for kind, status in statuses(envelope) if status == "node_usage"}
    assert usages == {"node-test-script", "engines-node", "node-version-file", "setup-node", "dockerfile", "compose"}
    assert len([s for _, s in statuses(envelope) if s == "node_usage"]) == 7
    setup_node = next(d for d in envelope["data"]["declarations"] if d["kind"] == "setup-node")
    assert "22" in setup_node["value"]
    assert any("Bun" in step for step in envelope["next_steps"])


# --------------------------------------------------------------------------
# Rule 3 and 4: Python patch, 3.14 minimum, uv, setup actions
# --------------------------------------------------------------------------

EOL_314 = "https://endoflife.date/api/python/3.14.json"
EOL_V1_314 = "https://endoflife.date/api/v1/products/python/releases/3.14"
PYPI_UV = "https://pypi.org/pypi/uv/json"
GITHUB_UV = "https://api.github.com/repos/astral-sh/uv/releases/latest"


def python_uv_latest() -> dict:
    return {
        EOL_314: {"cycle": "3.14", "latest": "3.14.8"},
        PYPI_UV: {"info": {"version": "0.12.23"}},
    }


def step(uses: str, with_lines: str = "") -> str:
    block = f"        with:\n{with_lines}" if with_lines else ""
    return f"jobs:\n  t:\n    steps:\n      - name: setup\n        uses: {uses}\n{block}      - run: make test\n"


def test_python_and_uv_following_the_rules_pass(checker, monkeypatch, capsys, tmp_path):
    write(tmp_path, ".python-version", "3.14\n")
    write(
        tmp_path,
        "pyproject.toml",
        '[project]\nname = "x"\nrequires-python = ">=3.14"\n\n[tool.uv]\nrequired-version = ">=0.9"\n',
    )
    write(tmp_path, "uv.toml", 'required-version = ">=0.12, <1"\n')
    write(tmp_path, ".tool-versions", "python 3.14.8\nuv latest\n")
    write(tmp_path, "mise.toml", '[tools]\npython = "3.14"\nuv = "0.12.23"\n')
    write(
        tmp_path,
        ".github/workflows/py.yml",
        step("actions/setup-python@v5", "          python-version: '3.14'\n          check-latest: true\n"),
    )
    write(tmp_path, ".github/workflows/uv.yml", step("astral-sh/setup-uv@v6", "          version: latest\n"))
    write(
        tmp_path,
        ".github/workflows/x.yml",
        step("actions/setup-python@v5", "          python-version: 3.x\n          check-latest: true\n"),
    )
    write(
        tmp_path,
        "Dockerfile",
        "FROM python:3.14-slim\nCOPY --from=ghcr.io/astral-sh/uv:0.12.23 /uv /uvx /bin/\nFROM ghcr.io/astral-sh/uv:python3.14-bookworm-slim\n",
    )
    net = FakeNet(python_uv_latest())

    code, envelope = run(checker, monkeypatch, capsys, tmp_path, net)

    assert code == 0, envelope
    assert all(status == "ok" for _, status in statuses(envelope)), statuses(envelope)
    assert envelope["data"]["latest"] == {"python3.14": "3.14.8", "uv": "0.12.23"}
    assert sorted(net.calls) == sorted([EOL_314, PYPI_UV])


@pytest.mark.parametrize(
    ("files", "kind", "reason"),
    [
        ({".python-version": "3.14.0\n"}, "python-version-file", "older_than_latest"),
        ({".python-version": "3.12\n"}, "python-version-file", "below_minimum"),
        ({"pyproject.toml": '[project]\nrequires-python = ">=3.12"\n'}, "requires-python", "below_minimum"),
        ({"pyproject.toml": '[project]\nrequires-python = "<4"\n'}, "requires-python", "below_minimum"),
        (
            {".github/workflows/ci.yml": step("actions/setup-python@v5", "          python-version: \"3.14.0\"\n")},
            "setup-python",
            "older_than_latest",
        ),
        (
            {
                ".github/workflows/ci.yml": step("actions/setup-python@v5", "          python-version-file: .python-version\n"),
                ".python-version": "3.13\n",
            },
            "setup-python",
            "below_minimum",
        ),
        ({".tool-versions": "python 3.14.2\n"}, "tool-versions", "older_than_latest"),
        ({".mise.toml": '[tools]\npython = "3.13"\n'}, "mise", "below_minimum"),
        ({"Dockerfile": "FROM python:3.12-slim\n"}, "dockerfile", "below_minimum"),
        ({"compose.yml": "services:\n  w:\n    image: python:3.14.1-alpine\n"}, "compose", "older_than_latest"),
        (
            {".github/workflows/ci.yml": step("astral-sh/setup-uv@v6", "          version: \"0.5.0\"\n")},
            "setup-uv",
            "older_than_latest",
        ),
        (
            {"pyproject.toml": '[project]\nrequires-python = ">=3.14"\n[tool.uv]\nrequired-version = "==0.9.0"\n'},
            "uv-required-version",
            "range_excludes_latest",
        ),
        ({"uv.toml": 'required-version = "<0.10"\n'}, "uv-required-version", "range_excludes_latest"),
        (
            {
                ".github/workflows/ci.yml": step("astral-sh/setup-uv@v6", "          version-file: uv.toml\n"),
                "uv.toml": 'required-version = "==0.9.0"\n',
            },
            "setup-uv",
            "range_excludes_latest",
        ),
        ({"Dockerfile": "FROM python:3.14\nCOPY --from=ghcr.io/astral-sh/uv:0.9.0 /uv /bin/\n"}, "dockerfile", "older_than_latest"),
        ({"Dockerfile": "FROM ghcr.io/astral-sh/uv:0.11-python3.14-bookworm\n"}, "dockerfile", "older_than_latest"),
        ({".tool-versions": "uv 0.9.0\n"}, "tool-versions", "older_than_latest"),
    ],
)
def test_older_python_or_uv_declaration_fails(checker, monkeypatch, capsys, tmp_path, files, kind, reason):
    for rel, text in files.items():
        write(tmp_path, rel, text)

    code, envelope = run(checker, monkeypatch, capsys, tmp_path, FakeNet(python_uv_latest()))

    assert code == 1, envelope
    assert envelope["status"] == "failed"
    assert any(
        d["kind"] == kind and d["status"] == "outdated" and d["reason"] == reason
        for d in envelope["data"]["declarations"]
    ), envelope["data"]["declarations"]


def test_python_minimum_needs_no_lookup(checker, monkeypatch, capsys, tmp_path):
    write(tmp_path, "pyproject.toml", '[project]\nrequires-python = ">=3.12"\n')
    write(tmp_path, ".python-version", "3.14\n")
    net = FakeNet({})

    code, envelope = run(checker, monkeypatch, capsys, tmp_path, net)

    assert code == 1
    assert net.calls == []
    assert envelope["errors"] == []


def test_setup_python_and_setup_uv_without_version_are_notes(checker, monkeypatch, capsys, tmp_path):
    write(tmp_path, ".github/workflows/py.yml", step("actions/setup-python@v5"))
    write(tmp_path, ".github/workflows/uv.yml", step("astral-sh/setup-uv@v6", "          enable-cache: true\n"))
    net = FakeNet({})

    code, envelope = run(checker, monkeypatch, capsys, tmp_path, net)

    assert code == 0
    assert sorted(statuses(envelope)) == [("setup-python", "implicit"), ("setup-uv", "implicit")]
    assert net.calls == []


def test_workflow_expression_is_a_note_not_a_failure(checker, monkeypatch, capsys, tmp_path):
    write(
        tmp_path,
        ".github/workflows/ci.yml",
        step("actions/setup-python@v5", "          python-version: ${{ matrix.python }}\n"),
    )

    code, envelope = run(checker, monkeypatch, capsys, tmp_path, FakeNet({}))

    assert code == 0
    assert statuses(envelope) == [("setup-python", "implicit")]


@pytest.mark.parametrize(
    ("files", "code_name"),
    [
        ({".python-version": "3.14.2\n"}, "python_lookup_failed"),
        ({".tool-versions": "uv 0.9.0\n"}, "uv_lookup_failed"),
    ],
)
def test_python_and_uv_lookup_failures_are_typed_errors(checker, monkeypatch, capsys, tmp_path, files, code_name):
    for rel, text in files.items():
        write(tmp_path, rel, text)

    code, envelope = run(checker, monkeypatch, capsys, tmp_path, FakeNet({}))

    assert code == 2
    assert [e["code"] for e in envelope["errors"]] == [code_name]


def test_uv_and_python_fallbacks(checker, monkeypatch, capsys, tmp_path):
    write(tmp_path, ".tool-versions", "uv 0.12.23\npython 3.14.8\n")
    net = FakeNet(
        {
            PYPI_UV: OSError("down"),
            GITHUB_UV: {"tag_name": "0.12.23", "prerelease": False},
            EOL_314: OSError("down"),
            EOL_V1_314: {"result": {"name": "3.14", "latest": {"name": "3.14.8"}}},
        }
    )

    code, envelope = run(checker, monkeypatch, capsys, tmp_path, net)

    assert code == 0, envelope
    assert envelope["data"]["latest"] == {"uv": "0.12.23", "python3.14": "3.14.8"}


def test_python_and_uv_are_looked_up_once_per_run(checker, monkeypatch, capsys, tmp_path):
    write(tmp_path, ".python-version", "3.14.8\n")
    write(tmp_path, ".tool-versions", "python 3.14.8\nuv 0.12.23\n")
    write(tmp_path, "mise.toml", '[tools]\npython = "3.14.8"\nuv = "0.12.23"\n')
    net = FakeNet(python_uv_latest())

    code, _ = run(checker, monkeypatch, capsys, tmp_path, net)

    assert code == 0
    assert sorted(net.calls) == sorted([EOL_314, PYPI_UV])


def test_latest_version_overrides_skip_lookups(checker, monkeypatch, capsys, tmp_path):
    write(tmp_path, ".tool-versions", "python 3.14.8\nuv 0.12.22\n")
    net = FakeNet({})

    code, envelope = run(
        checker, monkeypatch, capsys, tmp_path, net,
        "--latest-version", "python3.14=3.14.8", "--latest-version", "uv=0.12.23",
    )

    assert code == 1
    assert net.calls == []
    assert statuses(envelope) == [("tool-versions", "ok"), ("tool-versions", "outdated")]


# --------------------------------------------------------------------------
# Rule 5: stateful service images stay on the latest release of their line
# --------------------------------------------------------------------------


def hub_list(repo: str, name: str, tags: list, next_url=None) -> dict:
    url = f"{HUB}{repo}/tags?page_size=100&name={name}"
    return {url: {"results": [{"name": t, "digest": "sha256:" + "0" * 64} for t in tags], "next": next_url}}


QUAY_26 = (
    "https://quay.io/api/v1/repository/keycloak/keycloak/tag/"
    "?onlyActiveTags=true&limit=100&filter_tag_name=like:26.&page=1"
)


def stateful_net() -> dict:
    return {
        **hub_list("library/postgres", "16.", ["16.10", "16.10-alpine3.22", "16.9-alpine", "16.10-bookworm", "16.2"]),
        **hub_list("library/postgres", "14.", ["14.19", "14.19-alpine", "14.18"]),
        **hub_list("healthsamurai/aidboxone", "2608.", ["2608.5", "2608.4", "2608.2"]),
        **hub_list("healthsamurai/aidboxone", "2410.", ["2410.13", "2410.12"]),
        **hub_list("postgis/postgis", "16-3.", ["16-3.5", "16-3.5-alpine", "16-3.4-alpine", "16-3.6.0beta1"]),
        QUAY_26: {"tags": [{"name": "26.8"}, {"name": "26.8.1"}, {"name": "26.1.4"}, {"name": "26.9.0-nightly"}], "has_additional": False},
    }


def test_stateful_images_on_their_latest_line_release_pass(checker, monkeypatch, capsys, tmp_path):
    write(
        tmp_path,
        "compose.yaml",
        "services:\n"
        "  db:\n    image: postgres:16-alpine\n"
        "  db2:\n    image: postgres:16.10-alpine3.21\n"
        "  old:\n    image: postgres:14.19\n"
        "  aidbox:\n    image: healthsamurai/aidboxone:2608.5\n"
        "  oldline:\n    image: healthsamurai/aidboxone:2410.13\n"
        "  gis:\n    image: postgis/postgis:16-3.5\n"
        "  kc:\n    image: quay.io/keycloak/keycloak:26.8\n"
        "  cache:\n    image: redis:7-alpine\n",
    )
    net = FakeNet(stateful_net())

    code, envelope = run(checker, monkeypatch, capsys, tmp_path, net)

    assert code == 0, envelope
    assert all(status == "ok" for _, status in statuses(envelope)), statuses(envelope)
    assert len(statuses(envelope)) == 8


@pytest.mark.parametrize(
    "image",
    [
        "postgres:16.2",
        "postgres:16.9-alpine",
        "healthsamurai/aidboxone:2608.2",
        "postgis/postgis:16-3.4-alpine",
        "quay.io/keycloak/keycloak:26.1",
        "quay.io/keycloak/keycloak:26.8.0",
    ],
)
def test_stateful_image_older_than_its_line_fails(checker, monkeypatch, capsys, tmp_path, image):
    write(tmp_path, "compose.yml", f"services:\n  s:\n    image: {image}\n")

    code, envelope = run(checker, monkeypatch, capsys, tmp_path, FakeNet(stateful_net()))

    assert code == 1, envelope
    [entry] = envelope["data"]["declarations"]
    assert (entry["kind"], entry["status"], entry["reason"]) == ("compose", "outdated", "older_than_latest")


def test_stateful_tag_list_is_paginated(checker, monkeypatch, capsys, tmp_path):
    write(tmp_path, "compose.yml", "services:\n  s:\n    image: postgres:16.9\n")
    page2 = "https://hub.docker.com/v2/repositories/library/postgres/tags?page=2&page_size=100&name=16."
    net = FakeNet({**hub_list("library/postgres", "16.", ["16.9"], next_url=page2), page2: {"results": [{"name": "16.10"}], "next": None}})

    code, envelope = run(checker, monkeypatch, capsys, tmp_path, net)

    assert code == 1, envelope
    assert page2 in net.calls


def test_stateful_floating_tag_digest_is_compared_with_the_tag(checker, monkeypatch, capsys, tmp_path):
    current = "sha256:" + "c" * 64
    write(tmp_path, "compose.yml", f"services:\n  a:\n    image: postgres:18@{current}\n  b:\n    image: postgres:18-alpine@{OLD_DIGEST}\n")
    net = FakeNet(
        {
            f"{HUB}library/postgres/tags/18": {"digest": current, "images": []},
            f"{HUB}library/postgres/tags/18-alpine": {"digest": current, "images": []},
        }
    )

    code, envelope = run(checker, monkeypatch, capsys, tmp_path, net)

    assert code == 1
    assert [(d["status"], d.get("reason")) for d in envelope["data"]["declarations"]] == [
        ("ok", None),
        ("outdated", "digest_not_latest"),
    ]


def test_stateful_digest_without_version_line_is_a_note(checker, monkeypatch, capsys, tmp_path):
    write(tmp_path, "compose.yml", f"services:\n  a:\n    image: healthsamurai/aidboxone@{OLD_DIGEST}\n")
    net = FakeNet({})

    code, envelope = run(checker, monkeypatch, capsys, tmp_path, net)

    assert code == 0
    assert statuses(envelope) == [("compose", "implicit")]
    assert net.calls == []


def test_stateful_lookup_failure_is_a_typed_error(checker, monkeypatch, capsys, tmp_path):
    write(tmp_path, "compose.yml", "services:\n  s:\n    image: postgres:16.2\n")

    code, envelope = run(checker, monkeypatch, capsys, tmp_path, FakeNet({}))

    assert code == 2
    assert [e["code"] for e in envelope["errors"]] == ["image_lookup_failed"]


def test_stateful_override_skips_the_lookup(checker, monkeypatch, capsys, tmp_path):
    write(tmp_path, "compose.yml", "services:\n  s:\n    image: postgres:16.2\n  t:\n    image: postgres:16.10\n")
    net = FakeNet({})

    code, envelope = run(checker, monkeypatch, capsys, tmp_path, net, "--latest-version", "postgres:16=16.10")

    assert code == 1
    assert net.calls == []
    assert statuses(envelope) == [("compose", "outdated"), ("compose", "ok")]


# --------------------------------------------------------------------------
# Review repairs (library-core#239 review round 2)
# --------------------------------------------------------------------------

STANDARD = Path(__file__).resolve().parents[1]
LATEST_OVERRIDES = (
    "--latest-version", "bun=1.4.2",
    "--latest-version", "uv=0.12.23",
    "--latest-version", "python3.14=3.14.8",
)


def run_offline(checker, monkeypatch, capsys, root, net=None):
    return run(checker, monkeypatch, capsys, root, net or FakeNet({}), *LATEST_OVERRIDES)


def entries(envelope: dict) -> list[tuple[str, str, str | None]]:
    return [(d["kind"], d["status"], d.get("reason")) for d in envelope["data"]["declarations"]]


def test_f1_standard_reports_an_omitted_setup_version_as_implicit():
    bun = (STANDARD / "bun.md").read_text(encoding="utf-8")
    python = (STANDARD / "python.md").read_text(encoding="utf-8")
    check = (STANDARD / "check.md").read_text(encoding="utf-8")
    assert "is not allowed either" not in bun
    setup_bun_row = next(line for line in bun.splitlines() if line.startswith("| CI `setup-bun`"))
    assert "`implicit`" in setup_bun_row
    setup_python_row = next(line for line in python.splitlines() if line.startswith("| CI `setup-python`"))
    assert "check-latest: true" in setup_python_row and "`implicit`" in setup_python_row
    assert "rollout" in check


@pytest.mark.parametrize(
    ("rel", "text", "expected"),
    [
        ("Dockerfile", "FROM oven/bun:${BUN_VERSION:-1.3.14}\n", ("dockerfile", "outdated", "older_than_latest")),
        ("compose.yml", "services:\n  a:\n    image: ${BUN_IMAGE:-oven/bun:1.3.14}\n", ("compose", "outdated", "older_than_latest")),
        ("compose.yml", "services:\n  a:\n    image: ${BUN_IMAGE-oven/bun:1.4.2}\n", ("compose", "ok", None)),
        ("Dockerfile", "ARG V=1.4.2\nFROM oven/bun:${V:-1.3.14}\n", ("dockerfile", "ok", None)),
        ("Dockerfile", "FROM oven/bun:${V}\n", ("dockerfile", "error", "unparseable")),
    ],
)
def test_f2_variable_defaults_are_resolved_and_judged(checker, monkeypatch, capsys, tmp_path, rel, text, expected):
    write(tmp_path, rel, text)

    _, envelope = run_offline(checker, monkeypatch, capsys, tmp_path)

    assert entries(envelope) == [expected]


@pytest.mark.parametrize("rel", [".github/actions/setup/action.yml", ".forgejo/actions/env/bun/action.yaml"])
def test_f3_setup_steps_in_local_actions_are_scanned(checker, monkeypatch, capsys, tmp_path, rel):
    write(
        tmp_path,
        rel,
        "runs:\n  using: composite\n  steps:\n    - uses: oven-sh/setup-bun@v2\n      with:\n        bun-version: 1.3.14\n",
    )

    code, envelope = run_offline(checker, monkeypatch, capsys, tmp_path)

    assert code == 1
    assert entries(envelope) == [("setup-bun", "outdated", "older_than_latest")]


def test_f5_full_version_tag_with_digest_is_checked_by_digest(checker, monkeypatch, capsys, tmp_path):
    write(
        tmp_path,
        "Dockerfile",
        f"FROM oven/bun:1.4.2@{OLD_DIGEST} AS a\nFROM oven/bun:1.4.2@{LATEST_AMD64_DIGEST}\n",
    )
    write(tmp_path, "compose.yml", f"services:\n  db:\n    image: postgres:16.10@{OLD_DIGEST}\n")
    net = FakeNet(
        {
            **hub_tag("1.4.2"),
            **hub_list("library/postgres", "16.", ["16.10"]),
            f"{HUB}library/postgres/tags/16.10": {"digest": LATEST_INDEX_DIGEST, "images": []},
        }
    )

    code, envelope = run(checker, monkeypatch, capsys, tmp_path, net, *LATEST_OVERRIDES)

    assert code == 1
    assert sorted(entries(envelope), key=str) == sorted(
        [
            ("compose", "outdated", "digest_not_latest"),
            ("dockerfile", "outdated", "digest_not_latest"),
            ("dockerfile", "ok", None),
        ],
        key=str,
    )


def test_f5_full_version_digest_on_ghcr_is_a_note_and_lookup_failure_is_typed(checker, monkeypatch, capsys, tmp_path):
    write(tmp_path, "Dockerfile", f"FROM ghcr.io/astral-sh/uv:0.12.23@{OLD_DIGEST}\nFROM oven/bun:1.4.2@{OLD_DIGEST}\n")

    code, envelope = run_offline(checker, monkeypatch, capsys, tmp_path)

    assert code == 2
    assert entries(envelope)[0] == ("dockerfile", "implicit", None)
    assert [e["code"] for e in envelope["errors"]] == ["digest_lookup_failed"]


def test_f7_mise_local_bun_dependency_and_continued_from_are_scanned(checker, monkeypatch, capsys, tmp_path):
    write(tmp_path, "mise.local.toml", '[tools]\nbun = "1.3.14"\n')
    write(tmp_path, "package.json", json.dumps({"devDependencies": {"bun": "1.3.14"}, "dependencies": {"bun": "^1.4.0"}}))
    write(tmp_path, "Dockerfile", "FROM \\\n  oven/bun:1.3.14 \\\n  AS build\n")

    code, envelope = run_offline(checker, monkeypatch, capsys, tmp_path)

    assert code == 1
    found = {(d["file"], d["kind"], d["status"], d["line"]) for d in envelope["data"]["declarations"]}
    assert found == {
        ("Dockerfile", "dockerfile", "outdated", 1),
        ("mise.local.toml", "mise", "outdated", 2),
        ("package.json", "bun-dependency", "ok", 1),
        ("package.json", "bun-dependency", "outdated", 1),
    }


@pytest.mark.parametrize(
    ("rel", "text", "kind"),
    [
        (
            ".github/workflows/ci.yml",
            'jobs:\n  t:\n    steps:\n      - uses: oven-sh/setup-bun@v2\n        with: {"bun-version": "1.3.14"}\n',
            "setup-bun",
        ),
        (
            ".github/workflows/ci.yml",
            "jobs:\n  t:\n    steps:\n      - {uses: oven-sh/setup-bun@v2, with: {bun-version: 1.3.14}}\n",
            "setup-bun",
        ),
        ("compose.yml", "services: {a: {image: oven/bun:1.3.14}}\n", "compose"),
        (".github/workflows/ci.yml", "jobs:\n  t:\n    container: {image: 'oven/bun:1.3.14'}\n", "workflow-image"),
    ],
)
def test_f9_quoted_keys_and_flow_style_are_read(checker, monkeypatch, capsys, tmp_path, rel, text, kind):
    write(tmp_path, rel, text)

    code, envelope = run_offline(checker, monkeypatch, capsys, tmp_path)

    assert code == 1, envelope
    assert entries(envelope) == [(kind, "outdated", "older_than_latest")]


def test_f10_from_lines_use_global_args_and_stage_args_stay_local(checker, monkeypatch, capsys, tmp_path):
    write(tmp_path, "Dockerfile", "ARG V=1.4.2\nFROM oven/bun:$V AS a\nARG V=1.3.14\nFROM oven/bun:$V\n")
    write(tmp_path, "b.Dockerfile", "FROM alpine\nARG V=1.3.14\nFROM oven/bun:${V}\n")
    write(tmp_path, "c.Dockerfile", "ARG U=0.12.23\nFROM alpine\nARG U\nCOPY --from=ghcr.io/astral-sh/uv:$U /uv /bin/\n")

    _, envelope = run_offline(checker, monkeypatch, capsys, tmp_path)

    found = [(d["file"], d["value"], d["status"]) for d in envelope["data"]["declarations"]]
    assert found == [
        ("Dockerfile", "oven/bun:1.4.2", "ok"),
        ("Dockerfile", "oven/bun:1.4.2", "ok"),
        ("b.Dockerfile", "oven/bun:${V}", "error"),
        ("c.Dockerfile", "ghcr.io/astral-sh/uv:0.12.23", "ok"),
    ]


def test_f11_every_listed_version_is_judged(checker, monkeypatch, capsys, tmp_path):
    write(tmp_path, "mise.toml", '[tools]\nbun = ["1.4.2", "1.3.14"]\n')
    write(tmp_path, ".tool-versions", "bun 1.4.2 1.3.14\n")

    code, envelope = run_offline(checker, monkeypatch, capsys, tmp_path)

    assert code == 1
    assert sorted(entries(envelope)) == [
        ("mise", "ok", None),
        ("mise", "outdated", "older_than_latest"),
        ("tool-versions", "ok", None),
        ("tool-versions", "outdated", "older_than_latest"),
    ]


def test_f13_templated_images_are_judged_only_when_the_check_owns_them(checker, monkeypatch, capsys, tmp_path):
    write(tmp_path, "compose.yml", "services:\n  app:\n    image: registry.cognovis.de/platform/app:${APP_VERSION}\n  web:\n    image: node:${NODE_VERSION}\n")
    write(
        tmp_path,
        ".github/workflows/ci.yml",
        "jobs:\n  t:\n    container:\n      image: oven/bun:${{ matrix.bun }}\n    services:\n      app:\n        image: ghcr.io/cognovis/app:${{ github.sha }}\n",
    )
    write(tmp_path, "Dockerfile", "ARG BASE_TAG\nFROM registry.cognovis.de/base:${BASE_TAG}\n")

    code, envelope = run_offline(checker, monkeypatch, capsys, tmp_path)

    assert code == 0, envelope
    assert sorted(entries(envelope), key=str) == [
        ("compose", "node_usage", "bun_migration_candidate"),
        ("workflow-image", "implicit", None),
    ]


@pytest.mark.parametrize(
    ("spec", "expected"),
    [
        ("==3.14.0", ("outdated", "range_excludes_latest")),
        (">=3.14,<3.14.3", ("outdated", "range_excludes_latest")),
        ("==3.14.*", ("ok", None)),
        ("~=3.14.0", ("ok", None)),
    ],
)
def test_f14_requires_python_must_admit_the_latest_patch(checker, monkeypatch, capsys, tmp_path, spec, expected):
    write(tmp_path, "pyproject.toml", f'[project]\nname = "x"\nrequires-python = "{spec}"\n')

    _, envelope = run(checker, monkeypatch, capsys, tmp_path, FakeNet(python_uv_latest()))

    [entry] = envelope["data"]["declarations"]
    assert (entry["status"], entry.get("reason")) == expected


def test_f14_plain_minimum_needs_no_lookup(checker, monkeypatch, capsys, tmp_path):
    write(tmp_path, "pyproject.toml", '[project]\nname = "x"\nrequires-python = ">=3.14"\n')
    net = FakeNet({})

    code, _ = run(checker, monkeypatch, capsys, tmp_path, net)

    assert code == 0
    assert net.calls == []


@pytest.mark.parametrize(
    ("rel", "text", "kind"),
    [
        ("Dockerfile", "FROM ghcr.io/astral-sh/uv:0.12.23-python3.12-bookworm\n", "dockerfile"),
        ("Dockerfile", "FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim\n", "dockerfile"),
        ("Dockerfile", "FROM python:3.12t-slim\n", "dockerfile"),
        (".github/workflows/ci.yml", step("astral-sh/setup-uv@v6", "          python-version: '3.12'\n"), "setup-uv"),
    ],
)
def test_f15_embedded_python_versions_meet_the_minimum(checker, monkeypatch, capsys, tmp_path, rel, text, kind):
    write(tmp_path, rel, text)

    code, envelope = run_offline(checker, monkeypatch, capsys, tmp_path)

    assert code == 1, envelope
    assert (kind, "outdated", "below_minimum") in entries(envelope)


def test_f16_setup_python_without_check_latest_is_a_note(checker, monkeypatch, capsys, tmp_path):
    write(tmp_path, ".github/workflows/a.yml", step("actions/setup-python@v5", "          python-version: '3.14'\n"))
    write(
        tmp_path,
        ".github/workflows/b.yml",
        step("actions/setup-python@v5", "          python-version: '3.14'\n          check-latest: true\n"),
    )

    code, envelope = run_offline(checker, monkeypatch, capsys, tmp_path)

    assert code == 0
    a = [(d["status"], d["value"]) for d in envelope["data"]["declarations"] if d["file"].endswith("a.yml")]
    b = [d["status"] for d in envelope["data"]["declarations"] if d["file"].endswith("b.yml")]
    assert ("implicit", "check-latest: (not true)") in a
    assert b == ["ok"]


def test_f16_setup_uv_lowest_resolution_fails(checker, monkeypatch, capsys, tmp_path):
    write(
        tmp_path,
        ".github/workflows/ci.yml",
        step("astral-sh/setup-uv@v6", "          version: '>=0.5'\n          resolution-strategy: lowest\n"),
    )

    code, envelope = run_offline(checker, monkeypatch, capsys, tmp_path)

    assert code == 1
    assert ("setup-uv", "outdated", "lowest_resolution") in entries(envelope)


@pytest.mark.parametrize(
    "image",
    [
        "postgres",
        "postgres:latest",
        "postgres:alpine",
        "healthsamurai/aidboxone:edge",
        "healthsamurai/aidboxone:stable",
        "quay.io/keycloak/keycloak:nightly",
    ],
)
def test_f17_stateful_image_without_a_major_line_fails(checker, monkeypatch, capsys, tmp_path, image):
    write(tmp_path, "compose.yml", f"services:\n  s:\n    image: {image}\n")
    net = FakeNet({})

    code, envelope = run(checker, monkeypatch, capsys, tmp_path, net)

    assert code == 1
    assert entries(envelope) == [("compose", "outdated", "major_unpinned")]
    assert net.calls == []


def test_f17_stateful_channel_with_digest_stays_a_note(checker, monkeypatch, capsys, tmp_path):
    write(tmp_path, "compose.yml", f"services:\n  s:\n    image: postgres:latest@{OLD_DIGEST}\n")

    code, envelope = run(checker, monkeypatch, capsys, tmp_path, FakeNet({}))

    assert code == 0
    assert entries(envelope) == [("compose", "implicit", None)]


@pytest.mark.parametrize(
    ("with_lines", "expected"),
    [
        ("          version: '>=0.5'\n", ("ok", None)),
        ("          version: '>=0.5,<0.9'\n", ("outdated", "range_excludes_latest")),
    ],
)
def test_f18_setup_uv_version_ranges(checker, monkeypatch, capsys, tmp_path, with_lines, expected):
    write(tmp_path, ".github/workflows/ci.yml", step("astral-sh/setup-uv@v6", with_lines))

    _, envelope = run_offline(checker, monkeypatch, capsys, tmp_path)

    assert [(s, r) for _, s, r in entries(envelope)] == [expected]


@pytest.mark.parametrize(
    ("version", "expected"),
    [
        ("'>=3.14 <3.15'", ("ok", None)),
        ("'>=3.12'", ("ok", None)),
        ("'>=3.9 <3.14'", ("outdated", "below_minimum")),
        ("'3.14.0 - 3.14.2'", ("outdated", "range_excludes_latest")),
        ("pypy3.10", ("implicit", None)),
    ],
)
def test_f18_setup_python_ranges_and_pypy(checker, monkeypatch, capsys, tmp_path, version, expected):
    write(
        tmp_path,
        ".github/workflows/ci.yml",
        step("actions/setup-python@v5", f"          python-version: {version}\n          check-latest: true\n"),
    )

    _, envelope = run_offline(checker, monkeypatch, capsys, tmp_path)

    assert [(s, r) for _, s, r in entries(envelope)] == [expected]


def test_f18_requires_python_prerelease_bound(checker, monkeypatch, capsys, tmp_path):
    write(tmp_path, "pyproject.toml", '[project]\nname = "x"\nrequires-python = ">=3.14.0rc1"\n')

    code, envelope = run_offline(checker, monkeypatch, capsys, tmp_path)

    assert code == 0, envelope
    assert entries(envelope) == [("requires-python", "ok", None)]


@pytest.mark.parametrize(
    ("target", "text", "expected"),
    [
        ("pyproject.toml", '[project]\nname = "x"\n[dependency-groups]\ndev = ["pytest", "uv==0.9.0"]\n', ("outdated", "range_excludes_latest")),
        ("pyproject.toml", '[project]\nname = "x"\ndependencies = ["uv>=0.12"]\n', ("ok", None)),
        ("requirements-dev.txt", "fastapi==1.0\nuv==0.12.23  # pinned\n", ("ok", None)),
        ("requirements.txt", "uv==0.9.0\n", ("outdated", "range_excludes_latest")),
    ],
)
def test_f19_setup_uv_version_file_reads_uv_requirements(checker, monkeypatch, capsys, tmp_path, target, text, expected):
    write(tmp_path, f"ci/{target}", text)
    write(tmp_path, ".github/workflows/ci.yml", step("astral-sh/setup-uv@v6", f"          version-file: ci/{target}\n"))

    _, envelope = run_offline(checker, monkeypatch, capsys, tmp_path)

    setup = [(d["status"], d.get("reason")) for d in envelope["data"]["declarations"] if d["kind"] == "setup-uv"]
    assert setup == [expected]


def test_f20_setup_uv_version_file_is_relative_to_working_directory(checker, monkeypatch, capsys, tmp_path):
    write(
        tmp_path,
        ".github/workflows/ci.yml",
        step("astral-sh/setup-uv@v6", "          working-directory: backend\n          version-file: uv.toml\n"),
    )
    write(tmp_path, "backend/uv.toml", 'required-version = "==0.9.0"\n')

    _, envelope = run_offline(checker, monkeypatch, capsys, tmp_path)

    setup = [(d["status"], d.get("reason")) for d in envelope["data"]["declarations"] if d["kind"] == "setup-uv"]
    assert setup == [("outdated", "range_excludes_latest")]


@pytest.mark.parametrize(
    ("image", "expected"),
    [
        ("quay.io/keycloak/keycloak:26.7.5-0", ("outdated", "older_than_latest")),
        ("quay.io/keycloak/keycloak:26.8.1-0", ("ok", None)),
        ("python:3.14.0rc1", ("outdated", "older_than_latest")),
        ("postgres:16rc1", ("error", "unparseable")),
    ],
)
def test_f21_version_bearing_tags_are_not_floating(checker, monkeypatch, capsys, tmp_path, image, expected):
    write(tmp_path, "compose.yml", f"services:\n  s:\n    image: {image}\n")

    _, envelope = run(checker, monkeypatch, capsys, tmp_path, FakeNet(stateful_net()), *LATEST_OVERRIDES)

    [entry] = envelope["data"]["declarations"]
    assert (entry["status"], entry.get("reason")) == expected


def test_f22_direct_node_scripts_and_workflow_node_test_are_reported(checker, monkeypatch, capsys, tmp_path):
    write(tmp_path, "package.json", json.dumps({"scripts": {"start": "node dist/index.js", "lint": "eslint ."}}))
    write(
        tmp_path,
        ".github/workflows/ci.yml",
        "jobs:\n  t:\n    steps:\n      - run: node --test test/\n      - name: suite\n        run: |\n          npm ci\n          node --experimental-strip-types --test\n",
    )

    code, envelope = run(checker, monkeypatch, capsys, tmp_path, FakeNet({}))

    assert code == 0
    assert sorted(entries(envelope)) == [
        ("node-script", "node_usage", "bun_migration_candidate"),
        ("node-test-run", "node_usage", "bun_migration_candidate"),
        ("node-test-run", "node_usage", "bun_migration_candidate"),
    ]


def test_f23_postgis_line_includes_the_postgis_major(checker, monkeypatch, capsys, tmp_path):
    write(tmp_path, "compose.yml", "services:\n  gis:\n    image: postgis/postgis:16-3.5\n  old:\n    image: postgis/postgis:16-3.4\n")
    net = FakeNet(
        {
            **hub_list("postgis/postgis", "16-", ["16-4.0", "16-3.5", "16-3.4"]),
            **hub_list("postgis/postgis", "16-3.", ["16-3.5", "16-3.4"]),
        }
    )

    _, envelope = run(checker, monkeypatch, capsys, tmp_path, net)

    assert [(d["value"], d["status"]) for d in envelope["data"]["declarations"]] == [
        ("postgis/postgis:16-3.5", "ok"),
        ("postgis/postgis:16-3.4", "outdated"),
    ]


def test_f24_hitting_the_pagination_bound_is_a_typed_error(checker, monkeypatch, capsys, tmp_path):
    write(tmp_path, "compose.yml", "services:\n  s:\n    image: postgres:16.10\n")
    base = "https://hub.docker.com/v2/repositories/library/postgres/tags?page_size=100&name=16."
    pages = [base] + [f"{base}&page={n}" for n in range(2, 13)]
    responses = {url: {"results": [{"name": "16.10"}], "next": pages[i + 1]} for i, url in enumerate(pages[:-1])}

    code, envelope = run(checker, monkeypatch, capsys, tmp_path, FakeNet(responses))

    assert code == 2
    assert [e["code"] for e in envelope["errors"]] == ["image_lookup_failed"]


# --------------------------------------------------------------------------
# Review repairs (library-core#257)
# --------------------------------------------------------------------------

PYTHON_315 = ("--latest-version", "python3.15=3.15.3")


@pytest.mark.parametrize(
    ("version", "expected"),
    [
        ("'>=3.15.0 <3.15.2'", ("outdated", "range_excludes_latest")),
        ("'>=3.14 <3.15.2'", ("outdated", "range_excludes_latest")),
        ("'>=3.15.0 <3.15.4'", ("ok", None)),
        ("'>=3.14 <3.16'", ("ok", None)),
    ],
)
def test_setup_python_range_is_judged_against_its_newest_admitted_minor(
    checker, monkeypatch, capsys, tmp_path, version, expected
):
    write(
        tmp_path,
        ".github/workflows/ci.yml",
        step("actions/setup-python@v5", f"          python-version: {version}\n          check-latest: true\n"),
    )

    _, envelope = run(checker, monkeypatch, capsys, tmp_path, FakeNet({}), *LATEST_OVERRIDES, *PYTHON_315)

    assert [(s, r) for _, s, r in entries(envelope)] == [expected]


@pytest.mark.parametrize(
    ("spec", "expected"),
    [
        (">=3.15.0,<3.15.2", ("outdated", "range_excludes_latest")),
        (">=3.14,<3.15.2", ("outdated", "range_excludes_latest")),
        (">=3.14,<3.15.4", ("ok", None)),
        (">=3.14,<3.16", ("ok", None)),
    ],
)
def test_requires_python_range_is_judged_against_its_newest_admitted_minor(
    checker, monkeypatch, capsys, tmp_path, spec, expected
):
    write(tmp_path, "pyproject.toml", f'[project]\nname = "x"\nrequires-python = "{spec}"\n')

    _, envelope = run(checker, monkeypatch, capsys, tmp_path, FakeNet({}), *LATEST_OVERRIDES, *PYTHON_315)

    assert [(s, r) for _, s, r in entries(envelope)] == [expected]


@pytest.mark.parametrize(
    ("rel", "text"),
    [
        ("pyproject.toml", '[project]\nname = "x"\nrequires-python = ">=3.9\n'),
        ("uv.toml", 'required-version = "==0.9.0"\n[pip\n'),
        ("mise.toml", '[tools]\npython = "3.12"\npython = "3.14"\n'),
    ],
)
def test_malformed_toml_is_an_unparseable_error(checker, monkeypatch, capsys, tmp_path, rel, text):
    write(tmp_path, rel, text)

    code, envelope = run_offline(checker, monkeypatch, capsys, tmp_path)

    assert code == 1, envelope
    assert [(d["file"], s, r) for d, (_, s, r) in zip(envelope["data"]["declarations"], entries(envelope))] == [
        (rel, "error", "unparseable")
    ]


def test_malformed_toml_version_file_is_an_unparseable_error(checker, monkeypatch, capsys, tmp_path):
    write(tmp_path, "ci/uv.toml", 'required-version = "==0.9.0"\n[pip\n')
    write(tmp_path, ".github/workflows/ci.yml", step("astral-sh/setup-uv@v6", "          version-file: ci/uv.toml\n"))

    code, envelope = run_offline(checker, monkeypatch, capsys, tmp_path)

    assert code == 1, envelope
    setup = [(d["status"], d.get("reason")) for d in envelope["data"]["declarations"] if d["kind"] == "setup-uv"]
    assert setup == [("error", "unparseable")]


@pytest.mark.parametrize(
    ("uses", "with_lines", "kind"),
    [
        (
            "actions/setup-python@v5",
            "          python-version-file: ${{ matrix.version_file }}\n          check-latest: true\n",
            "setup-python",
        ),
        (
            "astral-sh/setup-uv@v6",
            "          working-directory: ${{ matrix.project }}\n          version-file: uv.toml\n",
            "setup-uv",
        ),
    ],
)
def test_expression_valued_version_file_is_an_implicit_note(
    checker, monkeypatch, capsys, tmp_path, uses, with_lines, kind
):
    write(tmp_path, ".github/workflows/ci.yml", step(uses, with_lines))

    code, envelope = run_offline(checker, monkeypatch, capsys, tmp_path)

    assert code == 0, envelope
    assert entries(envelope) == [(kind, "implicit", None)]


@pytest.mark.parametrize(
    ("target", "kept"),
    [
        ("https://objects.githubusercontent.com/releases/latest.json", False),
        ("https://api.github.com.evil.example/repos/oven-sh/bun/releases/latest", False),
        ("http://api.github.com/repos/oven-sh/bun/releases/latest", False),
        ("https://api.github.com/repositories/357728969/releases/latest", True),
    ],
)
def test_github_token_is_dropped_on_redirect_to_another_host(checker, target, kept):
    import urllib.request

    original = urllib.request.Request(GITHUB_URL, headers={"Authorization": "Bearer secret", "Accept": "x"})
    handler = checker.RedirectHandler()

    redirected = handler.redirect_request(original, None, 302, "Found", {}, target)

    headers = {k.lower(): v for k, v in redirected.header_items()}
    assert ("authorization" in headers) is kept
    assert headers["accept"] == "x"


def test_fetch_json_does_not_send_the_token_to_the_redirect_host(checker, monkeypatch):
    import http.server
    import threading

    for name in ("http_proxy", "HTTP_PROXY", "https_proxy", "HTTPS_PROXY", "all_proxy", "ALL_PROXY"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("no_proxy", "*")
    seen: dict[str, dict] = {}

    def serve(handle):
        server = http.server.HTTPServer(("127.0.0.1", 0), type("H", (http.server.BaseHTTPRequestHandler,), {
            "do_GET": handle, "log_message": lambda *a: None,
        }))
        threading.Thread(target=server.serve_forever, daemon=True).start()
        return server

    def target_get(self):
        seen["target"] = dict(self.headers)
        body = b'{"tag_name": "bun-v1.4.2"}'
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    target = serve(target_get)

    def origin_get(self):
        seen["origin"] = dict(self.headers)
        self.send_response(302)
        self.send_header("Location", f"http://localhost:{target.server_port}/release")
        self.send_header("Content-Length", "0")
        self.end_headers()

    origin = serve(origin_get)
    try:
        payload = checker.fetch_json(
            f"http://127.0.0.1:{origin.server_port}/latest", 5.0, {"Authorization": "Bearer secret"}
        )
    finally:
        origin.shutdown()
        target.shutdown()

    assert payload == {"tag_name": "bun-v1.4.2"}
    assert seen["origin"].get("Authorization") == "Bearer secret"
    assert "Authorization" not in seen["target"]


EOL_316 = "https://endoflife.date/api/python/3.16.json"
EOL_V1_316 = "https://endoflife.date/api/v1/products/python/releases/3.16"


def http_error(url: str, code: int):
    import urllib.error

    return urllib.error.HTTPError(url, code, "status", {}, None)


UNRELEASED_316 = {EOL_316: http_error(EOL_316, 404), EOL_V1_316: http_error(EOL_V1_316, 404)}


@pytest.mark.parametrize(
    ("version", "expected"),
    [
        ("'>=3.14 <3.16.1'", ("ok", None)),
        ("'>=3.15.0 <3.15.2 || >=3.16.0 <3.16.1'", ("outdated", "range_excludes_latest")),
    ],
)
def test_setup_python_range_falls_back_from_an_unreleased_newest_line(
    checker, monkeypatch, capsys, tmp_path, version, expected
):
    write(
        tmp_path,
        ".github/workflows/ci.yml",
        step("actions/setup-python@v5", f"          python-version: {version}\n          check-latest: true\n"),
    )

    code, envelope = run(
        checker, monkeypatch, capsys, tmp_path, FakeNet(UNRELEASED_316), *LATEST_OVERRIDES, *PYTHON_315
    )

    assert [(s, r) for _, s, r in entries(envelope)] == [expected]
    assert envelope["errors"] == []
    assert code == (0 if expected[0] == "ok" else 1)


@pytest.mark.parametrize(
    ("spec", "responses", "expected"),
    [
        (">=3.14,<=3.16", UNRELEASED_316, ("ok", None)),
        (">=3.14,!=3.15.3,<3.16.1", UNRELEASED_316, ("outdated", "range_excludes_latest")),
        (
            ">=3.14,<=3.16",
            {EOL_316: {"cycle": "3.16", "latest": "3.16.0a2"}, EOL_V1_316: http_error(EOL_V1_316, 404)},
            ("ok", None),
        ),
    ],
)
def test_requires_python_range_falls_back_from_an_unreleased_newest_line(
    checker, monkeypatch, capsys, tmp_path, spec, responses, expected
):
    write(tmp_path, "pyproject.toml", f'[project]\nname = "x"\nrequires-python = "{spec}"\n')

    _, envelope = run(checker, monkeypatch, capsys, tmp_path, FakeNet(responses), *LATEST_OVERRIDES, *PYTHON_315)

    assert [(s, r) for _, s, r in entries(envelope)] == [expected]
    assert envelope["errors"] == []


@pytest.mark.parametrize(
    "responses",
    [
        {EOL_316: OSError("down"), EOL_V1_316: http_error(EOL_V1_316, 404)},
        {EOL_316: http_error(EOL_316, 503), EOL_V1_316: http_error(EOL_V1_316, 404)},
    ],
)
def test_a_failing_newest_line_lookup_stays_a_lookup_error(checker, monkeypatch, capsys, tmp_path, responses):
    write(tmp_path, "pyproject.toml", '[project]\nname = "x"\nrequires-python = ">=3.14,<=3.16"\n')

    code, envelope = run(checker, monkeypatch, capsys, tmp_path, FakeNet(responses), *LATEST_OVERRIDES, *PYTHON_315)

    assert code == 2
    assert [(s, r) for _, s, r in entries(envelope)] == [("error", "python_lookup_failed")]
    assert [e["code"] for e in envelope["errors"]] == ["python_lookup_failed"]


@pytest.mark.parametrize(
    ("version", "expected"),
    [
        ("'>=3.14 <3.15.3 || >=3.15.4 <3.17'", ("outdated", "range_excludes_latest")),
        ("'>=3.14 <3.17'", ("ok", None)),
    ],
)
def test_setup_python_range_fully_admitting_an_unreleased_line_is_judged_on_the_released_one(
    checker, monkeypatch, capsys, tmp_path, version, expected
):
    write(
        tmp_path,
        ".github/workflows/ci.yml",
        step("actions/setup-python@v5", f"          python-version: {version}\n          check-latest: true\n"),
    )

    _, envelope = run(checker, monkeypatch, capsys, tmp_path, FakeNet(UNRELEASED_316), *LATEST_OVERRIDES, *PYTHON_315)

    assert [(s, r) for _, s, r in entries(envelope)] == [expected]
    assert envelope["errors"] == []


@pytest.mark.parametrize(
    ("spec", "expected"),
    [
        (">=3.14,!=3.15.3,<3.17", ("outdated", "range_excludes_latest")),
        (">=3.14,!=3.15.3", ("outdated", "range_excludes_latest")),
        (">=3.14,<3.17", ("ok", None)),
    ],
)
def test_requires_python_range_fully_admitting_an_unreleased_line_is_judged_on_the_released_one(
    checker, monkeypatch, capsys, tmp_path, spec, expected
):
    write(tmp_path, "pyproject.toml", f'[project]\nname = "x"\nrequires-python = "{spec}"\n')

    _, envelope = run(checker, monkeypatch, capsys, tmp_path, FakeNet(UNRELEASED_316), *LATEST_OVERRIDES, *PYTHON_315)

    assert [(s, r) for _, s, r in entries(envelope)] == [expected]
    assert envelope["errors"] == []


@pytest.mark.parametrize("version", ["'>=3.14'", "'^3.14'", "'>=3.14 <4'"])
def test_a_range_admitting_every_python_from_the_minimum_needs_no_lookup(
    checker, monkeypatch, capsys, tmp_path, version
):
    write(
        tmp_path,
        ".github/workflows/ci.yml",
        step("actions/setup-python@v5", f"          python-version: {version}\n          check-latest: true\n"),
    )
    net = FakeNet({})

    _, envelope = run(checker, monkeypatch, capsys, tmp_path, net, *LATEST_OVERRIDES)

    assert [(s, r) for _, s, r in entries(envelope)] == [("ok", None)]
    assert net.calls == []

from __future__ import annotations

import pytest

from timing_cli import serve
from timing_cli.config import Config


@pytest.fixture(autouse=True)
def reset_mcp_auth():
    try:
        yield
    finally:
        serve.mcp.auth = None


def test_http_transport_requires_bearer_token(monkeypatch):
    monkeypatch.setattr(serve, "load_config", lambda: Config())

    with pytest.raises(ValueError, match="HTTP transport requires"):
        serve.run_server(transport="http")


def test_http_transport_configures_auth(monkeypatch):
    calls = []

    def fake_run(*args, **kwargs):
        calls.append((args, kwargs))

    monkeypatch.setattr(serve, "load_config", lambda: Config(mcp_http_token="secret"))
    monkeypatch.setattr(serve.mcp, "run", fake_run)

    serve.run_server(transport="http", host="127.0.0.1", port=8321)

    assert calls == [((), {"transport": "http", "host": "127.0.0.1", "port": 8321})]
    assert isinstance(serve.mcp.auth, serve.StaticBearerTokenVerifier)

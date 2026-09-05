from __future__ import annotations

import plistlib
from unittest.mock import MagicMock, patch

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
    monkeypatch.delenv("TIMING_MCP_TOKEN", raising=False)
    monkeypatch.setattr(serve, "load_config", lambda: Config())

    with pytest.raises(ValueError, match="HTTP transport requires"):
        serve.run_server(transport="http")


def test_http_transport_configures_auth(monkeypatch):
    monkeypatch.delenv("TIMING_MCP_TOKEN", raising=False)
    calls = []

    def fake_run(*args, **kwargs):
        calls.append((args, kwargs))

    monkeypatch.setattr(serve, "load_config", lambda: Config(mcp_http_token="secret"))
    monkeypatch.setattr(serve.mcp, "run", fake_run)

    serve.run_server(transport="http", host="127.0.0.1", port=8321)

    assert calls == [((), {"transport": "http", "host": "127.0.0.1", "port": 8321})]
    assert isinstance(serve.mcp.auth, serve.StaticBearerTokenVerifier)


class TestLaunchAgentDeploy:
    """LaunchAgent install/uninstall for 'timing serve --transport http'."""

    def test_install_writes_launch_agent_plist(self, tmp_path, monkeypatch):
        fake_plist = tmp_path / "agent.plist"
        monkeypatch.setattr(serve, "LAUNCH_AGENT_PATH", fake_plist)
        monkeypatch.setattr(serve, "load_config", lambda: Config(mcp_http_token="secret"))

        with patch("timing_cli.serve.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="501", returncode=0)
            path = serve.install_launch_agent(host="127.0.0.1", port=8321)

        assert path == fake_plist
        assert fake_plist.exists()
        payload = plistlib.loads(fake_plist.read_bytes())
        assert payload["Label"] == "de.sussdorff.timing-serve"
        assert payload["LimitLoadToSessionType"] == "Aqua"
        assert payload["RunAtLoad"] is True
        assert payload["KeepAlive"] is True
        args = payload["ProgramArguments"]
        assert "serve" in args
        assert "--transport" in args
        assert "http" in args

    def test_install_without_token_raises(self, tmp_path, monkeypatch):
        fake_plist = tmp_path / "agent.plist"
        monkeypatch.setattr(serve, "LAUNCH_AGENT_PATH", fake_plist)
        monkeypatch.delenv("TIMING_MCP_TOKEN", raising=False)
        monkeypatch.setattr(serve, "load_config", lambda: Config())

        with pytest.raises(ValueError, match="HTTP transport requires"):
            serve.install_launch_agent()

        assert not fake_plist.exists()

    def test_uninstall_removes_plist(self, tmp_path, monkeypatch):
        fake_plist = tmp_path / "agent.plist"
        fake_plist.write_bytes(plistlib.dumps({"Label": "de.sussdorff.timing-serve"}))
        monkeypatch.setattr(serve, "LAUNCH_AGENT_PATH", fake_plist)

        with patch("timing_cli.serve.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="501", returncode=0)
            serve.uninstall_launch_agent()

        assert not fake_plist.exists()

    def test_uninstall_missing_plist_is_noop(self, tmp_path, monkeypatch):
        fake_plist = tmp_path / "agent.plist"
        monkeypatch.setattr(serve, "LAUNCH_AGENT_PATH", fake_plist)

        with patch("timing_cli.serve.subprocess.run") as mock_run:
            serve.uninstall_launch_agent()

        mock_run.assert_not_called()

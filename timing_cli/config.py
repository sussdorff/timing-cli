"""Configuration: database location, Web-API access, and classification rules.

Config is loaded from ``~/.config/timing-cli/config.toml`` when present, else
sensible defaults are used. The Web-API token can also come from the
``TIMING_API_KEY`` environment variable (which takes precedence).
"""

from __future__ import annotations

import os
import tomllib
from pathlib import Path

from pydantic import BaseModel, Field

# Default location of the Timing.app Core-Data store on macOS.
DEFAULT_DB_PATH = (
    Path.home()
    / "Library"
    / "Application Support"
    / "info.eurocomp.Timing2"
    / "SQLite.db"
)

DEFAULT_API_BASE_URL = "https://web.timingapp.com/api/v1"

CONFIG_PATH = Path.home() / ".config" / "timing-cli" / "config.toml"


class Rule(BaseModel):
    """A classification rule mapping app usage onto a project.

    A rule matches when every provided pattern matches (case-insensitive
    substring for ``app``/``bundle_id``, regex for ``title``/``path``). The
    first matching rule (in list order) wins.
    """

    project: str = Field(description="Target project title the match maps to")
    app: str | None = None
    bundle_id: str | None = None
    title: str | None = Field(default=None, description="Regex matched against the window title")
    path: str | None = Field(default=None, description="Regex matched against the document path")


class Config(BaseModel):
    """Runtime configuration for timing-cli."""

    db_path: Path = DEFAULT_DB_PATH
    api_base_url: str = DEFAULT_API_BASE_URL
    api_token: str | None = None
    mcp_http_token: str | None = None

    # Aggregation tuning (see analysis.aggregate).
    min_block_seconds: int = Field(
        default=120,
        description="Drop aggregated blocks shorter than this many seconds",
    )
    gap_merge_seconds: int = Field(
        default=300,
        description="Merge same-project slices separated by a gap up to this many seconds",
    )

    rules: list[Rule] = Field(default_factory=list)
    project_mappings: dict[str, str] = Field(default_factory=dict)

    def resolved_token(self) -> str | None:
        """Return the API token, preferring the environment variable."""
        return os.environ.get("TIMING_API_KEY") or self.api_token

    def resolved_mcp_http_token(self) -> str | None:
        """Return the MCP HTTP bearer token, preferring the environment variable."""
        return os.environ.get("TIMING_MCP_TOKEN") or self.mcp_http_token


def load_config(path: Path | None = None) -> Config:
    """Load configuration from disk, falling back to defaults.

    Unknown keys are ignored so the config format can evolve without breaking
    older files.
    """
    cfg_path = path or CONFIG_PATH
    if not cfg_path.exists():
        return Config()

    with cfg_path.open("rb") as fh:
        data = tomllib.load(fh)

    rules = [Rule(**r) for r in data.pop("rules", [])]
    known = {k: v for k, v in data.items() if k in Config.model_fields}
    if "db_path" in known:
        known["db_path"] = Path(known["db_path"]).expanduser()
    return Config(rules=rules, **known)

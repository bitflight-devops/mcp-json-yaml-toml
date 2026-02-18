"""MCP JSON/YAML/TOML - MCP server for JSON, YAML, and TOML configuration files."""

from __future__ import annotations

from mcp_json_yaml_toml.logging import configure_logging
from mcp_json_yaml_toml.version import __version__

configure_logging()

__all__ = ["__version__"]

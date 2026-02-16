"""MCP server for querying and modifying JSON, YAML, and TOML files.

Thin registration shell: FastMCP init, schema manager, tool imports, and main().
Tool logic lives in ``tools/``, business logic in ``services/``.
"""

from __future__ import annotations

import datetime

from fastmcp import FastMCP

from mcp_json_yaml_toml.schemas import SchemaManager

# ---------------------------------------------------------------------------
# Core objects — MUST be defined BEFORE tool module imports so that
# ``from mcp_json_yaml_toml.server import mcp`` resolves without error.
# ---------------------------------------------------------------------------
mcp = FastMCP("mcp-json-yaml-toml", mask_error_details=False)
schema_manager = SchemaManager()
_SERVER_START_TIME = datetime.datetime.now(datetime.UTC)

# ---------------------------------------------------------------------------
# Tool imports trigger @mcp.tool / @mcp.resource / @mcp.prompt registration.
# Tests access ``server.data_query``, ``server.data``, etc.
# ---------------------------------------------------------------------------
from mcp_json_yaml_toml.models.responses import SchemaResponse  # noqa: E402
from mcp_json_yaml_toml.tools.constraints import (  # noqa: E402
    constraint_list,
    constraint_validate,
    convert_to_schema,
    explain_config,
    get_constraint_definition,
    list_all_constraints,
    suggest_improvements,
)
from mcp_json_yaml_toml.tools.convert import data_convert, data_merge  # noqa: E402
from mcp_json_yaml_toml.tools.data import data  # noqa: E402
from mcp_json_yaml_toml.tools.diff import data_diff  # noqa: E402
from mcp_json_yaml_toml.tools.query import data_query  # noqa: E402
from mcp_json_yaml_toml.tools.schema import data_schema  # noqa: E402

# ---------------------------------------------------------------------------
# Explicit exports — public API only.
# ---------------------------------------------------------------------------
__all__ = [
    # Server state
    "_SERVER_START_TIME",
    # Models
    "SchemaResponse",
    # Tools
    "constraint_list",
    "constraint_validate",
    "convert_to_schema",
    "data",
    "data_convert",
    "data_diff",
    "data_merge",
    "data_query",
    "data_schema",
    # Prompts
    "explain_config",
    # Resources
    "get_constraint_definition",
    "list_all_constraints",
    # Core objects
    "main",
    "mcp",
    "schema_manager",
    "suggest_improvements",
]


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main() -> None:  # pragma: no cover
    """Entry point for the MCP server."""
    mcp.run()


if __name__ == "__main__":  # pragma: no cover
    main()

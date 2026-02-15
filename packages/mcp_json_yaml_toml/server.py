"""MCP server for querying and modifying JSON, YAML, and TOML files.

Thin registration shell: FastMCP init, schema manager, tool imports, and main().
Tool logic lives in ``tools/``, business logic in ``services/``.
"""

from __future__ import annotations

from fastmcp import FastMCP

from mcp_json_yaml_toml.schemas import SchemaManager

# ---------------------------------------------------------------------------
# Core objects — MUST be defined BEFORE tool module imports so that
# ``from mcp_json_yaml_toml.server import mcp`` resolves without error.
# ---------------------------------------------------------------------------
mcp = FastMCP("mcp-json-yaml-toml", mask_error_details=False)
schema_manager = SchemaManager()

# ---------------------------------------------------------------------------
# Re-exports for backward compatibility (models, services, tools).
# Tool imports also trigger @mcp.tool / @mcp.resource / @mcp.prompt
# registration.  Tests access ``server.data_query``, ``server.data``, etc.
# ---------------------------------------------------------------------------
from mcp_json_yaml_toml.models.responses import SchemaResponse  # noqa: E402
from mcp_json_yaml_toml.services.data_operations import (  # noqa: E402
    _build_query_response,
    _dispatch_delete_operation,
    _dispatch_get_operation,
    _dispatch_set_operation,
    _validate_and_write_content,
    is_schema,
)
from mcp_json_yaml_toml.services.pagination import (  # noqa: E402
    ADVISORY_PAGE_THRESHOLD,
    MAX_PRIMITIVE_DISPLAY_LENGTH,
    PAGE_SIZE_CHARS,
    _decode_cursor,
    _encode_cursor,
    _get_pagination_hint,
    _paginate_result,
    _summarize_structure,
)
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
from mcp_json_yaml_toml.tools.query import data_query  # noqa: E402
from mcp_json_yaml_toml.tools.schema import data_schema  # noqa: E402

# ---------------------------------------------------------------------------
# Explicit exports — tells mypy these names are part of the public API.
# ---------------------------------------------------------------------------
__all__ = [
    # Pagination re-exports (backward compat)
    "ADVISORY_PAGE_THRESHOLD",
    "MAX_PRIMITIVE_DISPLAY_LENGTH",
    "PAGE_SIZE_CHARS",
    # Models
    "SchemaResponse",
    # Service re-exports (backward compat)
    "_build_query_response",
    "_decode_cursor",
    "_dispatch_delete_operation",
    "_dispatch_get_operation",
    "_dispatch_set_operation",
    "_encode_cursor",
    "_get_pagination_hint",
    "_paginate_result",
    "_summarize_structure",
    "_validate_and_write_content",
    "constraint_list",
    "constraint_validate",
    "convert_to_schema",
    # Tools
    "data",
    "data_convert",
    "data_merge",
    "data_query",
    "data_schema",
    # Prompts
    "explain_config",
    "get_constraint_definition",
    "is_schema",
    # Resources
    "list_all_constraints",
    "main",
    # Core objects
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

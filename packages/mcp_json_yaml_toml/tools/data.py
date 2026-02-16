"""The ``data`` tool -- get, set, or delete data in JSON, YAML, and TOML files."""

from __future__ import annotations

from typing import Annotated, Literal, assert_never

from pydantic import Field

from mcp_json_yaml_toml.formats.base import resolve_file_path
from mcp_json_yaml_toml.models.responses import (  # noqa: TC001 — FastMCP resolves return type at runtime
    DataResponse,
    MutationResponse,
    SchemaResponse,
    ServerInfoResponse,
)
from mcp_json_yaml_toml.server import mcp, schema_manager
from mcp_json_yaml_toml.services.data_operations import (
    _dispatch_delete_operation,
    _dispatch_get_operation,
    _dispatch_set_operation,
)


@mcp.tool(
    timeout=60.0,
    annotations={
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
def data(
    file_path: Annotated[str, Field(description="Path to file")],
    operation: Annotated[
        Literal["get", "set", "delete"],
        Field(description="Operation: 'get', 'set', or 'delete'"),
    ],
    key_path: Annotated[
        str | None,
        Field(
            description="Dot-separated key path (required for set/delete, optional for get)"
        ),
    ] = None,
    value: Annotated[
        str | None,
        Field(description="Value to set as JSON string (required for operation='set')"),
    ] = None,
    value_type: Annotated[
        Literal["string", "number", "boolean", "null", "json"] | None,
        Field(
            description="How to interpret the value parameter for SET operations. "
            "'string': treat value as literal string (no JSON parsing). "
            "'number': parse value as JSON number. "
            "'boolean': parse value as JSON boolean. "
            "'null': set to null/None (value parameter ignored). "
            "'json' or None (default): parse value as JSON (current behavior, maintains backward compatibility)."
        ),
    ] = None,
    data_type: Annotated[
        Literal["data", "schema", "meta"],
        Field(description="Type for get: 'data', 'schema', or 'meta' (server info)"),
    ] = "data",
    return_type: Annotated[
        Literal["keys", "all"],
        Field(
            description="Return type for get: 'keys' (structure) or 'all' (full data)"
        ),
    ] = "all",
    output_format: Annotated[
        Literal["json", "yaml", "toml"] | None, Field(description="Output format")
    ] = None,
    cursor: Annotated[str | None, Field(description="Pagination cursor")] = None,
) -> DataResponse | SchemaResponse | MutationResponse | ServerInfoResponse:
    """Get, set, or delete data in JSON, YAML, or TOML files.

    Use when you need to get, set, or delete specific values or entire sections in a structured data file.

    Output contract: Returns {"success": bool, "result": Any, "file": str, ...}.
    Side effects: Modifies file on disk if operation is 'set' or 'delete'.
    Failure modes: FileNotFoundError if file missing. ToolError if format disabled or invalid JSON.

    Operations:
    - get: Retrieve data, schema, or structure
    - set: Update/create value at key_path (always writes to file)
    - delete: Remove key/element at key_path (always writes to file)
    """
    if data_type == "meta":
        from mcp_json_yaml_toml.services.get_operations import (  # noqa: PLC0415
            _handle_meta_get,
        )

        return _handle_meta_get()

    path = resolve_file_path(file_path)

    schema_info = schema_manager.get_schema_info_for_file(path)

    match operation:
        case "get":
            return _dispatch_get_operation(
                path,
                data_type,
                return_type,
                key_path,
                output_format,
                cursor,
                schema_info,
                schema_manager,
            )
        case "set":
            return _dispatch_set_operation(
                path, key_path, value, value_type, schema_info, schema_manager
            )
        case "delete":
            return _dispatch_delete_operation(
                path, key_path, schema_info, schema_manager
            )
        case _:
            assert_never(operation)
    return None

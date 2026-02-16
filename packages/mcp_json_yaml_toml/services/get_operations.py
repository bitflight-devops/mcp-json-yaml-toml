"""GET dispatch and handler logic for data operations.

Handles read-only data flow: file -> yq query -> format -> paginate -> response.
Extracted from data_operations.py (ARCH-06).
"""

from __future__ import annotations

import datetime
from typing import TYPE_CHECKING, Any, Literal, TypeGuard

import orjson
from fastmcp.exceptions import ToolError

from mcp_json_yaml_toml.backends.base import FormatType, YQExecutionError
from mcp_json_yaml_toml.backends.yq import execute_yq
from mcp_json_yaml_toml.config import require_format_enabled, validate_format
from mcp_json_yaml_toml.formats.base import (
    _detect_file_format,
    should_fallback_toml_to_json,
)
from mcp_json_yaml_toml.models.responses import (
    DataResponse,
    SchemaResponse,
    ServerInfoResponse,
)
from mcp_json_yaml_toml.services.pagination import (
    PAGE_SIZE_CHARS,
    _paginate_result,
    _summarize_structure,
)

if TYPE_CHECKING:
    from pathlib import Path

    from strong_typing.core import JsonType

    from mcp_json_yaml_toml.schemas import SchemaInfo, SchemaManager

__all__ = [
    "_dispatch_get_operation",
    "_handle_data_get_schema",
    "_handle_data_get_structure",
    "_handle_data_get_value",
    "_handle_meta_get",
    "is_schema",
]


def _handle_meta_get() -> ServerInfoResponse:
    """Handle GET operation with data_type='meta'.

    Returns server metadata: version, uptime, start time.
    No file I/O -- entirely in-memory.

    Returns:
        ServerInfoResponse with version, uptime_seconds, start_time_epoch.
    """
    import mcp_json_yaml_toml  # noqa: PLC0415 — lazy to avoid circular: server -> tools/data -> data_operations -> get_operations -> server
    from mcp_json_yaml_toml.server import _SERVER_START_TIME  # noqa: PLC0415

    now = datetime.datetime.now(datetime.UTC)
    uptime = (now - _SERVER_START_TIME).total_seconds()

    return ServerInfoResponse(
        success=True,
        file="-",
        version=mcp_json_yaml_toml.__version__,
        uptime_seconds=round(uptime, 2),
        start_time_epoch=round(_SERVER_START_TIME.timestamp(), 3),
    )


def is_schema(value: Any) -> TypeGuard[JsonType]:
    """Check if value is a valid Schema (dict)."""
    return isinstance(value, dict) and all(
        isinstance(key, str)
        and isinstance(item_value, (bool, int, float, str, dict, list))
        for key, item_value in value.items()
    )


def _handle_data_get_schema(
    path: Path, schema_manager: SchemaManager
) -> SchemaResponse:
    """Handle GET operation with data_type='schema'.

    Args:
        path: Path to configuration file
        schema_manager: Schema manager instance

    Returns:
        SchemaResponse model with schema information
    """
    schema_info = schema_manager.get_schema_info_for_file(path)
    schema_data = schema_manager.get_schema_for_file(path)

    if schema_data:
        return SchemaResponse(
            success=True,
            file=str(path),
            schema=schema_data,
            message="Schema found via Schema Store",
            schema_info=schema_info,
        )

    return SchemaResponse(
        success=False, file=str(path), message=f"No schema found for file: {path.name}"
    )


def _handle_data_get_structure(
    path: Path,
    key_path: str | None,
    input_format: FormatType,
    cursor: str | None,
    schema_info: SchemaInfo | None,
) -> DataResponse:
    """Handle GET operation with return_type='keys'.

    Args:
        path: Path to configuration file
        key_path: Optional key path to query
        input_format: File format type
        cursor: Optional pagination cursor
        schema_info: Optional schema information

    Returns:
        DataResponse with structure summary

    Raises:
        ToolError: If query fails
    """
    expression = (
        "."
        if not key_path
        else (f".{key_path}" if not key_path.startswith(".") else key_path)
    )
    try:
        result = execute_yq(
            expression,
            input_file=path,
            input_format=input_format,
            output_format=FormatType.JSON,
        )
        if result.data is None:
            return DataResponse(
                success=True,
                result=None,
                format="json",
                file=str(path),
                structure_summary="Empty or invalid data",
                schema_info=schema_info,
            )

        summary = _summarize_structure(result.data, max_depth=1, full_keys_mode=True)
        summary_str = orjson.dumps(summary, option=orjson.OPT_INDENT_2).decode()

        if len(summary_str) > PAGE_SIZE_CHARS or cursor is not None:
            pagination = _paginate_result(summary_str, cursor)
            return DataResponse(
                success=True,
                result=pagination["data"],
                format="json",
                file=str(path),
                paginated=True,
                nextCursor=pagination.get("nextCursor"),
            )
        return DataResponse(
            success=True,
            result=summary,
            format="json",
            file=str(path),
            schema_info=schema_info,
        )
    except YQExecutionError as e:
        raise ToolError(f"Query failed: {e}") from e


def _handle_data_get_value(
    path: Path,
    key_path: str,
    input_format: FormatType,
    output_fmt: FormatType,
    cursor: str | None,
    schema_info: SchemaInfo | None,
    output_format_explicit: bool = True,
) -> DataResponse:
    """Handle GET operation with return_type='all' for data values.

    Args:
        path: Path to configuration file
        key_path: Key path to query
        input_format: File format type
        output_fmt: Output format
        cursor: Optional pagination cursor
        schema_info: Optional schema information
        output_format_explicit: Whether output format was explicitly specified

    Returns:
        DataResponse with data value

    Raises:
        ToolError: If query fails
    """
    expression = f".{key_path}" if not key_path.startswith(".") else key_path

    try:
        result = execute_yq(
            expression,
            input_file=path,
            input_format=input_format,
            output_format=output_fmt,
        )
        result_str = (
            result.stdout
            if output_fmt != FormatType.JSON
            else orjson.dumps(result.data, option=orjson.OPT_INDENT_2).decode()
        )

        if len(result_str) > PAGE_SIZE_CHARS or cursor is not None:
            hint = None
            if isinstance(result.data, list):
                hint = "Result is a list. Use '.[start:end]' to slice or '. | length' to count."
            elif isinstance(result.data, dict):
                hint = "Result is an object. Use '.key' to select or '. | keys' to list keys."

            pagination = _paginate_result(result_str, cursor, advisory_hint=hint)
            return DataResponse(
                success=True,
                result=pagination["data"],
                format=output_fmt,
                file=str(path),
                paginated=True,
                nextCursor=pagination.get("nextCursor"),
                advisory=pagination.get("advisory"),
            )
        return DataResponse(
            success=True,
            result=result_str if output_fmt != FormatType.JSON else result.data,
            format=output_fmt,
            file=str(path),
            schema_info=schema_info,
        )
    except YQExecutionError as e:
        if should_fallback_toml_to_json(
            e, output_format_explicit, output_fmt, input_format
        ):
            return _handle_data_get_value(
                path,
                key_path,
                input_format,
                FormatType.JSON,
                cursor,
                schema_info,
                output_format_explicit=True,
            )
        raise ToolError(f"Query failed: {e}") from e


def _dispatch_get_operation(
    path: Path,
    data_type: Literal["data", "schema"],
    return_type: Literal["keys", "all"],
    key_path: str | None,
    output_format: Literal["json", "yaml", "toml"] | None,
    cursor: str | None,
    schema_info: SchemaInfo | None,
    schema_manager: SchemaManager | None = None,
) -> DataResponse | SchemaResponse:
    """Dispatch GET operation to appropriate handler.

    Args:
        path: Path to configuration file
        data_type: Type of request (data or schema)
        return_type: Return type (keys or all)
        key_path: Optional key path
        output_format: Optional output format
        cursor: Optional pagination cursor
        schema_info: Optional schema information
        schema_manager: Schema manager instance for schema operations

    Returns:
        DataResponse or SchemaResponse from handler

    Raises:
        ToolError: If format disabled or validation fails
    """
    if data_type == "schema":
        if schema_manager is None:
            raise ToolError("schema_manager is required for schema operations")
        return _handle_data_get_schema(path, schema_manager)

    input_format = _detect_file_format(path)
    require_format_enabled(input_format)

    # Track whether output format was explicitly provided
    output_format_explicit = output_format is not None

    if output_format is None:
        output_fmt: FormatType = input_format
    else:
        output_fmt = validate_format(output_format)

    if return_type == "keys":
        return _handle_data_get_structure(
            path, key_path, input_format, cursor, schema_info
        )

    if key_path is None:
        raise ToolError(
            "key_path is required when operation='get' and data_type='data'"
        )

    return _handle_data_get_value(
        path,
        key_path,
        input_format,
        output_fmt,
        cursor,
        schema_info,
        output_format_explicit,
    )

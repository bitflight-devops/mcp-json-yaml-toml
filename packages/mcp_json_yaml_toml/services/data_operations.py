"""Data operations business logic extracted from server.py.

Contains all CRUD handler logic: dispatchers, data get/set/delete handlers,
query response builder, write validation, and type guards.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal, TypeGuard

import orjson
from fastmcp.exceptions import ToolError

from mcp_json_yaml_toml.config import require_format_enabled, validate_format
from mcp_json_yaml_toml.formats.base import (
    _detect_file_format,
    _parse_content_for_validation,
    _parse_set_value,
    should_fallback_toml_to_json,
)
from mcp_json_yaml_toml.models.responses import DataResponse, SchemaResponse
from mcp_json_yaml_toml.services.pagination import (
    PAGE_SIZE_CHARS,
    _get_pagination_hint,
    _paginate_result,
    _summarize_structure,
)
from mcp_json_yaml_toml.services.schema_validation import _validate_against_schema
from mcp_json_yaml_toml.toml_utils import delete_toml_key, set_toml_value
from mcp_json_yaml_toml.yaml_optimizer import optimize_yaml_file
from mcp_json_yaml_toml.yq_wrapper import FormatType, YQExecutionError, execute_yq

if TYPE_CHECKING:
    from pathlib import Path

    from strong_typing.core import JsonType

    from mcp_json_yaml_toml.schemas import SchemaInfo, SchemaManager

__all__ = [
    "_build_query_response",
    "_delete_toml_key_handler",
    "_delete_yq_key_handler",
    "_dispatch_delete_operation",
    "_dispatch_get_operation",
    "_dispatch_set_operation",
    "_handle_data_delete",
    "_handle_data_get_schema",
    "_handle_data_get_structure",
    "_handle_data_get_value",
    "_handle_data_set",
    "_optimize_yaml_if_needed",
    "_set_toml_value_handler",
    "_validate_and_write_content",
    "is_schema",
]


def _validate_and_write_content(
    path: Path, content: str, schema_path: Path | None, input_format: FormatType | str
) -> None:
    """Validate content against schema (if present) and write to file.

    Args:
        path: Target file path
        content: New file content string
        schema_path: Path to schema file or None
        input_format: File format (json, yaml, toml)

    Raises:
        ToolError: If validation fails
    """
    if schema_path:
        validation_data = _parse_content_for_validation(content, input_format)
        if validation_data is not None:
            is_valid, msg = _validate_against_schema(validation_data, schema_path)
            if not is_valid:
                raise ToolError(f"Schema validation failed: {msg}")

    path.write_text(content, encoding="utf-8")


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
) -> dict[str, Any]:
    """Handle GET operation with return_type='keys'.

    Args:
        path: Path to configuration file
        key_path: Optional key path to query
        input_format: File format type
        cursor: Optional pagination cursor
        schema_info: Optional schema information

    Returns:
        Response dict with structure summary

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
        response: dict[str, Any]
        if result.data is None:
            response = {
                "success": True,
                "result": None,
                "format": "json",
                "file": str(path),
                "structure_summary": "Empty or invalid data",
            }
            if schema_info:
                response["schema_info"] = schema_info
            return response

        summary = _summarize_structure(result.data, max_depth=1, full_keys_mode=True)
        summary_str = orjson.dumps(summary, option=orjson.OPT_INDENT_2).decode()

        if len(summary_str) > PAGE_SIZE_CHARS or cursor is not None:
            pagination = _paginate_result(summary_str, cursor)
            response = {
                "success": True,
                "result": pagination["data"],
                "format": "json",
                "file": str(path),
                "paginated": True,
            }
            if "nextCursor" in pagination:
                response["nextCursor"] = pagination["nextCursor"]
            return response
        response = {
            "success": True,
            "result": summary,
            "format": "json",
            "file": str(path),
        }
        if schema_info:
            response["schema_info"] = schema_info
    except YQExecutionError as e:
        raise ToolError(f"Query failed: {e}") from e
    else:
        return response


def _handle_data_get_value(
    path: Path,
    key_path: str,
    input_format: FormatType,
    output_fmt: FormatType,
    cursor: str | None,
    schema_info: SchemaInfo | None,
    output_format_explicit: bool = True,
) -> dict[str, Any]:
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
        Response dict with data value

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
            if output_fmt != "json"
            else orjson.dumps(result.data, option=orjson.OPT_INDENT_2).decode()
        )

        if len(result_str) > PAGE_SIZE_CHARS or cursor is not None:
            hint = None
            if isinstance(result.data, list):
                hint = "Result is a list. Use '.[start:end]' to slice or '. | length' to count."
            elif isinstance(result.data, dict):
                hint = "Result is an object. Use '.key' to select or '. | keys' to list keys."

            pagination = _paginate_result(result_str, cursor, advisory_hint=hint)
            response = {
                "success": True,
                "result": pagination["data"],
                "format": output_fmt,
                "file": str(path),
                "paginated": True,
            }
            if "nextCursor" in pagination:
                response["nextCursor"] = pagination["nextCursor"]
            if "advisory" in pagination:
                response["advisory"] = pagination["advisory"]
            return response
        response = {
            "success": True,
            "result": result_str if output_fmt != "json" else result.data,
            "format": output_fmt,
            "file": str(path),
        }
        if schema_info:
            response["schema_info"] = schema_info
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
    else:
        return response


def _set_toml_value_handler(
    path: Path,
    key_path: str,
    parsed_value: Any,
    schema_info: SchemaInfo | None,
    schema_path: Path | None = None,
) -> dict[str, Any]:
    """Handle TOML set operation.

    Args:
        path: Path to configuration file
        key_path: Dot-notation key path to set
        parsed_value: Parsed value to set
        schema_info: Optional schema information
        schema_path: Optional path to schema file for validation

    Returns:
        Response dict with operation result
    """
    try:
        modified_toml = set_toml_value(path, key_path, parsed_value)
        _validate_and_write_content(path, modified_toml, schema_path, "toml")

        response = {
            "success": True,
            "result": "File modified successfully",
            "file": str(path),
        }
        if schema_info:
            response["schema_info"] = schema_info
    except Exception as e:
        if isinstance(e, ToolError):
            raise
        raise ToolError(f"TOML set operation failed: {e}") from e
    else:
        return response


def _optimize_yaml_if_needed(path: Path) -> bool:
    """Optimize YAML file with anchors if applicable.

    Args:
        path: Path to YAML file

    Returns:
        True if optimization was applied, False otherwise
    """
    original_content = path.read_text(encoding="utf-8")
    if "&" not in original_content and "*" not in original_content:
        return False

    reparse_result = execute_yq(
        ".",
        input_file=path,
        input_format=FormatType.YAML,
        output_format=FormatType.JSON,
    )
    if reparse_result.data is None:
        return False

    optimized_yaml = optimize_yaml_file(reparse_result.data)
    if optimized_yaml:
        path.write_text(optimized_yaml, encoding="utf-8")
        return True
    return False


def _handle_data_set(
    path: Path,
    key_path: str,
    value: str | None,
    value_type: Literal["string", "number", "boolean", "null", "json"] | None,
    input_format: FormatType,
    schema_info: SchemaInfo | None,
    schema_manager: SchemaManager | None = None,
) -> dict[str, Any]:
    """Handle SET operation.

    Args:
        path: Path to configuration file
        key_path: Key path to set
        value: Value to set (interpretation depends on value_type)
        value_type: How to interpret the value parameter
        input_format: File format type
        schema_info: Optional schema information
        schema_manager: Schema manager instance for schema path lookup

    Returns:
        Response dict with operation result

    Raises:
        ToolError: If operation fails
    """
    parsed_value = _parse_set_value(value, value_type)

    # Validating before write (Phase 9)
    schema_path: Path | None = None
    if schema_info and schema_manager is not None:
        schema_path = schema_manager.get_schema_path_for_file(path)

    if input_format == "toml":
        return _set_toml_value_handler(
            path, key_path, parsed_value, schema_info, schema_path
        )

    # YAML/JSON use yq.
    yq_value = orjson.dumps(parsed_value).decode()
    expression = (
        f".{key_path} = {yq_value}"
        if not key_path.startswith(".")
        else f"{key_path} = {yq_value}"
    )

    try:
        # Dry run - get modified content
        result = execute_yq(
            expression,
            input_file=path,
            input_format=input_format,
            output_format=input_format,
            in_place=False,
        )

        _validate_and_write_content(path, result.stdout, schema_path, input_format)

    except YQExecutionError as e:
        raise ToolError(f"Set operation failed: {e}") from e
    except Exception as e:
        if isinstance(e, ToolError):
            raise
        raise ToolError(f"Set operation failed: {e}") from e
    else:
        optimized = False
        if input_format == "yaml":
            optimized = _optimize_yaml_if_needed(path)

        response = {
            "success": True,
            "result": "File modified successfully",
            "file": str(path),
        }

        if optimized:
            response["optimized"] = True
            response["message"] = "File modified and optimized with YAML anchors"

        if schema_info:
            response["schema_info"] = schema_info

        return response


def _delete_toml_key_handler(
    path: Path, key_path: str, schema_path: Path | None, schema_info: SchemaInfo | None
) -> dict[str, Any]:
    """Handle TOML delete operation.

    Args:
        path: Path to file
        key_path: Key path to delete
        schema_path: Optional path to schema file
        schema_info: Optional schema information

    Returns:
        Response dict with operation result

    Raises:
        ToolError: If operation fails
    """
    try:
        modified_toml = delete_toml_key(path, key_path)
        _validate_and_write_content(path, modified_toml, schema_path, "toml")
    except KeyError as e:
        raise ToolError(f"TOML delete operation failed: {e}") from e
    except ToolError:
        raise
    except Exception as e:
        raise ToolError(f"TOML delete operation failed: {e}") from e

    response: dict[str, Any] = {
        "success": True,
        "result": "File modified successfully",
        "file": str(path),
    }
    if schema_info:
        response["schema_info"] = schema_info
    return response


def _delete_yq_key_handler(
    path: Path,
    key_path: str,
    input_format: FormatType,
    schema_path: Path | None,
    schema_info: SchemaInfo | None,
) -> dict[str, Any]:
    """Handle YAML/JSON delete operation using yq.

    Args:
        path: Path to file
        key_path: Key path to delete
        input_format: File format type
        schema_path: Optional path to schema file
        schema_info: Optional schema information

    Returns:
        Response dict with operation result

    Raises:
        ToolError: If operation fails
    """
    expression = (
        f"del(.{key_path})" if not key_path.startswith(".") else f"del({key_path})"
    )

    try:
        result = execute_yq(
            expression,
            input_file=path,
            input_format=input_format,
            output_format=input_format,
            in_place=False,
        )
        _validate_and_write_content(path, result.stdout, schema_path, input_format)
    except YQExecutionError as e:
        raise ToolError(f"Delete operation failed: {e}") from e
    except ToolError:
        raise
    except Exception as e:
        raise ToolError(f"Delete operation failed: {e}") from e

    response: dict[str, Any] = {
        "success": True,
        "result": "File modified successfully",
        "file": str(path),
    }
    if schema_info:
        response["schema_info"] = schema_info
    return response


def _handle_data_delete(
    path: Path,
    key_path: str,
    input_format: FormatType,
    schema_info: SchemaInfo | None,
    schema_manager: SchemaManager | None = None,
) -> dict[str, Any]:
    """Handle DELETE operation.

    Args:
        path: Path to configuration file
        key_path: Key path to delete
        input_format: File format type
        schema_info: Optional schema information
        schema_manager: Schema manager instance for schema path lookup

    Returns:
        Response dict with operation result

    Raises:
        ToolError: If operation fails
    """
    schema_path: Path | None = None
    if schema_info and schema_manager is not None:
        schema_path = schema_manager.get_schema_path_for_file(path)

    if input_format == "toml":
        return _delete_toml_key_handler(path, key_path, schema_path, schema_info)

    return _delete_yq_key_handler(
        path, key_path, input_format, schema_path, schema_info
    )


def _dispatch_get_operation(
    path: Path,
    data_type: Literal["data", "schema"],
    return_type: Literal["keys", "all"],
    key_path: str | None,
    output_format: Literal["json", "yaml", "toml"] | None,
    cursor: str | None,
    schema_info: SchemaInfo | None,
    schema_manager: SchemaManager | None = None,
) -> dict[str, Any]:
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
        Response dict from handler

    Raises:
        ToolError: If format disabled or validation fails
    """
    if data_type == "schema":
        if schema_manager is None:
            raise ToolError("schema_manager is required for schema operations")
        # Return dict representation of Pydantic model
        return _handle_data_get_schema(path, schema_manager).model_dump(
            exclude_none=True, by_alias=True
        )

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


def _dispatch_set_operation(
    path: Path,
    key_path: str | None,
    value: str | None,
    value_type: Literal["string", "number", "boolean", "null", "json"] | None,
    schema_info: SchemaInfo | None,
    schema_manager: SchemaManager | None = None,
) -> dict[str, Any]:
    """Dispatch SET operation to handler.

    Args:
        path: Path to configuration file
        key_path: Key path to set
        value: JSON string value
        value_type: How to interpret the value parameter
        schema_info: Optional schema information
        schema_manager: Schema manager instance for schema path lookup

    Returns:
        Response dict from handler

    Raises:
        ToolError: If validation fails or format disabled
    """
    if key_path is None:
        raise ToolError("key_path is required for operation='set'")
    if value is None and value_type != "null":
        raise ToolError(
            "value is required for operation='set' (except when value_type='null')"
        )

    input_format = _detect_file_format(path)
    require_format_enabled(input_format)

    return _handle_data_set(
        path, key_path, value, value_type, input_format, schema_info, schema_manager
    )


def _dispatch_delete_operation(
    path: Path,
    key_path: str | None,
    schema_info: SchemaInfo | None,
    schema_manager: SchemaManager | None = None,
) -> dict[str, Any]:
    """Dispatch DELETE operation to handler.

    Args:
        path: Path to configuration file
        key_path: Key path to delete
        schema_info: Optional schema information
        schema_manager: Schema manager instance for schema path lookup

    Returns:
        Response dict from handler

    Raises:
        ToolError: If validation fails or format disabled
    """
    if key_path is None:
        raise ToolError("key_path is required for operation='delete'")

    input_format = _detect_file_format(path)
    require_format_enabled(input_format)

    return _handle_data_delete(
        path, key_path, input_format, schema_info, schema_manager
    )


def _build_query_response(
    result: Any, output_format: FormatType, path: Path, cursor: str | None
) -> DataResponse:
    """Build response for data_query.

    Args:
        result: YQ execution result
        output_format: Output format
        path: File path
        cursor: Pagination cursor

    Returns:
        DataResponse model instance
    """
    result_str = (
        result.stdout
        if output_format != "json"
        else orjson.dumps(result.data, option=orjson.OPT_INDENT_2).decode()
    )

    if len(result_str) > PAGE_SIZE_CHARS or cursor is not None:
        hint = _get_pagination_hint(result.data)
        pagination = _paginate_result(result_str, cursor, advisory_hint=hint)
        return DataResponse(
            success=True,
            result=pagination["data"],
            format=output_format,
            file=str(path),
            paginated=True,
            nextCursor=pagination.get("nextCursor"),
            advisory=pagination.get("advisory"),
        )

    return DataResponse(
        success=True,
        result=result_str if output_format != "json" else result.data,
        format=output_format,
        file=str(path),
    )

"""SET/DELETE dispatch and handler logic for data operations.

Handles the write flow: parse value -> execute mutation -> validate -> write -> optimize.
Extracted from data_operations.py (ARCH-06).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal

import orjson
from fastmcp.exceptions import ToolError

from mcp_json_yaml_toml.backends.base import FormatType, YQExecutionError
from mcp_json_yaml_toml.backends.yq import execute_yq
from mcp_json_yaml_toml.config import require_format_enabled
from mcp_json_yaml_toml.formats.base import (
    _detect_file_format,
    _parse_content_for_validation,
    _parse_set_value,
)
from mcp_json_yaml_toml.models.responses import MutationResponse
from mcp_json_yaml_toml.services.schema_validation import _validate_against_schema
from mcp_json_yaml_toml.toml_utils import delete_toml_key, set_toml_value
from mcp_json_yaml_toml.yaml_optimizer import optimize_yaml_file

if TYPE_CHECKING:
    from pathlib import Path

    from mcp_json_yaml_toml.schemas import SchemaInfo, SchemaManager

__all__ = [
    "_delete_toml_key_handler",
    "_delete_yq_key_handler",
    "_dispatch_delete_operation",
    "_dispatch_set_operation",
    "_handle_data_delete",
    "_handle_data_set",
    "_optimize_yaml_if_needed",
    "_set_toml_value_handler",
    "_validate_and_write_content",
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


def _set_toml_value_handler(
    path: Path,
    key_path: str,
    parsed_value: Any,
    schema_info: SchemaInfo | None,
    schema_path: Path | None = None,
) -> MutationResponse:
    """Handle TOML set operation.

    Args:
        path: Path to configuration file
        key_path: Dot-notation key path to set
        parsed_value: Parsed value to set
        schema_info: Optional schema information
        schema_path: Optional path to schema file for validation

    Returns:
        MutationResponse with operation result
    """
    try:
        modified_toml = set_toml_value(path, key_path, parsed_value)
        _validate_and_write_content(path, modified_toml, schema_path, FormatType.TOML)
    except (KeyError, TypeError, ValueError, OSError) as e:
        raise ToolError(f"TOML set operation failed: {e}") from e
    else:
        return MutationResponse(
            success=True,
            result="File modified successfully",
            file=str(path),
            schema_info=schema_info,
        )


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
) -> MutationResponse:
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
        MutationResponse with operation result

    Raises:
        ToolError: If operation fails
    """
    parsed_value = _parse_set_value(value, value_type)

    # Validating before write (Phase 9)
    schema_path: Path | None = None
    if schema_info and schema_manager is not None:
        schema_path = schema_manager.get_schema_path_for_file(path)

    if input_format == FormatType.TOML:
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
    except (TypeError, ValueError, OSError) as e:
        raise ToolError(f"Set operation failed: {e}") from e
    else:
        optimized = False
        if input_format == FormatType.YAML:
            optimized = _optimize_yaml_if_needed(path)

        return MutationResponse(
            success=True,
            result="File modified successfully",
            file=str(path),
            optimized=optimized,
            message="File modified and optimized with YAML anchors"
            if optimized
            else None,
            schema_info=schema_info,
        )


def _delete_toml_key_handler(
    path: Path, key_path: str, schema_path: Path | None, schema_info: SchemaInfo | None
) -> MutationResponse:
    """Handle TOML delete operation.

    Args:
        path: Path to file
        key_path: Key path to delete
        schema_path: Optional path to schema file
        schema_info: Optional schema information

    Returns:
        MutationResponse with operation result

    Raises:
        ToolError: If operation fails
    """
    try:
        modified_toml = delete_toml_key(path, key_path)
        _validate_and_write_content(path, modified_toml, schema_path, FormatType.TOML)
    except KeyError as e:
        raise ToolError(f"TOML delete operation failed: {e}") from e
    except (TypeError, ValueError, OSError) as e:
        raise ToolError(f"TOML delete operation failed: {e}") from e

    return MutationResponse(
        success=True,
        result="File modified successfully",
        file=str(path),
        schema_info=schema_info,
    )


def _delete_yq_key_handler(
    path: Path,
    key_path: str,
    input_format: FormatType,
    schema_path: Path | None,
    schema_info: SchemaInfo | None,
) -> MutationResponse:
    """Handle YAML/JSON delete operation using yq.

    Args:
        path: Path to file
        key_path: Key path to delete
        input_format: File format type
        schema_path: Optional path to schema file
        schema_info: Optional schema information

    Returns:
        MutationResponse with operation result

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
    except (TypeError, ValueError, OSError) as e:
        raise ToolError(f"Delete operation failed: {e}") from e

    return MutationResponse(
        success=True,
        result="File modified successfully",
        file=str(path),
        schema_info=schema_info,
    )


def _handle_data_delete(
    path: Path,
    key_path: str,
    input_format: FormatType,
    schema_info: SchemaInfo | None,
    schema_manager: SchemaManager | None = None,
) -> MutationResponse:
    """Handle DELETE operation.

    Args:
        path: Path to configuration file
        key_path: Key path to delete
        input_format: File format type
        schema_info: Optional schema information
        schema_manager: Schema manager instance for schema path lookup

    Returns:
        MutationResponse with operation result

    Raises:
        ToolError: If operation fails
    """
    schema_path: Path | None = None
    if schema_info and schema_manager is not None:
        schema_path = schema_manager.get_schema_path_for_file(path)

    if input_format == FormatType.TOML:
        return _delete_toml_key_handler(path, key_path, schema_path, schema_info)

    return _delete_yq_key_handler(
        path, key_path, input_format, schema_path, schema_info
    )


def _dispatch_set_operation(
    path: Path,
    key_path: str | None,
    value: str | None,
    value_type: Literal["string", "number", "boolean", "null", "json"] | None,
    schema_info: SchemaInfo | None,
    schema_manager: SchemaManager | None = None,
) -> MutationResponse:
    """Dispatch SET operation to handler.

    Args:
        path: Path to configuration file
        key_path: Key path to set
        value: JSON string value
        value_type: How to interpret the value parameter
        schema_info: Optional schema information
        schema_manager: Schema manager instance for schema path lookup

    Returns:
        MutationResponse from handler

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
) -> MutationResponse:
    """Dispatch DELETE operation to handler.

    Args:
        path: Path to configuration file
        key_path: Key path to delete
        schema_info: Optional schema information
        schema_manager: Schema manager instance for schema path lookup

    Returns:
        MutationResponse from handler

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

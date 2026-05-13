"""Format detection, content parsing for validation, and value parsing for SET operations.

Pure utility functions that operate on format types and raw data.
Extracted from server.py to complete ARCH-02.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import orjson
import tomlkit
from fastmcp.exceptions import ToolError
from ruamel.yaml import YAML

from mcp_json_yaml_toml.backends.base import FormatType, YQExecutionError


def _detect_file_format(file_path: str | Path) -> FormatType:
    """Detect format from file extension.

    Args:
        file_path: Path to file

    Returns:
        Detected format type

    Raises:
        ToolError: If format cannot be detected
    """
    path = Path(file_path)
    suffix = path.suffix.lower().lstrip(".")
    # Handle yml -> yaml alias
    if suffix == "yml":
        suffix = "yaml"

    try:
        return FormatType(suffix)
    except ValueError:
        valid_formats = [f.value for f in FormatType]
        raise ToolError(
            f"Cannot detect format from extension '.{suffix}'. "
            f"Supported formats: {', '.join(valid_formats)}"
        ) from None


def _parse_content_for_validation(
    content: str, input_format: FormatType | str
) -> Any | None:
    """Parse content string into data structure for schema validation.

    Args:
        content: Raw file content string
        input_format: File format (json, yaml, toml)

    Returns:
        Parsed data structure or None if format not recognized

    Raises:
        ToolError: If parsing fails
    """
    # Normalize to FormatType for consistent comparison
    try:
        fmt = (
            FormatType(input_format)
            if not isinstance(input_format, FormatType)
            else input_format
        )
    except ValueError:
        return None

    # Initialized for the non-data fallback case and to keep return flow simple.
    parsed_data: Any | None = None
    try:
        match fmt:
            case FormatType.JSON:
                parsed_data = orjson.loads(content)
            case FormatType.YAML:
                yaml = YAML(typ="safe", pure=True)
                documents = list(yaml.load_all(content))
                if documents:
                    parsed_data = documents[0] if len(documents) == 1 else documents
            case FormatType.TOML:
                parsed_data = tomlkit.parse(content)
            case _:
                parsed_data = None
    except Exception as e:
        raise ToolError(f"Failed to parse content for validation: {e}") from e
    return parsed_data


def _parse_typed_json(
    value: str, expected_type: type | tuple[type, ...], type_name: str
) -> Any:
    """Parse JSON value and validate type.

    Args:
        value: JSON string to parse
        expected_type: Expected Python type or tuple of types
        type_name: Human-readable type name for error messages

    Returns:
        Parsed value

    Raises:
        ToolError: If parsing fails or type doesn't match
    """
    try:
        parsed = orjson.loads(value)
    except orjson.JSONDecodeError as e:
        raise ToolError(f"Invalid {type_name} value: {e}") from e
    if not isinstance(parsed, expected_type):
        raise ToolError(
            f"value_type='{type_name}' but value parses to {type(parsed).__name__}: {value}"
        )
    return parsed


def _parse_set_value(
    value: str | None,
    value_type: Literal["string", "number", "boolean", "null", "json"] | None,
) -> Any:
    """Parse value for SET operation based on value_type.

    Args:
        value: Value to parse
        value_type: How to interpret the value

    Returns:
        Parsed value ready for setting

    Raises:
        ToolError: If value is invalid for the specified type
    """
    if value_type == "null":
        return None
    if value is None:
        raise ToolError(f"value is required when value_type='{value_type or 'json'}'")

    match value_type:
        case "string":
            return value
        case "number":
            return _parse_typed_json(value, (int, float), "number")
        case "boolean":
            return _parse_typed_json(value, bool, "boolean")
        case _:
            # value_type is None or "json" - parse as JSON
            try:
                return orjson.loads(value)
            except orjson.JSONDecodeError as e:
                raise ToolError(f"Invalid JSON value: {e}") from e


def resolve_file_path(file_path: str, *, must_exist: bool = True) -> Path:
    """Resolve and validate a file path.

    Args:
        file_path: Raw file path string from tool input.
        must_exist: If True (default), raise ToolError when file does not exist.

    Returns:
        Resolved absolute Path.

    Raises:
        ToolError: If must_exist is True and file does not exist.
    """
    path = Path(file_path).expanduser().resolve()
    if must_exist and not path.exists():
        raise ToolError(f"File not found: {file_path}")
    return path


def should_fallback_toml_to_json(
    error: YQExecutionError,
    output_format_explicit: bool,
    output_format: FormatType,
    input_format: FormatType,
) -> bool:
    """Check if a TOML output failure should fall back to JSON.

    yq cannot encode nested/non-scalar structures as TOML output. When the output
    format was auto-selected (not explicit), this function identifies the specific
    error and signals the caller to retry with JSON output.

    Args:
        error: The YQExecutionError from the failed execution.
        output_format_explicit: Whether the user explicitly requested this output format.
        output_format: The output format that was used.
        input_format: The input file format.

    Returns:
        True if the caller should retry with FormatType.JSON output.
    """
    return (
        not output_format_explicit
        and output_format == FormatType.TOML
        and input_format == FormatType.TOML
        and "only scalars" in str(error.stderr)
    )


def _validate_document_index(document_index: int | None) -> int | None:
    """Validate optional YAML document index."""
    if document_index is None:
        return None
    if document_index < 0:
        raise ToolError("document_index must be >= 0")
    return document_index


def wrap_expression_for_document(expression: str, document_index: int | None) -> str:
    """Wrap a yq expression to target a specific document index."""
    validated_index = _validate_document_index(document_index)
    if validated_index is None:
        return expression
    return f"select(documentIndex == {validated_index}) | ({expression})"


def wrap_mutation_expression_for_document(
    expression: str, document_index: int | None
) -> str:
    """Wrap a yq mutation expression to edit only one document."""
    validated_index = _validate_document_index(document_index)
    if validated_index is None:
        return expression
    return f"with(select(documentIndex == {validated_index}); {expression})"


__all__ = [
    "_detect_file_format",
    "_parse_content_for_validation",
    "_parse_set_value",
    "_parse_typed_json",
    "resolve_file_path",
    "should_fallback_toml_to_json",
    "wrap_expression_for_document",
    "wrap_mutation_expression_for_document",
]

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

from mcp_json_yaml_toml.yq_wrapper import FormatType, YQExecutionError


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
    try:
        if input_format == "json":
            return orjson.loads(content)
        if input_format in {"yaml", FormatType.YAML}:
            yaml = YAML(typ="safe", pure=True)
            return yaml.load(content)
        if input_format in {"toml", FormatType.TOML}:
            return tomlkit.parse(content)
    except Exception as e:
        raise ToolError(f"Failed to parse content for validation: {e}") from e
    return None


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


__all__ = [
    "_detect_file_format",
    "_parse_content_for_validation",
    "_parse_set_value",
    "_parse_typed_json",
    "resolve_file_path",
    "should_fallback_toml_to_json",
]

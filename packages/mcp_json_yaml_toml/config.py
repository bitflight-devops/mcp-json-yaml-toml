"""Configuration management for MCP config tools.

This module handles:
- Environment variable parsing for enabled formats
- Format validation
- Default configuration values
"""

from __future__ import annotations

import functools
import os

from fastmcp.exceptions import ToolError

from mcp_json_yaml_toml.backends.base import FormatType

__all__ = [
    "DEFAULT_FORMATS",
    "get_enabled_formats_str",
    "is_format_enabled",
    "parse_enabled_formats",
    "require_format_enabled",
    "validate_format",
]

# Default enabled formats
DEFAULT_FORMATS: tuple[FormatType, ...] = (
    FormatType.JSON,
    FormatType.YAML,
    FormatType.TOML,
)


@functools.lru_cache(maxsize=1)
def parse_enabled_formats() -> tuple[FormatType, ...]:
    """Parse enabled formats from environment variable.

    Reads the MCP_CONFIG_FORMATS environment variable and parses it as a
    comma-separated list of format names. Falls back to DEFAULT_FORMATS if
    the environment variable is not set or is invalid.

    Returns:
        Tuple of enabled FormatType values (immutable for cache safety)

    Examples:
        >>> os.environ["MCP_CONFIG_FORMATS"] = "json,yaml"
        >>> parse_enabled_formats()
        (<FormatType.JSON: 'json'>, <FormatType.YAML: 'yaml'>)

        >>> os.environ.pop("MCP_CONFIG_FORMATS", None)
        >>> parse_enabled_formats()
        (<FormatType.JSON: 'json'>, <FormatType.YAML: 'yaml'>, <FormatType.TOML: 'toml'>)
    """
    env_value = os.environ.get("MCP_CONFIG_FORMATS", "").strip()

    if not env_value:
        return DEFAULT_FORMATS

    # Parse comma-separated list
    format_names = [name.strip().lower() for name in env_value.split(",")]

    # Validate and convert to FormatType
    valid_format_names = {fmt.value for fmt in FormatType}

    enabled_formats: list[FormatType] = [
        FormatType(name) for name in format_names if name in valid_format_names
    ]

    # Fall back to defaults if no valid formats found
    if not enabled_formats:
        return DEFAULT_FORMATS

    return tuple(enabled_formats)


def require_format_enabled(format_type: FormatType | str) -> None:
    """Raise ToolError if the given format is not enabled.

    Args:
        format_type: The format to check (FormatType enum or string).

    Raises:
        ToolError: If format is disabled, with message listing enabled formats.
    """
    if not is_format_enabled(format_type):
        enabled = parse_enabled_formats()
        raise ToolError(
            f"Format '{format_type}' is not enabled. "
            f"Enabled formats: {', '.join(f.value for f in enabled)}"
        )


def is_format_enabled(format_name: str) -> bool:
    """Check if a specific format is enabled.

    Args:
        format_name: Format name to check (case-insensitive)

    Returns:
        True if the format is enabled, False otherwise

    Examples:
        >>> is_format_enabled("json")
        True

        >>> is_format_enabled("xml")
        False

        >>> is_format_enabled("YAML")
        True
    """
    enabled_formats = parse_enabled_formats()
    normalized_name = format_name.lower()

    return any(fmt.value == normalized_name for fmt in enabled_formats)


def validate_format(format_name: str) -> FormatType:
    """Validate and convert a format name to FormatType.

    Args:
        format_name: Format name to validate (case-insensitive)

    Returns:
        FormatType enum value

    Raises:
        ValueError: If format_name is not a valid format

    Examples:
        >>> validate_format("json")
        <FormatType.JSON: 'json'>

        >>> validate_format("YAML")
        <FormatType.YAML: 'yaml'>

        >>> validate_format("invalid")
        Traceback (most recent call last):
            ...
        ValueError: Invalid format 'invalid'. Valid formats: json, yaml, toml, xml
    """
    normalized_name = format_name.lower()

    try:
        return FormatType(normalized_name)
    except ValueError as e:
        valid_formats = ", ".join(fmt.value for fmt in FormatType)
        raise ValueError(
            f"Invalid format '{format_name}'. Valid formats: {valid_formats}"
        ) from e


def get_enabled_formats_str() -> str:
    """Get enabled formats as a comma-separated string.

    Returns:
        Comma-separated string of enabled format names

    Examples:
        >>> get_enabled_formats_str()
        'json,yaml,toml'
    """
    enabled_formats = parse_enabled_formats()
    return ",".join(fmt.value for fmt in enabled_formats)

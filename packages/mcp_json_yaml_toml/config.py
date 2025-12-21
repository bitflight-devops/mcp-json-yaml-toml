"""Configuration management for MCP config tools.

This module handles:
- Environment variable parsing for enabled formats
- Format validation
- Default configuration values
"""

import os

from mcp_json_yaml_toml.yq_wrapper import FormatType

# Default enabled formats
DEFAULT_FORMATS: list[FormatType] = [FormatType.JSON, FormatType.YAML, FormatType.TOML]


def parse_enabled_formats() -> list[FormatType]:
    """Parse enabled formats from environment variable.

    Reads the MCP_CONFIG_FORMATS environment variable and parses it as a
    comma-separated list of format names. Falls back to DEFAULT_FORMATS if
    the environment variable is not set or is invalid.

    Returns:
        List of enabled FormatType values

    Examples:
        >>> os.environ["MCP_CONFIG_FORMATS"] = "json,yaml"
        >>> parse_enabled_formats()
        [<FormatType.JSON: 'json'>, <FormatType.YAML: 'yaml'>]

        >>> os.environ.pop("MCP_CONFIG_FORMATS", None)
        >>> parse_enabled_formats()
        [<FormatType.JSON: 'json'>, <FormatType.YAML: 'yaml'>, <FormatType.TOML: 'toml'>]
    """
    env_value = os.environ.get("MCP_CONFIG_FORMATS", "").strip()

    if not env_value:
        return list(DEFAULT_FORMATS)

    # Parse comma-separated list
    format_names = [name.strip().lower() for name in env_value.split(",")]

    # Validate and convert to FormatType
    valid_format_names = {fmt.value for fmt in FormatType}

    enabled_formats: list[FormatType] = [
        FormatType(name) for name in format_names if name in valid_format_names
    ]

    # Fall back to defaults if no valid formats found
    if not enabled_formats:
        return list(DEFAULT_FORMATS)

    return enabled_formats


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

"""MCP server for querying and modifying JSON, YAML, and TOML configuration files.

This server provides tools for reading, modifying, validating, and transforming
configuration files using yq. Tools are dynamically registered based on the
MCP_CONFIG_FORMATS environment variable.
"""

import base64
from pathlib import Path
from typing import Annotated, Any, Literal, assert_never

import orjson
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from pydantic import Field

from mcp_json_yaml_toml.config import (
    is_format_enabled,
    parse_enabled_formats,
    validate_format,
)
from mcp_json_yaml_toml.lmql_constraints import (
    ConstraintRegistry,
    get_constraint_hint,
    validate_tool_input,
)
from mcp_json_yaml_toml.schemas import SchemaManager
from mcp_json_yaml_toml.yq_wrapper import (
    FormatType,
    YQError,
    YQExecutionError,
    execute_yq,
)

# Initialize FastMCP server
mcp = FastMCP("config-tools", mask_error_details=False)

# Initialize Schema Manager
schema_manager = SchemaManager()

# Pagination constants
PAGE_SIZE_CHARS = 10000
ADVISORY_PAGE_THRESHOLD = 2  # Show advisory when result spans more than this many pages
MAX_PRIMITIVE_DISPLAY_LENGTH = 100  # Truncate primitive values longer than this


def _encode_cursor(offset: int) -> str:
    """Encode pagination offset into opaque cursor token.

    Args:
        offset: Character offset into result string

    Returns:
        Base64-encoded opaque cursor string
    """
    cursor_data = orjson.dumps({"offset": offset})
    return base64.b64encode(cursor_data).decode()


def _decode_cursor(cursor: str) -> int:
    """Decode cursor token to extract offset.

    Args:
        cursor: Opaque cursor string from previous response

    Returns:
        Character offset

    Raises:
        ToolError: If cursor is invalid or malformed
    """
    try:
        cursor_data = base64.b64decode(cursor.encode())
        data = orjson.loads(cursor_data)
        offset = data.get("offset")
        if not isinstance(offset, int) or offset < 0:
            raise ToolError("Invalid cursor: offset must be non-negative integer")
    except (ValueError, orjson.JSONDecodeError) as e:
        raise ToolError(f"Invalid cursor format: {e}") from e
    else:
        return offset


def _paginate_result(
    result_str: str, cursor: str | None, advisory_hint: str | None = None
) -> dict[str, Any]:
    """Paginate a result string at PAGE_SIZE_CHARS boundary.

    Args:
        result_str: Complete result string to paginate
        cursor: Optional cursor from previous page
        advisory_hint: Optional specific advisory hint to include

    Returns:
        Dictionary with 'data' (page content), 'nextCursor' (if more pages),
        and 'advisory' (if result spans >2 pages)
    """
    offset = 0 if cursor is None else _decode_cursor(cursor)

    # Only raise error if cursor is explicitly provided and exceeds data
    if cursor is not None and offset >= len(result_str):
        raise ToolError(f"Cursor offset {offset} exceeds result size {len(result_str)}")

    # Extract page
    page_end = offset + PAGE_SIZE_CHARS
    page_data = result_str[offset:page_end]

    response: dict[str, Any] = {"data": page_data}

    # Add nextCursor if more data exists
    if page_end < len(result_str):
        response["nextCursor"] = _encode_cursor(page_end)

        # Advisory for large results (>2 pages)
        total_pages = (len(result_str) + PAGE_SIZE_CHARS - 1) // PAGE_SIZE_CHARS
        if total_pages > ADVISORY_PAGE_THRESHOLD:
            base_advisory = (
                f"Result spans {total_pages} pages ({len(result_str):,} chars). "
                "Consider querying for specific keys (e.g., '.data | keys') or counts "
                "(e.g., '.items | length') to reduce result size."
            )
            response["advisory"] = (
                f"{base_advisory} {advisory_hint}" if advisory_hint else base_advisory
            )

    return response


def _summarize_list_structure(
    data: list[Any], depth: int, max_depth: int, full_keys_mode: bool
) -> Any:
    """Summarize list structure for _summarize_structure.

    Args:
        data: List to summarize
        depth: Current recursion depth
        max_depth: Maximum depth to traverse
        full_keys_mode: If True, show representative structure

    Returns:
        Summarized list structure
    """
    if not data:
        return []

    if full_keys_mode:
        # Show representative structure based on first item type
        first_item = data[0]
        if isinstance(first_item, (dict, list)):
            return [
                _summarize_structure(first_item, depth + 1, max_depth, full_keys_mode)
            ]
        return [type(first_item).__name__]
    # Original behavior: summary + sample
    summary = f"<list with {len(data)} items>"
    sample = _summarize_structure(data[0], depth + 1, max_depth, full_keys_mode)
    return {"__summary__": summary, "first_item_sample": sample}


def _summarize_structure(
    data: Any, depth: int = 0, max_depth: int = 1, full_keys_mode: bool = False
) -> Any:
    """Create a summary of the data structure.

    Args:
        data: The data to summarize
        depth: Current recursion depth
        max_depth: Maximum depth to traverse (ignored if full_keys_mode=True)
        full_keys_mode: If True, recursively show all keys and types without depth limits

    Returns:
        Summarized data structure showing keys and types
    """
    # In full_keys_mode, ignore max_depth and show complete structure
    if not full_keys_mode and depth > max_depth:
        if isinstance(data, dict):
            return f"<dict with {len(data)} keys>"
        if isinstance(data, list):
            return f"<list with {len(data)} items>"
        return type(data).__name__

    if isinstance(data, dict):
        # Return keys with their types/summaries recursively
        return {
            k: _summarize_structure(v, depth + 1, max_depth, full_keys_mode)
            for k, v in data.items()
        }
    if isinstance(data, list):
        return _summarize_list_structure(data, depth, max_depth, full_keys_mode)
    # Primitive - show type name in full_keys_mode, otherwise show value
    if full_keys_mode:
        return type(data).__name__
    s = str(data)
    if len(s) <= MAX_PRIMITIVE_DISPLAY_LENGTH:
        return s
    return s[: MAX_PRIMITIVE_DISPLAY_LENGTH - 3] + "..."


def _detect_file_format(file_path: Path) -> FormatType:
    """Detect format from file extension.

    Args:
        file_path: Path to file

    Returns:
        Detected format type

    Raises:
        ToolError: If format cannot be detected
    """
    suffix = file_path.suffix.lower()
    format_map = {
        ".json": "json",
        ".yaml": "yaml",
        ".yml": "yaml",
        ".toml": "toml",
        ".xml": "xml",
    }

    if suffix not in format_map:
        raise ToolError(
            f"Cannot detect format from extension '{suffix}'. Supported extensions: {', '.join(format_map.keys())}"
        )

    return format_map[suffix]  # type: ignore[return-value]


def _find_schema_file(config_path: Path) -> Path | None:
    """Find schema file for the given config file.

    Looks for .schema.json, .schema.yaml, or .schema.yml files with the same base name.

    Args:
        config_path: Path to config file

    Returns:
        Path to schema file if found, None otherwise
    """
    base_name = config_path.stem

    # Try different schema file patterns
    schema_patterns = [
        f"{base_name}.schema.json",
        f"{base_name}.schema.yaml",
        f"{base_name}.schema.yml",
    ]

    for pattern in schema_patterns:
        schema_path = config_path.parent / pattern
        if schema_path.exists():
            return schema_path

    return None


def _handle_data_get_schema(
    path: Path, schema_manager: SchemaManager
) -> dict[str, Any]:
    """Handle GET operation with data_type='schema'.

    Args:
        path: Path to configuration file
        schema_manager: Schema manager instance

    Returns:
        Response dict with schema information
    """
    schema_info = schema_manager.get_schema_info_for_file(path)
    schema_data = schema_manager.get_schema_for_file(path)

    if schema_data:
        response = {
            "success": True,
            "file": str(path),
            "schema": schema_data,
            "message": "Schema found via Schema Store",
        }
        if schema_info:
            response["schema_info"] = schema_info
        return response
    return {
        "success": False,
        "file": str(path),
        "message": f"No schema found for file: {path.name}",
    }


def _handle_data_get_structure(
    path: Path,
    key_path: str | None,
    input_format: FormatType,
    cursor: str | None,
    schema_info: dict[str, Any] | None,
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
            expression, input_file=path, input_format=input_format, output_format="json"
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
        return response
    except YQExecutionError as e:
        raise ToolError(f"Query failed: {e}") from e


def _handle_data_get_value(
    path: Path,
    key_path: str,
    input_format: FormatType,
    output_fmt: FormatType,
    cursor: str | None,
    schema_info: dict[str, Any] | None,
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
        return response
    except YQExecutionError as e:
        # Auto-fallback to JSON if TOML output was auto-selected and yq can't encode nested structures
        if (
            not output_format_explicit
            and output_fmt == "toml"
            and input_format == "toml"
            and "only scalars" in str(e.stderr)
        ):
            # Retry with JSON output format
            return _handle_data_get_value(
                path,
                key_path,
                input_format,
                "json",
                cursor,
                schema_info,
                output_format_explicit=True,
            )
        raise ToolError(f"Query failed: {e}") from e


def _set_toml_value_handler(
    path: Path, key_path: str, parsed_value: Any, schema_info: dict[str, Any] | None
) -> dict[str, Any]:
    """Handle TOML set operation."""
    from mcp_json_yaml_toml.toml_utils import set_toml_value

    try:
        modified_toml = set_toml_value(path, key_path, parsed_value)
        path.write_text(modified_toml, encoding="utf-8")
        response = {
            "success": True,
            "result": "File modified successfully",
            "file": str(path),
        }
        if schema_info:
            response["schema_info"] = schema_info
    except Exception as e:
        raise ToolError(f"TOML set operation failed: {e}") from e
    else:
        return response


def _optimize_yaml_if_needed(path: Path) -> bool:
    """Optimize YAML file with anchors if applicable."""
    original_content = path.read_text(encoding="utf-8")
    if "&" not in original_content and "*" not in original_content:
        return False

    from mcp_json_yaml_toml.yaml_optimizer import optimize_yaml_file

    reparse_result = execute_yq(
        ".", input_file=path, input_format="yaml", output_format="json"
    )
    if reparse_result.data is None:
        return False

    optimized_yaml = optimize_yaml_file(reparse_result.data)
    if optimized_yaml:
        path.write_text(optimized_yaml, encoding="utf-8")
        return True
    return False


def _parse_set_value(  # noqa: C901
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
    match value_type:
        case "null":
            return None
        case "string":
            if value is None:
                raise ToolError("value is required when value_type='string'")
            return value
        case "number":
            if value is None:
                raise ToolError("value is required when value_type='number'")
            try:
                parsed = orjson.loads(value)
            except orjson.JSONDecodeError as e:
                raise ToolError(f"Invalid number value: {e}") from e
            else:
                if not isinstance(parsed, (int, float)):
                    raise ToolError(
                        f"value_type='number' but value parses to {type(parsed).__name__}: {value}"
                    )
                return parsed
        case "boolean":
            if value is None:
                raise ToolError("value is required when value_type='boolean'")
            try:
                parsed = orjson.loads(value)
            except orjson.JSONDecodeError as e:
                raise ToolError(f"Invalid boolean value: {e}") from e
            else:
                if not isinstance(parsed, bool):
                    raise ToolError(
                        f"value_type='boolean' but value parses to {type(parsed).__name__}: {value}"
                    )
                return parsed
        case _:
            # value_type is None or "json" - parse as JSON (current/default behavior)
            if value is None:
                raise ToolError("value is required for SET operation")
            try:
                return orjson.loads(value)
            except orjson.JSONDecodeError as e:
                raise ToolError(f"Invalid JSON value: {e}") from e


def _handle_data_set(
    path: Path,
    key_path: str,
    value: str | None,
    value_type: Literal["string", "number", "boolean", "null", "json"] | None,
    input_format: FormatType,
    schema_info: dict[str, Any] | None,
) -> dict[str, Any]:
    """Handle SET operation.

    Args:
        path: Path to configuration file
        key_path: Key path to set
        value: Value to set (interpretation depends on value_type)
        value_type: How to interpret the value parameter
        input_format: File format type
        schema_info: Optional schema information

    Returns:
        Response dict with operation result

    Raises:
        ToolError: If operation fails
    """
    parsed_value = _parse_set_value(value, value_type)

    if input_format == "toml":
        return _set_toml_value_handler(path, key_path, parsed_value, schema_info)

    # YAML/JSON use yq
    yq_value = orjson.dumps(parsed_value).decode()
    expression = (
        f".{key_path} = {yq_value}"
        if not key_path.startswith(".")
        else f"{key_path} = {yq_value}"
    )

    try:
        execute_yq(
            expression,
            input_file=path,
            input_format=input_format,
            output_format=input_format,
            in_place=True,
        )
    except YQExecutionError as e:
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


def _handle_data_delete(
    path: Path,
    key_path: str,
    input_format: FormatType,
    schema_info: dict[str, Any] | None,
) -> dict[str, Any]:
    """Handle DELETE operation.

    Args:
        path: Path to configuration file
        key_path: Key path to delete
        input_format: File format type
        schema_info: Optional schema information

    Returns:
        Response dict with operation result

    Raises:
        ToolError: If operation fails
    """
    # TOML requires special handling since yq cannot write TOML
    if input_format == "toml":
        from mcp_json_yaml_toml.toml_utils import delete_toml_key

        try:
            modified_toml = delete_toml_key(path, key_path)
            path.write_text(modified_toml, encoding="utf-8")
            response = {
                "success": True,
                "result": "File modified successfully",
                "file": str(path),
            }

            if schema_info:
                response["schema_info"] = schema_info
        except KeyError as e:
            raise ToolError(f"TOML delete operation failed: {e}") from e
        except Exception as e:
            raise ToolError(f"TOML delete operation failed: {e}") from e
        else:
            return response

    # YAML/JSON use yq
    expression = (
        f"del(.{key_path})" if not key_path.startswith(".") else f"del({key_path})"
    )

    try:
        execute_yq(
            expression,
            input_file=path,
            input_format=input_format,
            output_format=input_format,
            in_place=True,
        )
        response = {
            "success": True,
            "result": "File modified successfully",
            "file": str(path),
        }
        if schema_info:
            response["schema_info"] = schema_info
    except YQExecutionError as e:
        raise ToolError(f"Delete operation failed: {e}") from e
    else:
        return response


def _validate_against_schema(data: Any, schema_path: Path) -> tuple[bool, str]:
    """Validate data against JSON schema.

    Args:
        data: Data to validate (parsed from JSON/YAML)
        schema_path: Path to schema file

    Returns:
        Tuple of (is_valid, message)
    """
    try:
        import jsonschema
    except ImportError:
        return True, "Schema validation skipped (jsonschema not installed)"

    try:
        # Load schema
        schema_format = _detect_file_format(schema_path)
        schema_result = execute_yq(
            ".",
            input_file=schema_path,
            input_format=schema_format,
            output_format="json",
        )

        if schema_result.data is None:
            return False, f"Failed to parse schema file: {schema_path}"

        schema = schema_result.data

        # Validate
        jsonschema.validate(instance=data, schema=schema)
    except jsonschema.ValidationError as e:
        return False, f"Schema validation failed: {e.message}"
    except jsonschema.SchemaError as e:
        return False, f"Invalid schema: {e.message}"
    except YQError as e:
        return False, f"Failed to load schema: {e}"
    except (OSError, orjson.JSONDecodeError) as e:
        return False, f"Schema validation error: {e}"
    else:
        return True, "Schema validation passed"


def _dispatch_get_operation(
    path: Path,
    data_type: Literal["data", "schema"],
    return_type: Literal["keys", "all"],
    key_path: str | None,
    output_format: Literal["json", "yaml", "toml"] | None,
    cursor: str | None,
    schema_info: dict[str, Any] | None,
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

    Returns:
        Response dict from handler

    Raises:
        ToolError: If format disabled or validation fails
    """
    if data_type == "schema":
        return _handle_data_get_schema(path, schema_manager)

    input_format = _detect_file_format(path)
    if not is_format_enabled(input_format):
        enabled = parse_enabled_formats()
        raise ToolError(
            f"Format '{input_format}' is not enabled. Enabled formats: {', '.join(f.value for f in enabled)}"
        )

    # Track whether output format was explicitly provided
    output_format_explicit = output_format is not None

    if output_format is None:
        output_fmt: FormatType = input_format
    else:
        validated = validate_format(output_format)
        output_fmt = validated.value

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
    schema_info: dict[str, Any] | None,
) -> dict[str, Any]:
    """Dispatch SET operation to handler.

    Args:
        path: Path to configuration file
        key_path: Key path to set
        value: JSON string value
        value_type: How to interpret the value parameter
        schema_info: Optional schema information

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
    if not is_format_enabled(input_format):
        enabled = parse_enabled_formats()
        raise ToolError(
            f"Format '{input_format}' is not enabled. Enabled formats: {', '.join(f.value for f in enabled)}"
        )

    return _handle_data_set(
        path, key_path, value, value_type, input_format, schema_info
    )


def _dispatch_delete_operation(
    path: Path, key_path: str | None, schema_info: dict[str, Any] | None
) -> dict[str, Any]:
    """Dispatch DELETE operation to handler.

    Args:
        path: Path to configuration file
        key_path: Key path to delete
        schema_info: Optional schema information

    Returns:
        Response dict from handler

    Raises:
        ToolError: If validation fails or format disabled
    """
    if key_path is None:
        raise ToolError("key_path is required for operation='delete'")

    input_format = _detect_file_format(path)
    if not is_format_enabled(input_format):
        enabled = parse_enabled_formats()
        raise ToolError(
            f"Format '{input_format}' is not enabled. Enabled formats: {', '.join(f.value for f in enabled)}"
        )

    return _handle_data_delete(path, key_path, input_format, schema_info)


@mcp.tool(annotations={"readOnlyHint": True})
def data_query(  # noqa: C901
    file_path: Annotated[str, Field(description="Path to configuration file")],
    expression: Annotated[
        str,
        Field(
            description="yq expression to evaluate (e.g., '.name', '.items[]', '.data.users')"
        ),
    ],
    output_format: Annotated[
        FormatType | None,
        Field(description="Output format (defaults to same as input file format)"),
    ] = None,
    cursor: Annotated[
        str | None,
        Field(
            description="Pagination cursor from previous response (omit for first page)"
        ),
    ] = None,
) -> dict[str, Any]:
    """Extract specific data, filter content, or transform structure without modification.

    Use when you need to extract specific data, filter content, or transform the structure of a JSON, YAML, or TOML file without modifying it.

    Output contract: Returns {"success": bool, "result": Any, "format": str, "file": str, ...}.
    Side effects: None (read-only).
    Failure modes: FileNotFoundError if file missing. ToolError if format disabled or query fails.
    """
    path = Path(file_path).expanduser().resolve()

    if not path.exists():
        raise ToolError(f"File not found: {file_path}")

    # Check if format is enabled
    input_format: FormatType = _detect_file_format(path)
    if not is_format_enabled(input_format):
        enabled = parse_enabled_formats()
        raise ToolError(
            f"Format '{input_format}' is not enabled. Enabled formats: {', '.join(f.value for f in enabled)}"
        )

    # Track whether output format was explicitly provided
    output_format_explicit = output_format is not None

    # Use input format as output if not specified
    output_format_value: FormatType = (
        input_format if output_format is None else validate_format(output_format).value
    )

    try:
        result = execute_yq(
            expression,
            input_file=path,
            input_format=input_format,
            output_format=output_format_value,
        )

        # Prepare result string for pagination
        result_str = (
            result.stdout
            if output_format_value != "json"
            else orjson.dumps(result.data, option=orjson.OPT_INDENT_2).decode()
        )

        # Apply pagination if result is large
        if len(result_str) > PAGE_SIZE_CHARS or cursor is not None:
            # Generate hint
            hint = None
            if isinstance(result.data, list):
                hint = "Result is a list. Use '.[start:end]' to slice or '. | length' to count."
            elif isinstance(result.data, dict):
                hint = "Result is an object. Use '.key' to select or '. | keys' to list keys."

            pagination = _paginate_result(result_str, cursor, advisory_hint=hint)
            response = {
                "success": True,
                "result": pagination["data"],
                "format": output_format_value,
                "file": str(path),
                "paginated": True,
            }
            if "nextCursor" in pagination:
                response["nextCursor"] = pagination["nextCursor"]
            if "advisory" in pagination:
                response["advisory"] = pagination["advisory"]
            return response
        # Small result - no pagination needed
        return {
            "success": True,
            "result": result_str if output_format_value != "json" else result.data,
            "format": output_format_value,
            "file": str(path),
        }

    except YQExecutionError as e:
        # Auto-fallback to JSON if TOML output was auto-selected and yq can't encode nested structures
        if (
            not output_format_explicit
            and output_format_value == "toml"
            and input_format == "toml"
            and "only scalars" in str(e.stderr)
        ):
            # Retry with JSON output format
            output_format_value = "json"
            result = execute_yq(
                expression,
                input_file=path,
                input_format=input_format,
                output_format=output_format_value,
            )
            result_str = orjson.dumps(result.data, option=orjson.OPT_INDENT_2).decode()

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
                    "format": output_format_value,
                    "file": str(path),
                    "paginated": True,
                }
                if "nextCursor" in pagination:
                    response["nextCursor"] = pagination["nextCursor"]
                if "advisory" in pagination:
                    response["advisory"] = pagination["advisory"]
                return response

            return {
                "success": True,
                "result": result.data,
                "format": output_format_value,
                "file": str(path),
            }
        raise ToolError(f"Query failed: {e}") from e


@mcp.tool()
def data(
    file_path: Annotated[str, Field(description="Path to configuration file")],
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
        Literal["data", "schema"], Field(description="Type for get: 'data' or 'schema'")
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
) -> dict[str, Any]:
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
    path = Path(file_path).expanduser().resolve()

    if not path.exists():
        raise ToolError(f"File not found: {file_path}")

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
            )
        case "set":
            return _dispatch_set_operation(
                path, key_path, value, value_type, schema_info
            )
        case "delete":
            return _dispatch_delete_operation(path, key_path, schema_info)
        case _:
            assert_never(operation)


def _handle_schema_validate(
    file_path: str | None, schema_path: str | None
) -> dict[str, Any]:
    """Handle validate action."""
    if not file_path:
        raise ToolError("file_path required for validate action")
    file_path_obj = Path(file_path).expanduser().resolve()
    if not file_path_obj.exists():
        raise ToolError(f"File not found: {file_path}")

    input_format = _detect_file_format(file_path_obj)
    if not is_format_enabled(input_format):
        enabled = parse_enabled_formats()
        raise ToolError(
            f"Format '{input_format}' is not enabled. Enabled formats: {', '.join(f.value for f in enabled)}"
        )

    validation_results: dict[str, Any] = {
        "file": str(file_path_obj),
        "format": input_format,
        "syntax_valid": False,
        "schema_validated": False,
    }

    try:
        result = execute_yq(
            ".",
            input_file=file_path_obj,
            input_format=input_format,
            output_format="json",
        )
        validation_results["syntax_valid"] = True
        validation_results["syntax_message"] = "Syntax is valid"

        schema_file: Path | None = None
        if schema_path:
            schema_file = Path(schema_path).expanduser().resolve()
            if not schema_file.exists():
                raise ToolError(f"Schema file not found: {schema_path}")
        else:
            schema_data = schema_manager.get_schema_for_file(file_path_obj)
            if schema_data:
                import tempfile

                with tempfile.NamedTemporaryFile(
                    mode="wb", suffix=".json", delete=False
                ) as tmp:
                    tmp.write(orjson.dumps(schema_data))
                    schema_file = Path(tmp.name)
            else:
                schema_file = _find_schema_file(file_path_obj)

        if schema_file:
            validation_results["schema_file"] = str(schema_file)
            is_valid, message = _validate_against_schema(result.data, schema_file)
            validation_results["schema_validated"] = is_valid
            validation_results["schema_message"] = message
        else:
            validation_results["schema_message"] = "No schema file found or provided"

        validation_results["overall_valid"] = validation_results["syntax_valid"] and (
            validation_results["schema_validated"] if schema_file else True
        )
    except YQExecutionError as e:
        validation_results["syntax_message"] = f"Syntax error: {e}"
        validation_results["overall_valid"] = False

    return validation_results


def _handle_schema_scan(
    search_paths: list[str] | None, max_depth: int
) -> dict[str, Any]:
    """Handle scan action."""
    if not search_paths:
        raise ToolError("search_paths required for scan action")
    paths = [Path(p).expanduser().resolve() for p in search_paths]
    discovered = schema_manager.scan_for_schema_dirs(paths, max_depth=max_depth)
    return {
        "success": True,
        "action": "scan",
        "discovered_count": len(discovered),
        "discovered_dirs": [str(p) for p in discovered],
    }


def _handle_schema_add_dir(path: str | None) -> dict[str, Any]:
    """Handle add_dir action."""
    if not path:
        raise ToolError("path required for add_dir action")
    dir_path = Path(path).expanduser().resolve()
    if not dir_path.exists():
        raise ToolError(f"Directory not found: {path}")
    if not dir_path.is_dir():
        raise ToolError(f"Not a directory: {path}")

    schema_manager.add_custom_dir(dir_path)
    return {
        "success": True,
        "action": "add_dir",
        "directory": str(dir_path),
        "message": "Directory added to schema cache locations",
    }


def _handle_schema_add_catalog(name: str | None, uri: str | None) -> dict[str, Any]:
    """Handle add_catalog action."""
    if not name or not uri:
        raise ToolError("name and uri required for add_catalog action")
    schema_manager.add_custom_catalog(name, uri)
    return {
        "success": True,
        "action": "add_catalog",
        "name": name,
        "uri": uri,
        "message": "Custom catalog added",
    }


def _handle_schema_associate(
    file_path: str | None, schema_url: str | None, schema_name: str | None
) -> dict[str, Any]:
    """Handle associate action."""
    if not file_path:
        raise ToolError("file_path required for associate action")
    file_path_obj = Path(file_path).expanduser().resolve()
    if not file_path_obj.exists():
        raise ToolError(f"File not found: {file_path}")

    url = schema_url
    name = schema_name

    if not url and schema_name:
        catalog = schema_manager._get_catalog()
        if catalog:
            for schema_info in catalog.get("schemas", []):
                if schema_info.get("name") == schema_name:
                    url = schema_info.get("url")
                    break
        if not url:
            raise ToolError(f"Schema '{schema_name}' not found in catalog")

    if not url:
        raise ToolError("Either schema_url or schema_name must be provided")

    schema_manager.add_file_association(file_path_obj, url, name)
    return {
        "success": True,
        "action": "associate",
        "file": str(file_path_obj),
        "schema_name": name or "unknown",
        "schema_url": url,
        "message": "File associated with schema",
    }


def _handle_schema_disassociate(file_path: str | None) -> dict[str, Any]:
    """Handle disassociate action."""
    if not file_path:
        raise ToolError("file_path required for disassociate action")
    file_path_obj = Path(file_path).expanduser().resolve()
    removed = schema_manager.remove_file_association(file_path_obj)
    return {
        "success": True,
        "action": "disassociate",
        "file": str(file_path_obj),
        "removed": removed,
        "message": "Association removed" if removed else "No association found",
    }


def _handle_schema_list() -> dict[str, Any]:
    """Handle list action."""
    config = schema_manager.get_config()
    return {"success": True, "action": "list", "config": config}


@mcp.tool()
def data_schema(
    action: Annotated[
        Literal[
            "validate",
            "scan",
            "add_dir",
            "add_catalog",
            "associate",
            "disassociate",
            "list",
        ],
        Field(
            description="Action: validate, scan, add_dir, add_catalog, associate, disassociate, or list"
        ),
    ],
    file_path: Annotated[
        str | None,
        Field(description="Path to file (for validate/associate/disassociate actions)"),
    ] = None,
    schema_path: Annotated[
        str | None, Field(description="Path to schema file (for validate action)")
    ] = None,
    schema_url: Annotated[
        str | None, Field(description="Schema URL (for associate action)")
    ] = None,
    schema_name: Annotated[
        str | None, Field(description="Schema name from catalog (for associate action)")
    ] = None,
    search_paths: Annotated[
        list[str] | None, Field(description="Paths to scan (for scan action)")
    ] = None,
    path: Annotated[
        str | None, Field(description="Directory path (for add_dir action)")
    ] = None,
    name: Annotated[
        str | None, Field(description="Catalog name (for add_catalog action)")
    ] = None,
    uri: Annotated[
        str | None, Field(description="Catalog URI (for add_catalog action)")
    ] = None,
    max_depth: Annotated[
        int, Field(description="Max search depth (for scan action)")
    ] = 5,
) -> dict[str, Any]:
    """Unified schema operations tool.

    Actions:
    - validate: Validate file syntax and optionally against schema
    - scan: Recursively search for schema directories
    - add_dir: Add custom schema directory
    - add_catalog: Add custom schema catalog
    - associate: Bind file to schema URL or name
    - disassociate: Remove file-to-schema association
    - list: Show current schema configuration

    Examples:
      - action="validate", file_path="config.json"
      - action="associate", file_path=".gitlab-ci.yml", schema_name="gitlab-ci"
      - action="disassociate", file_path=".gitlab-ci.yml"
      - action="list"
    """
    match action:
        case "validate":
            return _handle_schema_validate(file_path, schema_path)
        case "scan":
            return _handle_schema_scan(search_paths, max_depth)
        case "add_dir":
            return _handle_schema_add_dir(path)
        case "add_catalog":
            return _handle_schema_add_catalog(name, uri)
        case "associate":
            return _handle_schema_associate(file_path, schema_url, schema_name)
        case "disassociate":
            return _handle_schema_disassociate(file_path)
        case "list":
            return _handle_schema_list()
        case _:
            assert_never(action)


@mcp.tool(annotations={"readOnlyHint": True})
def data_convert(
    file_path: Annotated[str, Field(description="Path to source configuration file")],
    output_format: Annotated[
        Literal["json", "yaml", "toml"],
        Field(description="Target format to convert to"),
    ],
    output_file: Annotated[
        str | None,
        Field(
            description="Optional output file path (if not provided, returns converted content)"
        ),
    ] = None,
) -> dict[str, Any]:
    """Convert configuration file format.

    Use when you need to transform a configuration file from one format (JSON, YAML, TOML) to another.

    Output contract: Returns {"success": bool, "result": str, ...} or writes to file.
    Side effects: Writes to output_file if provided.
    Failure modes: FileNotFoundError if input missing. ToolError if formats same or conversion fails.
    """
    path = Path(file_path).expanduser().resolve()

    if not path.exists():
        raise ToolError(f"File not found: {file_path}")

    # Detect input format
    input_format = _detect_file_format(path)
    if not is_format_enabled(input_format):
        enabled = parse_enabled_formats()
        raise ToolError(
            f"Input format '{input_format}' is not enabled. Enabled formats: {', '.join(f.value for f in enabled)}"
        )

    # Validate output format
    validated = validate_format(output_format)
    output_fmt: FormatType = validated.value

    if input_format == output_fmt:
        raise ToolError(f"Input and output formats are the same: {input_format}")

    # JSON/YAML to TOML conversion is not supported due to yq limitations
    # yq's TOML encoder only supports scalar values, not complex nested structures
    if output_fmt == "toml" and input_format in {"json", "yaml"}:
        raise ToolError(
            f"Conversion from {input_format.upper()} to TOML is not supported. "
            "The underlying yq tool cannot encode complex nested structures to TOML format. "
            "Supported conversions: JSON↔YAML, TOML→JSON, TOML→YAML."
        )

    try:
        # Convert
        result = execute_yq(
            ".", input_file=path, input_format=input_format, output_format=output_fmt
        )

        # Write to file if requested
        if output_file:
            out_path = Path(output_file).expanduser().resolve()
            out_path.write_text(result.stdout, encoding="utf-8")
            return {
                "success": True,
                "input_file": str(path),
                "output_file": str(out_path),
                "input_format": input_format,
                "output_format": output_fmt,
                "message": f"Converted {input_format} to {output_fmt}",
            }
        return {
            "success": True,
            "input_file": str(path),
            "input_format": input_format,
            "output_format": output_fmt,
            "result": result.stdout,
        }

    except YQExecutionError as e:
        raise ToolError(f"Conversion failed: {e}") from e


@mcp.tool(annotations={"readOnlyHint": True})
def data_merge(
    file_path1: Annotated[
        str, Field(description="Path to first configuration file (base)")
    ],
    file_path2: Annotated[
        str, Field(description="Path to second configuration file (overlay)")
    ],
    output_format: Annotated[
        Literal["json", "yaml", "toml"] | None,
        Field(description="Output format (defaults to format of first file)"),
    ] = None,
    output_file: Annotated[
        str | None,
        Field(
            description="Optional output file path (if not provided, returns merged content)"
        ),
    ] = None,
) -> dict[str, Any]:
    """Merge two configuration files into a single deep-merged configuration.

    Performs a deep merge where values from the second (overlay) file override or extend
    those in the first (base) file. If output_file is provided the merged result is written
    to that path; otherwise the merged content is returned in the response.

    Parameters:
        file_path1 (str): Path to the base configuration file.
        file_path2 (str): Path to the overlay configuration file whose values override the base.
        output_format (str | None): Desired output format: "json", "yaml", or "toml". Defaults to the format of the first file.
        output_file (str | None): Optional path to write the merged output. When omitted, merged content is returned.

    Returns:
        dict: A payload describing the merge. On success includes "success": True, "file1", "file2",
        "output_format", and either "result" (merged content) or "output_file" (written path).

    Raises:
        ToolError: If an input file is missing, its format is not enabled, the output format is invalid, or the merge fails.
    """
    path1 = Path(file_path1).expanduser().resolve()
    path2 = Path(file_path2).expanduser().resolve()

    if not path1.exists():
        raise ToolError(f"First file not found: {file_path1}")
    if not path2.exists():
        raise ToolError(f"Second file not found: {file_path2}")

    # Detect formats
    format1 = _detect_file_format(path1)
    format2 = _detect_file_format(path2)

    if not is_format_enabled(format1):
        enabled = parse_enabled_formats()
        raise ToolError(
            f"Format of first file '{format1}' is not enabled. Enabled formats: {', '.join(f.value for f in enabled)}"
        )
    if not is_format_enabled(format2):
        enabled = parse_enabled_formats()
        raise ToolError(
            f"Format of second file '{format2}' is not enabled. Enabled formats: {', '.join(f.value for f in enabled)}"
        )

    # Determine output format
    output_fmt = output_format or format1
    output_fmt = validate_format(output_fmt).value

    try:
        # Read both files into JSON for merging
        result1 = execute_yq(
            ".", input_file=path1, input_format=format1, output_format="json"
        )
        result2 = execute_yq(
            ".", input_file=path2, input_format=format2, output_format="json"
        )

        # Merge using yq's multiply operator (*)
        # This does a deep merge
        merged_json = orjson.dumps(result1.data).decode() if result1.data else "{}"
        overlay_json = orjson.dumps(result2.data).decode() if result2.data else "{}"

        # Use yq to merge
        merge_expression = f". * {overlay_json}"
        merge_result = execute_yq(
            merge_expression,
            input_data=merged_json,
            input_format="json",
            output_format=output_fmt,
        )

        # Write to file if requested
        if output_file:
            out_path = Path(output_file).expanduser().resolve()
            out_path.write_text(merge_result.stdout, encoding="utf-8")
            return {
                "success": True,
                "file1": str(path1),
                "file2": str(path2),
                "output_file": str(out_path),
                "output_format": output_fmt,
                "message": "Files merged successfully",
            }
        return {
            "success": True,
            "file1": str(path1),
            "file2": str(path2),
            "output_format": output_fmt,
            "result": merge_result.stdout,
        }

    except YQExecutionError as e:
        raise ToolError(f"Merge failed: {e}") from e


# =============================================================================
# LMQL Constraint Resources and Tools
# =============================================================================


@mcp.resource("lmql://constraints")
def list_all_constraints() -> dict[str, Any]:
    """Provide metadata and definitions for all registered LMQL constraints.

    Returns:
        A dictionary with:
        - "constraints": a mapping of all constraint definitions keyed by name.
        - "description": a short human-readable description of the constraint collection.
        - "usage": a brief usage note for applying these constraints in constrained generation.
    """
    return {
        "constraints": ConstraintRegistry.get_all_definitions(),
        "description": "LMQL-style constraints for validating tool inputs",
        "usage": "Use these constraints with LMQL or similar tools for constrained generation",
    }


@mcp.resource("lmql://constraints/{name}")
def get_constraint_definition(name: str) -> dict[str, Any]:
    """Retrieve the definition of a named LMQL constraint.

    Raises:
        ToolError: If the constraint name is not registered; the error message lists available constraints.

    Returns:
        dict: Constraint definition containing fields such as pattern, examples, and LMQL syntax.
    """
    constraint = ConstraintRegistry.get(name)
    if not constraint:
        available = ConstraintRegistry.list_constraints()
        raise ToolError(
            f"Unknown constraint: '{name}'. Available: {', '.join(available)}"
        )
    return constraint.get_definition()


@mcp.tool(annotations={"readOnlyHint": True})
def constraint_validate(
    constraint_name: Annotated[
        str,
        Field(
            description="Name of the constraint to validate against (e.g., 'YQ_PATH', 'CONFIG_FORMAT', 'INT')"
        ),
    ],
    value: Annotated[str, Field(description="Value to validate")],
) -> dict[str, Any]:
    """Validate a value against an LMQL-style constraint.

    Use this tool to check if a value satisfies a constraint before using it
    in other operations. Supports partial validation - can tell if an incomplete
    input could still become valid.

    Output contract: Returns {"valid": bool, "error": str?, "is_partial": bool?, ...}.
    Side effects: None (read-only validation).
    Failure modes: ToolError if constraint name unknown.

    Available constraints:
    - YQ_PATH: Valid yq path (e.g., '.users[0].name')
    - YQ_EXPRESSION: Valid yq expression with pipes (e.g., '.items | length')
    - CONFIG_FORMAT: Valid format ('json', 'yaml', 'toml', 'xml')
    - KEY_PATH: Dot-separated key path (e.g., 'config.database.host')
    - INT: Valid integer
    - JSON_VALUE: Valid JSON syntax
    - FILE_PATH: Valid file path syntax
    """
    result = validate_tool_input(constraint_name, value)
    response = result.to_dict()
    response["constraint"] = constraint_name
    response["value"] = value

    # Add hint for invalid values
    if not result.valid:
        hint = get_constraint_hint(constraint_name, value)
        if hint:
            response["hint"] = hint

    return response


@mcp.tool(annotations={"readOnlyHint": True})
def constraint_list() -> dict[str, Any]:
    """Return a list of all registered LMQL constraints with their metadata.

    Returns:
        result (dict): A dictionary with keys:
            - "constraints": a list of constraint objects; each object includes a "name" key and the constraint's definition fields (e.g., "description", any other metadata).
            - "usage": a string describing how to validate a value against a constraint (e.g., call `constraint_validate(constraint_name, value)`).
    """
    definitions = ConstraintRegistry.get_all_definitions()
    return {
        "constraints": [{"name": name, **defn} for name, defn in definitions.items()],
        "usage": (
            "Use constraint_validate(constraint_name, value) to validate inputs. "
            "Access constraint definitions via lmql://constraints/{name} resource."
        ),
    }


@mcp.prompt()
def explain_config(file_path: str) -> str:
    """Produce a natural-language prompt that requests an analysis of a configuration file.

    The generated prompt asks an assistant to:
    1. Identify the file format (JSON, YAML, TOML).
    2. Summarize the file's key sections and their purpose.
    3. Highlight critical settings and potential misconfigurations.
    4. Check adherence to an available schema, if one exists.

    Parameters:
        file_path (str): Path to the configuration file to be analyzed.

    Returns:
        prompt (str): A formatted prompt string referring to the provided file path.
    """
    return f"""Please analyze and explain the configuration file at '{file_path}'.

    1. Identify the file format (JSON, YAML, TOML).
    2. Summarize the key sections and their purpose.
    3. Highlight any critical settings or potential misconfigurations.
    4. If a schema is available, check if the config adheres to it.
    """


@mcp.prompt()
def suggest_improvements(file_path: str) -> str:
    """Generate a prompt to suggest improvements for a configuration file."""
    return f"""Please review the configuration file at '{file_path}' and suggest improvements.

    Consider:
    1. Security best practices (e.g., exposed secrets).
    2. Performance optimizations.
    3. Readability and structure (e.g., comments, organization).
    4. Redundant or deprecated settings.
    """


@mcp.prompt()
def convert_to_schema(file_path: str) -> str:
    """Generate a prompt to create a JSON schema from a configuration file."""
    return f"""Please generate a JSON schema based on the configuration file at '{file_path}'.

    1. Infer types for all fields.
    2. Mark fields as required or optional based on common patterns.
    3. Add descriptions for fields where the purpose is clear.
    4. Use standard JSON Schema Draft 7 or later.
    """


def main() -> None:  # pragma: no cover
    """Entry point for the MCP server."""
    mcp.run()


if __name__ == "__main__":  # pragma: no cover
    main()

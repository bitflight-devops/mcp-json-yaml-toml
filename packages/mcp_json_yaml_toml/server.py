"""MCP server for querying and modifying JSON, YAML, and TOML configuration files.

This server provides tools for reading, modifying, validating, and transforming
configuration files using yq. Tools are dynamically registered based on the
MCP_CONFIG_FORMATS environment variable.
"""

import base64
from pathlib import Path
from typing import Annotated, Any, Literal

import orjson
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from pydantic import Field

from mcp_json_yaml_toml.config import is_format_enabled, parse_enabled_formats, validate_format
from mcp_json_yaml_toml.schemas import SchemaManager
from mcp_json_yaml_toml.yq_wrapper import FormatType, YQError, YQExecutionError, execute_yq

# Initialize FastMCP server
mcp = FastMCP("config-tools", mask_error_details=False)

# Initialize Schema Manager
schema_manager = SchemaManager()

# Pagination constants
PAGE_SIZE_CHARS = 10000


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



def _paginate_result(result_str: str, cursor: str | None, advisory_hint: str | None = None) -> dict[str, Any]:
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
        if total_pages > 2:
            base_advisory = (
                f"Result spans {total_pages} pages ({len(result_str):,} chars). "
                "Consider querying for specific keys (e.g., '.data | keys') or counts "
                "(e.g., '.items | length') to reduce result size."
            )
            response["advisory"] = f"{base_advisory} {advisory_hint}" if advisory_hint else base_advisory

    return response


def _summarize_structure(data: Any, depth: int = 0, max_depth: int = 1) -> Any:
    """Create a summary of the data structure.

    Args:
        data: The data to summarize
        depth: Current recursion depth
        max_depth: Maximum depth to traverse

    Returns:
        Summarized data structure
    """
    if depth > max_depth:
        if isinstance(data, dict):
            return f"<dict with {len(data)} keys>"
        elif isinstance(data, list):
            return f"<list with {len(data)} items>"
        else:
            return type(data).__name__

    if isinstance(data, dict):
        # Return keys with their types/summaries
        return {k: _summarize_structure(v, depth + 1, max_depth) for k, v in data.items()}
    elif isinstance(data, list):
        if not data:
            return []
        # Show summary and first item as sample
        summary = f"<list with {len(data)} items>"
        sample = _summarize_structure(data[0], depth + 1, max_depth)
        return {"__summary__": summary, "first_item_sample": sample}
    else:
        # Primitive
        s = str(data)
        if len(s) > 100:
            return s[:97] + "..."
        return data


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
    format_map = {".json": "json", ".yaml": "yaml", ".yml": "yaml", ".toml": "toml", ".xml": "xml"}

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
    schema_patterns = [f"{base_name}.schema.json", f"{base_name}.schema.yaml", f"{base_name}.schema.yml"]

    for pattern in schema_patterns:
        schema_path = config_path.parent / pattern
        if schema_path.exists():
            return schema_path

    return None


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
        schema_result = execute_yq(".", input_file=schema_path, input_format=schema_format, output_format="json")

        if schema_result.data is None:
            return False, f"Failed to parse schema file: {schema_path}"

        schema = schema_result.data

        # Validate
        jsonschema.validate(instance=data, schema=schema)
    except jsonschema.ValidationError as e:
        return False, f"Schema validation failed: {e.message}"
    except YQError as e:
        return False, f"Failed to load schema: {e}"
    except Exception as e:
        return False, f"Unexpected schema validation error: {e}"
    else:
        return True, "Schema validation passed"


@mcp.tool(annotations={"readOnlyHint": True})
def data_query(
    file_path: Annotated[str, Field(description="Path to configuration file")],
    expression: Annotated[
        str, Field(description="yq expression to evaluate (e.g., '.name', '.items[]', '.data.users')")
    ],
    output_format: Annotated[
        Literal["json", "yaml", "toml"] | None,
        Field(description="Output format (defaults to same as input file format)"),
    ] = None,
    cursor: Annotated[
        str | None, Field(description="Pagination cursor from previous response (omit for first page)")
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
    input_format = _detect_file_format(path)
    if not is_format_enabled(input_format):
        enabled = parse_enabled_formats()
        raise ToolError(
            f"Format '{input_format}' is not enabled. Enabled formats: {', '.join(f.value for f in enabled)}"
        )

    # Use input format as output if not specified
    output_format = input_format if output_format is None else validate_format(output_format).value  # type: ignore[assignment]

    try:
        result = execute_yq(expression, input_file=path, input_format=input_format, output_format=output_format)  # type: ignore[arg-type]

        # Prepare result string for pagination
        result_str = result.stdout if output_format != "json" else orjson.dumps(result.data, option=orjson.OPT_INDENT_2).decode()

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
                "format": output_format,
                "file": str(path),
                "paginated": True,
            }
            if "nextCursor" in pagination:
                response["nextCursor"] = pagination["nextCursor"]
            if "advisory" in pagination:
                response["advisory"] = pagination["advisory"]
            return response
        else:
            # Small result - no pagination needed
            return {
                "success": True,
                "result": result_str if output_format != "json" else result.data,
                "format": output_format,
                "file": str(path),
            }

    except YQExecutionError as e:
        raise ToolError(f"Query failed: {e}") from e


@mcp.tool()
def data(
    file_path: Annotated[str, Field(description="Path to configuration file")],
    operation: Annotated[Literal["get", "set", "delete"], Field(description="Operation: 'get', 'set', or 'delete'")],
    key_path: Annotated[str | None, Field(description="Dot-separated key path (required for set/delete, optional for get)")] = None,
    value: Annotated[str | None, Field(description="Value to set as JSON string (required for operation='set')")] = None,
    type: Annotated[Literal["data", "schema"], Field(description="Type for get: 'data' or 'schema'")] = "data",
    return_type: Annotated[Literal["keys", "all"], Field(description="Return type for get: 'keys' (structure) or 'all' (full data)")] = "all",
    output_format: Annotated[Literal["json", "yaml", "toml"] | None, Field(description="Output format")] = None,
    in_place: Annotated[bool, Field(description="Modify file in place (for set/delete)")] = False,
    cursor: Annotated[str | None, Field(description="Pagination cursor")] = None,
) -> dict[str, Any]:
    """Read, update, or delete configuration data.

    Use when you need to read, update, or delete specific values or entire sections in a configuration file.

    Output contract: Returns {"success": bool, "result": Any, "file": str, ...}.
    Side effects: Modifies file on disk if operation is 'set' or 'delete' and in_place=True.
    Failure modes: FileNotFoundError if file missing. ToolError if format disabled or invalid JSON.

    Operations:
    - get: Retrieve data, schema, or structure
    - set: Update/create value at key_path
    - delete: Remove key/element at key_path
    """
    path = Path(file_path).expanduser().resolve()
    
    if not path.exists():
        raise ToolError(f"File not found: {file_path}")
    
    # Get schema info for this file (lightweight, doesn't fetch full schema)
    schema_info = schema_manager.get_schema_info_for_file(path)
    
    # Handle GET operation
    if operation == "get":
        # Schema request
        if type == "schema":
            schema_data = schema_manager.get_schema_for_file(path)
            if schema_data:
                response = {
                    "success": True,
                    "file": str(path),
                    "schema": schema_data,
                    "message": "Schema found via Schema Store"
                }
                if schema_info:
                    response["schema_info"] = schema_info
                return response
            else:
                return {
                    "success": False,
                    "file": str(path),
                    "message": f"No schema found for file: {path.name}"
                }
        
        # Data/structure request
        input_format = _detect_file_format(path)
        if not is_format_enabled(input_format):
            enabled = parse_enabled_formats()
            raise ToolError(f"Format '{input_format}' is not enabled. Enabled formats: {', '.join(f.value for f in enabled)}")
        
        output_fmt = input_format if output_format is None else validate_format(output_format).value
        
        # Structure request (keys only)
        if return_type == "keys":
            expression = "." if not key_path else (f".{key_path}" if not key_path.startswith(".") else key_path)
            try:
                result = execute_yq(expression, input_file=path, input_format=input_format, output_format="json")
                if result.data is None:
                    response = {"success": True, "result": None, "format": "json", "file": str(path), "structure_summary": "Empty or invalid data"}
                    if schema_info:
                        response["schema_info"] = schema_info
                    return response
                
                summary = _summarize_structure(result.data, max_depth=1)
                summary_str = orjson.dumps(summary, option=orjson.OPT_INDENT_2).decode()
                
                if len(summary_str) > PAGE_SIZE_CHARS or cursor is not None:
                    pagination = _paginate_result(summary_str, cursor)
                    response = {"success": True, "result": pagination["data"], "format": "json", "file": str(path), "paginated": True}
                    if "nextCursor" in pagination:
                        response["nextCursor"] = pagination["nextCursor"]
                    return response
                else:
                    response = {"success": True, "result": summary, "format": "json", "file": str(path)}
                    if schema_info:
                        response["schema_info"] = schema_info
                    return response
            except YQExecutionError as e:
                raise ToolError(f"Query failed: {e}") from e
        
        # Data request (full data)
        if key_path is None:
            raise ToolError("key_path is required when operation='get' and type='data'")
        
        expression = f".{key_path}" if not key_path.startswith(".") else key_path
        
        try:
            result = execute_yq(expression, input_file=path, input_format=input_format, output_format=output_fmt)
            result_str = result.stdout if output_fmt != "json" else orjson.dumps(result.data, option=orjson.OPT_INDENT_2).decode()
            
            if len(result_str) > PAGE_SIZE_CHARS or cursor is not None:
                hint = None
                if isinstance(result.data, list):
                    hint = "Result is a list. Use '.[start:end]' to slice or '. | length' to count."
                elif isinstance(result.data, dict):
                    hint = "Result is an object. Use '.key' to select or '. | keys' to list keys."
                
                pagination = _paginate_result(result_str, cursor, advisory_hint=hint)
                response = {"success": True, "result": pagination["data"], "format": output_fmt, "file": str(path), "paginated": True}
                if "nextCursor" in pagination:
                    response["nextCursor"] = pagination["nextCursor"]
                if "advisory" in pagination:
                    response["advisory"] = pagination["advisory"]
                return response
            else:
                response = {"success": True, "result": result_str if output_fmt != "json" else result.data, "format": output_fmt, "file": str(path)}
                if schema_info:
                    response["schema_info"] = schema_info
                return response
        except YQExecutionError as e:
            raise ToolError(f"Query failed: {e}") from e
    
    # Handle SET operation
    elif operation == "set":
        if key_path is None:
            raise ToolError("key_path is required for operation='set'")
        if value is None:
            raise ToolError("value is required for operation='set'")
        
        input_format = _detect_file_format(path)
        if not is_format_enabled(input_format):
            enabled = parse_enabled_formats()
            raise ToolError(f"Format '{input_format}' is not enabled. Enabled formats: {', '.join(f.value for f in enabled)}")
        
        try:
            parsed_value = orjson.loads(value)
        except orjson.JSONDecodeError as e:
            raise ToolError(f"Invalid JSON value: {e}") from e
        
        # TOML requires special handling since yq cannot write TOML
        if input_format == "toml":
            from mcp_json_yaml_toml.toml_utils import set_toml_value
            
            try:
                modified_toml = set_toml_value(path, key_path, parsed_value)
                
                if in_place:
                    path.write_text(modified_toml, encoding="utf-8")
                    response = {
                        "success": True,
                        "modified_in_place": True,
                        "result": "File modified successfully",
                        "file": str(path)
                    }
                else:
                    response = {
                        "success": True,
                        "modified_in_place": False,
                        "result": modified_toml,
                        "file": str(path)
                    }
                
                if schema_info:
                    response["schema_info"] = schema_info
                return response
            except Exception as e:
                raise ToolError(f"TOML set operation failed: {e}") from e
        
        # YAML/JSON use yq
        yq_value = orjson.dumps(parsed_value).decode() if isinstance(parsed_value, str) else value
        expression = f".{key_path} = {yq_value}" if not key_path.startswith(".") else f"{key_path} = {yq_value}"
        
        try:
            result = execute_yq(expression, input_file=path, input_format=input_format, output_format=input_format, in_place=in_place)
            
            # Optimize YAML files with anchors if in_place and format is YAML
            optimized = False
            if in_place and input_format == "yaml":
                # Check if file already uses anchors before optimizing
                # This respects the original file's conventions and avoids adding
                # anchors to files whose parsers might not support them
                original_content = path.read_text(encoding="utf-8")
                file_uses_anchors = "&" in original_content or "*" in original_content
                
                if file_uses_anchors:
                    from mcp_json_yaml_toml.yaml_optimizer import optimize_yaml_file
                    
                    # Re-parse the modified file to get the data
                    reparse_result = execute_yq(".", input_file=path, input_format="yaml", output_format="json")
                    
                    if reparse_result.data is not None:
                        # Try to optimize
                        optimized_yaml = optimize_yaml_file(reparse_result.data)
                        
                        if optimized_yaml:
                            # Write optimized YAML back to file
                            path.write_text(optimized_yaml, encoding="utf-8")
                            optimized = True
            
            response = {
                "success": True,
                "modified_in_place": in_place,
                "result": result.stdout if not in_place else "File modified successfully",
                "file": str(path)
            }
            
            if optimized:
                response["optimized"] = True
                response["message"] = "File modified and optimized with YAML anchors"
            
            if schema_info:
                response["schema_info"] = schema_info
            return response
        except YQExecutionError as e:
            raise ToolError(f"Set operation failed: {e}") from e
    
    # Handle DELETE operation
    elif operation == "delete":
        if key_path is None:
            raise ToolError("key_path is required for operation='delete'")
        
        input_format = _detect_file_format(path)
        if not is_format_enabled(input_format):
            enabled = parse_enabled_formats()
            raise ToolError(f"Format '{input_format}' is not enabled. Enabled formats: {', '.join(f.value for f in enabled)}")
        
        # TOML requires special handling since yq cannot write TOML
        if input_format == "toml":
            from mcp_json_yaml_toml.toml_utils import delete_toml_key
            
            try:
                modified_toml = delete_toml_key(path, key_path)
                
                if in_place:
                    path.write_text(modified_toml, encoding="utf-8")
                    response = {
                        "success": True,
                        "modified_in_place": True,
                        "result": "File modified successfully",
                        "file": str(path)
                    }
                else:
                    response = {
                        "success": True,
                        "modified_in_place": False,
                        "result": modified_toml,
                        "file": str(path)
                    }
                
                if schema_info:
                    response["schema_info"] = schema_info
                return response
            except KeyError as e:
                raise ToolError(f"TOML delete operation failed: {e}") from e
            except Exception as e:
                raise ToolError(f"TOML delete operation failed: {e}") from e
        
        # YAML/JSON use yq
        expression = f"del(.{key_path})" if not key_path.startswith(".") else f"del({key_path})"
        
        try:
            result = execute_yq(expression, input_file=path, input_format=input_format, output_format=input_format, in_place=in_place)
            response = {"success": True, "modified_in_place": in_place, "result": result.stdout if not in_place else "File modified successfully", "file": str(path)}
            if schema_info:
                response["schema_info"] = schema_info
            return response
        except YQExecutionError as e:
            raise ToolError(f"Delete operation failed: {e}") from e



@mcp.tool()
def data_schema(
    action: Annotated[Literal["validate", "scan", "add_dir", "add_catalog", "associate", "disassociate", "list"], Field(description="Action: validate, scan, add_dir, add_catalog, associate, disassociate, or list")],
    file_path: Annotated[str | None, Field(description="Path to file (for validate/associate/disassociate actions)")] = None,
    schema_path: Annotated[str | None, Field(description="Path to schema file (for validate action)")] = None,
    schema_url: Annotated[str | None, Field(description="Schema URL (for associate action)")] = None,
    schema_name: Annotated[str | None, Field(description="Schema name from catalog (for associate action)")] = None,
    search_paths: Annotated[list[str] | None, Field(description="Paths to scan (for scan action)")] = None,
    path: Annotated[str | None, Field(description="Directory path (for add_dir action)")] = None,
    name: Annotated[str | None, Field(description="Catalog name (for add_catalog action)")] = None,
    uri: Annotated[str | None, Field(description="Catalog URI (for add_catalog action)")] = None,
    max_depth: Annotated[int, Field(description="Max search depth (for scan action)")] = 5,
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
      - action="associate", file_path="gitlab-ci.yml", schema_name="gitlab-ci"
      - action="disassociate", file_path="gitlab-ci.yml"
      - action="list"
    """
    # Handle VALIDATE action
    if action == "validate":
        if not file_path:
            raise ToolError("file_path required for validate action")
        
        path = Path(file_path).expanduser().resolve()
        if not path.exists():
            raise ToolError(f"File not found: {file_path}")
        
        input_format = _detect_file_format(path)
        if not is_format_enabled(input_format):
            enabled = parse_enabled_formats()
            raise ToolError(f"Format '{input_format}' is not enabled. Enabled formats: {', '.join(f.value for f in enabled)}")
        
        validation_results: dict[str, Any] = {
            "file": str(path),
            "format": input_format,
            "syntax_valid": False,
            "schema_validated": False,
        }
        
        try:
            result = execute_yq(".", input_file=path, input_format=input_format, output_format="json")
            validation_results["syntax_valid"] = True
            validation_results["syntax_message"] = "Syntax is valid"
            
            schema_file: Path | None = None
            if schema_path:
                schema_file = Path(schema_path).expanduser().resolve()
                if not schema_file.exists():
                    raise ToolError(f"Schema file not found: {schema_path}")
            else:
                schema_data = schema_manager.get_schema_for_file(path)
                if schema_data:
                    import tempfile
                    with tempfile.NamedTemporaryFile(mode='wb', suffix='.json', delete=False) as tmp:
                        tmp.write(orjson.dumps(schema_data))
                        schema_file = Path(tmp.name)
                else:
                    schema_file = _find_schema_file(path)
            
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
    
    # Handle SCAN action
    elif action == "scan":
        if not search_paths:
            raise ToolError("search_paths required for scan action")
        
        paths = [Path(p).expanduser().resolve() for p in search_paths]
        discovered = schema_manager.scan_for_schema_dirs(paths, max_depth=max_depth)
        
        return {
            "success": True,
            "action": "scan",
            "discovered_count": len(discovered),
            "discovered_dirs": [str(p) for p in discovered]
        }
    
    # Handle ADD_DIR action
    elif action == "add_dir":
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
            "message": "Directory added to schema cache locations"
        }
    
    # Handle ADD_CATALOG action
    elif action == "add_catalog":
        if not name or not uri:
            raise ToolError("name and uri required for add_catalog action")
        
        schema_manager.add_custom_catalog(name, uri)
        
        return {
            "success": True,
            "action": "add_catalog",
            "name": name,
            "uri": uri,
            "message": "Custom catalog added"
        }
    
    # Handle ASSOCIATE action
    elif action == "associate":
        if not file_path:
            raise ToolError("file_path required for associate action")
        
        path = Path(file_path).expanduser().resolve()
        if not path.exists():
            raise ToolError(f"File not found: {file_path}")
        
        # Get schema URL - either from schema_url parameter or look up schema_name in catalog
        url = schema_url
        name = schema_name
        
        if not url and schema_name:
            # Look up schema URL from catalog by name
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
        
        schema_manager.add_file_association(path, url, name)
        
        return {
            "success": True,
            "action": "associate",
            "file": str(path),
            "schema_name": name or "unknown",
            "schema_url": url,
            "message": "File associated with schema"
        }
    
    # Handle DISASSOCIATE action
    elif action == "disassociate":
        if not file_path:
            raise ToolError("file_path required for disassociate action")
        
        path = Path(file_path).expanduser().resolve()
        removed = schema_manager.remove_file_association(path)
        
        return {
            "success": True,
            "action": "disassociate",
            "file": str(path),
            "removed": removed,
            "message": "Association removed" if removed else "No association found"
        }
    
    # Handle LIST action
    elif action == "list":
        config = schema_manager.get_config()
        
        return {
            "success": True,
            "action": "list",
            "config": config
        }



@mcp.tool(annotations={"readOnlyHint": True})
def data_convert(
    file_path: Annotated[str, Field(description="Path to source configuration file")],
    output_format: Annotated[Literal["json", "yaml", "toml"], Field(description="Target format to convert to")],
    output_file: Annotated[
        str | None, Field(description="Optional output file path (if not provided, returns converted content)")
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
    output_fmt = validate_format(output_format).value

    if input_format == output_fmt:
        raise ToolError(f"Input and output formats are the same: {input_format}")

    try:
        # Convert
        result = execute_yq(".", input_file=path, input_format=input_format, output_format=output_fmt)  # type: ignore[arg-type]

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
        else:
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
    file_path1: Annotated[str, Field(description="Path to first configuration file (base)")],
    file_path2: Annotated[str, Field(description="Path to second configuration file (overlay)")],
    output_format: Annotated[
        Literal["json", "yaml", "toml"] | None, Field(description="Output format (defaults to format of first file)")
    ] = None,
    output_file: Annotated[
        str | None, Field(description="Optional output file path (if not provided, returns merged content)")
    ] = None,
) -> dict[str, Any]:
    """Merge two configuration files.

    Use when you need to combine two configuration files into a single result (deep merge).

    Output contract: Returns {"success": bool, "result": str, ...} or writes to file.
    Side effects: Writes to output_file if provided.
    Failure modes: FileNotFoundError if files missing. ToolError if formats disabled or merge fails.
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
    output_fmt = output_format if output_format else format1
    output_fmt = validate_format(output_fmt).value

    try:
        # Read both files into JSON for merging
        result1 = execute_yq(".", input_file=path1, input_format=format1, output_format="json")
        result2 = execute_yq(".", input_file=path2, input_format=format2, output_format="json")

        # Merge using yq's multiply operator (*)
        # This does a deep merge
        merged_json = orjson.dumps(result1.data).decode() if result1.data else "{}"
        overlay_json = orjson.dumps(result2.data).decode() if result2.data else "{}"

        # Use yq to merge
        merge_expression = f". * {overlay_json}"
        merge_result = execute_yq(
            merge_expression, input_data=merged_json, input_format="json", output_format=output_fmt
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
        else:
            return {
                "success": True,
                "file1": str(path1),
                "file2": str(path2),
                "output_format": output_fmt,
                "result": merge_result.stdout,
            }

    except YQExecutionError as e:
        raise ToolError(f"Merge failed: {e}") from e



@mcp.prompt()
def explain_config(file_path: str) -> str:
    """Generate a prompt to explain a configuration file."""
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


def main() -> None:
    """Entry point for the MCP server."""
    mcp.run()


if __name__ == "__main__":
    main()

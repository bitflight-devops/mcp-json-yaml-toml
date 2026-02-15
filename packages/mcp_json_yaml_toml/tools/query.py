"""The ``data_query`` tool -- read-only data extraction and filtering."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

from fastmcp.exceptions import ToolError
from pydantic import Field

from mcp_json_yaml_toml.config import (
    is_format_enabled,
    parse_enabled_formats,
    validate_format,
)
from mcp_json_yaml_toml.formats.base import _detect_file_format
from mcp_json_yaml_toml.models.responses import (
    DataResponse,  # noqa: TC001 — runtime import required by FastMCP/Pydantic for return-type resolution
)
from mcp_json_yaml_toml.server import mcp
from mcp_json_yaml_toml.services.data_operations import _build_query_response
from mcp_json_yaml_toml.yq_wrapper import FormatType, YQExecutionError, execute_yq


@mcp.tool(
    timeout=60.0,
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
def data_query(
    file_path: Annotated[str, Field(description="Path to file")],
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
) -> DataResponse:
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
    # Use input format as output if not specified
    output_format_value: FormatType = (
        input_format if output_format is None else validate_format(output_format)
    )

    try:
        result = execute_yq(
            expression,
            input_file=path,
            input_format=input_format,
            output_format=output_format_value,
        )
        return _build_query_response(result, output_format_value, path, cursor)

    except YQExecutionError as e:
        # Auto-fallback to JSON if TOML output was auto-selected and yq can't encode nested structures
        if (
            not output_format_explicit
            and output_format_value == FormatType.TOML
            and input_format == FormatType.TOML
            and "only scalars" in str(e.stderr)
        ):
            # Retry with JSON output format
            result = execute_yq(
                expression,
                input_file=path,
                input_format=input_format,
                output_format=FormatType.JSON,
            )
            return _build_query_response(result, FormatType.JSON, path, cursor)
        raise ToolError(f"Query failed: {e}") from e

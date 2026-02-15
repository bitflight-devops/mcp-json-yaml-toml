"""The ``data_convert`` and ``data_merge`` tools -- format conversion and file merging."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any, Literal

import orjson
from fastmcp.exceptions import ToolError
from pydantic import Field

from mcp_json_yaml_toml.config import (
    is_format_enabled,
    parse_enabled_formats,
    validate_format,
)
from mcp_json_yaml_toml.formats.base import _detect_file_format
from mcp_json_yaml_toml.server import mcp
from mcp_json_yaml_toml.yq_wrapper import FormatType, YQExecutionError, execute_yq


@mcp.tool(
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    }
)
def data_convert(
    file_path: Annotated[str, Field(description="Path to source file")],
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
    """Convert file format.

    Use when you need to transform a file from one format (JSON, YAML, TOML) to another.

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
    output_fmt: FormatType = validate_format(output_format)

    if input_format == output_fmt:
        raise ToolError(f"Input and output formats are the same: {input_format}")

    # JSON/YAML to TOML conversion is not supported due to yq limitations
    # yq's TOML encoder only supports scalar values, not complex nested structures
    if output_fmt == FormatType.TOML and input_format in {
        FormatType.JSON,
        FormatType.YAML,
    }:
        raise ToolError(
            f"Conversion from {input_format.upper()} to TOML is not supported. "
            "The underlying yq tool cannot encode complex nested structures to TOML format. "
            "Supported conversions: JSON<>YAML, TOML->JSON, TOML->YAML."
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


@mcp.tool(
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    }
)
def data_merge(
    file_path1: Annotated[str, Field(description="Path to first file (base)")],
    file_path2: Annotated[str, Field(description="Path to second file (overlay)")],
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
    """Merge two files into a single deep-merged configuration.

    Performs a deep merge where values from the second (overlay) file override or extend
    those in the first (base) file. If output_file is provided the merged result is written
    to that path; otherwise the merged content is returned in the response.

    Parameters:
        file_path1 (str): Path to the base file.
        file_path2 (str): Path to the overlay file whose values override the base.
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
    output_fmt = validate_format(output_format or format1.value)

    try:
        # Read both files into JSON for merging
        result1 = execute_yq(
            ".", input_file=path1, input_format=format1, output_format=FormatType.JSON
        )
        result2 = execute_yq(
            ".", input_file=path2, input_format=format2, output_format=FormatType.JSON
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
            input_format=FormatType.JSON,
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

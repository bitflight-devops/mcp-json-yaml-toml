"""The ``data_diff`` tool -- structured comparison of configuration files."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

from fastmcp.exceptions import ToolError
from pydantic import Field

from mcp_json_yaml_toml.config import is_format_enabled, parse_enabled_formats
from mcp_json_yaml_toml.formats.base import _detect_file_format
from mcp_json_yaml_toml.models.responses import DiffResponse
from mcp_json_yaml_toml.server import mcp
from mcp_json_yaml_toml.services.diff_operations import (
    build_diff_statistics,
    build_diff_summary,
    compute_diff,
)
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
def data_diff(
    file_path1: Annotated[str, Field(description="Path to first file (base)")],
    file_path2: Annotated[str, Field(description="Path to second file (comparison)")],
    ignore_order: Annotated[
        bool, Field(description="Ignore list/array ordering in comparison")
    ] = False,
) -> DiffResponse:
    """Compare two configuration files and return structured differences.

    Performs a deep comparison of two configuration files (JSON, YAML, TOML)
    and returns a structured diff with statistics and a human-readable summary.
    Supports cross-format comparison (e.g. JSON vs YAML).

    Output contract: Returns DiffResponse with has_differences, differences dict,
    statistics, and summary.
    Side effects: None (read-only).
    Failure modes: ToolError if files not found or formats disabled.
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
            f"Format of first file '{format1}' is not enabled. "
            f"Enabled formats: {', '.join(f.value for f in enabled)}"
        )
    if not is_format_enabled(format2):
        enabled = parse_enabled_formats()
        raise ToolError(
            f"Format of second file '{format2}' is not enabled. "
            f"Enabled formats: {', '.join(f.value for f in enabled)}"
        )

    try:
        # Parse both files to Python dicts via yq -> JSON pipeline
        result1 = execute_yq(
            ".", input_file=path1, input_format=format1, output_format=FormatType.JSON
        )
        result2 = execute_yq(
            ".", input_file=path2, input_format=format2, output_format=FormatType.JSON
        )

        data1 = result1.data
        data2 = result2.data

        # Compute diff
        diff_dict = compute_diff(data1, data2, ignore_order=ignore_order)
        has_differences = bool(diff_dict)

        # Build statistics and summary
        stats = build_diff_statistics(diff_dict) if has_differences else {}
        summary = build_diff_summary(stats, has_differences=has_differences)

        return DiffResponse(
            success=True,
            file1=str(path1),
            file2=str(path2),
            file1_format=format1.value
            if isinstance(format1, FormatType)
            else str(format1),
            file2_format=format2.value
            if isinstance(format2, FormatType)
            else str(format2),
            has_differences=has_differences,
            summary=summary,
            differences=diff_dict if has_differences else None,
            statistics=stats if has_differences else None,
        )

    except YQExecutionError as e:
        raise ToolError(f"Diff failed: {e}") from e

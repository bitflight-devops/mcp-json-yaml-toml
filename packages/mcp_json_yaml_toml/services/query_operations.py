"""Query response builder for data_query tool.

Standalone function used by tools/query.py to format yq results.
Extracted from data_operations.py (ARCH-06).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import orjson

from mcp_json_yaml_toml.backends.base import FormatType
from mcp_json_yaml_toml.models.responses import DataResponse
from mcp_json_yaml_toml.services.pagination import (
    PAGE_SIZE_CHARS,
    _get_pagination_hint,
    _paginate_result,
)

if TYPE_CHECKING:
    from pathlib import Path

__all__ = ["_build_query_response"]


def _build_query_response(
    result: Any, output_format: FormatType, path: Path, cursor: str | None
) -> DataResponse:
    """Build response for data_query.

    Args:
        result: YQ execution result
        output_format: Output format
        path: File path
        cursor: Pagination cursor

    Returns:
        DataResponse model instance
    """
    result_str = (
        result.stdout
        if output_format != FormatType.JSON
        else orjson.dumps(result.data, option=orjson.OPT_INDENT_2).decode()
    )

    if len(result_str) > PAGE_SIZE_CHARS or cursor is not None:
        hint = _get_pagination_hint(result.data)
        pagination = _paginate_result(result_str, cursor, advisory_hint=hint)
        return DataResponse(
            success=True,
            result=pagination["data"],
            format=output_format,
            file=str(path),
            paginated=True,
            nextCursor=pagination.get("nextCursor"),
            advisory=pagination.get("advisory"),
        )

    return DataResponse(
        success=True,
        result=result_str if output_format != FormatType.JSON else result.data,
        format=output_format,
        file=str(path),
    )

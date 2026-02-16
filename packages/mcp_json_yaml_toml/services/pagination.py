"""Pagination logic for cursor-based result chunking and structure summarization.

Extracted from server.py to reduce complexity and create a focused, testable module.
This module is fully self-contained with no project-internal dependencies.
"""

from __future__ import annotations

import base64
from typing import Any

import orjson
from fastmcp.exceptions import ToolError

__all__ = [
    "ADVISORY_PAGE_THRESHOLD",
    "MAX_PRIMITIVE_DISPLAY_LENGTH",
    "PAGE_SIZE_CHARS",
    "_decode_cursor",
    "_encode_cursor",
    "_get_pagination_hint",
    "_paginate_result",
    "_summarize_depth_exceeded",
    "_summarize_list_structure",
    "_summarize_primitive",
    "_summarize_structure",
]

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


def _summarize_depth_exceeded(data: Any) -> Any:
    """Return summary showing keys for dicts (recursively) when max depth is exceeded.

    Args:
        data: The data to summarize

    Returns:
        Dict with keys mapped to summaries, or type string for primitives
    """
    if isinstance(data, dict):
        return {k: _summarize_depth_exceeded(v) for k, v in data.items()}
    if isinstance(data, list):
        return f"<list with {len(data)} items>"
    return type(data).__name__


def _summarize_primitive(data: Any, full_keys_mode: bool) -> Any:
    """Summarize a primitive value.

    Args:
        data: The primitive value
        full_keys_mode: If True, return type name only

    Returns:
        Type name or truncated string value
    """
    if full_keys_mode:
        return type(data).__name__
    s = str(data)
    if len(s) <= MAX_PRIMITIVE_DISPLAY_LENGTH:
        return s
    return s[: MAX_PRIMITIVE_DISPLAY_LENGTH - 3] + "..."


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
        return _summarize_depth_exceeded(data)

    if isinstance(data, dict):
        return {
            k: _summarize_structure(v, depth + 1, max_depth, full_keys_mode)
            for k, v in data.items()
        }
    if isinstance(data, list):
        return _summarize_list_structure(data, depth, max_depth, full_keys_mode)
    return _summarize_primitive(data, full_keys_mode)


def _get_pagination_hint(data: Any) -> str | None:
    """Get advisory hint for paginated data.

    Args:
        data: The result data

    Returns:
        Hint string or None
    """
    if isinstance(data, list):
        return "Result is a list. Use '.[start:end]' to slice or '. | length' to count."
    if isinstance(data, dict):
        return "Result is an object. Use '.key' to select or '. | keys' to list keys."
    return None

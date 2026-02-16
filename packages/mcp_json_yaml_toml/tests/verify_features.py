"""Verification tests for MCP JSON/YAML/TOML server features.

This module contains verification tests for data_query tool and pagination hints.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, cast

from mcp_json_yaml_toml.models.responses import DataResponse
from mcp_json_yaml_toml.server import data_query

if TYPE_CHECKING:
    from collections.abc import Callable


# FastMCP 3.x: decorators return the original function directly.
_data_query = cast("Callable[..., DataResponse]", data_query)


def test_hints() -> None:
    """Test pagination hints with a large file query.

    Verifies that data_query returns a properly structured DataResponse,
    and validates pagination fields when the response is paginated.
    """
    github_test_yml = Path(".github/workflows/test.yml")
    result = _data_query(str(github_test_yml), ".", output_format="json")

    assert isinstance(result, DataResponse)
    assert result.success is True

    if result.paginated:
        assert result.advisory is not None, "Paginated response must include advisory"
        assert result.nextCursor is not None, (
            "Paginated response must include nextCursor"
        )
    else:
        assert result.result is not None, "Non-paginated response must include result"
        assert len(str(result.result)) > 0, "Result must be non-empty"


if __name__ == "__main__":
    try:
        test_hints()
    except Exception as e:
        print(f"Test failed: {e}")
        import traceback

        traceback.print_exc()

"""Verification tests for MCP JSON/YAML/TOML server features.

This module contains verification tests for data_query tool and pagination hints.
"""

from pathlib import Path
from typing import Any

from mcp_json_yaml_toml.server import data_query


def call_tool(tool: object, *args: Any, **kwargs: Any) -> dict[str, Any]:
    """Call a FastMCP tool function, extracting .fn if present.

    Args:
        tool: Either a FastMCP FunctionTool wrapper or a callable function.
        *args: Positional arguments to pass to the tool function.
        **kwargs: Keyword arguments to pass to the tool function.

    Returns:
        The dictionary result from calling the tool function.

    Raises:
        TypeError: If the tool is not callable.
    """
    # FastMCP wraps tools in FunctionTool which has .fn attribute
    # If no .fn attribute, assume tool is already callable
    fn_attr = getattr(tool, "fn", None)
    func = fn_attr if fn_attr is not None else tool
    if not callable(func):
        raise TypeError(f"Tool {tool!r} is not callable and has no .fn attribute")
    result = func(*args, **kwargs)
    if not isinstance(result, dict):
        raise TypeError(f"Expected dict result, got {type(result)}")
    return result


def test_hints() -> None:
    """Test pagination hints with a large file query."""
    print("\nTesting hints...")
    # Query that returns the whole file (which is large)
    github_test_yml = Path(".github/workflows/test.yml")
    print(f"Querying {github_test_yml} as JSON to trigger pagination")
    result = call_tool(data_query, str(github_test_yml), ".", output_format="json")

    if result.get("paginated"):
        print("Pagination active")
        print("Advisory:", result.get("advisory"))
    else:
        print("Result was not paginated (size:", len(str(result.get("result"))), ")")


if __name__ == "__main__":
    try:
        test_hints()
    except Exception as e:
        print(f"Test failed: {e}")
        import traceback

        traceback.print_exc()

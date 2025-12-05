"""Integration tests for FastMCP client with MCP JSON/YAML/TOML server.

These tests verify the server's behavior through the FastMCP client interface.
"""

import json
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any

import pytest
import pytest_asyncio
from fastmcp import Client
from fastmcp.client.client import CallToolResult
from mcp.types import TextContent

from mcp_json_yaml_toml.server import mcp


def extract_text_response(result: CallToolResult) -> dict[str, Any]:
    """Extract and parse JSON response from CallToolResult.

    Args:
        result: The result from client.call_tool()

    Returns:
        Parsed JSON response as dictionary

    Raises:
        AssertionError: If content is not TextContent
    """
    content = result.content[0]
    assert isinstance(content, TextContent), (
        f"Expected TextContent, got {type(content)}"
    )
    parsed: dict[str, Any] = json.loads(content.text)
    return parsed


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[Client[Any], None]:
    """Create a FastMCP client connected to the server using async context manager.

    Yields:
        Client: FastMCP client instance connected to the MCP server.
    """
    async with Client(mcp) as client:
        yield client


@pytest.mark.asyncio
async def test_data_query_json(client: Client[Any], tmp_path: Path) -> None:
    """Test data_query tool with a JSON file."""
    # Setup
    test_file = tmp_path / "test.json"
    data = {"users": [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]}
    test_file.write_text(json.dumps(data))

    # Execute
    result = await client.call_tool(
        "data_query",
        arguments={"file_path": str(test_file), "expression": ".users[0].name"},
    )

    # Parse response
    response = extract_text_response(result)

    assert response["success"] is True
    assert response["result"] == "Alice"
    assert response["format"] == "json"


@pytest.mark.asyncio
async def test_data_set_json(client: Client[Any], tmp_path: Path) -> None:
    """Test data tool (set operation) with a JSON file."""
    # Setup
    test_file = tmp_path / "config.json"
    data = {"settings": {"theme": "light"}}
    test_file.write_text(json.dumps(data))

    # Execute
    result = await client.call_tool(
        "data",
        arguments={
            "file_path": str(test_file),
            "operation": "set",
            "key_path": "settings.theme",
            "value": '"dark"',
        },
    )

    # Verify response
    response = extract_text_response(result)
    assert response["success"] is True
    assert response["result"] == "File modified successfully"

    # Verify file content
    new_content = json.loads(test_file.read_text())
    assert new_content["settings"]["theme"] == "dark"


@pytest.mark.asyncio
async def test_data_delete_json(client: Client[Any], tmp_path: Path) -> None:
    """Test data tool (delete operation) with a JSON file."""
    # Setup
    test_file = tmp_path / "data.json"
    data = {"temp": "delete_me", "keep": "me"}
    test_file.write_text(json.dumps(data))

    # Execute
    result = await client.call_tool(
        "data",
        arguments={
            "file_path": str(test_file),
            "operation": "delete",
            "key_path": "temp",
        },
    )

    # Verify
    response = extract_text_response(result)
    assert response["success"] is True

    # Verify file content
    new_content = json.loads(test_file.read_text())
    assert "temp" not in new_content
    assert new_content["keep"] == "me"


@pytest.mark.asyncio
async def test_error_handling_missing_file(client: Client[Any]) -> None:
    """Test error handling for missing file."""
    with pytest.raises(Exception) as excinfo:
        await client.call_tool(
            "data_query",
            arguments={"file_path": "/nonexistent/file.json", "expression": "."},
        )

    # FastMCP client might raise the tool error directly or wrap it
    # We check if the error message contains "File not found"
    assert "File not found" in str(excinfo.value)

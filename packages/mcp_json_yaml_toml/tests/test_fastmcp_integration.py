
import pytest
import pytest_asyncio
from fastmcp import Client
import json
from pathlib import Path
from mcp_json_yaml_toml.server import mcp

@pytest_asyncio.fixture
async def client():
    """Create a FastMCP client connected to the server using async context manager."""
    async with Client(mcp) as client:
        yield client



@pytest.mark.asyncio
async def test_data_query_json(client, tmp_path):
    """Test data_query tool with a JSON file."""
    # Setup
    test_file = tmp_path / "test.json"
    data = {"users": [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]}
    test_file.write_text(json.dumps(data))
    
    # Execute
    result = await client.call_tool(
        "data_query",
        arguments={
            "file_path": str(test_file),
            "expression": ".users[0].name"
        }
    )
    
    # FastMCP Client.call_tool returns CallToolResult
    # We need to parse the JSON content from the result
    # result.content is likely a list of TextContent
    assert result.content[0].type == "text"
    response = json.loads(result.content[0].text)
    
    assert response["success"] is True
    assert response["result"] == "Alice"
    assert response["format"] == "json"

@pytest.mark.asyncio
async def test_data_set_json(client, tmp_path):
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
            "in_place": True
        }
    )
    
    # Verify response
    response = json.loads(result.content[0].text)
    assert response["success"] is True
    assert response["modified_in_place"] is True
    
    # Verify file content
    new_content = json.loads(test_file.read_text())
    assert new_content["settings"]["theme"] == "dark"

@pytest.mark.asyncio
async def test_data_delete_json(client, tmp_path):
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
            "in_place": True
        }
    )
    
    # Verify
    response = json.loads(result.content[0].text)
    assert response["success"] is True
    
    # Verify file content
    new_content = json.loads(test_file.read_text())
    assert "temp" not in new_content
    assert new_content["keep"] == "me"

@pytest.mark.asyncio
async def test_error_handling_missing_file(client):
    """Test error handling for missing file."""
    with pytest.raises(Exception) as excinfo:
        await client.call_tool(
            "data_query",
            arguments={
                "file_path": "/nonexistent/file.json",
                "expression": "."
            }
        )
    
    # FastMCP client might raise the tool error directly or wrap it
    # We check if the error message contains "File not found"
    assert "File not found" in str(excinfo.value)

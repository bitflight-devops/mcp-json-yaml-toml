"""Tests for MCP server tools.

Comprehensive tests for all MCP tools: data_query, data, data_schema, data_convert, and data_merge.

Note: FastMCP 3.x decorators return the original function directly.
In 2.x, .fn was needed to access the underlying function; in 3.x it's not.
"""

from __future__ import annotations

import json
import time
import unittest.mock
from typing import TYPE_CHECKING, Any, cast

import pytest
from fastmcp.exceptions import ToolError

from mcp_json_yaml_toml import server
from mcp_json_yaml_toml.lmql_constraints import ConstraintRegistry
from mcp_json_yaml_toml.models.responses import ServerInfoResponse
from mcp_json_yaml_toml.yq_wrapper import FormatType

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

# FastMCP 3.x: decorators return the original function directly (no .fn needed).
# At runtime these are callable; cast to satisfy mypy's FunctionTool type.
data_query_fn = cast("Callable[..., Any]", server.data_query)
data_fn = cast("Callable[..., Any]", server.data)
data_schema_fn = cast("Callable[..., Any]", server.data_schema)
data_convert_fn = cast("Callable[..., Any]", server.data_convert)
data_merge_fn = cast("Callable[..., Any]", server.data_merge)


class TestDataQuery:
    """Test data_query tool."""

    @pytest.mark.integration
    def test_data_query_when_valid_json_then_returns_result(
        self, sample_json_config: Path
    ) -> None:
        """Test data_query successfully queries JSON file.

        Tests: JSON querying functionality
        How: Query .name from sample JSON config
        Why: Verify basic query operation works
        """
        # Arrange - sample JSON config
        # Act - query name field
        result = data_query_fn(str(sample_json_config), ".name")

        # Assert - returns correct data
        assert result["success"] is True
        assert result["result"] == "test-app"
        assert result["format"] == "json"
        assert result["file"] == str(sample_json_config)

    @pytest.mark.integration
    def test_data_query_when_nested_field_then_returns_value(
        self, sample_json_config: Path
    ) -> None:
        """Test data_query queries nested field.

        Tests: Nested field access
        How: Query .database.host from config
        Why: Verify nested object traversal works
        """
        # Arrange - sample config with nested data
        # Act - query nested field
        result = data_query_fn(str(sample_json_config), ".database.host")

        # Assert - returns nested value
        assert result["success"] is True
        assert result["result"] == "localhost"

    @pytest.mark.integration
    def test_data_query_when_array_index_then_returns_element(
        self, sample_json_config: Path
    ) -> None:
        """Test data_query queries array element.

        Tests: Array indexing
        How: Query .servers[0] from config
        Why: Verify array access works
        """
        # Arrange - config with array
        # Act - query first array element
        result = data_query_fn(str(sample_json_config), ".servers[0]")

        # Assert - returns array element
        assert result["success"] is True
        assert result["result"] == "server1.example.com"

    @pytest.mark.integration
    def test_data_query_when_yaml_with_json_output_then_converts(
        self, sample_yaml_config: Path
    ) -> None:
        """Test data_query converts YAML to JSON output.

        Tests: Format conversion in query
        How: Query YAML file with JSON output format
        Why: Verify output format conversion
        """
        # Arrange - YAML config
        # Act - query with JSON output
        result = data_query_fn(str(sample_yaml_config), ".name", output_format="json")

        # Assert - returns JSON data
        assert result["success"] is True
        assert result["result"] == "test-app"
        assert result["format"] == "json"

    @pytest.mark.integration
    def test_data_query_when_file_missing_then_raises_tool_error(self) -> None:
        """Test data_query raises error for missing file.

        Tests: Missing file handling
        How: Query non-existent file
        Why: Verify error handling for missing files
        """
        # Arrange - non-existent file path
        # Act & Assert - raises ToolError
        with pytest.raises(ToolError, match="File not found"):
            data_query_fn("/nonexistent/file.json", ".name")

    @pytest.mark.integration
    def test_data_query_when_invalid_expression_then_raises_tool_error(
        self, sample_json_config: Path
    ) -> None:
        """Test data_query raises error for invalid yq expression.

        Tests: Invalid expression handling
        How: Use malformed yq expression
        Why: Verify error handling for bad queries
        """
        # Arrange - sample config
        # Act & Assert - raises ToolError
        with pytest.raises(ToolError, match="Query failed"):
            data_query_fn(str(sample_json_config), ".bad[")

    def test_data_query_when_format_disabled_then_raises_tool_error(
        self, sample_json_config: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test data_query raises error for disabled format.

        Tests: Format filtering enforcement
        How: Disable JSON format and try to query JSON file
        Why: Verify format restrictions are enforced
        """
        # Arrange - disable JSON format
        monkeypatch.setenv("MCP_CONFIG_FORMATS", "yaml,toml")

        # Act & Assert - raises ToolError
        with pytest.raises(ToolError, match="Format 'json' is not enabled"):
            data_query_fn(str(sample_json_config), ".name")


class TestData:
    """Test unified data tool (get, set, delete)."""

    # --- GET Operations ---

    @pytest.mark.integration
    def test_data_get_when_simple_key_then_returns_value(
        self, sample_json_config: Path
    ) -> None:
        """Test data get retrieves simple key.

        Tests: Simple key retrieval
        How: Get 'name' key from config
        Why: Verify basic get operation
        """
        # Arrange - sample config
        # Act - get name key
        result = data_fn(str(sample_json_config), operation="get", key_path="name")

        # Assert - returns value
        assert result["success"] is True
        assert result["result"] == "test-app"

    @pytest.mark.integration
    def test_data_get_when_nested_key_then_returns_value(
        self, sample_json_config: Path
    ) -> None:
        """Test data get retrieves nested key.

        Tests: Nested key access
        How: Get 'database.port' from config
        Why: Verify dot-notation path traversal
        """
        # Arrange - config with nested structure
        # Act - get nested key
        result = data_fn(
            str(sample_json_config), operation="get", key_path="database.port"
        )

        # Assert - returns nested value
        assert result["success"] is True
        assert result["result"] == 5432

    @pytest.mark.integration
    def test_data_get_when_array_index_then_returns_element(
        self, sample_json_config: Path
    ) -> None:
        """Test data get retrieves array element.

        Tests: Array indexing via get
        How: Get 'servers[1]' from config
        Why: Verify array access in get
        """
        # Arrange - config with array
        # Act - get array element
        result = data_fn(
            str(sample_json_config), operation="get", key_path="servers[1]"
        )

        # Assert - returns element
        assert result["success"] is True
        assert result["result"] == "server2.example.com"

    @pytest.mark.integration
    def test_data_get_when_return_type_keys_then_returns_structure(
        self, sample_json_config: Path
    ) -> None:
        """Test data get retrieves structure (keys only).

        Tests: Structure retrieval
        How: Get structure of 'database'
        Why: Verify structure summary
        """
        # Arrange - sample config
        # Act - get structure
        result = data_fn(
            str(sample_json_config),
            operation="get",
            return_type="keys",
            key_path="database",
        )

        # Assert - returns structure summary
        assert result["success"] is True
        assert "host" in result["result"]
        assert "port" in result["result"]

    @pytest.mark.integration
    def test_data_get_when_data_type_schema_then_returns_schema(
        self, sample_json_config: Path, sample_json_schema: Path, tmp_path: Path
    ) -> None:
        """Test data get retrieves schema.

        Tests: Schema retrieval
        How: Get schema for file
        Why: Verify schema lookup
        """
        # Arrange - config with schema
        file_path = tmp_path / "app.json"
        schema_path = tmp_path / "app.schema.json"
        file_path.write_text(sample_json_config.read_text(encoding="utf-8"))
        schema_path.write_text(sample_json_schema.read_text(encoding="utf-8"))

        # Manual registration required now that implicit adjacency is removed
        from mcp_json_yaml_toml import server
        from mcp_json_yaml_toml.schemas import FileAssociation

        # Force a fresh config with our association
        server.schema_manager.config.file_associations[str(file_path.resolve())] = (
            FileAssociation(schema_url=str(schema_path.resolve()), source="user")
        )

        # Mock _fetch_schema to handle our local path "URL"
        original_fetch = server.schema_manager._fetch_schema

        def mock_fetch(url: str) -> dict[str, Any] | None:
            if url == str(schema_path.resolve()):
                return cast("dict[str, Any]", json.loads(schema_path.read_text()))
            return original_fetch(url)

        with unittest.mock.patch.object(
            server.schema_manager, "_fetch_schema", side_effect=mock_fetch
        ):
            # Act - get schema
            result = data_fn(str(file_path), operation="get", data_type="schema")

        # Assert - returns schema
        assert result["success"] is True
        assert result["schema"]["type"] == "object"

    # --- SET Operations ---

    @pytest.mark.integration
    def test_data_set_when_simple_value_then_updates_file(
        self, sample_json_config: Path, tmp_path: Path
    ) -> None:
        """Test data set modifies value.

        Tests: Set operation
        How: Set value on temp copy
        Why: Verify set operation writes to file
        """
        # Arrange - create temp copy
        temp_config = tmp_path / "test_config.json"
        temp_config.write_text(sample_json_config.read_text(encoding="utf-8"))

        # Act - set value
        result = data_fn(
            str(temp_config), operation="set", key_path="name", value='"new-name"'
        )

        # Assert - file modified
        assert result["success"] is True
        assert result["result"] == "File modified successfully"

        # Verify file was modified
        modified_data = json.loads(temp_config.read_text())
        assert modified_data["name"] == "new-name"

    @pytest.mark.integration
    def test_data_set_when_nested_value_then_updates_file(
        self, sample_json_config: Path, tmp_path: Path
    ) -> None:
        """Test data set modifies nested value.

        Tests: Nested value modification
        How: Set database.port to new value
        Why: Verify nested modification works
        """
        # Arrange - create temp copy
        temp_config = tmp_path / "test_config.json"
        temp_config.write_text(sample_json_config.read_text(encoding="utf-8"))

        # Act - set nested value
        result = data_fn(
            str(temp_config), operation="set", key_path="database.port", value="3306"
        )

        # Assert - file modified
        assert result["success"] is True
        assert result["result"] == "File modified successfully"

        # Verify file was modified
        modified_data = json.loads(temp_config.read_text())
        assert modified_data["database"]["port"] == 3306

    @pytest.mark.integration
    def test_data_set_when_in_place_then_modifies_file(
        self, sample_json_config: Path, tmp_path: Path
    ) -> None:
        """Test data set modifies file in place.

        Tests: In-place file modification
        How: Create temp copy and set with in_place=True
        Why: Verify in-place modification works
        """
        # Arrange - create temp copy
        temp_config = tmp_path / "temp_config.json"
        temp_config.write_text(sample_json_config.read_text(encoding="utf-8"))

        # Act - set value in place
        result = data_fn(
            str(temp_config), operation="set", key_path="name", value='"modified"'
        )

        # Assert - file modified
        assert result["success"] is True
        assert result["result"] == "File modified successfully"
        modified_data = json.loads(temp_config.read_text())
        assert modified_data["name"] == "modified"

    # --- DELETE Operations ---

    @pytest.mark.integration
    def test_data_delete_when_simple_key_then_removes_key(
        self, sample_json_config: Path, tmp_path: Path
    ) -> None:
        """Test data delete removes simple key.

        Tests: Simple key deletion
        How: Delete 'version' key
        Why: Verify basic delete operation
        """
        # Arrange - create temp copy
        temp_config = tmp_path / "test_config.json"
        temp_config.write_text(sample_json_config.read_text(encoding="utf-8"))

        # Act - delete key
        result = data_fn(str(temp_config), operation="delete", key_path="version")

        # Assert - file modified
        assert result["success"] is True
        assert result["result"] == "File modified successfully"

        # Verify file was modified
        modified_data = json.loads(temp_config.read_text())
        assert "version" not in modified_data
        assert "name" in modified_data  # Other keys preserved

    @pytest.mark.integration
    def test_data_delete_when_in_place_then_modifies_file(
        self, sample_json_config: Path, tmp_path: Path
    ) -> None:
        """Test data delete modifies file in place.

        Tests: In-place deletion
        How: Create temp copy and delete with in_place=True
        Why: Verify in-place deletion works
        """
        # Arrange - create temp copy
        temp_config = tmp_path / "temp_config.json"
        temp_config.write_text(sample_json_config.read_text(encoding="utf-8"))

        # Act - delete in place
        result = data_fn(str(temp_config), operation="delete", key_path="version")

        # Assert - file modified
        assert result["success"] is True
        assert result["result"] == "File modified successfully"
        modified_data = json.loads(temp_config.read_text())
        assert "version" not in modified_data

    # --- TOML Nested Structure Output Tests ---
    # Note: yq v4.52.2+ supports nested TOML output (earlier versions had scalar-only limitation)

    @pytest.mark.integration
    def test_data_get_when_toml_nested_then_succeeds(
        self, sample_toml_config: Path
    ) -> None:
        """Test data get succeeds with nested TOML structures.

        Tests: yq v4.52.2+ can output nested TOML structures
        How: Get nested object from TOML without specifying output_format
        Why: Verify yq's improved TOML output support works correctly
        """
        # Arrange - TOML file with nested structure
        # Act - get nested object without specifying output format (defaults to TOML)
        result = data_fn(str(sample_toml_config), operation="get", key_path="database")

        # Assert - TOML output succeeds with nested structures (yq v4.52.2+ improvement)
        assert result["success"] is True
        assert result["format"] == FormatType.TOML
        assert isinstance(result["result"], str)  # TOML output is serialized as string
        assert "host" in result["result"]
        assert "localhost" in result["result"]

    @pytest.mark.integration
    def test_data_get_when_toml_explicit_format_then_succeeds(
        self, sample_toml_config: Path
    ) -> None:
        """Test data get succeeds when TOML output explicitly requested for nested data.

        Tests: yq v4.52.2+ can output nested TOML structures
        How: Get nested object from TOML with explicit output_format='toml'
        Why: Verify explicit TOML requests work for nested data
        """
        # Arrange - TOML file with nested structure
        # Act - explicitly request TOML output for nested data
        result = data_fn(
            str(sample_toml_config),
            operation="get",
            key_path="database",
            output_format="toml",
        )

        # Assert - TOML output succeeds with nested structures (yq v4.52.2+ improvement)
        assert result["success"] is True
        assert result["format"] == FormatType.TOML
        assert isinstance(result["result"], str)  # TOML output is serialized as string
        assert "host" in result["result"]
        assert "localhost" in result["result"]

    @pytest.mark.integration
    def test_data_query_when_toml_nested_then_succeeds(
        self, sample_toml_config: Path
    ) -> None:
        """Test data_query succeeds with nested TOML structures.

        Tests: yq v4.52.2+ can output nested TOML structures
        How: Query nested object from TOML without specifying output_format
        Why: Verify data_query benefits from yq's improved TOML output support
        """
        # Arrange - TOML file with nested structure
        # Act - query nested object without specifying output format
        result = data_query_fn(str(sample_toml_config), ".database")

        # Assert - TOML output succeeds with nested structures (yq v4.52.2+ improvement)
        assert result["success"] is True
        assert result["format"] == FormatType.TOML
        assert isinstance(result["result"], str)  # TOML output is serialized as string
        assert "host" in result["result"]
        assert "localhost" in result["result"]

    @pytest.mark.integration
    def test_data_query_when_toml_explicit_format_then_succeeds(
        self, sample_toml_config: Path
    ) -> None:
        """Test data_query succeeds when TOML output explicitly requested.

        Tests: yq v4.52.2+ can output nested TOML structures
        How: Query nested object with explicit output_format='toml'
        Why: Verify data_query can handle explicit TOML requests for nested data
        """
        # Arrange - TOML file with nested structure
        # Act - explicitly request TOML output
        result = data_query_fn(
            str(sample_toml_config), ".database", output_format="toml"
        )

        # Assert - TOML output succeeds with nested structures (yq v4.52.2+ improvement)
        assert result["success"] is True
        assert result["format"] == FormatType.TOML
        assert isinstance(result["result"], str)  # TOML output is serialized as string
        assert "host" in result["result"]
        assert "localhost" in result["result"]

    @pytest.mark.integration
    def test_data_get_when_toml_scalar_then_no_fallback(
        self, sample_toml_config: Path
    ) -> None:
        """Test data get returns TOML for scalar values (no fallback needed).

        Tests: TOML output works for scalar values without fallback
        How: Get scalar value from TOML without specifying output_format
        Why: Verify fallback only occurs for nested structures, not scalars
        """
        # Arrange - TOML file
        # Act - get scalar value (defaults to TOML output)
        result = data_fn(str(sample_toml_config), operation="get", key_path="name")

        # Assert - TOML output works for scalars (no fallback)
        assert result["success"] is True
        # For scalar strings, TOML output includes newline, strip for comparison
        assert result["result"].strip() == "test-app"


class TestDataSchema:
    """Test unified data_schema tool."""

    @pytest.mark.integration
    def test_data_schema_when_valid_syntax_then_passes(
        self, sample_json_config: Path
    ) -> None:
        """Test data_schema validate passes for valid file.

        Tests: Valid file validation
        How: Validate syntactically correct JSON
        Why: Verify validation succeeds for valid files
        """
        # Arrange - valid JSON config
        # Act - validate
        result = data_schema_fn(action="validate", file_path=str(sample_json_config))

        # Assert - validation passes
        assert result["syntax_valid"] is True
        assert result["overall_valid"] is True
        assert "Syntax is valid" in result["syntax_message"]

    @pytest.mark.integration
    def test_data_schema_when_invalid_syntax_then_fails(
        self, invalid_json_config: Path
    ) -> None:
        """Test data_schema validate fails for invalid syntax.

        Tests: Invalid syntax detection
        How: Validate malformed JSON
        Why: Verify syntax errors are caught
        """
        # Arrange - invalid JSON
        # Act - validate
        result = data_schema_fn(action="validate", file_path=str(invalid_json_config))

        # Assert - validation fails
        assert result["syntax_valid"] is False
        assert result["overall_valid"] is False
        assert "Syntax error" in result["syntax_message"]

    @pytest.mark.integration
    def test_data_schema_when_valid_against_schema_then_passes(
        self, sample_json_config: Path, sample_json_schema: Path
    ) -> None:
        """Test data_schema validate with matching schema.

        Tests: Schema validation success
        How: Validate config against matching schema
        Why: Verify schema validation works
        """
        # Arrange - valid config and matching schema
        # Act - validate with schema
        result = data_schema_fn(
            action="validate",
            file_path=str(sample_json_config),
            schema_path=str(sample_json_schema),
        )

        # Assert - passes schema validation
        assert result["syntax_valid"] is True
        assert result["schema_validated"] is True
        assert result["overall_valid"] is True
        assert "Schema validation passed" in result["schema_message"]

    @pytest.mark.integration
    def test_data_schema_when_scan_then_finds_schemas(self, tmp_path: Path) -> None:
        """Test data_schema scan finds schemas.

        Tests: Schema scanning
        How: Scan directory with schemas
        Why: Verify scanning works
        """
        # Arrange - create schema file
        schema_path = tmp_path / "test.schema.json"
        schema_path.write_text("{}")

        # Act - scan
        result = data_schema_fn(action="scan", search_paths=[str(tmp_path)])

        # Assert - finds schema dir
        assert result["success"] is True
        assert result["discovered_count"] > 0
        assert str(tmp_path) in result["discovered_dirs"]

    @pytest.mark.integration
    def test_data_schema_when_add_dir_then_registers(self, tmp_path: Path) -> None:
        """Test data_schema add_dir adds directory.

        Tests: Add schema directory
        How: Add custom directory
        Why: Verify directory registration
        """
        # Arrange - directory
        # Act - add dir
        result = data_schema_fn(action="add_dir", path=str(tmp_path))

        # Assert - added
        assert result["success"] is True
        assert result["directory"] == str(tmp_path)

    @pytest.mark.integration
    def test_data_schema_when_add_catalog_then_registers(self) -> None:
        """Test data_schema add_catalog adds catalog.

        Tests: Add schema catalog
        How: Add custom catalog
        Why: Verify catalog registration
        """
        # Arrange
        # Act - add catalog
        result = data_schema_fn(
            action="add_catalog", name="test", uri="http://example.com/catalog.json"
        )

        # Assert - added
        assert result["success"] is True
        assert result["name"] == "test"

    @pytest.mark.integration
    def test_data_schema_when_list_then_returns_config(self) -> None:
        """Test data_schema list shows config.

        Tests: List configuration
        How: List schemas
        Why: Verify list operation
        """
        # Arrange
        # Act - list
        result = data_schema_fn(action="list")

        # Assert - returns config
        assert result["success"] is True
        assert "config" in result


class TestDataConvert:
    """Test data_convert tool."""

    @pytest.mark.integration
    def test_data_convert_when_json_to_yaml_then_converts(
        self, sample_json_config: Path
    ) -> None:
        """Test data_convert converts JSON to YAML.

        Tests: JSON to YAML conversion
        How: Convert JSON file to YAML format
        Why: Verify basic format conversion
        """
        # Arrange - JSON config
        # Act - convert to YAML
        result = data_convert_fn(str(sample_json_config), "yaml")

        # Assert - conversion successful
        assert result["success"] is True
        assert result["input_format"] == "json"
        assert result["output_format"] == "yaml"
        assert "name: test-app" in result["result"]

    @pytest.mark.integration
    def test_data_convert_when_yaml_to_json_then_converts(
        self, sample_yaml_config: Path
    ) -> None:
        """Test data_convert converts YAML to JSON.

        Tests: YAML to JSON conversion
        How: Convert YAML file to JSON format
        Why: Verify reverse conversion
        """
        # Arrange - YAML config
        # Act - convert to JSON
        result = data_convert_fn(str(sample_yaml_config), "json")

        # Assert - conversion successful
        assert result["success"] is True
        assert result["input_format"] == "yaml"
        assert result["output_format"] == "json"
        # Parse to verify valid JSON
        converted_data = json.loads(result["result"])
        assert converted_data["name"] == "test-app"

    @pytest.mark.integration
    def test_data_convert_when_json_to_toml_then_raises_error(
        self, sample_json_config: Path
    ) -> None:
        """Test data_convert rejects JSON to TOML conversion.

        Tests: JSON to TOML conversion rejection
        How: Attempt conversion and verify error
        Why: yq cannot encode complex nested structures to TOML format
        """
        # Arrange - JSON config
        # Act & Assert - conversion rejected with clear message
        with pytest.raises(ToolError) as exc_info:
            data_convert_fn(str(sample_json_config), "toml")

        error_message = str(exc_info.value)
        assert "not supported" in error_message.lower()
        assert "TOML" in error_message

    @pytest.mark.integration
    def test_data_convert_when_output_file_then_writes(
        self, sample_json_config: Path, tmp_path: Path
    ) -> None:
        """Test data_convert writes to output file.

        Tests: File output for conversion
        How: Convert and write to specified file
        Why: Verify file writing capability
        """
        # Arrange - JSON config and output path
        output_file = tmp_path / "output.yaml"

        # Act - convert with output file
        result = data_convert_fn(
            str(sample_json_config), "yaml", output_file=str(output_file)
        )

        # Assert - file written
        assert result["success"] is True
        assert result["output_file"] == str(output_file)
        assert output_file.exists()
        content = output_file.read_text()
        assert "name: test-app" in content

    @pytest.mark.integration
    def test_data_convert_when_same_format_then_raises_error(
        self, sample_json_config: Path
    ) -> None:
        """Test data_convert rejects same input/output format.

        Tests: Format validation
        How: Try to convert JSON to JSON
        Why: Ensure meaningless conversions are rejected
        """
        # Arrange - JSON config
        # Act & Assert - raises ToolError
        with pytest.raises(ToolError, match="Input and output formats are the same"):
            data_convert_fn(str(sample_json_config), "json")

    @pytest.mark.integration
    def test_data_convert_when_file_missing_then_raises_error(self) -> None:
        """Test data_convert raises error for missing file.

        Tests: Missing file error handling
        How: Convert non-existent file
        Why: Verify error handling
        """
        # Arrange - non-existent file
        # Act & Assert - raises ToolError
        with pytest.raises(ToolError, match="File not found"):
            data_convert_fn("/nonexistent/file.json", "yaml")


class TestDataMerge:
    """Test data_merge tool."""

    @pytest.mark.integration
    def test_data_merge_when_two_json_files_then_merges(
        self, sample_json_config: Path, tmp_path: Path
    ) -> None:
        """Test data_merge merges two JSON files.

        Tests: Basic merge operation
        How: Create two JSON files and merge them
        Why: Verify merge functionality works
        """
        # Arrange - two JSON configs
        file1 = tmp_path / "config1.json"
        file2 = tmp_path / "config2.json"
        file1.write_text(json.dumps({"name": "app1", "version": "1.0"}))
        file2.write_text(json.dumps({"version": "2.0", "author": "test"}))

        # Act - merge files
        result = data_merge_fn(str(file1), str(file2), output_format="json")

        # Assert - merged correctly
        assert result["success"] is True
        merged_data = json.loads(result["result"])
        assert merged_data["name"] == "app1"  # From file1
        assert merged_data["version"] == "2.0"  # Overridden by file2
        assert merged_data["author"] == "test"  # Added from file2

    @pytest.mark.integration
    def test_data_merge_when_nested_objects_then_deep_merges(
        self, tmp_path: Path
    ) -> None:
        """Test data_merge performs deep merge.

        Tests: Deep merge strategy
        How: Merge nested objects
        Why: Verify nested merging works correctly
        """
        # Arrange - configs with nested objects
        file1 = tmp_path / "config1.json"
        file2 = tmp_path / "config2.json"
        file1.write_text(json.dumps({"database": {"host": "localhost", "port": 5432}}))
        file2.write_text(json.dumps({"database": {"port": 3306, "user": "admin"}}))

        # Act - merge
        result = data_merge_fn(str(file1), str(file2), output_format="json")

        # Assert - deep merged
        merged_data = json.loads(result["result"])
        assert merged_data["database"]["host"] == "localhost"  # Preserved
        assert merged_data["database"]["port"] == 3306  # Overridden
        assert merged_data["database"]["user"] == "admin"  # Added

    @pytest.mark.integration
    def test_data_merge_when_different_formats_then_merges(
        self, sample_json_config: Path, sample_yaml_config: Path
    ) -> None:
        """Test data_merge merges different formats.

        Tests: Cross-format merging
        How: Merge JSON and YAML files
        Why: Verify format-agnostic merging
        """
        # Arrange - JSON and YAML configs
        # Act - merge different formats
        result = data_merge_fn(
            str(sample_json_config), str(sample_yaml_config), output_format="json"
        )

        # Assert - merged successfully
        assert result["success"] is True
        merged_data = json.loads(result["result"])
        assert "name" in merged_data
        assert "database" in merged_data

    @pytest.mark.integration
    def test_data_merge_when_output_file_then_writes(self, tmp_path: Path) -> None:
        """Test data_merge writes to output file.

        Tests: File output for merge
        How: Merge and write to specified file
        Why: Verify file writing capability
        """
        # Arrange - two configs and output path
        file1 = tmp_path / "config1.json"
        file2 = tmp_path / "config2.json"
        output_file = tmp_path / "merged.json"
        file1.write_text(json.dumps({"key1": "value1"}))
        file2.write_text(json.dumps({"key2": "value2"}))

        # Act - merge with output file
        result = data_merge_fn(str(file1), str(file2), output_file=str(output_file))

        # Assert - file written
        assert result["success"] is True
        assert result["output_file"] == str(output_file)
        assert output_file.exists()
        merged_data = json.loads(output_file.read_text())
        assert "key1" in merged_data
        assert "key2" in merged_data

    @pytest.mark.integration
    def test_data_merge_when_file_missing_then_raises_error(
        self, sample_json_config: Path
    ) -> None:
        """Test data_merge raises error if first file missing.

        Tests: First file validation
        How: Merge with non-existent first file
        Why: Verify error handling
        """
        # Arrange - non-existent first file
        # Act & Assert - raises ToolError
        with pytest.raises(ToolError, match="File not found"):
            data_merge_fn("/nonexistent/file.json", str(sample_json_config))


class TestPrompts:
    """Test prompt templates."""

    def test_explain_config_when_called_then_returns_prompt(self) -> None:
        """Test explain_config prompt generation.

        Note: FastMCP 3.x decorators return the original function directly,
        so we call the function without .fn accessor.
        We use cast() to assert the known runtime type.
        """

        explain_fn = cast("Callable[..., Any]", server.explain_config)
        prompt = cast("str", explain_fn("config.json"))
        assert "analyze and explain" in prompt
        assert "config.json" in prompt

    def test_suggest_improvements_when_called_then_returns_prompt(self) -> None:
        """Test suggest_improvements prompt generation.

        Note: See test_explain_config docstring for type cast explanation.
        """

        suggest_fn = cast("Callable[..., Any]", server.suggest_improvements)
        prompt = cast("str", suggest_fn("config.yaml"))
        assert "suggest improvements" in prompt
        assert "config.yaml" in prompt

    def test_convert_to_schema_when_called_then_returns_prompt(self) -> None:
        """Test convert_to_schema prompt generation.

        Note: See test_explain_config docstring for type cast explanation.
        """

        convert_fn = cast("Callable[..., Any]", server.convert_to_schema)
        prompt = cast("str", convert_fn("data.toml"))
        assert "generate a JSON schema" in prompt
        assert "data.toml" in prompt


# FastMCP 3.x: decorators return the original function directly (no .fn needed).
constraint_validate_fn = cast("Callable[..., Any]", server.constraint_validate)
constraint_list_fn = cast("Callable[..., Any]", server.constraint_list)


class TestConstraintTools:
    """Test LMQL constraint validation tools."""

    def test_constraint_validate_when_valid_yq_path_then_returns_valid(self) -> None:
        """
        Verify that the YQ_PATH constraint accepts a valid yq-style path.

        Asserts that validating the string ".name" with the "YQ_PATH" constraint yields a result marked valid, includes the constraint name and the original value, and does not contain an error entry.
        """
        result = constraint_validate_fn("YQ_PATH", ".name")

        assert result["valid"] is True
        assert result["constraint"] == "YQ_PATH"
        assert result["value"] == ".name"
        assert "error" not in result

    def test_constraint_validate_when_invalid_yq_path_then_returns_invalid(
        self,
    ) -> None:
        """Test constraint_validate with invalid YQ_PATH.

        Tests: Invalid constraint validation
        How: Validate 'users' (missing dot) against YQ_PATH
        Why: Verify invalid inputs are rejected with suggestions
        """
        result = constraint_validate_fn("YQ_PATH", "users")

        assert result["valid"] is False
        assert result["constraint"] == "YQ_PATH"
        assert "error" in result
        assert ".users" in result.get("suggestions", [])

    def test_constraint_validate_when_partial_input_then_returns_partial(self) -> None:
        """Test constraint_validate with partial input.

        Tests: Partial input detection
        How: Validate just '.' which is incomplete YQ_PATH
        Why: Verify partial inputs are identified for streaming
        """
        result = constraint_validate_fn("YQ_PATH", ".")

        assert result["valid"] is False
        assert result["is_partial"] is True
        assert "remaining_pattern" in result

    def test_constraint_validate_when_config_format_then_validates(self) -> None:
        """
        Verify CONFIG_FORMAT enum constraint accepts allowed formats and rejects invalid ones.

        Asserts that "json" and "yaml" validate successfully and that "csv" is reported as invalid.
        """
        result = constraint_validate_fn("CONFIG_FORMAT", "json")
        assert result["valid"] is True

        result = constraint_validate_fn("CONFIG_FORMAT", "yaml")
        assert result["valid"] is True

        result = constraint_validate_fn("CONFIG_FORMAT", "csv")
        assert result["valid"] is False

    def test_constraint_validate_when_int_then_validates(self) -> None:
        """Test constraint_validate with INT constraint.

        Tests: Integer constraint validation
        How: Validate various integer strings
        Why: Verify numeric validation works
        """
        result = constraint_validate_fn("INT", "42")
        assert result["valid"] is True

        result = constraint_validate_fn("INT", "-123")
        assert result["valid"] is True

        result = constraint_validate_fn("INT", "3.14")
        assert result["valid"] is False

    def test_constraint_validate_when_json_value_then_validates(self) -> None:
        """Test constraint_validate with JSON_VALUE constraint.

        Tests: JSON value constraint validation
        How: Validate various JSON values
        Why: Verify JSON parsing validation works
        """
        result = constraint_validate_fn("JSON_VALUE", '"hello"')
        assert result["valid"] is True

        result = constraint_validate_fn("JSON_VALUE", '{"key": "value"}')
        assert result["valid"] is True

        result = constraint_validate_fn("JSON_VALUE", '{"incomplete":')
        assert result["valid"] is False
        assert result["is_partial"] is True

    def test_constraint_validate_when_unknown_then_returns_error(self) -> None:
        """Test constraint_validate with unknown constraint.

        Tests: Unknown constraint handling
        How: Use non-existent constraint name
        Why: Verify proper error for unknown constraints
        """
        result = constraint_validate_fn("UNKNOWN_CONSTRAINT", "value")

        assert result["valid"] is False
        assert "Unknown constraint" in result["error"]

    def test_constraint_list_when_called_then_returns_all(self) -> None:
        """Test constraint_list returns all registered constraints.

        Tests: Constraint listing
        How: Call constraint_list and check contents
        Why: Verify all constraints are discoverable
        """
        result = constraint_list_fn()

        assert "constraints" in result
        assert "usage" in result

        constraint_names = [c["name"] for c in result["constraints"]]
        assert "YQ_PATH" in constraint_names
        assert "YQ_EXPRESSION" in constraint_names
        assert "CONFIG_FORMAT" in constraint_names
        assert "INT" in constraint_names
        assert "KEY_PATH" in constraint_names
        assert "JSON_VALUE" in constraint_names
        assert "FILE_PATH" in constraint_names

    def test_constraint_list_when_called_then_includes_descriptions(self) -> None:
        """Test constraint_list includes constraint descriptions.

        Tests: Constraint metadata
        How: Check that constraints have descriptions
        Why: Verify constraints are self-documenting
        """
        result = constraint_list_fn()

        for constraint in result["constraints"]:
            assert "name" in constraint
            assert "description" in constraint


class TestConstraintResources:
    """Test LMQL constraint MCP resources.

    Note: These tests verify the underlying ConstraintRegistry functions
    that power the MCP resources. The actual MCP resource decorators
    wrap these functions for client access.
    """

    def test_constraint_registry_when_get_all_then_returns_definitions(self) -> None:
        """
        Verify that the constraint registry exposes all expected constraint definitions.

        Asserts that the registry contains definitions for YQ_PATH, CONFIG_FORMAT, INT, KEY_PATH, JSON_VALUE, and FILE_PATH.
        """
        definitions = ConstraintRegistry.get_all_definitions()

        assert "YQ_PATH" in definitions
        assert "CONFIG_FORMAT" in definitions
        assert "INT" in definitions
        assert "KEY_PATH" in definitions
        assert "JSON_VALUE" in definitions
        assert "FILE_PATH" in definitions

    def test_constraint_definition_when_yq_path_then_returns_complete(self) -> None:
        """
        Verify that the YQ_PATH constraint resource exposes a complete definition.

        Asserts the returned definition has name "YQ_PATH" and includes the keys "description", "pattern", and "examples".
        """
        from mcp_json_yaml_toml.lmql_constraints import YQPathConstraint

        result = YQPathConstraint.get_definition()

        assert result["name"] == "YQ_PATH"
        assert "description" in result
        assert "pattern" in result
        assert "examples" in result

    def test_constraint_definition_when_config_format_then_returns_allowed_values(
        self,
    ) -> None:
        """
        Verify that the CONFIG_FORMAT constraint definition exposes the expected allowed formats.

        Asserts the definition name equals "CONFIG_FORMAT" and that the `allowed_values` list includes "json", "yaml", and "toml".
        """
        from mcp_json_yaml_toml.lmql_constraints import ConfigFormatConstraint

        result = ConfigFormatConstraint.get_definition()

        assert result["name"] == "CONFIG_FORMAT"
        assert "allowed_values" in result
        allowed = result["allowed_values"]
        assert isinstance(allowed, list)
        assert "json" in allowed
        assert "yaml" in allowed
        assert "toml" in allowed

    def test_constraint_registry_when_unknown_then_returns_none(self) -> None:
        """Test unknown constraint returns None.

        Tests: Unknown constraint handling in resource
        How: Request non-existent constraint via registry
        Why: Verify proper handling for unknown constraints
        """
        result = ConstraintRegistry.get("NONEXISTENT")
        assert result is None


class TestEdgeCases:
    """Edge case tests for MCP tool error handling."""

    @pytest.mark.skipif(
        __import__("os").getuid() == 0, reason="root bypasses permissions"
    )
    def test_data_query_when_file_not_readable_then_raises_error(
        self, tmp_path: Path
    ) -> None:
        """Test data_query raises error for unreadable files.

        Tests: Permission error handling
        How: Create JSON file with 0o000 permissions, attempt query
        Why: Verify graceful handling of OS-level permission errors
        """
        # Arrange - create unreadable file
        test_file = tmp_path / "unreadable.json"
        test_file.write_text('{"key": "value"}')
        test_file.chmod(0o000)

        try:
            # Act & Assert - should raise error
            with pytest.raises(ToolError):
                data_query_fn(str(test_file), ".")
        finally:
            # Cleanup - restore permissions so tmp_path can be cleaned
            test_file.chmod(0o644)

    def test_data_query_when_binary_file_then_handles_gracefully(
        self, tmp_path: Path
    ) -> None:
        """Test data_query handles binary content without crashing.

        Tests: Binary/malformed input handling
        How: Create file with random binary bytes, give .json extension
        Why: Verify server doesn't crash on non-text content
        """
        # Arrange - create binary file with .json extension
        binary_file = tmp_path / "binary.json"
        binary_file.write_bytes(bytes(range(256)))

        # Act - yq may return null result or raise error; either is acceptable
        try:
            result = data_query_fn(str(binary_file), ".")
            # Assert - result exists but may have null data
            assert result is not None
        except ToolError:
            # ToolError is also acceptable for invalid binary input
            pass

    def test_data_query_when_json_with_bom_then_handles_gracefully(
        self, tmp_path: Path
    ) -> None:
        """Test data_query handles UTF-8 BOM gracefully.

        Tests: BOM marker handling
        How: Create JSON file with UTF-8 BOM prefix
        Why: Verify server handles BOM without crashing
        """
        # Arrange - create JSON file with BOM
        bom_file = tmp_path / "bom.json"
        bom_file.write_bytes(b"\xef\xbb\xbf" + b'{"key": "value"}')

        # Act - either success or clear error is acceptable
        try:
            result = data_query_fn(str(bom_file), ".")
            # Assert - if successful, result should have data
            assert "result" in result
        except ToolError:
            # ToolError is acceptable -- BOM may cause parse failure
            pass

    def test_data_query_when_empty_file_then_handles_gracefully(
        self, tmp_path: Path
    ) -> None:
        """Test data_query handles empty files without crashing.

        Tests: Empty file handling
        How: Create 0-byte .json file, attempt query
        Why: Verify graceful handling of empty input
        """
        # Arrange - create empty file
        empty_file = tmp_path / "empty.json"
        empty_file.write_text("")

        # Act - yq treats empty file as null; either result or error is acceptable
        try:
            result = data_query_fn(str(empty_file), ".")
            # Assert - result exists but may have null data
            assert result is not None
        except ToolError:
            # ToolError is also acceptable for empty files
            pass


class TestDataMeta:
    """Test data_type='meta' server info path."""

    @pytest.mark.integration
    def test_data_when_meta_type_then_returns_server_info(self) -> None:
        """Test data returns server metadata for data_type='meta'.

        Tests: Meta data type returns server info
        How: Call data with data_type='meta' and verify response fields
        Why: Verify server introspection through unified data tool
        """
        # Arrange - no file needed for meta
        # Act - request server info
        result = data_fn(file_path="-", operation="get", data_type="meta")

        # Assert - returns complete server info
        assert result.success is True
        assert result.file == "-"
        assert isinstance(result.version, str)
        assert len(result.version) > 0
        assert result.uptime_seconds >= 0
        assert result.start_time_epoch > 0
        assert isinstance(result, ServerInfoResponse)

    @pytest.mark.integration
    def test_data_when_meta_type_then_no_file_resolution(self) -> None:
        """Test data_type='meta' bypasses file resolution.

        Tests: Short-circuit before resolve_file_path
        How: Patch resolve_file_path to raise, verify meta still succeeds
        Why: Verify no file I/O occurs for meta requests
        """
        # Arrange - patch resolve_file_path to fail
        with unittest.mock.patch(
            "mcp_json_yaml_toml.tools.data.resolve_file_path",
            side_effect=AssertionError("should not be called"),
        ):
            # Act - request meta (should short-circuit before resolve_file_path)
            result = data_fn(file_path="-", operation="get", data_type="meta")

        # Assert - succeeds without touching file resolution
        assert result.success is True
        assert isinstance(result, ServerInfoResponse)

    @pytest.mark.integration
    def test_data_when_meta_type_then_uptime_increases_over_time(self) -> None:
        """Test uptime_seconds increases between successive meta calls.

        Tests: Uptime reflects real elapsed time
        How: Call meta twice with a small sleep, compare uptime values
        Why: Verify uptime is computed dynamically, not cached
        """
        # Arrange - first call
        result1 = data_fn(file_path="-", operation="get", data_type="meta")

        # Act - wait briefly and call again
        time.sleep(0.05)
        result2 = data_fn(file_path="-", operation="get", data_type="meta")

        # Assert - uptime increased
        assert result2.uptime_seconds > result1.uptime_seconds

    @pytest.mark.integration
    def test_data_when_data_type_unchanged_then_still_works(
        self, sample_json_config: Path
    ) -> None:
        """Test existing data_type='data' operations are unaffected.

        Tests: Regression -- existing behavior preserved
        How: Call data with data_type='data' and return_type='keys'
        Why: Verify adding 'meta' didn't break existing code paths
        """
        # Arrange - sample JSON config
        # Act - use existing data_type='data' path
        result = data_fn(
            str(sample_json_config),
            operation="get",
            data_type="data",
            return_type="keys",
        )

        # Assert - existing behavior works
        assert result["success"] is True

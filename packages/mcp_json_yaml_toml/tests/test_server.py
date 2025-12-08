"""Tests for MCP server tools.

Comprehensive tests for all MCP tools: data_query, data, data_schema, data_convert, and data_merge.

Note: FastMCP decorates functions as FunctionTool objects. Access the underlying
function via .fn attribute (e.g., server.data_query.fn()).
"""

import json
from pathlib import Path

import pytest
from fastmcp.exceptions import ToolError

from mcp_json_yaml_toml import server
from mcp_json_yaml_toml.lmql_constraints import ConstraintRegistry

# Extract underlying functions from FastMCP FunctionTool wrappers
data_query_fn = server.data_query.fn
data_fn = server.data.fn
data_schema_fn = server.data_schema.fn
data_convert_fn = server.data_convert.fn
data_merge_fn = server.data_merge.fn


class TestDataQuery:
    """Test data_query tool."""

    @pytest.mark.integration
    def test_data_query_json_success(self, sample_json_config: Path) -> None:
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
    def test_data_query_nested_field(self, sample_json_config: Path) -> None:
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
    def test_data_query_array_element(self, sample_json_config: Path) -> None:
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
    def test_data_query_yaml_to_json(self, sample_yaml_config: Path) -> None:
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
    def test_data_query_file_not_found(self) -> None:
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
    def test_data_query_invalid_expression(self, sample_json_config: Path) -> None:
        """Test data_query raises error for invalid yq expression.

        Tests: Invalid expression handling
        How: Use malformed yq expression
        Why: Verify error handling for bad queries
        """
        # Arrange - sample config
        # Act & Assert - raises ToolError
        with pytest.raises(ToolError, match="Query failed"):
            data_query_fn(str(sample_json_config), ".bad[")

    def test_data_query_disabled_format(
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
    def test_data_get_simple_key(self, sample_json_config: Path) -> None:
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
    def test_data_get_nested_key(self, sample_json_config: Path) -> None:
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
    def test_data_get_array_index(self, sample_json_config: Path) -> None:
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
    def test_data_get_structure(self, sample_json_config: Path) -> None:
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
    def test_data_get_schema(
        self, sample_json_config: Path, sample_json_schema: Path, tmp_path: Path
    ) -> None:
        """Test data get retrieves schema.

        Tests: Schema retrieval
        How: Get schema for file
        Why: Verify schema lookup
        """
        # Arrange - config with schema
        config_path = tmp_path / "app.json"
        schema_path = tmp_path / "app.schema.json"
        config_path.write_text(sample_json_config.read_text(encoding="utf-8"))
        schema_path.write_text(sample_json_schema.read_text(encoding="utf-8"))

        # Act - get schema
        result = data_fn(str(config_path), operation="get", data_type="schema")

        # Assert - returns schema
        assert result["success"] is True
        assert result["schema"]["type"] == "object"

    # --- SET Operations ---

    @pytest.mark.integration
    def test_data_set_simple_value(
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
    def test_data_set_nested_value(
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
    def test_data_set_in_place(self, sample_json_config: Path, tmp_path: Path) -> None:
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
    def test_data_delete_simple_key(
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
    def test_data_delete_in_place(
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

    # --- TOML Output Format Auto-Fallback Tests ---

    @pytest.mark.integration
    def test_data_get_toml_nested_auto_fallback(self, sample_toml_config: Path) -> None:
        """Test data get auto-falls back to JSON for nested TOML data.

        Tests: Auto-fallback from TOML to JSON when yq can't encode nested structures
        How: Get nested object from TOML without specifying output_format
        Why: Verify automatic JSON fallback when TOML encoder fails with "only scalars"
        """
        # Arrange - TOML file with nested structure
        # Act - get nested object without specifying output format (defaults to TOML)
        result = data_fn(str(sample_toml_config), operation="get", key_path="database")

        # Assert - auto-fallback to JSON successful
        assert result["success"] is True
        assert result["format"] == "json"  # Fell back from toml to json
        assert isinstance(result["result"], dict)
        assert result["result"]["host"] == "localhost"
        assert result["result"]["port"] == 5432

    @pytest.mark.integration
    def test_data_get_toml_explicit_format_fails(
        self, sample_toml_config: Path
    ) -> None:
        """Test data get raises error when TOML output explicitly requested for nested data.

        Tests: Error when explicitly requesting TOML output for nested structures
        How: Get nested object from TOML with explicit output_format='toml'
        Why: Verify explicit TOML request shows proper error instead of silent fallback
        """
        # Arrange - TOML file with nested structure
        # Act - explicitly request TOML output for nested data
        # Assert - raises ToolError with yq message
        with pytest.raises(ToolError) as exc_info:
            data_fn(
                str(sample_toml_config),
                operation="get",
                key_path="database",
                output_format="toml",
            )

        # Verify error message mentions the yq limitation
        assert "Query failed" in str(exc_info.value)

    @pytest.mark.integration
    def test_data_query_toml_nested_auto_fallback(
        self, sample_toml_config: Path
    ) -> None:
        """Test data_query auto-falls back to JSON for nested TOML data.

        Tests: Auto-fallback in data_query tool for TOML nested structures
        How: Query nested object from TOML without specifying output_format
        Why: Verify data_query also implements auto-fallback behavior
        """
        # Arrange - TOML file with nested structure
        # Act - query nested object without specifying output format
        result = data_query_fn(str(sample_toml_config), ".database")

        # Assert - auto-fallback to JSON successful
        assert result["success"] is True
        assert result["format"] == "json"  # Fell back from toml to json
        assert isinstance(result["result"], dict)
        assert result["result"]["host"] == "localhost"
        assert result["result"]["port"] == 5432

    @pytest.mark.integration
    def test_data_query_toml_explicit_format_fails(
        self, sample_toml_config: Path
    ) -> None:
        """Test data_query raises error when TOML output explicitly requested.

        Tests: Error when explicitly requesting TOML output in data_query
        How: Query nested object with explicit output_format='toml'
        Why: Verify explicit TOML request shows proper error
        """
        # Arrange - TOML file with nested structure
        # Act & Assert - raises ToolError
        with pytest.raises(ToolError) as exc_info:
            data_query_fn(str(sample_toml_config), ".database", output_format="toml")

        # Verify error message
        assert "Query failed" in str(exc_info.value)

    @pytest.mark.integration
    def test_data_get_toml_scalar_no_fallback(self, sample_toml_config: Path) -> None:
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
    def test_data_schema_validate_valid_syntax(self, sample_json_config: Path) -> None:
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
    def test_data_schema_validate_invalid_syntax(
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
    def test_data_schema_validate_with_schema_success(
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
    def test_data_schema_scan(self, tmp_path: Path) -> None:
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
    def test_data_schema_add_dir(self, tmp_path: Path) -> None:
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
    def test_data_schema_add_catalog(self) -> None:
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
    def test_data_schema_list(self) -> None:
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
    def test_data_convert_json_to_yaml(self, sample_json_config: Path) -> None:
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
    def test_data_convert_yaml_to_json(self, sample_yaml_config: Path) -> None:
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
    def test_data_convert_json_to_toml_not_supported(
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
    def test_data_convert_with_output_file(
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
    def test_data_convert_same_format_error(self, sample_json_config: Path) -> None:
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
    def test_data_convert_file_not_found(self) -> None:
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
    def test_data_merge_two_json_files(
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
    def test_data_merge_deep_merge(self, tmp_path: Path) -> None:
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
    def test_data_merge_different_formats(
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
    def test_data_merge_with_output_file(self, tmp_path: Path) -> None:
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
    def test_data_merge_file1_not_found(self, sample_json_config: Path) -> None:
        """Test data_merge raises error if first file missing.

        Tests: First file validation
        How: Merge with non-existent first file
        Why: Verify error handling
        """
        # Arrange - non-existent first file
        # Act & Assert - raises ToolError
        with pytest.raises(ToolError, match="First file not found"):
            data_merge_fn("/nonexistent/file.json", str(sample_json_config))


class TestPrompts:
    """Test prompt templates."""

    def test_explain_config(self) -> None:
        """Test explain_config prompt generation.

        Note: FastMCP's FunctionPrompt.fn is typed as returning
        PromptResult | Awaitable[PromptResult], but for sync prompt functions
        that return str, it actually returns str at runtime.
        We use cast() to assert the known runtime type.
        """
        from typing import cast

        prompt = cast("str", server.explain_config.fn("config.json"))
        assert "analyze and explain" in prompt
        assert "config.json" in prompt

    def test_suggest_improvements(self) -> None:
        """Test suggest_improvements prompt generation.

        Note: See test_explain_config docstring for type cast explanation.
        """
        from typing import cast

        prompt = cast("str", server.suggest_improvements.fn("config.yaml"))
        assert "suggest improvements" in prompt
        assert "config.yaml" in prompt

    def test_convert_to_schema(self) -> None:
        """Test convert_to_schema prompt generation.

        Note: See test_explain_config docstring for type cast explanation.
        """
        from typing import cast

        prompt = cast("str", server.convert_to_schema.fn("data.toml"))
        assert "generate a JSON schema" in prompt
        assert "data.toml" in prompt


# Extract underlying functions for LMQL constraint tools
constraint_validate_fn = server.constraint_validate.fn
constraint_list_fn = server.constraint_list.fn


class TestConstraintTools:
    """Test LMQL constraint validation tools."""

    def test_constraint_validate_valid_yq_path(self) -> None:
        """
        Verify that the YQ_PATH constraint accepts a valid yq-style path.

        Asserts that validating the string ".name" with the "YQ_PATH" constraint yields a result marked valid, includes the constraint name and the original value, and does not contain an error entry.
        """
        result = constraint_validate_fn("YQ_PATH", ".name")

        assert result["valid"] is True
        assert result["constraint"] == "YQ_PATH"
        assert result["value"] == ".name"
        assert "error" not in result

    def test_constraint_validate_invalid_yq_path(self) -> None:
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

    def test_constraint_validate_partial_input(self) -> None:
        """Test constraint_validate with partial input.

        Tests: Partial input detection
        How: Validate just '.' which is incomplete YQ_PATH
        Why: Verify partial inputs are identified for streaming
        """
        result = constraint_validate_fn("YQ_PATH", ".")

        assert result["valid"] is False
        assert result["is_partial"] is True
        assert "remaining_pattern" in result

    def test_constraint_validate_config_format(self) -> None:
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

    def test_constraint_validate_int(self) -> None:
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

    def test_constraint_validate_json_value(self) -> None:
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

    def test_constraint_validate_unknown_constraint(self) -> None:
        """Test constraint_validate with unknown constraint.

        Tests: Unknown constraint handling
        How: Use non-existent constraint name
        Why: Verify proper error for unknown constraints
        """
        result = constraint_validate_fn("UNKNOWN_CONSTRAINT", "value")

        assert result["valid"] is False
        assert "Unknown constraint" in result["error"]

    def test_constraint_list_returns_all_constraints(self) -> None:
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

    def test_constraint_list_includes_descriptions(self) -> None:
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

    def test_list_all_constraints_resource(self) -> None:
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

    def test_get_constraint_definition_resource(self) -> None:
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

    def test_get_constraint_definition_config_format(self) -> None:
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

    def test_get_constraint_definition_unknown(self) -> None:
        """Test unknown constraint returns None.

        Tests: Unknown constraint handling in resource
        How: Request non-existent constraint via registry
        Why: Verify proper handling for unknown constraints
        """
        result = ConstraintRegistry.get("NONEXISTENT")
        assert result is None

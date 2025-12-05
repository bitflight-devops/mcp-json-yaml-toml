"""Tests for SET operation type preservation across JSON, YAML, and TOML files.

This module verifies that the `data` tool's SET operation correctly preserves
value types when writing to configuration files. The discovered bug causes
strings that look like numbers (e.g., "3.11") to be coerced to floats.

Tests: Type preservation in SET operations via actual MCP JSON-RPC protocol
How: Create fixtures with known types, call MCP tools via subprocess, verify types
Why: Direct function calls bypass protocol layer where type coercion occurs

Note: These tests are expected to FAIL initially as they document a known bug
where type coercion occurs during SET operations in the MCP protocol layer.

IMPORTANT: These tests use actual MCP JSON-RPC protocol via subprocess to expose
bugs that would not be caught by direct function calls.
"""

from __future__ import annotations

import json
import math
from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from pathlib import Path

    from mcp_json_yaml_toml.tests.mcp_protocol_client import MCPClient

# ==============================================================================
# Test Fixtures
# ==============================================================================


@pytest.fixture
def json_config_with_types(tmp_path: Path) -> Path:
    """Create JSON config file with various value types for testing.

    Returns:
        Path to created JSON config file with all testable types
    """
    config_data = {
        "string_value": "hello",
        "string_numeric": "3.11",
        "string_integer": "42",
        "string_bool": "true",
        "integer_value": 42,
        "float_value": math.pi,
        "float_whole": 3.0,
        "bool_true": True,
        "bool_false": False,
        "null_value": None,
        "array_strings": ["a", "b", "c"],
        "array_integers": [1, 2, 3],
        "object_value": {"nested": "value", "count": 10},
    }

    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(config_data, indent=2), encoding="utf-8")
    return config_path


@pytest.fixture
def yaml_config_with_types(tmp_path: Path) -> Path:
    """Create YAML config file with various value types for testing.

    Returns:
        Path to created YAML config file with all testable types
    """
    yaml_content = """string_value: "hello"
string_numeric: "3.11"
string_integer: "42"
string_bool: "true"
integer_value: 42
float_value: 3.14
float_whole: 3.0
bool_true: true
bool_false: false
null_value: null
array_strings:
  - "a"
  - "b"
  - "c"
array_integers:
  - 1
  - 2
  - 3
object_value:
  nested: "value"
  count: 10
"""

    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml_content, encoding="utf-8")
    return config_path


@pytest.fixture
def toml_config_with_types(tmp_path: Path) -> Path:
    """Create TOML config file with various value types for testing.

    Returns:
        Path to created TOML config file with all testable types
    """
    toml_content = """string_value = "hello"
string_numeric = "3.11"
string_integer = "42"
string_bool = "true"
integer_value = 42
float_value = 3.14
float_whole = 3.0
bool_true = true
bool_false = false
array_strings = ["a", "b", "c"]
array_integers = [1, 2, 3]

[object_value]
nested = "value"
count = 10
"""

    config_path = tmp_path / "config.toml"
    config_path.write_text(toml_content, encoding="utf-8")
    return config_path


# ==============================================================================
# Helper Functions for Protocol-Based Testing
# ==============================================================================


def get_value_via_protocol(
    mcp_client: MCPClient, file_path: Path, key_path: str
) -> Any:
    """Get a value from config file using the MCP protocol.

    Always requests JSON output format to get properly parsed Python types.

    Args:
        mcp_client: MCP client connected via JSON-RPC protocol
        file_path: Path to configuration file
        key_path: Dot-separated key path

    Returns:
        The value at the specified key path as a Python object
    """
    result = mcp_client.call_tool(
        "data",
        {
            "file_path": str(file_path),
            "operation": "get",
            "key_path": key_path,
            "output_format": "json",
        },
    )
    return result["result"]


def set_value_via_protocol(
    mcp_client: MCPClient, file_path: Path, key_path: str, json_value: str
) -> dict[str, Any]:
    """Set a value in config file using the MCP protocol.

    Args:
        mcp_client: MCP client connected via JSON-RPC protocol
        file_path: Path to configuration file
        key_path: Dot-separated key path
        json_value: Value as JSON string

    Returns:
        Result dictionary from data tool
    """
    return mcp_client.call_tool(
        "data",
        {
            "file_path": str(file_path),
            "operation": "set",
            "key_path": key_path,
            "value": json_value,
        },
    )


def read_file_and_parse_value(file_path: Path, key_path: str) -> Any:
    """Read file directly and extract value to verify actual file content.

    This bypasses the MCP server completely to verify what was actually
    written to the file.

    Args:
        file_path: Path to configuration file
        key_path: Dot-separated key path (supports simple single-level keys)

    Returns:
        The value from the file
    """
    suffix = file_path.suffix.lower()
    content = file_path.read_text(encoding="utf-8")

    if suffix == ".json":
        data = json.loads(content)
        return data.get(key_path)
    if suffix in (".yaml", ".yml"):
        # Use ruamel.yaml for accurate YAML parsing
        from ruamel.yaml import YAML

        yaml = YAML()
        data = yaml.load(content)
        return data.get(key_path) if data else None
    if suffix == ".toml":
        import tomlkit

        data = tomlkit.parse(content)
        return data.get(key_path)
    error_msg = f"Unsupported file format: {suffix}"
    raise ValueError(error_msg)


# ==============================================================================
# String Type Preservation Tests
# ==============================================================================


class TestStringTypePreservation:
    """Test that string values remain strings after SET operations via MCP protocol."""

    @pytest.mark.protocol
    @pytest.mark.integration
    @pytest.mark.parametrize("file_format", ["json", "yaml", "toml"])
    def test_set_plain_string(
        self,
        file_format: str,
        json_config_with_types: Path,
        yaml_config_with_types: Path,
        toml_config_with_types: Path,
        mcp_client: MCPClient,
    ) -> None:
        """Test SET preserves plain string type via MCP protocol.

        Tests: Plain string type preservation through MCP JSON-RPC protocol
        How: Set a new string value via protocol, verify it remains a string
        Why: Basic string handling must work correctly through the full protocol stack
        """
        # Arrange - select appropriate fixture
        config_map = {
            "json": json_config_with_types,
            "yaml": yaml_config_with_types,
            "toml": toml_config_with_types,
        }
        config_path = config_map[file_format]

        # Act - set a new string value via MCP protocol
        set_value_via_protocol(mcp_client, config_path, "string_value", '"world"')

        # Assert - verify actual file content (bypass protocol for verification)
        actual_value = read_file_and_parse_value(config_path, "string_value")
        assert isinstance(actual_value, str), (
            f"Expected str, got {type(actual_value).__name__}: {actual_value!r}"
        )
        assert actual_value == "world"

    @pytest.mark.protocol
    @pytest.mark.integration
    @pytest.mark.parametrize("file_format", ["json", "yaml", "toml"])
    def test_set_numeric_looking_string(
        self,
        file_format: str,
        json_config_with_types: Path,
        yaml_config_with_types: Path,
        toml_config_with_types: Path,
        mcp_client: MCPClient,
    ) -> None:
        """Test SET preserves string that looks like a float via MCP protocol.

        Tests: Numeric-looking string type preservation through MCP protocol
        How: Set string "3.12" via protocol, verify it does NOT become float 3.12
        Why: Version strings like "3.11" must remain strings through the protocol

        Note: This test documents the known bug where "3.12" becomes 3.12
        when passing through the MCP JSON-RPC protocol layer.
        """
        # Arrange - select appropriate fixture
        config_map = {
            "json": json_config_with_types,
            "yaml": yaml_config_with_types,
            "toml": toml_config_with_types,
        }
        config_path = config_map[file_format]

        # Act - set a string that looks like a float via MCP protocol
        set_value_via_protocol(mcp_client, config_path, "string_numeric", '"3.12"')

        # Assert - verify actual file content (bypass protocol for verification)
        actual_value = read_file_and_parse_value(config_path, "string_numeric")
        assert isinstance(actual_value, str), (
            f"Type coercion bug in {file_format} via MCP protocol: "
            f"Expected str, got {type(actual_value).__name__}: {actual_value!r}. "
            f"String '3.12' was incorrectly converted to {type(actual_value).__name__} "
            f"when passing through MCP JSON-RPC protocol."
        )
        assert actual_value == "3.12"

    @pytest.mark.protocol
    @pytest.mark.integration
    @pytest.mark.parametrize("file_format", ["json", "yaml", "toml"])
    def test_set_integer_looking_string(
        self,
        file_format: str,
        json_config_with_types: Path,
        yaml_config_with_types: Path,
        toml_config_with_types: Path,
        mcp_client: MCPClient,
    ) -> None:
        """Test SET preserves string that looks like an integer via MCP protocol.

        Tests: Integer-looking string type preservation through MCP protocol
        How: Set string "99" via protocol, verify it does NOT become integer 99
        Why: Strings like "42" or port numbers as strings must remain strings
        """
        # Arrange - select appropriate fixture
        config_map = {
            "json": json_config_with_types,
            "yaml": yaml_config_with_types,
            "toml": toml_config_with_types,
        }
        config_path = config_map[file_format]

        # Act - set a string that looks like an integer via MCP protocol
        set_value_via_protocol(mcp_client, config_path, "string_integer", '"99"')

        # Assert - verify actual file content (bypass protocol for verification)
        actual_value = read_file_and_parse_value(config_path, "string_integer")
        assert isinstance(actual_value, str), (
            f"Type coercion bug in {file_format} via MCP protocol: "
            f"Expected str, got {type(actual_value).__name__}: {actual_value!r}. "
            f"String '99' was incorrectly converted to {type(actual_value).__name__}."
        )
        assert actual_value == "99"

    @pytest.mark.protocol
    @pytest.mark.integration
    @pytest.mark.parametrize("file_format", ["json", "yaml", "toml"])
    def test_set_bool_looking_string(
        self,
        file_format: str,
        json_config_with_types: Path,
        yaml_config_with_types: Path,
        toml_config_with_types: Path,
        mcp_client: MCPClient,
    ) -> None:
        """Test SET preserves string that looks like a boolean via MCP protocol.

        Tests: Boolean-looking string type preservation through MCP protocol
        How: Set string "false" via protocol, verify it does NOT become boolean false
        Why: String values that match boolean keywords must remain strings
        """
        # Arrange - select appropriate fixture
        config_map = {
            "json": json_config_with_types,
            "yaml": yaml_config_with_types,
            "toml": toml_config_with_types,
        }
        config_path = config_map[file_format]

        # Act - set a string that looks like a boolean via MCP protocol
        set_value_via_protocol(mcp_client, config_path, "string_bool", '"false"')

        # Assert - verify actual file content (bypass protocol for verification)
        actual_value = read_file_and_parse_value(config_path, "string_bool")
        assert isinstance(actual_value, str), (
            f"Type coercion bug in {file_format} via MCP protocol: "
            f"Expected str, got {type(actual_value).__name__}: {actual_value!r}. "
            f"String 'false' was incorrectly converted to {type(actual_value).__name__}."
        )
        assert actual_value == "false"


# ==============================================================================
# Numeric Type Preservation Tests
# ==============================================================================


class TestNumericTypePreservation:
    """Test that numeric values maintain their types after SET operations via MCP protocol."""

    @pytest.mark.protocol
    @pytest.mark.integration
    @pytest.mark.parametrize("file_format", ["json", "yaml", "toml"])
    def test_set_integer_value(
        self,
        file_format: str,
        json_config_with_types: Path,
        yaml_config_with_types: Path,
        toml_config_with_types: Path,
        mcp_client: MCPClient,
    ) -> None:
        """Test SET preserves integer type via MCP protocol.

        Tests: Integer type preservation through MCP JSON-RPC protocol
        How: Set a new integer value via protocol, verify it remains an integer
        Why: Integer values must not become strings or floats through the protocol
        """
        # Arrange - select appropriate fixture
        config_map = {
            "json": json_config_with_types,
            "yaml": yaml_config_with_types,
            "toml": toml_config_with_types,
        }
        config_path = config_map[file_format]

        # Act - set an integer value via MCP protocol
        set_value_via_protocol(mcp_client, config_path, "integer_value", "100")

        # Assert - verify actual file content
        actual_value = read_file_and_parse_value(config_path, "integer_value")
        assert isinstance(actual_value, int), (
            f"Expected int, got {type(actual_value).__name__}: {actual_value!r}"
        )
        assert actual_value == 100

    @pytest.mark.protocol
    @pytest.mark.integration
    @pytest.mark.parametrize("file_format", ["json", "yaml", "toml"])
    def test_set_float_value(
        self,
        file_format: str,
        json_config_with_types: Path,
        yaml_config_with_types: Path,
        toml_config_with_types: Path,
        mcp_client: MCPClient,
    ) -> None:
        """Test SET preserves float type via MCP protocol.

        Tests: Float type preservation through MCP JSON-RPC protocol
        How: Set a new float value via protocol, verify it remains a float
        Why: Float values must maintain precision through the protocol
        """
        # Arrange - select appropriate fixture
        config_map = {
            "json": json_config_with_types,
            "yaml": yaml_config_with_types,
            "toml": toml_config_with_types,
        }
        config_path = config_map[file_format]

        # Act - set a float value via MCP protocol
        set_value_via_protocol(mcp_client, config_path, "float_value", str(math.e))

        # Assert - verify actual file content
        actual_value = read_file_and_parse_value(config_path, "float_value")
        assert isinstance(actual_value, float), (
            f"Expected float, got {type(actual_value).__name__}: {actual_value!r}"
        )
        assert abs(actual_value - math.e) < 0.0001

    @pytest.mark.protocol
    @pytest.mark.integration
    @pytest.mark.parametrize("file_format", ["json", "yaml", "toml"])
    def test_set_whole_number_float(
        self,
        file_format: str,
        json_config_with_types: Path,
        yaml_config_with_types: Path,
        toml_config_with_types: Path,
        mcp_client: MCPClient,
    ) -> None:
        """Test SET preserves whole number as float via MCP protocol.

        Tests: Whole number float type preservation through MCP protocol
        How: Set float 5.0 via protocol, verify it remains float (not integer 5)
        Why: Explicit floats like 3.0 should remain floats through the protocol

        Note: JSON/YAML may not distinguish 3 from 3.0 during serialization,
        but when explicitly set as 3.0, behavior should be consistent.
        """
        # Arrange - select appropriate fixture
        config_map = {
            "json": json_config_with_types,
            "yaml": yaml_config_with_types,
            "toml": toml_config_with_types,
        }
        config_path = config_map[file_format]

        # Act - set a whole number as float via MCP protocol
        set_value_via_protocol(mcp_client, config_path, "float_whole", "5.0")

        # Assert - value is numeric (JSON doesn't distinguish int/float for whole numbers)
        actual_value = read_file_and_parse_value(config_path, "float_whole")
        assert isinstance(actual_value, (int, float)), (
            f"Expected numeric, got {type(actual_value).__name__}: {actual_value!r}"
        )
        assert actual_value == 5.0


# ==============================================================================
# Boolean Type Preservation Tests
# ==============================================================================


class TestBooleanTypePreservation:
    """Test that boolean values maintain their types after SET operations via MCP protocol."""

    @pytest.mark.protocol
    @pytest.mark.integration
    @pytest.mark.parametrize("file_format", ["json", "yaml", "toml"])
    def test_set_true_value(
        self,
        file_format: str,
        json_config_with_types: Path,
        yaml_config_with_types: Path,
        toml_config_with_types: Path,
        mcp_client: MCPClient,
    ) -> None:
        """Test SET preserves boolean true via MCP protocol.

        Tests: Boolean true type preservation through MCP protocol
        How: Set true value via protocol, verify it is boolean True, not string "true"
        Why: Boolean values must remain booleans through the protocol
        """
        # Arrange - select appropriate fixture
        config_map = {
            "json": json_config_with_types,
            "yaml": yaml_config_with_types,
            "toml": toml_config_with_types,
        }
        config_path = config_map[file_format]

        # Act - set boolean true via MCP protocol (was false)
        set_value_via_protocol(mcp_client, config_path, "bool_false", "true")

        # Assert - verify actual file content
        actual_value = read_file_and_parse_value(config_path, "bool_false")
        assert isinstance(actual_value, bool), (
            f"Expected bool, got {type(actual_value).__name__}: {actual_value!r}"
        )
        assert actual_value is True

    @pytest.mark.protocol
    @pytest.mark.integration
    @pytest.mark.parametrize("file_format", ["json", "yaml", "toml"])
    def test_set_false_value(
        self,
        file_format: str,
        json_config_with_types: Path,
        yaml_config_with_types: Path,
        toml_config_with_types: Path,
        mcp_client: MCPClient,
    ) -> None:
        """Test SET preserves boolean false via MCP protocol.

        Tests: Boolean false type preservation through MCP protocol
        How: Set false value via protocol, verify it is boolean False, not string "false"
        Why: Boolean values must remain booleans through the protocol
        """
        # Arrange - select appropriate fixture
        config_map = {
            "json": json_config_with_types,
            "yaml": yaml_config_with_types,
            "toml": toml_config_with_types,
        }
        config_path = config_map[file_format]

        # Act - set boolean false via MCP protocol (was true)
        set_value_via_protocol(mcp_client, config_path, "bool_true", "false")

        # Assert - verify actual file content
        actual_value = read_file_and_parse_value(config_path, "bool_true")
        assert isinstance(actual_value, bool), (
            f"Expected bool, got {type(actual_value).__name__}: {actual_value!r}"
        )
        assert actual_value is False


# ==============================================================================
# Null Type Preservation Tests
# ==============================================================================


class TestNullTypePreservation:
    """Test that null values maintain their types after SET operations via MCP protocol."""

    @pytest.mark.protocol
    @pytest.mark.integration
    @pytest.mark.parametrize("file_format", ["json", "yaml"])
    def test_set_null_value(
        self,
        file_format: str,
        json_config_with_types: Path,
        yaml_config_with_types: Path,
        mcp_client: MCPClient,
    ) -> None:
        """Test SET preserves null type via MCP protocol.

        Tests: Null type preservation through MCP protocol
        How: Set null value via protocol, verify it is None, not string "null"
        Why: Null values must remain null through the protocol

        Note: TOML does not have a native null type, so excluded from this test.
        """
        # Arrange - select appropriate fixture
        config_map = {"json": json_config_with_types, "yaml": yaml_config_with_types}
        config_path = config_map[file_format]

        # First set to a non-null value, then set back to null via protocol
        set_value_via_protocol(mcp_client, config_path, "string_value", "null")

        # Assert - verify actual file content
        actual_value = read_file_and_parse_value(config_path, "string_value")
        assert actual_value is None, (
            f"Expected None, got {type(actual_value).__name__}: {actual_value!r}"
        )


# ==============================================================================
# Complex Type Preservation Tests
# ==============================================================================


class TestComplexTypePreservation:
    """Test that arrays and objects maintain their types after SET operations via MCP protocol."""

    @pytest.mark.protocol
    @pytest.mark.integration
    @pytest.mark.parametrize("file_format", ["json", "yaml", "toml"])
    def test_set_array_of_strings(
        self,
        file_format: str,
        json_config_with_types: Path,
        yaml_config_with_types: Path,
        toml_config_with_types: Path,
        mcp_client: MCPClient,
    ) -> None:
        """Test SET preserves array of strings via MCP protocol.

        Tests: Array type preservation through MCP protocol
        How: Set a new array via protocol, verify elements remain strings
        Why: Array contents must maintain their types through the protocol
        """
        # Arrange - select appropriate fixture
        config_map = {
            "json": json_config_with_types,
            "yaml": yaml_config_with_types,
            "toml": toml_config_with_types,
        }
        config_path = config_map[file_format]

        # Act - set a new array of strings via MCP protocol
        set_value_via_protocol(
            mcp_client, config_path, "array_strings", '["x", "y", "z"]'
        )

        # Assert - verify actual file content
        actual_value = read_file_and_parse_value(config_path, "array_strings")
        assert isinstance(actual_value, list), (
            f"Expected list, got {type(actual_value).__name__}: {actual_value!r}"
        )
        assert list(actual_value) == ["x", "y", "z"]
        for item in actual_value:
            assert isinstance(item, str), (
                f"Array item should be str, got {type(item).__name__}"
            )

    @pytest.mark.protocol
    @pytest.mark.integration
    @pytest.mark.parametrize("file_format", ["json", "yaml", "toml"])
    def test_set_array_of_integers(
        self,
        file_format: str,
        json_config_with_types: Path,
        yaml_config_with_types: Path,
        toml_config_with_types: Path,
        mcp_client: MCPClient,
    ) -> None:
        """Test SET preserves array of integers via MCP protocol.

        Tests: Array with integers type preservation through MCP protocol
        How: Set a new array via protocol, verify elements remain integers
        Why: Numeric arrays must maintain element types through the protocol
        """
        # Arrange - select appropriate fixture
        config_map = {
            "json": json_config_with_types,
            "yaml": yaml_config_with_types,
            "toml": toml_config_with_types,
        }
        config_path = config_map[file_format]

        # Act - set a new array of integers via MCP protocol
        set_value_via_protocol(
            mcp_client, config_path, "array_integers", "[10, 20, 30]"
        )

        # Assert - verify actual file content
        actual_value = read_file_and_parse_value(config_path, "array_integers")
        assert isinstance(actual_value, list), (
            f"Expected list, got {type(actual_value).__name__}: {actual_value!r}"
        )
        assert list(actual_value) == [10, 20, 30]
        for item in actual_value:
            assert isinstance(item, int), (
                f"Array item should be int, got {type(item).__name__}"
            )

    @pytest.mark.protocol
    @pytest.mark.integration
    @pytest.mark.parametrize("file_format", ["json", "yaml"])
    def test_set_object_value(
        self,
        file_format: str,
        json_config_with_types: Path,
        yaml_config_with_types: Path,
        mcp_client: MCPClient,
    ) -> None:
        """Test SET preserves object/dict value via MCP protocol.

        Tests: Object type preservation through MCP protocol
        How: Set a new object via protocol, verify it remains a dict with correct types
        Why: Nested objects must maintain their structure and value types through the protocol

        Note: TOML inline tables have limitations, so excluded from this test.
        """
        # Arrange - select appropriate fixture
        config_map = {"json": json_config_with_types, "yaml": yaml_config_with_types}
        config_path = config_map[file_format]

        # Act - set a new object via MCP protocol
        set_value_via_protocol(
            mcp_client, config_path, "object_value", '{"key": "val", "num": 42}'
        )

        # Assert - verify actual file content
        actual_value = read_file_and_parse_value(config_path, "object_value")
        assert isinstance(actual_value, dict), (
            f"Expected dict, got {type(actual_value).__name__}: {actual_value!r}"
        )
        assert actual_value["key"] == "val"
        assert isinstance(actual_value["key"], str)
        assert actual_value["num"] == 42
        assert isinstance(actual_value["num"], int)


# ==============================================================================
# Edge Case Tests for Numeric-Looking Strings
# ==============================================================================


class TestNumericLookingStringEdgeCases:
    """Additional edge case tests for strings that could be misinterpreted as numbers via MCP protocol."""

    @pytest.mark.protocol
    @pytest.mark.integration
    @pytest.mark.parametrize(
        "string_value",
        [
            "3.11",  # Python version
            "1.0.0",  # Semantic version
            "192.168.1.1",  # IP address
            "+42",  # Signed integer
            "-3.14",  # Negative float
            "1e10",  # Scientific notation
            "0x1A",  # Hex notation
            "007",  # Leading zeros
            "3.",  # Trailing decimal
            ".5",  # Leading decimal
        ],
    )
    @pytest.mark.parametrize("file_format", ["json", "yaml", "toml"])
    def test_numeric_looking_strings_preserved(
        self,
        string_value: str,
        file_format: str,
        json_config_with_types: Path,
        yaml_config_with_types: Path,
        toml_config_with_types: Path,
        mcp_client: MCPClient,
    ) -> None:
        """Test that various numeric-looking strings remain strings via MCP protocol.

        Tests: Edge case string type preservation through MCP protocol
        How: Set strings that look like numbers via protocol, verify they remain strings
        Why: Version strings, IPs, and other numeric-looking data must stay strings
        """
        # Arrange - select appropriate fixture
        config_map = {
            "json": json_config_with_types,
            "yaml": yaml_config_with_types,
            "toml": toml_config_with_types,
        }
        config_path = config_map[file_format]

        # Act - set a numeric-looking string via MCP protocol (JSON-encoded)
        json_encoded_value = json.dumps(string_value)
        set_value_via_protocol(
            mcp_client, config_path, "string_value", json_encoded_value
        )

        # Assert - verify actual file content (bypass protocol for verification)
        actual_value = read_file_and_parse_value(config_path, "string_value")
        assert isinstance(actual_value, str), (
            f"Type coercion bug for '{string_value}' in {file_format} via MCP protocol: "
            f"Expected str, got {type(actual_value).__name__}: {actual_value!r}"
        )
        assert actual_value == string_value


# ==============================================================================
# Round-Trip Type Preservation Tests
# ==============================================================================


class TestRoundTripTypePreservation:
    """Test that types survive a full round-trip (set via protocol -> read file)."""

    @pytest.mark.protocol
    @pytest.mark.integration
    @pytest.mark.parametrize("file_format", ["json", "yaml", "toml"])
    def test_roundtrip_preserves_all_types(
        self,
        file_format: str,
        json_config_with_types: Path,
        yaml_config_with_types: Path,
        toml_config_with_types: Path,
        mcp_client: MCPClient,
    ) -> None:
        """Test that all value types survive a set-via-protocol -> read-file cycle.

        Tests: Full round-trip type preservation through MCP protocol
        How: Set values via protocol, read file directly to verify types preserved
        Why: Configuration management requires type fidelity through the protocol
        """
        # Arrange - select appropriate fixture
        config_map = {
            "json": json_config_with_types,
            "yaml": yaml_config_with_types,
            "toml": toml_config_with_types,
        }
        config_path = config_map[file_format]

        # Define test cases: (key, new_json_value, expected_type, expected_value)
        test_cases: list[tuple[str, str, type, Any]] = [
            ("string_value", '"updated"', str, "updated"),
            ("string_numeric", '"4.0"', str, "4.0"),
            ("integer_value", "999", int, 999),
            ("float_value", "1.5", float, 1.5),
            ("bool_true", "false", bool, False),
            ("array_strings", '["p", "q"]', list, ["p", "q"]),
        ]

        # Act & Assert - verify each type survives round-trip
        for key, json_value, expected_type, expected_value in test_cases:
            set_value_via_protocol(mcp_client, config_path, key, json_value)
            actual_value = read_file_and_parse_value(config_path, key)

            # Handle list comparison for TOML (may return special list type)
            if expected_type is list:
                assert isinstance(actual_value, (list, tuple)), (
                    f"Round-trip type mismatch for '{key}' in {file_format}: "
                    f"Expected list-like, got {type(actual_value).__name__}: {actual_value!r}"
                )
                assert list(actual_value) == expected_value, (
                    f"Value mismatch for '{key}': expected {expected_value!r}, got {list(actual_value)!r}"
                )
            else:
                assert isinstance(actual_value, expected_type), (
                    f"Round-trip type mismatch for '{key}' in {file_format}: "
                    f"Expected {expected_type.__name__}, got {type(actual_value).__name__}: {actual_value!r}"
                )
                assert actual_value == expected_value, (
                    f"Value mismatch for '{key}': expected {expected_value!r}, got {actual_value!r}"
                )


# ==============================================================================
# AI Agent Usage Pattern Tests - EXPOSE TYPE COERCION BUG
# ==============================================================================


class TestAIAgentUsagePatternsBug:
    """Tests demonstrating the type coercion bug when AI agents use the MCP tool.

    CONTEXT:
    AI agents naturally send values like `value="3.12"` when they want to set
    a string value. However, the MCP protocol layer strips the outer quotes
    during JSON serialization/deserialization, so the server receives `3.12`
    (a valid JSON number) instead of `"3.12"` (a JSON string).

    ROOT CAUSE:
    In server.py:436, `parsed_value = orjson.loads(value)` expects `value`
    to be valid JSON. When an AI agent sends `value="3.12"`, the server
    receives `3.12` which parses as a float, not a string.

    WORKAROUND (current tests use this):
    Send `value='"3.12"'` - a JSON-encoded string literal with inner quotes.
    This is unnatural for AI agents and not discoverable without documentation.

    THE BUG:
    There is no way for an AI agent to naturally express "set this to the
    string 3.12" without knowing to double-encode the value.

    These tests are marked xfail because they EXPOSE a known bug.
    When the bug is fixed, remove the xfail markers.
    """

    @pytest.mark.protocol
    @pytest.mark.integration
    def test_ai_agent_sets_python_version_string_toml(
        self, toml_config_with_types: Path, mcp_client: MCPClient
    ) -> None:
        """Test AI agent setting Python version string in TOML using value_type parameter.

        Tests: AI agent usage pattern for setting version strings with value_type
        How: Send value="3.12" with value_type="string", verify file content
        Why: Demonstrates that value_type parameter solves the type coercion bug

        Scenario:
        AI agent wants to set `pythonVersion = "3.12"` in pyproject.toml.
        Agent sends: {"value": "3.12", "value_type": "string"}
        Result: File contains `pythonVersion = "3.12"` (a string as intended).
        """
        # Arrange - Use TOML config (where bug was originally observed)
        config_path = toml_config_with_types

        # Act - Send value with value_type="string" to treat it as literal string
        mcp_client.call_tool(
            "data",
            {
                "file_path": str(config_path),
                "operation": "set",
                "key_path": "string_numeric",
                "value": "3.12",  # The string we want to set
                "value_type": "string",  # Treat as literal string (no JSON parsing)
            },
        )

        # Assert - The file should contain the STRING "3.12", not the NUMBER 3.12
        actual_value = read_file_and_parse_value(config_path, "string_numeric")

        assert isinstance(actual_value, str), (
            f"Expected str with value_type='string', got {type(actual_value).__name__}: {actual_value!r}"
        )
        assert actual_value == "3.12"

    @pytest.mark.protocol
    @pytest.mark.integration
    def test_ai_agent_sets_port_as_string_yaml(
        self, yaml_config_with_types: Path, mcp_client: MCPClient
    ) -> None:
        """Test AI agent setting port number as string in YAML using value_type parameter.

        Tests: AI agent usage pattern for setting port strings with value_type
        How: Send value="8080" with value_type="string", verify file content
        Why: Demonstrates that value_type parameter solves the type coercion bug

        Scenario:
        AI agent wants to set `port: "8080"` (string) in a config.
        Agent sends: {"value": "8080", "value_type": "string"}
        Result: File contains `port: "8080"` (a string as intended).
        """
        # Arrange
        config_path = yaml_config_with_types

        # Act - AI agent sends value with value_type="string"
        mcp_client.call_tool(
            "data",
            {
                "file_path": str(config_path),
                "operation": "set",
                "key_path": "string_integer",
                "value": "8080",  # The string we want to set
                "value_type": "string",  # Treat as literal string
            },
        )

        # Assert - Should be STRING "8080", not INTEGER 8080
        actual_value = read_file_and_parse_value(config_path, "string_integer")

        assert isinstance(actual_value, str), (
            f"Expected str with value_type='string', got {type(actual_value).__name__}: {actual_value!r}"
        )
        assert actual_value == "8080"

    @pytest.mark.protocol
    @pytest.mark.integration
    def test_ai_agent_sets_enabled_as_literal_string_json(
        self, json_config_with_types: Path, mcp_client: MCPClient
    ) -> None:
        """Test AI agent setting 'true' as literal string in JSON using value_type parameter.

        Tests: AI agent usage pattern for setting boolean-looking strings with value_type
        How: Send value="true" with value_type="string", verify file content
        Why: Demonstrates that value_type parameter solves the type coercion bug

        Scenario:
        AI agent wants to set `enabled: "true"` (the string literal, not boolean).
        Agent sends: {"value": "true", "value_type": "string"}
        Result: File contains `enabled: "true"` (string as intended).
        """
        # Arrange
        config_path = json_config_with_types

        # Act - AI agent sends value with value_type="string"
        mcp_client.call_tool(
            "data",
            {
                "file_path": str(config_path),
                "operation": "set",
                "key_path": "string_bool",
                "value": "true",  # The string we want to set
                "value_type": "string",  # Treat as literal string
            },
        )

        # Assert - Should be STRING "true", not BOOLEAN True
        actual_value = read_file_and_parse_value(config_path, "string_bool")

        assert isinstance(actual_value, str), (
            f"Expected str with value_type='string', got {type(actual_value).__name__}: {actual_value!r}"
        )
        assert actual_value == "true"

    @pytest.mark.protocol
    @pytest.mark.integration
    @pytest.mark.parametrize("file_format", ["json", "yaml"])
    def test_ai_agent_sets_null_as_literal_string(
        self,
        file_format: str,
        json_config_with_types: Path,
        yaml_config_with_types: Path,
        mcp_client: MCPClient,
    ) -> None:
        """Test AI agent setting 'null' as literal string using value_type parameter.

        Tests: AI agent usage pattern for setting null-looking strings with value_type
        How: Send value="null" with value_type="string", verify file content
        Why: Demonstrates that value_type parameter solves the type coercion bug

        Scenario:
        AI agent wants to set a field to the literal string "null" (e.g., for display).
        Agent sends: {"value": "null", "value_type": "string"}
        Result: File contains the string "null" (not None/null).
        """
        # Arrange
        config_map = {"json": json_config_with_types, "yaml": yaml_config_with_types}
        config_path = config_map[file_format]

        # Act - AI agent sends value with value_type="string"
        mcp_client.call_tool(
            "data",
            {
                "file_path": str(config_path),
                "operation": "set",
                "key_path": "string_value",
                "value": "null",  # The string we want to set
                "value_type": "string",  # Treat as literal string
            },
        )

        # Assert - Should be STRING "null", not None
        actual_value = read_file_and_parse_value(config_path, "string_value")

        assert actual_value is not None, "Expected str 'null', got None"
        assert isinstance(actual_value, str), (
            f"Expected str with value_type='string', got {type(actual_value).__name__}: {actual_value!r}"
        )
        assert actual_value == "null"


class TestAIAgentVersionStringsBug:
    """Tests specifically for version string handling - a common AI agent use case.

    Version strings like "3.11", "1.0.0", "2.7" are extremely common in configuration
    files (pyproject.toml, package.json equivalents, CI configs). AI agents frequently
    need to modify these values.

    These tests verify that AI agents CANNOT set version strings without
    knowing the workaround of double-encoding.
    """

    @pytest.mark.protocol
    @pytest.mark.integration
    @pytest.mark.parametrize(
        "version_string",
        [
            "3.11",  # Python version
            "3.0",  # Major.minor
            "2",  # Single digit version
            "10",  # Two digit version
        ],
    )
    @pytest.mark.parametrize("file_format", ["json", "yaml", "toml"])
    def test_ai_agent_simple_version_strings(
        self,
        version_string: str,
        file_format: str,
        json_config_with_types: Path,
        yaml_config_with_types: Path,
        toml_config_with_types: Path,
        mcp_client: MCPClient,
    ) -> None:
        """Test AI agent setting simple version strings using value_type parameter.

        Tests: AI agent usage pattern for simple version strings with value_type
        How: Send version strings with value_type="string", verify file content
        Why: Demonstrates that value_type parameter solves the type coercion bug

        These version strings look like valid numbers to JSON parsing, but with
        value_type="string" they are preserved as strings.
        """
        # Arrange
        config_map = {
            "json": json_config_with_types,
            "yaml": yaml_config_with_types,
            "toml": toml_config_with_types,
        }
        config_path = config_map[file_format]

        # Act - AI agent sends version string with value_type="string"
        mcp_client.call_tool(
            "data",
            {
                "file_path": str(config_path),
                "operation": "set",
                "key_path": "string_numeric",
                "value": version_string,
                "value_type": "string",  # Treat as literal string
            },
        )

        # Assert - Should be STRING
        actual_value = read_file_and_parse_value(config_path, "string_numeric")

        assert isinstance(actual_value, str), (
            f"Expected str with value_type='string', got {type(actual_value).__name__} ({actual_value!r}) in {file_format}"
        )
        assert actual_value == version_string

    @pytest.mark.protocol
    @pytest.mark.integration
    @pytest.mark.parametrize(
        "version_string",
        [
            "1.0.0",  # Semver - NOT valid JSON, will fail parsing
            "v1.2.3",  # Prefixed version - NOT valid JSON
            "2024.01.15",  # Date-based version - NOT valid JSON
        ],
    )
    @pytest.mark.parametrize("file_format", ["json", "yaml", "toml"])
    def test_ai_agent_complex_version_strings_fail_with_parse_error(
        self,
        version_string: str,
        file_format: str,
        json_config_with_types: Path,
        yaml_config_with_types: Path,
        toml_config_with_types: Path,
        mcp_client: MCPClient,
    ) -> None:
        """Test AI agent setting complex version strings fails with JSON parse error.

        Tests: AI agent usage pattern for semver and complex version strings
        How: Send version strings that are not valid JSON, expect MCP error response
        Why: Demonstrates that AI agents get an error for some strings but not others

        These version strings are NOT valid JSON numbers, so orjson.loads()
        fails with a parse error. This is a DIFFERENT failure mode than
        the type coercion bug - these at least fail loudly.

        Note: MCP returns errors with isError=true in the result, not as protocol
        errors. The error message is returned as text content, not JSON.
        """
        # Arrange
        config_map = {
            "json": json_config_with_types,
            "yaml": yaml_config_with_types,
            "toml": toml_config_with_types,
        }
        config_path = config_map[file_format]

        # Act - Call the tool with an invalid JSON value
        # MCP returns error responses with isError=true in the result
        # The response.result.content[0].text contains the error message (not JSON)
        response = mcp_client._send_request(
            "tools/call",
            {
                "name": "data",
                "arguments": {
                    "file_path": str(config_path),
                    "operation": "set",
                    "key_path": "string_value",
                    "value": version_string,  # Not valid JSON
                },
            },
        )

        # Assert - MCP should return an error response
        result = response.get("result", {})
        is_error = result.get("isError", False)
        content = result.get("content", [])
        error_text = content[0].get("text", "") if content else ""

        assert is_error is True, (
            f"Expected MCP to return isError=true for invalid JSON value '{version_string}', "
            f"but got isError={is_error}. Response: {response}"
        )
        assert "Invalid JSON value" in error_text, (
            f"Expected error message to contain 'Invalid JSON value' for '{version_string}', but got: {error_text}"
        )

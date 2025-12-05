"""Tests for configuration management module.

Tests configuration format validation, environment variable parsing,
and default configuration handling.
"""

import pytest

from mcp_json_yaml_toml.config import (
    DEFAULT_FORMATS,
    ConfigFormat,
    get_enabled_formats_str,
    is_format_enabled,
    parse_enabled_formats,
    validate_format,
)


class TestConfigFormat:
    """Test ConfigFormat enum."""

    def test_config_format_values(self) -> None:
        """Test ConfigFormat enum has correct string values.

        Tests: ConfigFormat enum values
        How: Assert each enum member has expected string value
        Why: Ensure format names match expected lowercase strings
        """
        # Arrange - get enum values
        # Act - access enum members
        # Assert - verify string values
        assert ConfigFormat.JSON.value == "json"
        assert ConfigFormat.YAML.value == "yaml"
        assert ConfigFormat.TOML.value == "toml"
        assert ConfigFormat.XML.value == "xml"

    def test_config_format_is_string_enum(self) -> None:
        """Test ConfigFormat is a StrEnum.

        Tests: ConfigFormat type
        How: Verify enum inherits from str
        Why: Ensure ConfigFormat can be used as string
        """
        # Arrange - get enum instance
        # Act - check type
        # Assert - verify is string
        assert isinstance(ConfigFormat.JSON, str)
        assert isinstance(ConfigFormat.YAML, str)


class TestParseEnabledFormats:
    """Test parse_enabled_formats function."""

    def test_parse_enabled_formats_default(self, clean_environment: None) -> None:
        """Test parse_enabled_formats returns defaults when env var not set.

        Tests: Default format configuration
        How: Call parse_enabled_formats with no MCP_CONFIG_FORMATS env var
        Why: Verify default behavior when environment is not configured
        """
        # Arrange - clean environment (no MCP_CONFIG_FORMATS)
        # Act - parse enabled formats
        result = parse_enabled_formats()

        # Assert - returns default formats
        assert result == list(DEFAULT_FORMATS)
        assert len(result) == 3
        assert ConfigFormat.JSON in result
        assert ConfigFormat.YAML in result
        assert ConfigFormat.TOML in result

    def test_parse_enabled_formats_from_env(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test parse_enabled_formats reads from environment variable.

        Tests: Environment variable parsing
        How: Set MCP_CONFIG_FORMATS and call parse_enabled_formats
        Why: Verify formats can be configured via environment
        """
        # Arrange - set environment variable
        monkeypatch.setenv("MCP_CONFIG_FORMATS", "json,toml")

        # Act - parse enabled formats
        result = parse_enabled_formats()

        # Assert - returns formats from env
        assert len(result) == 2
        assert ConfigFormat.JSON in result
        assert ConfigFormat.TOML in result
        assert ConfigFormat.YAML not in result

    def test_parse_enabled_formats_single_format(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test parse_enabled_formats with single format.

        Tests: Single format configuration
        How: Set MCP_CONFIG_FORMATS to single value
        Why: Verify single format can be enabled
        """
        # Arrange - set single format
        monkeypatch.setenv("MCP_CONFIG_FORMATS", "yaml")

        # Act - parse enabled formats
        result = parse_enabled_formats()

        # Assert - returns single format
        assert len(result) == 1
        assert result[0] == ConfigFormat.YAML

    def test_parse_enabled_formats_case_insensitive(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test parse_enabled_formats is case-insensitive.

        Tests: Case-insensitive parsing
        How: Set MCP_CONFIG_FORMATS with mixed case
        Why: Ensure user-friendly configuration parsing
        """
        # Arrange - set mixed case formats
        monkeypatch.setenv("MCP_CONFIG_FORMATS", "JSON,Yaml,TOML")

        # Act - parse enabled formats
        result = parse_enabled_formats()

        # Assert - returns normalized formats
        assert len(result) == 3
        assert ConfigFormat.JSON in result
        assert ConfigFormat.YAML in result
        assert ConfigFormat.TOML in result

    def test_parse_enabled_formats_whitespace_handling(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test parse_enabled_formats handles whitespace.

        Tests: Whitespace trimming
        How: Set MCP_CONFIG_FORMATS with extra spaces
        Why: Ensure robust parsing of user input
        """
        # Arrange - set formats with whitespace
        monkeypatch.setenv("MCP_CONFIG_FORMATS", " json , yaml , toml ")

        # Act - parse enabled formats
        result = parse_enabled_formats()

        # Assert - returns trimmed formats
        assert len(result) == 3
        assert ConfigFormat.JSON in result
        assert ConfigFormat.YAML in result
        assert ConfigFormat.TOML in result

    def test_parse_enabled_formats_invalid_falls_back(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test parse_enabled_formats falls back to defaults on invalid input.

        Tests: Invalid input handling
        How: Set MCP_CONFIG_FORMATS to invalid values
        Why: Ensure graceful degradation with bad configuration
        """
        # Arrange - set invalid formats
        monkeypatch.setenv("MCP_CONFIG_FORMATS", "invalid,badformat")

        # Act - parse enabled formats
        result = parse_enabled_formats()

        # Assert - returns defaults
        assert result == list(DEFAULT_FORMATS)

    def test_parse_enabled_formats_empty_string_returns_default(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test parse_enabled_formats returns defaults for empty string.

        Tests: Empty string handling
        How: Set MCP_CONFIG_FORMATS to empty string
        Why: Verify empty configuration falls back to defaults
        """
        # Arrange - set empty string
        monkeypatch.setenv("MCP_CONFIG_FORMATS", "")

        # Act - parse enabled formats
        result = parse_enabled_formats()

        # Assert - returns defaults
        assert result == list(DEFAULT_FORMATS)

    def test_parse_enabled_formats_partial_valid(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test parse_enabled_formats with mix of valid and invalid formats.

        Tests: Partial validation
        How: Set MCP_CONFIG_FORMATS with some valid and some invalid
        Why: Verify valid formats are parsed, invalid ones ignored
        """
        # Arrange - set mix of valid and invalid
        monkeypatch.setenv("MCP_CONFIG_FORMATS", "json,invalid,yaml,badformat")

        # Act - parse enabled formats
        result = parse_enabled_formats()

        # Assert - returns only valid formats
        assert len(result) == 2
        assert ConfigFormat.JSON in result
        assert ConfigFormat.YAML in result


class TestIsFormatEnabled:
    """Test is_format_enabled function."""

    def test_is_format_enabled_default_json(self, clean_environment: None) -> None:
        """Test is_format_enabled returns True for default formats.

        Tests: Default format checking
        How: Check if JSON is enabled with default config
        Why: Verify default formats are enabled
        """
        # Arrange - clean environment
        # Act - check if json enabled
        result = is_format_enabled("json")

        # Assert - json is enabled by default
        assert result is True

    def test_is_format_enabled_default_yaml(self, clean_environment: None) -> None:
        """Test YAML is enabled by default.

        Tests: Default YAML support
        How: Check is_format_enabled for yaml
        Why: Verify YAML in default formats
        """
        # Arrange - clean environment
        # Act - check yaml
        result = is_format_enabled("yaml")

        # Assert - yaml enabled
        assert result is True

    def test_is_format_enabled_default_toml(self, clean_environment: None) -> None:
        """Test TOML is enabled by default.

        Tests: Default TOML support
        How: Check is_format_enabled for toml
        Why: Verify TOML in default formats
        """
        # Arrange - clean environment
        # Act - check toml
        result = is_format_enabled("toml")

        # Assert - toml enabled
        assert result is True

    def test_is_format_enabled_xml_not_default(self, clean_environment: None) -> None:
        """Test XML is not enabled by default.

        Tests: Non-default format exclusion
        How: Check is_format_enabled for xml
        Why: Verify XML not in defaults
        """
        # Arrange - clean environment
        # Act - check xml
        result = is_format_enabled("xml")

        # Assert - xml not enabled
        assert result is False

    def test_is_format_enabled_case_insensitive(self, clean_environment: None) -> None:
        """Test is_format_enabled is case-insensitive.

        Tests: Case-insensitive format checking
        How: Check various case variations
        Why: Ensure user-friendly API
        """
        # Arrange - clean environment
        # Act - check different cases
        # Assert - all variations work
        assert is_format_enabled("JSON") is True
        assert is_format_enabled("Json") is True
        assert is_format_enabled("json") is True
        assert is_format_enabled("YAML") is True

    def test_is_format_enabled_respects_env_config(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test is_format_enabled respects environment configuration.

        Tests: Environment-based filtering
        How: Set MCP_CONFIG_FORMATS and check format
        Why: Verify environment controls format availability
        """
        # Arrange - enable only json
        monkeypatch.setenv("MCP_CONFIG_FORMATS", "json")

        # Act - check formats
        json_enabled = is_format_enabled("json")
        yaml_enabled = is_format_enabled("yaml")

        # Assert - only json enabled
        assert json_enabled is True
        assert yaml_enabled is False


class TestValidateFormat:
    """Test validate_format function."""

    def test_validate_format_valid_json(self) -> None:
        """Test validate_format accepts valid JSON format.

        Tests: Valid format validation
        How: Call validate_format with 'json'
        Why: Verify valid formats are accepted
        """
        # Arrange - valid format string
        # Act - validate format
        result = validate_format("json")

        # Assert - returns ConfigFormat enum
        assert result == ConfigFormat.JSON
        assert isinstance(result, ConfigFormat)

    def test_validate_format_valid_yaml(self) -> None:
        """Test validate_format accepts valid YAML format.

        Tests: YAML validation
        How: Call validate_format with 'yaml'
        Why: Verify YAML is valid format
        """
        # Arrange - yaml format
        # Act - validate
        result = validate_format("yaml")

        # Assert - returns YAML enum
        assert result == ConfigFormat.YAML

    def test_validate_format_valid_toml(self) -> None:
        """Test validate_format accepts valid TOML format.

        Tests: TOML validation
        How: Call validate_format with 'toml'
        Why: Verify TOML is valid format
        """
        # Arrange - toml format
        # Act - validate
        result = validate_format("toml")

        # Assert - returns TOML enum
        assert result == ConfigFormat.TOML

    def test_validate_format_valid_xml(self) -> None:
        """Test validate_format accepts valid XML format.

        Tests: XML validation
        How: Call validate_format with 'xml'
        Why: Verify XML is valid format
        """
        # Arrange - xml format
        # Act - validate
        result = validate_format("xml")

        # Assert - returns XML enum
        assert result == ConfigFormat.XML

    def test_validate_format_case_insensitive(self) -> None:
        """Test validate_format is case-insensitive.

        Tests: Case-insensitive validation
        How: Validate mixed-case format strings
        Why: Ensure user-friendly validation
        """
        # Arrange - mixed case formats
        # Act - validate each
        # Assert - all work
        assert validate_format("JSON") == ConfigFormat.JSON
        assert validate_format("Json") == ConfigFormat.JSON
        assert validate_format("YAML") == ConfigFormat.YAML
        assert validate_format("Yaml") == ConfigFormat.YAML

    def test_validate_format_invalid_raises_valueerror(self) -> None:
        """Test validate_format raises ValueError for invalid format.

        Tests: Invalid format rejection
        How: Call validate_format with invalid string
        Why: Ensure validation catches bad input
        """
        # Arrange - invalid format
        # Act & Assert - raises ValueError
        with pytest.raises(ValueError, match="Invalid format 'invalid'"):
            validate_format("invalid")

    def test_validate_format_invalid_error_message(self) -> None:
        """Test validate_format error message includes valid formats.

        Tests: Error message quality
        How: Catch ValueError and check message
        Why: Ensure helpful error messages for users
        """
        # Arrange - invalid format
        # Act & Assert - check error message
        with pytest.raises(ValueError) as exc_info:
            validate_format("badformat")

        error_msg = str(exc_info.value)
        assert "Invalid format 'badformat'" in error_msg
        assert "Valid formats:" in error_msg
        assert "json" in error_msg
        assert "yaml" in error_msg
        assert "toml" in error_msg
        assert "xml" in error_msg


class TestGetEnabledFormatsStr:
    """Test get_enabled_formats_str function."""

    def test_get_enabled_formats_str_default(self, clean_environment: None) -> None:
        """Test get_enabled_formats_str returns default formats as string.

        Tests: Default formats string representation
        How: Call get_enabled_formats_str with default config
        Why: Verify string representation of defaults
        """
        # Arrange - clean environment
        # Act - get formats string
        result = get_enabled_formats_str()

        # Assert - returns comma-separated default formats
        assert result == "json,yaml,toml"

    def test_get_enabled_formats_str_custom(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test get_enabled_formats_str with custom configuration.

        Tests: Custom format string representation
        How: Set MCP_CONFIG_FORMATS and get string
        Why: Verify string representation matches config
        """
        # Arrange - set custom formats
        monkeypatch.setenv("MCP_CONFIG_FORMATS", "yaml,xml")

        # Act - get formats string
        result = get_enabled_formats_str()

        # Assert - returns configured formats
        assert result == "yaml,xml"

    def test_get_enabled_formats_str_single_format(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test get_enabled_formats_str with single format.

        Tests: Single format string representation
        How: Set single format and get string
        Why: Verify single format string handling
        """
        # Arrange - set single format
        monkeypatch.setenv("MCP_CONFIG_FORMATS", "json")

        # Act - get formats string
        result = get_enabled_formats_str()

        # Assert - returns single format
        assert result == "json"

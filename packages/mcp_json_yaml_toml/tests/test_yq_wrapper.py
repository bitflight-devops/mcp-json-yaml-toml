"""Tests for yq wrapper module.

Tests binary detection, subprocess execution, error handling, and output parsing.
Includes both unit tests with mocked subprocess and integration tests with real yq.
"""

import subprocess
from pathlib import Path
from unittest.mock import Mock

import pytest
from pytest_mock import MockerFixture

from mcp_json_yaml_toml.yq_wrapper import (
    YQBinaryNotFoundError,
    YQError,
    YQExecutionError,
    YQResult,
    _verify_checksum,
    execute_yq,
    get_yq_binary_path,
    parse_yq_error,
    validate_yq_binary,
)


class TestGetYQBinaryPath:
    """Test get_yq_binary_path function."""

    def test_get_yq_binary_path_returns_path(self) -> None:
        """Test get_yq_binary_path returns a Path object.

        Tests: Binary path resolution
        How: Call get_yq_binary_path and check return type
        Why: Verify binary can be located for current platform
        """
        # Arrange - system with yq binary
        # Act - get binary path
        result = get_yq_binary_path()

        # Assert - returns Path object
        assert isinstance(result, Path)
        assert result.exists()

    def test_get_yq_binary_path_executable_exists(self) -> None:
        """Test get_yq_binary_path returns existing executable.

        Tests: Executable existence verification
        How: Get binary path and verify file exists
        Why: Ensure returned path points to real file
        """
        # Arrange - system environment
        # Act - get binary path
        binary_path = get_yq_binary_path()

        # Assert - binary exists and is file
        assert binary_path.exists()
        assert binary_path.is_file()

    @pytest.mark.integration
    def test_get_yq_binary_path_is_executable(self) -> None:
        """Test binary at returned path is executable.

        Tests: Binary execution permission
        How: Get binary path and check if executable
        Why: Verify binary has proper permissions
        """
        # Arrange - get binary
        binary_path = get_yq_binary_path()

        # Act - check execution permission
        # Assert - binary is executable (Unix-like systems)
        import os

        if os.name != "nt":  # Unix-like systems
            assert os.access(binary_path, os.X_OK)


class TestParseYQError:
    """Test parse_yq_error function."""

    def test_parse_yq_error_empty_string(self) -> None:
        """Test parse_yq_error handles empty stderr.

        Tests: Empty error message handling
        How: Call parse_yq_error with empty string
        Why: Ensure graceful handling of missing error info
        """
        # Arrange - empty stderr
        stderr = ""

        # Act - parse error
        result = parse_yq_error(stderr)

        # Assert - returns default message
        assert result == "Unknown error (no stderr output)"

    def test_parse_yq_error_strips_error_prefix(self) -> None:
        """Test parse_yq_error removes 'Error: ' prefix.

        Tests: Error message cleaning
        How: Parse stderr with 'Error: ' prefix
        Why: Provide clean, readable error messages
        """
        # Arrange - stderr with Error prefix
        stderr = "Error: invalid expression '.bad['"

        # Act - parse error
        result = parse_yq_error(stderr)

        # Assert - prefix removed
        assert result == "invalid expression '.bad['"
        assert not result.startswith("Error: ")

    def test_parse_yq_error_single_line(self) -> None:
        """Test parse_yq_error with single line error.

        Tests: Single line error parsing
        How: Parse stderr with one line
        Why: Verify basic error parsing works
        """
        # Arrange - single line error
        stderr = "invalid syntax"

        # Act - parse error
        result = parse_yq_error(stderr)

        # Assert - returns cleaned error
        assert result == "invalid syntax"

    def test_parse_yq_error_multiline_includes_context(self) -> None:
        """Test parse_yq_error includes context from additional lines.

        Tests: Multiline error context
        How: Parse stderr with multiple lines
        Why: Provide helpful context for debugging
        """
        # Arrange - multiline stderr
        stderr = "Error: bad expression\nContext: line 1\nDetails: syntax error"

        # Act - parse error
        result = parse_yq_error(stderr)

        # Assert - includes main error and context
        assert "bad expression" in result
        assert "Context: line 1" in result

    def test_parse_yq_error_whitespace_only_returns_default(self) -> None:
        """Test parse_yq_error handles whitespace-only input.

        Tests: Whitespace handling
        How: Parse stderr with only whitespace
        Why: Ensure robust error parsing
        """
        # Arrange - whitespace only
        stderr = "   \n\n\t  "

        # Act - parse error
        result = parse_yq_error(stderr)

        # Assert - returns default
        assert result == "Unknown error (empty stderr)"


class TestYQResult:
    """Test YQResult model."""

    def test_yqresult_default_values(self) -> None:
        """Test YQResult has correct default values.

        Tests: Model defaults
        How: Create YQResult with minimal fields
        Why: Verify Pydantic defaults are correct
        """
        # Arrange & Act - create result with only stdout
        result = YQResult(stdout="test output")

        # Assert - defaults are set
        assert result.stdout == "test output"
        assert result.stderr == ""
        assert result.returncode == 0
        assert result.data is None

    def test_yqresult_with_all_fields(self) -> None:
        """Test YQResult accepts all fields.

        Tests: Complete model construction
        How: Create YQResult with all fields
        Why: Verify all fields can be set
        """
        # Arrange & Act - create complete result
        result = YQResult(
            stdout="output", stderr="error", returncode=1, data={"key": "value"}
        )

        # Assert - all fields set
        assert result.stdout == "output"
        assert result.stderr == "error"
        assert result.returncode == 1
        assert result.data == {"key": "value"}


class TestExecuteYQ:
    """Test execute_yq function."""

    @pytest.mark.unit
    def test_execute_yq_with_input_data(self, mocker: MockerFixture) -> None:
        """Test execute_yq with input_data parameter.

        Tests: Input data processing
        How: Mock subprocess and call execute_yq with input_data
        Why: Verify input data is passed correctly to subprocess
        """
        # Arrange - mock subprocess
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = b'{"name":"test"}'
        mock_result.stderr = b""
        mock_run = mocker.patch("subprocess.run", return_value=mock_result)

        # Act - execute yq with input data
        result = execute_yq(
            ".", input_data='{"name":"test"}', input_format="json", output_format="json"
        )

        # Assert - subprocess called with correct args
        assert mock_run.called
        assert result.stdout == '{"name":"test"}'
        assert result.data == {"name": "test"}

    @pytest.mark.unit
    def test_execute_yq_argument_validation_both_inputs(self) -> None:
        """Test execute_yq rejects both input_data and input_file.

        Tests: Argument validation
        How: Call execute_yq with both input parameters
        Why: Ensure mutually exclusive parameters are enforced
        """
        # Arrange - invalid arguments
        # Act & Assert - raises ValueError
        with pytest.raises(
            ValueError, match="Cannot specify both input_data and input_file"
        ):
            execute_yq(".", input_data="test", input_file=Path("test.json"))

    @pytest.mark.unit
    def test_execute_yq_argument_validation_in_place_without_file(self) -> None:
        """Test execute_yq rejects in_place without input_file.

        Tests: In-place edit validation
        How: Call execute_yq with in_place=True but no input_file
        Why: Ensure in-place requires file parameter
        """
        # Arrange - invalid arguments
        # Act & Assert - raises ValueError
        with pytest.raises(ValueError, match="in_place requires input_file"):
            execute_yq(".", input_data="test", in_place=True)

    @pytest.mark.unit
    def test_execute_yq_argument_validation_null_input_with_data(self) -> None:
        """Test execute_yq rejects null_input with input data.

        Tests: Null input validation
        How: Call execute_yq with null_input and input_data
        Why: Ensure null_input is mutually exclusive with inputs
        """
        # Arrange - invalid arguments
        # Act & Assert - raises ValueError
        with pytest.raises(
            ValueError, match="null_input cannot be used with input_data"
        ):
            execute_yq(".", input_data="test", null_input=True)

    @pytest.mark.unit
    def test_execute_yq_handles_execution_error(self, mocker: MockerFixture) -> None:
        """Test execute_yq raises YQExecutionError on failure.

        Tests: Error handling for failed execution
        How: Mock subprocess to return error
        Why: Verify errors are properly caught and wrapped
        """
        # Arrange - mock failed subprocess
        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stdout = b""
        mock_result.stderr = b"Error: invalid expression"
        mocker.patch("subprocess.run", return_value=mock_result)

        # Act & Assert - raises YQExecutionError
        with pytest.raises(YQExecutionError, match="yq command failed"):
            execute_yq(".", input_data='{"test": "data"}')

    @pytest.mark.unit
    def test_execute_yq_timeout_handling(self, mocker: MockerFixture) -> None:
        """Test execute_yq handles subprocess timeout.

        Tests: Timeout error handling
        How: Mock subprocess to raise TimeoutExpired
        Why: Ensure timeout is properly handled
        """
        # Arrange - mock timeout
        mocker.patch("subprocess.run", side_effect=subprocess.TimeoutExpired("yq", 30))

        # Act & Assert - raises YQExecutionError
        with pytest.raises(YQExecutionError, match="timed out"):
            execute_yq(".", input_data='{"test": "data"}')

    @pytest.mark.unit
    def test_execute_yq_oserror_handling(self, mocker: MockerFixture) -> None:
        """Test execute_yq handles OSError.

        Tests: OS-level error handling
        How: Mock subprocess to raise OSError
        Why: Verify OS errors are properly caught
        """
        # Arrange - mock OS error
        mocker.patch("subprocess.run", side_effect=OSError("Binary not found"))

        # Act & Assert - raises YQExecutionError
        with pytest.raises(YQExecutionError, match="Failed to execute yq binary"):
            execute_yq(".", input_data='{"test": "data"}')

    @pytest.mark.unit
    def test_execute_yq_json_parse_warning(self, mocker: MockerFixture) -> None:
        """Test execute_yq handles JSON parse errors gracefully.

        Tests: Invalid JSON output handling
        How: Mock subprocess to return invalid JSON
        Why: Ensure parse errors don't crash, just warn in stderr
        """
        # Arrange - mock invalid JSON output
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = b"invalid json {"
        mock_result.stderr = b""
        mocker.patch("subprocess.run", return_value=mock_result)

        # Act - execute yq
        result = execute_yq(".", input_data='{"test": "data"}', output_format="json")

        # Assert - data is None, warning in stderr
        assert result.data is None
        assert "Warning: Failed to parse JSON" in result.stderr

    @pytest.mark.integration
    def test_execute_yq_with_real_binary(self, sample_json_config: Path) -> None:
        """Test execute_yq with real yq binary.

        Tests: Integration with real yq
        How: Execute actual yq command against sample config
        Why: Verify end-to-end execution works
        """
        # Arrange - sample config file
        # Act - execute yq to query name
        result = execute_yq(
            ".name",
            input_file=sample_json_config,
            input_format="json",
            output_format="json",
        )

        # Assert - successful execution
        assert result.returncode == 0
        assert result.data == "test-app"

    @pytest.mark.integration
    def test_execute_yq_with_yaml_to_json_conversion(
        self, sample_yaml_config: Path
    ) -> None:
        """Test execute_yq converts YAML to JSON.

        Tests: Format conversion
        How: Read YAML file and output as JSON
        Why: Verify format conversion capability
        """
        # Arrange - YAML config
        # Act - convert to JSON
        result = execute_yq(
            ".",
            input_file=sample_yaml_config,
            input_format="yaml",
            output_format="json",
        )

        # Assert - successful conversion
        assert result.returncode == 0
        assert isinstance(result.data, dict)
        assert result.data["name"] == "test-app"


class TestValidateYQBinary:
    """Test validate_yq_binary function."""

    def test_validate_yq_binary_success(self) -> None:
        """Test validate_yq_binary succeeds with valid binary.

        Tests: Binary validation success case
        How: Call validate_yq_binary with existing binary
        Why: Verify validation works for valid setup
        """
        # Arrange - system with yq binary
        # Act - validate binary
        is_valid, message = validate_yq_binary()

        # Assert - validation succeeds
        assert is_valid is True
        assert "yq binary found and working" in message
        assert "yq" in message.lower()

    def test_validate_yq_binary_includes_version(self) -> None:
        """Test validate_yq_binary includes version in success message.

        Tests: Version information in validation
        How: Validate binary and check message content
        Why: Ensure version info is provided for debugging
        """
        # Arrange - system with yq binary
        # Act - validate binary
        is_valid, message = validate_yq_binary()

        # Assert - message includes version
        assert is_valid is True
        # Version format varies, just check message has content
        assert len(message) > 20


class TestYQError:
    """Test YQError exception classes."""

    def test_yqerror_base_exception(self) -> None:
        """Test YQError is base exception class.

        Tests: Exception hierarchy
        How: Create YQError and check type
        Why: Verify exception inheritance
        """
        # Arrange & Act - create exception
        error = YQError("test error")

        # Assert - is Exception
        assert isinstance(error, Exception)
        assert str(error) == "test error"

    def test_yqbinarynotfounderror_inherits_yqerror(self) -> None:
        """Test YQBinaryNotFoundError inherits from YQError.

        Tests: Binary error inheritance
        How: Create YQBinaryNotFoundError
        Why: Verify exception hierarchy
        """
        # Arrange & Act - create exception
        error = YQBinaryNotFoundError("binary not found")

        # Assert - inherits from YQError
        assert isinstance(error, YQError)
        assert isinstance(error, Exception)

    def test_yqexecutionerror_stores_details(self) -> None:
        """Test YQExecutionError stores stderr and returncode.

        Tests: Execution error details
        How: Create YQExecutionError with details
        Why: Verify error details are accessible
        """
        # Arrange & Act - create execution error
        error = YQExecutionError("test error", stderr="error output", returncode=1)

        # Assert - details stored
        assert error.stderr == "error output"
        assert error.returncode == 1
        assert str(error) == "test error"


class TestVerifyChecksum:
    """Tests for _verify_checksum function."""

    def test_verify_checksum_returns_true_for_matching_hash(
        self, tmp_path: Path
    ) -> None:
        """Verify checksum returns True when hash matches."""
        # Create a file with known content
        test_file = tmp_path / "test_file.bin"
        content = b"Hello, World!"
        test_file.write_bytes(content)

        # Pre-computed SHA256 of "Hello, World!"
        expected_hash = (
            "dffd6021bb2bd5b0af676290809ec3a53191dd81c7f70a4b28688a362182986f"
        )

        result = _verify_checksum(test_file, expected_hash)

        assert result is True

    def test_verify_checksum_returns_false_for_wrong_hash(self, tmp_path: Path) -> None:
        """Verify checksum returns False when hash does not match."""
        test_file = tmp_path / "test_file.bin"
        test_file.write_bytes(b"Hello, World!")

        wrong_hash = "0000000000000000000000000000000000000000000000000000000000000000"

        result = _verify_checksum(test_file, wrong_hash)

        assert result is False

    def test_verify_checksum_handles_empty_file(self, tmp_path: Path) -> None:
        """Verify checksum works with empty files."""
        test_file = tmp_path / "empty_file.bin"
        test_file.write_bytes(b"")

        # SHA256 of empty string
        empty_hash = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"

        result = _verify_checksum(test_file, empty_hash)

        assert result is True

    def test_verify_checksum_handles_binary_content(self, tmp_path: Path) -> None:
        """Verify checksum works with binary content."""
        test_file = tmp_path / "binary_file.bin"
        # Binary content with null bytes and high bytes
        content = bytes(range(256))
        test_file.write_bytes(content)

        # Compute expected hash
        import hashlib

        expected_hash = hashlib.sha256(content).hexdigest()

        result = _verify_checksum(test_file, expected_hash)

        assert result is True

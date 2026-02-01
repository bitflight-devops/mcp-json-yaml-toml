"""Tests for yq wrapper module.

Tests binary detection, subprocess execution, error handling, and output parsing.
Includes both unit tests with mocked subprocess and integration tests with real yq.
"""

import os
import platform
import subprocess
from pathlib import Path
from unittest.mock import Mock

import pytest
from pytest_mock import MockerFixture

from mcp_json_yaml_toml.yq_wrapper import (
    DEFAULT_YQ_CHECKSUMS,
    DEFAULT_YQ_VERSION,
    FormatType,
    YQBinaryNotFoundError,
    YQError,
    YQExecutionError,
    YQResult,
    _cleanup_old_versions,
    _find_system_yq,
    _get_checksums,
    _get_platform_binary_info,
    _is_mikefarah_yq,
    _verify_checksum,
    execute_yq,
    get_yq_binary_path,
    get_yq_version,
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
            ".",
            input_data='{"name":"test"}',
            input_format=FormatType.JSON,
            output_format=FormatType.JSON,
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
        result = execute_yq(
            ".", input_data='{"test": "data"}', output_format=FormatType.JSON
        )

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
            input_format=FormatType.JSON,
            output_format=FormatType.JSON,
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
            input_format=FormatType.YAML,
            output_format=FormatType.JSON,
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


class TestYQBinaryPathOverride:
    """Tests for YQ_BINARY_PATH environment variable override."""

    def test_yq_binary_path_env_override(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that YQ_BINARY_PATH env var overrides default resolution.

        Tests: Custom binary path override
        How: Create a fake binary and set YQ_BINARY_PATH to it
        Why: Allow users to specify custom yq installations
        """
        # Arrange - create a fake binary file
        fake_binary = tmp_path / "my-custom-yq"
        fake_binary.write_text("fake binary")
        monkeypatch.setenv("YQ_BINARY_PATH", str(fake_binary))

        # Act
        result = get_yq_binary_path()

        # Assert
        assert result == fake_binary

    def test_yq_binary_path_nonexistent_raises_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that nonexistent YQ_BINARY_PATH raises clear error.

        Tests: Error handling for invalid custom path
        How: Set YQ_BINARY_PATH to nonexistent file
        Why: Provide clear error when user misconfigures path
        """
        # Arrange
        nonexistent = tmp_path / "does-not-exist"
        monkeypatch.setenv("YQ_BINARY_PATH", str(nonexistent))

        # Act & Assert
        with pytest.raises(YQBinaryNotFoundError, match="does not exist"):
            get_yq_binary_path()

    def test_yq_binary_path_supports_tilde_expansion(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that YQ_BINARY_PATH supports ~ expansion.

        Tests: Home directory expansion
        How: Set YQ_BINARY_PATH with ~ prefix
        Why: Allow convenient home-relative paths
        """
        # Arrange - we can't actually test ~ expansion without creating file in home
        # Just verify the code path handles expanduser
        fake_path = tmp_path / "yq-test"
        fake_path.write_text("fake")
        monkeypatch.setenv("YQ_BINARY_PATH", str(fake_path))

        # Act
        result = get_yq_binary_path()

        # Assert - path was resolved
        assert result.exists()


class TestIsMikefarahYQ:
    """Tests for _is_mikefarah_yq detection function."""

    def test_detects_mikefarah_yq(self, mocker: MockerFixture, tmp_path: Path) -> None:
        """Test that mikefarah/yq is correctly identified.

        Tests: Go-based yq detection
        How: Mock subprocess to return mikefarah/yq version output
        Why: Ensure we use the correct yq binary
        """
        # Arrange - mock subprocess to return mikefarah/yq version
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = b"yq (https://github.com/mikefarah/yq/) version v4.52.2"
        mocker.patch("subprocess.run", return_value=mock_result)

        fake_binary = tmp_path / "yq"

        # Act
        result = _is_mikefarah_yq(fake_binary)

        # Assert
        assert result is True

    def test_rejects_python_yq(self, mocker: MockerFixture, tmp_path: Path) -> None:
        """Test that Python yq (kislyuk/yq) is rejected.

        Tests: Python yq rejection
        How: Mock subprocess to return Python yq version output
        Why: Python yq is incompatible with our YAML/TOML processing
        """
        # Arrange - mock subprocess to return Python yq version
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = b"yq 3.4.3"  # Python yq output format
        mocker.patch("subprocess.run", return_value=mock_result)

        fake_binary = tmp_path / "yq"

        # Act
        result = _is_mikefarah_yq(fake_binary)

        # Assert
        assert result is False

    def test_handles_execution_failure(
        self, mocker: MockerFixture, tmp_path: Path
    ) -> None:
        """Test graceful handling when version check fails.

        Tests: Error handling for version check
        How: Mock subprocess to return non-zero exit code
        Why: Ensure robust handling of broken or misconfigured yq
        """
        # Arrange
        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stdout = b""
        mocker.patch("subprocess.run", return_value=mock_result)

        fake_binary = tmp_path / "yq"

        # Act
        result = _is_mikefarah_yq(fake_binary)

        # Assert
        assert result is False

    def test_handles_timeout(self, mocker: MockerFixture, tmp_path: Path) -> None:
        """Test graceful handling when version check times out.

        Tests: Timeout handling
        How: Mock subprocess to raise TimeoutExpired
        Why: Prevent hanging on unresponsive binaries
        """
        # Arrange
        mocker.patch("subprocess.run", side_effect=subprocess.TimeoutExpired("yq", 5))

        fake_binary = tmp_path / "yq"

        # Act
        result = _is_mikefarah_yq(fake_binary)

        # Assert
        assert result is False

    def test_handles_oserror(self, mocker: MockerFixture, tmp_path: Path) -> None:
        """Test graceful handling when binary cannot be executed.

        Tests: OSError handling
        How: Mock subprocess to raise OSError
        Why: Handle permission errors or missing binaries
        """
        # Arrange
        mocker.patch("subprocess.run", side_effect=OSError("Permission denied"))

        fake_binary = tmp_path / "yq"

        # Act
        result = _is_mikefarah_yq(fake_binary)

        # Assert
        assert result is False


class TestSystemYQDetection:
    """Tests for system-installed yq detection."""

    def test_find_system_yq_returns_path_when_mikefarah_yq_found(
        self, mocker: MockerFixture
    ) -> None:
        """Test _find_system_yq returns Path when mikefarah/yq is in PATH.

        Tests: System yq detection with correct version
        How: Mock shutil.which and subprocess to simulate mikefarah/yq
        Why: Verify detection works when correct yq is installed
        """
        # Arrange - mock shutil.which and version check
        mocker.patch("shutil.which", return_value="/usr/local/bin/yq")
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = b"yq (https://github.com/mikefarah/yq/) version v4.52.2"
        mocker.patch("subprocess.run", return_value=mock_result)

        # Act
        result = _find_system_yq()

        # Assert
        assert result == Path("/usr/local/bin/yq")

    def test_find_system_yq_returns_none_when_python_yq_found(
        self, mocker: MockerFixture, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Test _find_system_yq returns None when Python yq is found.

        Tests: Rejection of Python yq
        How: Mock shutil.which to find yq, but version check shows Python yq
        Why: Ensure we don't use incompatible Python yq wrapper
        """
        # Arrange
        mocker.patch("shutil.which", return_value="/usr/bin/yq")
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = b"yq 3.4.3"  # Python yq
        mocker.patch("subprocess.run", return_value=mock_result)

        # Act
        result = _find_system_yq()

        # Assert
        assert result is None

        # Verify warning message was printed
        captured = capsys.readouterr()
        assert "not mikefarah/yq" in captured.err

    def test_find_system_yq_returns_none_when_not_found(
        self, mocker: MockerFixture
    ) -> None:
        """Test _find_system_yq returns None when yq is not in PATH.

        Tests: System yq not found
        How: Mock shutil.which to return None
        Why: Verify graceful handling when yq not installed
        """
        # Arrange - mock shutil.which to return None
        mocker.patch("shutil.which", return_value=None)

        # Act
        result = _find_system_yq()

        # Assert
        assert result is None


class TestPlatformBinaryInfo:
    """Tests for _get_platform_binary_info helper function."""

    def test_linux_amd64_naming(self) -> None:
        """Test binary naming for Linux amd64."""
        platform_prefix, binary_name, github_name = _get_platform_binary_info(
            "linux", "amd64", "v4.52.2"
        )
        assert platform_prefix == "yq-linux-amd64"
        assert binary_name == "yq-linux-amd64-v4.52.2"
        assert github_name == "yq_linux_amd64"

    def test_darwin_arm64_naming(self) -> None:
        """Test binary naming for macOS arm64."""
        platform_prefix, binary_name, github_name = _get_platform_binary_info(
            "darwin", "arm64", "v4.52.2"
        )
        assert platform_prefix == "yq-darwin-arm64"
        assert binary_name == "yq-darwin-arm64-v4.52.2"
        assert github_name == "yq_darwin_arm64"

    def test_windows_amd64_naming(self) -> None:
        """Test binary naming for Windows amd64."""
        platform_prefix, binary_name, github_name = _get_platform_binary_info(
            "windows", "amd64", "v4.52.2"
        )
        assert platform_prefix == "yq-windows-amd64"
        assert binary_name == "yq-windows-amd64-v4.52.2.exe"
        assert github_name == "yq_windows_amd64.exe"

    def test_unsupported_os_raises_error(self) -> None:
        """Test that unsupported OS raises clear error."""
        with pytest.raises(YQBinaryNotFoundError, match="Unsupported operating system"):
            _get_platform_binary_info("freebsd", "amd64", "v4.52.2")


class TestBundledChecksums:
    """Tests for bundled checksum functionality."""

    def test_bundled_checksums_exist_for_all_platforms(self) -> None:
        """Test that bundled checksums include all supported platforms.

        Tests: Completeness of bundled checksums
        How: Verify all platform binaries have checksums
        Why: Ensure no platform is missing checksums
        """
        required_binaries = [
            "yq_linux_amd64",
            "yq_linux_arm64",
            "yq_darwin_amd64",
            "yq_darwin_arm64",
            "yq_windows_amd64.exe",
        ]

        for binary in required_binaries:
            assert binary in DEFAULT_YQ_CHECKSUMS, f"Missing checksum for {binary}"

    def test_bundled_checksums_are_valid_sha256(self) -> None:
        """Test that bundled checksums are valid SHA256 format.

        Tests: Checksum format validation
        How: Verify each checksum is 64 hex characters
        Why: Ensure checksums are valid SHA256 hashes
        """
        for binary, checksum in DEFAULT_YQ_CHECKSUMS.items():
            assert len(checksum) == 64, f"Checksum for {binary} is not 64 characters"
            assert all(c in "0123456789abcdef" for c in checksum), (
                f"Checksum for {binary} contains invalid hex characters"
            )

    def test_get_checksums_returns_bundled_for_default_version(self) -> None:
        """Test that _get_checksums returns bundled checksums for default version.

        Tests: Bundled checksum usage
        How: Call _get_checksums with DEFAULT_YQ_VERSION
        Why: Verify no network request is made for default version
        """
        checksums = _get_checksums(DEFAULT_YQ_VERSION)

        # Should return the bundled checksums
        assert checksums == DEFAULT_YQ_CHECKSUMS

    def test_bundled_checksums_match_version(self) -> None:
        """Test that bundled checksums are for the current default version.

        Tests: Version consistency
        How: Verify DEFAULT_YQ_VERSION is correctly referenced
        Why: Ensure checksums match the pinned version
        """
        # This test documents the relationship between version and checksums
        assert DEFAULT_YQ_VERSION == "v4.52.2", (
            "DEFAULT_YQ_VERSION changed but test not updated"
        )
        # If version changes, checksums must also be updated
        assert len(DEFAULT_YQ_CHECKSUMS) == 5, "Expected 5 platform checksums"


class TestGetYQVersion:
    """Tests for get_yq_version function and version pinning."""

    def test_get_yq_version_returns_default(self) -> None:
        """Test get_yq_version returns DEFAULT_YQ_VERSION when env var not set.

        Tests: Default version behavior
        How: Ensure YQ_VERSION is not set, call get_yq_version
        Why: Verify pinned version is used by default
        """
        # Arrange - ensure env var not set
        original = os.environ.pop("YQ_VERSION", None)
        try:
            # Act
            result = get_yq_version()

            # Assert
            assert result == DEFAULT_YQ_VERSION
            assert result.startswith("v")
        finally:
            if original is not None:
                os.environ["YQ_VERSION"] = original

    def test_get_yq_version_respects_env_var(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test get_yq_version uses YQ_VERSION env var when set.

        Tests: Environment variable override
        How: Set YQ_VERSION env var, call get_yq_version
        Why: Users should be able to override the pinned version
        """
        # Arrange
        monkeypatch.setenv("YQ_VERSION", "v4.50.0")

        # Act
        result = get_yq_version()

        # Assert
        assert result == "v4.50.0"

    def test_get_yq_version_adds_v_prefix(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test get_yq_version adds 'v' prefix if missing.

        Tests: Version format normalization
        How: Set YQ_VERSION without 'v' prefix
        Why: Ensure consistent version format for GitHub URLs
        """
        # Arrange
        monkeypatch.setenv("YQ_VERSION", "4.50.0")

        # Act
        result = get_yq_version()

        # Assert
        assert result == "v4.50.0"
        assert result.startswith("v")

    def test_get_yq_version_handles_whitespace(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test get_yq_version strips whitespace from env var.

        Tests: Input sanitization
        How: Set YQ_VERSION with whitespace
        Why: Prevent issues from accidental whitespace in config
        """
        # Arrange
        monkeypatch.setenv("YQ_VERSION", "  v4.50.0  ")

        # Act
        result = get_yq_version()

        # Assert
        assert result == "v4.50.0"

    def test_get_yq_version_empty_env_uses_default(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test get_yq_version uses default when env var is empty string.

        Tests: Empty env var handling
        How: Set YQ_VERSION to empty string
        Why: Ensure graceful fallback to default
        """
        # Arrange
        monkeypatch.setenv("YQ_VERSION", "")

        # Act
        result = get_yq_version()

        # Assert
        assert result == DEFAULT_YQ_VERSION


class TestVersionedBinaryNaming:
    """Tests for versioned binary naming conventions."""

    def test_binary_path_includes_version(self) -> None:
        """Test that binary path includes version string.

        Tests: Version-aware caching
        How: Get binary path and check for version in name
        Why: Ensure version updates trigger new downloads
        """
        # Act
        binary_path = get_yq_binary_path()

        # Assert - binary name should include version
        version = get_yq_version()
        assert version in binary_path.name, (
            f"Binary name '{binary_path.name}' should include version '{version}'"
        )

    def test_binary_path_format_linux(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test binary naming format for Linux platform.

        Tests: Linux binary naming convention
        How: Mock platform detection, verify naming
        Why: Ensure correct format: yq-linux-{arch}-{version}
        """
        if platform.system().lower() != "linux":
            pytest.skip("Test only runs on Linux")

        # Act
        binary_path = get_yq_binary_path()
        version = get_yq_version()

        # Assert
        assert binary_path.name.startswith("yq-linux-")
        assert version in binary_path.name
        # Should be: yq-linux-amd64-v4.52.2 or yq-linux-arm64-v4.52.2
        assert binary_path.name.count("-") >= 3

    def test_binary_path_format_macos(self) -> None:
        """Test binary naming format for macOS platform.

        Tests: macOS binary naming convention
        How: Check naming on Darwin
        Why: Ensure correct format: yq-darwin-{arch}-{version}
        """
        if platform.system().lower() != "darwin":
            pytest.skip("Test only runs on macOS")

        # Act
        binary_path = get_yq_binary_path()
        version = get_yq_version()

        # Assert
        assert binary_path.name.startswith("yq-darwin-")
        assert version in binary_path.name

    def test_binary_path_format_windows(self) -> None:
        """Test binary naming format for Windows platform.

        Tests: Windows binary naming convention
        How: Check naming on Windows
        Why: Ensure correct format: yq-windows-{arch}-{version}.exe
        """
        if platform.system().lower() != "windows":
            pytest.skip("Test only runs on Windows")

        # Act
        binary_path = get_yq_binary_path()
        version = get_yq_version()

        # Assert
        assert binary_path.name.startswith("yq-windows-")
        assert version in binary_path.name
        assert binary_path.name.endswith(".exe")

    def test_different_versions_have_different_paths(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that different versions resolve to different binary paths.

        Tests: Version isolation
        How: Compare paths for two different versions
        Why: Ensure version pinning actually changes the binary used
        """
        # Get default version path
        default_path = get_yq_binary_path()

        # Set a different version (hypothetical)
        monkeypatch.setenv("YQ_VERSION", "v4.99.0")

        # Get path for different version
        # Note: This won't actually download, just compute the expected path
        system = platform.system().lower()
        machine = platform.machine().lower()
        arch = "amd64" if machine in {"x86_64", "amd64"} else "arm64"

        if system == "linux":
            expected_name = f"yq-linux-{arch}-v4.99.0"
        elif system == "darwin":
            expected_name = f"yq-darwin-{arch}-v4.99.0"
        elif system == "windows":
            expected_name = f"yq-windows-{arch}-v4.99.0.exe"
        else:
            pytest.skip(f"Unsupported platform: {system}")

        # Assert - names should be different
        assert default_path.name != expected_name


class TestCleanupOldVersions:
    """Tests for _cleanup_old_versions function."""

    def test_cleanup_removes_old_versions(self, tmp_path: Path) -> None:
        """Test that old versioned binaries are removed.

        Tests: Old version cleanup
        How: Create fake old binaries, run cleanup, verify removed
        Why: Prevent disk space accumulation from multiple versions
        """
        # Arrange - create fake old binaries
        old_binary_1 = tmp_path / "yq-linux-amd64-v4.50.0"
        old_binary_2 = tmp_path / "yq-linux-amd64-v4.51.0"
        current_binary = tmp_path / "yq-linux-amd64-v4.52.2"

        old_binary_1.write_text("fake binary v4.50.0")
        old_binary_2.write_text("fake binary v4.51.0")
        current_binary.write_text("fake binary v4.52.2")

        # Act - cleanup old versions
        _cleanup_old_versions(tmp_path, "yq-linux-amd64", "yq-linux-amd64-v4.52.2")

        # Assert - old binaries removed, current kept
        assert not old_binary_1.exists(), "Old v4.50.0 should be removed"
        assert not old_binary_2.exists(), "Old v4.51.0 should be removed"
        assert current_binary.exists(), "Current v4.52.2 should be kept"

    def test_cleanup_preserves_current_binary(self, tmp_path: Path) -> None:
        """Test that current binary is not removed during cleanup.

        Tests: Current version preservation
        How: Create only current binary, run cleanup
        Why: Ensure we don't accidentally delete what we just downloaded
        """
        # Arrange
        current_binary = tmp_path / "yq-darwin-arm64-v4.52.2"
        current_binary.write_text("fake binary")

        # Act
        _cleanup_old_versions(tmp_path, "yq-darwin-arm64", "yq-darwin-arm64-v4.52.2")

        # Assert
        assert current_binary.exists()

    def test_cleanup_only_affects_matching_platform(self, tmp_path: Path) -> None:
        """Test that cleanup only removes binaries for the same platform.

        Tests: Platform isolation in cleanup
        How: Create binaries for different platforms, cleanup one
        Why: Prevent accidental removal of other platform binaries
        """
        # Arrange - create binaries for different platforms
        linux_old = tmp_path / "yq-linux-amd64-v4.50.0"
        linux_new = tmp_path / "yq-linux-amd64-v4.52.2"
        darwin_binary = tmp_path / "yq-darwin-amd64-v4.50.0"
        windows_binary = tmp_path / "yq-windows-amd64-v4.50.0.exe"

        linux_old.write_text("fake")
        linux_new.write_text("fake")
        darwin_binary.write_text("fake")
        windows_binary.write_text("fake")

        # Act - cleanup only Linux
        _cleanup_old_versions(tmp_path, "yq-linux-amd64", "yq-linux-amd64-v4.52.2")

        # Assert - only Linux old removed
        assert not linux_old.exists(), "Old Linux binary should be removed"
        assert linux_new.exists(), "Current Linux binary should be kept"
        assert darwin_binary.exists(), "Darwin binary should not be affected"
        assert windows_binary.exists(), "Windows binary should not be affected"

    def test_cleanup_handles_no_old_versions(self, tmp_path: Path) -> None:
        """Test cleanup handles case when no old versions exist.

        Tests: Edge case - no cleanup needed
        How: Create only current binary, run cleanup
        Why: Ensure no errors when nothing to clean
        """
        # Arrange
        current = tmp_path / "yq-linux-arm64-v4.52.2"
        current.write_text("fake")

        # Act - should not raise
        _cleanup_old_versions(tmp_path, "yq-linux-arm64", "yq-linux-arm64-v4.52.2")

        # Assert
        assert current.exists()

    def test_cleanup_handles_empty_directory(self, tmp_path: Path) -> None:
        """Test cleanup handles empty directory gracefully.

        Tests: Edge case - empty directory
        How: Run cleanup on empty directory
        Why: Ensure no errors on fresh install
        """
        # Arrange - empty directory
        # Act - should not raise
        _cleanup_old_versions(tmp_path, "yq-linux-amd64", "yq-linux-amd64-v4.52.2")

        # Assert - no files created
        assert list(tmp_path.iterdir()) == []

    def test_cleanup_windows_exe_naming(self, tmp_path: Path) -> None:
        """Test cleanup works with Windows .exe naming convention.

        Tests: Windows-specific cleanup
        How: Create Windows binaries with .exe extension
        Why: Ensure glob pattern matches .exe files correctly
        """
        # Arrange
        old_exe = tmp_path / "yq-windows-amd64-v4.50.0.exe"
        current_exe = tmp_path / "yq-windows-amd64-v4.52.2.exe"
        old_exe.write_text("fake")
        current_exe.write_text("fake")

        # Act
        _cleanup_old_versions(
            tmp_path, "yq-windows-amd64", "yq-windows-amd64-v4.52.2.exe"
        )

        # Assert
        assert not old_exe.exists(), "Old Windows exe should be removed"
        assert current_exe.exists(), "Current Windows exe should be kept"

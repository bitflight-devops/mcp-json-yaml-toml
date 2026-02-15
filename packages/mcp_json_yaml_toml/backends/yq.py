"""Query execution backend for yq.

Implements the YqBackend class (ARCH-04) and module-level execute_yq function
for subprocess-based query execution against YAML/JSON/TOML/XML data.
"""

from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING, Any

import orjson

from mcp_json_yaml_toml.backends.base import FormatType, YQExecutionError, YQResult
from mcp_json_yaml_toml.backends.binary_manager import (
    get_yq_binary_path,
    validate_yq_binary,
)

if TYPE_CHECKING:
    from pathlib import Path


def parse_yq_error(stderr: str) -> str:
    """Parse yq error message into AI-friendly format.

    Args:
        stderr: Raw stderr output from yq

    Returns:
        Cleaned, human-readable error message
    """
    if not stderr:
        return "Unknown error (no stderr output)"

    # yq error messages typically start with "Error: "
    lines = stderr.strip().split("\n")

    # Extract the main error message
    error_lines = [line for line in lines if line.strip()]

    if not error_lines:
        return "Unknown error (empty stderr)"

    # Clean up common yq error patterns
    main_error = error_lines[0]

    # Remove "Error: " prefix if present
    main_error = main_error.removeprefix("Error: ")

    # Add context from additional lines if helpful
    if len(error_lines) > 1:
        context = " | ".join(error_lines[1:3])  # Include up to 2 context lines
        return f"{main_error} ({context})"

    return main_error


def _validate_execute_args(
    input_data: str | None,
    input_file: Path | str | None,
    in_place: bool,
    null_input: bool,
) -> None:
    """Validate arguments for execute_yq.

    Args:
        input_data: Input data as string
        input_file: Path to input file
        in_place: Whether to modify file in place
        null_input: Whether to use null input

    Raises:
        ValueError: If arguments are invalid
    """
    if input_data is not None and input_file is not None:
        raise ValueError("Cannot specify both input_data and input_file")

    if in_place and input_file is None:
        raise ValueError("in_place requires input_file to be specified")

    if null_input and (input_data is not None or input_file is not None):
        raise ValueError("null_input cannot be used with input_data or input_file")


def _build_yq_command(
    binary_path: Path,
    expression: str,
    input_file: Path | str | None,
    input_format: FormatType,
    output_format: FormatType,
    in_place: bool,
    null_input: bool,
) -> list[str]:
    """Build yq command arguments.

    Args:
        binary_path: Path to yq binary
        expression: yq expression to evaluate
        input_file: Path to input file (if any)
        input_format: Format of input data
        output_format: Format for output
        in_place: Modify file in place
        null_input: Don't read input

    Returns:
        List of command arguments
    """
    cmd: list[str] = [str(binary_path)]

    # Add format flags
    if not null_input:
        cmd.extend(["-p", input_format])
    cmd.extend(["-o", output_format])

    # Add in-place flag if requested
    if in_place:
        cmd.append("-i")

    # Add null-input flag if requested
    if null_input:  # pragma: no cover
        cmd.append("-n")

    # Add expression
    cmd.append(expression)

    # Add input file if specified
    if input_file is not None:
        cmd.append(str(input_file))

    return cmd


def _run_yq_subprocess(
    cmd: list[str], input_data: str | None
) -> subprocess.CompletedProcess[bytes]:
    """Run yq subprocess with error handling.

    Args:
        cmd: Command arguments
        input_data: Input data as string (if any)

    Returns:
        Completed subprocess result

    Raises:
        YQExecutionError: If execution fails
    """
    try:
        return subprocess.run(
            cmd,
            input=input_data.encode("utf-8") if input_data else None,
            capture_output=True,
            check=False,  # We'll handle errors ourselves
            timeout=30,  # 30 second timeout
        )
    except subprocess.TimeoutExpired as e:
        raise YQExecutionError(
            "yq command timed out after 30 seconds", stderr=str(e), returncode=-1
        ) from e
    except OSError as e:
        raise YQExecutionError(
            f"Failed to execute yq binary: {e}", stderr=str(e), returncode=-1
        ) from e


def _parse_json_output(
    stdout: str, stderr: str, output_format: FormatType
) -> tuple[Any, str]:
    """Parse JSON output from yq.

    Args:
        stdout: Standard output from yq
        stderr: Standard error from yq
        output_format: Expected output format

    Returns:
        Tuple of (parsed_data, updated_stderr)
    """
    parsed_data: Any = None
    if output_format == "json" and stdout.strip():
        try:
            parsed_data = orjson.loads(stdout)
        except orjson.JSONDecodeError as e:
            # Don't fail on parse error, just leave data as None
            stderr = f"{stderr}\nWarning: Failed to parse JSON output: {e}"
    return parsed_data, stderr


def execute_yq(
    expression: str,
    input_data: str | None = None,
    input_file: Path | str | None = None,
    input_format: FormatType = FormatType.YAML,
    output_format: FormatType = FormatType.JSON,
    in_place: bool = False,
    null_input: bool = False,
) -> YQResult:
    """Execute yq command with the given expression and input.

    Args:
        expression: yq expression to evaluate (e.g., '.name', '.items[]')
        input_data: Input data as string (mutually exclusive with input_file)
        input_file: Path to input file (mutually exclusive with input_data)
        input_format: Format of input data (default: yaml)
        output_format: Format for output (default: json)
        in_place: Modify file in place (only valid with input_file)
        null_input: Don't read input, useful for creating new content

    Returns:
        YQResult object with stdout, stderr, returncode, and parsed data

    Raises:
        YQBinaryNotFoundError: If yq binary cannot be found
        YQExecutionError: If yq execution fails
        ValueError: If arguments are invalid (e.g., both input_data and input_file)
    """
    # Validate arguments
    _validate_execute_args(input_data, input_file, in_place, null_input)

    # Get binary path
    binary_path = get_yq_binary_path()

    # Build command
    cmd = _build_yq_command(
        binary_path,
        expression,
        input_file,
        input_format,
        output_format,
        in_place,
        null_input,
    )

    # Execute command
    result = _run_yq_subprocess(cmd, input_data)

    # Decode output
    stdout = result.stdout.decode("utf-8")
    stderr = result.stderr.decode("utf-8")

    # Check for errors
    if result.returncode != 0:
        error_msg = parse_yq_error(stderr)
        raise YQExecutionError(
            f"yq command failed: {error_msg}",
            stderr=stderr,
            returncode=result.returncode,
        )

    # Parse JSON output if applicable
    parsed_data, stderr = _parse_json_output(stdout, stderr, output_format)

    return YQResult(
        stdout=stdout, stderr=stderr, returncode=result.returncode, data=parsed_data
    )


class YqBackend:
    """yq-based query backend implementing QueryBackend protocol."""

    def execute(
        self,
        expression: str,
        input_data: str | None = None,
        input_file: Path | str | None = None,
        input_format: FormatType = FormatType.YAML,
        output_format: FormatType = FormatType.JSON,
        in_place: bool = False,
        null_input: bool = False,
    ) -> YQResult:
        """Execute a yq expression.

        Args:
            expression: yq expression to evaluate.
            input_data: Input data as string (mutually exclusive with input_file).
            input_file: Path to input file (mutually exclusive with input_data).
            input_format: Format of input data.
            output_format: Format for output.
            in_place: Modify file in place (only valid with input_file).
            null_input: Don't read input, useful for creating new content.

        Returns:
            YQResult with execution output.
        """
        return execute_yq(
            expression=expression,
            input_data=input_data,
            input_file=input_file,
            input_format=input_format,
            output_format=output_format,
            in_place=in_place,
            null_input=null_input,
        )

    def validate(self) -> tuple[bool, str]:
        """Validate the yq binary is available and functional.

        Returns:
            Tuple of (is_valid, message) describing the validation result.
        """
        return validate_yq_binary()


__all__ = [
    "YqBackend",
    "_build_yq_command",
    "_parse_json_output",
    "_run_yq_subprocess",
    "_validate_execute_args",
    "execute_yq",
    "parse_yq_error",
]

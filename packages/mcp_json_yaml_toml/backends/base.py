"""Base types and protocol for query execution backends.

Defines the shared type foundation used across the MCP server:
- FormatType enum for supported file formats
- YQResult model for execution results
- Error class hierarchy for execution failures
- QueryBackend protocol for pluggable backend implementations
"""

from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING, Any, Protocol

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from pathlib import Path


class YQError(Exception):
    """Base exception for yq execution errors."""


class YQBinaryNotFoundError(YQError):
    """Raised when the platform-specific yq binary cannot be found."""


class YQExecutionError(YQError):
    """Raised when yq execution fails.

    Attributes:
        message: Human-readable error description.
        stderr: Raw stderr output from yq.
        returncode: Process exit code.
    """

    def __init__(self, message: str, stderr: str, returncode: int) -> None:
        """Initialize execution error with details.

        Args:
            message: Human-readable error description.
            stderr: Raw stderr output from yq.
            returncode: Process exit code.
        """
        super().__init__(message)
        self.stderr = stderr
        self.returncode = returncode


class YQResult(BaseModel):
    """Result of a yq execution."""

    stdout: str = Field(description="Standard output from yq command")
    stderr: str = Field(default="", description="Standard error from yq command")
    returncode: int = Field(default=0, description="Exit code from yq process")
    data: Any = Field(default=None, description="Parsed output data (if JSON output)")


class FormatType(StrEnum):
    """Supported file format types for yq operations."""

    JSON = "json"
    YAML = "yaml"
    TOML = "toml"
    XML = "xml"
    CSV = "csv"
    TSV = "tsv"
    PROPS = "props"


class QueryBackend(Protocol):
    """Protocol for pluggable query execution backends."""

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
        """Execute a query expression against input data.

        Args:
            expression: Query expression to evaluate.
            input_data: Input data as string (mutually exclusive with input_file).
            input_file: Path to input file (mutually exclusive with input_data).
            input_format: Format of input data.
            output_format: Format for output.
            in_place: Modify file in place (only valid with input_file).
            null_input: Don't read input, useful for creating new content.

        Returns:
            YQResult with execution output.
        """
        ...

    def validate(self) -> tuple[bool, str]:
        """Validate that the backend is properly configured and operational.

        Returns:
            Tuple of (is_valid, message) describing the validation result.
        """
        ...


__all__ = [
    "FormatType",
    "QueryBackend",
    "YQBinaryNotFoundError",
    "YQError",
    "YQExecutionError",
    "YQResult",
]

"""YQ binary wrapper for cross-platform YAML/JSON/TOML querying and manipulation.

This module provides a Python interface to the bundled yq binary, handling:
- Platform-specific binary selection (Linux, macOS, Windows)
- Architecture detection (amd64, arm64)
- Subprocess execution with proper error handling
- Input/output format conversions
- Error message parsing for AI-friendly responses
- Auto-download of missing binaries from GitHub releases
"""

import contextlib
import hashlib
import os
import platform
import subprocess
import sys
from pathlib import Path
from typing import Any, Literal

import httpx
import orjson
from pydantic import BaseModel, Field


class YQError(Exception):
    """Base exception for yq execution errors."""


class YQBinaryNotFoundError(YQError):
    """Raised when the platform-specific yq binary cannot be found."""


class YQExecutionError(YQError):
    """Raised when yq execution fails."""

    def __init__(self, message: str, stderr: str, returncode: int) -> None:
        """Initialize execution error with details.

        Args:
            message: Human-readable error description
            stderr: Raw stderr output from yq
            returncode: Process exit code
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


FormatType = Literal["json", "yaml", "toml", "xml", "csv", "tsv", "props"]

# GitHub repository for yq
GITHUB_REPO = "mikefarah/yq"
GITHUB_API_BASE = "https://api.github.com"

# Checksum file parsing constants
CHECKSUM_MIN_FIELDS = 19  # Minimum fields in checksum line
CHECKSUM_SHA256_INDEX = 18  # SHA-256 hash position (0-indexed)


def _get_storage_location() -> Path:
    """Get the storage location for downloaded yq binaries with fallback.

    Priority:
    1. ~/.local/bin/ (if writable) - standard user binary location
    2. Package directory binaries/ (fallback if ~/.local/bin/ not accessible)

    Returns:
        Path to storage directory (created if it doesn't exist and writable)
    """
    # Try primary location: ~/.local/bin/
    local_bin = Path.home() / ".local" / "bin"
    try:
        local_bin.mkdir(parents=True, exist_ok=True)
        # Test if writable
        test_file = local_bin / ".write_test"
        test_file.touch()
        test_file.unlink()
    except (OSError, PermissionError):  # pragma: no cover
        pass
    else:
        return local_bin

    # Fallback to package directory - only reached when ~/.local/bin is not writable
    pkg_binaries = Path(__file__).parent / "binaries"  # pragma: no cover
    pkg_binaries.mkdir(parents=True, exist_ok=True)  # pragma: no cover
    return pkg_binaries  # pragma: no cover


def _get_latest_release_tag() -> str:  # pragma: no cover
    """Query GitHub API for the latest yq release tag.

    Returns:
        The tag name of the latest release (e.g., "v4.48.2")

    Raises:
        YQError: If API request fails or response is invalid
    """
    url = f"{GITHUB_API_BASE}/repos/{GITHUB_REPO}/releases/latest"
    headers = {"Accept": "application/vnd.github+json"}

    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.get(url, headers=headers, follow_redirects=True)
            response.raise_for_status()
            data = response.json()
            return str(data["tag_name"])
    except httpx.HTTPStatusError as e:
        raise YQError(
            f"GitHub API request failed: HTTP {e.response.status_code}"
        ) from e
    except httpx.RequestError as e:
        raise YQError(f"Network error accessing GitHub API: {e}") from e
    except (KeyError, ValueError) as e:
        raise YQError(f"Invalid GitHub API response: {e}") from e


def _download_file(url: str, dest_path: Path) -> None:  # pragma: no cover
    """Download a file from URL to destination path.

    Args:
        url: The URL to download from
        dest_path: The local path to save the file

    Raises:
        YQError: If download fails
    """
    headers = {"User-Agent": "mcp-json-yaml-toml/1.0"}

    try:
        with httpx.Client(timeout=60.0) as client:
            response = client.get(url, headers=headers, follow_redirects=True)
            response.raise_for_status()
            dest_path.write_bytes(response.content)
    except httpx.HTTPStatusError as e:
        raise YQError(f"Failed to download {url}: HTTP {e.response.status_code}") from e
    except httpx.RequestError as e:
        raise YQError(f"Network error downloading {url}: {e}") from e


def _get_checksums(version: str) -> dict[str, str]:  # pragma: no cover
    """Download and parse the checksums file for a given version.

    Args:
        version: The release version tag (e.g., "v4.48.2")

    Returns:
        Dictionary mapping binary names to their SHA256 checksums

    Raises:
        YQError: If checksums file cannot be downloaded or parsed
    """
    url = f"https://github.com/{GITHUB_REPO}/releases/download/{version}/checksums"
    headers = {"User-Agent": "mcp-json-yaml-toml/1.0"}

    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.get(url, headers=headers, follow_redirects=True)
            response.raise_for_status()
            content = response.text
    except httpx.HTTPStatusError as e:
        raise YQError(
            f"Failed to download checksums: HTTP {e.response.status_code}"
        ) from e
    except httpx.RequestError as e:
        raise YQError(f"Network error downloading checksums: {e}") from e

    # Parse checksums file - format is space-separated with SHA256 at specific index
    checksums: dict[str, str] = {}
    for line in content.strip().split("\n"):
        parts = line.split()
        if len(parts) >= CHECKSUM_MIN_FIELDS:
            binary_name = parts[0]
            sha256_hash = parts[CHECKSUM_SHA256_INDEX]
            checksums[binary_name] = sha256_hash

    return checksums


def _verify_checksum(file_path: Path, expected_hash: str) -> bool:
    """Verify a file's SHA256 checksum.

    Args:
        file_path: Path to the file to verify
        expected_hash: Expected SHA256 hash in hexadecimal

    Returns:
        True if checksum matches, False otherwise
    """
    sha256 = hashlib.sha256()
    sha256.update(file_path.read_bytes())
    actual_hash = sha256.hexdigest()
    return actual_hash == expected_hash


def _download_yq_binary(
    binary_name: str, github_name: str, dest_path: Path, version: str
) -> None:  # pragma: no cover
    """Download and verify a single yq binary with file locking.

    Uses file locking to ensure only one process downloads the binary when
    multiple processes attempt simultaneously. Other processes wait for the
    lock holder to complete the download.

    Args:
        binary_name: Local filename (e.g., "yq-linux-amd64")
        github_name: GitHub release asset name (e.g., "yq_linux_amd64")
        dest_path: Destination path for downloaded binary
        version: Release version tag (e.g., "v4.48.2")

    Raises:
        YQError: If download or verification fails
    """
    import fcntl
    import uuid

    # Use a lock file to coordinate between parallel processes
    lock_path = dest_path.with_suffix(".lock")

    # Open lock file (create if doesn't exist)
    with Path(lock_path).open("w", encoding="utf-8") as lock_file:
        # Acquire exclusive lock - blocks until available
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)

        try:
            # Re-check if another process completed the download while we waited
            if dest_path.exists():
                print(
                    f"Binary already downloaded by another process at {dest_path}",
                    file=sys.stderr,
                )
                return

            print(f"Downloading yq {version} for your platform...", file=sys.stderr)

            # Get checksums for this version
            print("Fetching checksums...", file=sys.stderr)
            checksums = _get_checksums(version)

            if github_name not in checksums:
                raise YQError(f"No checksum found for {github_name}")

            # Use unique temp file in case of failure
            temp_path = dest_path.with_suffix(f".tmp.{uuid.uuid4().hex[:8]}")

            try:
                # Download binary to temp file
                url = f"https://github.com/{GITHUB_REPO}/releases/download/{version}/{github_name}"
                print(f"Downloading {github_name}...", file=sys.stderr)
                _download_file(url, temp_path)

                # Verify checksum on temp file
                print("Verifying checksum...", file=sys.stderr)
                if not _verify_checksum(temp_path, checksums[github_name]):
                    raise YQError(f"Checksum verification failed for {github_name}")

                # Set executable permissions on Unix binaries before rename
                if os.name != "nt":
                    temp_path.chmod(0o755)

                # Atomic rename to final destination
                temp_path.rename(dest_path)

                print(
                    f"Successfully downloaded and verified {binary_name}",
                    file=sys.stderr,
                )

            finally:
                # Clean up temp file if it still exists (e.g., if verification failed)
                if temp_path.exists():
                    temp_path.unlink()

        finally:
            # Release lock (implicit when file closes, but be explicit)
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)

    # Clean up lock file (best effort - may fail if another process is using it)
    with contextlib.suppress(OSError):
        lock_path.unlink()


def get_yq_binary_path() -> Path:
    """Get the path to the platform-specific yq binary.

    Detects the current operating system and architecture, then returns the
    path to the appropriate bundled yq binary. If the binary is not found in
    bundled locations, attempts to auto-download it from GitHub releases.

    Returns:
        Path to the yq binary executable

    Raises:
        YQBinaryNotFoundError: If the binary for this platform cannot be found or downloaded
    """
    system = platform.system().lower()
    machine = platform.machine().lower()

    # Normalize architecture names
    if machine in {"x86_64", "amd64"}:
        arch = "amd64"
    elif machine in {"arm64", "aarch64"}:  # pragma: no cover
        arch = "arm64"
    else:  # pragma: no cover
        raise YQBinaryNotFoundError(
            f"Unsupported architecture: {machine}. Supported architectures: x86_64/amd64, arm64/aarch64"
        )

    # Determine binary filename and GitHub asset name
    if system == "linux":
        binary_name = f"yq-linux-{arch}"
        github_name = f"yq_linux_{arch}"
    elif system == "darwin":  # pragma: no cover
        binary_name = f"yq-darwin-{arch}"
        github_name = f"yq_darwin_{arch}"
    elif system == "windows":  # pragma: no cover
        binary_name = f"yq-windows-{arch}.exe"
        github_name = f"yq_windows_{arch}.exe"
    else:  # pragma: no cover
        raise YQBinaryNotFoundError(
            f"Unsupported operating system: {system}. Supported systems: Linux, Darwin (macOS), Windows"
        )

    # Look for binary in multiple locations
    # 1. ~/.local/bin/ or package binaries/ (determined by _get_storage_location)
    storage_dir = _get_storage_location()
    storage_binary = storage_dir / binary_name

    # Check if binary already exists
    if storage_binary.exists():
        return storage_binary

    # Binary not found - attempt auto-download
    # This code path is only reached when binary is missing (not during normal testing)
    print(
        f"\nyq binary not found for {system}/{arch}", file=sys.stderr
    )  # pragma: no cover
    print(
        "Attempting to auto-download from GitHub releases...", file=sys.stderr
    )  # pragma: no cover

    try:  # pragma: no cover
        # Get latest release version
        version = _get_latest_release_tag()

        # Download to storage directory
        _download_yq_binary(binary_name, github_name, storage_binary, version)

        # Verify it exists and return
        if storage_binary.exists():
            print(
                f"Auto-download successful. Binary stored at: {storage_binary}\n",
                file=sys.stderr,
            )
            return storage_binary

        raise YQBinaryNotFoundError(
            "Binary download completed but file not found at expected location"
        )

    except YQError as e:  # pragma: no cover
        # Download failed - provide helpful error message
        raise YQBinaryNotFoundError(
            f"yq binary not found for {system}/{arch} and auto-download failed: {e}\n"
            f"Attempted storage location: {storage_binary}\n"
            f"Please ensure you have write permissions to ~/.local/bin/ or the package directory"
        ) from e


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
    input_format: FormatType = "yaml",
    output_format: FormatType = "json",
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


def validate_yq_binary() -> tuple[bool, str]:
    """Validate that the yq binary exists and is executable.

    Returns:
        Tuple of (is_valid, message) where message describes the result
    """
    try:
        binary_path = get_yq_binary_path()

        # Check if file exists
        if not binary_path.exists():  # pragma: no cover
            return False, f"Binary not found at {binary_path}"

        # Check if executable (Unix-like systems)
        if os.name != "nt" and not os.access(binary_path, os.X_OK):  # pragma: no cover
            return False, f"Binary at {binary_path} is not executable"

        # Try to run version command
        result = subprocess.run(
            [str(binary_path), "--version"], capture_output=True, check=False, timeout=5
        )

        if result.returncode != 0:  # pragma: no cover
            return False, f"Binary failed to execute: {result.stderr.decode('utf-8')}"
    except YQBinaryNotFoundError as e:  # pragma: no cover
        return False, str(e)
    except (
        OSError,
        subprocess.SubprocessError,
        subprocess.TimeoutExpired,
    ) as e:  # pragma: no cover
        return False, f"Error validating yq binary: {e}"
    else:
        version = result.stdout.decode("utf-8").strip()
        return True, f"yq binary found and working: {version}"

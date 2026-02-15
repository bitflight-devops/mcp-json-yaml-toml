"""Binary lifecycle management for yq.

Handles platform-specific binary discovery, downloading, verification,
version management, and caching. Decoupled from query execution (ARCH-03).
"""

from __future__ import annotations

import contextlib
import hashlib
import os
import platform
import re
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

import httpx
import portalocker

from mcp_json_yaml_toml.backends.base import YQBinaryNotFoundError, YQError

# GitHub repository for yq
GITHUB_REPO = "mikefarah/yq"

# Checksum file parsing constants
CHECKSUM_MIN_FIELDS = 19  # Minimum fields in checksum line
CHECKSUM_SHA256_INDEX = 18  # SHA-256 hash position (0-indexed)

# Default yq version - pinned to a tested release for reproducibility
# Override with YQ_VERSION environment variable if needed
DEFAULT_YQ_VERSION = "v4.52.2"

# Bundled SHA256 checksums for the default version - avoids network request
# These are verified during the weekly yq update workflow
# fmt: off
DEFAULT_YQ_CHECKSUMS: dict[str, str] = {
    "yq_darwin_amd64": "54a63555210e73abed09108097072e28bf82a6bb20439a72b55509c4dd42378d",
    "yq_darwin_arm64": "34613ea97c4c77e1894a8978dbf72588d187a69a6292c10dab396c767a1ecde7",
    "yq_linux_amd64": "a74bd266990339e0c48a2103534aef692abf99f19390d12c2b0ce6830385c459",
    "yq_linux_arm64": "c82856ac30da522f50dcdd4f53065487b5a2927e9b87ff637956900986f1f7c2",
    "yq_windows_amd64.exe": "2b6cd8974004fa0511f6b6b359d2698214fadeb4599f0b00e8d85ae62b3922d4",
}
# fmt: on


def get_yq_version() -> str:
    """Get the yq version to use for downloads.

    Reads the YQ_VERSION environment variable if set, otherwise returns
    the pinned DEFAULT_YQ_VERSION. This ensures reproducible builds by
    defaulting to a tested version rather than always fetching "latest".

    Returns:
        Version string (e.g., "v4.52.2")
    """
    version = os.environ.get("YQ_VERSION", "").strip()
    if version:
        # Ensure version starts with 'v' for consistency with GitHub tags
        if not version.startswith("v"):
            version = f"v{version}"
        return version
    return DEFAULT_YQ_VERSION


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
    pkg_binaries = Path(__file__).parent.parent / "binaries"  # pragma: no cover
    pkg_binaries.mkdir(parents=True, exist_ok=True)  # pragma: no cover
    return pkg_binaries  # pragma: no cover


def _get_download_headers() -> dict[str, str]:
    """Get HTTP headers for GitHub release downloads.

    Returns minimal headers needed for downloading release assets from GitHub CDN.
    Note: Since we download from the releases CDN (not the API), authentication
    is generally not required. However, we include the token if available for:
    - GitHub Enterprise environments that require auth
    - Private repository forks
    - Corporate proxy/firewall environments

    Returns:
        Dictionary of HTTP headers
    """
    headers = {"User-Agent": "mcp-json-yaml-toml/1.0"}

    # Include auth token if available (may help in enterprise/private repo scenarios)
    github_token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if github_token:
        headers["Authorization"] = f"Bearer {github_token}"

    return headers


def _download_file(url: str, dest_path: Path) -> None:  # pragma: no cover
    """Download a file from URL to destination path.

    Args:
        url: The URL to download from
        dest_path: The local path to save the file

    Raises:
        YQError: If download fails
    """
    headers = _get_download_headers()

    try:
        with httpx.Client(timeout=60.0) as client:
            response = client.get(url, headers=headers, follow_redirects=True)
            response.raise_for_status()
            dest_path.write_bytes(response.content)
    except httpx.HTTPStatusError as e:
        raise YQError(f"Failed to download {url}: HTTP {e.response.status_code}") from e
    except httpx.RequestError as e:
        raise YQError(f"Network error downloading {url}: {e}") from e


def _get_checksums(version: str) -> dict[str, str]:
    """Get SHA256 checksums for yq binaries.

    For the default pinned version, returns bundled checksums (no network request).
    For custom versions (via YQ_VERSION env var), downloads checksums from GitHub.

    Args:
        version: The release version tag (e.g., "v4.52.2")

    Returns:
        Dictionary mapping binary names to their SHA256 checksums

    Raises:
        YQError: If checksums cannot be obtained (network error for custom versions)
    """
    # Use bundled checksums for the default version - no network request needed
    if version == DEFAULT_YQ_VERSION:
        return DEFAULT_YQ_CHECKSUMS

    # For custom versions, download checksums from GitHub
    return _fetch_checksums_from_github(version)  # pragma: no cover


def _fetch_checksums_from_github(version: str) -> dict[str, str]:  # pragma: no cover
    """Download and parse checksums file from GitHub releases.

    This is only called for custom versions (YQ_VERSION env var).
    The default pinned version uses bundled checksums instead.

    Args:
        version: The release version tag (e.g., "v4.50.0")

    Returns:
        Dictionary mapping binary names to their SHA256 checksums

    Raises:
        YQError: If checksums file cannot be downloaded or parsed
    """
    url = f"https://github.com/{GITHUB_REPO}/releases/download/{version}/checksums"
    headers = _get_download_headers()

    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.get(url, headers=headers, follow_redirects=True)
            response.raise_for_status()
            content = response.text
    except httpx.HTTPStatusError as e:
        raise YQError(
            f"Failed to download checksums for {version}: HTTP {e.response.status_code}"
        ) from e
    except httpx.RequestError as e:
        raise YQError(f"Network error downloading checksums for {version}: {e}") from e

    # Parse checksums file - format is space-separated with SHA256 at specific index
    checksums: dict[str, str] = {}
    for line in content.strip().split("\n"):
        parts = line.split()
        if len(parts) >= CHECKSUM_MIN_FIELDS:
            binary_name = parts[0]
            sha256_hash = parts[CHECKSUM_SHA256_INDEX]
            checksums[binary_name] = sha256_hash

    return checksums


def _cleanup_old_versions(
    storage_dir: Path, platform_prefix: str, current_binary: str
) -> None:  # pragma: no cover
    """Clean up old version binaries after a successful download.

    Removes old versioned binaries for the same platform to prevent disk space
    accumulation. For example, when downloading yq-linux-amd64-v4.53.0, this
    will remove yq-linux-amd64-v4.52.2 if it exists.

    Args:
        storage_dir: Directory containing yq binaries
        platform_prefix: Platform/arch prefix (e.g., "yq-linux-amd64")
        current_binary: Current binary filename to keep (e.g., "yq-linux-amd64-v4.53.0")
    """
    # Find old versioned binaries matching the platform prefix
    # Pattern: yq-linux-amd64-v*.* (matches versioned binaries)
    for old_binary in storage_dir.glob(f"{platform_prefix}-v*"):
        if old_binary.name != current_binary:
            try:
                old_binary.unlink()
                print(f"Cleaned up old version: {old_binary.name}", file=sys.stderr)
            except OSError as e:
                # Best effort - don't fail if cleanup fails
                print(
                    f"Note: Could not remove old binary {old_binary.name}: {e}",
                    file=sys.stderr,
                )


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
    binary_name: str,
    github_name: str,
    dest_path: Path,
    version: str,
    platform_prefix: str,
) -> None:  # pragma: no cover
    """Download and verify a single yq binary with cross-platform file locking.

    Uses portalocker for cross-platform file locking to ensure only one process
    downloads the binary. Other processes block until the lock is released.
    After successful download, cleans up old versions of the same platform binary.

    Args:
        binary_name: Local filename (e.g., "yq-linux-amd64-v4.52.2")
        github_name: GitHub release asset name (e.g., "yq_linux_amd64")
        dest_path: Destination path for downloaded binary
        version: Release version tag (e.g., "v4.48.2")
        platform_prefix: Platform/arch prefix without version (e.g., "yq-linux-amd64")

    Raises:
        YQError: If download or verification fails
    """
    # Fast path: check if already exists (no lock needed)
    if dest_path.exists():
        print(f"Binary already exists at {dest_path}", file=sys.stderr)
        return

    # Use a lock file to coordinate between processes
    lock_path = dest_path.with_suffix(".lock")

    # Timeout calculation: 14MB binary @ 500 Kbps = ~224s, plus overhead for checksums/redirects
    # Using 300s (5 min) to accommodate slow connections while not blocking indefinitely
    lock_timeout = 300

    # Acquire exclusive lock - blocks until available (cross-platform via portalocker)
    with portalocker.Lock(lock_path, timeout=lock_timeout) as _lock:
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
                f"Successfully downloaded and verified {binary_name}", file=sys.stderr
            )

            # Clean up old versions after successful download
            _cleanup_old_versions(dest_path.parent, platform_prefix, binary_name)

        finally:
            # Clean up temp file if it still exists (e.g., if verification failed)
            with contextlib.suppress(OSError):
                if temp_path.exists():
                    temp_path.unlink()

    # Clean up lock file (best effort - may fail if another process is using it)
    with contextlib.suppress(OSError):
        lock_path.unlink()


def _get_yq_version_string(yq_path: Path) -> str | None:
    """Get the version string from a yq binary.

    Args:
        yq_path: Path to the yq binary

    Returns:
        Version string (e.g., "v4.52.2") if mikefarah/yq, None otherwise
    """
    try:
        result = subprocess.run(
            [str(yq_path), "--version"], capture_output=True, check=False, timeout=5
        )
    except (OSError, subprocess.TimeoutExpired, subprocess.SubprocessError):
        return None
    else:
        if result.returncode != 0:
            return None
        version_output = result.stdout.decode("utf-8", errors="replace")
        # mikefarah/yq outputs: "yq (https://github.com/mikefarah/yq/) version v4.x.x"
        if "mikefarah/yq" not in version_output:
            return None
        # Extract version from the output
        match = re.search(r"version\s+(v[\d.]+)", version_output)
        if match:
            return match.group(1)
        return None


def _is_mikefarah_yq(yq_path: Path) -> bool:
    """Check if a yq binary is the mikefarah/yq (Go-based) version.

    There are two common yq tools:
    - mikefarah/yq: Go-based, outputs "yq (https://github.com/mikefarah/yq/) version v4.x.x"
    - kislyuk/yq: Python-based wrapper around jq, outputs "yq 3.x.x"

    We need the mikefarah version for YAML/TOML/XML support.

    Args:
        yq_path: Path to the yq binary to check

    Returns:
        True if this is mikefarah/yq, False otherwise
    """
    return _get_yq_version_string(yq_path) is not None


def _parse_version(version_str: str) -> tuple[int, ...]:
    """Parse a version string like 'v4.52.2' into comparable tuple.

    Args:
        version_str: Version string (with or without 'v' prefix)

    Returns:
        Tuple of integers for comparison (e.g., (4, 52, 2))
    """
    # Strip 'v' prefix if present
    version = version_str.lstrip("v")
    # Split by '.' and convert to integers
    parts = []
    for part in version.split("."):
        # Handle pre-release suffixes like "4.52.2-rc1"
        num_part = part.split("-")[0]
        if num_part.isdigit():
            parts.append(int(num_part))
    return tuple(parts)


def _version_meets_minimum(system_version: str, minimum_version: str) -> bool:
    """Check if system version meets the minimum required version.

    Args:
        system_version: Version string of system yq (e.g., "v4.53.0")
        minimum_version: Minimum required version (e.g., "v4.52.2")

    Returns:
        True if system_version >= minimum_version
    """
    try:
        system_parts = _parse_version(system_version)
        minimum_parts = _parse_version(minimum_version)
    except (ValueError, IndexError):
        # If parsing fails, reject the version
        return False
    else:
        return system_parts >= minimum_parts


def _find_system_yq() -> Path | None:
    """Find yq binary installed via system package manager with compatible version.

    Checks if yq is available in the system PATH (e.g., installed via
    homebrew, apt, chocolatey, or go install). Only returns the path if:
    1. It's the mikefarah/yq (Go-based) version, not the Python yq wrapper
    2. Its version is >= our pinned DEFAULT_YQ_VERSION (minimum required version)

    This ensures the system yq has all required features (like nested TOML output
    support added in v4.52.2) while allowing newer compatible versions.

    Returns:
        Path to system yq binary if found with compatible version, None otherwise
    """
    yq_path = shutil.which("yq")
    if yq_path:
        path = Path(yq_path)
        system_version = _get_yq_version_string(path)
        if system_version is None:
            # Found yq but it's Python yq or unrecognized
            print(
                f"Found yq at {yq_path} but it's not mikefarah/yq (Go version). "
                "Install the correct yq: brew install yq | choco install yq | snap install yq",
                file=sys.stderr,
            )
            return None

        pinned_version = get_yq_version()
        if _version_meets_minimum(system_version, pinned_version):
            return path

        # Found mikefarah/yq but version is too old
        print(
            f"Found yq {system_version} at {yq_path} but need >= {pinned_version}. "
            f"Will download minimum required version.",
            file=sys.stderr,
        )
    return None


def _get_platform_binary_info(
    system: str, arch: str, version: str
) -> tuple[str, str, str]:
    """Get platform-specific binary naming information.

    Args:
        system: Operating system (linux, darwin, windows)
        arch: Architecture (amd64, arm64)
        version: yq version string (e.g., v4.52.2)

    Returns:
        Tuple of (platform_prefix, binary_name, github_name)

    Raises:
        YQBinaryNotFoundError: If the platform is not supported
    """
    if system == "linux":
        platform_prefix = f"yq-linux-{arch}"
        binary_name = f"{platform_prefix}-{version}"
        github_name = f"yq_linux_{arch}"
    elif system == "darwin":
        platform_prefix = f"yq-darwin-{arch}"
        binary_name = f"{platform_prefix}-{version}"
        github_name = f"yq_darwin_{arch}"
    elif system == "windows":
        platform_prefix = f"yq-windows-{arch}"
        binary_name = f"{platform_prefix}-{version}.exe"
        github_name = f"yq_windows_{arch}.exe"
    else:
        raise YQBinaryNotFoundError(
            f"Unsupported operating system: {system}. "
            f"Supported systems: Linux, Darwin (macOS), Windows"
        )
    return platform_prefix, binary_name, github_name


def get_yq_binary_path() -> Path:
    """Get the path to the yq binary.

    Resolution order:
    1. YQ_BINARY_PATH env var (explicit user override)
    2. Cached versioned binary (~/.local/bin/yq-{platform}-{arch}-{version})
    3. System PATH lookup (yq from homebrew/apt/chocolatey)
    4. Auto-download from GitHub releases CDN

    Returns:
        Path to the yq binary executable

    Raises:
        YQBinaryNotFoundError: If the binary cannot be found or downloaded
    """
    # 1. Check for explicit user override via YQ_BINARY_PATH
    custom_path = os.environ.get("YQ_BINARY_PATH", "").strip()
    if custom_path:
        custom_binary = Path(custom_path).expanduser()
        if custom_binary.exists() and custom_binary.is_file():
            return custom_binary
        raise YQBinaryNotFoundError(
            f"YQ_BINARY_PATH set to '{custom_path}' but file does not exist"
        )

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

    # Get the target version (pinned default or env var override)
    version = get_yq_version()

    # Get platform-specific binary naming
    platform_prefix, binary_name, github_name = _get_platform_binary_info(
        system, arch, version
    )

    # Look for binary in multiple locations
    # 2. Cached versioned binary (~/.local/bin/ or package binaries/)
    storage_dir = _get_storage_location()
    storage_binary = storage_dir / binary_name

    if storage_binary.exists():
        return storage_binary

    # 3. Check system PATH for yq installed via package manager
    # (homebrew, apt, chocolatey, go install, etc.)
    system_yq = _find_system_yq()
    if system_yq:
        print(
            f"Using system-installed yq at: {system_yq}", file=sys.stderr
        )  # pragma: no cover
        return system_yq  # pragma: no cover

    # 4. Binary not found - attempt auto-download from GitHub
    print(
        f"\nyq binary not found for {system}/{arch}", file=sys.stderr
    )  # pragma: no cover
    print(
        "Attempting to auto-download from GitHub releases...", file=sys.stderr
    )  # pragma: no cover
    print(
        "Tip: Install yq via package manager to avoid downloads:", file=sys.stderr
    )  # pragma: no cover
    print(
        "  macOS: brew install yq | Windows: choco install yq | Linux: snap install yq",
        file=sys.stderr,
    )  # pragma: no cover

    try:  # pragma: no cover
        # Download to storage directory (version already resolved above)
        _download_yq_binary(
            binary_name, github_name, storage_binary, version, platform_prefix
        )

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


__all__ = [
    "CHECKSUM_MIN_FIELDS",
    "CHECKSUM_SHA256_INDEX",
    "DEFAULT_YQ_CHECKSUMS",
    "DEFAULT_YQ_VERSION",
    "GITHUB_REPO",
    "_cleanup_old_versions",
    "_download_file",
    "_download_yq_binary",
    "_fetch_checksums_from_github",
    "_find_system_yq",
    "_get_checksums",
    "_get_download_headers",
    "_get_platform_binary_info",
    "_get_storage_location",
    "_get_yq_version_string",
    "_is_mikefarah_yq",
    "_parse_version",
    "_verify_checksum",
    "_version_meets_minimum",
    "get_yq_binary_path",
    "get_yq_version",
    "validate_yq_binary",
]

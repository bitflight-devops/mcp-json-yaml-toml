#!/usr/bin/env python3
"""Update DEFAULT_YQ_CHECKSUMS in yq_wrapper.py.

This script is called by the weekly yq-update workflow to update
the bundled checksums after a new yq version is released.

Usage:
    python update_yq_checksums.py

Environment variables (required):
    CS_DARWIN_AMD64: SHA256 checksum for darwin amd64 binary
    CS_DARWIN_ARM64: SHA256 checksum for darwin arm64 binary
    CS_LINUX_AMD64: SHA256 checksum for linux amd64 binary
    CS_LINUX_ARM64: SHA256 checksum for linux arm64 binary
    CS_WINDOWS_AMD64: SHA256 checksum for windows amd64 binary
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

# SHA256 hash length in hexadecimal characters
SHA256_HEX_LENGTH = 64


def get_checksums_from_env() -> dict[str, str]:
    """Read checksums from environment variables.

    Returns:
        Dictionary mapping binary names to their SHA256 checksums.

    Raises:
        KeyError: If any required environment variable is missing.
    """
    return {
        "yq_darwin_amd64": os.environ["CS_DARWIN_AMD64"],
        "yq_darwin_arm64": os.environ["CS_DARWIN_ARM64"],
        "yq_linux_amd64": os.environ["CS_LINUX_AMD64"],
        "yq_linux_arm64": os.environ["CS_LINUX_ARM64"],
        "yq_windows_amd64.exe": os.environ["CS_WINDOWS_AMD64"],
    }


def build_replacement(checksums: dict[str, str]) -> str:
    """Build the replacement string for DEFAULT_YQ_CHECKSUMS.

    Args:
        checksums: Dictionary mapping binary names to checksums.

    Returns:
        Formatted Python code for the checksums dict.
    """
    return f"""# fmt: off
DEFAULT_YQ_CHECKSUMS: dict[str, str] = {{
    "yq_darwin_amd64": "{checksums["yq_darwin_amd64"]}",
    "yq_darwin_arm64": "{checksums["yq_darwin_arm64"]}",
    "yq_linux_amd64": "{checksums["yq_linux_amd64"]}",
    "yq_linux_arm64": "{checksums["yq_linux_arm64"]}",
    "yq_windows_amd64.exe": "{checksums["yq_windows_amd64.exe"]}",
}}
# fmt: on"""


def update_checksums(file_path: Path, checksums: dict[str, str]) -> bool:
    """Update the DEFAULT_YQ_CHECKSUMS dict in yq_wrapper.py.

    Args:
        file_path: Path to yq_wrapper.py
        checksums: Dictionary mapping binary names to checksums.

    Returns:
        True if the file was updated, False if pattern not found.
    """
    content = file_path.read_text(encoding="utf-8")

    # Pattern to match the entire DEFAULT_YQ_CHECKSUMS dict
    pattern = (
        r"# fmt: off\nDEFAULT_YQ_CHECKSUMS: dict\[str, str\] = \{[^}]+\}\n# fmt: on"
    )

    replacement = build_replacement(checksums)
    new_content = re.sub(pattern, replacement, content)

    if new_content == content:
        return False

    file_path.write_text(new_content, encoding="utf-8")
    return True


def main() -> int:
    """Main entry point.

    Returns:
        Exit code (0 for success, 1 for error).
    """
    # Find yq_wrapper.py relative to script location
    script_dir = Path(__file__).parent
    repo_root = script_dir.parent.parent
    wrapper_path = repo_root / "packages" / "mcp_json_yaml_toml" / "yq_wrapper.py"

    if not wrapper_path.exists():
        print(f"Error: {wrapper_path} not found", file=sys.stderr)
        return 1

    try:
        checksums = get_checksums_from_env()
    except KeyError as e:
        print(f"Error: Missing environment variable {e}", file=sys.stderr)
        return 1

    # Validate checksums are valid SHA256
    for name, checksum in checksums.items():
        if len(checksum) != SHA256_HEX_LENGTH or not all(
            c in "0123456789abcdef" for c in checksum
        ):
            print(
                f"Error: Invalid SHA256 checksum for {name}: {checksum}",
                file=sys.stderr,
            )
            return 1

    if update_checksums(wrapper_path, checksums):
        print(f"Updated checksums in {wrapper_path}")
    else:
        print("Warning: Pattern not found, no changes made", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())

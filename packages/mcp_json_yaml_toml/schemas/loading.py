"""Schema content extraction -- functions that extract $schema URLs from file content."""

from __future__ import annotations

import fnmatch
import re
from pathlib import Path  # noqa: TC003 — used at runtime in function bodies

import orjson
import tomlkit
from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError
from tomlkit.exceptions import ParseError, TOMLKitError

# Regex to strip C-style comments (/* ... */) and C++-style comments (// ...)
_COMMENT_RE = re.compile(r"//.*?$|/\*.*?\*/", re.DOTALL | re.MULTILINE)


def _strip_json_comments(text: str) -> str:
    """Strip C-style and C++-style comments from JSON text."""
    return _COMMENT_RE.sub("", text)


def _extract_from_json(content: str) -> str | None:
    """Extract $schema from JSON/JSONC content."""
    try:
        # Try strict JSON first
        data = orjson.loads(content)
    except orjson.JSONDecodeError:
        # Try stripping comments for JSONC
        try:
            clean_content = _strip_json_comments(content)
            data = orjson.loads(clean_content)
        except orjson.JSONDecodeError:
            return None

    if isinstance(data, dict):
        return data.get("$schema")
    return None


def _extract_from_yaml(content: str) -> str | None:
    """Extract $schema from YAML content.

    Supports:
    - yaml-language-server modeline: # yaml-language-server: $schema=URL
    - Top-level $schema key
    """
    # Check for yaml-language-server modeline first

    modeline_match = re.search(
        r"#\s*yaml-language-server:\s*\$schema=(\S+)", content, re.IGNORECASE
    )
    if modeline_match:
        return modeline_match.group(1)

    # Check for top-level $schema key
    yaml = YAML(typ="safe", pure=True)
    try:
        data = yaml.load(content)
        if isinstance(data, dict):
            return data.get("$schema")
    except YAMLError:
        pass
    return None


def _extract_from_toml(content: str) -> str | None:
    """Extract schema URL from TOML content.

    Supports:
    - Taplo directive: #:schema URL
    - Top-level $schema key
    """
    # Check for Taplo-style schema directive first
    directive_match = re.search(r"#:schema\s+(\S+)", content)
    if directive_match:
        return directive_match.group(1)

    # Check for top-level $schema key
    try:
        data = tomlkit.parse(content)
        return data.get("$schema")
    except (ParseError, TOMLKitError):
        pass
    return None


def _extract_schema_url_from_content(file_path: Path) -> str | None:
    """Attempt to extract $schema URL from file content.

    Supports:
    - JSON/JSONC (top-level "$schema" key)
    - YAML (top-level "$schema" key)
    - TOML (top-level "$schema" key)

    Args:
        file_path: Path to the file.

    Returns:
        Schema URL if found, None otherwise.
    """
    if not file_path.exists():
        return None

    try:
        # Read content (assuming utf-8)
        content = file_path.read_text(encoding="utf-8")
        suffix = file_path.suffix.lower()

        url = None
        match suffix:
            case ".json" | ".jsonc":
                url = _extract_from_json(content)
            case ".yaml" | ".yml":
                url = _extract_from_yaml(content)
                if not url:
                    # Also try JSON extraction for YAML files as they might be JSON
                    url = _extract_from_json(content)
            case ".toml":
                url = _extract_from_toml(content)
            case _:
                # Fallback for filenames like ".markdownlint-cli2.jsonc"
                if file_path.name.endswith(".jsonc"):
                    url = _extract_from_json(content)
    except (OSError, UnicodeDecodeError):
        return None
    else:
        return url

    return None


def _match_glob_pattern(file_path: Path, pattern: str) -> bool:
    """Match a file path against a SchemaStore glob pattern.

    Supports:
    - ** for matching any directory depth
    - * for matching any filename part
    - Negation patterns like !(config) are not supported

    Args:
        file_path: Absolute or relative path to match.
        pattern: Glob pattern from SchemaStore (e.g., '**/.github/workflows/*.yml').

    Returns:
        True if the path matches the pattern.
    """
    # Skip negation patterns - too complex for basic matching
    if "!(" in pattern:
        return False

    path_str = str(file_path)

    # Normalize separators
    pattern = pattern.replace("\\", "/")
    path_str = path_str.replace("\\", "/")

    # Handle ** patterns by converting to fnmatch-compatible form
    if "**/" in pattern:
        # Pattern like **/.github/workflows/*.yml
        # Need to match any prefix, then the rest literally
        suffix = pattern.split("**/", 1)[1]
        # Check if path ends with the suffix pattern
        return fnmatch.fnmatch(path_str, "*/" + suffix) or fnmatch.fnmatch(
            path_str, suffix
        )

    # Simple glob pattern
    return fnmatch.fnmatch(path_str, pattern)

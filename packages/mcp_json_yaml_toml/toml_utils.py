"""TOML manipulation utilities.

Since yq cannot write TOML (only read), we use tomlkit for TOML write operations.
tomlkit preserves comments and formatting, consistent with our ruamel.yaml approach for YAML.
"""

from __future__ import annotations

from collections.abc import MutableMapping
from typing import TYPE_CHECKING, Any

import tomlkit

if TYPE_CHECKING:
    from pathlib import Path


def _navigate_to_parent(
    data: MutableMapping[str, Any], key_path: str, *, create_missing: bool = False
) -> tuple[MutableMapping[str, Any], str]:
    """Navigate a nested mapping to the parent of the target key.

    Args:
        data: Root mapping to navigate.
        key_path: Dot-separated key path (e.g., "database.port").
        create_missing: If True, create intermediate tables for missing keys.
            If False (default), raise KeyError on missing intermediate keys.

    Returns:
        Tuple of (parent_mapping, final_key_name).

    Raises:
        KeyError: If an intermediate key is missing and create_missing is False.
        TypeError: If an intermediate value is not a mapping (e.g., navigating through a string).
    """
    keys = key_path.split(".")
    current: MutableMapping[str, Any] = data
    for key in keys[:-1]:
        if key not in current:
            if create_missing:
                current[key] = {}
            else:
                raise KeyError(f"Key path '{key_path}' not found")
        nested = current[key]
        if not isinstance(nested, MutableMapping):
            msg = f"Cannot navigate through non-table value at key '{key}'"
            raise TypeError(msg)
        current = nested
    return current, keys[-1]


def set_toml_value(file_path: Path, key_path: str, value: Any) -> str:
    """Set a value in a TOML file.

    Args:
        file_path: Path to TOML file
        key_path: Dot-separated key path (e.g., "database.port")
        value: Value to set

    Returns:
        Modified TOML content as string (preserves comments and formatting)
    """
    content = file_path.read_text(encoding="utf-8")
    data = tomlkit.parse(content)
    parent, final_key = _navigate_to_parent(data, key_path, create_missing=True)
    parent[final_key] = value
    return tomlkit.dumps(data)


def delete_toml_key(file_path: Path, key_path: str) -> str:
    """Delete a key from a TOML file.

    Args:
        file_path: Path to TOML file
        key_path: Dot-separated key path (e.g., "database.port")

    Returns:
        Modified TOML content as string (preserves comments and formatting)
    """
    content = file_path.read_text(encoding="utf-8")
    data = tomlkit.parse(content)
    parent, final_key = _navigate_to_parent(data, key_path, create_missing=False)
    if final_key not in parent:
        raise KeyError(f"Key path '{key_path}' not found")
    del parent[final_key]
    return tomlkit.dumps(data)

"""TOML manipulation utilities.

Since yq cannot write TOML (only read), we use tomlkit for TOML write operations.
tomlkit preserves comments and formatting, consistent with our ruamel.yaml approach for YAML.
"""

from collections.abc import MutableMapping
from pathlib import Path
from typing import Any

import tomlkit


def set_toml_value(file_path: Path, key_path: str, value: Any) -> str:
    """Set a value in a TOML file.

    Args:
        file_path: Path to TOML file
        key_path: Dot-separated key path (e.g., "database.port")
        value: Value to set

    Returns:
        Modified TOML content as string (preserves comments and formatting)
    """
    # Read existing TOML
    content = file_path.read_text(encoding="utf-8")
    data = tomlkit.parse(content)

    # Navigate to the key and set value
    keys = key_path.split(".")
    # TOMLDocument and Table both implement MutableMapping
    current: MutableMapping[str, Any] = data

    # Navigate to parent, creating intermediate tables as needed
    for key in keys[:-1]:
        if key not in current:
            current[key] = {}
        nested = current[key]
        if not isinstance(nested, MutableMapping):
            msg = f"Cannot navigate through non-table value at key '{key}'"
            raise TypeError(msg)
        current = nested

    # Set the final key
    current[keys[-1]] = value

    # Write back (preserves comments and formatting)
    return tomlkit.dumps(data)


def delete_toml_key(file_path: Path, key_path: str) -> str:
    """Delete a key from a TOML file.

    Args:
        file_path: Path to TOML file
        key_path: Dot-separated key path (e.g., "database.port")

    Returns:
        Modified TOML content as string (preserves comments and formatting)
    """
    # Read existing TOML
    content = file_path.read_text(encoding="utf-8")
    data = tomlkit.parse(content)

    # Navigate to the key and delete
    keys = key_path.split(".")
    # TOMLDocument and Table both implement MutableMapping
    current: MutableMapping[str, Any] = data

    # Navigate to parent
    for key in keys[:-1]:
        if key not in current:
            raise KeyError(f"Key path '{key_path}' not found")
        nested = current[key]
        if not isinstance(nested, MutableMapping):
            msg = f"Cannot navigate through non-table value at key '{key}'"
            raise TypeError(msg)
        current = nested

    # Delete the final key
    if keys[-1] not in current:
        raise KeyError(f"Key path '{key_path}' not found")

    del current[keys[-1]]

    # Write back (preserves comments and formatting)
    return tomlkit.dumps(data)

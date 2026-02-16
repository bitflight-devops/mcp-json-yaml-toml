"""Schema directory scanning -- find IDE schema directories from config, environment, and patterns."""

from __future__ import annotations

import logging
import os
from pathlib import Path

import orjson
from strong_typing.exception import JsonKeyError, JsonTypeError, JsonValueError
from strong_typing.serialization import json_to_object

from mcp_json_yaml_toml.schemas.models import DefaultSchemaStores

SCHEMA_STORE_CATALOG_URL = "https://www.schemastore.org/api/json/catalog.json"
CACHE_EXPIRY_SECONDS = 24 * 60 * 60  # 24 hours


def _load_default_ide_patterns() -> list[str]:
    """Load default IDE schema patterns from bundled JSON file.

    Returns:
        List of glob patterns for known IDE schema locations.
    """
    try:
        default_stores_path = (
            Path(__file__).parent.parent / "default_schema_stores.json"
        )
        if default_stores_path.exists():
            raw_data = orjson.loads(default_stores_path.read_bytes())
            stores = json_to_object(DefaultSchemaStores, raw_data)
            return stores.ide_patterns
    except (
        OSError,
        orjson.JSONDecodeError,
        JsonKeyError,
        JsonTypeError,
        JsonValueError,
    ) as e:
        logging.debug("Failed to load default IDE patterns: %s", e)
    return []


def _expand_ide_patterns() -> list[Path]:
    """Expand IDE patterns to actual paths.

    Returns:
        List of existing schema directories from known IDE locations.
    """
    locations: list[Path] = []
    patterns = _load_default_ide_patterns()
    home = Path.home()

    for pattern in patterns:
        # Expand ~ to home directory
        expanded_pattern = pattern.replace("~", str(home))
        pattern_path = Path(expanded_pattern)

        # Handle glob patterns
        if "*" in expanded_pattern:
            parent = pattern_path.parent
            glob_pattern = pattern_path.name
            if parent.exists():
                locations.extend(
                    matched_path
                    for matched_path in parent.glob(glob_pattern)
                    if matched_path.is_dir()
                )
        # Direct path
        elif pattern_path.exists() and pattern_path.is_dir():
            locations.append(pattern_path)

    return locations


def _get_ide_schema_locations() -> list[Path]:
    """Get IDE schema cache locations from config, environment, and patterns.

    Checks config file first, then MCP_SCHEMA_CACHE_DIRS environment variable,
    then known IDE patterns from default_schema_stores.json.

    Returns:
        List of potential schema cache directories.
    """
    locations = []
    home = Path.home()

    # 1. Load from config file
    config_path = (
        home / ".cache" / "mcp-json-yaml-toml" / "schemas" / "schema_config.json"
    )
    if config_path.exists():
        try:
            config = orjson.loads(config_path.read_bytes())
            # Add custom dirs
            for dir_str in config.get("custom_cache_dirs", []):
                dir_path = Path(dir_str)
                if dir_path.exists() and dir_path.is_dir():
                    locations.append(dir_path)
            # Add discovered dirs
            for dir_str in config.get("discovered_dirs", []):
                dir_path = Path(dir_str)
                if dir_path.exists() and dir_path.is_dir():
                    locations.append(dir_path)
        except orjson.JSONDecodeError:
            pass

    # 2. Check environment variable for custom locations
    # Use os.pathsep for cross-platform compatibility (: on Unix, ; on Windows)
    env_dirs = os.getenv("MCP_SCHEMA_CACHE_DIRS")
    if env_dirs:
        for dir_str in env_dirs.split(os.pathsep):
            dir_path = Path(dir_str.strip()).expanduser()
            if dir_path.exists() and dir_path.is_dir():
                locations.append(dir_path)

    # 3. Expand known IDE patterns
    locations.extend(_expand_ide_patterns())

    return locations

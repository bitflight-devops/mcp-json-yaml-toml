"""IDE extension schema discovery -- VS Code extension schema parsing and caching."""

from __future__ import annotations

import contextlib
import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import orjson
from strong_typing.exception import JsonKeyError, JsonTypeError, JsonValueError
from strong_typing.serialization import json_to_object, object_to_json

from mcp_json_yaml_toml.schemas.loading import _match_glob_pattern
from mcp_json_yaml_toml.schemas.models import (
    ExtensionSchemaMapping,
    IDESchemaIndex,
    SchemaInfo,
)
from mcp_json_yaml_toml.schemas.scanning import _expand_ide_patterns

if TYPE_CHECKING:
    from collections.abc import Iterator


def _get_ide_schema_index_path() -> Path:
    """Get the path to the IDE schema index cache file.

    Returns:
        Path to ide_schema_index.json in the cache directory.
    """
    return (
        Path.home()
        / ".cache"
        / "mcp-json-yaml-toml"
        / "schemas"
        / "ide_schema_index.json"
    )


def _extract_validation_mapping(
    validation: dict[str, Any], extension_dir: Path, extension_id: str
) -> ExtensionSchemaMapping | None:
    """Extract schema mapping from a validation entry."""
    file_match = validation.get("fileMatch")
    url = validation.get("url")

    if not file_match or not url:
        return None

    # Normalize fileMatch to always be a list
    if isinstance(file_match, str):
        file_match = [file_match]
    elif not isinstance(file_match, list):
        return None

    # Resolve relative url to absolute path
    if url.startswith("./"):
        schema_path = extension_dir / url[2:]
    elif url.startswith("/"):
        schema_path = Path(url)
    else:
        schema_path = extension_dir / url

    # Only include if the schema file actually exists
    if schema_path.exists():
        return ExtensionSchemaMapping(
            file_match=file_match,
            schema_path=str(schema_path.resolve()),
            extension_id=extension_id,
        )
    return None


def _parse_extension_schemas(extension_dir: Path) -> list[ExtensionSchemaMapping]:
    """Parse a VS Code extension's package.json for schema mappings.

    Extracts `contributes.jsonValidation` and `contributes.yamlValidation`
    entries that map file patterns to bundled schema files.

    Args:
        extension_dir: Path to the extension directory (contains package.json).

    Returns:
        List of ExtensionSchemaMapping objects for discovered schemas.
    """
    mappings: list[ExtensionSchemaMapping] = []
    package_json = extension_dir / "package.json"

    if not package_json.exists():
        return mappings

    try:
        data = orjson.loads(package_json.read_bytes())
    except (OSError, orjson.JSONDecodeError):
        return mappings

    if not isinstance(data, dict):
        return mappings

    # Extract extension ID from directory name or package.json
    extension_id = data.get("publisher", "")
    extension_name = data.get("name", "")
    if extension_id and extension_name:
        extension_id = f"{extension_id}.{extension_name}"
    else:
        # Fallback to directory name (e.g., "davidanson.vscode-markdownlint-0.60.0")
        extension_id = (
            extension_dir.name.rsplit("-", 2)[0]
            if "-" in extension_dir.name
            else extension_dir.name
        )

    contributes = data.get("contributes", {})
    if not isinstance(contributes, dict):
        return mappings

    # Process both jsonValidation and yamlValidation
    for validation_key in ("jsonValidation", "yamlValidation"):
        validations = contributes.get(validation_key, [])
        if not isinstance(validations, list):
            continue

        for validation in validations:
            if not isinstance(validation, dict):
                continue

            mapping = _extract_validation_mapping(
                validation, extension_dir, extension_id
            )
            if mapping:
                mappings.append(mapping)

    return mappings


def _find_potential_extension_dirs(extension_dirs: list[Path]) -> Iterator[Path]:
    """Yield potential extension directories from a list of roots."""
    for ext_parent in extension_dirs:
        if not ext_parent.exists() or not ext_parent.is_dir():
            continue

        # Check if this is an extension directory itself (has package.json)
        if (ext_parent / "package.json").exists():
            yield ext_parent
        else:
            # Scan subdirectories for extensions
            try:
                for subdir in ext_parent.iterdir():
                    if subdir.is_dir() and (subdir / "package.json").exists():
                        yield subdir
            except OSError:
                pass


def _build_ide_schema_index(extension_dirs: list[Path]) -> IDESchemaIndex:
    """Build index of schemas from IDE extensions.

    Scans provided directories for extensions with package.json that define
    jsonValidation or yamlValidation.

    Args:
        extension_dirs: List of IDE extension parent directories to scan
                       (e.g., ~/.antigravity/extensions/).

    Returns:
        IDESchemaIndex containing all discovered schema mappings.
    """
    all_mappings: list[ExtensionSchemaMapping] = []
    extension_mtimes: dict[str, float] = {}

    for ext_dir in _find_potential_extension_dirs(extension_dirs):
        mappings = _parse_extension_schemas(ext_dir)
        all_mappings.extend(mappings)
        with contextlib.suppress(OSError):
            extension_mtimes[str(ext_dir)] = ext_dir.stat().st_mtime

    return IDESchemaIndex(
        mappings=all_mappings,
        extension_mtimes=extension_mtimes,
        last_built=datetime.datetime.now(datetime.UTC).isoformat(),
    )


class IDESchemaProvider:
    """Manages discovery and caching of IDE extension schemas."""

    def __init__(self) -> None:
        """Initialize the IDE schema provider."""
        self._cache: IDESchemaIndex | None = None

    def get_index(self) -> IDESchemaIndex:
        """Get the IDE schema index, building and caching as needed."""
        # Try to use in-memory cache first
        if self._cache is not None:
            return self._cache

        # Try to load from disk cache
        index = self._load_index()
        if index is not None:
            self._cache = index
            return index

        # Build fresh index from IDE extension directories
        extension_dirs = _expand_ide_patterns()
        index = _build_ide_schema_index(extension_dirs)

        # Save to disk cache
        self._save_index(index)
        self._cache = index

        return index

    def lookup_schema(self, filename: str, file_path: Path) -> SchemaInfo | None:
        """Look up schema info from IDE extension index.

        Args:
            filename: Base filename to match against patterns.
            file_path: Full path for glob pattern matching.

        Returns:
            SchemaInfo with name, url (file://), and source if found.
        """
        index = self.get_index()

        for mapping in index.mappings:
            for pattern in mapping.file_match:
                # Check exact filename match first (fast path)
                if filename == pattern:
                    return SchemaInfo(
                        name=mapping.extension_id,
                        url=f"file://{mapping.schema_path}",
                        source="ide",
                    )
                # Check glob pattern match
                if _match_glob_pattern(file_path, pattern):
                    return SchemaInfo(
                        name=mapping.extension_id,
                        url=f"file://{mapping.schema_path}",
                        source="ide",
                    )

        return None

    def _load_index(self) -> IDESchemaIndex | None:
        """Load IDE schema index from cache if valid."""
        index_path = _get_ide_schema_index_path()
        if not index_path.exists():
            return None

        try:
            raw_data = orjson.loads(index_path.read_bytes())
            index = json_to_object(IDESchemaIndex, raw_data)
        except (
            OSError,
            orjson.JSONDecodeError,
            JsonKeyError,
            JsonTypeError,
            JsonValueError,
        ):
            return None

        # Check if any extension directories have changed
        for ext_dir_str, cached_mtime in index.extension_mtimes.items():
            ext_dir = Path(ext_dir_str)
            if not ext_dir.exists():
                return None  # Directory removed, rebuild
            try:
                current_mtime = ext_dir.stat().st_mtime
                if current_mtime != cached_mtime:
                    return None  # Directory changed, rebuild
            except OSError:
                return None

        return index

    def _save_index(self, index: IDESchemaIndex) -> None:
        """Save IDE schema index to cache file."""
        index_path = _get_ide_schema_index_path()
        index_path.parent.mkdir(parents=True, exist_ok=True)
        index_path.write_bytes(
            orjson.dumps(object_to_json(index), option=orjson.OPT_INDENT_2)
        )

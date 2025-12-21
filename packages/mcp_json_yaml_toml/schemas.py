"""Schema management module for MCP server.

Handles automatic schema discovery via Schema Store and local caching.
"""

import contextlib
import datetime
import fnmatch
import logging
import os
import re
import time
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Annotated, Any

import httpx
import orjson
import tomlkit
from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError
from strong_typing.auxiliary import Alias
from strong_typing.core import Schema
from strong_typing.exception import JsonKeyError, JsonTypeError, JsonValueError
from strong_typing.serialization import json_to_object, object_to_json
from tomlkit.exceptions import ParseError, TOMLKitError


@dataclass
class SchemaInfo:
    """Schema metadata information."""

    name: str
    url: str
    source: str


# Dataclasses for known JSON structures - strong_typing handles deserialization
@dataclass
class SchemaEntry:
    """A single schema entry from Schema Store catalog."""

    name: str = ""
    url: str = ""
    description: str = ""
    fileMatch: list[str] = field(default_factory=list)
    versions: dict[str, str] = field(default_factory=dict)


@dataclass
class SchemaCatalog:
    """Schema Store catalog structure."""

    schemas: list[SchemaEntry] = field(default_factory=list)
    version: int = 1
    schema_ref: Annotated[str, Alias("$schema")] = ""


@dataclass
class FileAssociation:
    """Association between a file and a schema URL."""

    schema_url: str = ""
    source: str = "user"


@dataclass
class SchemaConfig:
    """Local schema configuration structure."""

    file_associations: dict[str, FileAssociation] = field(default_factory=dict)
    custom_cache_dirs: list[str] = field(default_factory=list)
    custom_catalogs: dict[str, str] = field(default_factory=dict)
    discovered_dirs: list[str] = field(default_factory=list)
    last_scan: str | None = None


@dataclass
class DefaultSchemaStores:
    """Default schema stores configuration."""

    ide_patterns: list[str] = field(default_factory=list)


@dataclass
class ExtensionSchemaMapping:
    """A file match pattern → local schema path mapping from an IDE extension."""

    file_match: list[str]
    schema_path: str  # Absolute path to local schema file
    extension_id: str  # e.g., "davidanson.vscode-markdownlint"


@dataclass
class IDESchemaIndex:
    """Cached index of schemas discovered from IDE extensions."""

    mappings: list[ExtensionSchemaMapping] = field(default_factory=list)
    extension_mtimes: dict[str, float] = field(default_factory=dict)
    last_built: str | None = None


SCHEMA_STORE_CATALOG_URL = "https://www.schemastore.org/api/json/catalog.json"
CACHE_EXPIRY_SECONDS = 24 * 60 * 60  # 24 hours

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


def _load_default_ide_patterns() -> list[str]:
    """Load default IDE schema patterns from bundled JSON file.

    Returns:
        List of glob patterns for known IDE schema locations.
    """
    try:
        default_stores_path = Path(__file__).parent / "default_schema_stores.json"
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
        logging.debug(f"Failed to load default IDE patterns: {e}")
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
    env_dirs = os.getenv("MCP_SCHEMA_CACHE_DIRS")
    if env_dirs:
        for dir_str in env_dirs.split(":"):
            dir_path = Path(dir_str.strip()).expanduser()
            if dir_path.exists() and dir_path.is_dir():
                locations.append(dir_path)

    # 3. Expand known IDE patterns
    locations.extend(_expand_ide_patterns())

    return locations


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


class SchemaManager:
    """Manages JSON schemas with local caching and Schema Store integration."""

    config: SchemaConfig
    _ide_provider: IDESchemaProvider

    def __init__(self, cache_dir: Path | None = None) -> None:
        """Initialize schema manager.

        Args:
            cache_dir: Optional custom cache directory. Defaults to ~/.cache/mcp-json-yaml-toml/schemas
        """
        if cache_dir:
            self.cache_dir = cache_dir
        else:
            self.cache_dir = Path.home() / ".cache" / "mcp-json-yaml-toml" / "schemas"

        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.catalog_path = self.cache_dir / "catalog.json"
        self.config_path = self.cache_dir / "schema_config.json"
        self.config = self._load_config()
        self._ide_provider = IDESchemaProvider()

    def _load_config(self) -> SchemaConfig:
        """Load schema configuration from file.

        Returns:
            Typed SchemaConfig dataclass.
        """
        if self.config_path.exists():
            try:
                raw_data = orjson.loads(self.config_path.read_bytes())
                return json_to_object(SchemaConfig, raw_data)
            except (
                orjson.JSONDecodeError,
                JsonKeyError,
                JsonTypeError,
                JsonValueError,
            ) as e:
                logging.debug(f"Failed to load schema config: {e}")

        # Return default empty config
        return SchemaConfig()

    def _save_config(self) -> None:
        """Save schema configuration to file."""
        self.config_path.write_bytes(
            orjson.dumps(object_to_json(self.config), option=orjson.OPT_INDENT_2)
        )

    def get_catalog(self) -> SchemaCatalog | None:
        """Get the Schema Store catalog as a typed SchemaCatalog dataclass.

        Returns:
            SchemaCatalog dataclass if available, None if fetch fails and no cache exists.
        """
        raw_catalog = self._get_raw_catalog()
        if raw_catalog is None:
            return None
        try:
            return json_to_object(SchemaCatalog, raw_catalog)
        except (JsonKeyError, JsonTypeError, JsonValueError) as e:
            logging.debug(f"Failed to parse catalog as SchemaCatalog: {e}")
            return None

    def get_ide_provider(self) -> IDESchemaProvider:
        """Get the IDE schema provider instance."""
        return self._ide_provider

    def _try_load_local_schema(self, schema_path: Path) -> Schema | None:
        """Attempt to load a local JSON schema file."""
        if not schema_path.exists():
            return None
        try:
            bytes_data = schema_path.read_bytes()
            if not bytes_data:
                return None
            data = orjson.loads(bytes_data)
        except (OSError, orjson.JSONDecodeError):
            return None

        # Properly narrow the type of the loaded JSON to match Schema
        # We check if it's a dict; for full validation against Schema (dict[str, JsonType])
        # we'd need a recursive check, but proving string keys is a good start.
        if isinstance(data, dict) and all(isinstance(k, str) for k in data):
            return data
        return None

    def get_schema_path_for_file(self, file_path: Path) -> Path | None:
        """Find and return the cached schema file path for a given file.

        This fetches and caches the schema if needed, then returns the path
        to the cached schema file rather than loading it into memory.

        Args:
            file_path: Path to the file to find a schema for.

        Returns:
            Path to the cached schema file if found, None otherwise.
        """
        info = self.get_schema_info_for_file(file_path)
        if not info:
            return None

        url = info.url
        if url.startswith("file://"):
            return Path(url[7:])

        return self._fetch_schema_to_cache(url)

    def get_schema_for_file(self, file_path: Path) -> Schema | None:
        """Find and return the schema for a given file.

        Args:
            file_path: Path to the file to find a schema for.

        Returns:
            Parsed schema dict if found, None otherwise.
        """
        info = self.get_schema_info_for_file(file_path)
        if not info:
            return None

        url = info.url
        if url.startswith("file://"):
            schema_path = Path(url[7:])
            loaded = self._try_load_local_schema(schema_path)
            if loaded is not None:
                return loaded

        return self._fetch_schema(url)

    def _lookup_catalog_schema(self, file_path: Path) -> SchemaInfo | None:
        """Look up schema in the Schema Store catalog."""
        catalog = self.get_catalog()
        if not catalog:
            return None

        filename = file_path.name
        for schema_entry in catalog.schemas:
            for pattern in schema_entry.fileMatch:
                # Check exact filename match first (fast path)
                if filename == pattern:
                    return SchemaInfo(
                        name=schema_entry.name, url=schema_entry.url, source="catalog"
                    )

                # Check glob pattern match
                if _match_glob_pattern(file_path, pattern):
                    return SchemaInfo(
                        name=schema_entry.name, url=schema_entry.url, source="catalog"
                    )
        return None

    def get_schema_info_for_file(self, file_path: Path) -> SchemaInfo | None:
        """Find and return schema information for a given file.

        Args:
            file_path: Path to the file to find a schema for.

        Returns:
            Dict with schema name, url, and source if found, None otherwise.
        """
        # 1. Check file associations first
        file_str = str(file_path.resolve())
        if file_str in self.config.file_associations:
            assoc = self.config.file_associations[file_str]
            return SchemaInfo(
                name="User Association", url=assoc.schema_url, source="user"
            )

        # 2. Check for $schema in content
        content_schema_url = _extract_schema_url_from_content(file_path)
        if content_schema_url:
            return SchemaInfo(
                name="In-file $schema", url=content_schema_url, source="content"
            )

        # 3. Check local IDE schema index
        filename = file_path.name
        ide_result = self._ide_provider.lookup_schema(filename, file_path)
        if ide_result:
            return SchemaInfo(
                name=ide_result.name, url=ide_result.url, source=ide_result.source
            )

        # 4. Check catalog
        return self._lookup_catalog_schema(file_path)

    def add_file_association(
        self, file_path: Path, schema_url: str, schema_name: str | None = None
    ) -> None:
        """Associate a file with a schema URL.

        Args:
            file_path: Path to the file.
            schema_url: URL of the schema.
            schema_name: Optional name of the schema (stored in source field).
        """
        file_str = str(file_path.resolve())
        self.config.file_associations[file_str] = FileAssociation(
            schema_url=schema_url, source=schema_name or "user"
        )
        self._save_config()

    def remove_file_association(self, file_path: Path) -> bool:
        """Remove file-to-schema association.

        Args:
            file_path: Path to the file.

        Returns:
            True if association was removed, False if it didn't exist.
        """
        file_str = str(file_path.resolve())
        if file_str in self.config.file_associations:
            del self.config.file_associations[file_str]
            self._save_config()
            return True
        return False

    def _get_raw_catalog(self) -> Schema | None:
        """Get the Schema Store catalog, using cache if available.

        Returns:
            Parsed catalog dict if available, None if fetch fails and no cache exists.
        """
        if self._is_cache_valid(self.catalog_path):
            try:
                cached: Schema = orjson.loads(self.catalog_path.read_bytes())
            except orjson.JSONDecodeError:
                pass  # Invalid cache, re-fetch
            else:
                return cached

        catalog: Schema | None = None
        try:
            response = httpx.get(SCHEMA_STORE_CATALOG_URL, timeout=10.0)
            response.raise_for_status()
            catalog = response.json()
            self.catalog_path.write_bytes(orjson.dumps(catalog))
        except (
            httpx.HTTPError,
            httpx.TimeoutException,
            OSError,
            orjson.JSONDecodeError,
        ):
            # If fetch fails and we have a stale cache, use it
            if self.catalog_path.exists():
                try:
                    stale: Schema = orjson.loads(self.catalog_path.read_bytes())
                except orjson.JSONDecodeError:
                    pass
                else:
                    return stale
            return None
        return catalog

    def _get_cache_path_for_url(self, url: str) -> Path:
        """Get the cache path for a schema URL.

        Args:
            url: URL of the schema.

        Returns:
            Path where the schema would be cached.
        """
        schema_filename = url.rsplit("/", maxsplit=1)[-1]
        if not schema_filename.endswith(".json"):
            schema_filename += ".json"
        return self.cache_dir / schema_filename

    def _fetch_schema_to_cache(self, url: str) -> Path | None:
        """Fetch a schema and return the cache path.

        Ensures the schema is cached locally and returns the path to the cache file.

        Args:
            url: URL of the schema to fetch.

        Returns:
            Path to the cached schema file, or None if fetch fails.
        """
        cache_path = self._get_cache_path_for_url(url)

        # If cache is valid, return it directly
        if self._is_cache_valid(cache_path):
            return cache_path

        # Try to fetch and cache the schema
        schema = self._fetch_schema(url)
        if schema is not None:
            return cache_path

        # Check if we have a stale cache we can use
        if cache_path.exists():
            return cache_path

        return None

    def _fetch_schema(self, url: str) -> Schema | None:
        """Fetch a schema from a URL, using cache if available.

        Args:
            url: URL of the schema to fetch.

        Returns:
            Parsed schema dict if available, None if fetch fails and no cache exists.
        """
        cache_path = self._get_cache_path_for_url(url)
        schema_filename = cache_path.name

        if self._is_cache_valid(cache_path):
            try:
                cached: Schema = orjson.loads(cache_path.read_bytes())
            except orjson.JSONDecodeError:
                pass
            else:
                return cached

        # Check IDE caches before making network request
        ide_schema = self._fetch_from_ide_cache(schema_filename, schema_url=url)
        if ide_schema:
            # Cache it locally for future use
            cache_path.write_bytes(orjson.dumps(ide_schema))
            return ide_schema

        schema: Schema | None = None
        try:
            response = httpx.get(url, timeout=10.0)
            response.raise_for_status()
            schema = response.json()
            cache_path.write_bytes(orjson.dumps(schema))
        except (
            httpx.HTTPError,
            httpx.TimeoutException,
            OSError,
            orjson.JSONDecodeError,
        ):
            # If fetch fails and we have a stale cache, use it
            if cache_path.exists():
                try:
                    stale: Schema = orjson.loads(cache_path.read_bytes())
                except orjson.JSONDecodeError:
                    pass
                else:
                    return stale
            return None
        return schema

    def _normalize_schema_url(self, url: str) -> str:
        """Normalize schema URL for comparison.

        Handles domain variants between www.schemastore.org and json.schemastore.org.

        Args:
            url: URL to normalize.

        Returns:
            Normalized URL with consistent domain.
        """
        # Normalize www.schemastore.org to json.schemastore.org for comparison
        return url.replace(
            "https://www.schemastore.org/", "https://json.schemastore.org/"
        )

    def _urls_match(self, url1: str, url2: str) -> bool:
        """Check if two schema URLs match, handling domain variants.

        Args:
            url1: First URL to compare.
            url2: Second URL to compare.

        Returns:
            True if URLs match after normalization, False otherwise.
        """
        if url1 == url2:
            return True

        # Normalize both URLs and compare
        normalized1 = self._normalize_schema_url(url1)
        normalized2 = self._normalize_schema_url(url2)

        if normalized1 == normalized2:
            return True

        # Fallback: compare just the filename portion
        filename1 = url1.rsplit("/", maxsplit=1)[-1]
        filename2 = url2.rsplit("/", maxsplit=1)[-1]

        return filename1 == filename2 and filename1.endswith(".json")

    def _search_hash_based_cache(
        self, cache_dir: Path, schema_url: str
    ) -> Schema | None:
        """Search hash-based cache (vscode-yaml style) by checking $id in content.

        Args:
            cache_dir: Directory containing hash-named schema files.
            schema_url: URL to match against schema $id field.

        Returns:
            Parsed schema dict if found, None otherwise.
        """
        if not cache_dir.exists():
            return None

        for cached_file in cache_dir.iterdir():
            if not cached_file.is_file():
                continue
            try:
                content = orjson.loads(cached_file.read_bytes())
                if isinstance(content, dict):
                    schema_id = content.get("$id")
                    if isinstance(schema_id, str) and self._urls_match(
                        schema_id, schema_url
                    ):
                        return content
            except (orjson.JSONDecodeError, OSError):
                continue
        return None

    def _fetch_from_ide_cache(
        self, schema_filename: str, schema_url: str | None = None
    ) -> Schema | None:
        """Try to find schema in IDE cache locations using concurrent checking.

        Searches for schemas by:
        1. Exact filename match (e.g., github-workflow.json)
        2. Schema $id field match for hash-based caches (e.g., vscode-yaml)

        Args:
            schema_filename: Name of the schema file to look for.
            schema_url: Optional URL to look for in hash-based caches.

        Returns:
            Parsed schema dict if found, None otherwise.
        """
        cache_dirs = _get_ide_schema_locations()

        def try_load_schema(cache_dir: Path) -> Schema | None:
            # Try exact filename match first
            schema_path = cache_dir / schema_filename
            if schema_path.exists():
                try:
                    loaded: Schema = orjson.loads(schema_path.read_bytes())
                except orjson.JSONDecodeError:
                    pass
                else:
                    return loaded

            # Try hash-based cache lookup
            if schema_url:
                return self._search_hash_based_cache(cache_dir, schema_url)
            return None

        # Check all directories concurrently
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = {
                executor.submit(try_load_schema, cache_dir): cache_dir
                for cache_dir in cache_dirs
            }

            for future in as_completed(futures):
                result = future.result()
                if result is not None:
                    # Cancel other futures if possible
                    for f in futures:
                        f.cancel()
                    return result

        return None

    def _is_cache_valid(self, path: Path) -> bool:
        """Check if a cached file is valid and not expired.

        Args:
            path: Path to the cached file.

        Returns:
            True if cache exists and is not expired, False otherwise.
        """
        if not path.exists():
            return False

        mtime = path.stat().st_mtime
        age = time.time() - mtime
        return age < CACHE_EXPIRY_SECONDS

    def scan_for_schema_dirs(
        self, search_paths: list[Path], max_depth: int = 5
    ) -> list[Path]:
        """Recursively scan directories for schema caches.

        Args:
            search_paths: List of directories to search.
            max_depth: Maximum directory depth to search.

        Returns:
            List of discovered schema directories.
        """
        discovered = []

        for search_path in search_paths:
            if not search_path.exists() or not search_path.is_dir():
                continue

            # Recursively find schema directories with improved heuristics
            for root, dirs, files in os.walk(search_path):
                # Calculate current depth
                depth = str(root).count(os.sep) - str(search_path).count(os.sep)
                if depth > max_depth:
                    dirs[:] = []  # Don't recurse further
                    continue

                dir_path = Path(root)
                is_schema_dir = False

                # Heuristic 1: Directory is named "schemas" or "jsonSchemas"
                if dir_path.name in {"schemas", "jsonSchemas"}:
                    is_schema_dir = True

                # Heuristic 2: Directory contains catalog.json
                if "catalog.json" in files:
                    is_schema_dir = True

                # Heuristic 3: Directory contains .schema.json files
                if any(f.endswith(".schema.json") for f in files):
                    is_schema_dir = True

                if is_schema_dir and dir_path not in discovered:
                    discovered.append(dir_path)

        # Update config
        self.config.discovered_dirs = [str(p) for p in discovered]
        self.config.last_scan = datetime.datetime.now(datetime.UTC).isoformat()
        self._save_config()

        return discovered

    def add_custom_dir(self, directory: Path) -> None:
        """Add a custom schema cache directory.

        Args:
            directory: Path to schema directory.
        """
        dir_str = str(directory.expanduser().resolve())
        if dir_str not in self.config.custom_cache_dirs:
            self.config.custom_cache_dirs.append(dir_str)
            self._save_config()

    def add_custom_catalog(self, name: str, uri: str) -> None:
        """Add a custom schema catalog.

        Args:
            name: Friendly name for the catalog.
            uri: URL or file path to catalog.json.
        """
        self.config.custom_catalogs[name] = uri
        self._save_config()

    def get_config(self) -> SchemaConfig:
        """Get current schema configuration.

        Returns:
            Current config dataclass.
        """
        return self.config

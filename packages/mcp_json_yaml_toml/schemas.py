"""Schema management module for MCP server.

Handles automatic schema discovery via Schema Store and local caching.
"""

import datetime
import fnmatch
import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import httpx
import orjson

SCHEMA_STORE_CATALOG_URL = "https://www.schemastore.org/api/json/catalog.json"
CACHE_EXPIRY_SECONDS = 24 * 60 * 60  # 24 hours


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
            data: dict[str, Any] = orjson.loads(default_stores_path.read_bytes())
            result: list[str] = data.get("ide_patterns", [])
            return result
    except (OSError, orjson.JSONDecodeError) as e:
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


class SchemaManager:
    """Manages JSON schemas with local caching and Schema Store integration."""

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

    def _load_config(self) -> dict[str, Any]:
        """Load schema configuration from file.

        Returns:
            Configuration dict with custom_cache_dirs, custom_catalogs, etc.
        """
        if self.config_path.exists():
            try:
                config: dict[str, Any] = orjson.loads(self.config_path.read_bytes())
            except orjson.JSONDecodeError:
                pass
            else:
                return config

        # Return default empty config
        return {
            "custom_cache_dirs": [],
            "custom_catalogs": {},
            "discovered_dirs": [],
            "last_scan": None,
        }

    def _save_config(self) -> None:
        """Save schema configuration to file."""
        self.config_path.write_bytes(
            orjson.dumps(self.config, option=orjson.OPT_INDENT_2)
        )

    def get_schema_path_for_file(self, file_path: Path) -> Path | None:
        """Find and return the cached schema file path for a given file.

        This fetches and caches the schema if needed, then returns the path
        to the cached schema file rather than loading it into memory.

        Args:
            file_path: Path to the file to find a schema for.

        Returns:
            Path to the cached schema file if found, None otherwise.
        """
        # 1. Check file associations first (highest priority)
        file_str = str(file_path.resolve())
        file_associations = self.config.get("file_associations", {})
        if file_str in file_associations:
            assoc = file_associations[file_str]
            schema_url = assoc.get("schema_url") if isinstance(assoc, dict) else assoc
            if isinstance(schema_url, str):
                return self._fetch_schema_to_cache(schema_url)

        # 2. Check catalog patterns
        catalog = self._get_catalog()
        if not catalog:
            return None

        filename = file_path.name

        for schema_info in catalog.get("schemas", []):
            if "fileMatch" not in schema_info:
                continue

            for pattern in schema_info["fileMatch"]:
                # Check exact filename match first (fast path)
                if filename == pattern:
                    return self._fetch_schema_to_cache(schema_info["url"])

                # Check glob pattern match
                if _match_glob_pattern(file_path, pattern):
                    return self._fetch_schema_to_cache(schema_info["url"])

        return None

    def get_schema_for_file(self, file_path: Path) -> dict[str, Any] | None:
        """Find and return the schema for a given file.

        Args:
            file_path: Path to the file to find a schema for.

        Returns:
            Parsed schema dict if found, None otherwise.
        """
        # 1. Check file associations first (highest priority)
        file_str = str(file_path.resolve())
        file_associations = self.config.get("file_associations", {})
        if file_str in file_associations:
            assoc = file_associations[file_str]
            schema_url = assoc.get("schema_url") if isinstance(assoc, dict) else assoc
            if isinstance(schema_url, str):
                return self._fetch_schema(schema_url)

        # 2. Check catalog patterns
        catalog = self._get_catalog()
        if not catalog:
            return None

        filename = file_path.name

        for schema_info in catalog.get("schemas", []):
            if "fileMatch" not in schema_info:
                continue

            for pattern in schema_info["fileMatch"]:
                # Check exact filename match first (fast path)
                if filename == pattern:
                    return self._fetch_schema(schema_info["url"])

                # Check glob pattern match
                if _match_glob_pattern(file_path, pattern):
                    return self._fetch_schema(schema_info["url"])

        return None

    def get_schema_info_for_file(self, file_path: Path) -> dict[str, Any] | None:
        """Get schema metadata (name, URL, source) without fetching full schema.

        Args:
            file_path: Path to the file.

        Returns:
            Dict with schema metadata or None if no schema found.
        """
        # 1. Check file associations
        file_str = str(file_path.resolve())
        file_associations = self.config.get("file_associations", {})
        if file_str in file_associations:
            assoc = file_associations[file_str]
            if isinstance(assoc, dict):
                return {
                    "name": assoc.get("schema_name", "unknown"),
                    "url": assoc.get("schema_url"),
                    "source": "file_association",
                }
            # Legacy format: just URL string
            return {"name": "unknown", "url": assoc, "source": "file_association"}

        # 2. Check catalog
        catalog = self._get_catalog()
        if not catalog:
            return None

        filename = file_path.name
        for schema_info in catalog.get("schemas", []):
            if "fileMatch" not in schema_info:
                continue

            for pattern in schema_info["fileMatch"]:
                # Check exact filename match first (fast path)
                if filename == pattern or _match_glob_pattern(file_path, pattern):
                    return {
                        "name": schema_info.get("name", "unknown"),
                        "url": schema_info.get("url"),
                        "source": "catalog",
                    }

        return None

    def add_file_association(
        self, file_path: Path, schema_url: str, schema_name: str | None = None
    ) -> None:
        """Associate a file with a schema URL.

        Args:
            file_path: Path to the file.
            schema_url: URL of the schema.
            schema_name: Optional name of the schema.
        """
        file_str = str(file_path.resolve())
        if "file_associations" not in self.config:
            self.config["file_associations"] = {}

        self.config["file_associations"][file_str] = {
            "schema_url": schema_url,
            "schema_name": schema_name or "unknown",
        }
        self._save_config()

    def remove_file_association(self, file_path: Path) -> bool:
        """Remove file-to-schema association.

        Args:
            file_path: Path to the file.

        Returns:
            True if association was removed, False if it didn't exist.
        """
        file_str = str(file_path.resolve())
        file_associations = self.config.get("file_associations", {})
        if file_str in file_associations:
            del file_associations[file_str]
            self._save_config()
            return True
        return False

    def _get_catalog(self) -> dict[str, Any] | None:
        """Get the Schema Store catalog, using cache if available.

        Returns:
            Parsed catalog dict if available, None if fetch fails and no cache exists.
        """
        if self._is_cache_valid(self.catalog_path):
            try:
                cached: dict[str, Any] = orjson.loads(self.catalog_path.read_bytes())
            except orjson.JSONDecodeError:
                pass  # Invalid cache, re-fetch
            else:
                return cached

        catalog: dict[str, Any] | None = None
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
                    stale: dict[str, Any] = orjson.loads(self.catalog_path.read_bytes())
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

    def _fetch_schema(self, url: str) -> dict[str, Any] | None:
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
                cached: dict[str, Any] = orjson.loads(cache_path.read_bytes())
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

        schema: dict[str, Any] | None = None
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
                    stale: dict[str, Any] = orjson.loads(cache_path.read_bytes())
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
    ) -> dict[str, Any] | None:
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
    ) -> dict[str, Any] | None:
        """Try to find schema in IDE cache locations using concurrent checking.

        Searches for schemas by:
        1. Exact filename match (e.g., github-workflow.json)
        2. Schema $id field match for hash-based caches (e.g., vscode-yaml)

        Args:
            schema_filename: Name of the schema file to look for.
            schema_url: Optional URL to match against schema $id field.

        Returns:
            Parsed schema dict if found, None otherwise.
        """
        cache_dirs = _get_ide_schema_locations()

        def try_load_schema(cache_dir: Path) -> dict[str, Any] | None:
            # Try exact filename match first
            schema_path = cache_dir / schema_filename
            if schema_path.exists():
                try:
                    loaded: dict[str, Any] = orjson.loads(schema_path.read_bytes())
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
        self.config["discovered_dirs"] = [str(p) for p in discovered]
        self.config["last_scan"] = datetime.datetime.now(datetime.UTC).isoformat()
        self._save_config()

        return discovered

    def add_custom_dir(self, directory: Path) -> None:
        """Add a custom schema cache directory.

        Args:
            directory: Path to schema directory.
        """
        dir_str = str(directory.expanduser().resolve())
        if dir_str not in self.config["custom_cache_dirs"]:
            self.config["custom_cache_dirs"].append(dir_str)
            self._save_config()

    def add_custom_catalog(self, name: str, uri: str) -> None:
        """Add a custom schema catalog.

        Args:
            name: Friendly name for the catalog.
            uri: URL or file path to catalog.json.
        """
        self.config["custom_catalogs"][name] = uri
        self._save_config()

    def get_config(self) -> dict[str, Any]:
        """Get current schema configuration.

        Returns:
            Copy of current config dict.
        """
        return self.config.copy()

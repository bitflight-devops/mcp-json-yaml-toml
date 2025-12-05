"""Tests for schema management module."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

from mcp_json_yaml_toml.schemas import (
    SchemaManager,
    _expand_ide_patterns,
    _get_ide_schema_locations,
    _load_default_ide_patterns,
)

if TYPE_CHECKING:
    import pytest


class TestLoadDefaultIdePatterns:
    """Tests for _load_default_ide_patterns function."""

    def test_loads_patterns_from_bundled_file(self) -> None:
        """Verify patterns are loaded from default_schema_stores.json."""
        patterns = _load_default_ide_patterns()

        assert isinstance(patterns, list)
        # The bundled file should have patterns
        assert len(patterns) > 0
        # All patterns should be strings
        assert all(isinstance(p, str) for p in patterns)

    def test_patterns_contain_home_expansion(self) -> None:
        """Verify patterns use ~ for home directory."""
        patterns = _load_default_ide_patterns()

        # At least some patterns should start with ~
        home_patterns = [p for p in patterns if p.startswith("~")]
        assert len(home_patterns) > 0


class TestExpandIdePatterns:
    """Tests for _expand_ide_patterns function."""

    def test_returns_empty_when_no_matching_paths(self, tmp_path: Path) -> None:
        """Verify empty list when no IDE paths exist."""
        # The default patterns won't match in a fresh tmp_path
        # This tests the function doesn't crash when paths don't exist
        locations = _expand_ide_patterns()

        assert isinstance(locations, list)
        # All returned items should be Path objects
        assert all(isinstance(p, Path) for p in locations)

    def test_expands_glob_patterns(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify glob patterns are expanded correctly."""
        # Create a directory structure matching a glob pattern
        schema_dir = tmp_path / "schemas"
        schema_dir.mkdir()

        # Mock _load_default_ide_patterns to return our test pattern
        test_pattern = str(tmp_path / "schemas")
        monkeypatch.setattr(
            "mcp_json_yaml_toml.schemas._load_default_ide_patterns",
            lambda: [test_pattern],
        )

        locations = _expand_ide_patterns()

        assert schema_dir in locations

    def test_expands_wildcard_patterns(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify wildcard patterns match multiple directories."""
        # Create multiple matching directories
        for name in ["schema1", "schema2", "schema3"]:
            (tmp_path / name).mkdir()

        # Pattern with wildcard
        test_pattern = str(tmp_path / "schema*")
        monkeypatch.setattr(
            "mcp_json_yaml_toml.schemas._load_default_ide_patterns",
            lambda: [test_pattern],
        )

        locations = _expand_ide_patterns()

        assert len(locations) == 3


class TestGetIdeSchemaLocations:
    """Tests for _get_ide_schema_locations function."""

    def test_includes_env_var_paths(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify MCP_SCHEMA_CACHE_DIRS paths are included."""
        schema_dir = tmp_path / "custom_schemas"
        schema_dir.mkdir()

        monkeypatch.setenv("MCP_SCHEMA_CACHE_DIRS", str(schema_dir))
        # Clear IDE patterns to isolate env var behavior
        monkeypatch.setattr("mcp_json_yaml_toml.schemas._expand_ide_patterns", list)

        locations = _get_ide_schema_locations()

        assert schema_dir in locations

    def test_includes_multiple_env_var_paths(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify multiple colon-separated paths are all included."""
        dir1 = tmp_path / "schemas1"
        dir2 = tmp_path / "schemas2"
        dir1.mkdir()
        dir2.mkdir()

        monkeypatch.setenv("MCP_SCHEMA_CACHE_DIRS", f"{dir1}:{dir2}")
        monkeypatch.setattr("mcp_json_yaml_toml.schemas._expand_ide_patterns", list)

        locations = _get_ide_schema_locations()

        assert dir1 in locations
        assert dir2 in locations

    def test_ignores_nonexistent_env_paths(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify nonexistent paths from env var are ignored."""
        nonexistent = tmp_path / "does_not_exist"

        monkeypatch.setenv("MCP_SCHEMA_CACHE_DIRS", str(nonexistent))
        monkeypatch.setattr("mcp_json_yaml_toml.schemas._expand_ide_patterns", list)

        locations = _get_ide_schema_locations()

        assert nonexistent not in locations

    def test_loads_from_config_file(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify paths are loaded from schema_config.json."""
        # Create cache directory structure
        cache_dir = tmp_path / ".cache" / "mcp-json-yaml-toml" / "schemas"
        cache_dir.mkdir(parents=True)

        # Create a custom schema directory
        custom_dir = tmp_path / "my_schemas"
        custom_dir.mkdir()

        # Write config file
        config = {"custom_cache_dirs": [str(custom_dir)], "discovered_dirs": []}
        config_path = cache_dir / "schema_config.json"
        config_path.write_text(json.dumps(config))

        # Mock Path.home() to return tmp_path
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        monkeypatch.delenv("MCP_SCHEMA_CACHE_DIRS", raising=False)
        monkeypatch.setattr("mcp_json_yaml_toml.schemas._expand_ide_patterns", list)

        locations = _get_ide_schema_locations()

        assert custom_dir in locations


class TestSchemaManagerFetchFromIdeCache:
    """Tests for SchemaManager._fetch_from_ide_cache method."""

    def test_finds_schema_in_ide_cache(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify schema is found when present in IDE cache."""
        # Create cache directory with schema
        cache_dir = tmp_path / "ide_cache"
        cache_dir.mkdir()

        schema_data = {"type": "object", "properties": {"name": {"type": "string"}}}
        schema_file = cache_dir / "test.schema.json"
        schema_file.write_text(json.dumps(schema_data))

        # Mock _get_ide_schema_locations to return our cache dir
        monkeypatch.setattr(
            "mcp_json_yaml_toml.schemas._get_ide_schema_locations", lambda: [cache_dir]
        )

        manager = SchemaManager(cache_dir=tmp_path / "manager_cache")
        result = manager._fetch_from_ide_cache("test.schema.json")

        assert result is not None
        assert result["type"] == "object"

    def test_returns_none_when_schema_not_found(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify None returned when schema not in any cache."""
        cache_dir = tmp_path / "empty_cache"
        cache_dir.mkdir()

        monkeypatch.setattr(
            "mcp_json_yaml_toml.schemas._get_ide_schema_locations", lambda: [cache_dir]
        )

        manager = SchemaManager(cache_dir=tmp_path / "manager_cache")
        result = manager._fetch_from_ide_cache("nonexistent.schema.json")

        assert result is None

    def test_handles_invalid_json_in_cache(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify invalid JSON files are skipped gracefully."""
        cache_dir = tmp_path / "bad_cache"
        cache_dir.mkdir()

        # Write invalid JSON
        bad_schema = cache_dir / "bad.schema.json"
        bad_schema.write_text("{ not valid json")

        monkeypatch.setattr(
            "mcp_json_yaml_toml.schemas._get_ide_schema_locations", lambda: [cache_dir]
        )

        manager = SchemaManager(cache_dir=tmp_path / "manager_cache")
        result = manager._fetch_from_ide_cache("bad.schema.json")

        # Should return None, not raise
        assert result is None

    def test_searches_multiple_cache_directories(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify all cache directories are searched."""
        # First cache - empty
        cache1 = tmp_path / "cache1"
        cache1.mkdir()

        # Second cache - has schema
        cache2 = tmp_path / "cache2"
        cache2.mkdir()
        schema_data = {"type": "string"}
        (cache2 / "found.schema.json").write_text(json.dumps(schema_data))

        monkeypatch.setattr(
            "mcp_json_yaml_toml.schemas._get_ide_schema_locations",
            lambda: [cache1, cache2],
        )

        manager = SchemaManager(cache_dir=tmp_path / "manager_cache")
        result = manager._fetch_from_ide_cache("found.schema.json")

        assert result is not None
        assert result["type"] == "string"

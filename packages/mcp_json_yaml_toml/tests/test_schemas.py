"""Tests for schema management module."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import TYPE_CHECKING

from mcp_json_yaml_toml.schemas import (
    SchemaManager,
    _build_ide_schema_index,
    _expand_ide_patterns,
    _get_ide_schema_locations,
    _load_default_ide_patterns,
)

if TYPE_CHECKING:
    import pytest


class TestLoadDefaultIdePatterns:
    """Tests for _load_default_ide_patterns function."""

    def test_load_default_ide_patterns_when_called_then_returns_nonempty_list(
        self,
    ) -> None:
        """Verify patterns are loaded from default_schema_stores.json."""
        patterns = _load_default_ide_patterns()

        assert isinstance(patterns, list)
        # The bundled file should have patterns
        assert len(patterns) > 0
        # All patterns should be strings
        assert all(isinstance(p, str) for p in patterns)

    def test_load_default_ide_patterns_when_called_then_contains_home_expansion(
        self,
    ) -> None:
        """Verify patterns use ~ for home directory."""
        patterns = _load_default_ide_patterns()

        # At least some patterns should start with ~
        home_patterns = [p for p in patterns if p.startswith("~")]
        assert len(home_patterns) > 0


class TestExpandIdePatterns:
    """Tests for _expand_ide_patterns function."""

    def test_expand_ide_patterns_when_no_matching_paths_then_returns_list(
        self, tmp_path: Path
    ) -> None:
        """Verify empty list when no IDE paths exist."""
        # The default patterns won't match in a fresh tmp_path
        # This tests the function doesn't crash when paths don't exist
        locations = _expand_ide_patterns()

        assert isinstance(locations, list)
        # All returned items should be Path objects
        assert all(isinstance(p, Path) for p in locations)

    def test_expand_ide_patterns_when_glob_pattern_then_expands_correctly(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify glob patterns are expanded correctly."""
        # Create a directory structure matching a glob pattern
        schema_dir = tmp_path / "schemas"
        schema_dir.mkdir()

        # Mock _load_default_ide_patterns to return our test pattern
        test_pattern = str(tmp_path / "schemas")
        monkeypatch.setattr(
            "mcp_json_yaml_toml.schemas.scanning._load_default_ide_patterns",
            lambda: [test_pattern],
        )

        locations = _expand_ide_patterns()

        assert schema_dir in locations

    def test_expand_ide_patterns_when_wildcard_then_matches_multiple(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify wildcard patterns match multiple directories."""
        # Create multiple matching directories
        for name in ["schema1", "schema2", "schema3"]:
            (tmp_path / name).mkdir()

        # Pattern with wildcard
        test_pattern = str(tmp_path / "schema*")
        monkeypatch.setattr(
            "mcp_json_yaml_toml.schemas.scanning._load_default_ide_patterns",
            lambda: [test_pattern],
        )

        locations = _expand_ide_patterns()

        assert len(locations) == 3


class TestGetIdeSchemaLocations:
    """Tests for _get_ide_schema_locations function."""

    def test_get_ide_schema_locations_when_env_var_set_then_includes_paths(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify MCP_SCHEMA_CACHE_DIRS paths are included."""
        schema_dir = tmp_path / "custom_schemas"
        schema_dir.mkdir()

        monkeypatch.setenv("MCP_SCHEMA_CACHE_DIRS", str(schema_dir))
        # Clear IDE patterns to isolate env var behavior
        monkeypatch.setattr(
            "mcp_json_yaml_toml.schemas.scanning._expand_ide_patterns", list
        )

        locations = _get_ide_schema_locations()

        assert schema_dir in locations

    def test_get_ide_schema_locations_when_multiple_env_paths_then_includes_all(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify multiple paths separated by os.pathsep are all included."""
        dir1 = tmp_path / "schemas1"
        dir2 = tmp_path / "schemas2"
        dir1.mkdir()
        dir2.mkdir()

        # Use os.pathsep for cross-platform compatibility (: on Unix, ; on Windows)
        monkeypatch.setenv("MCP_SCHEMA_CACHE_DIRS", f"{dir1}{os.pathsep}{dir2}")
        monkeypatch.setattr(
            "mcp_json_yaml_toml.schemas.scanning._expand_ide_patterns", list
        )

        locations = _get_ide_schema_locations()

        assert dir1 in locations
        assert dir2 in locations

    def test_get_ide_schema_locations_when_nonexistent_path_then_ignores(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify nonexistent paths from env var are ignored."""
        nonexistent = tmp_path / "does_not_exist"

        monkeypatch.setenv("MCP_SCHEMA_CACHE_DIRS", str(nonexistent))
        monkeypatch.setattr(
            "mcp_json_yaml_toml.schemas.scanning._expand_ide_patterns", list
        )

        locations = _get_ide_schema_locations()

        assert nonexistent not in locations

    def test_get_ide_schema_locations_when_config_file_exists_then_loads_paths(
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
        monkeypatch.setattr(
            "mcp_json_yaml_toml.schemas.scanning._expand_ide_patterns", list
        )

        locations = _get_ide_schema_locations()

        assert custom_dir in locations


class TestSchemaManagerFetchFromIdeCache:
    """Tests for SchemaManager._fetch_from_ide_cache method."""

    def test_fetch_from_ide_cache_when_schema_present_then_returns_schema(
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
            "mcp_json_yaml_toml.schemas.manager._get_ide_schema_locations",
            lambda: [cache_dir],
        )

        manager = SchemaManager(cache_dir=tmp_path / "manager_cache")
        result = manager._fetch_from_ide_cache("test.schema.json")

        assert result is not None
        assert result["type"] == "object"

    def test_fetch_from_ide_cache_when_schema_missing_then_returns_none(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify None returned when schema not in any cache."""
        cache_dir = tmp_path / "empty_cache"
        cache_dir.mkdir()

        monkeypatch.setattr(
            "mcp_json_yaml_toml.schemas.manager._get_ide_schema_locations",
            lambda: [cache_dir],
        )

        manager = SchemaManager(cache_dir=tmp_path / "manager_cache")
        result = manager._fetch_from_ide_cache("nonexistent.schema.json")

        assert result is None

    def test_fetch_from_ide_cache_when_invalid_json_then_returns_none(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify invalid JSON files are skipped gracefully."""
        cache_dir = tmp_path / "bad_cache"
        cache_dir.mkdir()

        # Write invalid JSON
        bad_schema = cache_dir / "bad.schema.json"
        bad_schema.write_text("{ not valid json")

        monkeypatch.setattr(
            "mcp_json_yaml_toml.schemas.manager._get_ide_schema_locations",
            lambda: [cache_dir],
        )

        manager = SchemaManager(cache_dir=tmp_path / "manager_cache")
        result = manager._fetch_from_ide_cache("bad.schema.json")

        # Should return None, not raise
        assert result is None

    def test_fetch_from_ide_cache_when_multiple_dirs_then_searches_all(
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
            "mcp_json_yaml_toml.schemas.manager._get_ide_schema_locations",
            lambda: [cache1, cache2],
        )

        manager = SchemaManager(cache_dir=tmp_path / "manager_cache")
        result = manager._fetch_from_ide_cache("found.schema.json")

        assert result is not None
        assert result["type"] == "string"

    def test_fetch_from_ide_cache_when_domain_variant_then_finds_by_id(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify schema found when $id uses different domain than query URL."""
        # Create hash-based cache directory (vscode-yaml style)
        cache_dir = tmp_path / "ide_cache"
        cache_dir.mkdir()

        # Schema with json.schemastore.org in $id
        schema_data = {
            "$id": "https://json.schemastore.org/github-workflow.json",
            "type": "object",
            "properties": {"name": {"type": "string"}},
        }
        schema_file = cache_dir / "abc123hash"
        schema_file.write_text(json.dumps(schema_data))

        monkeypatch.setattr(
            "mcp_json_yaml_toml.schemas.manager._get_ide_schema_locations",
            lambda: [cache_dir],
        )

        manager = SchemaManager(cache_dir=tmp_path / "manager_cache")

        # Query with www.schemastore.org (catalog URL)
        result = manager._fetch_from_ide_cache(
            "github-workflow.json",
            schema_url="https://www.schemastore.org/github-workflow.json",
        )

        assert result is not None
        assert result["$id"] == "https://json.schemastore.org/github-workflow.json"
        assert result["type"] == "object"

    def test_fetch_from_ide_cache_when_different_domain_then_finds_by_filename(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify schema found by filename when domains differ completely."""
        cache_dir = tmp_path / "ide_cache"
        cache_dir.mkdir()

        # Schema with different base domain
        schema_data = {
            "$id": "https://example.com/schemas/my-schema.json",
            "type": "boolean",
        }
        schema_file = cache_dir / "xyz789hash"
        schema_file.write_text(json.dumps(schema_data))

        monkeypatch.setattr(
            "mcp_json_yaml_toml.schemas.manager._get_ide_schema_locations",
            lambda: [cache_dir],
        )

        manager = SchemaManager(cache_dir=tmp_path / "manager_cache")

        # Query with completely different domain but same filename
        result = manager._fetch_from_ide_cache(
            "my-schema.json", schema_url="https://other-domain.org/my-schema.json"
        )

        assert result is not None
        assert result["type"] == "boolean"


class TestParseExtensionSchemas:
    """Tests for extension schema parsing through _build_ide_schema_index public API."""

    def test_build_ide_schema_index_when_json_validation_then_parses_correctly(
        self, tmp_path: Path
    ) -> None:
        """Verify jsonValidation entries are parsed correctly via _build_ide_schema_index."""
        ext_dir = tmp_path / "my.extension-1.0.0"
        ext_dir.mkdir()

        # Create a schema file
        schema_file = ext_dir / "my-schema.json"
        schema_file.write_text('{"type": "object"}')

        # Create package.json with jsonValidation
        package_json = ext_dir / "package.json"
        package_json.write_text(
            json.dumps({
                "name": "my-extension",
                "publisher": "testpub",
                "contributes": {
                    "jsonValidation": [
                        {"fileMatch": ".myconfig.json", "url": "./my-schema.json"}
                    ]
                },
            })
        )

        index = _build_ide_schema_index([tmp_path])

        assert len(index.mappings) == 1
        assert index.mappings[0].file_match == [".myconfig.json"]
        assert index.mappings[0].schema_path == str(schema_file.resolve())
        assert index.mappings[0].extension_id == "testpub.my-extension"

    def test_build_ide_schema_index_when_array_file_match_then_preserves_array(
        self, tmp_path: Path
    ) -> None:
        """Verify fileMatch arrays are preserved via _build_ide_schema_index."""
        ext_dir = tmp_path / "ext"
        ext_dir.mkdir()
        (ext_dir / "schema.json").write_text("{}")
        (ext_dir / "package.json").write_text(
            json.dumps({
                "name": "ext",
                "publisher": "pub",
                "contributes": {
                    "jsonValidation": [
                        {
                            "fileMatch": [".config1.json", ".config2.json"],
                            "url": "./schema.json",
                        }
                    ]
                },
            })
        )

        index = _build_ide_schema_index([tmp_path])

        assert len(index.mappings) == 1
        assert index.mappings[0].file_match == [".config1.json", ".config2.json"]

    def test_build_ide_schema_index_when_missing_schema_file_then_skips(
        self, tmp_path: Path
    ) -> None:
        """Verify mappings to non-existent schema files are skipped via _build_ide_schema_index."""
        ext_dir = tmp_path / "ext"
        ext_dir.mkdir()
        # No schema file created
        (ext_dir / "package.json").write_text(
            json.dumps({
                "name": "ext",
                "publisher": "pub",
                "contributes": {
                    "jsonValidation": [
                        {"fileMatch": ".config.json", "url": "./missing-schema.json"}
                    ]
                },
            })
        )

        index = _build_ide_schema_index([tmp_path])

        assert len(index.mappings) == 0

    def test_build_ide_schema_index_when_yaml_validation_then_parses_correctly(
        self, tmp_path: Path
    ) -> None:
        """Verify yamlValidation entries are also parsed via _build_ide_schema_index."""
        ext_dir = tmp_path / "ext"
        ext_dir.mkdir()
        (ext_dir / "schema.json").write_text("{}")
        (ext_dir / "package.json").write_text(
            json.dumps({
                "name": "ext",
                "publisher": "pub",
                "contributes": {
                    "yamlValidation": [
                        {"fileMatch": ".myconfig.yaml", "url": "./schema.json"}
                    ]
                },
            })
        )

        index = _build_ide_schema_index([tmp_path])

        assert len(index.mappings) == 1
        assert index.mappings[0].file_match == [".myconfig.yaml"]


class TestLookupIdeSchema:
    """Tests for IDESchemaProvider.lookup_schema method."""

    def test_lookup_schema_when_exact_filename_then_returns_match(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify exact filename matching works."""
        from mcp_json_yaml_toml.schemas import (
            ExtensionSchemaMapping,
            IDESchemaIndex,
            IDESchemaProvider,
        )

        # Mock the index
        mock_index = IDESchemaIndex(
            mappings=[
                ExtensionSchemaMapping(
                    file_match=[".myconfig.json"],
                    schema_path="/path/to/schema.json",
                    extension_id="test.extension",
                )
            ]
        )
        monkeypatch.setattr(IDESchemaProvider, "get_index", lambda self: mock_index)

        provider = IDESchemaProvider()
        result = provider.lookup_schema(".myconfig.json", tmp_path / ".myconfig.json")

        assert result is not None
        assert result.name == "test.extension"
        assert result.url == "file:///path/to/schema.json"
        assert result.source == "ide"

    def test_lookup_schema_when_no_match_then_returns_none(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify None is returned when no patterns match."""
        from mcp_json_yaml_toml.schemas import IDESchemaIndex, IDESchemaProvider

        mock_index = IDESchemaIndex(mappings=[])
        monkeypatch.setattr(IDESchemaProvider, "get_index", lambda self: mock_index)

        provider = IDESchemaProvider()
        result = provider.lookup_schema("unknown.json", tmp_path / "unknown.json")

        assert result is None


class TestIdeSchemaIntegration:
    """Integration tests for IDE schema discovery with SchemaManager."""

    def test_get_schema_info_when_ide_mapping_exists_then_finds_schema(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify IDE schema is found in get_schema_info_for_file lookup chain."""
        from mcp_json_yaml_toml.schemas import (
            ExtensionSchemaMapping,
            IDESchemaIndex,
            IDESchemaProvider,
        )

        # Create a test file without $schema in content
        test_file = tmp_path / ".myconfig.json"
        test_file.write_text('{"key": "value"}')

        # Mock IDE schema index
        mock_index = IDESchemaIndex(
            mappings=[
                ExtensionSchemaMapping(
                    file_match=[".myconfig.json"],
                    schema_path="/path/to/schema.json",
                    extension_id="test.ext",
                )
            ]
        )
        monkeypatch.setattr(IDESchemaProvider, "get_index", lambda self: mock_index)

        manager = SchemaManager(cache_dir=tmp_path / "cache")
        result = manager.get_schema_info_for_file(test_file)

        assert result is not None
        assert result.source == "ide"
        assert result.name == "test.ext"
        assert "file://" in result.url

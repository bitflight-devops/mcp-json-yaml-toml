"""Schema management package -- re-exports all public symbols for backward compatibility.

Modules:
    models: Pure dataclass definitions (SchemaInfo, SchemaEntry, etc.)
    loading: Content extraction functions (_extract_from_json, etc.)
    scanning: Directory scanning helpers (_get_ide_schema_locations, etc.)
    ide_cache: IDE extension schema discovery (IDESchemaProvider, etc.)
    manager: SchemaManager facade class
"""

from __future__ import annotations

from mcp_json_yaml_toml.schemas.ide_cache import (
    IDESchemaProvider,
    _build_ide_schema_index,
    _extract_validation_mapping,
    _find_potential_extension_dirs,
    _get_ide_schema_index_path,
    _parse_extension_schemas,
)
from mcp_json_yaml_toml.schemas.loading import (
    _extract_from_json,
    _extract_from_toml,
    _extract_from_yaml,
    _extract_schema_url_from_content,
    _match_glob_pattern,
    _strip_json_comments,
)
from mcp_json_yaml_toml.schemas.manager import SchemaManager
from mcp_json_yaml_toml.schemas.models import (
    DefaultSchemaStores,
    ExtensionSchemaMapping,
    FileAssociation,
    IDESchemaIndex,
    SchemaCatalog,
    SchemaConfig,
    SchemaEntry,
    SchemaInfo,
)
from mcp_json_yaml_toml.schemas.scanning import (
    CACHE_EXPIRY_SECONDS,
    SCHEMA_STORE_CATALOG_URL,
    _expand_ide_patterns,
    _get_ide_schema_locations,
    _load_default_ide_patterns,
)

__all__ = [
    "CACHE_EXPIRY_SECONDS",
    # scanning
    "SCHEMA_STORE_CATALOG_URL",
    "DefaultSchemaStores",
    "ExtensionSchemaMapping",
    "FileAssociation",
    "IDESchemaIndex",
    "IDESchemaProvider",
    "SchemaCatalog",
    "SchemaConfig",
    "SchemaEntry",
    # models
    "SchemaInfo",
    # manager
    "SchemaManager",
    "_build_ide_schema_index",
    "_expand_ide_patterns",
    "_extract_from_json",
    "_extract_from_toml",
    "_extract_from_yaml",
    "_extract_schema_url_from_content",
    "_extract_validation_mapping",
    "_find_potential_extension_dirs",
    # ide_cache
    "_get_ide_schema_index_path",
    "_get_ide_schema_locations",
    "_load_default_ide_patterns",
    "_match_glob_pattern",
    "_parse_extension_schemas",
    # loading
    "_strip_json_comments",
]

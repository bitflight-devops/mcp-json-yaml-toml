"""Schema data models -- pure dataclass definitions with no business logic."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Annotated

from strong_typing.auxiliary import Alias


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
    """A file match pattern -> local schema path mapping from an IDE extension."""

    file_match: list[str]
    schema_path: str  # Absolute path to local schema file
    extension_id: str  # e.g., "davidanson.vscode-markdownlint"


@dataclass
class IDESchemaIndex:
    """Cached index of schemas discovered from IDE extensions."""

    mappings: list[ExtensionSchemaMapping] = field(default_factory=list)
    extension_mtimes: dict[str, float] = field(default_factory=dict)
    last_built: str | None = None

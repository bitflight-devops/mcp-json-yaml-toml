# Module Dependencies Usage

This document describes each dependency and its specific usage within the MCP JSON/YAML/TOML server.

---

## Core Dependencies

### `fastmcp` (>=0.3.0)

**Purpose**: MCP (Model Context Protocol) server framework

**Usage**:

- `FastMCP` class - Main server instance
- `@mcp.tool()` decorator - Tool registration
- `ToolError` exception - Error handling for tool failures
- Provides the foundation for exposing tools to LLMs via MCP

**Files**: `server.py`, `schemas.py`

---

### `orjson` (>=3.10.0)

**Purpose**: Fast JSON parsing and serialization

**Usage**:

- Parsing JSON values in `data` tool's `set` operation
- High-performance JSON handling for large JSON/YAML/TOML files
- Used instead of stdlib `json` for performance-critical paths

**Files**: `server.py` (line 447: `orjson.loads(value)`)

---

### `ruamel.yaml` (>=0.18.0)

**Purpose**: Advanced YAML processing with anchor/alias support

**Usage**:

- **YAML anchor optimization** - Generates YAML with anchors (`&`) and aliases (`*`)
- Preserves YAML formatting, comments, and structure
- Provides fine-grained control over YAML output
- **Note**: This is the ONLY YAML library used in the codebase

**Files**: `yaml_optimizer.py`

**Why not PyYAML?**:

- PyYAML cannot programmatically create anchors/aliases
- ruamel.yaml offers better round-trip preservation
- ruamel.yaml is a superset of PyYAML functionality

---

### `tomlkit` (>=0.13.0)

**Purpose**: Style-preserving TOML parser and writer

**Usage**:

- Reading and writing TOML files for SET/DELETE operations
- **Critical Feature**: Preserves comments, formatting, and key order
- Consistent with our philosophy of maintaining file fidelity (like `ruamel.yaml`)

**Files**: `toml_utils.py`

**Why tomlkit?**:

- `tomli` is read-only
- `tomli-w` does not preserve comments or formatting
- `tomlkit` provides full round-trip preservation, making the MCP "smart" about existing code styles

---

### `httpx` (>=0.27.0)

**Purpose**: Async HTTP client for fetching schemas

**Usage**:

- Fetching JSON schemas from SchemaStore.org
- Downloading schema catalogs
- Async requests for better performance when validating multiple files

**Files**: `schemas.py` (SchemaManager class)

---

### `lmql` (>=0.7.0)

**Purpose**: Guided generation and input validation

**Usage**:

- `constraint_validate` tool - Partial and complete input validation
- `constraint_list` tool - Listing available steering constraints
- Uses regex derivative technology to provide remaining patterns for continuous generation.

**Files**: `server.py`

---

### `json-strong-typing` (>=0.4.2)

**Purpose**: Enhanced type safety and automated deserialization

**Usage**:

- Modeling structured data in `schemas.py` and `server.py`
- Automatic conversion from JSON dictionaries to Python `@dataclass` instances
- Used for `SchemaConfig`, `SchemaCatalog`, and `IDESchemaIndex`.

**Files**: `schemas.py`, `server.py`

---

### `jsonschema` (>=4.25.1)

**Purpose**: Core schema validation engine

**Usage**:

- Validating files during `data_schema` actions
- **Enforced validation on write** in `data` tool
- Integrated with `referencing` to manage schema registries and avoid legacy auto-fetches.

**Files**: `server.py`, `schemas.py`

---

## External Tool Dependencies

### `yq` (binary)

**Purpose**: Multi-format data manipulation and transformation

**Usage**:

- Primary engine for `data_query` and `data_convert`
- Handles complex path expressions and format translations
- JIT asset: Auto-downloaded and managed via `yq_wrapper.py`.

---

## Summary

| Dependency           | Purpose                        | Status             |
| -------------------- | ------------------------------ | ------------------ |
| `fastmcp`            | MCP server framework           | ❌ Core            |
| `orjson`             | Fast JSON parsing              | ❌ Core            |
| `ruamel.yaml`        | YAML anchor optimization       | ❌ Core            |
| `tomlkit`            | Style-preserving TOML          | ❌ Core            |
| `lmql`               | Guided generation              | ❌ Core            |
| `json-strong-typing` | Type safety & dataclasses      | ❌ Core            |
| `jsonschema`         | Schema validation              | ❌ Core            |
| `referencing`        | Schema registry management     | ❌ Core (internal) |
| `yq` (binary)        | Data manipulation & conversion | ❌ Core            |

---

## Dependency Consolidation

### ✅ Standardized: `json-strong-typing`

Replaced manual dictionary validation with strong-typed dataclasses for configuration and schema metadata.

### ✅ Removed: `pyyaml`

Strictly use `ruamel.yaml` for production-grade anchor support.

### ✅ Updated: `jsonschema` & `referencing`

Migrated to modern `Registry` based validation to eliminate deprecated auto-resolving behavior.

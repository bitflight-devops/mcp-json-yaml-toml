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
- High-performance JSON handling for large configuration files
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

## External Tool Dependencies

### `yq` (binary, not Python package)
**Purpose**: Command-line YAML/JSON/TOML processor

**Usage**:
- **Primary data manipulation** - All read/write/query operations
- Format conversion (YAML ↔ JSON ↔ TOML ↔ XML)
- JQ-style querying and transformations
- Bundled as platform-specific binary in `bin/` directory

**Files**: `yq_wrapper.py` (executes binary via subprocess)

**Why yq?**:
- Battle-tested, widely used tool
- Handles edge cases better than pure Python libraries
- Supports multiple formats with consistent interface
- XML support (not available in Python YAML/TOML libs)

---

## Optional Dependencies

### `jsonschema` (optional, imported dynamically)
**Purpose**: JSON Schema validation

**Usage**:
- Validating configuration files against JSON schemas
- Imported only when validation is requested
- Not a hard dependency - gracefully degrades if not installed

**Files**: `server.py` (line 206: `import jsonschema`)

---

## Development Dependencies

See `pyproject.toml` `[project.optional-dependencies]` for:
- `pytest` - Testing framework
- `pytest-cov` - Test coverage
- `pytest-asyncio` - Async test support
- `pytest-mock` - Mocking utilities
- `mypy` - Type checking
- `ruff` - Linting and formatting

---

## Dependency Consolidation Opportunities

### ✅ Removed: `pyyaml`
- **Status**: Removed (not used anywhere)
- **Replaced by**: `ruamel.yaml` (superset functionality)

### ✅ Added: `tomlkit`
- **Status**: Added for TOML write support
- **Reason**: yq cannot write TOML files, and we need to preserve comments
- **Benefit**: Maintains file fidelity (comments, formatting) just like `ruamel.yaml`

### ✅ Minimal Dependencies
- Only 5 core runtime dependencies
- Each serves a distinct, necessary purpose
- No redundancy or overlap

---

## Summary

| Dependency | Purpose | Can Remove? |
|------------|---------|-------------|
| `fastmcp` | MCP server framework | ❌ Core |
| `orjson` | Fast JSON parsing | ❌ Core |
| `ruamel.yaml` | YAML anchor optimization | ❌ Core |
| `tomlkit` | TOML read/write | ❌ Core (yq can't write TOML) |
| `httpx` | Schema fetching | ❌ Core |
| `jsonschema` | Schema validation | ⚠️ Optional |
| `yq` (binary) | Data manipulation | ❌ Core |

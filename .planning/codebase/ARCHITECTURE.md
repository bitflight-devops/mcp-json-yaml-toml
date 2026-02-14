# Architecture

**Analysis Date:** 2026-02-14

## Pattern Overview

**Overall:** Layered MCP (Model Context Protocol) server with unified tool interface

**Key Characteristics:**

- Format-agnostic design supporting JSON, YAML, TOML with pluggable format handling
- Centralized yq binary wrapper for all file transformations
- Schema discovery and validation layer using JSON Schema Store
- LMQL-based constraint validation for input validation and client-side generation
- Streaming/pagination support for large results (10KB chunks)
- Format preservation (comments, anchors, formatting) through specialized libraries

## Layers

**Entry Point (Server Registration):**

- Purpose: FastMCP server initialization and tool registration
- Location: `packages/mcp_json_yaml_toml/server.py` (lines 49-50, main entry point at lines 1874-1880)
- Contains: Tool definitions, resource handlers, prompt generators
- Depends on: All other layers
- Used by: MCP client/orchestrator

**Configuration & Format Layer:**

- Purpose: Parse environment variables, validate enabled formats, normalize format names
- Location: `packages/mcp_json_yaml_toml/config.py`
- Contains: `parse_enabled_formats()`, `is_format_enabled()`, `validate_format()`
- Depends on: FormatType enum from yq_wrapper
- Used by: Server tools to determine which formats are accessible

**Binary Execution Layer (yq Wrapper):**

- Purpose: Cross-platform yq binary management, execution, error handling
- Location: `packages/mcp_json_yaml_toml/yq_wrapper.py`
- Contains: `execute_yq()` function, binary detection/download, YQResult model, FormatType enum
- Depends on: httpx for remote binary downloads, portalocker for file locking
- Used by: Server tools, schema validation, format detection

**Format-Specific Handlers:**

- **TOML Handler**: `packages/mcp_json_yaml_toml/toml_utils.py`
  - Uses tomlkit (preserves comments and formatting)
  - Implements `set_toml_value()` and `delete_toml_key()` since yq cannot write TOML
  - Called from `_set_toml_value_handler()` and `_delete_toml_key_handler()`

- **YAML Handler**: `packages/mcp_json_yaml_toml/yaml_optimizer.py`
  - Detects duplicate structures and creates YAML anchors
  - Implements hashing-based duplicate detection
  - Configurable via env vars: `YAML_ANCHOR_MIN_SIZE`, `YAML_ANCHOR_MIN_DUPLICATES`, `YAML_ANCHOR_OPTIMIZATION`
  - Called from `_optimize_yaml_if_needed()` after write operations

**Schema Management Layer:**

- Purpose: Discover, validate, and cache schemas from Schema Store or local directories
- Location: `packages/mcp_json_yaml_toml/schemas.py`
- Contains: `SchemaManager` class, schema discovery, file associations, catalog management
- Depends on: httpx for Schema Store API, ruamel.yaml and tomlkit for file parsing
- Used by: Server tools for schema retrieval and validation

**Validation & Constraints Layer:**

- Purpose: LMQL-style input validation with partial/incremental checking
- Location: `packages/mcp_json_yaml_toml/lmql_constraints.py`
- Contains: Abstract `Constraint` base class, `ConstraintRegistry`, `ValidationResult` model
- Constraints: YQ_PATH, YQ_EXPRESSION, CONFIG_FORMAT, KEY_PATH, INT, JSON_VALUE, FILE_PATH
- Depends on: lmql library for Regex pattern matching
- Used by: `constraint_validate()` tool, exported via resources at `lmql://constraints`

**Tool Implementation Layer:**

- Purpose: Business logic for CRUD operations on config files
- Location: `packages/mcp_json_yaml_toml/server.py` (lines 1065-1822)
- Contains: Tool functions (`data()`, `data_query()`, `data_schema()`, `data_convert()`, `data_merge()`) and helper handlers
- Depends on: All lower layers
- Used by: MCP client/orchestrator

## Data Flow

**GET Operation (Read):**

1. Client calls `data()` with operation="get"
2. `_dispatch_get_operation()` routes to appropriate handler based on data_type (schema vs data)
3. For data: `_handle_data_get_structure()` or `_handle_data_get_value()`
4. Format detected via `_detect_file_format()` (uses Path.suffix)
5. Format enabled check via `config.is_format_enabled()`
6. `execute_yq()` executes query expression on file
7. Result formatted based on output_format parameter
8. Result paginated if > 10KB via `_paginate_result()`
9. Optional advisory hint added if result spans >2 pages
10. Response includes success, result data, format, file path

**SET Operation (Write):**

1. Client calls `data()` with operation="set"
2. Value parsed based on value_type (string, number, boolean, null, json) via `_parse_set_value()`
3. TOML: delegates to `_set_toml_value_handler()` using tomlkit (preserves formatting)
4. YAML/JSON: executes yq expression with assignment, gets modified content
5. Schema validation via `_validate_and_write_content()` if schema exists
6. File written with validation checked
7. YAML post-processing: `_optimize_yaml_if_needed()` detects anchors and creates them if applicable
8. Response includes success, result message, optimized flag if applicable

**DELETE Operation (Delete):**

1. Client calls `data()` with operation="delete"
2. Format detected and validated
3. TOML: delegates to `_delete_toml_key_handler()` using tomlkit
4. YAML/JSON: executes yq delete expression via `_delete_yq_key_handler()`
5. Result written with schema validation if applicable
6. Response includes success message

**QUERY Operation (Search/Filter):**

1. Client calls `data_query()` with yq expression
2. File format detected, enabled check performed
3. `execute_yq()` executes arbitrary expression
4. Output format auto-falls back from TOML to JSON if yq can't encode nested structures
5. Result paginated if > 10KB
6. Response includes result, format, pagination cursor if applicable

**State Management:**

- In-memory state: SchemaManager singleton holds schema cache and file associations
- File-based state: `.schema-cache/` directory stores downloaded schemas and associations
- No persistent session state; each operation is independent
- Pagination uses opaque base64-encoded cursors with offset (no server-side storage)

## Key Abstractions

**FormatType Enum:**

- Purpose: Strongly-typed format names (JSON, YAML, TOML, XML, CSV, TSV, PROPS)
- Location: `packages/mcp_json_yaml_toml/yq_wrapper.py` (lines 64-73)
- Used by: Config layer, server tools for format validation
- Pattern: StrEnum allows direct string comparison and serialization

**YQResult Model:**

- Purpose: Standardized result container for all yq executions
- Location: `packages/mcp_json_yaml_toml/yq_wrapper.py` (lines 55-62)
- Contains: stdout (str), stderr (str), returncode (int), data (Any for JSON output)
- Pattern: Pydantic model ensures type safety and serialization

**SchemaInfo Dataclass:**

- Purpose: Metadata about discovered schemas (name, URL, source)
- Location: `packages/mcp_json_yaml_toml/schemas.py` (lines 31-37)
- Used by: Server tools to include schema info in responses
- Pattern: Lightweight carrier for schema context

**Constraint Base Class:**

- Purpose: Template for input validation logic with partial matching support
- Location: `packages/mcp_json_yaml_toml/lmql_constraints.py` (lines 68-102)
- Pattern: ABC with ClassVar metadata, static validate() method returns ValidationResult
- Extensions: YQPathConstraint, YQExpressionConstraint, ConfigFormatConstraint, etc.

## Entry Points

**MCP Server Entry Point:**

- Location: `packages/mcp_json_yaml_toml/server.py` line 1874-1880
- Function: `main()`
- Triggers: Command line invocation via `mcp-json-yaml-toml` script (defined in pyproject.toml line 42)
- Responsibilities: Initialize FastMCP server, call `mcp.run()` to start listening

**Tool Entry Points (FastMCP decorated):**

- `data()` (lines 1203-1284): Main CRUD tool, dispatches to operation handlers
- `data_query()` (lines 1065-1140): Query-only (read-only) tool for complex expressions
- `data_schema()` (lines 1455-1528): Schema management operations
- `data_convert()` (lines 1531-1611): Format conversion tool
- `data_merge()` (lines 1614-1718): Deep merge operation

**Resource Entry Points (MCP resources):**

- `lmql://constraints` (line 1726): Returns all constraint definitions
- `lmql://constraints/{name}` (line 1743): Returns specific constraint definition

**Prompt Entry Points (MCP prompts):**

- `explain_config()` (lines 1824-1846): Generates analysis prompt
- `suggest_improvements()` (lines 1849-1859): Generates improvement prompt
- `convert_to_schema()` (lines 1862-1871): Generates schema generation prompt

## Error Handling

**Strategy:** Fail-fast with descriptive error messages for AI context

**Patterns:**

- **Format Validation Errors**: Caught at entry, list enabled formats in error message
  - Example: `"Format 'xml' is not enabled. Enabled formats: json, yaml, toml"`

- **File Not Found**: Caught at operation start, raises ToolError before proceeding

- **Schema Validation Errors**: Caught during write operations, prevents file modification
  - Uses jsonschema validators with $ref resolution
  - Returns tuple of (is_valid, message)

- **yq Execution Errors**: Wrapped in YQExecutionError with stderr for debugging
  - Auto-fallback for TOML output: if nested structures, retry with JSON output
  - Example: `"Set operation failed: {e}"` with full yq error context

- **Pagination Errors**: Invalid cursor raises ToolError with offset details
  - Example: `"Cursor offset 50000 exceeds result size 10000"`

- **Constraint Validation**: Returns ValidationResult with error message and optional hints
  - Supports partial validation: is_partial=True + remaining_pattern for incomplete input

## Cross-Cutting Concerns

**Logging:**

- Uses Python logging module (configured via logger in modules)
- Default log level INFO; modules import logging and create loggers
- Schema manager logs cache operations and discovery
- No centralized logging configuration (relies on application setup)

**Validation:**

- Format validation: `config.validate_format()` normalizes and validates format names
- Schema validation: `_validate_against_schema()` uses Draft7Validator or Draft202012Validator
- Input constraints: `constraint_validate()` uses LMQL regex patterns
- Pagination: `_decode_cursor()` validates base64 and JSON structure before use

**Authentication:**

- No authentication required (100% local processing)
- Optional schema catalog access uses httpx with 10-second timeout
- Binary downloads use checksums for integrity verification

**Pagination:**

- Constants: PAGE_SIZE_CHARS=10000, ADVISORY_PAGE_THRESHOLD=2
- Cursor encoding: base64-encoded JSON with offset field
- Advisory triggers: If result > 2 pages, includes size and suggests optimizations
- Hints: Context-aware hints for lists (slicing, length) and objects (key selection)

**Format Preservation:**

- YAML: ruamel.yaml (typ="safe") preserves comments, anchors, formatting
- TOML: tomlkit for write operations preserves comments and formatting
- JSON: orjson for fast parsing and serialization
- Post-optimization: YAML anchors created after write if duplicates detected

---

_Architecture analysis: 2026-02-14_

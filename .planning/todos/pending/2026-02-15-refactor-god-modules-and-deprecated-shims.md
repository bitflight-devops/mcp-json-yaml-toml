---
created: 2026-02-15T15:54:17.756Z
title: Refactor god modules and deprecated shims
area: services
files:
  - packages/mcp_json_yaml_toml/services/data_operations.py
  - packages/mcp_json_yaml_toml/schemas.py
  - packages/mcp_json_yaml_toml/yq_wrapper.py
  - packages/mcp_json_yaml_toml/server.py:62-101
  - packages/mcp_json_yaml_toml/config.py:13
  - packages/mcp_json_yaml_toml/formats/base.py:17
  - packages/mcp_json_yaml_toml/tools/query.py:22
  - packages/mcp_json_yaml_toml/tools/diff.py:20
  - packages/mcp_json_yaml_toml/tools/convert.py:20
  - packages/mcp_json_yaml_toml/tools/schema.py:15
  - packages/mcp_json_yaml_toml/services/schema_validation.py:21
  - packages/mcp_json_yaml_toml/backends/base.py:67-69
  - packages/mcp_json_yaml_toml/lmql_constraints.py:718-723
---

## Problem

Architectural issues identified by code review:

**C-3. data_operations.py god module (756 lines, 14+ concerns)**: Handles schema resolution, structure summarization, value retrieval, pagination orchestration, TOML/YAML/JSON mutations, query building, and three dispatch functions. SRP violation.

**C-5. Production imports through deprecated yq_wrapper.py shim**: 8 production modules import FormatType, execute_yq through the shim whose docstring says "New code should import directly from backends."

**M-1. server.py re-exports 10 private \_-prefixed symbols in**all\*\*\*\*: Breaks encapsulation conventions.

**M-3. schemas.py::SchemaManager.**init** does filesystem I/O at import time**: mkdir and \_load_config() run during server.py module import.

**M-4. schemas.py::\_fetch_from_ide_cache creates new ThreadPoolExecutor per call**: Should use instance-level executor.

**M-5. TOML fallback logic duplicated**: tools/query.py:92 and data_operations.py:270.

**M-6. tools/schema.py uses module-level singleton**: 8 handler functions access global schema_manager instead of parameter injection.

**M-13. FormatType has unused enum members (CSV, TSV, PROPS)**: No production code uses them.

**M-14. FilePathConstraint.validate always returns valid=True**: Dead regex check at lmql_constraints.py:718-723.

**M-15. schemas.py god module (1201 lines, 7+ responsibilities)**: Needs decomposition.

## Solution

1. Split data_operations.py into: get_operations.py, mutation_operations.py, query_operations.py
2. Split schemas.py into focused sub-modules (schema loading, IDE cache, schema scanning, validation)
3. Migrate 8 production imports from yq_wrapper.py to backends.base / backends.yq
4. Remove private symbols from server.py **all**; update tests to import from originating modules
5. Defer SchemaManager init to first access (lazy initialization)
6. Use instance-level ThreadPoolExecutor in schemas.py
7. Extract TOML fallback to shared helper
8. Accept schema_manager as parameter in tools/schema.py handlers
9. Remove unused FormatType members (CSV, TSV, PROPS) or document as reserved
10. Fix FilePathConstraint.validate dead code

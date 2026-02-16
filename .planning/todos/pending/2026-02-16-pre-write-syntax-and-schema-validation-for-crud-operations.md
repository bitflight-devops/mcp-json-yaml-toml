---
created: 2026-02-16T17:49:48.732Z
title: Pre-write syntax and schema validation for CRUD operations
area: services
source: "GitHub issue #1 (bitflight-devops/mcp-json-yaml-toml)"
files:
  - packages/mcp_json_yaml_toml/services/mutation_operations.py
  - packages/mcp_json_yaml_toml/services/schema_validation.py
  - packages/mcp_json_yaml_toml/tools/data.py
  - packages/mcp_json_yaml_toml/toml_utils.py
  - packages/mcp_json_yaml_toml/schemas/manager.py
---

## Problem

When agents use `data(operation="set")` or `data(operation="delete")` with `in_place=True`, changes are written to disk without validation. This can result in syntactically invalid or schema-non-compliant files.

Current flow: `Agent calls data(operation="set") -> Parse value -> Execute yq/tomlkit -> Write to disk`

Missing: validate syntax and schema compliance of the resulting content BEFORE writing.

## Solution

From GitHub issue #1:

**Phase 1 — Syntax validation:**

- For JSON/YAML: parse modified content with yq before writing
- For TOML: parse modified content with tomlkit before writing

**Phase 2 — Schema validation:**

- Check if schema is available via `SchemaManager.get_schema_for_file()`
- If schema exists, validate using `_validate_against_schema()` before writing
- Return clear error messages on validation failure

**Phase 3 — API enhancement:**

- Add `skip_validation: bool = False` parameter to `data()` tool
- Atomic operation: if validation fails, file is NOT modified

Existing infrastructure to leverage: `_validate_against_schema()` in schema_validation.py, `SchemaManager.get_schema_for_file()` in schemas/manager.py.

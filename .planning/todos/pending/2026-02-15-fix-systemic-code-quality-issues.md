---
created: 2026-02-15T15:54:17.756Z
title: Fix systemic code quality issues
area: services
files:
  - packages/mcp_json_yaml_toml/services/data_operations.py:322-325,419-422,466-469,518-521
  - packages/mcp_json_yaml_toml/services/data_operations.py:130,158,208,298,367,446,471,487,523,539,576,646,687
  - packages/mcp_json_yaml_toml/tools/convert.py:60-63,168-177
  - packages/mcp_json_yaml_toml/tools/diff.py:62-73
  - packages/mcp_json_yaml_toml/tools/query.py:68-71
  - packages/mcp_json_yaml_toml/tools/schema.py:37-41
  - packages/mcp_json_yaml_toml/config.py:79
  - packages/mcp_json_yaml_toml/backends/binary_manager.py:228-595
  - packages/mcp_json_yaml_toml/models/responses.py
---

## Problem

Code review identified 6 critical and 4 major systemic issues across production code:

**C-1. dict[str, Any] returns instead of typed Pydantic models**: 13 handler functions in data_operations.py return raw dicts while DataResponse, MutationResponse, ValidationResponse exist in models/responses.py with \_DictAccessMixin for backward compat. Eliminates compile-time type safety.

**C-2. Duplicated format-enable-check (9 sites)**: Identical 4-line blocks in tools/convert.py, tools/diff.py, tools/query.py, tools/schema.py, services/data_operations.py. Shotgun surgery to change.

**C-4. Broad except Exception with isinstance re-raise (4 sites)**: data_operations.py:322,419,466,518 catches MemoryError/SystemExit and wraps in ToolError.

**C-6. print() for logging in binary_manager.py (16 sites)**: stderr is MCP JSON-RPC transport. print() may interfere with protocol communication.

**M-2. config.py::is_format_enabled() re-parses env var every call**: No caching.

**M-7. yaml_optimizer.py env config crashes on invalid value at import**: int(os.getenv(...)) with no validation.

**M-8. formats/base.py mixed string/enum comparison**: Line 64 uses raw string, line 66 uses mixed set.

**M-9. f-strings in logging.debug()**: schemas.py:290,672,695 -- evaluated even when disabled.

## Solution

1. Extract `require_format_enabled()` to config.py -- eliminates 9-site duplication
2. Migrate 13 data_operations.py handlers to return Pydantic response models
3. Fix except patterns: `except ToolError: raise` / `except Exception:` two-clause or catch specific types
4. Replace print() with logging.getLogger(**name**) in binary_manager.py
5. Add functools.cache to parse_enabled_formats()
6. Wrap yaml_optimizer env parsing in try/except with defaults
7. Normalize formats/base.py to enum comparisons via match-case
8. Use %-style lazy formatting in logging.debug() calls

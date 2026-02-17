---
phase: 02-tool-layer-refactoring
plan: 02
subsystem: api
tags: [refactoring, service-layer, data-operations, extraction]

# Dependency graph
requires:
  - phase: 02-01
    provides: "services/ package with pagination.py, schema_validation.py, and response models"
provides:
  - "services/data_operations.py with all CRUD business logic (15 functions)"
  - "server.py delegates to service layer for data operations"
  - "schema_manager passed as parameter (no globals in service layer)"
affects: [02-03, 02-04]

# Tech tracking
tech-stack:
  added: []
  patterns:
    [
      "service-layer delegation for data CRUD",
      "schema_manager as parameter injection",
    ]

key-files:
  created:
    - "packages/mcp_json_yaml_toml/services/data_operations.py"
  modified:
    - "packages/mcp_json_yaml_toml/server.py"

key-decisions:
  - "schema_manager passed as optional parameter (default None) to all dispatch/handler functions that previously used global"
  - "Re-export _validate_and_write_content and is_schema from server.py for backward compat (noqa: F401)"

patterns-established:
  - "Service functions accept schema_manager as parameter, not global reference"
  - "Re-export pattern: noqa:F401 for backward-compatible re-exports from server.py"

# Metrics
duration: 8min
completed: 2026-02-15
---

# Phase 2 Plan 02: Data Operations Extraction Summary

**Extract 15 data CRUD functions (~680 lines) from server.py into services/data_operations.py with schema_manager parameter injection**

## Performance

- **Duration:** 8 min
- **Started:** 2026-02-15T03:03:52Z
- **Completed:** 2026-02-15T03:12:13Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- Extracted 15 functions (dispatchers, CRUD handlers, query builder, validation, type guard) to services/data_operations.py
- Reduced server.py from 1499 to 819 lines (680-line reduction, 45% smaller)
- Converted schema_manager from global access to parameter injection in all service functions
- All 393 tests pass without modification, mypy and basedpyright clean

## Task Commits

Each task was committed atomically:

1. **Task 1: Create services/data_operations.py with extracted business logic** - `e2157d0` (feat)
2. **Task 2: Update server.py to import from services/data_operations.py** - `df16f9a` (refactor)

## Files Created/Modified

- `packages/mcp_json_yaml_toml/services/data_operations.py` - All data CRUD business logic: dispatchers, get/set/delete handlers, query response builder, write validation, type guard (758 lines, 15 functions)
- `packages/mcp_json_yaml_toml/server.py` - Imports from services.data_operations, passes schema_manager to dispatch functions (819 lines, reduced from 1499)

## Decisions Made

- **schema_manager as optional parameter:** Functions that previously accessed global `schema_manager` now accept it as `schema_manager: SchemaManager | None = None`. This preserves backward compatibility while making dependencies explicit. The `data` tool in server.py passes the module-level `schema_manager` instance to each dispatch call.
- **Re-export for backward compat:** `_validate_and_write_content` and `is_schema` are imported in server.py with `noqa: F401` to maintain backward compatibility for any code importing these from `server.py`. Follows the same pattern established in Plan 02-01 for pagination re-exports.
- **TYPE_CHECKING for Path/SchemaManager/SchemaInfo:** The linter correctly moved `Path`, `SchemaManager`, and `SchemaInfo` imports into `TYPE_CHECKING` block in data_operations.py since `from __future__ import annotations` makes all annotations strings at runtime.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- services/data_operations.py is ready for Plan 03 (tool layer split) to reference
- server.py tool decorators now delegate to service layer, ready for further extraction
- Schema handler functions (_handle_schema_\*) remain in server.py for Plan 03/04 extraction

## Self-Check: PASSED

- FOUND: packages/mcp_json_yaml_toml/services/data_operations.py
- FOUND: .planning/phases/02-tool-layer-refactoring/02-02-SUMMARY.md
- FOUND: e2157d0 (Task 1 commit)
- FOUND: df16f9a (Task 2 commit)

---

_Phase: 02-tool-layer-refactoring_
_Completed: 2026-02-15_

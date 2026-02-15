---
phase: 05-type-safety-and-dry-foundation
plan: 02
subsystem: architecture
tags:
  [type-safety, pydantic, response-models, exception-handling, enum-consistency]

# Dependency graph
requires:
  - phase: 05-01
    provides: DRY utilities (resolve_file_path, require_format_enabled, should_fallback_toml_to_json)
provides:
  - All service handler functions return typed Pydantic models (DataResponse, MutationResponse, SchemaResponse)
  - Specific exception catches replacing broad except Exception blocks
  - FormatType enum-only comparisons across formats/base.py and services/data_operations.py
  - Alias-aware _DictAccessMixin for backward-compatible dict-like access on all response models
affects: [05-03-god-module-splitting, testing-improvements]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Typed Pydantic returns: All CRUD handlers return DataResponse/MutationResponse/SchemaResponse instead of dict[str, Any]"
    - "Specific exception catches: (KeyError, TypeError, ValueError, OSError) instead of broad except Exception with isinstance guards"
    - "FormatType match/case: _parse_content_for_validation normalizes input then uses match/case on FormatType enum"
    - "Runtime type imports for FastMCP: noqa: TC001 on response model imports since FastMCP resolves annotations at decorator time"

key-files:
  created: []
  modified:
    - packages/mcp_json_yaml_toml/services/data_operations.py
    - packages/mcp_json_yaml_toml/formats/base.py
    - packages/mcp_json_yaml_toml/tools/data.py
    - packages/mcp_json_yaml_toml/models/responses.py

key-decisions:
  - "Use union return type DataResponse | SchemaResponse | MutationResponse on data tool instead of common base ToolResponse, because SchemaResponse does not inherit from ToolResponse"
  - "Add _DictAccessMixin to SchemaResponse for backward-compat dict access after removing .model_dump() call in _dispatch_get_operation"
  - "Make _DictAccessMixin alias-aware via _resolve_field_name() to handle SchemaResponse's schema_ field (alias='schema')"
  - "Keep response model imports at runtime in tools/data.py with noqa: TC001 since FastMCP resolves return type annotations at decorator registration time"

patterns-established:
  - "Alias-aware dict mixin: _DictAccessMixin._resolve_field_name() resolves Pydantic field aliases before getattr, preventing collision with BaseModel methods"
  - "Runtime import exemption: FastMCP tool decorators need return type models available at import time, not just TYPE_CHECKING"

# Metrics
duration: 13min
completed: 2026-02-15
---

# Phase 5 Plan 2: Type Safety Migration Summary

**All 13 service handlers migrated from dict[str, Any] to typed Pydantic returns with specific exception catches and enum-only format comparisons**

## Performance

- **Duration:** 13 min
- **Started:** 2026-02-15T20:22:13Z
- **Completed:** 2026-02-15T20:35:14Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

- Migrated all 13 handler/dispatcher functions in data_operations.py from `dict[str, Any]` to `DataResponse`, `MutationResponse`, or `SchemaResponse`
- Replaced 4 broad `except Exception` blocks with specific `(KeyError, TypeError, ValueError, OSError)` catches
- Normalized all format comparisons in base.py and data_operations.py to use `FormatType` enum values
- Rewrote `_parse_content_for_validation` with match/case on normalized FormatType
- Made `_DictAccessMixin` alias-aware to support SchemaResponse backward compatibility

## Task Commits

Each task was committed atomically:

1. **Task 1: Migrate handlers to Pydantic returns and fix exception handling** - `afa4fe0` (feat)
2. **Task 2: Fix FormatType enum consistency in format comparisons** - `6e60cc8` (refactor)

## Files Created/Modified

- `packages/mcp_json_yaml_toml/services/data_operations.py` - All 13 functions return typed Pydantic models; 4 broad exception blocks replaced with specific catches; all string format comparisons replaced with FormatType enum
- `packages/mcp_json_yaml_toml/formats/base.py` - `_parse_content_for_validation` rewritten with match/case on normalized FormatType
- `packages/mcp_json_yaml_toml/tools/data.py` - Return type changed to `DataResponse | SchemaResponse | MutationResponse`; runtime imports for FastMCP decorator
- `packages/mcp_json_yaml_toml/models/responses.py` - `_DictAccessMixin` made alias-aware via `_resolve_field_name()`; `SchemaResponse` gains `_DictAccessMixin` for dict-like access

## Decisions Made

- **Union return type over ToolResponse base:** `SchemaResponse` does not inherit from `ToolResponse`, so the data tool uses `DataResponse | SchemaResponse | MutationResponse` as its return type instead of the common base class.
- **Alias-aware mixin:** Added `_resolve_field_name()` to `_DictAccessMixin` to handle Pydantic field aliases (specifically SchemaResponse's `schema_` field with `alias="schema"`). Without this, `result["schema"]` would return Pydantic's built-in `.schema()` method instead of the field value.
- **Runtime imports with noqa:** FastMCP's `@mcp.tool()` decorator resolves type annotations at registration time via `TypeAdapter`. Response models must be importable at runtime, not just under `TYPE_CHECKING`. Added `noqa: TC001` to prevent ruff from moving them.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Added \_DictAccessMixin to SchemaResponse**

- **Found during:** Task 1 (Pydantic return migration)
- **Issue:** After removing `.model_dump()` call in `_dispatch_get_operation`, `SchemaResponse` was returned directly but lacked dict-like access. Tests using `result["success"]` on schema responses failed with `TypeError: 'SchemaResponse' object is not subscriptable`.
- **Fix:** Added `_DictAccessMixin` as parent of `SchemaResponse`
- **Files modified:** packages/mcp_json_yaml_toml/models/responses.py
- **Verification:** All 415 tests pass
- **Committed in:** afa4fe0

**2. [Rule 1 - Bug] Made \_DictAccessMixin alias-aware**

- **Found during:** Task 1 (Pydantic return migration)
- **Issue:** `result["schema"]` on SchemaResponse returned Pydantic's `.schema()` class method instead of the `schema_` field (which uses `alias="schema"`). `_DictAccessMixin.__getitem__` called `getattr(self, "schema")` which hit the method, not the aliased field.
- **Fix:** Added `_resolve_field_name()` method that checks field aliases before falling back to the key as-is
- **Files modified:** packages/mcp_json_yaml_toml/models/responses.py
- **Verification:** test_data_get_schema passes; all 415 tests pass
- **Committed in:** afa4fe0

**3. [Rule 3 - Blocking] Runtime import for FastMCP decorator type resolution**

- **Found during:** Task 1 (Updating tools/data.py return type)
- **Issue:** Ruff auto-moved response model imports into `TYPE_CHECKING` block. FastMCP's `@mcp.tool()` decorator uses `TypeAdapter` to resolve return type annotations at import time, causing `NameError: name 'DataResponse' is not defined` at module load.
- **Fix:** Kept imports at runtime with `noqa: TC001` comment explaining why
- **Files modified:** packages/mcp_json_yaml_toml/tools/data.py
- **Verification:** All 415 tests pass; server loads correctly
- **Committed in:** afa4fe0

---

**Total deviations:** 3 auto-fixed (2 bugs, 1 blocking)
**Impact on plan:** All auto-fixes necessary for correctness. The alias-awareness and runtime import patterns are reusable for future response model migrations.

## Issues Encountered

None beyond the deviations documented above.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- TYPE-01 (Pydantic returns), TYPE-02 (FormatType enum consistency), and TYPE-03 (specific exception handling) all complete
- All service layer functions now have compile-time type safety
- `_DictAccessMixin` alias resolution pattern available for any future aliased fields
- Ready for Phase 05 Plan 03 (god module splitting) if planned, or Phase 06

## Self-Check: PASSED

- All 4 modified files verified present on disk
- Both task commits verified in git log (afa4fe0, 6e60cc8)
- SUMMARY.md exists at expected path

---

_Phase: 05-type-safety-and-dry-foundation_
_Completed: 2026-02-15_

---
phase: 02-tool-layer-refactoring
plan: 01
subsystem: api
tags: [pydantic, response-models, schema-validation, jsonschema, refactoring]

# Dependency graph
requires:
  - phase: 01-architectural-foundation
    provides: "formats/base.py with _detect_file_format and _parse_content_for_validation, services/ package structure"
provides:
  - "Pydantic response models for all tool return shapes (models/responses.py)"
  - "Schema validation service extracted from server.py (services/schema_validation.py)"
  - "SchemaResponse importable from both models.responses and server module (backward compat)"
affects: [02-02, 02-03, 02-04]

# Tech tracking
tech-stack:
  added: []
  patterns:
    [
      "Pydantic response models with extra=allow for safe refactoring",
      "TYPE_CHECKING guard exception: Pydantic field types must be runtime imports (noqa: TC001)",
    ]

key-files:
  created:
    - packages/mcp_json_yaml_toml/models/__init__.py
    - packages/mcp_json_yaml_toml/models/responses.py
    - packages/mcp_json_yaml_toml/services/schema_validation.py
  modified:
    - packages/mcp_json_yaml_toml/server.py

key-decisions:
  - "ToolResponse base uses extra=allow as safety net during refactoring (tighten to forbid in Plan 04)"
  - "SchemaInfo must be runtime import in responses.py despite from __future__ annotations (Pydantic model building requirement)"
  - "ValueError used instead of orjson.JSONDecodeError in schema_validation.py to avoid unnecessary orjson dependency"

patterns-established:
  - "Pydantic response model hierarchy: ToolResponse base with extra=allow, specialized subclasses"
  - "Service extraction pattern: move function to services/ module, import back in server.py"

# Metrics
duration: 13min
completed: 2026-02-15
---

# Phase 2 Plan 01: Response Models and Schema Validation Service Summary

**10 Pydantic response models in models/responses.py and \_validate_against_schema extracted to services/schema_validation.py with zero test breakage**

## Performance

- **Duration:** 13 min
- **Started:** 2026-02-15T02:48:12Z
- **Completed:** 2026-02-15T03:01:30Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

- Created 10 Pydantic response models covering all tool return shapes (ToolResponse, DataResponse, MutationResponse, ValidationResponse, SchemaActionResponse, ConvertResponse, MergeResponse, ConstraintValidateResponse, ConstraintListResponse, SchemaResponse)
- Extracted \_validate_against_schema function from server.py to services/schema_validation.py with all required imports
- Updated server.py to import from new locations, removing 7 unused imports (httpx, Draft7Validator, Draft202012Validator, SchemaError, ValidationError, Registry/Resource/NoSuchResource, YQError, BaseModel)
- All 393 tests pass without modification

## Task Commits

Each task was committed atomically:

1. **Task 1: Create Pydantic response models and schema validation service** - `ee9f054` (feat)
2. **Task 2: Update server.py to import from new locations** - `b21f6bd` (refactor)

## Files Created/Modified

- `packages/mcp_json_yaml_toml/models/__init__.py` - Package marker for models
- `packages/mcp_json_yaml_toml/models/responses.py` - All 10 Pydantic response models with **all** exports
- `packages/mcp_json_yaml_toml/services/schema_validation.py` - Schema validation with Draft 7/2020-12 and httpx $ref resolution
- `packages/mcp_json_yaml_toml/server.py` - Removed SchemaResponse class and \_validate_against_schema function, added imports from new locations

## Decisions Made

- ToolResponse base uses `extra="allow"` as a safety net during the refactoring phase -- prevents breakage from any dict keys in current code that weren't enumerated in models. Can be tightened to `"forbid"` after Plan 04 when all tools return typed models.
- SchemaInfo must remain a runtime import in responses.py (`noqa: TC001`) because Pydantic requires field types to be resolvable at model building time, even with `from __future__ import annotations`.
- Used `ValueError` instead of `orjson.JSONDecodeError` in schema_validation.py exception handler to avoid importing orjson in a module that doesn't otherwise need it. `orjson.JSONDecodeError` is a subclass of `ValueError`, so this is functionally equivalent.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed SchemaInfo runtime import for Pydantic model building**

- **Found during:** Task 2 (test_data_get_schema failure)
- **Issue:** The linter's ruff TC001 rule moved SchemaInfo to TYPE_CHECKING in responses.py. Pydantic needs the actual type at runtime for model construction, causing `PydanticUserError: SchemaResponse is not fully defined`.
- **Fix:** Moved SchemaInfo back to runtime import with `noqa: TC001` annotation explaining why
- **Files modified:** packages/mcp_json_yaml_toml/models/responses.py
- **Verification:** All 393 tests pass
- **Committed in:** b21f6bd (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Essential fix for correctness. No scope creep.

## Issues Encountered

None beyond the auto-fixed deviation above.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Response models ready for Plan 02 (unified data tool refactoring)
- Schema validation service extracted and tested, ready for Plan 03 (schema tool refactoring)
- ToolResponse extra="allow" provides safety margin for iterative tool migration

---

_Phase: 02-tool-layer-refactoring_
_Completed: 2026-02-15_

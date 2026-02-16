---
phase: 02-tool-layer-refactoring
plan: 04
subsystem: api
tags: [fastmcp, pydantic, mcp-annotations, tool-annotations, output-schema]

requires:
  - phase: 02-tool-layer-refactoring (plan 02)
    provides: "Pydantic response models in models/responses.py"
  - phase: 02-tool-layer-refactoring (plan 03)
    provides: "Tool modules extracted to tools/ directory"
provides:
  - "Complete MCP annotations (readOnlyHint, destructiveHint, idempotentHint, openWorldHint) on all 7 tools"
  - "Pydantic return types on 5 single-shape tools with FastMCP output_schema generation"
  - "_DictAccessMixin for backward-compatible dict-like access on response models"
affects: [phase-03-structured-output, phase-04-testing]

tech-stack:
  added: []
  patterns:
    - "_DictAccessMixin: Pydantic models with dict-like __getitem__/__contains__/get for backward compat"
    - "Runtime import pattern: noqa TC001 for response model imports needed by FastMCP return-type resolution"
    - "MCP annotation dict form: annotations={readOnlyHint: ..., destructiveHint: ..., ...}"

key-files:
  created: []
  modified:
    - packages/mcp_json_yaml_toml/models/responses.py
    - packages/mcp_json_yaml_toml/services/data_operations.py
    - packages/mcp_json_yaml_toml/tools/data.py
    - packages/mcp_json_yaml_toml/tools/query.py
    - packages/mcp_json_yaml_toml/tools/schema.py
    - packages/mcp_json_yaml_toml/tools/convert.py
    - packages/mcp_json_yaml_toml/tools/constraints.py

key-decisions:
  - "_DictAccessMixin added to response models for backward-compatible dict-like access (tests use result['key'] and 'key' in result patterns)"
  - "ConstraintValidateResponse uses extra='allow' for dynamic fields (suggestions, remaining_pattern) from ValidationResult.to_dict()"
  - "Response model imports use runtime imports (not TYPE_CHECKING) because FastMCP/Pydantic resolve return type annotations at module load time"
  - "is_partial maps False->None in ConstraintValidateResponse to maintain 'key not in result' semantics via _DictAccessMixin.__contains__"

patterns-established:
  - "_DictAccessMixin: All response models support result['key'], 'key' in result, result.get('key') with None-as-absent semantics"
  - "Runtime TC001 imports: Return type models must be runtime imports for FastMCP output_schema generation"

duration: 17min
completed: 2026-02-15
---

# Phase 2 Plan 04: Tool Annotations and Pydantic Return Types Summary

**Complete MCP annotations on all 7 tools and Pydantic return types on 5 single-shape tools with FastMCP output_schema auto-generation**

## Performance

- **Duration:** 17 min
- **Started:** 2026-02-15T03:27:26Z
- **Completed:** 2026-02-15T03:44:26Z
- **Tasks:** 2
- **Files modified:** 7

## Accomplishments

- All 7 tools have complete MCP annotations (readOnlyHint, destructiveHint, idempotentHint, openWorldHint)
- 5 single-shape tools (data_query, data_convert, data_merge, constraint_validate, constraint_list) return Pydantic models with FastMCP output_schema generation
- 2 polymorphic tools (data, data_schema) retain dict[str, Any] returns by design
- \_DictAccessMixin enables backward-compatible dict-like access on all response models
- All 393 tests pass, ruff clean, mypy clean (no new errors), basedpyright clean
- FMCP-04 (Pydantic response models) and FMCP-05 (tool annotations) requirements complete

## Task Commits

Each task was committed atomically:

1. **Task 1: Add complete annotations to all tools** - `9a7ceee` (feat)
2. **Task 2: Add Pydantic return types to single-shape tools** - `09f64fc` (feat)

## Files Created/Modified

- `packages/mcp_json_yaml_toml/models/responses.py` - Added \_DictAccessMixin for dict-like access; ConstraintValidateResponse gets extra="allow" and mixin
- `packages/mcp_json_yaml_toml/services/data_operations.py` - \_build_query_response returns DataResponse model instead of raw dict
- `packages/mcp_json_yaml_toml/tools/data.py` - Added complete annotations (readOnly=F, destructive=T, idempotent=T, openWorld=F)
- `packages/mcp_json_yaml_toml/tools/query.py` - Added complete annotations; return type changed to DataResponse
- `packages/mcp_json_yaml_toml/tools/schema.py` - Added complete annotations (readOnly=F, destructive=F, idempotent=T, openWorld=T)
- `packages/mcp_json_yaml_toml/tools/convert.py` - Added complete annotations; data_convert returns ConvertResponse, data_merge returns MergeResponse
- `packages/mcp_json_yaml_toml/tools/constraints.py` - Added complete annotations; constraint_validate returns ConstraintValidateResponse, constraint_list returns ConstraintListResponse

## Decisions Made

- **\_DictAccessMixin**: Added to all response models to maintain backward compatibility with existing test patterns (`result["key"]`, `"key" in result`, `result.get("key")`). The mixin treats None-valued fields as absent in `__contains__` checks, matching the prior dict behavior where keys were only added when values were non-None.
- **Runtime imports for response models**: FastMCP resolves return type annotations at module load time via `get_type_hints()`. Imports under `TYPE_CHECKING` cause `NameError` at runtime. Used runtime imports with `noqa: TC001` comments (consistent with existing SchemaInfo pattern).
- **ConstraintValidateResponse extra="allow"**: The constraint validation API returns dynamic fields (`suggestions`, `remaining_pattern`) from `ValidationResult.to_dict()` that aren't part of the fixed schema. Using Pydantic's `extra="allow"` preserves these in the model instance.
- **is_partial False-to-None mapping**: `ValidationResult.is_partial` defaults to `False`, but tests check `"is_partial" in result` (expecting absence when False). Mapping `False` to `None` maintains the dict-absent semantics via `_DictAccessMixin.__contains__`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] \_DictAccessMixin for backward-compatible dict access**

- **Found during:** Task 2 (Pydantic return types)
- **Issue:** Returning Pydantic model instances broke 393 tests that use dict-like access (`result["success"]`, `"error" not in result`, `result.get("suggestions", [])`). Pydantic v2 models don't support `[]` access.
- **Fix:** Created `_DictAccessMixin` with `__getitem__`, `__contains__` (None-as-absent), and `get()` methods. Applied to `ToolResponse` base class and standalone response models.
- **Files modified:** `packages/mcp_json_yaml_toml/models/responses.py`
- **Verification:** All 393 tests pass without modification
- **Committed in:** `09f64fc` (Task 2 commit)

**2. [Rule 3 - Blocking] Runtime imports instead of TYPE_CHECKING for response models**

- **Found during:** Task 2 (data_query return type)
- **Issue:** Linter auto-moved `DataResponse` import into `TYPE_CHECKING` block. FastMCP resolves return type annotations at module load time; `NameError: name 'DataResponse' is not defined` at server startup.
- **Fix:** Used runtime imports with `noqa: TC001` annotation, consistent with existing `SchemaInfo` import pattern in the codebase.
- **Files modified:** `packages/mcp_json_yaml_toml/tools/query.py`, `convert.py`, `constraints.py`
- **Verification:** Server loads successfully, output_schema generated for all 5 tools
- **Committed in:** `09f64fc` (Task 2 commit)

---

**Total deviations:** 2 auto-fixed (both Rule 3 - blocking)
**Impact on plan:** Both fixes necessary for the Pydantic return type migration to work without breaking tests or server startup. No scope creep.

## Issues Encountered

None beyond the auto-fixed deviations above.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Phase 2 (Tool Layer Refactoring) is now complete -- all 4 plans executed
- All tools have complete MCP annotations for client behavior semantics
- 5 tools generate output_schema via Pydantic return types (foundation for Phase 3 structured output)
- ToolResponse.extra="allow" can be tightened to "forbid" once Phase 3 confirms no dynamic fields needed
- Ready to proceed to Phase 3

## Self-Check: PASSED

All 7 modified files verified present. Both commit hashes (9a7ceee, 09f64fc) found in git log.

---

_Phase: 02-tool-layer-refactoring_
_Completed: 2026-02-15_

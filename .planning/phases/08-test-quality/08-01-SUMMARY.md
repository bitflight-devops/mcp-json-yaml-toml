---
phase: 08-test-quality
plan: 01
subsystem: testing
tags: [pytest, parametrize, assertions, public-api-testing]

# Dependency graph
requires:
  - phase: 07-architecture-refactoring
    provides: schemas package split with _build_ide_schema_index public API
provides:
  - Proper assert-based test_hints() in verify_features.py
  - Public API tests for schema parsing via _build_ide_schema_index
  - Parametrized tests across test_diff, test_lmql_constraints, test_yq_wrapper
affects: []

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "@pytest.mark.parametrize for repetitive valid/invalid input tests"
    - "Typed cast pattern for FastMCP tool functions in test modules"

key-files:
  created: []
  modified:
    - packages/mcp_json_yaml_toml/tests/verify_features.py
    - packages/mcp_json_yaml_toml/tests/test_schemas.py
    - packages/mcp_json_yaml_toml/tests/test_diff.py
    - packages/mcp_json_yaml_toml/tests/test_lmql_constraints.py
    - packages/mcp_json_yaml_toml/tests/test_yq_wrapper.py

key-decisions:
  - "Use Callable[..., DataResponse] cast pattern for FastMCP tool functions (matches test_diff.py convention)"
  - "Route schema parsing tests through _build_ide_schema_index (public API in __all__) instead of _parse_extension_schemas"

patterns-established:
  - "Parametrize pattern: Combine tests with identical assertion logic (assert result.valid is True) into single parametrized test"
  - "Keep tests with unique assertions as individual methods (e.g., partial match, suggestions, error messages)"

# Metrics
duration: 10min
completed: 2026-02-16
---

# Phase 8 Plan 1: Test Quality Summary

**Assert-based verify_features.py, public API schema tests via \_build_ide_schema_index, and 11 new @pytest.mark.parametrize decorators across 4 test files**

## Performance

- **Duration:** 10 min
- **Started:** 2026-02-16T04:40:56Z
- **Completed:** 2026-02-16T04:51:18Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments

- Replaced print-only test_hints() with 6 assert statements validating DataResponse structure and pagination fields
- Refactored 4 TestParseExtensionSchemas tests from direct \_parse_extension_schemas calls to \_build_ide_schema_index public API
- Added 11 @pytest.mark.parametrize decorators reducing 80+ lines of repetitive test code across 4 files
- All 416 tests pass at 82.52% coverage with zero regressions

## Task Commits

Each task was committed atomically:

1. **Task 1: Fix verify_features.py assertions and refactor test_schemas.py** - `0ddc271` (test)
2. **Task 2: Convert repetitive test data to @pytest.mark.parametrize** - `7561784` (test)

## Files Created/Modified

- `packages/mcp_json_yaml_toml/tests/verify_features.py` - Replaced call_tool dict wrapper with typed Callable cast; added 6 assert statements for DataResponse validation
- `packages/mcp_json_yaml_toml/tests/test_schemas.py` - Refactored TestParseExtensionSchemas to use \_build_ide_schema_index; removed \_parse_extension_schemas imports
- `packages/mcp_json_yaml_toml/tests/test_diff.py` - Parametrized missing file tests (first/second positions)
- `packages/mcp_json_yaml_toml/tests/test_lmql_constraints.py` - 8 parametrize decorators for valid paths, expressions, formats, integers, keys, values, file paths
- `packages/mcp_json_yaml_toml/tests/test_yq_wrapper.py` - 2 parametrize decorators for version parsing and minimum version comparison

## Decisions Made

- Used `Callable[..., DataResponse]` cast pattern for `data_query` tool (consistent with `data_diff_fn` pattern in test_diff.py)
- Routed schema parsing tests through `_build_ide_schema_index([tmp_path])` which is in `__all__` and exercises `_parse_extension_schemas` internally

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed verify_features.py call_tool TypeError**

- **Found during:** Task 1 (verify_features.py assertions)
- **Issue:** `call_tool()` expected dict return but `data_query` now returns `DataResponse` Pydantic model (changed during v1.1 response model refactoring)
- **Fix:** Replaced `call_tool` dict wrapper with typed `cast("Callable[..., DataResponse]", data_query)` and direct attribute access
- **Files modified:** packages/mcp_json_yaml_toml/tests/verify_features.py
- **Verification:** test_hints passes with proper assertions on DataResponse attributes
- **Committed in:** 0ddc271

**2. [Rule 1 - Bug] Fixed mypy arg-type error from incorrect cast type**

- **Found during:** Task 1 (pre-commit hook)
- **Issue:** Initial cast as `type[DataResponse]` made mypy interpret first arg as `bool` (DataResponse.**init** signature). Needed `Callable[..., DataResponse]` instead.
- **Fix:** Changed cast to `Callable[..., DataResponse]` with TYPE_CHECKING import for Callable
- **Files modified:** packages/mcp_json_yaml_toml/tests/verify_features.py
- **Verification:** mypy passes, basedpyright passes
- **Committed in:** 0ddc271

---

**Total deviations:** 2 auto-fixed (2 bugs)
**Impact on plan:** Both fixes necessary for correctness. test_hints was already failing before this plan. No scope creep.

## Issues Encountered

None beyond the auto-fixed deviations above.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Plan 08-01 complete, ready for 08-02 (remaining test quality improvements)
- All linting gates pass on modified files
- Full test suite: 416 passed, 2 skipped, 82.52% coverage

---

_Phase: 08-test-quality_
_Completed: 2026-02-16_

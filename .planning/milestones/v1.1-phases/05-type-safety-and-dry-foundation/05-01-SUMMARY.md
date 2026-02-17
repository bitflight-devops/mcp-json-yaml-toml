---
phase: 05-type-safety-and-dry-foundation
plan: 01
subsystem: architecture
tags:
  [dry, refactoring, shared-utilities, format-validation, path-resolution, toml]

# Dependency graph
requires: []
provides:
  - require_format_enabled() shared function in config.py
  - resolve_file_path() shared function in formats/base.py
  - should_fallback_toml_to_json() shared function in formats/base.py
  - _navigate_to_parent() shared function in toml_utils.py
affects: [05-02-type-safety]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Single-function format gate: require_format_enabled() replaces 4-line check-and-raise pattern"
    - "Shared file resolution: resolve_file_path() with must_exist flag for input vs output paths"
    - "Predicate extraction: should_fallback_toml_to_json() encapsulates multi-condition retry logic"
    - "Navigation extraction: _navigate_to_parent() with create_missing flag for set vs delete"

key-files:
  created: []
  modified:
    - packages/mcp_json_yaml_toml/config.py
    - packages/mcp_json_yaml_toml/formats/base.py
    - packages/mcp_json_yaml_toml/toml_utils.py
    - packages/mcp_json_yaml_toml/tools/data.py
    - packages/mcp_json_yaml_toml/tools/query.py
    - packages/mcp_json_yaml_toml/tools/convert.py
    - packages/mcp_json_yaml_toml/tools/diff.py
    - packages/mcp_json_yaml_toml/tools/schema.py
    - packages/mcp_json_yaml_toml/services/data_operations.py

key-decisions:
  - "Standardize error messages: resolve_file_path() uses 'File not found' instead of context-specific prefixes like 'First file not found'"
  - "Keep directory path resolution as-is: resolve_file_path() is for files; schema scan/add_dir still use inline Path resolution"
  - "Keep output file path resolution as-is: output paths that may not exist yet are not candidates for resolve_file_path(must_exist=True)"

patterns-established:
  - "DRY gate pattern: Add shared utility to config.py or formats/base.py, then replace all call sites in tools/ and services/"
  - "Navigation extraction: Private helpers with keyword-only flags to distinguish set (create_missing=True) from delete behavior"

# Metrics
duration: 13min
completed: 2026-02-15
---

# Phase 5 Plan 1: DRY Utility Extraction Summary

**Four shared utility functions replacing 20+ duplicated code blocks across 9 modules**

## Performance

- **Duration:** 13 min
- **Started:** 2026-02-15T20:05:54Z
- **Completed:** 2026-02-15T20:19:40Z
- **Tasks:** 2
- **Files modified:** 11

## Accomplishments

- Extracted `require_format_enabled()` replacing 9 duplicated 4-line check-and-raise blocks
- Extracted `resolve_file_path()` replacing 7 file-path-resolve-and-check blocks across tool modules
- Extracted `should_fallback_toml_to_json()` replacing 2 inline multi-condition TOML fallback checks
- Extracted `_navigate_to_parent()` replacing duplicated key-path navigation in set_toml_value and delete_toml_key

## Task Commits

Each task was committed atomically:

1. **Task 1: Extract DRY utility functions** - `47b24c4` (refactor)
2. **Task 2: Replace all duplicated call sites** - `3e0eb90` (refactor) + `2f0c3fd` (test)

## Files Created/Modified

- `packages/mcp_json_yaml_toml/config.py` - Added require_format_enabled(), **all** exports
- `packages/mcp_json_yaml_toml/formats/base.py` - Added resolve_file_path() and should_fallback_toml_to_json()
- `packages/mcp_json_yaml_toml/toml_utils.py` - Extracted \_navigate_to_parent(), refactored set/delete functions
- `packages/mcp_json_yaml_toml/tools/data.py` - Replaced path resolution with resolve_file_path()
- `packages/mcp_json_yaml_toml/tools/query.py` - Replaced format check, path resolution, and TOML fallback
- `packages/mcp_json_yaml_toml/tools/convert.py` - Replaced format checks and path resolution in convert/merge
- `packages/mcp_json_yaml_toml/tools/diff.py` - Replaced format checks and path resolution
- `packages/mcp_json_yaml_toml/tools/schema.py` - Replaced format check and path resolution in validate/associate/disassociate
- `packages/mcp_json_yaml_toml/services/data_operations.py` - Replaced 3 format checks and 1 TOML fallback
- `packages/mcp_json_yaml_toml/tests/test_diff.py` - Updated error message assertions
- `packages/mcp_json_yaml_toml/tests/test_server.py` - Updated error message assertion

## Decisions Made

- **Standardized error messages:** `resolve_file_path()` uses generic "File not found: {path}" instead of context-specific prefixes like "First file not found" or "Second file not found". The file path in the message provides sufficient context.
- **Selective path resolution replacement:** Directory paths (schema scan, add_dir) and output file paths (convert, merge output_file) kept inline Path resolution since they have different semantics (directories, may-not-exist paths).
- **require_format_enabled accepts FormatType | str:** Matches the existing `is_format_enabled` signature to support all existing call sites without type narrowing.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Updated test assertions for standardized error messages**

- **Found during:** Task 2 (Replace call sites)
- **Issue:** 3 tests expected "First file not found" / "Second file not found" but resolve_file_path() produces "File not found"
- **Fix:** Updated match strings in test_diff.py (2 tests) and test_server.py (1 test)
- **Files modified:** packages/mcp_json_yaml_toml/tests/test_diff.py, packages/mcp_json_yaml_toml/tests/test_server.py
- **Verification:** All 415 tests pass
- **Committed in:** 3e0eb90 and 2f0c3fd

**2. [Rule 3 - Blocking] Cleared stale mypy cache causing false positives**

- **Found during:** Task 2 (Committing test_server.py)
- **Issue:** Stale mypy incremental cache caused "FunctionTool not callable" false positives on test_server.py when pre-commit hook ran
- **Fix:** Cleared .mypy_cache directory
- **Verification:** mypy passes clean on all modified files
- **Committed in:** 2f0c3fd

---

**Total deviations:** 2 auto-fixed (1 bug, 1 blocking)
**Impact on plan:** Both auto-fixes necessary for correctness. No scope creep.

## Issues Encountered

None beyond the deviations documented above.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- All DRY utilities in place, ready for Plan 02 (type safety improvements)
- `require_format_enabled()` provides the foundation for typed format validation
- `resolve_file_path()` provides consistent Path handling for type narrowing
- `should_fallback_toml_to_json()` and `_navigate_to_parent()` reduce code surface for type annotation work

## Self-Check: PASSED

- All 4 utility functions verified present in their target modules
- All 3 task commits verified in git log
- SUMMARY.md exists at expected path

---

_Phase: 05-type-safety-and-dry-foundation_
_Completed: 2026-02-15_

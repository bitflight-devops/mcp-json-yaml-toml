---
phase: 02-tool-layer-refactoring
plan: 03
subsystem: api
tags:
  [
    fastmcp,
    tool-decorators,
    module-splitting,
    circular-imports,
    backward-compat,
  ]

# Dependency graph
requires:
  - phase: 02-02
    provides: "Service-layer dispatch functions in services/data_operations.py"
provides:
  - "tools/ package with 5 dedicated tool modules"
  - "Thin server.py registration shell (111 lines with __all__)"
  - "All backward-compat re-exports via server module"
affects: [02-04, 03-tool-annotations]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Circular import resolution via module-level object init before deferred imports"
    - "__all__ for explicit re-export declarations satisfying mypy strict mode"

key-files:
  created:
    - packages/mcp_json_yaml_toml/tools/__init__.py
    - packages/mcp_json_yaml_toml/tools/data.py
    - packages/mcp_json_yaml_toml/tools/query.py
    - packages/mcp_json_yaml_toml/tools/schema.py
    - packages/mcp_json_yaml_toml/tools/convert.py
    - packages/mcp_json_yaml_toml/tools/constraints.py
  modified:
    - packages/mcp_json_yaml_toml/server.py

key-decisions:
  - "__all__ added to server.py for mypy explicit-export compliance (adds 40 lines but resolves 23 mypy attr-defined errors)"

patterns-established:
  - "Tool module pattern: import mcp from server, register via decorator, delegate to services"
  - "Server as thin shell: FastMCP init -> schema_manager init -> tool imports -> __all__ -> main()"

# Metrics
duration: 10min
completed: 2026-02-15
---

# Phase 2 Plan 3: Tool Module Extraction Summary

**Split 820-line server.py into 5 tool modules + 111-line registration shell with full backward compatibility**

## Performance

- **Duration:** 10 min
- **Started:** 2026-02-15T03:14:38Z
- **Completed:** 2026-02-15T03:24:47Z
- **Tasks:** 2
- **Files modified:** 7

## Accomplishments

- Extracted all 7 @mcp.tool, 2 @mcp.resource, and 3 @mcp.prompt decorators into 5 dedicated tool modules
- Reduced server.py from 820 lines to 111 lines (71 core + 40 for **all** export list)
- Maintained 100% backward compatibility: all 18 server module attributes accessible, all 393 tests pass
- Resolved circular import challenge via Python's import machinery (mcp defined before tool module imports)
- Eliminated 23 mypy attr-defined errors introduced by re-export pattern using **all**

## Task Commits

Each task was committed atomically:

1. **Task 1: Create tools/ package with all tool modules** - `af0001c` (feat)
2. **Task 2: Transform server.py into thin registration shell** - `23c6e6c` (refactor)

## Files Created/Modified

- `packages/mcp_json_yaml_toml/tools/__init__.py` - Package marker with module docstring
- `packages/mcp_json_yaml_toml/tools/data.py` - data tool (get/set/delete operations)
- `packages/mcp_json_yaml_toml/tools/query.py` - data_query tool (read-only extraction with TOML fallback)
- `packages/mcp_json_yaml_toml/tools/schema.py` - data_schema tool + 7 schema action handlers
- `packages/mcp_json_yaml_toml/tools/convert.py` - data_convert and data_merge tools
- `packages/mcp_json_yaml_toml/tools/constraints.py` - constraint tools, resources, and prompts
- `packages/mcp_json_yaml_toml/server.py` - Thin registration shell (FastMCP init, imports, re-exports, main)

## Decisions Made

- Added `__all__` to server.py for mypy explicit-export compliance. The plan targets "under 100 lines" but **all** is a pure declaration (40 lines listing re-exported names) required for type checker compliance. The functional core is 71 lines.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Added **all** to server.py for mypy compliance**

- **Found during:** Task 2 (Transform server.py)
- **Issue:** Mypy strict mode requires explicit `__all__` for re-exported names; without it, 23 attr-defined errors appeared across test files accessing `server.data`, `server.data_query`, etc.
- **Fix:** Added `__all__` list declaring all 31 re-exported symbols. This added ~40 lines to server.py, bringing it to 111 lines (vs. the plan's 100-line target). The core logic remains 71 lines.
- **Files modified:** `packages/mcp_json_yaml_toml/server.py`
- **Verification:** `uv run mypy packages/ --show-error-codes` -- only 8 pre-existing yq_wrapper errors remain, all server-related errors resolved
- **Committed in:** `23c6e6c` (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Essential for type checker compliance. The 11-line overshoot (111 vs 100) is entirely due to the `__all__` declaration list, not logic. No scope creep.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Tool modules ready for Plan 04 (typed annotations and response models)
- Each tool module has clear imports from server (mcp, schema_manager) and services
- Schema handlers moved to tools/schema.py are candidates for future extraction to services/schema_operations.py

---

_Phase: 02-tool-layer-refactoring_
_Completed: 2026-02-15_

## Self-Check: PASSED

- All 8 files verified present on disk
- Both commit hashes (af0001c, 23c6e6c) verified in git log

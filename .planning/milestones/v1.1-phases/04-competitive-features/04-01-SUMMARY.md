---
phase: 04-competitive-features
plan: 01
subsystem: tools
tags: [deepdiff, diffing, cross-format, mcp-tool, pydantic]

# Dependency graph
requires:
  - phase: 02-tool-layer-refactoring
    provides: tool/service/model layered architecture, ToolResponse base class, _DictAccessMixin
  - phase: 03-fastmcp-migration
    provides: FastMCP 3.x @mcp.tool decorator pattern, timeout annotations
provides:
  - data_diff MCP tool for structured configuration file comparison
  - DiffResponse Pydantic model with differences dict, statistics, summary
  - diff_operations service with compute_diff, build_diff_statistics, build_diff_summary
  - Cross-format comparison (JSON vs YAML vs TOML)
affects: [04-02, documentation, tool-registry]

# Tech tracking
tech-stack:
  added: [deepdiff>=8.0.0, orderly-set]
  patterns:
    [
      DeepDiff verbose_level=2 to_dict() pipeline,
      cast() for FastMCP FunctionTool mypy compat,
    ]

key-files:
  created:
    - packages/mcp_json_yaml_toml/services/diff_operations.py
    - packages/mcp_json_yaml_toml/tools/diff.py
    - packages/mcp_json_yaml_toml/tests/test_diff.py
  modified:
    - packages/mcp_json_yaml_toml/models/responses.py
    - packages/mcp_json_yaml_toml/server.py
    - pyproject.toml

key-decisions:
  - "DeepDiff verbose_level=2 for detailed old/new value reporting in diff output"
  - "cast() alias pattern for mypy FunctionTool-not-callable when prek checks tool+test files together"
  - "Import data_diff from server module (not tools.diff) in tests to avoid circular import"

patterns-established:
  - "Diff tool pattern: parse both files to JSON via yq pipeline, then DeepDiff for semantic comparison"
  - "Test alias pattern: cast('Callable[..., ResponseType]', server.tool_fn) for mypy strict mode compat"

# Metrics
duration: 18min
completed: 2026-02-15
---

# Phase 4 Plan 1: Config Diff Tool Summary

**data_diff MCP tool with DeepDiff-powered cross-format comparison, structured diff output, statistics, and human-readable summaries**

## Performance

- **Duration:** 18 min
- **Started:** 2026-02-15T07:04:17Z
- **Completed:** 2026-02-15T07:22:46Z
- **Tasks:** 2
- **Files modified:** 7

## Accomplishments

- data_diff tool registered in MCP server with readOnlyHint, idempotentHint annotations
- Cross-format comparison works: JSON vs YAML vs TOML files compared semantically
- DiffResponse model with has_differences, differences dict, statistics, and summary fields
- 17 tests covering service layer (compute_diff, statistics, summary) and tool integration (identical files, different files, cross-format, missing files, ignore_order)

## Task Commits

Each task was committed atomically:

1. **Task 1: Add deepdiff dependency, DiffResponse model, and diff service** - `aae7488` (feat)
2. **Task 2: Create data_diff tool, register in server, and add tests** - `422635f` (feat)

## Files Created/Modified

- `packages/mcp_json_yaml_toml/services/diff_operations.py` - DeepDiff wrapper with compute_diff, build_diff_statistics, build_diff_summary
- `packages/mcp_json_yaml_toml/tools/diff.py` - data_diff @mcp.tool with file parsing, format detection, diff computation
- `packages/mcp_json_yaml_toml/tests/test_diff.py` - 17 tests: 6 unit (compute_diff), 2 unit (statistics), 2 unit (summary), 7 integration (tool)
- `packages/mcp_json_yaml_toml/models/responses.py` - Added DiffResponse Pydantic model
- `packages/mcp_json_yaml_toml/server.py` - Registered data_diff import and **all** export
- `pyproject.toml` - Added deepdiff>=8.0.0 dependency

## Decisions Made

- DeepDiff with verbose_level=2 provides old_value/new_value detail in diff output
- Import data_diff from server module in tests (not from tools.diff) to avoid circular import through mcp object
- cast("Callable[..., DiffResponse]", server.data_diff) resolves mypy FunctionTool-not-callable when prek runs mypy on tool+test files together
- Included pre-existing branch typing improvements in Task 2 commit to ensure consistent type resolution during pre-commit hooks

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Fixed circular import in test file**

- **Found during:** Task 2 (tests)
- **Issue:** `from mcp_json_yaml_toml.tools.diff import data_diff` caused circular import: test -> tools/diff -> server -> tools/diff
- **Fix:** Changed to `from mcp_json_yaml_toml import server` + `server.data_diff` alias pattern (matching test_server.py)
- **Files modified:** packages/mcp_json_yaml_toml/tests/test_diff.py
- **Verification:** All 17 tests pass, no import errors
- **Committed in:** 422635f (Task 2 commit)

**2. [Rule 3 - Blocking] Fixed mypy FunctionTool-not-callable error**

- **Found during:** Task 2 (quality gates)
- **Issue:** mypy sees `server.data_diff` as `FunctionTool` (FastMCP decorator return type) when tools/diff.py is in the same mypy invocation via prek --files
- **Fix:** Used `cast("Callable[..., DiffResponse]", server.data_diff)` to give mypy the correct callable type
- **Files modified:** packages/mcp_json_yaml_toml/tests/test_diff.py
- **Verification:** `uv run prek run --files` passes all gates including mypy
- **Committed in:** 422635f (Task 2 commit)

---

**Total deviations:** 2 auto-fixed (2 blocking)
**Impact on plan:** Both fixes necessary for test infrastructure compatibility. No scope creep.

## Issues Encountered

- Pre-existing unstaged branch changes (typing improvements from Phase 4 research) caused pre-commit hook failures when stashed during commit. Resolved by including necessary source files in commit staging to ensure consistent type resolution.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- data_diff tool fully operational and tested, ready for Plan 04-02
- All 410 existing tests continue passing (no regressions)
- Coverage at 79.63% (above 60% threshold)

---

_Phase: 04-competitive-features_
_Completed: 2026-02-15_

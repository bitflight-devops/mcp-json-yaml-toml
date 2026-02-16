---
phase: 06-operational-safety
plan: 01
subsystem: infra
tags: [logging, stdlib, binary-manager, yq]

# Dependency graph
requires:
  - phase: 01-architectural-foundation
    provides: "backends/ package with binary_manager.py module"
provides:
  - "Structured logging in binary_manager.py via stdlib logging module"
  - "Module-level logger using logging.getLogger(__name__)"
  - "Log level mapping: info (progress), warning (fallbacks), debug (details)"
affects: [06-operational-safety, logging-configuration]

# Tech tracking
tech-stack:
  added: [logging (stdlib)]
  patterns: [lazy-%-formatting-for-log-calls, module-level-getLogger]

key-files:
  created: []
  modified:
    - packages/mcp_json_yaml_toml/backends/binary_manager.py
    - packages/mcp_json_yaml_toml/tests/test_yq_wrapper.py
    - packages/mcp_json_yaml_toml/yq_wrapper.py

key-decisions:
  - "stdlib logging over loguru for this migration — matches existing architecture, no new dependency"
  - "Lazy %-formatting for all log calls — prevents string interpolation when log level is filtered"

patterns-established:
  - "Module-level logger: logger = logging.getLogger(__name__) after constants"
  - "Log level mapping: info=progress, warning=fallback/advisory, debug=details/cache-hits"
  - "Lazy %-formatting: logger.info('msg %s', var) not logger.info(f'msg {var}')"

# Metrics
duration: 6min
completed: 2026-02-16
---

# Phase 6 Plan 1: Binary Manager Logging Migration Summary

**Replaced all 17 print(file=sys.stderr) calls in binary_manager.py with stdlib logging using lazy %-formatting and appropriate log levels**

## Performance

- **Duration:** 6 min
- **Started:** 2026-02-16T02:10:01Z
- **Completed:** 2026-02-16T02:16:05Z
- **Tasks:** 1
- **Files modified:** 3

## Accomplishments

- Replaced all 17 print(file=sys.stderr) calls with logging module calls
- Established log level mapping: info for progress, warning for fallbacks, debug for cache hits
- All log calls use lazy %-formatting (zero f-strings in log calls)
- Removed unused `import sys` from binary_manager.py

## Task Commits

Each task was committed atomically:

1. **Task 1: Migrate binary_manager.py from print() to logging module** - `4bf9c84` (feat)

**Plan metadata:** pending (docs: complete plan)

## Files Created/Modified

- `packages/mcp_json_yaml_toml/backends/binary_manager.py` - Replaced 17 print() calls with logging, added logger, removed sys import
- `packages/mcp_json_yaml_toml/tests/test_yq_wrapper.py` - Updated 2 tests from capsys to caplog for warning assertions
- `packages/mcp_json_yaml_toml/yq_wrapper.py` - Added private functions to **all** to fix mypy re-export errors

## Decisions Made

- Used stdlib `logging` module (not loguru) — matches plan objective, no new dependency needed
- Lazy %-formatting for all log calls — prevents unnecessary string interpolation when log level is filtered
- Log level mapping: `info` for user-visible progress (downloads, verification), `warning` for fallbacks/advisories (wrong yq version, cleanup failures), `debug` for internal details (binary already exists/cached)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Updated tests from capsys to caplog**

- **Found during:** Task 1 (verification)
- **Issue:** 2 tests in test_yq_wrapper.py asserted on capsys.readouterr().err for print() output. After migrating to logging, output no longer goes to stderr via print.
- **Fix:** Changed tests to use caplog fixture with at_level("WARNING") context manager
- **Files modified:** packages/mcp_json_yaml_toml/tests/test_yq_wrapper.py
- **Verification:** Both tests pass with caplog assertions
- **Committed in:** 4bf9c84 (part of task commit)

**2. [Rule 3 - Blocking] Fixed mypy re-export errors in yq_wrapper.py**

- **Found during:** Task 1 (commit — pre-commit hook blocked)
- **Issue:** yq*wrapper.py imported private `*`prefixed functions from binary_manager but did not include them in`**all**`, causing mypy `attr-defined` errors for test imports
- **Fix:** Added 8 private functions to yq_wrapper.py `__all__` list
- **Files modified:** packages/mcp_json_yaml_toml/yq_wrapper.py
- **Verification:** mypy passes clean on all 3 files
- **Committed in:** 4bf9c84 (part of task commit)

---

**Total deviations:** 2 auto-fixed (1 bug fix, 1 blocking)
**Impact on plan:** Both auto-fixes necessary for correctness and commit ability. No scope creep.

## Issues Encountered

None — migration was straightforward. Pre-existing test failures in test_config.py and test_server.py (from other uncommitted changes) are unrelated to this plan.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- binary_manager.py now emits structured log records via logging module
- Ready for Plan 02 (remaining print-to-logging migrations in other modules)
- Future logging configuration (handlers, formatters, log levels) can be added centrally

---

_Phase: 06-operational-safety_
_Completed: 2026-02-16_

---
phase: 07-architecture-refactoring
plan: 02
subsystem: schemas, server, tools
tags: [refactoring, architecture, module-splitting, dependency-injection]

# Dependency graph
requires:
  - phase: 07-architecture-refactoring
    plan: 01
    provides: Facade pattern for backward-compatible module splitting
provides:
  - Focused schemas package with 5 sub-modules (models, loading, scanning, ide_cache, manager)
  - Clean server.py __all__ with zero private symbol re-exports
  - Parameterized schema_manager in all tool handler functions
affects: [08-testing-hardening]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Package splitting with __init__.py re-export facade for backward compatibility"
    - "Dependency injection via parameter passing for tool handler testability"
    - "Per-file-ignore for intra-package private imports (PLC2701)"

key-files:
  created:
    - packages/mcp_json_yaml_toml/schemas/__init__.py
    - packages/mcp_json_yaml_toml/schemas/models.py
    - packages/mcp_json_yaml_toml/schemas/loading.py
    - packages/mcp_json_yaml_toml/schemas/scanning.py
    - packages/mcp_json_yaml_toml/schemas/ide_cache.py
    - packages/mcp_json_yaml_toml/schemas/manager.py
  modified:
    - packages/mcp_json_yaml_toml/server.py
    - packages/mcp_json_yaml_toml/tools/schema.py
    - packages/mcp_json_yaml_toml/tests/test_schemas.py
    - packages/mcp_json_yaml_toml/tests/test_pagination.py
    - pyproject.toml
  deleted:
    - packages/mcp_json_yaml_toml/schemas.py

key-decisions:
  - "PLC2701 per-file-ignore for schemas/*.py -- intra-package private imports are expected across sub-modules after splitting"
  - "Monkeypatch targets updated to reference defining sub-modules (scanning, manager) rather than __init__ re-exports"
  - "noqa: TC003 on Path import in loading.py -- ruff auto-fix incorrectly moves runtime-required Path into TYPE_CHECKING"

patterns-established:
  - "Package splitting: create focused sub-modules, convert original to __init__.py re-export facade"
  - "Handler dependency injection: pass singleton via parameter for testability, wire in tool function"

# Metrics
duration: 12min
completed: 2026-02-16
---

# Phase 7 Plan 2: Schema Package Split, Server Cleanup, and Handler Parameterization Summary

**Split 1201-line schemas.py into 5-module package; removed 14 private re-exports from server.py **all**; added schema_manager parameter to all 7 schema tool handlers**

## Performance

- **Duration:** 12 min
- **Started:** 2026-02-16T03:45:09Z
- **Completed:** 2026-02-16T03:57:29Z
- **Tasks:** 2
- **Files modified:** 11 (6 created, 4 modified, 1 deleted)

## Accomplishments

- Split schemas.py (1201 lines) into schemas/ package with 5 focused modules: models.py (8 dataclasses), loading.py (content extraction), scanning.py (directory scanning), ide_cache.py (IDE extension discovery), manager.py (SchemaManager facade)
- Created **init**.py re-export facade preserving all existing import paths
- Removed 14 private symbols from server.py **all** (zero \_-prefixed exports remain)
- Removed data_operations and pagination re-export imports from server.py
- Added schema_manager: SchemaManager parameter to all 7 handler functions in tools/schema.py
- Migrated test_pagination.py imports from server.py to services.pagination
- Updated test_schemas.py monkeypatch targets to reference defining sub-modules
- All 415 tests pass unchanged; all quality gates pass

## Task Commits

Each task was committed atomically:

1. **Task 1: Split schemas.py into focused sub-modules (ARCH-07)** - `f16ba5a` (refactor)
2. **Task 2: Clean server.py **all** and parameterize schema_manager (ARCH-09 + ARCH-10)** - `3c4f40d` (refactor)

## Files Created/Modified

### Task 1: Schema Package Split

- `schemas/__init__.py` - Re-export facade (all 26 public symbols)
- `schemas/models.py` - 8 dataclass definitions (SchemaInfo, SchemaEntry, SchemaCatalog, FileAssociation, SchemaConfig, DefaultSchemaStores, ExtensionSchemaMapping, IDESchemaIndex)
- `schemas/loading.py` - Content extraction functions (\_extract_from_json, \_extract_from_yaml, \_extract_from_toml, \_extract_schema_url_from_content, \_match_glob_pattern, \_strip_json_comments)
- `schemas/scanning.py` - Directory scanning helpers (\_load_default_ide_patterns, \_expand_ide_patterns, \_get_ide_schema_locations, constants)
- `schemas/ide_cache.py` - IDE extension schema discovery (IDESchemaProvider, \_parse_extension_schemas, \_build_ide_schema_index)
- `schemas/manager.py` - SchemaManager class (config, catalog, fetch, association methods)
- `schemas.py` - DELETED (replaced by package)

### Task 2: Server Cleanup and Handler Parameterization

- `server.py` - Removed 14 private symbol re-exports and their import blocks; **all** now has 16 public symbols
- `tools/schema.py` - All 7 _handle_schema_\* functions now accept schema_manager: SchemaManager parameter
- `tests/test_pagination.py` - Import from services.pagination instead of server
- `tests/test_schemas.py` - Monkeypatch targets updated to defining sub-modules

## Decisions Made

- **PLC2701 per-file-ignore**: Added `"packages/**/schemas/*.py" = ["PLC2701"]` to pyproject.toml because intra-package private imports are expected after splitting a monolith into sub-modules
- **Monkeypatch target migration**: Updated test patches from `mcp_json_yaml_toml.schemas._fn` to `mcp_json_yaml_toml.schemas.<submodule>._fn` since functions are now called from their defining modules, not through **init**
- **noqa: TC003 for Path import**: Ruff auto-fix incorrectly moves runtime-required `Path` into TYPE_CHECKING in loading.py; suppressed with noqa comment

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] PLC2701 linter errors for intra-package private imports**

- **Found during:** Task 1 (package creation)
- **Issue:** ruff PLC2701 flags cross-module `_`-prefixed imports within the schemas package
- **Fix:** Added per-file-ignore in pyproject.toml for `packages/**/schemas/*.py`
- **Files modified:** pyproject.toml
- **Committed in:** f16ba5a (Task 1 commit)

**2. [Rule 1 - Bug] Ruff TC003 auto-fix incorrectly moves runtime Path import to TYPE_CHECKING**

- **Found during:** Task 1 (loading.py creation)
- **Issue:** ruff auto-fix moves `from pathlib import Path` into TYPE_CHECKING block, but Path is used at runtime in function bodies (`.exists()`, `.read_text()`, `.suffix`)
- **Fix:** Added `# noqa: TC003` comment to Path import in loading.py
- **Files modified:** packages/mcp_json_yaml_toml/schemas/loading.py
- **Committed in:** f16ba5a (Task 1 commit)

---

**Total deviations:** 2 auto-fixed (1 blocking, 1 bug)
**Impact on plan:** Both are linter configuration issues from the module split. No scope creep.

## Issues Encountered

None

## User Setup Required

None -- no external service configuration required.

## Next Phase Readiness

- All service and schema modules are now cleanly split with focused responsibilities
- server.py is a pure registration shell with only public API exports
- Tool handlers are testable in isolation via dependency injection
- Ready for Phase 8 (testing hardening)

## Self-Check: PASSED

- All 6 new files exist in schemas/
- Old schemas.py deleted
- Both commits verified (f16ba5a, 3c4f40d)
- server.py **all** has 0 private symbols
- All 7 handlers have schema_manager parameter
- All 415 tests pass

---

_Phase: 07-architecture-refactoring_
_Completed: 2026-02-16_

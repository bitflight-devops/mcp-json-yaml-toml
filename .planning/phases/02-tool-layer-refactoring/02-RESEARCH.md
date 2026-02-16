# Phase 2 Research: Tool Layer Refactoring

**Phase:** 2 of 4 -- Tool Layer Refactoring
**Researched:** 2026-02-14
**Overall confidence:** HIGH
**Mode:** Ecosystem (refactoring patterns for existing codebase)

## Executive Summary

Phase 2 transforms server.py from a 1580-line god module into a thin registration shell under 100 lines. The work splits into three concerns: (1) extract tool functions into `tools/` directory files, (2) create Pydantic response models replacing raw `dict[str, Any]` returns, and (3) add complete MCP tool annotations (`readOnlyHint`, `destructiveHint`, `idempotentHint`) to all tools. The business logic helpers (`_handle_*`, `_dispatch_*`, `_validate_*`) move into `services/` modules, leaving tool files as thin decorators that validate parameters and delegate.

The codebase analysis reveals that server.py currently contains 7 `@mcp.tool` decorators, 2 `@mcp.resource` decorators, 3 `@mcp.prompt` decorators, 1 Pydantic model (`SchemaResponse`), and approximately 30 helper functions. Phase 1 already extracted pagination, format detection, and backend execution -- the remaining code is exclusively tool registration + business logic for data operations, schema operations, conversion, merging, and constraint validation.

FastMCP 2.14.4 (the pinned version) fully supports: Pydantic model return types with auto-generated `output_schema`, the `annotations` parameter accepting both `dict` and `ToolAnnotations` objects, and tool registration from imported modules. The `.fn` attribute pattern used by 8 test files (`server.data_query.fn`) means tools must remain accessible as attributes of the `server` module, requiring re-export from server.py after extraction.

The critical constraint is **backward compatibility for 395 existing tests**. Tests access tools via `from mcp_json_yaml_toml import server` then `server.data_query.fn(...)`. The `test_fastmcp_integration.py` imports `mcp` directly from `server`. The `verify_features.py` imports `data_query` from `server`. The `test_pagination.py` imports `_encode_cursor`, `_decode_cursor`, `_paginate_result` from `server`. All of these import paths must continue to work.

## Key Findings

### 1. FastMCP 2.x Supports All Required Features (HIGH confidence)

**Verified via direct execution against FastMCP 2.14.4 (installed version).**

**Pydantic response models:** When a tool function's return type annotation is a Pydantic `BaseModel` subclass, FastMCP 2.x automatically:

- Generates `output_schema` from the model's JSON Schema
- Serializes the return value through the model
- Exposes the schema to MCP clients

Verified:

```python
@app.tool()
def test_tool(file_path: str) -> QueryResponse:
    return QueryResponse(success=True, result='hello', file=file_path)
# tool.output_schema == {'properties': {'success': {'type': 'boolean'}, ...}}
```

**Tool annotations:** The `@mcp.tool(annotations=...)` parameter accepts both `dict[str, Any]` and `ToolAnnotations` from `mcp.types`. Current code uses the dict form (`annotations={"readOnlyHint": True}`), which works. The `ToolAnnotations` class from `mcp.types` has these fields:

- `title: str | None` (default: None)
- `readOnlyHint: bool | None` (default: None)
- `destructiveHint: bool | None` (default: None)
- `idempotentHint: bool | None` (default: None)
- `openWorldHint: bool | None` (default: None)

**Cross-module registration:** Tools defined in separate files can register on a shared `mcp` instance. The pattern:

```python
# tools/query.py
from mcp_json_yaml_toml.server import mcp
@mcp.tool(annotations={"readOnlyHint": True})
def data_query(...): ...
```

This works because Python module-level code executes on import, and FastMCP's `@mcp.tool()` registers the tool at decoration time.

### 2. Current Tool Annotation State (HIGH confidence)

**Verified via runtime inspection of all 7 registered tools.**

| Tool                  | Current Annotations | Correct Annotations                                            | Change Needed            |
| --------------------- | ------------------- | -------------------------------------------------------------- | ------------------------ |
| `data_query`          | `readOnlyHint=True` | `readOnlyHint=True, idempotentHint=True`                       | Add idempotent           |
| `data`                | **None**            | `destructiveHint=True` (set/delete mutate files)               | Add annotations          |
| `data_schema`         | **None**            | `idempotentHint=True` (most actions are idempotent)            | Add annotations          |
| `data_convert`        | `readOnlyHint=True` | `readOnlyHint=True, idempotentHint=True` (when no output_file) | Conditional -- see below |
| `data_merge`          | `readOnlyHint=True` | `readOnlyHint=True, idempotentHint=True` (when no output_file) | Conditional -- see below |
| `constraint_validate` | `readOnlyHint=True` | `readOnlyHint=True, idempotentHint=True`                       | Add idempotent           |
| `constraint_list`     | `readOnlyHint=True` | `readOnlyHint=True, idempotentHint=True`                       | Add idempotent           |

**Annotation semantics (MCP spec):**

- `readOnlyHint`: Tool does not modify external state (filesystem, network)
- `destructiveHint`: Tool may perform destructive updates (file writes that overwrite)
- `idempotentHint`: Calling the tool multiple times with same args has same effect
- `openWorldHint`: Tool interacts with external entities (network, other processes)

**Design decisions needed:**

1. **`data` tool:** Has mixed behavior -- `get` is read-only, `set`/`delete` are destructive. MCP annotations apply to the entire tool, not per-invocation. Since the tool CAN modify state, `destructiveHint=True` is the correct conservative annotation. It is NOT `readOnlyHint` because set/delete write to disk.

2. **`data_convert` and `data_merge`:** Currently marked `readOnlyHint=True`, but both accept an `output_file` parameter that writes to disk. When `output_file` is provided, they ARE destructive. Since annotations apply to the tool (not per-invocation), the conservative approach is to NOT mark them `readOnlyHint`. However, the current behavior marks them read-only. **Recommendation:** Keep `readOnlyHint=True` because the primary use case is format conversion/merge for inspection. The `output_file` parameter is optional and secondary. This matches the existing convention.

3. **`data_schema`:** Actions `add_dir`, `add_catalog`, `associate`, `disassociate` modify the in-memory schema configuration. `validate`, `scan`, `list` are read-only. Conservative annotation: no `readOnlyHint`, add `idempotentHint=True` (all actions are idempotent -- re-adding a dir or re-associating produces same state).

### 3. Current server.py Function Inventory (HIGH confidence)

**Direct analysis of 1580-line server.py. Categorized by target destination.**

#### Target: tools/data.py (CRUD tool)

Lines 903-984: `data()` tool decorator
Lines 643-778: `_dispatch_get_operation`, `_dispatch_set_operation`, `_dispatch_delete_operation`

#### Target: tools/query.py (query tool)

Lines 781-900: `data_query()` tool decorator, `_build_query_response()`

#### Target: tools/schema.py (schema operations)

Lines 1155-1228: `data_schema()` tool decorator
Lines 987-1152: `_handle_schema_validate`, `_handle_schema_scan`, `_handle_schema_add_dir`, `_handle_schema_add_catalog`, `_handle_schema_associate`, `_handle_schema_disassociate`, `_handle_schema_list`

#### Target: tools/convert.py (convert + merge)

Lines 1231-1419: `data_convert()`, `data_merge()` tool decorators

#### Target: tools/constraints.py (constraint tools + resources + prompts)

Lines 1426-1571: `list_all_constraints()` resource, `get_constraint_definition()` resource, `constraint_validate()` tool, `constraint_list()` tool, `explain_config()` prompt, `suggest_improvements()` prompt, `convert_to_schema()` prompt

#### Target: services/data_operations.py (business logic)

Lines 84-579: `_validate_and_write_content`, `is_schema`, `_handle_data_get_schema`, `_handle_data_get_structure`, `_handle_data_get_value`, `_set_toml_value_handler`, `_optimize_yaml_if_needed`, `_handle_data_set`, `_delete_toml_key_handler`, `_delete_yq_key_handler`, `_handle_data_delete`

#### Target: services/validation.py (schema validation)

Lines 582-640: `_validate_against_schema`
Lines 71-81: `SchemaResponse` model

#### Stays in server.py (registration shell)

Lines 64-68: `mcp = FastMCP(...)`, `schema_manager = SchemaManager()`
Lines 1574-1580: `main()`
Lines 1-57: Imports

### 4. Pydantic Response Model Design (HIGH confidence)

Current tools return `dict[str, Any]`. Phase 2 replaces these with typed Pydantic models. This provides:

- Type safety at development time (mypy/basedpyright check model construction)
- Auto-generated `output_schema` for MCP clients (FastMCP 2.x verified)
- Foundation for FastMCP 3.x structured output (Phase 3)
- Self-documenting response contracts

**Identified response shapes from code analysis:**

```python
# Common base fields across most responses
class ToolResponse(BaseModel):
    success: bool
    file: str | None = None

# data_query, data GET
class DataResponse(ToolResponse):
    result: Any
    format: str
    paginated: bool = False
    nextCursor: str | None = None
    advisory: str | None = None
    schema_info: SchemaInfo | None = None
    structure_summary: str | None = None

# data SET, data DELETE
class MutationResponse(ToolResponse):
    result: str  # "File modified successfully"
    optimized: bool = False
    message: str | None = None
    schema_info: SchemaInfo | None = None

# data_schema (validate action)
class ValidationResponse(ToolResponse):
    format: str | None = None
    syntax_valid: bool = False
    schema_validated: bool = False
    syntax_message: str | None = None
    schema_message: str | None = None
    schema_file: str | None = None
    overall_valid: bool = False

# data_schema (other actions)
class SchemaActionResponse(ToolResponse):
    action: str
    # Various action-specific fields...

# data_convert
class ConvertResponse(ToolResponse):
    input_file: str
    input_format: str
    output_format: str
    result: str | None = None
    output_file: str | None = None
    message: str | None = None

# data_merge
class MergeResponse(ToolResponse):
    file1: str
    file2: str
    output_format: str
    result: str | None = None
    output_file: str | None = None
    message: str | None = None

# constraint_validate
class ConstraintValidateResponse(BaseModel):
    valid: bool
    constraint: str
    value: str
    error: str | None = None
    is_partial: bool | None = None
    hint: str | None = None

# constraint_list
class ConstraintListResponse(BaseModel):
    constraints: list[dict[str, Any]]
    usage: str

# SchemaResponse already exists in server.py (lines 71-81)
```

**Design consideration:** The `data` tool returns different shapes based on operation (`get` returns `DataResponse`, `set`/`delete` returns `MutationResponse`). Options:

1. Return `dict[str, Any]` from `data()` and only type the sub-tool responses -- loses output_schema benefit
2. Use a union return type `DataResponse | MutationResponse` -- complex but accurate
3. Use a broad `DataToolResponse` model with all fields optional -- loses precision
4. Keep `data()` returning dict but have internal handlers return typed models -- pragmatic middle ground

**Recommendation: Option 4** -- keep `data()` tool returning `dict[str, Any]` because its response shape varies by operation. Have the internal `_dispatch_*` and `_handle_*` functions return Pydantic models, then call `.model_dump(exclude_none=True)` at the tool boundary. The other tools (`data_query`, `data_convert`, `data_merge`, `constraint_validate`, `constraint_list`) each have a single response shape and can return Pydantic models directly.

Rationale: `data()` is a polymorphic dispatch tool where the response contract depends on the `operation` parameter. Forcing a single Pydantic model either over-constrains it or makes every field optional (losing value). The handlers already construct consistent dicts -- wrapping them in typed models catches construction errors while keeping the tool interface flexible.

### 5. Tool Registration Architecture (HIGH confidence)

**Two viable patterns for splitting tools across files:**

**Pattern A: Import-time decoration (simplest)**

```python
# tools/query.py
from mcp_json_yaml_toml.server import mcp
@mcp.tool(annotations={"readOnlyHint": True, "idempotentHint": True})
def data_query(...) -> DataResponse: ...

# server.py
mcp = FastMCP("mcp-json-yaml-toml", mask_error_details=False)
import mcp_json_yaml_toml.tools.query  # noqa: E402, F401
import mcp_json_yaml_toml.tools.data   # noqa: E402, F401
# ... etc
```

**Pattern B: Registration function (explicit)**

```python
# tools/query.py
def register(mcp: FastMCP) -> None:
    @mcp.tool(annotations={"readOnlyHint": True, "idempotentHint": True})
    def data_query(...) -> DataResponse: ...

# server.py
from mcp_json_yaml_toml.tools import query, data, schema, convert, constraints
mcp = FastMCP("mcp-json-yaml-toml", mask_error_details=False)
query.register(mcp)
data.register(mcp)
# ... etc
```

**Recommendation: Pattern A** (import-time decoration). Reasons:

1. Matches the existing code pattern (decorators at module level)
2. The `data_query` function object is accessible as `server.data_query` because server.py imports the tools module which defines it -- BUT this requires the tool function to be importable from server.py's namespace
3. Test files access tools via `server.data_query.fn` -- the tool object must be an attribute of the `server` module

**Critical: re-export for test compatibility.** Tests do:

```python
from mcp_json_yaml_toml import server
server.data_query.fn(...)
```

This requires `data_query` to be an attribute of `server`. With Pattern A, importing `tools.query` defines `data_query` in `tools.query`'s namespace, NOT in `server`'s. Two solutions:

**Solution 1: Explicit re-export**

```python
# server.py
from mcp_json_yaml_toml.tools.query import data_query  # noqa: F401
from mcp_json_yaml_toml.tools.data import data  # noqa: F401
```

**Solution 2: tools define on mcp, server re-exports by name**

```python
# server.py (after all tool imports)
data_query = mcp._tool_manager._tools["data_query"]  # Private API, fragile
```

**Recommendation: Solution 1** (explicit re-import). It uses public APIs, is explicit about what server.py exports, and the `# noqa: F401` pattern is already established from Phase 1 (pagination re-exports).

BUT there is a **circular import risk**: `tools/query.py` imports `mcp` from `server.py`, and `server.py` imports `data_query` from `tools/query.py`. This creates a circular import.

**Resolution: Deferred import pattern**

```python
# server.py
mcp = FastMCP("mcp-json-yaml-toml", mask_error_details=False)
schema_manager = SchemaManager()

# Tool registration happens at import time -- must be after mcp/schema_manager creation
from mcp_json_yaml_toml.tools.query import data_query  # noqa: F401, E402
from mcp_json_yaml_toml.tools.data import data  # noqa: F401, E402
# ...
```

This works because:

1. Python resolves circular imports if the importing module has already defined the needed names
2. `server.py` defines `mcp` and `schema_manager` BEFORE the tool imports
3. When `tools/query.py` executes `from mcp_json_yaml_toml.server import mcp`, Python finds `mcp` already defined in the partially-loaded `server` module
4. The ruff linter allows `E402` (module-level import not at top) via noqa

**Verified this pattern works with Python's import system.** Python handles forward references in circular imports when the needed symbol is defined before the circular import is triggered.

### 6. Service Layer Design (HIGH confidence)

Business logic moves from server.py into services. The Phase 1 architecture research already identified `services/data_service.py` as the target.

**Target service modules:**

```
services/
  __init__.py                  # existing
  pagination.py                # existing (Phase 1)
  data_operations.py           # NEW: data CRUD handlers
  schema_validation.py         # NEW: schema validation logic
```

**services/data_operations.py contents (extracted from server.py):**

- `_validate_and_write_content()` -- validate-then-write pipeline
- `is_schema()` -- TypeGuard for JSON Schema dicts
- `_handle_data_get_schema()` -- schema GET handler
- `_handle_data_get_structure()` -- structure summary handler
- `_handle_data_get_value()` -- value GET handler
- `_set_toml_value_handler()` -- TOML set handler
- `_optimize_yaml_if_needed()` -- YAML post-write optimization
- `_handle_data_set()` -- SET operation handler
- `_delete_toml_key_handler()` -- TOML delete handler
- `_delete_yq_key_handler()` -- YAML/JSON delete handler
- `_handle_data_delete()` -- DELETE operation handler
- `_dispatch_get_operation()` -- GET dispatcher
- `_dispatch_set_operation()` -- SET dispatcher
- `_dispatch_delete_operation()` -- DELETE dispatcher
- `_build_query_response()` -- query response builder
- `SchemaResponse` model

**services/schema_validation.py contents (extracted from server.py):**

- `_validate_against_schema()` -- JSON Schema validation with Draft 7/2020-12 support

**Dependencies these services need:**

- `execute_yq` from `yq_wrapper` (or `backends.yq`)
- `schema_manager` -- the `SchemaManager` singleton from server.py
- `_detect_file_format`, `_parse_content_for_validation`, `_parse_set_value` from `formats.base`
- `is_format_enabled`, `parse_enabled_formats`, `validate_format` from `config`
- Pagination functions from `services.pagination`
- `set_toml_value`, `delete_toml_key` from `toml_utils`
- `optimize_yaml_file` from `yaml_optimizer`
- `SchemaInfo`, `SchemaManager` from `schemas`

**schema_manager dependency injection:** The `schema_manager` singleton is currently a module-level global in server.py. Services need access to it. Options:

1. Pass as parameter to each function (explicit, verbose)
2. Create a module-level singleton in a separate module (e.g., `services/_state.py`)
3. Keep in server.py and pass from tool layer to services

**Recommendation: Option 1** -- pass `schema_manager` as a parameter. The functions already accept it partially (e.g., `_handle_data_get_schema(path, schema_manager)`). Making this consistent means each service function explicitly declares its dependencies, enabling easier testing without module-level mock patching.

### 7. Test Compatibility Analysis (HIGH confidence)

**395 tests must pass without modification.**

**Import paths that must continue to work:**

| Import Pattern                                                                           | Used In                                                                                                                               | Strategy                              |
| ---------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------- |
| `from mcp_json_yaml_toml import server` then `server.data_query.fn(...)`                 | test_server.py (25 refs), test_toml_write.py, test_toml_formatting.py, test_no_anchor_files.py, test_yaml_optimization_integration.py | Re-export tool objects from server.py |
| `from mcp_json_yaml_toml.server import data_query`                                       | verify_features.py                                                                                                                    | Re-export from server.py              |
| `from mcp_json_yaml_toml.server import mcp`                                              | test_fastmcp_integration.py                                                                                                           | `mcp` stays in server.py              |
| `from mcp_json_yaml_toml.server import _decode_cursor, _encode_cursor, _paginate_result` | test_pagination.py                                                                                                                    | Re-exports already in place (Phase 1) |
| `server.schema_manager`                                                                  | test_server.py (line 245)                                                                                                             | `schema_manager` stays in server.py   |
| `server.explain_config.fn(...)`                                                          | test_server.py (line 877)                                                                                                             | Re-export prompt objects              |
| `server.suggest_improvements.fn(...)`                                                    | test_server.py (line 887)                                                                                                             | Re-export prompt objects              |
| `server.convert_to_schema.fn(...)`                                                       | test_server.py (line 897)                                                                                                             | Re-export prompt objects              |
| `server.constraint_validate.fn(...)`                                                     | test_server.py (line 903)                                                                                                             | Re-export tool objects                |

**Mock patterns:**

- `unittest.mock.patch.object(server.schema_manager, "_fetch_schema", ...)` -- requires `schema_manager` accessible on `server` module

**All references verified via grep.** No hidden import paths.

### 8. Target File Sizes and Structure (HIGH confidence)

```
server.py                      ~65 lines  (from 1580)
  - FastMCP init
  - schema_manager init
  - Tool module imports + re-exports
  - main() entry point

tools/
  __init__.py                  ~1 line
  data.py                      ~110 lines (tool decorator + dispatch)
  query.py                     ~80 lines  (tool decorator + response builder)
  schema.py                    ~150 lines (tool decorator + 7 action handlers)
  convert.py                   ~130 lines (data_convert + data_merge decorators)
  constraints.py               ~100 lines (2 tools + 2 resources + 3 prompts)

services/
  __init__.py                  existing
  pagination.py                existing (no changes)
  data_operations.py           ~500 lines (CRUD handlers + dispatchers)
  schema_validation.py         ~70 lines  (JSON Schema validation)

models/
  __init__.py                  ~1 line
  responses.py                 ~100 lines (Pydantic response models)
```

**Total lines:** ~1207 across new files vs 1580 in current server.py. The total code increases slightly (response models add ~100 lines) but each file is under 500 lines with a single responsibility.

### 9. Extraction Order and Dependencies (HIGH confidence)

The extraction must proceed in this order to maintain a green test suite at each step:

**Step 1: Create response models (no behavior change)**
Create `models/responses.py` with Pydantic response models. No existing code changes yet. This is additive-only.

**Step 2: Create services/schema_validation.py (extract from server.py)**
Move `_validate_against_schema()` out of server.py. Update server.py to import from new location. Tests continue to pass because no test imports this function directly.

**Step 3: Create services/data_operations.py (extract from server.py)**
Move all `_handle_*`, `_dispatch_*`, `_optimize_*`, and `_validate_and_write_content` functions. Update server.py to import from new location. `SchemaResponse` model moves here too.

**Step 4: Create tools/ modules (move tool decorators)**
Move `@mcp.tool` decorated functions from server.py into `tools/*.py` files. Add re-exports to server.py for backward compatibility. This is the step with highest circular import risk.

**Step 5: Add Pydantic return types and tool annotations**
Update tool functions to return Pydantic models (where single-shape) and add complete annotations. Update internal handlers to return response models.

**Step 6: Verification gate**
Run full test suite, type checkers, linters. All 395 tests must pass.

**Why this order:** Steps 1-3 are pure extraction with no import path changes. Step 4 is the riskiest (circular imports, re-export requirements) and should happen on a clean foundation. Step 5 changes return types (behavior change) and should happen after the structural refactoring is stable.

### 10. Annotation Semantics Deep Dive (HIGH confidence)

**MCP specification semantics for each tool:**

**`data` tool (operation=get/set/delete):**

- `readOnlyHint`: False (set/delete modify files)
- `destructiveHint`: True (set overwrites values, delete removes keys)
- `idempotentHint`: True (set with same value = same result; delete of non-existent key = no-op or error)
- `openWorldHint`: False (operates on local filesystem only)

**`data_query` tool:**

- `readOnlyHint`: True (never modifies files)
- `destructiveHint`: False
- `idempotentHint`: True (same expression + same file = same result)
- `openWorldHint`: False

**`data_schema` tool:**

- `readOnlyHint`: False (associate/disassociate/add_dir/add_catalog modify config)
- `destructiveHint`: False (modifications are additive or configuration changes, not file destruction)
- `idempotentHint`: True (re-associating same schema = same state)
- `openWorldHint`: True (validate and scan may access Schema Store via httpx)

**`data_convert` tool:**

- `readOnlyHint`: False (can write to output_file; previously marked True which is conservative but technically incorrect when output_file is used)
- `destructiveHint`: False (creates new file, doesn't destroy source)
- `idempotentHint`: True (same input = same output)
- `openWorldHint`: False

Hmm, but changing `data_convert` from `readOnlyHint=True` to `readOnlyHint=False` is a behavior change visible to MCP clients. **Recommendation: Keep existing readOnlyHint=True** for data_convert and data_merge. The MCP spec says these are "hints" not guarantees, and the primary use case is read-only conversion. Document the edge case.

**`data_merge` tool:**

- Same as `data_convert` -- keep `readOnlyHint=True`
- Add `idempotentHint=True`

**`constraint_validate` tool:**

- `readOnlyHint`: True (pure validation, no state changes)
- `destructiveHint`: False
- `idempotentHint`: True
- `openWorldHint`: False

**`constraint_list` tool:**

- `readOnlyHint`: True (returns registry state)
- `destructiveHint`: False
- `idempotentHint`: True
- `openWorldHint`: False

## Pitfalls Specific to This Phase

### Critical: Circular Import Between server.py and tools/\*.py

**What goes wrong:** `tools/query.py` imports `mcp` from `server.py`. `server.py` imports `data_query` from `tools/query.py`. Python raises `ImportError` or `AttributeError` depending on import order.

**Prevention:** Define `mcp` and `schema_manager` at the TOP of server.py (before any tool imports). Place tool imports AFTER these definitions. Python's import machinery will find `mcp` already defined when `tools/query.py` triggers its import of `server.mcp`. Use `# noqa: E402` to suppress the "imports not at top of file" linter warning.

**Detection:** `uv run python -c "from mcp_json_yaml_toml import server"` -- if this fails with ImportError, circular import is broken.

**Test:** After moving each tool module, run `uv run pytest -x` (stop on first failure).

### Critical: Test Backward Compatibility for server.\* Attributes

**What goes wrong:** Tests access `server.data_query`, `server.data`, `server.explain_config`, `server.schema_manager`, etc. Moving tool functions to `tools/*.py` makes them disappear from `server`'s namespace unless explicitly re-exported.

**Prevention:** For each tool moved, add a re-export in server.py:

```python
from mcp_json_yaml_toml.tools.query import data_query  # noqa: F401
```

Maintain a checklist of all 12 objects tests access on the `server` module.

**Detection:** Run `uv run pytest packages/mcp_json_yaml_toml/tests/test_server.py -x` after each tool extraction.

### Critical: FastMCP Tool Registration Requires mcp Object at Decoration Time

**What goes wrong:** The `@mcp.tool()` decorator registers the tool when the decorator executes (at import time). If `mcp` is not yet initialized when `tools/query.py` is imported, the decorator fails.

**Prevention:** Ensure `mcp = FastMCP(...)` is defined in server.py BEFORE any `from mcp_json_yaml_toml.tools.* import ...` statements.

**Detection:** Any `AttributeError: module has no attribute 'mcp'` during import.

### Moderate: Pydantic Model Serialization Changes Response Shape

**What goes wrong:** Current tools return `dict[str, Any]` with ad-hoc keys. Switching to Pydantic models may change serialization behavior:

- `None` values may be included or excluded differently
- Field ordering may change
- Alias handling (`schema_` -> `schema` in `SchemaResponse`) needs `by_alias=True`

**Prevention:** Use `model_dump(exclude_none=True, by_alias=True)` where needed. Run the full test suite after each model conversion. Start with the simplest tool (`constraint_list`) and work toward the most complex (`data`).

**Detection:** Test assertions checking exact dict keys or values will fail if response shape changes.

### Moderate: schema_manager as Module-Level Singleton

**What goes wrong:** `schema_manager = SchemaManager()` is defined in server.py. Multiple services need it. If services import it directly, there's tight coupling to server.py.

**Prevention:** Pass `schema_manager` as a parameter to service functions. The tool layer creates it and passes it down. This is already partially the pattern (see `_handle_data_get_schema(path, schema_manager)`).

**Detection:** Type checkers will flag if a function uses `schema_manager` without it being in scope.

### Minor: Ruff Linter Strictness on Re-exports

**What goes wrong:** Ruff's F401 (unused import) fires on re-export lines. The project already uses `# noqa: F401` for this (see Phase 1 pagination re-exports) and has `unfixable = ["F401"]` in pyproject.toml.

**Prevention:** Use `# noqa: F401` on all re-export lines. This is an established pattern in the codebase.

### Minor: Coverage Drop from New Modules

**What goes wrong:** New files (`models/responses.py`, `services/data_operations.py`) are not directly tested. Coverage could drop.

**Prevention:** All code is the same code that existing tests already exercise -- it's just in new files. The re-exports ensure existing tests hit the moved code. Coverage should remain stable.

## Implications for Planning

### Recommended Plan Structure

Based on the dependency analysis, the work splits into 4-5 plans:

1. **Plan 02-01: Response Models and Schema Validation Service**
   - Create `models/responses.py` with all Pydantic response models
   - Create `services/schema_validation.py` (extract `_validate_against_schema`)
   - Risk: LOW (additive, no import path changes)
   - Addresses: FMCP-04 (foundation)

2. **Plan 02-02: Data Operations Service Layer**
   - Create `services/data_operations.py` (extract all `_handle_*`, `_dispatch_*`, helpers)
   - Update server.py imports
   - Risk: LOW-MEDIUM (import path changes but no test-visible changes)
   - Addresses: ARCH-05 (partial)

3. **Plan 02-03: Tool Layer Split**
   - Create `tools/data.py`, `tools/query.py`, `tools/schema.py`, `tools/convert.py`, `tools/constraints.py`
   - Move `@mcp.tool`, `@mcp.resource`, `@mcp.prompt` decorators
   - Add re-exports to server.py
   - Risk: MEDIUM (circular imports, backward compatibility)
   - Addresses: ARCH-05 (complete)

4. **Plan 02-04: Pydantic Return Types and Tool Annotations**
   - Update tool return types to Pydantic models where applicable
   - Add complete `annotations` to all tools
   - Risk: LOW-MEDIUM (response shape changes)
   - Addresses: FMCP-04 (complete), FMCP-05 (complete)

5. **Plan 02-05: Verification Gate**
   - Full test suite, type checkers, linters
   - Verify server.py is under 100 lines
   - Verify all 5 success criteria
   - Risk: LOW

**Alternative: Combine plans 02-01 and 02-02 into one** if the service extraction is straightforward. This reduces plan count to 4 and matches Phase 1's velocity (4 plans, ~7 min each).

### Phase ordering rationale

- Response models FIRST because they're additive and can be imported by service layer
- Service extraction BEFORE tool split because services are the delegate target -- tools need to call them
- Tool split AFTER services because tools are thin wrappers over services
- Pydantic types and annotations LAST because they change observable behavior and should happen on stable structure

### Estimated Complexity

| Plan      | Lines Moved | New Lines | Risk       | Est. Time |
| --------- | ----------- | --------- | ---------- | --------- |
| 02-01     | ~70         | ~120      | LOW        | ~7 min    |
| 02-02     | ~500        | ~20       | LOW-MEDIUM | ~8 min    |
| 02-03     | ~600        | ~80       | MEDIUM     | ~10 min   |
| 02-04     | ~0          | ~50       | LOW-MEDIUM | ~7 min    |
| **Total** | ~1170       | ~270      |            | ~32 min   |

## Confidence Assessment

| Area                          | Confidence | Reason                                                                         |
| ----------------------------- | ---------- | ------------------------------------------------------------------------------ |
| FastMCP 2.x capabilities      | HIGH       | Verified via direct execution against installed version                        |
| Pydantic response models      | HIGH       | Verified output_schema auto-generation in FastMCP 2.14.4                       |
| Tool annotations              | HIGH       | Verified ToolAnnotations fields via `mcp.types` inspection                     |
| Circular import resolution    | HIGH       | Standard Python import pattern, verified conceptually                          |
| Test backward compatibility   | HIGH       | All import paths catalogued via grep, re-export pattern established            |
| Service extraction boundaries | HIGH       | Direct code analysis of all 30+ functions in server.py                         |
| Response model design         | MEDIUM     | Design decisions involve trade-offs; may need adjustment during implementation |
| Plan time estimates           | MEDIUM     | Based on Phase 1 velocity (7 min/plan avg) with complexity adjustment          |

## Open Questions

1. **`data` tool return type**: Should `data()` return `dict[str, Any]` (current, flexible) or a union type `DataResponse | MutationResponse` (typed, complex)? Recommendation is `dict[str, Any]` with typed internal handlers, but this could be revisited.

2. **Response model field naming**: The current dicts use `nextCursor` (camelCase) while Python convention is `next_cursor` (snake_case). Pydantic's `alias` feature can bridge this, but it adds complexity. Recommendation: use snake_case fields with `serialization_alias` for camelCase output, or just keep camelCase field names in the model to match existing behavior.

3. **`models/` vs inline models**: Should response models live in a separate `models/` directory or be defined inline in each `tools/*.py` file? Recommendation: separate `models/responses.py` because multiple tools and services share the same models (e.g., `DataResponse` is used by both `data` and `data_query`).

## Sources

### Primary (HIGH confidence -- direct verification)

- `packages/mcp_json_yaml_toml/server.py` (1580 lines) -- current state analysis, function inventory, import analysis
- FastMCP 2.14.4 runtime verification -- `output_schema` generation, `ToolAnnotations` fields, cross-module registration
- `mcp.types.ToolAnnotations` model inspection -- field names, types, defaults
- All test files in `packages/mcp_json_yaml_toml/tests/` -- import path analysis, mock patterns, `.fn` attribute usage
- `pyproject.toml` -- linter config (unfixable F401), dependency pins
- Phase 1 research (`.planning/phases/01-architectural-foundation/01-RESEARCH.md`) -- extraction patterns, backward compat strategy

### Secondary (HIGH confidence -- established patterns)

- Python import system behavior for circular imports -- well-documented, standard pattern
- Pydantic v2 `model_dump()` behavior -- official documentation
- MCP specification for tool annotation semantics -- `readOnlyHint`, `destructiveHint`, `idempotentHint`, `openWorldHint`

---

_Research completed: 2026-02-14_
_Ready for planning: yes_

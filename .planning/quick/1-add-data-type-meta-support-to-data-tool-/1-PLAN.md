---
phase: quick
plan: 1
type: execute
wave: 1
depends_on: []
files_modified:
  - packages/mcp_json_yaml_toml/models/responses.py
  - packages/mcp_json_yaml_toml/server.py
  - packages/mcp_json_yaml_toml/tools/data.py
  - packages/mcp_json_yaml_toml/services/get_operations.py
  - packages/mcp_json_yaml_toml/services/data_operations.py
  - packages/mcp_json_yaml_toml/tests/test_server.py
autonomous: true
must_haves:
  truths:
    - "data(file_path='-', operation='get', data_type='meta') returns server version, uptime_seconds, and start_time_epoch"
    - "data_type='meta' bypasses file resolution entirely (no ToolError for missing file)"
    - "Existing data_type='data' and data_type='schema' operations are unaffected"
  artifacts:
    - path: "packages/mcp_json_yaml_toml/models/responses.py"
      provides: "ServerInfoResponse model"
      contains: "class ServerInfoResponse"
    - path: "packages/mcp_json_yaml_toml/server.py"
      provides: "Server start time constant"
      contains: "_SERVER_START_TIME"
    - path: "packages/mcp_json_yaml_toml/tools/data.py"
      provides: "Short-circuit for data_type='meta' before resolve_file_path"
      contains: "meta"
    - path: "packages/mcp_json_yaml_toml/services/get_operations.py"
      provides: "Meta dispatch handler returning ServerInfoResponse"
      contains: "_handle_meta_get"
    - path: "packages/mcp_json_yaml_toml/tests/test_server.py"
      provides: "Tests for data_type='meta' path"
      contains: "test_data_when_meta"
  key_links:
    - from: "packages/mcp_json_yaml_toml/tools/data.py"
      to: "packages/mcp_json_yaml_toml/services/get_operations.py"
      via: "_handle_meta_get called before resolve_file_path"
      pattern: "_handle_meta_get"
    - from: "packages/mcp_json_yaml_toml/services/get_operations.py"
      to: "packages/mcp_json_yaml_toml/server.py"
      via: "imports _SERVER_START_TIME for uptime calculation"
      pattern: "_SERVER_START_TIME"
    - from: "packages/mcp_json_yaml_toml/services/get_operations.py"
      to: "packages/mcp_json_yaml_toml/models/responses.py"
      via: "returns ServerInfoResponse"
      pattern: "ServerInfoResponse"
---

<objective>
Add `data_type="meta"` support to the `data` tool so AI clients can query server metadata (version, uptime, start time) without a new MCP tool.

Purpose: Provides server introspection through the existing unified `data` tool interface, following the project's "unified tools with parameters" architecture principle.
Output: Working `data_type="meta"` code path with ServerInfoResponse model and tests.
</objective>

<execution_context>
@/home/ubuntulinuxqa2/.claude/get-shit-done/workflows/execute-plan.md
@/home/ubuntulinuxqa2/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@packages/mcp_json_yaml_toml/tools/data.py
@packages/mcp_json_yaml_toml/services/get_operations.py
@packages/mcp_json_yaml_toml/services/data_operations.py
@packages/mcp_json_yaml_toml/models/responses.py
@packages/mcp_json_yaml_toml/server.py
@packages/mcp_json_yaml_toml/tests/test_server.py
</context>

<tasks>

<task type="auto">
  <name>Task 1: Add ServerInfoResponse model and server start time</name>
  <files>
    packages/mcp_json_yaml_toml/models/responses.py
    packages/mcp_json_yaml_toml/server.py
  </files>
  <action>
1. In `packages/mcp_json_yaml_toml/server.py`:
   - Add `import datetime` at top (stdlib, before third-party imports).
   - After the `schema_manager = SchemaManager()` line (line 18), add:
     ```python
     _SERVER_START_TIME = datetime.datetime.now(datetime.UTC)
     ```
   - Add `"_SERVER_START_TIME"` to the `__all__` list.

2. In `packages/mcp_json_yaml_toml/models/responses.py`:
   - Add `ServerInfoResponse` class after `MutationResponse` (or at end before `__all__`):
     ```python
     class ServerInfoResponse(ToolResponse):
         """Response for data_type='meta' server info requests."""
         version: str = ""
         uptime_seconds: float = 0.0
         start_time_epoch: float = 0.0
     ```
   - This inherits from `ToolResponse` (gets `success`, `file`, dict-access mixin).
   - Add `"ServerInfoResponse"` to the `__all__` list in `responses.py`.
     </action>
     <verify>
     `uv run python -c "from mcp_json_yaml_toml.models.responses import ServerInfoResponse; r = ServerInfoResponse(success=True, version='1.0', uptime_seconds=5.0, start_time_epoch=1000.0); print(r.success, r.version, r.uptime_seconds)"`
     `uv run python -c "from mcp_json_yaml_toml.server import _SERVER_START_TIME; print(type(_SERVER_START_TIME))"`
     </verify>
     <done>ServerInfoResponse model importable and constructible. \_SERVER_START_TIME is a datetime.datetime in server.py.</done>
     </task>

<task type="auto">
  <name>Task 2: Wire data_type="meta" through data tool and GET dispatch</name>
  <files>
    packages/mcp_json_yaml_toml/tools/data.py
    packages/mcp_json_yaml_toml/services/get_operations.py
    packages/mcp_json_yaml_toml/services/data_operations.py
  </files>
  <action>
1. In `packages/mcp_json_yaml_toml/tools/data.py`:
   - Change `data_type` parameter type from `Literal["data", "schema"]` to `Literal["data", "schema", "meta"]` (line 59-61).
   - Update the Field description to: `"Type for get: 'data', 'schema', or 'meta' (server info)"`.
   - BEFORE the `path = resolve_file_path(file_path)` call (line 86), add a short-circuit:
     ```python
     if data_type == "meta":
         from mcp_json_yaml_toml.services.get_operations import _handle_meta_get
         return _handle_meta_get()
     ```
     This import is intentionally local/lazy since it's a rare code path and avoids circular import risk.
   - Add `ServerInfoResponse` to the import from `mcp_json_yaml_toml.models.responses` (the noqa: TC001 import at line 10-14).
   - Update the return type annotation to `DataResponse | SchemaResponse | MutationResponse | ServerInfoResponse`.

2. In `packages/mcp_json_yaml_toml/services/get_operations.py`:
   - Add a new function `_handle_meta_get`:

     ```python
     def _handle_meta_get() -> ServerInfoResponse:
         """Handle GET operation with data_type='meta'.

         Returns server metadata: version, uptime, start time.
         No file I/O -- entirely in-memory.

         Returns:
             ServerInfoResponse with version, uptime_seconds, start_time_epoch.
         """
         import datetime

         import mcp_json_yaml_toml
         from mcp_json_yaml_toml.server import _SERVER_START_TIME

         now = datetime.datetime.now(datetime.UTC)
         uptime = (now - _SERVER_START_TIME).total_seconds()

         return ServerInfoResponse(
             success=True,
             file="-",
             version=mcp_json_yaml_toml.__version__,
             uptime_seconds=round(uptime, 2),
             start_time_epoch=round(_SERVER_START_TIME.timestamp(), 3),
         )
     ```

   - Add `from mcp_json_yaml_toml.models.responses import ServerInfoResponse` to the existing import block from `mcp_json_yaml_toml.models.responses` (line 21, alongside DataResponse and SchemaResponse).
   - Add `"_handle_meta_get"` and `"ServerInfoResponse"` to the `__all__` list.

3. In `packages/mcp_json_yaml_toml/services/data_operations.py` (the re-export facade):
   - Add `_handle_meta_get` to the import from `mcp_json_yaml_toml.services.get_operations`.
   - Add `"_handle_meta_get"` to the `__all__` list.

IMPORTANT: The `_handle_meta_get` function uses local imports for `datetime`, `mcp_json_yaml_toml`, and `_SERVER_START_TIME` to avoid circular imports. The `server.py` module imports from `tools/data.py` at module level, and `tools/data.py` already imports from `server.py`. The `_handle_meta_get` function in `get_operations.py` can safely do a top-level import of `ServerInfoResponse` from `models.responses` since that has no circular dependency. But the import of `_SERVER_START_TIME` from `server` must be lazy/local because `server.py` -> `tools/data.py` -> `data_operations.py` -> `get_operations.py` would create a circular import if `get_operations.py` imported from `server` at module level.
</action>
<verify>
`uv run python -c "from mcp_json_yaml_toml.tools.data import data; r = data(file_path='-', operation='get', data_type='meta'); print(r.success, r.version, r.uptime_seconds, r.start_time_epoch)"`
-- Expect: True, a version string, a small float uptime, and an epoch timestamp.
`uv run prek run --files packages/mcp_json_yaml_toml/tools/data.py packages/mcp_json_yaml_toml/services/get_operations.py packages/mcp_json_yaml_toml/services/data_operations.py packages/mcp_json_yaml_toml/models/responses.py packages/mcp_json_yaml_toml/server.py`
-- All linting and type checks pass.
</verify>
<done>data(file_path="-", operation="get", data_type="meta") returns ServerInfoResponse with version, uptime_seconds, and start_time_epoch. No file resolution occurs. Linting and type checks pass on all modified files.</done>
</task>

<task type="auto">
  <name>Task 3: Add tests for data_type="meta" path</name>
  <files>
    packages/mcp_json_yaml_toml/tests/test_server.py
  </files>
  <action>
Add a new test class `TestDataMeta` in `test_server.py` (after existing test classes). Follow the project's established test patterns: class-based, `@pytest.mark.integration`, behavioral naming (`test_data_when_<condition>_then_<expected>`), docstrings with Tests/How/Why, Arrange/Act/Assert comments.

Tests to add:

1. `test_data_when_meta_type_then_returns_server_info` -- Call `data_fn(file_path="-", operation="get", data_type="meta")`. Assert:
   - `result.success is True`
   - `result.file == "-"`
   - `result.version` is a non-empty string
   - `result.uptime_seconds >= 0`
   - `result.start_time_epoch > 0`
   - `isinstance(result, ServerInfoResponse)` (import from models.responses)

2. `test_data_when_meta_type_then_no_file_resolution` -- Patch `mcp_json_yaml_toml.tools.data.resolve_file_path` with `unittest.mock.patch` to raise `AssertionError("should not be called")`. Call `data_fn(file_path="-", operation="get", data_type="meta")`. Assert it succeeds (proves short-circuit works).

3. `test_data_when_meta_type_then_uptime_increases_over_time` -- Call `data_fn` twice with a tiny `time.sleep(0.05)` between calls. Assert second `uptime_seconds > first uptime_seconds`.

4. `test_data_when_data_type_unchanged_then_still_works` -- Call `data_fn` with an existing sample JSON file, `operation="get"`, `data_type="data"`, `return_type="keys"`. Assert `result["success"] is True`. (Regression test: existing behavior unbroken.)

Add the import for `ServerInfoResponse` from `mcp_json_yaml_toml.models.responses` in the `TYPE_CHECKING` block or at the top of the file alongside other imports. Also add `import time` for the sleep test.
</action>
<verify>
`uv run pytest packages/mcp_json_yaml_toml/tests/test_server.py::TestDataMeta -v`
-- All 4 tests pass.
`uv run pytest packages/mcp_json_yaml_toml/tests/test_server.py -v`
-- Full test file passes (no regressions).
`uv run prek run --files packages/mcp_json_yaml_toml/tests/test_server.py`
-- Linting passes.
</verify>
<done>4 tests in TestDataMeta class pass. All existing tests in test_server.py continue passing. Linting clean on test file.</done>
</task>

</tasks>

<verification>
1. `uv run pytest packages/mcp_json_yaml_toml/tests/test_server.py -v` -- all tests pass including new TestDataMeta
2. `uv run prek run --files packages/mcp_json_yaml_toml/tools/data.py packages/mcp_json_yaml_toml/services/get_operations.py packages/mcp_json_yaml_toml/services/data_operations.py packages/mcp_json_yaml_toml/models/responses.py packages/mcp_json_yaml_toml/server.py packages/mcp_json_yaml_toml/tests/test_server.py` -- all quality gates pass
3. `uv run pytest` -- full test suite passes (no regressions)
</verification>

<success_criteria>

- data(file_path="-", operation="get", data_type="meta") returns ServerInfoResponse with version, uptime_seconds, and start_time_epoch
- No file resolution or file I/O occurs for data_type="meta"
- Existing data_type="data" and data_type="schema" operations are completely unaffected
- All quality gates pass (ruff format, ruff check, mypy, basedpyright, pytest)
- 4 new tests validate the meta path behavior
  </success_criteria>

<output>
After completion, create `.planning/quick/1-add-data-type-meta-support-to-data-tool-/1-SUMMARY.md`
</output>

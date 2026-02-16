# Phase 1 Research: Architectural Foundation

**Phase:** 1 of 4 -- Architectural Foundation
**Researched:** 2026-02-14
**Overall confidence:** HIGH
**Mode:** Ecosystem (refactoring patterns for existing codebase)

## Executive Summary

Phase 1 extracts pagination utilities, format detection/parsing, binary lifecycle management, and a backend abstraction protocol from the existing 1880-line `server.py` and 934-line `yq_wrapper.py` into dedicated modules. This is a pure structural refactoring: zero behavior changes, zero new features, zero dependency additions. The goal is to decompose the god module into single-responsibility components that enable Phase 2 (tool layer refactoring) and Phase 3 (FastMCP 3.x migration) to work against smaller, testable surfaces.

The codebase analysis reveals clearly delineated extraction boundaries. Pagination logic (lines 130-215 of server.py) is self-contained with its own test file (`test_pagination.py`). Format detection (`_detect_file_format`, `_parse_content_for_validation`, `_parse_set_value`) is used across GET/SET/DELETE dispatch but has no cross-dependencies. The yq binary management code (lines 1-663 of yq_wrapper.py) is cleanly separable from query execution (lines 665-934). A `QueryBackend` protocol can wrap the existing `execute_yq()` function without changing any call site semantics.

The critical constraint is **"all existing tests pass without modification"** (Success Criterion 5). The test suite has 395 tests. Three test files import directly from modules being refactored: `test_pagination.py` imports `_encode_cursor`, `_decode_cursor`, `_paginate_result` from `server`; `test_yq_wrapper.py` imports from `yq_wrapper`; and `verify_features.py` imports `data_query` from `server`. The extraction strategy must maintain backward-compatible import paths via re-exports from the original modules, or the success criterion fails.

Additionally, SAFE-01 (pin `ruamel.yaml>=0.18.0,<0.19`) is assigned to this phase. The current pin is `>=0.18.0` with a comment about 0.19 but no upper bound enforced. ruamel.yaml 0.19.0 replaced `ruamel.yaml.clib` with `ruamel.yaml.clibz` (a zig-compiled variant), which causes build failures in Docker slim images and CI environments without a C/zig toolchain. The installed version is 0.18.17. The fix is a one-line change to `pyproject.toml`.

## Key Findings

### 1. Extraction Boundaries in server.py (HIGH confidence)

Direct analysis of server.py (1880 lines) identifies four extraction targets:

**Pagination (lines 130-215, ~85 lines):**

- Constants: `PAGE_SIZE_CHARS`, `ADVISORY_PAGE_THRESHOLD`, `MAX_PRIMITIVE_DISPLAY_LENGTH`
- Functions: `_encode_cursor`, `_decode_cursor`, `_paginate_result`
- Supporting: `_summarize_structure`, `_summarize_list_structure`, `_summarize_depth_exceeded`, `_summarize_primitive`, `_get_pagination_hint` (lines 218-1200)
- Dependencies: `base64`, `orjson` (standard/existing)
- Test coupling: `test_pagination.py` imports `_encode_cursor`, `_decode_cursor`, `_paginate_result` from `mcp_json_yaml_toml.server`

**Format detection and value parsing (scattered, ~80 lines total):**

- `_detect_file_format` (lines 311-334): file extension to FormatType mapping
- `_parse_content_for_validation` (lines 69-94): format-aware content parsing (orjson/YAML/tomlkit)
- `_parse_set_value` (lines 628-662): typed value parsing for SET operations
- `_parse_typed_json` (lines 601-625): JSON value parsing with type validation
- Dependencies: `orjson`, `tomlkit`, `ruamel.yaml`, `FormatType` from yq_wrapper

**Schema validation (lines 866-924, ~58 lines):**

- `_validate_against_schema`: JSON Schema validation with Draft 7/2020-12 support
- `_validate_and_write_content` (lines 97-118): validate-then-write pipeline
- Dependencies: `jsonschema`, `httpx`, `referencing`
- These could move to a `services/validation.py` but are not explicitly required by ARCH-01 through ARCH-04

**Data operation handlers (lines 337-863, ~526 lines):**

- `_handle_data_get_schema`, `_handle_data_get_structure`, `_handle_data_get_value`
- `_handle_data_set`, `_set_toml_value_handler`, `_optimize_yaml_if_needed`
- `_handle_data_delete`, `_delete_toml_key_handler`, `_delete_yq_key_handler`
- `_dispatch_get_operation`, `_dispatch_set_operation`, `_dispatch_delete_operation`
- These remain in server.py for this phase; they move to services/ in Phase 2

### 2. Extraction Boundaries in yq_wrapper.py (HIGH confidence)

Direct analysis of yq_wrapper.py (934 lines) identifies two components:

**Binary lifecycle management (lines 1-663, ~663 lines):**

- Binary discovery: `get_yq_binary_path`, `_find_system_yq`, `_get_storage_location`
- Version management: `get_yq_version`, `_get_yq_version_string`, `_is_mikefarah_yq`, `_parse_version`, `_version_meets_minimum`
- Download/verify: `_download_yq_binary`, `_download_file`, `_get_checksums`, `_fetch_checksums_from_github`, `_verify_checksum`, `_cleanup_old_versions`
- Platform detection: `_get_platform_binary_info`, `_get_download_headers`
- Constants: `GITHUB_REPO`, `DEFAULT_YQ_VERSION`, `DEFAULT_YQ_CHECKSUMS`, `CHECKSUM_*`
- Validation: `validate_yq_binary`
- This entire block becomes `backends/binary_manager.py`

**Query execution (lines 665-934, ~269 lines):**

- `execute_yq`: main entry point, calls `get_yq_binary_path` then runs subprocess
- `_validate_execute_args`, `_build_yq_command`, `_run_yq_subprocess`, `_parse_json_output`
- `parse_yq_error`: error message formatting
- Data types: `FormatType`, `YQResult`, `YQError`, `YQBinaryNotFoundError`, `YQExecutionError`
- This becomes `backends/yq.py` with the `YqBackend` class implementing `QueryBackend`

**Shared types that must remain importable from yq_wrapper:**

- `FormatType` (imported by config.py, server.py, test_server.py, test_config.py)
- `YQError`, `YQExecutionError` (imported by server.py)
- `execute_yq` (imported by server.py in 14+ call sites)
- `YQResult`, `YQBinaryNotFoundError` (imported by test_yq_wrapper.py)

### 3. QueryBackend Protocol Design (HIGH confidence)

The Protocol pattern from `typing.Protocol` (PEP 544) is the correct abstraction. Python 3.11+ fully supports it, both mypy and basedpyright verify structural subtyping against Protocol classes.

**Protocol design based on current `execute_yq` signature:**

```python
from typing import Protocol
from pathlib import Path

class QueryBackend(Protocol):
    def execute(
        self,
        expression: str,
        input_data: str | None = None,
        input_file: Path | str | None = None,
        input_format: FormatType = FormatType.YAML,
        output_format: FormatType = FormatType.JSON,
        in_place: bool = False,
        null_input: bool = False,
    ) -> YQResult: ...

    def validate(self) -> tuple[bool, str]: ...
```

**Why Protocol over ABC:**

- No import coupling: consumers don't need to inherit from the base
- Structural subtyping: any class matching the signature is valid
- Both mypy (strict mode enabled in this project) and basedpyright (basic mode) support it
- Aligns with this project's existing use of `StrEnum`, `BaseModel`, and modern Python typing

**YqBackend implementation:**

- Wraps current `execute_yq` as `execute()` method
- Holds reference to `BinaryManager` for binary resolution
- `validate()` wraps current `validate_yq_binary()`

### 4. Backward Compatibility Strategy (HIGH confidence)

Success Criterion 5 requires all 395 existing tests pass without modification. The following import paths must continue to work:

| Current Import                                                                                                                                                     | Test File                                | Strategy                                                                                                                        |
| ------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ---------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------- |
| `from mcp_json_yaml_toml.server import _encode_cursor, _decode_cursor, _paginate_result`                                                                           | test_pagination.py                       | Re-export from server.py: `from mcp_json_yaml_toml.services.pagination import _encode_cursor, _decode_cursor, _paginate_result` |
| `from mcp_json_yaml_toml.yq_wrapper import FormatType, YQError, YQExecutionError, execute_yq, YQResult, YQBinaryNotFoundError, validate_yq_binary, parse_yq_error` | test_yq_wrapper.py                       | Re-export from yq_wrapper.py shim module                                                                                        |
| `from mcp_json_yaml_toml.server import mcp`                                                                                                                        | test_fastmcp_integration.py              | `mcp` object stays in server.py                                                                                                 |
| `from mcp_json_yaml_toml.server import data_query`                                                                                                                 | verify_features.py                       | Tool function stays in server.py (moves in Phase 2)                                                                             |
| `from mcp_json_yaml_toml import server` then `server.data(...)`                                                                                                    | test_server.py, test_toml_write.py, etc. | Tool functions stay in server.py                                                                                                |
| `from mcp_json_yaml_toml.config import ...`                                                                                                                        | test_config.py                           | config.py unchanged in Phase 1                                                                                                  |

**Implementation pattern:**

```python
# yq_wrapper.py becomes a shim:
"""Backward-compatible shim. Real implementation in backends/."""
from mcp_json_yaml_toml.backends.yq import (  # noqa: F401
    execute_yq,
    parse_yq_error,
    validate_yq_binary,
)
from mcp_json_yaml_toml.backends.binary_manager import (  # noqa: F401
    get_yq_binary_path,
    get_yq_version,
)
from mcp_json_yaml_toml.backends.base import (  # noqa: F401
    FormatType,
    YQError,
    YQExecutionError,
    YQBinaryNotFoundError,
    YQResult,
)
```

### 5. ruamel.yaml Pin (SAFE-01) (HIGH confidence)

**Current state:** `ruamel.yaml>=0.18.0` with comment "0.19.x has different API" but no upper bound enforced in the dependency spec.

**Risk:** ruamel.yaml 0.19.0 (released 2025-12-31) replaced the `ruamel.yaml.clib` dependency with `ruamel.yaml.clibz`, which requires a zig compiler for building from source. Docker slim images, CI runners without zig, and some deployment targets fail to install 0.19.x. This is a documented issue (see [AWS bedrock-agentcore issue #415](https://github.com/aws/bedrock-agentcore-starter-toolkit/issues/415)).

**Fix:** Change pyproject.toml line 37:

```
"ruamel.yaml>=0.18.0,<0.19",  # 0.19.x requires zig compiler for ruamel.yaml.clibz
```

**Installed version:** 0.18.17 (within range, no change to lock file behavior)

### 6. Target Directory Structure (HIGH confidence)

```
packages/mcp_json_yaml_toml/
  __init__.py                  # unchanged
  server.py                    # reduced (~1400 lines after pagination extraction)
  config.py                    # unchanged
  yq_wrapper.py                # becomes backward-compatible shim (~30 lines)
  toml_utils.py                # unchanged (moves to formats/ in Phase 2)
  yaml_optimizer.py            # unchanged (moves to formats/ in Phase 2)
  schemas.py                   # unchanged
  lmql_constraints.py          # unchanged
  version.py                   # unchanged
  backends/
    __init__.py
    base.py                    # QueryBackend protocol, FormatType, error types, YQResult
    binary_manager.py           # Binary lifecycle (discovery, download, verify, cache)
    yq.py                      # YqBackend class implementing QueryBackend
  services/
    __init__.py
    pagination.py              # Cursor encode/decode, paginate_result, structure summary
  formats/
    __init__.py
    base.py                    # _detect_file_format, _parse_content_for_validation, _parse_set_value
```

### 7. Dependency Graph After Extraction (HIGH confidence)

```
server.py
  imports: backends.yq.YqBackend (or execute_yq via shim)
  imports: services.pagination.*
  imports: formats.base.*
  imports: config, schemas, lmql_constraints, toml_utils, yaml_optimizer

backends/yq.py
  imports: backends.binary_manager.get_yq_binary_path
  imports: backends.base.FormatType, YQResult, YQError, YQExecutionError

backends/binary_manager.py
  imports: (stdlib only: pathlib, platform, subprocess, hashlib, os, shutil, uuid)
  imports: httpx, portalocker (existing deps)

services/pagination.py
  imports: base64, orjson (existing deps)
  imports: (no project imports -- fully independent)

formats/base.py
  imports: backends.base.FormatType
  imports: orjson, tomlkit, ruamel.yaml (existing deps)
```

No circular dependencies. Each new module has a clear downward dependency flow.

### 8. What NOT to Extract in Phase 1 (HIGH confidence)

The following items stay in server.py until Phase 2:

- **Tool decorator functions** (data, data_query, data_schema, data_convert, data_merge, constraint_validate, constraint_list): These are the MCP tool entry points. Phase 2 moves them to `tools/` directory.
- **Data operation handlers** (_handle_data_get\_\_, *handle_data_set, \_handle_data_delete, \_dispatch*_): Business logic moves to `services/data_service.py` in Phase 2.
- **Schema operation handlers** (_handle_schema_\*): Move to `tools/schema.py` in Phase 2.
- **Schema validation functions** (\_validate_against_schema, \_validate_and_write_content): Move to `services/validation.py` in Phase 2.
- **MCP prompts and resources**: Move to dedicated modules in Phase 2.

Extracting these in Phase 1 would increase scope without delivering additional architectural value. The Phase 1 extractions are the _prerequisites_ for Phase 2's tool layer refactoring.

## Pitfalls Specific to This Phase

### Critical: Import Path Breakage

**What goes wrong:** Moving functions to new modules breaks `from mcp_json_yaml_toml.server import _paginate_result` in test_pagination.py and similar imports.
**Prevention:** Every extracted function must be re-exported from its original module. Add a test gate that verifies backward-compatible import paths.
**Detection:** Run `uv run pytest` after each extraction step. Any import error is an immediate signal.

### Critical: Circular Import During Extraction

**What goes wrong:** `backends/yq.py` imports `FormatType` from `backends/base.py`, but if `base.py` also needs something from `yq.py`, Python raises `ImportError`.
**Prevention:** Keep `FormatType`, `YQResult`, and error types in `backends/base.py` (leaf module). `yq.py` imports from `base.py`, never the reverse. `binary_manager.py` has no project imports at all.
**Detection:** Running `python -c "from mcp_json_yaml_toml.backends import yq"` after creating the module.

### Moderate: server.py Still Imports execute_yq Directly

**What goes wrong:** Phase 1 creates `YqBackend` but server.py still calls `execute_yq()` directly in 14+ call sites. If we change these call sites, test_server.py tests that mock `execute_yq` may break.
**Prevention:** In Phase 1, server.py continues to call `execute_yq()` via the shim. The `YqBackend` class exists but is not wired into server.py yet. Phase 2 wires it through the service layer.
**Detection:** All 395 tests must pass. If any test mocking `yq_wrapper.execute_yq` fails, the shim is not properly delegating.

### Moderate: Coverage Threshold Failure

**What goes wrong:** The project requires 60% coverage. Moving code to new modules that aren't exercised by existing tests could drop coverage below threshold.
**Prevention:** The shim modules re-export to original paths, so existing tests still exercise the code. New modules like `backends/binary_manager.py` contain code that was already pragmatically excluded from coverage (`# pragma: no cover` on download/platform functions). No coverage regression expected.
**Detection:** `uv run pytest` includes `--cov` by default. Check coverage report after extraction.

### Minor: Type Checker Strictness

**What goes wrong:** basedpyright (basic mode) and mypy (strict mode) may flag new issues when code moves between modules (e.g., re-exported types losing type information).
**Prevention:** Use explicit `__all__` in shim modules. Ensure re-exports use direct assignment, not star imports. Run `uv run mypy packages/ --show-error-codes && uv run basedpyright packages/` after each extraction.
**Detection:** CI quality gates catch type errors.

## Implications for Planning

### Recommended Task Ordering

1. **SAFE-01 first** -- Pin `ruamel.yaml<0.19` in pyproject.toml. One-line change, independent of everything else, reduces risk immediately.

2. **Create `backends/base.py`** -- Define `FormatType`, error types, `YQResult`, and `QueryBackend` Protocol. This is the foundation module with zero dependencies on existing code. Move types out of yq_wrapper.py, add re-exports to yq_wrapper.py shim.

3. **Create `backends/binary_manager.py`** -- Extract binary lifecycle functions from yq_wrapper.py. These are self-contained (no imports from other project modules except the constants that move to base.py). Update yq_wrapper.py shim.

4. **Create `backends/yq.py`** -- Extract query execution into `YqBackend` class. Keep `execute_yq` as a module-level function (for backward compatibility) that delegates to a default `YqBackend` instance. Update yq_wrapper.py shim.

5. **Create `services/pagination.py`** -- Extract pagination functions from server.py. Update server.py to re-export from new location.

6. **Create `formats/base.py`** -- Extract format detection and value parsing from server.py. Update server.py imports.

7. **Verification gate** -- Run full test suite, type checkers, linters. All 395 tests must pass. All quality gates must pass.

### Task Dependencies

```
SAFE-01 (independent)
  |
backends/base.py (independent of SAFE-01)
  |
  +---> backends/binary_manager.py (needs base.py types)
  |       |
  |       +---> backends/yq.py (needs binary_manager + base.py)
  |
services/pagination.py (independent of backends/)
  |
formats/base.py (needs backends/base.py for FormatType)
  |
Verification gate (needs all above)
```

Tasks 1-2 can run in parallel. Tasks 3-4 are sequential. Task 5 is independent of 3-4 and can run in parallel with them. Task 6 depends on task 2 only. Task 7 runs last.

### Estimated Complexity

| Task                       | Lines Moved | New Lines | Risk   | Notes                                       |
| -------------------------- | ----------- | --------- | ------ | ------------------------------------------- |
| SAFE-01                    | 0           | 1         | LOW    | One-line pyproject.toml change              |
| backends/base.py           | ~80         | ~30       | LOW    | Type definitions, Protocol class            |
| backends/binary_manager.py | ~550        | ~10       | LOW    | Self-contained, mostly `# pragma: no cover` |
| backends/yq.py             | ~270        | ~40       | MEDIUM | Must maintain `execute_yq` backward compat  |
| services/pagination.py     | ~170        | ~10       | LOW    | Self-contained with dedicated test file     |
| formats/base.py            | ~80         | ~10       | LOW    | Pure functions, no state                    |
| yq_wrapper.py shim         | -800        | ~30       | MEDIUM | Must re-export all public symbols           |
| Verification               | 0           | 0         | LOW    | Run existing suite                          |

**Total estimated:** ~1150 lines moved, ~130 lines of new boilerplate (imports, `__init__.py`, Protocol definition, shim). Net reduction in server.py: ~250 lines (pagination + format detection). Net reduction in yq_wrapper.py: ~900 lines (becomes 30-line shim).

## Confidence Assessment

| Area                   | Confidence | Reason                                                            |
| ---------------------- | ---------- | ----------------------------------------------------------------- |
| Extraction boundaries  | HIGH       | Direct code analysis of server.py and yq_wrapper.py               |
| Backward compatibility | HIGH       | All import paths catalogued from test grep analysis               |
| Protocol design        | HIGH       | PEP 544 is stable since Python 3.8, verified by mypy/pyright docs |
| SAFE-01 fix            | HIGH       | ruamel.yaml 0.19 breakage confirmed via PyPI and GitHub issues    |
| Test pass guarantee    | HIGH       | Shim pattern is standard Python; re-exports preserve import paths |
| Phase 2 prerequisites  | HIGH       | Clear dependency chain from extraction targets                    |

## Open Questions

None. This phase is pure extraction refactoring with well-understood patterns. All extraction boundaries are visible in the source code, all test coupling points are catalogued, and the backward compatibility strategy is proven (Python re-export shims are standard practice).

## Sources

### Primary (HIGH confidence -- direct code analysis)

- `packages/mcp_json_yaml_toml/server.py` (1880 lines) -- extraction target analysis
- `packages/mcp_json_yaml_toml/yq_wrapper.py` (934 lines) -- extraction target analysis
- `packages/mcp_json_yaml_toml/tests/test_pagination.py` -- import coupling analysis
- `packages/mcp_json_yaml_toml/tests/test_yq_wrapper.py` -- import coupling analysis
- `packages/mcp_json_yaml_toml/tests/conftest.py` -- test infrastructure analysis
- `pyproject.toml` -- dependency and tooling configuration
- `.planning/ROADMAP.md` -- phase requirements and success criteria
- `.planning/REQUIREMENTS.md` -- requirement definitions

### Secondary (HIGH confidence -- official documentation)

- [PEP 544: Protocols](https://peps.python.org/pep-0544/) -- structural subtyping specification
- [mypy Protocol documentation](https://mypy.readthedocs.io/en/stable/protocols.html) -- type checker support verification
- [typing.python.org Protocol reference](https://typing.python.org/en/latest/reference/protocols.html) -- best practices
- [ruamel.yaml PyPI](https://pypi.org/project/ruamel.yaml/) -- version 0.19.0 changelog
- [AWS bedrock-agentcore issue #415](https://github.com/aws/bedrock-agentcore-starter-toolkit/issues/415) -- ruamel.yaml 0.19 build failure documentation

---

_Research completed: 2026-02-14_
_Ready for planning: yes_

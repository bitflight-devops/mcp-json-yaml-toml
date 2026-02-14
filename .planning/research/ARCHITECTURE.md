# Architecture Research

**Domain:** MCP server for structured data manipulation (JSON/YAML/TOML)
**Researched:** 2026-02-14
**Confidence:** HIGH (current codebase analysis) / MEDIUM (FastMCP 3.x migration specifics)

## Current Architecture (As-Is)

### System Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                       MCP Transport Layer                           │
│                   (FastMCP 2.x runtime, stdio)                      │
├─────────────────────────────────────────────────────────────────────┤
│                        server.py (1880 lines)                       │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌──────────────────┐ │
│  │  7 @tools  │ │ 2 @resource│ │ 3 @prompt  │ │  ~30 _handle_*   │ │
│  │ decorators │ │ decorators │ │ decorators │ │  helper funcs    │ │
│  └─────┬──────┘ └─────┬──────┘ └─────┬──────┘ └───────┬──────────┘ │
│        │              │              │                 │            │
│        └──────────────┴──────────────┴─────────────────┘            │
│                              │                                      │
├──────────────────────────────┼──────────────────────────────────────┤
│                     Domain Services Layer                           │
│  ┌──────────────┐ ┌──────────────┐ ┌────────────────────────────┐  │
│  │ schemas.py   │ │lmql_const.py │ │      config.py             │  │
│  │ (1195 lines) │ │ (846 lines)  │ │      (129 lines)           │  │
│  │ SchemaManager│ │ConstraintReg │ │ format enable/disable      │  │
│  └──────────────┘ └──────────────┘ └────────────────────────────┘  │
│                                                                     │
├─────────────────────────────────────────────────────────────────────┤
│                     Execution Backend Layer                          │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │               yq_wrapper.py (934 lines)                       │  │
│  │  ┌─────────────────┐  ┌─────────────────┐  ┌──────────────┐  │  │
│  │  │ Binary Mgmt     │  │ Query Execution │  │ Error Parse  │  │  │
│  │  │ (~560 lines)    │  │ (~230 lines)    │  │ (~40 lines)  │  │  │
│  │  │ download/verify │  │ build cmd, run  │  │ AI-friendly  │  │  │
│  │  │ locate/validate │  │ subprocess call │  │ messages     │  │  │
│  │  └─────────────────┘  └─────────────────┘  └──────────────┘  │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                                                                     │
│  ┌──────────────┐  ┌──────────────────┐                            │
│  │ toml_utils.py│  │ yaml_optimizer.py│                            │
│  │ (87 lines)   │  │ (372 lines)      │                            │
│  │ tomlkit r/w  │  │ anchor/alias opt │                            │
│  └──────────────┘  └──────────────────┘                            │
│                                                                     │
├─────────────────────────────────────────────────────────────────────┤
│                     External Binaries / Libraries                    │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐           │
│  │ yq binary│  │ tomlkit  │  │ruamel.yml│  │ orjson   │           │
│  │(mikefarah│  │ (TOML    │  │ (YAML    │  │ (JSON    │           │
│  │  /yq)    │  │  write)  │  │  fidelity│  │  fast)   │           │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘           │
└─────────────────────────────────────────────────────────────────────┘
```

### Current Component Responsibilities

| Component             | Responsibility                                                                                                                                  | Lines | Communicates With                                                         |
| --------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------- | ----- | ------------------------------------------------------------------------- |
| `server.py`           | Tool/resource/prompt registration, request dispatch, pagination, response formatting, format detection, schema validation orchestration         | 1880  | yq_wrapper, schemas, lmql_constraints, config, toml_utils, yaml_optimizer |
| `yq_wrapper.py`       | Binary resolution (env/cache/system/download), platform detection, checksum verification, subprocess execution, command building, error parsing | 934   | yq binary (subprocess), GitHub API (httpx)                                |
| `schemas.py`          | Schema Store catalog fetching, IDE extension schema discovery, file-to-schema matching, schema caching                                          | 1195  | httpx (Schema Store), filesystem (IDE extensions)                         |
| `lmql_constraints.py` | Regex-based input validation, constraint registry, partial validation support                                                                   | 846   | lmql.ops.regex                                                            |
| `config.py`           | Environment variable parsing for enabled formats                                                                                                | 129   | yq_wrapper (FormatType enum)                                              |
| `toml_utils.py`       | TOML-specific set/delete using tomlkit (yq can't write TOML)                                                                                    | 87    | tomlkit                                                                   |
| `yaml_optimizer.py`   | YAML anchor/alias deduplication                                                                                                                 | 372   | ruamel.yaml, orjson                                                       |

### Current Data Flow

```
MCP Client Request
    │
    ▼
FastMCP runtime deserializes → @mcp.tool decorator
    │
    ▼
Tool function (server.py)
    ├── _detect_file_format(path) → FormatType
    ├── is_format_enabled(format) → bool
    ├── schema_manager.get_schema_info_for_file(path) → SchemaInfo?
    │
    ├── [GET operations]
    │   ├── execute_yq(expression, input_file, input_format, output_format)
    │   │       └── get_yq_binary_path() → resolves binary → subprocess.run()
    │   ├── _paginate_result(result_str, cursor)
    │   └── return dict response
    │
    ├── [SET operations]
    │   ├── TOML → _set_toml_value_handler() → toml_utils.set_toml_value()
    │   ├── YAML/JSON → execute_yq(..., in_place=True)
    │   │   └── _optimize_yaml_if_needed(path) → yaml_optimizer
    │   └── _validate_and_write_content(path, content, schema)
    │
    └── [DELETE operations]
        ├── TOML → _delete_toml_key_handler() → toml_utils.delete_toml_key()
        └── YAML/JSON → execute_yq(..., in_place=True)
```

## Identified Architectural Problems

### Problem 1: server.py Is a God Module

**Observed:** 1880 lines mixing tool registration, business logic, pagination, format detection, value parsing, schema validation orchestration, and response formatting. Thirty-plus internal helper functions.

**Impact:** Adding a new tool requires understanding the entire file. Testing business logic requires FastMCP context. The file has seven distinct responsibilities (tool registration, dispatch, pagination, format handling, value parsing, schema orchestration, response building).

### Problem 2: yq_wrapper.py Mixes Two Unrelated Concerns

**Observed:** Binary lifecycle management (~560 lines: download, verify, locate, version check, platform detection, cleanup) is entangled with query execution (~230 lines: build command, run subprocess, parse output). These change for completely different reasons.

**Impact:** Changing binary management (e.g., adding a new download source) forces re-testing query execution. Swapping execution backends (dasel, native) requires navigating binary management code.

### Problem 3: Format-Specific Logic Scattered Across Modules

**Observed:** TOML write operations bypass yq entirely (`toml_utils.py`). YAML post-processing lives in `yaml_optimizer.py`. JSON parsing uses `orjson` directly in server.py. Format detection is in server.py but FormatType is in yq_wrapper.py.

**Impact:** No clear boundary for "how does format X work." Adding a new format requires changes in 4+ files with no guiding interface.

### Problem 4: Direct Coupling to yq Binary

**Observed:** `execute_yq()` is called 14 times directly from server.py. The function name, parameters, and error types (`YQError`, `YQExecutionError`) leak yq-specific concepts into the business logic layer.

**Impact:** Cannot swap execution backends without changing every call site in server.py.

## Recommended Architecture (To-Be)

### Target System Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                       MCP Transport Layer                           │
│               (FastMCP 3.x runtime, StreamableHTTP)                 │
├─────────────────────────────────────────────────────────────────────┤
│                       Tool Registration Layer                       │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ │
│  │tools/    │ │tools/    │ │tools/    │ │tools/    │ │tools/    │ │
│  │data.py   │ │query.py  │ │schema.py │ │convert.py│ │constrain │ │
│  │(get/set/ │ │(yq expr) │ │(validate │ │(format   │ │_tools.py │ │
│  │ delete)  │ │          │ │ scan etc)│ │ convert) │ │          │ │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘ │
│       └─────────────┴────────────┴─────────────┴────────────┘       │
│                              │                                      │
├──────────────────────────────┼──────────────────────────────────────┤
│                      Service Layer (new)                             │
│  ┌────────────────────┐  ┌───────────┐  ┌───────────────────────┐  │
│  │  data_service.py   │  │ pagination│  │  response_builder.py  │  │
│  │  (format routing,  │  │ .py       │  │  (consistent response │  │
│  │   validation, r/w) │  │           │  │   formatting)         │  │
│  └─────────┬──────────┘  └───────────┘  └───────────────────────┘  │
│            │                                                        │
├────────────┼────────────────────────────────────────────────────────┤
│            │      Backend Abstraction Layer (new)                    │
│  ┌─────────┴──────────────────────────────────────────────────┐    │
│  │              QueryBackend (Protocol / ABC)                  │    │
│  │  query(expr, input, in_fmt, out_fmt) → QueryResult          │    │
│  │  supports_format(fmt) → bool                                │    │
│  │  validate_expression(expr) → bool                           │    │
│  └─────────┬───────────────────┬───────────────────┬──────────┘    │
│            │                   │                   │               │
│  ┌─────────┴────┐  ┌──────────┴────┐  ┌──────────┴─────────┐     │
│  │ YqBackend    │  │ DaselBackend  │  │ NativeBackend      │     │
│  │ (default)    │  │ (future)      │  │ (future, no binary)│     │
│  └─────────┬────┘  └───────────────┘  └────────────────────┘     │
│            │                                                       │
├────────────┼───────────────────────────────────────────────────────┤
│            │       Binary Management Layer (extracted)              │
│  ┌─────────┴──────────────────────────────────────────────────┐   │
│  │            BinaryManager (Protocol / ABC)                   │   │
│  │  get_binary_path() → Path                                   │   │
│  │  validate_binary() → (bool, str)                            │   │
│  └─────────┬────────────────────┬─────────────────────────┐   │   │
│  ┌─────────┴────┐  ┌───────────┴────┐  ┌─────────────────┘   │   │
│  │ YqBinaryMgr  │  │ DaselBinaryMgr│  │ (future impls)      │   │
│  │ download,    │  │               │  │                      │   │
│  │ verify, cache│  │               │  │                      │   │
│  └──────────────┘  └───────────────┘  └──────────────────────┘   │
│                                                                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐             │
│  │ schemas.py   │  │constraints.py│  │ config.py    │             │
│  │ (unchanged)  │  │ (unchanged)  │  │ (unchanged)  │             │
│  └──────────────┘  └──────────────┘  └──────────────┘             │
│                                                                     │
├─────────────────────────────────────────────────────────────────────┤
│                    Format Handlers Layer (new)                       │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐             │
│  │FormatHandler │  │FormatHandler │  │FormatHandler │             │
│  │  (JSON)      │  │  (YAML)      │  │  (TOML)      │             │
│  │ parse, write │  │ parse, write │  │ parse, write │             │
│  │ orjson       │  │ ruamel+optim │  │ tomlkit      │             │
│  └──────────────┘  └──────────────┘  └──────────────┘             │
└─────────────────────────────────────────────────────────────────────┘
```

### Component Boundaries

| Component                      | Responsibility                                                                    | Communicates With                          |
| ------------------------------ | --------------------------------------------------------------------------------- | ------------------------------------------ |
| `tools/*.py` (5 files)         | Thin tool registration, parameter validation, delegate to services                | data_service, pagination, response_builder |
| `services/data_service.py`     | Format routing, schema validation orchestration, read/write coordination          | QueryBackend, FormatHandler, SchemaManager |
| `services/pagination.py`       | Cursor encode/decode, page extraction, advisory hints                             | None (pure utility)                        |
| `services/response_builder.py` | Consistent response dict construction                                             | None (pure utility)                        |
| `backends/base.py`             | `QueryBackend` protocol definition, `QueryResult` model, `BackendError` hierarchy | None (interface only)                      |
| `backends/yq.py`               | yq-specific command building, subprocess execution, error parsing                 | BinaryManager                              |
| `backends/binary_manager.py`   | Binary resolution, download, verification, caching                                | GitHub API, filesystem                     |
| `formats/base.py`              | `FormatHandler` protocol: parse, serialize, detect                                | None (interface only)                      |
| `formats/json_handler.py`      | JSON parse/serialize via orjson                                                   | orjson                                     |
| `formats/yaml_handler.py`      | YAML parse/serialize via ruamel.yaml, anchor optimization                         | ruamel.yaml, yaml_optimizer                |
| `formats/toml_handler.py`      | TOML parse/serialize via tomlkit                                                  | tomlkit                                    |
| `schemas.py`                   | Schema discovery, caching, validation (unchanged)                                 | httpx, filesystem                          |
| `constraints.py`               | LMQL constraint validation (unchanged)                                            | lmql                                       |
| `config.py`                    | Environment-based format configuration (unchanged)                                | None                                       |

### Recommended Project Structure

```
packages/mcp_json_yaml_toml/
├── __init__.py
├── config.py                    # Environment config (unchanged)
├── version.py                   # Version (unchanged)
├── server.py                    # Entry point: FastMCP init + tool imports (< 50 lines)
│
├── tools/                       # Tool registration layer (thin)
│   ├── __init__.py
│   ├── data.py                  # data() tool: get/set/delete
│   ├── query.py                 # data_query() tool
│   ├── schema.py                # data_schema() tool
│   ├── convert.py               # data_convert(), data_merge() tools
│   └── constraints.py           # constraint_validate(), constraint_list() tools
│                                  + resources and prompts
│
├── services/                    # Business logic layer
│   ├── __init__.py
│   ├── data_service.py          # Format routing, validation orchestration
│   ├── pagination.py            # Cursor-based pagination
│   └── response_builder.py      # Response dict construction
│
├── backends/                    # Execution backend abstraction
│   ├── __init__.py
│   ├── base.py                  # QueryBackend protocol, QueryResult, BackendError
│   ├── yq.py                   # YqBackend implementation
│   └── binary_manager.py       # Binary lifecycle (download, verify, cache)
│
├── formats/                     # Format-specific handlers
│   ├── __init__.py
│   ├── base.py                  # FormatHandler protocol, FormatType enum
│   ├── json_handler.py          # JSON via orjson
│   ├── yaml_handler.py          # YAML via ruamel.yaml + optimizer
│   └── toml_handler.py          # TOML via tomlkit
│
├── schemas.py                   # Schema management (unchanged initially)
├── lmql_constraints.py          # Constraint validation (unchanged initially)
├── yaml_optimizer.py            # Anchor optimization (moved into formats/ later)
│
└── tests/                       # Tests (existing structure)
    └── ...
```

### Structure Rationale

- **tools/**: Each file contains one or two `@mcp.tool` decorators with minimal logic. Thin wrappers that validate input and delegate. Keeps the MCP registration surface small and testable without FastMCP runtime.
- **services/**: Business logic with no dependency on FastMCP. Functions can be unit-tested with plain Python. This is where pagination, format detection, and response construction live.
- **backends/**: The abstraction boundary that enables swapping yq for dasel or a native implementation. Each backend implements the same `QueryBackend` protocol.
- **formats/**: Encapsulates format-specific parsing and serialization. Eliminates the scattered pattern where TOML bypasses yq while YAML uses yq then post-processes with ruamel.yaml.

## Architectural Patterns

### Pattern 1: Backend Protocol (Strategy Pattern)

**What:** Define a `QueryBackend` protocol that all execution engines implement. The service layer programs against the protocol, not the concrete backend.

**When to use:** When the execution engine may change (yq to dasel) or when multiple backends coexist (yq for query, native for write).

**Trade-offs:** Adds an interface layer (+1 file, +1 import hop). Worth it because it decouples 14 direct `execute_yq()` calls from the business logic.

**Example:**

```python
from typing import Protocol, runtime_checkable
from pathlib import Path
from dataclasses import dataclass

@dataclass
class QueryResult:
    """Backend-agnostic query result."""
    stdout: str
    data: Any = None
    stderr: str = ""

class BackendError(Exception):
    """Base error for backend execution failures."""
    def __init__(self, message: str, stderr: str = "", returncode: int = -1) -> None:
        super().__init__(message)
        self.stderr = stderr
        self.returncode = returncode

@runtime_checkable
class QueryBackend(Protocol):
    """Protocol for data query/manipulation backends."""

    def query(
        self,
        expression: str,
        input_file: Path | None = None,
        input_data: str | None = None,
        input_format: str = "yaml",
        output_format: str = "json",
        in_place: bool = False,
    ) -> QueryResult: ...

    def supports_format(self, fmt: str) -> bool: ...
```

### Pattern 2: Format Handler Registry

**What:** Each format (JSON, YAML, TOML) has a handler that owns parsing and serialization. A registry maps FormatType to handler.

**When to use:** When format-specific logic is scattered (TOML write uses tomlkit, YAML write goes through yq then ruamel.yaml post-processing, JSON uses orjson directly).

**Trade-offs:** Slight overhead for simple operations. Eliminates the `if format == "toml": use_tomlkit() elif format == "yaml": use_yq_then_ruamel()` branching scattered through server.py.

**Example:**

```python
from typing import Protocol, Any
from pathlib import Path

class FormatHandler(Protocol):
    """Protocol for format-specific parse/serialize operations."""

    def parse(self, content: str) -> Any: ...
    def serialize(self, data: Any) -> str: ...
    def detect(self, path: Path) -> bool: ...

class TomlHandler:
    """TOML format handler using tomlkit for comment-preserving operations."""

    def parse(self, content: str) -> Any:
        return tomlkit.parse(content)

    def serialize(self, data: Any) -> str:
        return tomlkit.dumps(data)

    def detect(self, path: Path) -> bool:
        return path.suffix.lower() == ".toml"
```

### Pattern 3: Thin Tool Registration

**What:** Tool functions contain only parameter validation and delegation. Business logic lives in services.

**When to use:** Always. This is the primary mechanism for reducing server.py from 1880 lines to under 50.

**Trade-offs:** More files to navigate. Mitigated by clear naming and the project structure.

**Example:**

```python
# tools/query.py
from fastmcp import FastMCP
from pydantic import Field
from typing import Annotated, Any

def register_query_tools(mcp: FastMCP) -> None:
    """Register query-related MCP tools."""

    @mcp.tool(annotations={"readOnlyHint": True})
    def data_query(
        file_path: Annotated[str, Field(description="Path to file")],
        expression: Annotated[str, Field(description="yq expression")],
        output_format: Annotated[str | None, Field(description="Output format")] = None,
        cursor: Annotated[str | None, Field(description="Pagination cursor")] = None,
    ) -> dict[str, Any]:
        """Extract data using expressions."""
        return data_service.query(file_path, expression, output_format, cursor)
```

## Data Flow (Target Architecture)

### Read (Query) Flow

```
MCP Client
    │
    ▼
FastMCP 3.x runtime
    │
    ▼
tools/query.py::data_query()          ← param validation only
    │
    ▼
services/data_service.py::query()      ← format detection, enabled check
    ├── config.is_format_enabled()
    ├── formats/base.py::detect_format(path) → FormatType
    │
    ▼
backends/yq.py::YqBackend.query()      ← backend-specific execution
    ├── binary_manager.get_binary_path()
    ├── _build_command()
    ├── _run_subprocess()
    └── return QueryResult
    │
    ▼
services/pagination.py::paginate()     ← cursor handling
    │
    ▼
services/response_builder.py::build()  ← consistent dict
    │
    ▼
Return to MCP Client
```

### Write (Set) Flow

```
MCP Client
    │
    ▼
tools/data.py::data(operation="set")   ← param validation
    │
    ▼
services/data_service.py::set_value()  ← format routing
    │
    ├── [TOML path]
    │   ├── formats/toml_handler.py::parse() → data
    │   ├── modify data in-memory
    │   ├── formats/toml_handler.py::serialize() → content
    │   └── schema validation → write file
    │
    ├── [YAML/JSON path]
    │   ├── backends/yq.py::YqBackend.query(..., in_place=True)
    │   ├── [YAML only] formats/yaml_handler.py::optimize()
    │   └── schema validation (post-write reparse)
    │
    ▼
Return to MCP Client
```

### Key Data Flows

1. **Query flow:** Client request -> tool (thin) -> data_service (routing) -> backend (execution) -> pagination -> response builder -> client. Data crosses 4 boundaries, each with a single responsibility.

2. **Write flow:** Client request -> tool -> data_service -> format handler OR backend -> schema validation -> filesystem write -> client. The fork at format handler vs. backend is the key design decision: TOML always uses the native handler (yq cannot write TOML), while YAML/JSON use the backend with optional post-processing.

3. **Schema flow:** Unchanged from current. SchemaManager resolves schemas via catalog + IDE extensions + file associations.

4. **Constraint flow:** Unchanged from current. ConstraintRegistry validates inputs via LMQL regex.

## FastMCP 3.x Migration Analysis

**Source:** [FastMCP upgrade guide](https://github.com/jlowin/fastmcp/blob/main/docs/development/upgrade-guide.mdx), [Context7 v3.0.0rc2 docs](/jlowin/fastmcp/v3.0.0rc2)
**Confidence:** HIGH (official upgrade guide verified)

### Changes Required for This Codebase

| Breaking Change                                                                                | Impact on This Project                                                                                                  | Action Required                         |
| ---------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------- | --------------------------------------- |
| Import path change (`from mcp.server.fastmcp import FastMCP` -> `from fastmcp import FastMCP`) | **None.** Already using `from fastmcp import FastMCP`.                                                                  | No change needed                        |
| `mask_error_details` constructor kwarg removed                                                 | **Yes.** `FastMCP("mcp-json-yaml-toml", mask_error_details=False)` will fail.                                           | Remove kwarg or find replacement        |
| `@mcp.tool(annotations={"readOnlyHint": True})` syntax                                         | **Verify.** The v3 docs show `annotations=ToolAnnotations(readOnlyHint=True)` in MCPMixin but dict form may still work. | Test; may need `ToolAnnotations` import |
| Decorators return functions instead of component objects                                       | **None.** No code treats decorated functions as component objects.                                                      | No change needed                        |
| `enable()`/`disable()` moved to server                                                         | **None.** Not used in current codebase.                                                                                 | No change needed                        |
| Metadata namespace `_fastmcp` -> `fastmcp`                                                     | **None.** Not accessing FastMCP metadata.                                                                               | No change needed                        |
| `ToolError` import path                                                                        | **Verify.** Currently `from fastmcp.exceptions import ToolError`.                                                       | Verify path unchanged in v3             |
| Resource return types (lists must be JSON string or ResourceResult)                            | **Potential.** `list_all_constraints()` returns a dict (fine). `get_constraint_definition()` returns a dict (fine).     | Likely no change                        |

### Migration Risk Assessment

The migration from FastMCP 2.x to 3.x is **low risk** for this codebase. The project uses a narrow surface of the FastMCP API:

- `FastMCP()` constructor (1 call site)
- `@mcp.tool()` decorator (7 call sites)
- `@mcp.resource()` decorator (2 call sites)
- `@mcp.prompt()` decorator (3 call sites)
- `ToolError` exception (60+ usage sites, but import path is the only concern)
- `mcp.run()` (1 call site)

The primary risk is the `mask_error_details=False` constructor parameter removal. The dependency pin `fastmcp>=2.14.4,<3` in `pyproject.toml` explicitly blocks v3 upgrades until ready.

### Recommended Migration Strategy

1. **Decouple first, migrate second.** The architecture restructuring (splitting server.py, extracting backends) should happen on FastMCP 2.x. This reduces the migration surface -- instead of changing 1880 lines in one file, each thin tool file has a small, testable FastMCP surface.
2. **Test with rc2.** Pin `fastmcp>=3.0.0rc2,<4` in a separate branch, run the test suite, identify failures.
3. **Address `mask_error_details`.** Check if there's a replacement config or if the default behavior in v3 matches the desired behavior (exposing error details to clients).
4. **Update `pyproject.toml` pin.** Change `fastmcp>=2.14.4,<3` to `fastmcp>=3.0.0,<4` once stable.

## Pluggable Backend Analysis

### yq vs. dasel Comparison

**Sources:** [dasel docs](https://daseldocs.tomwright.me/), [yq GitHub](https://github.com/mikefarah/yq), Context7 research
**Confidence:** MEDIUM (documentation-based, not tested in this codebase)

| Criterion            | yq (current)                                              | dasel (candidate)                  |
| -------------------- | --------------------------------------------------------- | ---------------------------------- |
| Query syntax         | jq-like (`.users[0].name`)                                | Dot notation (`users.[0].name`)    |
| TOML write           | Cannot write TOML (read only)                             | Full TOML read/write               |
| Format coverage      | YAML, JSON, TOML, XML, CSV, TSV, props                    | JSON, YAML, TOML, XML, CSV, HCL    |
| Binary size          | ~14 MB                                                    | ~8 MB                              |
| Expression power     | Full jq expression language (pipes, filters, map, select) | Query + filter + map, more limited |
| Community            | ~12k GitHub stars                                         | ~5k GitHub stars                   |
| Comment preservation | No (yq strips comments)                                   | No                                 |

### Backend Abstraction Trade-offs

**Pro: Unified TOML handling.** The most compelling reason to support dasel is TOML write. Currently, TOML set/delete bypasses yq entirely via `toml_utils.py`, creating a split code path. dasel's native TOML write would unify this.

**Con: Expression language gap.** yq's jq-like expressions are significantly more powerful than dasel's query syntax. The `data_query` tool exposes raw yq expressions to clients. Switching backends would break client-side expressions.

**Recommendation:** Implement the backend abstraction layer but keep yq as the default and only backend. The abstraction's value is in separating binary management from execution, not in actually running dasel today. dasel becomes an option when specific use cases demand it (e.g., environments where yq isn't available).

### Native Backend Possibility

A "NativeBackend" using only Python libraries (orjson, ruamel.yaml, tomlkit) for basic get/set/delete operations is viable for simple paths but cannot replicate yq's expression language. It could serve as a fallback for environments where external binaries are prohibited.

## Anti-Patterns

### Anti-Pattern 1: God Module

**What people do:** Put all tool definitions, business logic, and utility functions in one file.
**Why it's wrong:** 1880 lines with 7 distinct responsibilities. Every change risks unrelated breakage. Testing requires loading the entire module.
**Do this instead:** Split into tools/ (registration), services/ (logic), backends/ (execution). Each file under 300 lines with a single responsibility.

### Anti-Pattern 2: Leaky Backend Abstraction

**What people do:** Use `execute_yq()` directly from tool functions, binding business logic to a specific binary.
**Why it's wrong:** 14 direct call sites means 14 places to change when swapping backends. Error types (`YQError`, `YQExecutionError`) leak into service layer.
**Do this instead:** Service layer calls `backend.query()`. Backend-specific errors are caught and re-raised as `BackendError`. Tool layer never imports from backends/.

### Anti-Pattern 3: Binary Management in Execution Module

**What people do:** Combine binary download/verification/caching with query execution in one module.
**Why it's wrong:** Binary management changes independently of execution logic (new download source, new platform, version bump vs. new query feature). ~560 lines of binary management obfuscate the ~230 lines of actual execution logic.
**Do this instead:** Extract `BinaryManager` class. `YqBackend` depends on `BinaryManager` via constructor injection.

## Scaling Considerations

| Concern             | Current Scale                  | 10x Scale                                         | 100x Scale                                             |
| ------------------- | ------------------------------ | ------------------------------------------------- | ------------------------------------------------------ |
| Subprocess overhead | Acceptable for single-user MCP | Each tool call spawns a process; could bottleneck | Consider connection pooling or long-running yq process |
| Binary management   | One-time download per version  | Works fine                                        | Works fine                                             |
| Schema catalog      | Fetched on first use, cached   | Memory usage grows with catalog size              | Add LRU eviction or lazy loading                       |
| Pagination          | 10KB pages, cursor-based       | Works fine                                        | Works fine                                             |

### Scaling Priorities

1. **First bottleneck:** Subprocess spawn latency. Each `execute_yq()` call spawns a new process. For high-frequency tool calls, this becomes the dominant cost. Mitigation: batch operations or persistent process.
2. **Second bottleneck:** Schema catalog memory. The full Schema Store catalog is loaded into memory. Mitigation: lazy loading with LRU cache.

## Build Order (Implementation Dependencies)

The restructuring should proceed in this order, with each phase independently shippable:

### Phase 1: Extract Utilities (no behavior change)

Extract from server.py into independent modules:

1. `services/pagination.py` — cursor encode/decode, page extraction (lines 130-215 of server.py)
2. `services/response_builder.py` — response dict construction
3. Move `FormatType` enum and `_detect_file_format()` to `formats/base.py`

**Dependency:** None. These are leaf extractions.
**Risk:** Low. Pure refactor with existing tests as safety net.

### Phase 2: Backend Abstraction (decouple execution)

1. Define `QueryBackend` protocol in `backends/base.py`
2. Extract `binary_manager.py` from yq_wrapper.py (lines 100-663)
3. Create `backends/yq.py` implementing `QueryBackend` using extracted execution logic (lines 700-898 of yq_wrapper.py)
4. Keep `yq_wrapper.py` as a backward-compatible shim that delegates to `backends/yq.py`

**Dependency:** Phase 1 (FormatType in formats/base.py).
**Risk:** Medium. Changes the execution path. Requires careful testing of the shim layer.

### Phase 3: Format Handlers (unify format-specific logic)

1. Define `FormatHandler` protocol in `formats/base.py`
2. Create `formats/json_handler.py`, `formats/yaml_handler.py`, `formats/toml_handler.py`
3. Absorb `toml_utils.py` into `formats/toml_handler.py`
4. Absorb YAML optimization into `formats/yaml_handler.py`

**Dependency:** Phase 1 (FormatType enum location).
**Risk:** Medium. TOML handler must preserve tomlkit's comment-preserving behavior. YAML handler must preserve anchor optimization.

### Phase 4: Service Layer (extract business logic)

1. Create `services/data_service.py` with query, set_value, delete_value, convert, merge functions
2. Wire data_service to use `QueryBackend` and `FormatHandler`

**Dependency:** Phases 2 and 3.
**Risk:** Medium. This is where the 14 `execute_yq()` call sites get replaced.

### Phase 5: Split Tool Registration (reduce server.py)

1. Create `tools/data.py`, `tools/query.py`, `tools/schema.py`, `tools/convert.py`, `tools/constraints.py`
2. Each file contains thin `@mcp.tool` functions that delegate to services
3. `server.py` becomes ~50 lines: FastMCP init + imports of tool registration functions

**Dependency:** Phase 4.
**Risk:** Low. Thin wrappers with clear delegation.

### Phase 6: FastMCP 3.x Migration

1. Update `pyproject.toml` pin
2. Address `mask_error_details` removal
3. Verify `ToolAnnotations` vs dict syntax
4. Test full suite

**Dependency:** Phase 5 (smaller files = smaller migration surface per file).
**Risk:** Low. Migration guide confirms minimal breaking changes for this usage pattern.

## Sources

- FastMCP upgrade guide: [https://github.com/jlowin/fastmcp/blob/main/docs/development/upgrade-guide.mdx](https://github.com/jlowin/fastmcp/blob/main/docs/development/upgrade-guide.mdx) — HIGH confidence (official docs)
- FastMCP v3.0.0rc2 documentation via Context7 (`/jlowin/fastmcp/v3.0.0rc2`) — HIGH confidence (version-pinned source)
- FastMCP 3.0 announcement: [https://www.jlowin.dev/blog/fastmcp-3](https://www.jlowin.dev/blog/fastmcp-3) — HIGH confidence (author's blog)
- Dasel documentation via Context7 (`/websites/daseldocs_tomwright_me`) — MEDIUM confidence (official docs, not tested in this codebase)
- Dasel GitHub: [https://github.com/TomWright/dasel](https://github.com/TomWright/dasel) — MEDIUM confidence
- yq GitHub: [https://github.com/mikefarah/yq](https://github.com/mikefarah/yq) — HIGH confidence (currently in use)
- Current codebase analysis: direct file reading of all source modules — HIGH confidence (primary evidence)

---

_Architecture research for: MCP server structured data manipulation (JSON/YAML/TOML)_
_Researched: 2026-02-14_

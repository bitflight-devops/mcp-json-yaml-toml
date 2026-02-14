# Codebase Structure

**Analysis Date:** 2026-02-14

## Directory Layout

```
mcp-json-yaml-toml/
├── packages/mcp_json_yaml_toml/      # Main package (installed as module)
│   ├── __init__.py                    # Package initialization, exports __version__
│   ├── py.typed                       # PEP 561 marker for type hints
│   ├── server.py                      # FastMCP server + all tool implementations
│   ├── yq_wrapper.py                  # yq binary execution + format handling
│   ├── config.py                      # Format configuration + validation
│   ├── schemas.py                     # Schema discovery and management
│   ├── lmql_constraints.py            # Input validation constraints
│   ├── toml_utils.py                  # TOML write operations (yq can't write TOML)
│   ├── yaml_optimizer.py              # YAML anchor optimization
│   ├── version.py                     # Version metadata
│   ├── default_schema_stores.json     # Default Schema Store configuration
│   ├── binaries/                      # Platform-specific yq binaries (auto-downloaded)
│   │   └── yq-linux-amd64-v4.52.2    # Example: Linux x64 binary (cached)
│   └── tests/                         # Test suite (100% co-located with source)
│       ├── conftest.py                # pytest fixtures and shared test setup
│       ├── __init__.py                # Test package marker
│       ├── mcp_protocol_client.py     # MCP protocol test client
│       ├── test_*.py                  # Individual test modules (20 test files)
│       └── verify_features.py         # Feature verification script
├── pyproject.toml                     # Project metadata + all tool configurations
├── uv.lock                            # Locked dependencies (uv package manager)
├── README.md                          # Project documentation
├── AGENTS.md                          # AI agent development guidelines (also linked as CLAUDE.md)
├── PRIVACY.md                         # Privacy/data handling policy
├── LICENSE                            # MIT license
└── .planning/codebase/                # GSD-generated codebase documentation (this directory)
    ├── ARCHITECTURE.md                # Architecture patterns and data flow
    ├── STRUCTURE.md                   # This file
    ├── CONVENTIONS.md                 # Coding conventions (generated separately)
    ├── TESTING.md                     # Testing patterns (generated separately)
    ├── STACK.md                       # Technology stack (generated separately)
    ├── INTEGRATIONS.md                # External integrations (generated separately)
    └── CONCERNS.md                    # Technical debt (generated separately)
```

## Directory Purposes

**packages/mcp_json_yaml_toml/:**

- Purpose: Main installable package namespace
- Contains: All source code, tests, binaries, type hints
- Key files: `server.py` is the monolithic entry point (1880 lines)

**packages/mcp_json_yaml_toml/tests/:**

- Purpose: Co-located test suite matching pytest conventions
- Contains: 20+ test files following `test_*.py` pattern
- Coverage: ~79% (minimum 60% enforced)
- Execution: Parallel via pytest-xdist (`-n auto`)
- Entry point for verification: `verify_features.py`

**packages/mcp_json_yaml_toml/binaries/:**

- Purpose: Cache directory for platform-specific yq binaries
- Auto-populated: First execution downloads binary if missing
- Versioned: `yq-{os}-{arch}-v{version}` naming scheme
- Integrity: SHA256 checksums verified after download
- Scope: One binary per platform/architecture combination

## Key File Locations

**Entry Points:**

- `packages/mcp_json_yaml_toml/server.py` (lines 1874-1880): `main()` function, called via `mcp-json-yaml-toml` CLI
- `pyproject.toml` (line 42): Script entry point definition

**Core Logic:**

- `packages/mcp_json_yaml_toml/server.py` (lines 1-1880): Server initialization, tool definitions, data flow orchestration
- `packages/mcp_json_yaml_toml/yq_wrapper.py` (lines 1-300+): Binary execution and error handling
- `packages/mcp_json_yaml_toml/schemas.py` (lines 1-300+): Schema Store integration and caching

**Tool Implementations:**

- `data()` tool: `server.py` lines 1203-1284
- `data_query()` tool: `server.py` lines 1065-1140
- `data_schema()` tool: `server.py` lines 1455-1528
- `data_convert()` tool: `server.py` lines 1531-1611
- `data_merge()` tool: `server.py` lines 1614-1718

**Format Handlers:**

- TOML write operations: `packages/mcp_json_yaml_toml/toml_utils.py`
- YAML optimization: `packages/mcp_json_yaml_toml/yaml_optimizer.py`
- Format detection and validation: `packages/mcp_json_yaml_toml/config.py`

**Testing:**

- Shared fixtures: `packages/mcp_json_yaml_toml/tests/conftest.py`
- MCP client helper: `packages/mcp_json_yaml_toml/tests/mcp_protocol_client.py`
- Integration tests marked with `@pytest.mark.integration`

**Configuration:**

- Build and tool config: `pyproject.toml`
- Dependencies: `pyproject.toml` (dependencies section) + `uv.lock` (locked versions)
- Linting: `pyproject.toml` (tool.ruff, tool.mypy, tool.basedpyright sections)
- Testing: `pyproject.toml` (tool.pytest.ini_options section)

## Naming Conventions

**Files:**

- Source modules: `snake_case.py` (e.g., `yq_wrapper.py`, `toml_utils.py`)
- Test files: `test_*.py` matching module under test (e.g., `test_yq_wrapper.py`)
- Binary cache: `yq-{os}-{arch}-v{version}` (e.g., `yq-linux-amd64-v4.52.2`)
- Configuration: `*.json` for data (e.g., `default_schema_stores.json`)

**Directories:**

- Package namespace: `mcp_json_yaml_toml` (snake_case, matches installed module name)
- Test directory: `tests/` at package level (co-located)
- Binary cache: `binaries/` for platform-specific executables

**Functions/Methods:**

- Public APIs: `snake_case` (e.g., `execute_yq()`, `validate_format()`)
- Private/internal: `_leading_underscore_snake_case` (e.g., `_dispatch_get_operation()`, `_validate_against_schema()`)
- Handler functions: `_handle_<operation>_<type>()` pattern (e.g., `_handle_data_set()`, `_handle_schema_validate()`)
- Helper functions: `_<action>_<noun>()` pattern (e.g., `_paginate_result()`, `_summarize_structure()`)

**Classes/Types:**

- Models (Pydantic): `PascalCase` (e.g., `YQResult`, `SchemaResponse`)
- Enums: `PascalCase` (e.g., `FormatType`)
- Dataclasses: `PascalCase` (e.g., `SchemaInfo`, `ValidationResult`)
- Exceptions: `PascalCase` ending in Error (e.g., `YQError`, `YQBinaryNotFoundError`)

**Constants:**

- Module-level: `UPPERCASE_WITH_UNDERSCORES` (e.g., `PAGE_SIZE_CHARS`, `DEFAULT_YQ_VERSION`)
- ClassVar: `UPPERCASE` (e.g., constraint names in ConstraintRegistry)

## Where to Add New Code

**New Feature (e.g., new tool or operation):**

- Primary code: Add to `packages/mcp_json_yaml_toml/server.py`
  - Tool function: Use `@mcp.tool()` decorator (lines follow FastMCP patterns)
  - Helper functions: Add with `_` prefix for internal use
- Tests: Add `packages/mcp_json_yaml_toml/tests/test_<feature>.py`
- Documentation: Update README.md with feature description

**New Format Handler (e.g., XML support):**

- If read-only: Handled by yq, no additional code needed (just enable via config)
- If write required: Create `packages/mcp_json_yaml_toml/<format>_utils.py` following toml_utils.py pattern
- Call from appropriate handler in server.py (e.g., `_handle_data_set()`)

**New Constraint (validation rule):**

- Implementation: Add class in `packages/mcp_json_yaml_toml/lmql_constraints.py` extending `Constraint`
- Registration: Automatically registered via ConstraintRegistry decorator
- Tests: Add to `packages/mcp_json_yaml_toml/tests/test_lmql_constraints.py`

**Utilities:**

- Shared helpers: `packages/mcp_json_yaml_toml/<domain>_utils.py` (e.g., `toml_utils.py`)
- Pure functions: Group by domain
- Pattern: Follow existing structure in toml_utils.py and yaml_optimizer.py

**Tests:**

- Placement: Co-located in `packages/mcp_json_yaml_toml/tests/` directory
- Naming: `test_<module>.py` matching source module name
- Fixtures: Shared in `conftest.py`, module-specific in individual test files
- Organization: Use `class Test<Feature>` for grouping related tests

## Special Directories

**packages/mcp_json_yaml_toml/binaries/:**

- Purpose: Platform-specific yq binary cache
- Generated: Yes (auto-downloaded on first use)
- Committed: No (.gitignore excludes binaries)
- Structure: Flat list of versioned binaries
- Naming: `yq-{platform}-{arch}-v{version}` (e.g., `yq-linux-amd64-v4.52.2`)
- Integrity: Checksums verified via DEFAULT_YQ_CHECKSUMS in yq_wrapper.py

**.planning/codebase/:**

- Purpose: GSD-generated codebase documentation and analysis
- Generated: Yes (created by `/gsd:map-codebase` orchestrator)
- Committed: Yes (tracked in git for visibility)
- Contents: ARCHITECTURE.md, STRUCTURE.md, CONVENTIONS.md, TESTING.md, STACK.md, INTEGRATIONS.md, CONCERNS.md

**packages/mcp_json_yaml_toml/tests/**pycache**/:**

- Purpose: Python bytecode cache
- Generated: Yes (auto-created by pytest)
- Committed: No (.gitignore excludes)
- Ignored: Yes (in .gitignore)

**packages/mcp_json_yaml_toml/.mypy_cache/:**

- Purpose: Mypy type checker cache
- Generated: Yes (auto-created by mypy)
- Committed: No (.gitignore excludes)
- Ignored: Yes (in .gitignore)

## Import Structure

**Public API** (from `__init__.py`):

- `from mcp_json_yaml_toml import __version__`

**Internal Imports** (server.py):

```python
from mcp_json_yaml_toml.config import parse_enabled_formats, validate_format, is_format_enabled
from mcp_json_yaml_toml.lmql_constraints import ConstraintRegistry, validate_tool_input
from mcp_json_yaml_toml.schemas import SchemaInfo, SchemaManager
from mcp_json_yaml_toml.toml_utils import delete_toml_key, set_toml_value
from mcp_json_yaml_toml.yaml_optimizer import optimize_yaml_file
from mcp_json_yaml_toml.yq_wrapper import FormatType, YQError, YQExecutionError, execute_yq
```

**Pattern:** Explicit imports grouped by module, no wildcard imports (except FormatType enum usage)

**Relative Imports:** None used; all imports are absolute or from package namespace

## Module Dependencies (Dependency Graph)

```
server.py (entry point)
├── config.py (format validation)
│   └── yq_wrapper.py (FormatType enum)
├── yq_wrapper.py (binary execution)
│   └── (external: httpx, portalocker, orjson)
├── schemas.py (schema management)
│   └── (external: httpx, orjson, ruamel.yaml, tomlkit)
├── lmql_constraints.py (input validation)
│   └── (external: lmql library)
├── toml_utils.py (TOML write handler)
│   └── (external: tomlkit)
└── yaml_optimizer.py (YAML optimization)
    └── (external: ruamel.yaml, orjson)

tests/
├── conftest.py (shared fixtures)
├── mcp_protocol_client.py (test utilities)
└── test_*.py (individual test modules)
    ├── pytest, pytest-asyncio, pytest-mock, pytest-xdist (runners)
    └── fixtures from conftest.py
```

---

_Structure analysis: 2026-02-14_

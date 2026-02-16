# Technology Stack

**Analysis Date:** 2025-02-14

## Languages

**Primary:**

- Python 3.11-3.12+ - Main MCP server implementation
  - Location: `packages/mcp_json_yaml_toml/`
  - All core logic, CLI entry point, schema management, and validation

**Secondary:**

- Bash/Shell - Subprocess calls for yq binary execution
  - Location: `packages/mcp_json_yaml_toml/yq_wrapper.py`
  - Cross-platform binary invocation and management

## Runtime

**Environment:**

- Python 3.11, 3.12, 3.13, 3.14 (officially supported versions)
- POSIX/Linux primary target (with Windows/macOS support via platform-specific binaries)

**Package Manager:**

- uv (UV package manager) - Primary dependency management
  - Lockfile: `uv.lock` present
  - Installation: `uv sync` for development environment
  - Commands: `uv run` for script execution, `uvx` for standalone CLI distribution

## Frameworks

**Core:**

- FastMCP 2.14.4 - MCP protocol server framework
  - Version constraint: `>=2.14.4,<3` (pinned to v2 until v3 stable)
  - Purpose: Server initialization, tool registration, resource management, error handling
  - Location: `packages/mcp_json_yaml_toml/server.py`

**CLI/Scripting:**

- Entry point: `mcp_json_yaml_toml.server:main` (defined in `pyproject.toml`)
- CLI invocation: `mcp-json-yaml-toml` command

**Data Processing:**

- ruamel.yaml 0.18.x - YAML parsing with comment/anchor preservation
  - Version constraint: `>=0.18.0` (intentionally pinned to 0.18, 0.19 has breaking API changes)
  - Purpose: Round-trip YAML parsing maintaining comments, anchors, formatting
  - Location: `packages/mcp_json_yaml_toml/server.py`, `packages/mcp_json_yaml_toml/schemas.py`

- tomlkit 0.14.0+ - TOML parsing with comment/formatting preservation
  - Version constraint: `>=0.14.0`
  - Purpose: TOML manipulation maintaining file structure and comments
  - Location: `packages/mcp_json_yaml_toml/server.py`, `packages/mcp_json_yaml_toml/toml_utils.py`

**Testing:**

- pytest 9.0.2+ - Test runner
  - Configuration: `pyproject.toml [tool.pytest.ini_options]`
  - Plugins: pytest-asyncio, pytest-cov, pytest-mock, pytest-xdist
  - Test parallelism: Automatic (-n auto flag)
  - Coverage minimum: 60% enforced via `tool.coverage.run`
  - Test discovery: `packages/mcp_json_yaml_toml/tests/test_*.py`

- pytest-asyncio - Async test support
- pytest-xdist - Parallel test execution
- pytest-cov - Coverage measurement
- pytest-mock - Mock fixture support

**Build/Dev:**

- hatchling - Build backend for wheel/sdist distribution
- hatch-vcs - Version control-based versioning (git tags)
- Ruff 0.14.14+ - Python linter and formatter
  - Purpose: Code formatting, linting (500+ rules enabled)
  - Format config: `pyproject.toml [tool.ruff.format]`
  - Lint rules: Extensive ruleset including security (S), type checking (TC), docstring (D)
  - Line length: 120 characters
  - Line ending: LF only

- mypy 1.19.1+ - Static type analysis (strict mode)
  - Configuration: `pyproject.toml [tool.mypy]`
  - Settings: strict=true, explicit_package_bases=true

- basedpyright 1.37.2+ - Pyright strict type analysis (alternative/complementary)
  - Configuration: `pyproject.toml [tool.basedpyright]`
  - Type checking mode: basic

- prek 0.2.19+ - Multi-tool linter orchestration
  - Purpose: Runs ruff format, ruff check, mypy, basedpyright, prettier in sequence
  - Usage: `uv run prek run --files <file_paths>` for targeted verification

- toml-sort 0.24.3+ - TOML file sorting
- uv-sort 0.7.0+ - Dependency sorting

## Key Dependencies

**Critical:**

- fastmcp >=2.14.4,<3 - MCP server protocol implementation
  - Why: Core framework for tool registration, resource exposure, error handling
  - Pinned to v2: v3.0.0b1 has breaking changes

- httpx >=0.28.1 - HTTP client library
  - Why: Async HTTP requests for remote schema fetching from SchemaStore.org and GitHub releases
  - Used in: `packages/mcp_json_yaml_toml/schemas.py`, `packages/mcp_json_yaml_toml/yq_wrapper.py`
  - Features: Timeout handling, redirect following, error handling

**Data Handling:**

- orjson >=3.11.6 - Fast JSON serialization/deserialization
  - Why: High-performance JSON operations, required by strong_typing deserialization
  - Used in: Schema caching, data parsing, response formatting

- json-strong-typing >=0.4.3 - Type-safe JSON deserialization
  - Why: Validates and deserializes complex JSON structures (schema catalog, IDE index)
  - Used in: `packages/mcp_json_yaml_toml/schemas.py` for catalog/config parsing

- jsonschema >=4.26.0 - JSON Schema validation
  - Why: Schema validation for JSON/YAML data
  - Supports: Draft 7 and Draft 2020-12 validators
  - Used in: `packages/mcp_json_yaml_toml/server.py` for schema validation

- pydantic - Data validation and serialization (dependency of fastmcp)
  - Used for: BaseModel definitions in yq_wrapper.py, schema definitions

- referencing - JSON Schema $ref resolution
  - Why: Resolves remote schema references via httpx retrieval
  - Used in: `packages/mcp_json_yaml_toml/server.py` for registry creation

**Format Processing:**

- ruamel.yaml >=0.18.0 - YAML with comment preservation
- tomlkit >=0.14.0 - TOML with formatting preservation

**Constraint Generation:**

- lmql >=0.7.3 - Language Model Query Language
  - Why: Regex-based constraint validation for LLM-guided generation
  - Used in: `packages/mcp_json_yaml_toml/lmql_constraints.py` for partial input validation

**File Locking:**

- portalocker >=3.1.1 - Cross-platform file locking
  - Why: Safe concurrent binary downloads during yq wrapper initialization
  - Used in: `packages/mcp_json_yaml_toml/yq_wrapper.py` for download coordination

**AI Integration:**

- tiktoken >=0.12.0 (dev only) - Token counting for OpenAI models
  - Why: Development tool for measuring token efficiency

## Configuration

**Environment:**

- MCP_CONFIG_FORMATS - Comma-separated list of enabled formats (defaults to json,yaml,toml)
  - Parsing: `packages/mcp_json_yaml_toml/config.py:parse_enabled_formats()`
  - Validation: Case-insensitive format names converted to FormatType enum

**Build:**

- `pyproject.toml` - Master configuration file
  - Project metadata, dependencies, dev tools, tool configurations
  - Build backend: hatchling
  - Version source: git tags (hatch-vcs)

- `uv.lock` - Locked dependency versions (committed to git)
  - Ensures reproducible builds and test environments

**Development Tools Configuration:**

- `.prettierrc.json` - Prettier configuration for markdown/JSON/YAML formatting
- `.pre-commit-config.yaml` - Pre-commit hooks for CI/local validation
- `.ruff.toml` equivalent in `pyproject.toml [tool.ruff]` - Linting/formatting rules

## Platform Requirements

**Development:**

- Python 3.11-3.14 with venv or equivalent
- git (for version detection via hatch-vcs)
- uv package manager
- Node.js (optional, for prettier markdown linting in CI)

**Production:**

- Python 3.11-3.14 runtime
- Network access required for:
  - GitHub releases: Auto-download missing yq binaries
  - SchemaStore.org: Fetch JSON Schema definitions
- Platform-specific yq binary (auto-downloaded on first run):
  - Linux amd64, Linux arm64
  - macOS amd64, macOS arm64
  - Windows amd64

**Deployment:**

- PyPI distribution: `pip install mcp-json-yaml-toml` or `uvx mcp-json-yaml-toml`
- MCP client integration via stdio transport
- Local-first: All data processing on user machine, no external APIs required beyond yq/schema downloads

---

_Stack analysis: 2025-02-14_

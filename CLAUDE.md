# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Skills to Enable

When working in this repository, activate these skills for comprehensive development support:

### Essential Skills for This Project

- **python3-development** - Provides Python 3.11+ development patterns, TDD workflows, orchestration guides for delegating to Python sub-agents, reference documentation for 50+ modules, and quality gate enforcement (ruff, mypy, pytest)
- **uv** - Complete guide for the uv package manager used in this project, including dependency management, virtual environments, Python version management, and CI/CD integration patterns
- **fastmcp-creator** - Comprehensive MCP server development guidance including FastMCP framework patterns, agent-centric design principles, tool design best practices, evaluation creation, and deployment strategies

### Additional Recommended Skills

- **hatchling** - Build system documentation (this project uses hatchling as its build backend per pyproject.toml)
- **mkdocs** - For documentation site generation if working on project documentation

## Project Overview

This is an MCP (Model Context Protocol) server that provides AI agents with tools to query and modify JSON, YAML, and TOML configuration files using the `yq` command-line tool. The server is built with FastMCP and provides a unified interface for configuration management.

## Common Development Commands

### Running Tests

```bash
# Run all tests with coverage
uv run pytest

# Run a specific test file
uv run pytest packages/mcp_json_yaml_toml/tests/test_server.py

# Run tests with verbose output
uv run pytest -v

# Run only fast tests (skip slow/integration tests)
uv run pytest -m "not slow and not integration"
```

### Code Quality

```bash
# Format code with ruff
uv run ruff format

# Lint and auto-fix issues
uv run ruff check --fix

# Type check with mypy
uv run mypy packages/

# Run all quality checks together
uv run ruff format && uv run ruff check --fix && uv run mypy packages/
```

### Building and Installing

```bash
# Install in development mode with all dependencies
uv pip install -e ".[dev]"

# Build the package
uv build

# Run the MCP server locally
uv run mcp-json-yaml-toml
```

## Architecture & Key Components

### Core Module Structure

The codebase follows a single-package structure under `packages/mcp_json_yaml_toml/`:

1. **server.py** - Main MCP server implementation
   - Registers tools dynamically based on enabled formats
   - Implements pagination for large results (10KB pages)
   - Provides 5 main tools: `data`, `data_query`, `data_schema`, `data_convert`, `data_merge`

2. **yq_wrapper.py** - Cross-platform yq binary wrapper
   - Auto-downloads missing binaries from GitHub releases
   - Handles platform/architecture detection (Linux/macOS/Windows, amd64/arm64)
   - Provides error handling and format conversions

3. **schemas.py** - JSON Schema management
   - Integrates with SchemaStore.org for automatic schema discovery
   - Caches schemas locally (~/.cache/mcp-json-yaml-toml/schemas)
   - Checks IDE caches first to minimize network requests

4. **yaml_optimizer.py** - YAML anchor/alias optimization
   - Automatically generates anchors for duplicate structures
   - Context-aware (only activates if file already uses anchors)
   - Uses ruamel.yaml for precise YAML manipulation

5. **toml_utils.py** - TOML file operations
   - Uses tomlkit to preserve comments and formatting
   - Handles TOML read/write operations (yq can't write TOML)

6. **config.py** - Configuration management
   - Manages enabled formats via MCP_CONFIG_FORMATS environment variable
   - Validates format support dynamically

### Key Design Decisions

1. **Unified Tools Architecture**: Instead of separate tools for each operation, uses unified `data` and `data_schema` tools with operation parameters. This reduces tool proliferation and improves discoverability.

2. **Format Preservation**: Uses ruamel.yaml and tomlkit specifically to preserve comments, formatting, and structure in configuration files. This maintains file fidelity during modifications.

3. **Pagination Strategy**: Implements cursor-based pagination at 10KB boundaries to handle large configuration files without overwhelming context windows.

4. **Binary Management**: Bundles yq binaries but also implements auto-download from GitHub releases as fallback, storing in ~/.local/bin/ when possible.

5. **Schema Discovery**: Multi-layered approach checking IDE caches → local cache → remote SchemaStore.org, minimizing network requests.

## Testing Strategy

### Test Organization

Tests are located in `packages/mcp_json_yaml_toml/tests/`:

- `test_server.py` - Main server functionality tests
- `test_yq_wrapper.py` - yq binary wrapper tests
- `test_config.py` - Configuration management tests
- `test_yaml_optimizer.py` - YAML anchor optimization tests
- `test_toml_*.py` - TOML-specific functionality tests
- `conftest.py` - Shared pytest fixtures

### Running Single Tests

```bash
# Run a specific test function
uv run pytest packages/mcp_json_yaml_toml/tests/test_server.py::test_data_query_json -v

# Run tests matching a pattern
uv run pytest -k "pagination" -v
```

## Environment Variables

- **MCP_CONFIG_FORMATS**: Comma-separated list of enabled formats (default: "json,yaml,toml")

  ```bash
  export MCP_CONFIG_FORMATS="json,yaml"  # Disable TOML support
  ```

- **MCP_SCHEMA_CACHE_DIRS**: Additional directories to search for schemas

  ```bash
  export MCP_SCHEMA_CACHE_DIRS="/opt/schemas:/usr/local/share/schemas"
  ```

- **YAML_ANCHOR_OPTIMIZATION**: Enable/disable YAML anchor optimization (default: "true")
- **YAML_ANCHOR_MIN_SIZE**: Minimum structure size for anchoring (default: 3)
- **YAML_ANCHOR_MIN_DUPLICATES**: Minimum duplicates to trigger anchoring (default: 2)

## Dependency Management

The project uses minimal, focused dependencies:

- **fastmcp**: MCP server framework (core)
- **orjson**: Fast JSON parsing (performance-critical paths)
- **ruamel.yaml**: YAML with anchor/alias support (only YAML library used)
- **tomlkit**: TOML with comment preservation (yq can't write TOML)
- **httpx**: Async HTTP for schema fetching

## Common Patterns

### Adding a New Tool

Tools are registered via FastMCP decorators in server.py. Follow the existing pattern:

```python
@mcp.tool(description="Tool description")
def tool_name(param: Annotated[str, Field(description="...")]) -> dict:
    # Implementation
```

### Error Handling

Use `ToolError` for user-facing errors that should be reported to the LLM:

```python
from fastmcp.exceptions import ToolError
raise ToolError("Descriptive error message")
```

### Format Detection

Use the config module utilities:

```python
from mcp_json_yaml_toml.config import validate_format, is_format_enabled
validate_format("yaml")  # Raises if format disabled
```

## Debug Tips

1. **Test yq binary directly**:

   ```bash
   ~/.local/bin/yq-linux-amd64 eval '.' test.yaml
   ```

2. **Check schema discovery**:

   ```bash
   ls ~/.cache/mcp-json-yaml-toml/schemas/
   ```

3. **Verbose test output**:

   ```bash
   uv run pytest -vv --tb=short
   ```

4. **Check coverage for specific module**:

   ```bash
   uv run pytest --cov=packages/mcp_json_yaml_toml/server --cov-report=term-missing
   ```

## Project Structure

```text
mcp-json-yaml-toml/
├── packages/mcp_json_yaml_toml/  # Main package
│   ├── server.py                 # MCP server implementation
│   ├── yq_wrapper.py            # yq binary wrapper
│   ├── schemas.py               # Schema management
│   ├── yaml_optimizer.py        # YAML anchor optimization
│   ├── toml_utils.py           # TOML operations
│   ├── config.py               # Configuration management
│   └── tests/                  # Test suite
├── scripts/                     # Utility scripts
│   └── benchmark_token_usage.py # Performance benchmarking
├── fixtures/                    # Test fixtures
├── pyproject.toml              # Project configuration
└── README.md                   # User documentation
```

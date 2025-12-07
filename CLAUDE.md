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

This is an MCP (Model Context Protocol) server that provides AI agents with tools to query and modify JSON, YAML, and TOML files using the `yq` command-line tool. The server is built with FastMCP and provides a unified interface for working with structured data in these formats (including configuration files, manifests, API responses, and other structured data).

---

## Code Quality Gates (MUST PASS)

**All code must pass these quality gates before it can be merged.** Run these checks before committing:

### Quick Validation Command

```bash
# Run all essential checks
uv run ruff format && uv run ruff check --fix && uv run mypy packages/ && uv run pytest --no-cov -q
```

### Pre-commit Hooks (prek)

This project uses `prek` (a Rust-based pre-commit alternative). Install and run hooks:

```bash
# Install hooks (first time only)
uv run prek install

# Run all hooks on staged files
uv run prek

# Run all hooks on all files
uv run prek --all-files

# Run specific hooks
uv run prek ruff ruff-format mypy
```

### CI Pipeline Gates

The GitHub Actions CI runs these checks on every PR. **All must pass:**

| Gate | Command | Description |
|------|---------|-------------|
| Format | `uv run ruff format --check` | Code formatting verification |
| Lint | `uv run ruff check` | Python linting (500+ rules) |
| Type Check | `uv run mypy packages/ --show-error-codes` | Static type analysis |
| Tests | `uv run pytest --cov=packages/mcp_json_yaml_toml` | Test suite with coverage |

---

## Formatters

Run these formatters before committing:

### Python (ruff format)

```bash
# Format all Python files
uv run ruff format

# Check formatting without changes
uv run ruff format --check
```

### YAML/JSON/Markdown (prettier)

```bash
# Format YAML, JSON, and Markdown files
uv run prek prettier
```

### Shell Scripts (shfmt)

```bash
# Format shell scripts (4-space indent, case indent)
uv run prek shell-fmt-go
```

---

## Linters

### Python - ruff

```bash
# Lint and auto-fix
uv run ruff check --fix

# Lint without fixing
uv run ruff check

# Show specific rule info
uv run ruff rule <RULE_CODE>
```

Key rule categories enabled:
- **D** - pydocstyle (docstrings)
- **ANN** - type annotations
- **B** - bugbear (common bugs)
- **S** - bandit (security)
- **PT** - pytest style

### Python - mypy (Type Checking)

```bash
# Type check all packages
uv run mypy packages/

# Show error codes for fixing
uv run mypy packages/ --show-error-codes
```

### Python - basedpyright (Alternative Type Checker)

```bash
# Run via prek
uv run prek basedpyright
```

### Shell Scripts - shellcheck

```bash
# Lint shell scripts
uv run prek shellcheck
```

### Markdown - markdownlint-cli2

```bash
# Lint Markdown files
uv run prek markdownlint-cli2
```

---

## Testing Requirements

### Running Tests

```bash
# Run all tests with coverage
uv run pytest

# Run with verbose output
uv run pytest -v

# Run specific test file
uv run pytest packages/mcp_json_yaml_toml/tests/test_server.py

# Run specific test class or function
uv run pytest packages/mcp_json_yaml_toml/tests/test_server.py::TestDataQuery -v

# Run tests matching a pattern
uv run pytest -k "constraint" -v

# Skip slow/integration tests
uv run pytest -m "not slow and not integration"

# Run without coverage (faster)
uv run pytest --no-cov
```

### Coverage Requirements

```bash
# Run with coverage report
uv run pytest --cov=packages/mcp_json_yaml_toml --cov-report=term-missing

# Generate XML report (for CI)
uv run pytest --cov=packages/mcp_json_yaml_toml --cov-report=xml
```

### Test Organization

Tests are located in `packages/mcp_json_yaml_toml/tests/`. Key test files include:

- `test_server.py` - Main server and tool tests
- `test_lmql_constraints.py` - LMQL constraint validation tests
- `test_yq_wrapper.py` - yq binary wrapper tests
- `test_config.py` - Configuration management tests
- `test_schemas.py` - Schema discovery and validation tests
- `test_yaml_optimizer.py` - YAML anchor optimization tests
- `test_yaml_optimization_integration.py` - YAML optimization integration tests
- `test_set_type_preservation.py` - Type preservation during set operations
- `test_fastmcp_integration.py` - FastMCP framework integration tests
- `test_no_anchor_files.py` - Tests for files without YAML anchors
- `test_toml_*.py` - TOML-specific functionality tests
- `conftest.py` - Shared pytest fixtures

This list is representative; see the `tests/` directory for all test files.

---

## Commit Message Convention

This project uses **Conventional Commits** with required scope. The pre-commit hook enforces this format:

```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

### Allowed Types

| Type | Description |
|------|-------------|
| `feat` | New feature |
| `fix` | Bug fix |
| `docs` | Documentation only |
| `style` | Formatting, no code change |
| `refactor` | Code restructuring |
| `perf` | Performance improvement |
| `test` | Adding/updating tests |
| `chore` | Maintenance tasks |
| `ci` | CI/CD changes |
| `build` | Build system changes |

### Examples

```bash
feat(server): add constraint_validate tool for LMQL validation
fix(yq): handle timeout in binary download
docs(tools): document constraint validation API
refactor(lmql): extract RegexConstraint base class
test(constraints): add tests for partial match detection
```

---

## Design Principles

### DRY (Don't Repeat Yourself)

- Extract common patterns into base classes (see `RegexConstraint`, `EnumConstraint`)
- Use template method pattern for customizable behavior
- Create factory functions for dynamic class generation

### SRP (Single Responsibility Principle)

- Each module has one clear purpose
- Each class handles one concern
- Functions should do one thing well

### OO Design Patterns Used

- **Template Method**: `RegexConstraint.validate()` with hooks for subclasses
- **Registry Pattern**: `ConstraintRegistry` for named constraint lookup
- **Factory Pattern**: `create_enum_constraint()`, `create_pattern_constraint()`
- **Decorator Pattern**: FastMCP's `@mcp.tool()` and `@mcp.resource()`

### Code Consistency

Follow existing patterns in the codebase:
- Use `ClassVar` for class-level type hints
- Use `@classmethod` for methods that don't need instance state
- Use dataclasses for simple data containers
- Use Pydantic models for validation and serialization

---

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

---

## Architecture & Key Components

### Core Module Structure

The codebase follows a single-package structure under `packages/mcp_json_yaml_toml/`:

1. **server.py** - Main MCP server implementation

   - Registers tools dynamically based on enabled formats
   - Implements pagination for large results (10KB pages)
   - Provides 7 main tools: `data`, `data_query`, `data_schema`, `data_convert`, `data_merge`, `constraint_validate`, `constraint_list`

2. **lmql_constraints.py** - LMQL-based constraint validation

   - Uses LMQL's Regex class for pattern matching with partial validation
   - Provides `RegexConstraint` and `EnumConstraint` base classes
   - Exposes constraints via MCP resources (`lmql://constraints`)

3. **yq_wrapper.py** - Cross-platform yq binary wrapper

   - Auto-downloads missing binaries from GitHub releases
   - Handles platform/architecture detection (Linux/macOS/Windows, amd64/arm64)
   - Provides error handling and format conversions

4. **schemas.py** - JSON Schema management

   - Integrates with SchemaStore.org for automatic schema discovery
   - Caches schemas locally (~/.cache/mcp-json-yaml-toml/schemas)
   - Checks IDE caches first to minimize network requests

5. **yaml_optimizer.py** - YAML anchor/alias optimization

   - Automatically generates anchors for duplicate structures
   - Context-aware (only activates if file already uses anchors)
   - Uses ruamel.yaml for precise YAML manipulation

6. **toml_utils.py** - TOML file operations

   - Uses tomlkit to preserve comments and formatting
   - Handles TOML read/write operations (yq can't write TOML)

7. **config.py** - Configuration management
   - Manages enabled formats via MCP_CONFIG_FORMATS environment variable
   - Validates format support dynamically

### Key Design Decisions

1. **Unified Tools Architecture**: Instead of separate tools for each operation, uses unified `data` and `data_schema` tools with operation parameters. This reduces tool proliferation and improves discoverability.

2. **Format Preservation**: Uses ruamel.yaml and tomlkit specifically to preserve comments, formatting, and structure in configuration files. This maintains file fidelity during modifications.

3. **Pagination Strategy**: Implements cursor-based pagination at 10KB boundaries to handle large configuration files without overwhelming context windows.

4. **Binary Management**: Bundles yq binaries but also implements auto-download from GitHub releases as fallback, storing in ~/.local/bin/ when possible.

5. **Schema Discovery**: Multi-layered approach checking IDE caches → local cache → remote SchemaStore.org, minimizing network requests.

6. **Constraint Validation**: Uses LMQL's regex derivatives for partial match detection, enabling guided generation in LLM clients.

---

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

---

## Dependency Management

The project uses minimal, focused dependencies:

- **fastmcp**: MCP server framework (core)
- **orjson**: Fast JSON parsing (performance-critical paths)
- **ruamel.yaml**: YAML with anchor/alias support (only YAML library used)
- **tomlkit**: TOML with comment preservation (yq can't write TOML)
- **httpx**: Async HTTP for schema fetching
- **lmql**: Constraint validation with partial match support

---

## Common Patterns

### Adding a New Tool

Tools are registered via FastMCP decorators in server.py. Follow the existing pattern:

```python
@mcp.tool(description="Tool description")
def tool_name(param: Annotated[str, Field(description="...")]) -> dict:
    # Implementation
```

### Adding a New Constraint

Create a new constraint by extending the appropriate base class:

```python
@ConstraintRegistry.register("MY_CONSTRAINT")
class MyConstraint(RegexConstraint):
    """Validates my custom pattern."""

    description = "Description for LLM clients"
    PATTERN = r"my-pattern-here"

    @classmethod
    def get_definition(cls) -> dict[str, Any]:
        base = super().get_definition()
        base["examples"] = ["example1", "example2"]
        return base
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

---

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

5. **Run single prek hook**:

   ```bash
   uv run prek ruff --all-files
   ```

---

## Project Structure

```text
mcp-json-yaml-toml/
├── packages/mcp_json_yaml_toml/  # Main package
│   ├── server.py                 # MCP server implementation
│   ├── lmql_constraints.py       # LMQL constraint validation
│   ├── yq_wrapper.py             # yq binary wrapper
│   ├── schemas.py                # Schema management
│   ├── yaml_optimizer.py         # YAML anchor optimization
│   ├── toml_utils.py             # TOML operations
│   ├── config.py                 # Configuration management
│   └── tests/                    # Test suite
├── docs/                         # Documentation
│   ├── tools.md                  # Tool reference (7 tools)
│   ├── clients.md                # Client setup guides
│   ├── module-usage.md           # Module dependencies
│   └── yq-wrapper.md             # yq wrapper usage
├── scripts/                      # Utility scripts
│   └── benchmark_token_usage.py  # Performance benchmarking
├── fixtures/                     # Test fixtures
├── .pre-commit-config.yaml       # Pre-commit/prek configuration
├── pyproject.toml                # Project configuration
└── README.md                     # User documentation
```

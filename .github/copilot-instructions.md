# Copilot Instructions - mcp-json-yaml-toml

## Repository Overview

**mcp-json-yaml-toml** is a token-efficient, schema-aware MCP (Model Context Protocol) server for safely reading and modifying JSON, YAML, and TOML files. It provides AI assistants with structured data manipulation tools that preserve comments and formatting while enforcing schema validation.

- **Size**: ~2.4MB, 28 Python files
- **Stack**: Python 3.11-3.14, FastMCP, uv package manager, hatchling build backend
- **Architecture**: 100% local processing, no API keys required
- **Key Features**: yq-based transformations, SchemaStore.org integration, LMQL constraint validation

## Prerequisites & Setup

### Required Tools

- **Python**: 3.11-3.14 (CI tests against 3.11, 3.12, 3.13, 3.14)
- **uv**: Package manager (replaces pip/poetry/pipenv)
- **Node.js**: Required for markdown/prettier linting (npx commands)

### Initial Setup

**ALWAYS run this first after cloning:**

```bash
uv sync  # Installs all dependencies and dev-tools (~30-60 seconds)
```

This command:

- Creates `.venv/` virtual environment
- Installs all Python dependencies from `pyproject.toml`
- Installs dev dependencies (pytest, ruff, mypy, basedpyright, prek)
- Is idempotent - safe to run multiple times

**NEVER use `pip install` or bare `python` commands. Always use `uv run <command>`.**

## Validation Commands (CI Enforcement)

All commands below must pass before merge. Run them in this exact order:

### 1. Code Formatting (5 seconds)

```bash
uv run ruff format --check
```

**If it fails**: Run `uv run ruff format` to auto-fix, then commit.

### 2. Code Linting (8 seconds)

```bash
uv run ruff check
```

**If it fails**: Run `uv run ruff check --fix` to auto-fix. Some issues require manual fixes.

### 3. Type Checking - Mypy (16 seconds)

```bash
uv run mypy packages/ --show-error-codes
```

**Critical**: NEVER suppress type errors with `# type: ignore` for structural issues. Fix the root cause.

### 4. Type Checking - Basedpyright (4 seconds)

```bash
uv run basedpyright packages/
```

### 5. Markdown Linting (5 seconds)

```bash
npx -y markdownlint-cli2
```

Uses `.markdownlint-cli2.jsonc` for configuration.

### 6. YAML/JSON/Markdown Formatting (5 seconds)

```bash
npx -y prettier --check "**/*.{md,json,yaml,yml}" --ignore-path .gitignore
```

**If it fails**: Run `npx -y prettier --write "**/*.{md,json,yaml,yml}" --ignore-path .gitignore` to auto-fix.

### 7. Tests (77 seconds, parallel execution)

```bash
uv run pytest
```

- **Runs**: 350+ tests with parallel execution (`-n auto`)
- **Coverage**: Minimum 60% required (current: ~79%)
- **Location**: `packages/mcp_json_yaml_toml/tests/`
- **Run specific tests**: `uv run pytest -k <pattern>`
- **Note**: 4 pre-existing test failures exist (not your responsibility to fix)

## Quick Validation Workflow

**After editing files, use prek for scoped verification:**

```bash
uv run prek run --files <file1> <file2>
```

**Example:**

```bash
uv run prek run --files packages/mcp_json_yaml_toml/server.py
```

**CRITICAL: NEVER use `--all-files` during feature work** - it causes diff pollution and rewrites git history.

## Project Architecture

### Directory Structure

```
mcp-json-yaml-toml/
├── packages/mcp_json_yaml_toml/     # Main package (ALL code here)
│   ├── server.py                    # MCP server & tool implementations
│   ├── yq_wrapper.py                # Binary management & yq execution
│   ├── schemas.py                   # Schema discovery & validation
│   ├── lmql_constraints.py          # LMQL constraint validation
│   ├── yaml_optimizer.py            # YAML anchor optimization
│   ├── toml_utils.py                # TOML utilities
│   ├── config.py                    # Configuration management
│   ├── version.py                   # Dynamic version from git tags
│   └── tests/                       # All test files (test_*.py)
│       ├── conftest.py              # Shared pytest fixtures
│       └── test_*.py                # Individual test modules
├── .github/workflows/               # CI/CD pipelines
│   ├── test.yml                     # Main CI (format/lint/type/test)
│   └── auto-publish.yml             # PyPI auto-publishing
├── docs/                            # Documentation
├── scripts/                         # Utility scripts
├── pyproject.toml                   # All configuration (build/lint/type/test)
├── .pre-commit-config.yaml          # Pre-commit hooks (uses prek)
├── AGENTS.md                        # Master instructions for AI agents
└── README.md                        # User documentation
```

### Key Configuration Files

- **pyproject.toml**: Single source of truth for all tool configs (ruff, mypy, basedpyright, pytest, hatch)
- **.pre-commit-config.yaml**: Git hooks config (uses `prek`, a Rust-based pre-commit replacement)
- **manifest.json**: MCPB manifest for MCP server distribution
- **.gitignore**: Excludes `.venv/`, `__pycache__/`, `binaries/`, build artifacts

## CI/CD Pipeline (`.github/workflows/test.yml`)

The CI runs these jobs in parallel (all must pass):

1. **format**: `uv run ruff format --check`
2. **lint**: `uv run ruff check --output-format=github`
3. **typecheck**: `uv run mypy packages/ --show-error-codes`
4. **basedpyright**: `uv run basedpyright packages/`
5. **lint-extra**: markdownlint, prettier, shellcheck, shfmt
6. **validate-manifest**: `npx -y @anthropic-ai/mcpb validate manifest.json`
7. **test**: Matrix across Python 3.11-3.14, uploads coverage XML
8. **coverage-summary**: Comments PR with coverage percentage
9. **release**: Auto-tags and releases on main branch merges

## Testing Guidelines

### Creating Tests

- **Location**: `packages/mcp_json_yaml_toml/tests/test_<feature>.py`
- **Naming**: `test_*.py` files, `test_*` functions, `Test*` classes
- **Fixtures**: Use shared fixtures from `conftest.py`
- **Coverage Target**: 60% minimum for new features
- **Parallel Safe**: Tests run with `pytest-xdist` (`-n auto`)

### Running Tests

```bash
# All tests (77 seconds)
uv run pytest

# Specific test file
uv run pytest packages/mcp_json_yaml_toml/tests/test_server.py

# Specific test pattern
uv run pytest -k "test_data_get"

# With verbose output
uv run pytest -v

# Skip parallel execution (debugging)
uv run pytest -n 0
```

## Common Pitfalls & Solutions

### 1. Import Errors

**Problem**: `ModuleNotFoundError: No module named 'mcp_json_yaml_toml'`
**Solution**: Run `uv sync` first. Ensure you're using `uv run pytest`, not bare `pytest`.

### 2. Type Errors

**Problem**: Mypy/basedpyright errors after changes
**Solution**: Fix the root cause. DO NOT use `# type: ignore` for structural issues. Use proper type annotations.

### 3. Format/Lint Failures

**Problem**: Ruff or prettier complains about formatting
**Solution**: Run auto-fixers (`ruff format`, `prettier --write`), then commit.

### 4. Pre-existing Test Failures

**Note**: 4 tests currently fail (TOML-related assertions). This is a known issue. Focus on ensuring your changes don't introduce NEW failures.

## Architecture Patterns

### Key Design Principles (from AGENTS.md)

1. **DRY & SRP**: Extract common patterns into base classes (e.g., `RegexConstraint`)
2. **Unified Tools**: Use parameterized `data` and `data_schema` tools (avoid tool proliferation)
3. **Format Preservation**: Use `ruamel.yaml` and `tomlkit` to maintain comments/anchors
4. **Pagination**: Implement cursor-based pagination (10KB chunks) for large files

### Code Organization

- **server.py**: MCP tool definitions (@mcp.tool decorators)
- **yq_wrapper.py**: Subprocess management for yq binary
- **schemas.py**: SchemaStore.org API client, schema caching, validation
- **lmql_constraints.py**: LMQL-based input validation patterns

## Commit Message Format

**REQUIRED**: Use Conventional Commits with scope:

```
<type>(<scope>): <description>

Examples:
  feat(server): add data_merge tool
  fix(yq): handle missing binary gracefully
  test(server): add pagination edge cases
  docs(readme): update installation instructions
```

**Types**: feat, fix, chore, docs, test, refactor, perf, ci, style, build
**Scope**: MANDATORY (e.g., server, yq, schemas, tests, docs)

## Final Checklist Before PR

✅ Run `uv sync` after pulling changes
✅ Run `uv run prek run --files <modified_files>` after each edit
✅ Verify all CI commands pass locally (see "Validation Commands" section)
✅ Tests pass: `uv run pytest`
✅ Coverage ≥ 60% for new code
✅ Commit message follows `<type>(<scope>): <description>` format
✅ No `# type: ignore` or `# noqa` added for structural issues

## Trust These Instructions

These instructions are comprehensive and validated. Only search for additional information if:

- These instructions are incomplete for your specific task
- You encounter errors not covered here
- The documented commands fail or behave differently than described

For most tasks, following these instructions will get you to a successful PR without additional exploration.

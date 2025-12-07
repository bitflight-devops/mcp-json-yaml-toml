# Copilot Coding Agent Instructions

## Repository

MCP server for JSON/YAML/TOML file manipulation. Python 3.11-3.12, FastMCP framework, uv package manager.

## Required Commands

Always use `uv run` prefix for Python commands. Never use `pip` or bare `python`.

### Setup
```bash
uv sync
```

### Before Every Commit (run in this order)
```bash
uv run ruff format
uv run ruff check --fix
uv run mypy packages/
uv run basedpyright
```

All four must pass. Do not specify paths for ruff - configuration is in pyproject.toml.

### Tests
```bash
uv run pytest
```

Coverage minimum: 60%. Tests run in parallel automatically.

## Commit Messages

Format: `<type>(<scope>): <description>`

Required types: feat, fix, chore, docs, test, refactor, perf, ci, style, build

Scope is mandatory. Examples:
- `feat(server): add validation tool`
- `fix(yaml): preserve comments`

## File Locations

| Purpose | Path |
|---------|------|
| Main source | `packages/mcp_json_yaml_toml/` |
| Entry point | `packages/mcp_json_yaml_toml/server.py` |
| Tests | `packages/mcp_json_yaml_toml/tests/` |
| All config | `pyproject.toml` |
| CI workflow | `.github/workflows/test.yml` |

## Lint Rules

- Google-style docstrings required
- Type annotations required on all functions
- `Returns:` section required in docstrings for functions with return values
- Tests exempt from documentation requirements (see `[tool.ruff.lint.per-file-ignores]`)

Check `pyproject.toml` for per-file exceptions before adding type: ignore comments.

## CI Jobs

1. `uv run ruff format --check`
2. `uv run ruff check --output-format=github`
3. `uv run mypy packages/ --show-error-codes`
4. `uv run pytest --cov=packages/mcp_json_yaml_toml`

## Do Not

- Modify lint rule configuration in pyproject.toml (humans set quality standards)
- Use `pip install` or `python -m pytest`
- Skip type checking
- Commit without running all four quality checks

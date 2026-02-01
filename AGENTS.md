# AGENTS.md - Master Instructions for AI Agents

This document is the **authoritative source of truth** for all AI agents (Claude Code, GitHub Copilot, Cursor, etc.) working in this repository. All coding assistants MUST read and follow these instructions to ensure consistency, quality, and architectural integrity.

---

## 1. Project Context & Stack

- **Purpose**: MCP server for advanced JSON/YAML/TOML manipulation using `yq`.
- **Core Stack**: Python 3.11-3.12+, FastMCP, uv, hatchling.
- **Key Logic**: Local binary management (`yq_wrapper.py`), schema discovery (`schemas.py`), and LMQL constraint validation (`lmql_constraints.py`).
- **Principles**: 100% local processing, zero required API keys, high-fidelity format preservation (comments/anchors).

---

## 2. Holistic Linting Philosophy

We don't just "fix errors"; we improve system health. AI Agents MUST follow these rules:

1.  **Resolution over Suppression**: Linting errors are symptoms of deeper issues (architecture, type flow, or logic). **NEVER** "squash" or silence errors with `# type: ignore` or `# noqa` for structural or type problems. Address the root cause.
2.  **Automation over Manual Work**: Never manually fix formatting, alignment, or quotes. Let the automated tools (`ruff format`, `prettier`) handle it.
3.  **Scoped Verification**: High-quality PRs are surgical. Always use the `--files` argument with `prek` to verify only your changes.
    - **NEVER** use `--all-files` during feature work (causes diff pollution and history destruction).

---

## 3. Mandatory Quality Gates

All code MUST pass these gates before being considered production-ready.

### The "One-Shot" Verification Loop

After editing ANY file, run this command:

```bash
uv run prek run --files <file_path1> <file_path2>
```

### Full Linting Suite (Enforced in CI)

| Gate         | Command                                    | Description                              |
| ------------ | ------------------------------------------ | ---------------------------------------- |
| **Format**   | `uv run ruff format --check`               | Python formatting check                  |
| **Lint**     | `uv run ruff check`                        | Python linting (500+ rules)              |
| **Type 1**   | `uv run mypy packages/ --show-error-codes` | Mypy static type analysis                |
| **Type 2**   | `uv run basedpyright packages/`            | Pyright strict type analysis             |
| **Markdown** | `npx markdownlint-cli2 "**/*.md"`          | Markdown style enforcement               |
| **Prettier** | `npx prettier --check`                     | YAML/JSON/MD formatting                  |
| **Tests**    | `uv run pytest`                            | Test suite (coverage enabled by default) |

---

## 4. Development Workflow

### Setup & Sync

```bash
uv sync  # Install all dependencies and dev-tools
```

### Dependency Management

Always use `uv add` and `uv remove` to manage dependencies:

```bash
uv add <package>          # Add a runtime dependency
uv add --dev <package>    # Add a dev dependency
uv remove <package>       # Remove a dependency
```

**NEVER** manually edit `pyproject.toml` to add/remove dependencies - `uv add/remove` handles version resolution, lockfile updates, and installation in one command.

### Testing Requirements

- **Creating Tests**: Place all tests in `packages/mcp_json_yaml_toml/tests/` using the `test_*.py` naming convention. Use `conftest.py` for shared fixtures.
- **Coverage**: Minimum 60% required for new features (Current: ~79%). Settings are automatically applied from `pyproject.toml`.
- **Parallelism**: Tests run in parallel automatically.
- **Manual Run**: `uv run pytest` for standard execution. Use `-k <pattern>` to run specific tests.
- **Feature Verification**: Run `uv run packages/mcp_json_yaml_toml/tests/verify_features.py` to manually verify pagination and hint advisory logic.

### Commit Conventions

Format: `<type>(<scope>): <description>`

- **Types**: feat, fix, chore, docs, test, refactor, perf, ci, style, build.
- **Scope**: Mandatory (e.g., `feat(server)`, `fix(yq)`).

---

## 5. Architecture & Design Principles

- **DRY & SRP**: Extract common patterns into base classes (see `RegexConstraint`).
- **Unified Tools**: Use unified `data` and `data_schema` tools with parameters to avoid tool proliferation.
- **Format Preservation**: Use `ruamel.yaml` and `tomlkit` to maintain file fidelity (comments, etc.).
- **Pagination**: Implement cursor-based pagination (10KB chunks) for large files.

---

## 6. Do Not Hallucinate

- Do **NOT** modify lint rule configurations in `pyproject.toml`.
- Do **NOT** use `pip install` or bare `python` commands.
- Do **NOT** manually edit `pyproject.toml` for dependencies - use `uv add/remove`.
- Do **NOT** skip type checking.
- Do **NOT** commit without running the "One-Shot" verification.

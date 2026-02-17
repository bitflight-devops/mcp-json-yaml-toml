# MCP JSON/YAML/TOML Server - AI Agent Instructions

AI agents working in this repository follow these instructions for consistency, quality, and architectural integrity.

---

## Project Context

**Purpose**: MCP server for advanced JSON/YAML/TOML manipulation using `yq`

**Stack**: Python 3.11-3.12+, FastMCP, uv, hatchling

**Core Components**:

- `yq_wrapper.py` - Local binary management
- `schemas.py` - Schema discovery
- `lmql_constraints.py` - LMQL constraint validation

**Design Principles**:

- 100% local processing (no API keys required)
- High-fidelity format preservation (comments, anchors, whitespace)
- Unified tools with parameters (avoid tool proliferation)
- Cursor-based pagination (10KB chunks for large files)

---

## Linting Philosophy

<linting_principles>

Linting errors indicate deeper issues in architecture, type flow, or logic. Address root causes rather than suppressing symptoms.

**Resolution Hierarchy**:

1. Structural/type problems → Fix architecture or type annotations
2. Formatting/style → Use automated tools (`ruff format`, `prettier`)
3. True false positives → Document why before suppressing

**Suppression Usage**:

- Acceptable: Vendored code, intentional examples, platform-specific constraints
- Unacceptable: Structural problems, type errors, logic issues

**Reason**: Suppressions (`# type: ignore`, `# noqa`) hide technical debt. Fixing root causes improves system health.

</linting_principles>

---

## Development Workflow

### Environment Setup

```bash
uv sync  # Install dependencies and dev-tools
```

### Dependency Management

```bash
uv add <package>          # Add runtime dependency
uv add --dev <package>    # Add dev dependency
uv remove <package>       # Remove dependency
```

`uv add/remove` handles version resolution, lockfile updates, and installation atomically. Manual `pyproject.toml` edits bypass dependency resolution and cause inconsistent environments.

### Verification Protocol

<verification_workflow>

After editing files, verify only changed files (surgical verification prevents diff pollution):

```bash
uv run prek run --files <file_path1> <file_path2>
```

**Scope Discipline**:

- Feature work → Use `--files` with specific paths
- Pre-release audit → Use `--all-files` (separate from feature commits)

**Reason**: `--all-files` during feature work reformats unrelated files, creating noise in git history and obscuring actual changes.

</verification_workflow>

### Quality Gates (CI-Enforced)

<quality_gates>

**Python**:

```bash
uv run ruff format --check          # Formatting (Black-compatible)
uv run ruff check                   # Linting (500+ rules)
uv run mypy packages/ --show-error-codes  # Type checking (mypy)
uv run basedpyright packages/       # Type checking (strict)
```

**Structured Data**:

```bash
npx prettier --check                # YAML/JSON/MD formatting
npx markdownlint-cli2 "**/*.md"     # Markdown style
```

**Tests**:

```bash
uv run pytest                       # Full test suite
uv run pytest -k <pattern>          # Specific tests
uv run packages/mcp_json_yaml_toml/tests/verify_features.py  # Manual feature verification
```

**Coverage**: Minimum 60% required for new features (current: ~79%). Configuration in `pyproject.toml` applies automatically.

**Test Location**: `packages/mcp_json_yaml_toml/tests/test_*.py` (use `conftest.py` for shared fixtures)

</quality_gates>

---

## Architecture Patterns

<architecture_principles>

**DRY & SRP**: Extract common patterns into base classes

Example: `RegexConstraint` base class eliminates duplication across constraint types.

**Unified Tool Design**: Use parameterized tools (`data`, `data_schema`) with operation parameters instead of creating separate tools per operation.

**Format Preservation**:

- YAML → `ruamel.yaml` (preserves comments, anchors, formatting)
- TOML → `tomlkit` (preserves comments, inline tables)
- JSON → Standard library with indent preservation

**Pagination**: Cursor-based pagination with 10KB chunks for large file operations.

</architecture_principles>

---

## Commit Conventions

```text
<type>(<scope>): <description>

Types: feat, fix, chore, docs, test, refactor, perf, ci, style, build
Scope: Mandatory (component or area affected)
```

**Examples**:

```text
feat(server): add cursor-based pagination for large YAML files
fix(yq): handle binary download on arm64 macOS
test(constraints): add regex pattern validation tests
```

---

## Constraints

<prohibited_actions>

Use the specified tools and workflows. Alternative approaches bypass project automation and cause inconsistent environments.

**Tool Usage**:

- Dependency management → Use `uv add/remove` (not manual `pyproject.toml` edits)
- Python execution → Use `uv run` (not bare `python` or `pip install`)
- Type checking → Run both `mypy` and `basedpyright` (required gates)

**Configuration**:

- Lint rules configured in `pyproject.toml` (do not modify without explicit requirement)
- Pre-commit hooks managed by `prek` (do not bypass with `--no-verify`)

**Verification**:

- Run `prek run --files` before committing (catches issues locally)
- Scoped verification during feature work (use `--all-files` only for pre-release audits)

</prohibited_actions>

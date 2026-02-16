# Coding Conventions

**Analysis Date:** 2026-02-14

## Naming Patterns

**Files:**

- Snake case for all module files: `yq_wrapper.py`, `lmql_constraints.py`, `yaml_optimizer.py`
- Test files follow pattern: `test_*.py`
- Configuration: lowercase with underscores: `pyproject.toml`

**Functions:**

- Snake case consistently: `parse_enabled_formats()`, `get_yq_binary_path()`, `_validate_and_write_content()`
- Private functions prefixed with single underscore: `_parse_content_for_validation()`, `_get_storage_location()`, `_compute_structure_hash()`
- Public API functions without leading underscore

**Variables:**

- Snake case for local and module-level: `enabled_formats`, `schema_manager`, `test_offsets`
- Constants in uppercase with underscores: `DEFAULT_YQ_VERSION`, `GITHUB_REPO`, `CHECKSUM_MIN_FIELDS`, `YAML_ANCHOR_MIN_SIZE`
- Type hints required for function parameters and return values

**Types and Classes:**

- PascalCase for classes: `SchemaResponse`, `YQError`, `ValidationResult`, `Constraint`, `RegexConstraint`
- Enum values uppercase: `FormatType.JSON`, `FormatType.YAML` (members are uppercase, inherited from StrEnum)
- Dataclasses with PascalCase names and field types explicitly annotated

## Code Style

**Formatting:**

- Tool: `ruff format` (automatic enforcement via `uv run prek run`)
- Double quotes for all strings (configured in `ruff.lint.flake8-quotes`)
- Line ending: LF only
- Max line length: 120 characters (configured in `tool.ruff.lint.pycodestyle`)
- Docstring quotes: Double quotes
- Skip magic trailing comma enabled

**Linting:**

- Tool: `ruff check` with extensive rule set (60+ rule categories enabled)
- Complexity limit: 12 McCabe complexity (configured in `tool.ruff.lint.mccabe`)
- Type checking: Both `mypy` (strict mode) and `basedpyright` (basic mode)
- Formatter: `prettier` for YAML/JSON/Markdown files
- Type annotations required for all public functions and methods (ANN rule enabled)

**Key Linting Rules:**

- `ANN`: Full type annotation enforcement (except ANN401 for JSON Any types)
- `S`: Security checks enabled (intentional subprocess usage allowed via ignore)
- `D`: Docstring enforcement (Google-style, per `pydocstyle` convention)
- `RUF`: Ruff-specific improvements required
- `UP`: Python language upgrade suggestions enforced
- `BLE`: No blind exception catching without specific handlers
- `PERF`: Performance improvements enforced
- `SIM`: Code simplification suggestions required
- `TRY`: Exception handling best practices enforced

## Import Organization

**Order:**

1. Standard library imports (e.g., `import os`, `from pathlib import Path`)
2. Third-party imports (e.g., `import httpx`, `from pydantic import BaseModel`)
3. Local package imports (e.g., `from mcp_json_yaml_toml.config import parse_enabled_formats`)
4. TYPE_CHECKING conditional imports for type hints only

**Requirements:**

- Required imports: `from __future__ import annotations` (enforced first via `ruff.lint.isort` config)
- Combine as imports enabled: `from typing import TYPE_CHECKING, Annotated, Any`
- Force single-line imports disabled (allows natural grouping)
- No relative imports; use absolute imports only

**Examples from codebase:**

```python
from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

import httpx
import orjson
from fastmcp.exceptions import ToolError

from mcp_json_yaml_toml.config import parse_enabled_formats
from mcp_json_yaml_toml.yq_wrapper import FormatType

if TYPE_CHECKING:
    from pytest_mock import MockerFixture
```

## Error Handling

**Patterns:**

- Specific exception types caught with immediate recovery action (fail-fast principle)
- Generic `Exception` catching only when handling broad library exceptions with known recovery
- Errors propagate naturally to caller if no specific recovery exists
- Custom exception hierarchy: `YQError` (base) → `YQBinaryNotFoundError`, `YQExecutionError`

**Examples:**

```python
# Specific recovery action - acceptable
try:
    return db.query(User, id)
except ConnectionError:
    logger.warning("DB unavailable, using cache")
    return cache.get(f"user:{id}")

# From yq_wrapper.py: specific exception types
try:
    local_bin.mkdir(parents=True, exist_ok=True)
    test_file = local_bin / ".write_test"
    test_file.touch()
    test_file.unlink()
except (OSError, PermissionError):  # pragma: no cover
    pass

# From server.py: ToolError wrapping for API layer
except Exception as e:
    raise ToolError(f"Failed to parse content for validation: {e}") from e
```

**Error Messages:**

- Include context about what operation failed
- For validation errors, include what was expected
- For file operations, include file path when relevant
- Chain exceptions with `from e` to preserve tracebacks

## Logging

**Framework:** Python `logging` module (used in `schemas.py` for warnings/debug)

**Patterns:**

- Import: `import logging` at module level
- Usage in modules: `logging.warning()`, `logging.debug()` (not console print except in scripts)
- No structured logging; simple string messages sufficient
- Used for warnings about missing resources or fallback behaviors

## Comments

**When to Comment:**

- Complex algorithms or non-obvious logic (e.g., checksum parsing in `yq_wrapper.py`)
- Explanations of why a choice was made (e.g., "fmt: off" before checksum dicts, "pragma: no cover" for platform-specific code)
- Trade-off explanations (e.g., why ruamel.yaml 0.18 is pinned)
- Environment variable configurations (e.g., `YAML_ANCHOR_MIN_SIZE` purpose)

**JSDoc/TSDoc:**

- Google-style docstrings required for all public functions and classes
- Format: Multiline with description, Args, Returns, Raises sections
- Include: Parameter descriptions, return type descriptions, exception types that can be raised
- Example docstrings use triple backticks with syntax highlighting

**Comment Examples from codebase:**

```python
# From yq_wrapper.py - explaining a workaround
# Ensure version starts with 'v' for consistency with GitHub tags
if not version.startswith("v"):
    version = f"v{version}"

# From config.py - inline explanation
# Parse comma-separated list
format_names = [name.strip().lower() for name in env_value.split(",")]

# From schemas.py - header sections
# ==============================================================================
# Dataclasses for known JSON structures - strong_typing handles deserialization
# ==============================================================================
```

## Function Design

**Size:**

- Target under 50 lines per function for readability
- Complex operations like file parsing or validation can exceed but should have clear single purpose
- Helper functions extracted when logic block is reused or exceeds 100 lines

**Parameters:**

- Maximum 7 positional parameters (PLR0913 ignored but still discouraged)
- Use Annotated types for constrained values: `path: Annotated[Path, "file must exist"]`
- Optional parameters with sensible defaults at end of signature
- No \* unpacking of large dictionaries; prefer explicit parameters or dataclasses

**Return Values:**

- Always type-annotated (enforced via ANN rule)
- Return None explicitly or return a value, never implicit None
- For multiple values, use dataclass (Pydantic BaseModel) not tuple
- Example: `YQResult` model instead of `(stdout, stderr, returncode)`

**Examples:**

```python
# From server.py - clear return type
def _parse_content_for_validation(
    content: str, input_format: FormatType | str
) -> Any | None:
    """Parse content string into data structure for schema validation."""

# From yq_wrapper.py - optional parameter with default
def get_yq_version() -> str:
    """Get the yq version to use for downloads."""
    version = os.environ.get("YQ_VERSION", "").strip()

# From schemas.py - dataclass return instead of tuple
@dataclass
class SchemaInfo:
    """Schema metadata information."""
    name: str
    url: str
    source: str
```

## Module Design

**Exports:**

- No wildcard imports `from X import *`
- Explicit imports from modules using qualified names
- Public API in `__init__.py` files with `__all__` list
- Internal helper functions not exported

**Barrel Files:**

- Package `__init__.py` only exports version: `from mcp_json_yaml_toml.version import __version__`
- No re-exporting of submodule contents; consumers import directly from submodules
- Example: `from mcp_json_yaml_toml.lmql_constraints import ConstraintRegistry`

**Module Structure Example (`server.py`):**

```python
# 1. Module docstring explaining purpose
"""MCP server for querying and modifying JSON, YAML, and TOML files."""

# 2. Imports organized by category
from __future__ import annotations
# ... standard library ...
# ... third party ...
# ... local imports ...

# 3. Global state (FastMCP instance, schema manager)
mcp = FastMCP("mcp-json-yaml-toml", mask_error_details=False)
schema_manager = SchemaManager()

# 4. Private helper functions (_prefixed)
def _parse_content_for_validation(...) -> Any | None:
    """..."""

# 5. Public tool implementations (registered with @mcp.tool decorator)
@mcp.tool()
def data_query(...) -> dict[str, Any]:
    """..."""
```

---

_Convention analysis: 2026-02-14_

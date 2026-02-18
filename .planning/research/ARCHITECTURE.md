# Architecture Research: Loguru Logging & Enhanced Schema Validation

**Domain:** MCP server for structured data manipulation (JSON/YAML/TOML)
**Researched:** 2026-02-17
**Focus:** Integration of loguru logging replacement and enhanced schema validation into existing layered architecture
**Confidence:** HIGH (codebase analysis + verified library documentation)

## Current Architecture Snapshot

The codebase completed a v1.1 refactoring that decomposed a monolithic `server.py` into a layered architecture:

```
server.py              ~84 lines   Entry point: FastMCP init + tool imports
tools/                 6 files     Thin @mcp.tool decorators delegating to services
services/              7 files     Business logic (get, mutation, query, diff, schema_validation, pagination)
backends/              3 files     yq binary management + execution abstraction
formats/               2 files     Format detection, content parsing, value parsing
schemas/               5 files     Schema discovery, loading, scanning, IDE cache, manager facade
models/                2 files     Pydantic response models, schema dataclasses
config.py                          Environment-based format configuration
telemetry.py                       OpenTelemetry tracer helper (no-op when SDK absent)
lmql_constraints.py                LMQL constraint validation
```

### Current Logging State

Three stdlib `logging` usage sites exist, all at DEBUG level:

| File                         | Usage                                                                           | Logger Pattern                 |
| ---------------------------- | ------------------------------------------------------------------------------- | ------------------------------ |
| `backends/binary_manager.py` | `logger = logging.getLogger(__name__)` with `.debug()`, `.info()`, `.warning()` | Module-level named logger      |
| `schemas/manager.py`         | `logging.debug()` (module-level calls)                                          | Direct `logging.debug()` calls |
| `schemas/scanning.py`        | `logging.debug()` (1 call)                                                      | Direct `logging.debug()` call  |

No centralized logging configuration exists. No log output is visible by default because no handlers are configured for the `mcp_json_yaml_toml` namespace.

### Current Schema Validation State

Schema validation lives in `services/schema_validation.py`:

- `_validate_against_schema(data, schema_path)` returns `tuple[bool, str]`
- Uses `Draft7Validator` or `Draft202012Validator` based on `$schema` field
- `referencing.Registry` with httpx retrieval for remote `$ref` resolution
- Catches **first** `ValidationError` only, returns `e.message` as a string
- Called from `_validate_and_write_content()` in mutation_operations.py (pre-write validation)
- Called from `_handle_schema_validate()` in tools/schema.py (explicit validation action)

## Integration Analysis: Loguru Logging

### What Changes

**NEW file:** `packages/mcp_json_yaml_toml/logging.py` -- centralized logging configuration

This module provides:

1. Loguru configuration (remove default sink, add controlled sinks)
2. InterceptHandler for stdlib logging compatibility
3. Environment-variable-driven sink setup
4. A single `configure_logging()` function called from server startup

**MODIFIED files (logging consumers):**

| File                         | Current                                          | After                                              |
| ---------------------------- | ------------------------------------------------ | -------------------------------------------------- |
| `backends/binary_manager.py` | `import logging` + `logging.getLogger(__name__)` | `from loguru import logger`                        |
| `schemas/manager.py`         | `import logging` + `logging.debug(...)`          | `from loguru import logger`                        |
| `schemas/scanning.py`        | `import logging` + `logging.debug(...)`          | `from loguru import logger`                        |
| `server.py`                  | No logging                                       | Add `configure_logging()` call before tool imports |

**NEW logging sites (should be added during integration):**

| File                              | What to Log                                     | Level         |
| --------------------------------- | ----------------------------------------------- | ------------- |
| `backends/yq.py`                  | yq subprocess commands, execution times, errors | DEBUG/WARNING |
| `services/schema_validation.py`   | Validation results, schema load failures        | DEBUG/WARNING |
| `services/mutation_operations.py` | File write operations, optimization results     | DEBUG         |
| `tools/data.py`                   | Tool invocations with file paths                | DEBUG         |
| `config.py`                       | Format enable/disable decisions                 | DEBUG         |

### Architecture of logging.py

```python
"""Centralized logging configuration for MCP JSON/YAML/TOML server.

Provides loguru-based structured logging with:
- Stdlib logging interception (captures httpx, jsonschema, etc.)
- Environment-variable-driven configuration
- MCP-safe defaults (stderr only, never stdout)
"""
from __future__ import annotations

import logging
import os
import sys

from loguru import logger


class InterceptHandler(logging.Handler):
    """Route stdlib logging to loguru.

    Captures log messages from third-party libraries (httpx, jsonschema,
    opentelemetry) and routes them through loguru's unified pipeline.
    """

    def emit(self, record: logging.LogRecord) -> None:
        # Get corresponding loguru level
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = str(record.levelno)

        # Find caller from where the logged message originated
        frame, depth = logging.currentframe(), 0
        while frame and (depth == 0 or frame.f_code.co_filename == logging.__file__):
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )


def configure_logging() -> None:
    """Configure logging for the MCP server.

    Environment variables:
        MCP_LOG_LEVEL: Minimum log level for stderr output (default: none/disabled)
        MCP_LOG_DIR: Directory for file logging with rotation (default: disabled)
        MCP_LOG_FORMAT: Log format string (default: loguru default)

    CRITICAL: Never writes to stdout -- MCP protocol uses stdout for messages.
    """
    # Remove loguru's default stderr handler
    logger.remove()

    # Stderr logging (opt-in via MCP_LOG_LEVEL)
    log_level = os.getenv("MCP_LOG_LEVEL", "").strip().upper()
    if log_level:
        logger.add(
            sys.stderr,
            level=log_level,
            format="<level>{level: <8}</level> | "
                   "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
                   "<level>{message}</level>",
            diagnose=False,  # No sensitive data in tracebacks
        )

    # File logging (opt-in via MCP_LOG_DIR)
    log_dir = os.getenv("MCP_LOG_DIR", "").strip()
    if log_dir:
        logger.add(
            f"{log_dir}/mcp-json-yaml-toml.log",
            rotation="10 MB",
            retention="3 days",
            level=log_level or "DEBUG",
            format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | "
                   "{name}:{function}:{line} - {message}",
            serialize=False,  # Human-readable by default; set True for JSON
            diagnose=False,
        )

    # Intercept stdlib logging -> loguru
    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)
```

### Integration Point: server.py

```python
# server.py -- add before tool imports
from mcp_json_yaml_toml.logging import configure_logging

configure_logging()  # Must run before any library imports that log

mcp = FastMCP("mcp-json-yaml-toml")
schema_manager = SchemaManager()
```

### MCP Protocol Safety

The MCP stdio transport uses stdout for protocol messages. Loguru's default handler writes to stderr, which is correct. The `configure_logging()` function explicitly targets `sys.stderr` and never adds a stdout sink. This is enforced by design, not by accident.

### Stdlib Interception Scope

The InterceptHandler captures logging from:

- `httpx` (HTTP request logging in binary_manager.py and schemas/manager.py)
- `jsonschema` (validation warnings)
- `opentelemetry` (if SDK configured)
- Any future library that uses stdlib logging

### Dependency Impact

Adding `loguru>=0.7.3` to `dependencies` in pyproject.toml. Loguru has zero dependencies (pure Python). No transitive dependency conflicts.

### Type Checking Compatibility

Loguru provides type stubs in its package. The `loguru-mypy` plugin (optional, add to dev dependencies) enables better type inference for `logger.opt()` and `logger.bind()`. Basedpyright works with loguru's built-in stubs without additional plugins.

## Integration Analysis: Enhanced Schema Validation

### What Changes

**MODIFIED file:** `services/schema_validation.py` -- the core change

Current signature and behavior:

```python
def _validate_against_schema(data: Any, schema_path: Path) -> tuple[bool, str]
```

New signature:

```python
def _validate_against_schema(
    data: Any, schema_path: Path, *, collect_all: bool = True
) -> ValidationResult
```

**NEW model:** Add `ValidationResult` dataclass to `models/responses.py` (or a new `models/validation.py`):

```python
@dataclass
class SchemaValidationError:
    """A single schema validation error with path context."""
    message: str
    json_path: str           # e.g., "$.database.port"
    schema_path: str         # e.g., "/properties/database/properties/port/type"
    validator: str           # e.g., "type", "required", "enum"
    context: list[str] = field(default_factory=list)  # Sub-errors for anyOf/oneOf

@dataclass
class ValidationResult:
    """Result of schema validation with all errors collected."""
    is_valid: bool
    errors: list[SchemaValidationError] = field(default_factory=list)
    error_count: int = 0

    @property
    def message(self) -> str:
        """Backward-compatible single message string."""
        if self.is_valid:
            return "Schema validation passed"
        if not self.errors:
            return "Schema validation failed"
        return self.errors[0].message

    def to_dict(self) -> dict[str, Any]:
        """Structured error output for tool responses."""
        ...
```

### Changes to Callers

**`services/mutation_operations.py` -- `_validate_and_write_content()`:**

```python
# Before:
is_valid, msg = _validate_against_schema(validation_data, schema_path)
if not is_valid:
    raise ToolError(f"Schema validation failed: {msg}")

# After:
result = _validate_against_schema(validation_data, schema_path)
if not result.is_valid:
    # Include structured errors in ToolError for AI context
    error_details = "; ".join(
        f"{e.json_path}: {e.message}" for e in result.errors[:5]
    )
    raise ToolError(f"Schema validation failed ({result.error_count} errors): {error_details}")
```

**`tools/schema.py` -- `_handle_schema_validate()`:**

```python
# Before:
is_valid, message = _validate_against_schema(result.data, schema_file)
validation_results["schema_validated"] = is_valid
validation_results["schema_message"] = message

# After:
validation = _validate_against_schema(result.data, schema_file)
validation_results["schema_validated"] = validation.is_valid
validation_results["schema_message"] = validation.message
validation_results["schema_errors"] = [
    {
        "path": e.json_path,
        "message": e.message,
        "validator": e.validator,
    }
    for e in validation.errors
]
validation_results["schema_error_count"] = validation.error_count
```

### Implementation Detail: iter_errors

The key change in `_validate_against_schema` is replacing:

```python
# Current: raises on first error
Draft202012Validator(schema, registry=registry).validate(data)
```

With:

```python
# New: collects all errors
validator_cls = Draft7Validator if "draft-07" in schema_dialect else Draft202012Validator
validator = validator_cls(schema, registry=registry)
errors = sorted(validator.iter_errors(data), key=lambda e: list(e.absolute_path))
```

`iter_errors()` is a built-in method on all jsonschema validators. It yields `ValidationError` objects without raising. Each error provides `.absolute_path`, `.schema_path`, `.message`, `.validator`, and `.context` (sub-errors for compound validators like `anyOf`/`oneOf`).

### Backward Compatibility

The `ValidationResult.message` property provides a single-string summary identical to the current output. Callers that previously destructured `tuple[bool, str]` need updating, but there are exactly **2 call sites** (identified above). The response dict format is additive -- `schema_message` and `schema_validated` fields are preserved, new `schema_errors` and `schema_error_count` fields are added.

### Response Model Changes

The `ValidationResponse` model in `models/responses.py` gains optional fields:

```python
class ValidationResponse(ToolResponse):
    format: str | None = None
    syntax_valid: bool = False
    schema_validated: bool = False
    syntax_message: str | None = None
    schema_message: str | None = None
    schema_file: str | None = None
    overall_valid: bool = False
    # NEW:
    schema_errors: list[dict[str, str]] | None = None
    schema_error_count: int = 0
```

## Component Boundary Map

### New Components

| Component               | Location                                          | Responsibility                                                   | Depends On             |
| ----------------------- | ------------------------------------------------- | ---------------------------------------------------------------- | ---------------------- |
| `logging.py`            | `packages/mcp_json_yaml_toml/logging.py`          | Loguru configuration, InterceptHandler, environment-driven sinks | loguru, stdlib logging |
| `SchemaValidationError` | `models/responses.py` (or `models/validation.py`) | Single validation error with path context                        | None (dataclass)       |
| `ValidationResult`      | `models/responses.py` (or `models/validation.py`) | Aggregated validation result with backward-compatible `.message` | SchemaValidationError  |

### Modified Components

| Component                         | What Changes                                                                 | Why                                           |
| --------------------------------- | ---------------------------------------------------------------------------- | --------------------------------------------- |
| `server.py`                       | Add `configure_logging()` call                                               | Initialize logging before any module loads    |
| `backends/binary_manager.py`      | Replace `import logging` with `from loguru import logger`                    | Unified logging pipeline                      |
| `schemas/manager.py`              | Replace `logging.debug()` with `logger.debug()`                              | Unified logging pipeline                      |
| `schemas/scanning.py`             | Replace `logging.debug()` with `logger.debug()`                              | Unified logging pipeline                      |
| `services/schema_validation.py`   | Return `ValidationResult` instead of `tuple[bool, str]`; use `iter_errors()` | Collect all errors, provide structured output |
| `services/mutation_operations.py` | Update `_validate_and_write_content()` to use `ValidationResult`             | Caller adapts to new return type              |
| `tools/schema.py`                 | Update `_handle_schema_validate()` to include structured errors              | Caller adapts to new return type              |
| `models/responses.py`             | Add `schema_errors` and `schema_error_count` to `ValidationResponse`         | Structured error output                       |

### Unchanged Components

| Component              | Why Unchanged                                                                        |
| ---------------------- | ------------------------------------------------------------------------------------ |
| `backends/base.py`     | No logging, no schema validation                                                     |
| `backends/yq.py`       | No stdlib logging (uses telemetry spans); logging additions are optional enhancement |
| `formats/base.py`      | Pure utilities, no logging needed                                                    |
| `tools/data.py`        | Delegates to services; logging happens at service level                              |
| `tools/query.py`       | Delegates to services                                                                |
| `tools/convert.py`     | Delegates to services                                                                |
| `tools/diff.py`        | Delegates to services                                                                |
| `config.py`            | Pure functions; logging additions are optional enhancement                           |
| `telemetry.py`         | OpenTelemetry traces are orthogonal to loguru logging                                |
| `lmql_constraints.py`  | No logging, no schema validation                                                     |
| `schemas/models.py`    | Pure dataclasses                                                                     |
| `schemas/loading.py`   | Pure extraction functions                                                            |
| `schemas/ide_cache.py` | No direct logging                                                                    |

## Data Flow Changes

### Logging Data Flow (New)

```
Application startup (server.py)
    |
    v
configure_logging()
    |-- Remove loguru default sink
    |-- Add stderr sink (if MCP_LOG_LEVEL set)
    |-- Add file sink (if MCP_LOG_DIR set)
    |-- Install InterceptHandler on stdlib root logger
    |
    v
All subsequent code:
    |
    |-- loguru.logger.debug/info/warning/error()  --> loguru pipeline
    |-- stdlib logging.debug/info/warning/error()  --> InterceptHandler --> loguru pipeline
    |-- httpx internal logging                     --> InterceptHandler --> loguru pipeline
    |
    v
Sinks (configured):
    |-- sys.stderr (filtered by MCP_LOG_LEVEL)
    |-- file (rotated, if MCP_LOG_DIR set)
```

### Schema Validation Data Flow (Changed)

```
BEFORE:
    _validate_against_schema(data, schema_path) -> (bool, str)
        |-- Validator.validate(data)  # raises on FIRST error
        |-- catch ValidationError -> return (False, e.message)

AFTER:
    _validate_against_schema(data, schema_path) -> ValidationResult
        |-- validator.iter_errors(data)  # yields ALL errors
        |-- for each error:
        |       |-- extract absolute_path -> json_path string
        |       |-- extract schema_path -> schema location
        |       |-- extract validator keyword
        |       |-- extract context (sub-errors for anyOf/oneOf)
        |       |-- build SchemaValidationError
        |-- return ValidationResult(is_valid, errors, error_count)
```

## Patterns to Follow

### Pattern: Environment-Gated Logging

Logging is disabled by default. No file output, no stderr output unless opted in. This matches the existing telemetry pattern (`telemetry.py` returns no-op tracer when OTEL SDK not configured).

```python
# Zero overhead when logging disabled
logger.remove()  # Remove default handler

# Opt-in only
if os.getenv("MCP_LOG_LEVEL"):
    logger.add(sys.stderr, level=...)
```

### Pattern: Structured Context with bind()

Loguru's `bind()` adds context to log messages without changing the message string:

```python
# In binary_manager.py
logger.bind(yq_version=version, platform=f"{system}/{arch}").info("Downloading yq binary")

# In mutation_operations.py
logger.bind(file=str(path), operation="set", format=input_format).debug("Executing mutation")
```

### Pattern: Backward-Compatible Return Type Evolution

The schema validation change uses a dataclass with a `.message` property that returns the same string the old `tuple[bool, str]` provided. This allows incremental migration of callers.

## Anti-Patterns to Avoid

### Anti-Pattern: Logging to stdout

MCP servers use stdout for protocol messages. Any loguru sink pointing to `sys.stdout` will corrupt the MCP protocol. The `configure_logging()` function explicitly prevents this.

### Anti-Pattern: Per-Module Logger Configuration

Loguru uses a single global `logger` object. Do not configure sinks in individual modules. All configuration happens in `logging.py` and is called once from `server.py`.

```python
# WRONG: configuring loguru in a module
# backends/binary_manager.py
from loguru import logger
logger.add("binary.log")  # NO -- creates duplicate sinks

# RIGHT: just use the global logger
from loguru import logger
logger.info("message")  # Sinks configured centrally
```

### Anti-Pattern: Catching All Validation Errors in a Loop

Don't manually iterate and try/except. Use `iter_errors()` which is specifically designed for collecting all errors:

```python
# WRONG: catching one at a time
errors = []
try:
    validator.validate(data)
except ValidationError as e:
    errors.append(e)  # Only gets the first one

# RIGHT: iter_errors yields all
errors = list(validator.iter_errors(data))
```

## Build Order

The two features are independent and can be built in either order. However, building loguru first provides logging for schema validation debugging.

### Recommended Order

**Step 1: Loguru logging infrastructure (logging.py + server.py integration)**

- Create `logging.py` with `configure_logging()`
- Add `configure_logging()` call to `server.py`
- Add `loguru>=0.7.3` to dependencies
- No behavior change until env vars are set

**Step 2: Replace stdlib logging in existing files**

- `backends/binary_manager.py`: Replace `import logging` / `logging.getLogger` with `from loguru import logger`
- `schemas/manager.py`: Replace `logging.debug()` with `logger.debug()`
- `schemas/scanning.py`: Replace `logging.debug()` with `logger.debug()`
- Total: 3 files, mechanical replacement

**Step 3: Add logging to key code paths (optional, can be deferred)**

- `backends/yq.py`: Log subprocess commands at DEBUG
- `services/mutation_operations.py`: Log file write operations
- `tools/*.py`: Log tool invocations

**Step 4: Schema validation models**

- Create `SchemaValidationError` and `ValidationResult` in `models/`
- Update `ValidationResponse` in `models/responses.py`

**Step 5: Enhanced schema validation logic**

- Modify `_validate_against_schema()` in `services/schema_validation.py`
- Replace `validate()` with `iter_errors()`
- Build `ValidationResult` from error list

**Step 6: Update callers**

- `services/mutation_operations.py`: Update `_validate_and_write_content()`
- `tools/schema.py`: Update `_handle_schema_validate()`

**Step 7: Tests**

- Test `configure_logging()` with env vars
- Test InterceptHandler captures stdlib logging
- Test `_validate_against_schema()` returns multiple errors
- Test backward compatibility of `ValidationResult.message`
- Test `schema_errors` field in validation response

### Dependency Graph

```
Step 1 (logging.py)
    |
    v
Step 2 (replace stdlib logging)    Step 4 (validation models)
    |                                   |
    v                                   v
Step 3 (add new logging sites)     Step 5 (iter_errors logic)
                                        |
                                        v
                                   Step 6 (update callers)
                                        |
                                        v
                                   Step 7 (tests)
```

Steps 1-3 (logging) and Steps 4-6 (schema validation) are independent tracks. Step 7 covers both.

## Testing Strategy

### Logging Tests

```python
# Test that configure_logging removes default handler
def test_configure_logging_removes_default():
    configure_logging()
    # No output when MCP_LOG_LEVEL not set

# Test stderr sink activation
def test_configure_logging_with_level(monkeypatch, capsys):
    monkeypatch.setenv("MCP_LOG_LEVEL", "DEBUG")
    configure_logging()
    logger.debug("test message")
    assert "test message" in capsys.readouterr().err

# Test InterceptHandler routes stdlib to loguru
def test_intercept_handler_captures_stdlib(monkeypatch, capsys):
    monkeypatch.setenv("MCP_LOG_LEVEL", "DEBUG")
    configure_logging()
    import logging
    logging.getLogger("test").warning("stdlib message")
    assert "stdlib message" in capsys.readouterr().err

# Test file sink rotation
def test_file_logging(monkeypatch, tmp_path):
    monkeypatch.setenv("MCP_LOG_DIR", str(tmp_path))
    monkeypatch.setenv("MCP_LOG_LEVEL", "DEBUG")
    configure_logging()
    logger.info("file test")
    log_file = tmp_path / "mcp-json-yaml-toml.log"
    assert log_file.exists()
```

### Schema Validation Tests

```python
# Test multiple errors collected
def test_validate_collects_all_errors(tmp_path):
    schema = {"type": "object", "properties": {"a": {"type": "integer"}, "b": {"type": "string"}}, "required": ["a", "b"]}
    schema_file = tmp_path / "schema.json"
    schema_file.write_text(json.dumps(schema))

    result = _validate_against_schema({"a": "not_int", "b": 42}, schema_file)
    assert not result.is_valid
    assert result.error_count == 2  # both type violations

# Test backward-compatible message
def test_validation_result_message_compat(tmp_path):
    # ... setup with one error
    result = _validate_against_schema(invalid_data, schema_file)
    assert isinstance(result.message, str)
    assert len(result.message) > 0

# Test json_path extraction
def test_validation_error_includes_path(tmp_path):
    # ... nested schema with deep path
    result = _validate_against_schema(data, schema_file)
    assert any("database.port" in e.json_path for e in result.errors)
```

## Sources

- [Loguru GitHub](https://github.com/Delgan/loguru) -- HIGH confidence (primary source)
- [Loguru migration guide](https://loguru.readthedocs.io/en/stable/resources/migration.html) -- HIGH confidence (official docs)
- [Loguru InterceptHandler recipe](https://github.com/Delgan/loguru/issues/78) -- HIGH confidence (author's recipe)
- [Loguru type hints](https://loguru.readthedocs.io/en/stable/api/type_hints.html) -- HIGH confidence (official docs)
- [loguru-mypy plugin](https://github.com/kornicameister/loguru-mypy) -- MEDIUM confidence (community plugin)
- [jsonschema error handling](https://python-jsonschema.readthedocs.io/en/latest/errors/) -- HIGH confidence (official docs)
- [jsonschema iter_errors](https://python-jsonschema.readthedocs.io/en/stable/errors/) -- HIGH confidence (official docs)
- [MCP stdio transport logging constraint](https://medium.com/@laurentkubaski/understanding-mcp-stdio-transport-protocol-ae3d5daf64db) -- MEDIUM confidence (community article, verified against MCP spec)
- [FastMCP logging docs](https://gofastmcp.com/servers/logging) -- HIGH confidence (official FastMCP docs)
- [Loguru PyPI (v0.7.3)](https://pypi.org/project/loguru/) -- HIGH confidence (primary source)
- Current codebase analysis: direct file reading of all source modules -- HIGH confidence (primary evidence)

---

_Architecture research for: Loguru logging replacement and enhanced schema validation integration_
_Researched: 2026-02-17_

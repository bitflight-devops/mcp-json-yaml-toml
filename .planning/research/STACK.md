# Stack Research: Loguru Logging + Enhanced Schema Validation

**Domain:** MCP server instrumentation and schema validation improvements
**Researched:** 2026-02-17
**Confidence:** HIGH

## Recommended Stack Additions

### New Runtime Dependency

| Technology | Version | Purpose                                             | Why Recommended                                                                                                                                                                                                                                                                                                                                                  |
| ---------- | ------- | --------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| loguru     | >=0.7.3 | Structured logging replacement for stdlib `logging` | Zero-config logger with built-in JSON serialization (`serialize=True`), automatic stderr output (MCP stdio transport compatible), `logger.bind()` for structured context, lazy evaluation. Eliminates boilerplate: no getLogger, no handler config, no formatter setup. Single global `logger` object replaces per-module `logging.getLogger(__name__)` pattern. |

### No New Dev Dependencies Required

loguru ships built-in `.pyi` type stubs that work with both mypy (strict mode) and basedpyright without plugins.

The `loguru-mypy` plugin exists but is effectively unmaintained (no releases in 12+ months). The built-in stubs are sufficient. **Do not add loguru-mypy.**

### No New Dependencies for Schema Validation

The enhanced schema validation features (JSON path errors, all-errors reporting, pre-write validation) require **zero new libraries**. Everything needed exists in the installed `jsonschema>=4.26.0`:

| Existing Capability     | API                                                                  | Verified                                                      |
| ----------------------- | -------------------------------------------------------------------- | ------------------------------------------------------------- |
| All-errors iteration    | `Draft202012Validator(schema).iter_errors(data)`                     | YES -- returns lazy iterator of all ValidationError instances |
| JSON path per error     | `ValidationError.json_path` (e.g., `$.foo.bar`)                      | YES -- returns RFC 9535 JSON Path string                      |
| Best error selection    | `jsonschema.exceptions.best_match(errors)`                           | YES -- selects most relevant error by path depth              |
| Error detail attributes | `.validator`, `.validator_value`, `.schema`, `.schema_path`, `.path` | YES -- all present                                            |
| Draft 2020-12 support   | `Draft202012Validator`                                               | YES -- already used                                           |
| Draft 7 support         | `Draft7Validator`                                                    | YES -- already used                                           |
| Remote $ref resolution  | `referencing.Registry(retrieve=...)`                                 | YES -- referencing 0.36.2 installed                           |

All capabilities verified by direct execution against the installed jsonschema 4.26.0 in the project venv.

## Installation

```bash
# Single new runtime dependency
uv add "loguru>=0.7.3"

# Nothing else needed -- jsonschema 4.26.0 already has all required capabilities
```

## Integration Points

### 1. Loguru + FastMCP (Critical)

**Constraint:** FastMCP uses stdlib `logging` with `RichHandler` on stderr. MCP protocol messages use stdout. All logging MUST go to stderr.

**Verified:** FastMCP's `fastmcp/utilities/logging.py` creates `logging.StreamHandler()` with `Console(stderr=True)`. Loguru defaults to stderr. No conflict.

**Pattern:** InterceptHandler bridges stdlib logging (from FastMCP, httpx, and other libraries) into loguru's unified pipeline:

```python
import logging
import sys
from loguru import logger

class InterceptHandler(logging.Handler):
    """Route stdlib logging to loguru."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = str(record.levelno)

        frame, depth = logging.currentframe(), 2
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )

def setup_logging(*, json_output: bool = False, level: str = "INFO") -> None:
    """Configure loguru as the unified logging backend."""
    logger.remove()
    logger.add(
        sys.stderr,
        level=level,
        serialize=json_output,
        format="<level>{level: <8}</level> | "
               "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> "
               "- <level>{message}</level>",
    )
    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)
```

### 2. Loguru + Existing Code (3 files to migrate)

**Current stdlib logging usage:**

| File                         | Pattern                                                                      | Calls     |
| ---------------------------- | ---------------------------------------------------------------------------- | --------- |
| `backends/binary_manager.py` | `logger = logging.getLogger(__name__)` + `.info()`, `.debug()`, `.warning()` | ~15 calls |
| `schemas/manager.py`         | `logging.debug()` direct calls                                               | 2 calls   |
| `schemas/scanning.py`        | `logging.debug()` direct call                                                | 1 call    |

**Migration:** Replace `import logging` / `logging.getLogger(__name__)` with `from loguru import logger`. API is nearly identical:

- `logger.info("msg %s", arg)` becomes `logger.info("msg {}", arg)` (curly brace format)
- `logger.debug("msg")` stays `logger.debug("msg")`
- `logger.warning("msg")` stays `logger.warning("msg")`

### 3. Schema Validation Enhancement (Zero new deps)

**Current code in `services/schema_validation.py`:**

- Calls `validator.validate(data)` which raises `ValidationError` on first error
- Returns `(bool, str)` tuple with a single error message
- No JSON path information in error output

**Enhancement path using existing jsonschema APIs:**

- Replace `validator.validate()` with `validator.iter_errors()` to collect all errors
- Format each error with `.json_path` for precise location reporting
- Use `best_match()` for summary when many errors exist

**Pre-write validation already exists** in `mutation_operations.py` via `_validate_and_write_content()`. The enhancement is to improve the error detail returned by `_validate_against_schema()` -- switching from single-error to all-errors mode with JSON paths.

## Alternatives Considered

| Recommended            | Alternative                            | When to Use Alternative                                                                                                                                                                 |
| ---------------------- | -------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| loguru 0.7.3           | structlog                              | If deep stdlib logging integration without interception is needed. structlog wraps stdlib loggers directly but requires more configuration. loguru wins on simplicity for this project. |
| loguru 0.7.3           | stdlib logging + custom JSON formatter | If zero new runtime dependencies is a hard constraint. The project already has 10 runtime deps; one more for dramatically better DX is justified.                                       |
| jsonschema iter_errors | Pydantic model validation              | Only if data models were Pydantic-based. They aren't -- the server validates arbitrary user data against external JSON Schema files. jsonschema is the correct tool.                    |

## What NOT to Use

| Avoid                    | Why                                                                                                                    | Use Instead                                        |
| ------------------------ | ---------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------- |
| loguru-mypy plugin       | Unmaintained (no releases in 12+ months). loguru's built-in `.pyi` stubs pass both mypy strict and basedpyright.       | loguru's built-in type stubs                       |
| python-json-logger       | Only formats stdlib logging as JSON. loguru's `serialize=True` does the same with less code and adds `bind()` context. | loguru with `serialize=True`                       |
| jsonschema FormatChecker | Adds runtime dependencies for format-specific validation (email, uri). Not needed for current requirements.            | Skip unless format validation explicitly requested |
| Custom JSON path builder | `ValidationError.json_path` already returns `$.foo.bar` syntax. No need for custom path traversal from `.path` deque.  | `error.json_path` attribute                        |

## Version Compatibility

| Package            | Compatible With          | Notes                                                                                                                                                                                                                                   |
| ------------------ | ------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| loguru>=0.7.3      | Python 3.11-3.14         | Supports 3.5+. No upper bound conflicts with project's `>=3.11,<3.15`.                                                                                                                                                                  |
| loguru>=0.7.3      | mypy>=1.19 (strict)      | Built-in `.pyi` stubs. No plugin needed.                                                                                                                                                                                                |
| loguru>=0.7.3      | basedpyright>=1.37       | Standard `.pyi` resolution. Works out of the box.                                                                                                                                                                                       |
| loguru>=0.7.3      | FastMCP 3.x              | Loguru defaults to stderr. InterceptHandler bridges stdlib from FastMCP.                                                                                                                                                                |
| loguru>=0.7.3      | ruff G rules             | Ruff's G001-G202 (logging-format) rules target stdlib `logging` only. loguru uses `{}` format syntax (not `%s`). May need to verify G rules don't false-positive on loguru calls. The project already ignores G rules except G201/G202. |
| jsonschema>=4.26.0 | referencing>=0.36.2      | Already installed and verified. `iter_errors()`, `json_path`, `best_match()` all functional.                                                                                                                                            |
| jsonschema>=4.26.0 | types-jsonschema>=4.26.0 | Already in dev deps (4.26.0.20260109). Type stubs cover `iter_errors` and `ValidationError` attributes.                                                                                                                                 |

## Configuration Recommendations

### Environment Variables

```python
# In config.py or a new logging.py module
import os

LOG_LEVEL = os.environ.get("MCP_LOG_LEVEL", "INFO")
LOG_JSON = os.environ.get("MCP_LOG_JSON", "false").lower() == "true"
```

### Test Configuration

```python
# In conftest.py
import sys
from loguru import logger

@pytest.fixture(autouse=True)
def _reset_loguru():
    """Reset loguru sink for each test to avoid cross-test leakage."""
    logger.remove()
    logger.add(sys.stderr, level="DEBUG")
    yield
```

## Sources

- [loguru PyPI](https://pypi.org/project/loguru/) -- version 0.7.3 confirmed (latest, released 2024-12-06)
- [loguru documentation](https://loguru.readthedocs.io/) -- serialize, InterceptHandler pattern, type hints
- [loguru GitHub](https://github.com/Delgan/loguru) -- releases, issue tracker
- [loguru-mypy GitHub](https://github.com/kornicameister/loguru-mypy) -- maintenance status: low activity
- [jsonschema error handling docs](https://python-jsonschema.readthedocs.io/en/latest/errors/) -- iter_errors, best_match, json_path
- [jsonschema exceptions API](https://python-jsonschema.readthedocs.io/en/stable/api/jsonschema/exceptions/) -- ValidationError attributes
- [FastMCP logging utilities](https://gofastmcp.com/python-sdk/fastmcp-utilities-logging) -- stdlib logging + RichHandler on stderr
- FastMCP source (`fastmcp/utilities/logging.py`) -- verified stdlib `logging.StreamHandler` with `Console(stderr=True)`
- Direct execution against installed jsonschema 4.26.0 -- all APIs verified functional

---

_Stack research for: loguru logging replacement + enhanced schema validation_
_Researched: 2026-02-17_

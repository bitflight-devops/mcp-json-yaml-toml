# Phase 9: Logging Infrastructure - Research

**Researched:** 2026-02-18
**Domain:** Python logging (loguru), stdlib interception, pytest caplog integration, type checking
**Confidence:** HIGH

<user_constraints>

## User Constraints (from CONTEXT.md)

### Locked Decisions

- **Log output format**: Structured JSON (JSONL) to file for machine parseability; human-readable colored output to console when console mode is explicitly enabled; default mode: JSONL to file only, stderr silent; minimal fields per JSON entry: timestamp, level, module, message
- **Verbosity & filtering**: Default log level: WARNING; MCP protocol events at DEBUG; business logic follows standard level hierarchy; size-based log rotation for JSONL file (e.g., 10MB threshold, keep N backups)
- **Configuration surface**: Environment variable prefix `MCP_JYT_` (`MCP_JYT_LOG_LEVEL`, `MCP_JYT_LOG_FILE`); default log file location: `~/.local/share/mcp-json-yaml-toml/logs/` (XDG data dir); `configure_logging()` called automatically on module import
- **caplog integration**: Full caplog support; automatic setup via conftest.py; file sink disabled during tests; tests assert on structured fields (levelname, module, message)
- **Env var naming**: `MCP_JYT_` prefix specifically to avoid conflicts with ~50 other MCP servers on the same machine
- **Dual output model**: JSONL to file is primary sink, console/stderr is secondary mode for debugging -- not both simultaneously by default

### Claude's Discretion

- Exact rotation size threshold and backup count
- PropagateHandler implementation details for caplog
- Loguru sink configuration internals
- Console output format string (when console mode enabled)

### Deferred Ideas (OUT OF SCOPE)

None
</user_constraints>

<phase_requirements>

## Phase Requirements

| ID     | Description                                                                                              | Research Support                                                                                                                                              |
| ------ | -------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| LOG-02 | Centralized logging configuration via `logging.py` module with `configure_logging()`                     | Loguru `logger.configure()` API verified; `logger.add()` for JSONL file sink with `serialize=True`; environment variable configuration via `MCP_JYT_*` prefix |
| LOG-03 | InterceptHandler captures project-namespace stdlib loggers (`mcp_json_yaml_toml.*`) and routes to loguru | Official InterceptHandler pattern from loguru docs verified; attach to specific namespace loggers only, not root                                              |
| LOG-05 | pytest caplog fixture overridden in conftest.py for loguru compatibility                                 | Official caplog override pattern verified; inline in conftest.py rather than `pytest-loguru` dependency                                                       |
| LOG-06 | All logging writes to stderr only (MCP stdout protocol safety)                                           | Loguru defaults to stderr; JSONL file sink goes to file path; no stdout sinks ever configured; `diagnose=False` for production safety                         |

</phase_requirements>

## Summary

This phase installs loguru 0.7.3, creates a centralized `logging.py` module with `configure_logging()`, implements InterceptHandler for stdlib logger bridging within the `mcp_json_yaml_toml.*` namespace, overrides the pytest caplog fixture for loguru compatibility, and verifies that mypy and basedpyright pass cleanly. No modules are migrated to loguru in this phase -- that is Phase 10.

The codebase currently has 3 files using stdlib `logging` (binary_manager.py with 1 named logger + ~18 call sites, scanning.py with 1 direct `logging.debug()` call, manager.py with 2 direct `logging.debug()` calls). Two existing tests use `caplog.at_level("WARNING", logger="mcp_json_yaml_toml.backends.binary_manager")` which will continue working through the InterceptHandler bridge. The InterceptHandler intercepts stdlib logging calls and routes them to loguru sinks, so existing code works without modification.

**Primary recommendation:** Install loguru 0.7.3 via `uv add`, create `packages/mcp_json_yaml_toml/logging.py` with `configure_logging()` that sets up JSONL file sink + optional stderr sink, implement InterceptHandler targeting only `mcp_json_yaml_toml.*` namespace loggers, override caplog fixture in conftest.py, and call `configure_logging()` from `__init__.py`.

## Standard Stack

### Core

| Library | Version | Purpose                       | Why Standard                                                                                                                                                                                             |
| ------- | ------- | ----------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| loguru  | 0.7.3   | Structured logging with sinks | De facto Python logging library; ships with PEP 484 stub files for type checker compatibility; `serialize=True` provides JSONL out of the box; single global logger eliminates `getLogger()` boilerplate |

### Supporting

| Library      | Version                   | Purpose                     | When to Use                                                                                                               |
| ------------ | ------------------------- | --------------------------- | ------------------------------------------------------------------------------------------------------------------------- |
| platformdirs | 4.5.1 (already installed) | XDG-compliant default paths | Resolve `~/.local/share/mcp-json-yaml-toml/logs/` cross-platform; transitive dep of FastMCP, no additional install needed |

### Alternatives Considered

| Instead of            | Could Use             | Tradeoff                                                                                                                                                           |
| --------------------- | --------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| loguru                | structlog             | structlog requires more configuration boilerplate; loguru's `serialize=True` handles JSONL natively; user decision locks loguru                                    |
| Inline caplog fixture | pytest-loguru 0.4.0   | pytest-loguru is ~15 lines of code doing exactly what the official docs recommend; inlining avoids an extra dependency and gives full control over filter behavior |
| loguru-mypy plugin    | loguru built-in stubs | loguru-mypy adds extra lazy-logging checks but has low maintenance activity; loguru's own `.pyi` stubs provide sufficient type coverage for mypy and basedpyright  |

**Installation:**

```bash
uv add loguru>=0.7.3
```

## Architecture Patterns

### New Module Location

```
packages/mcp_json_yaml_toml/
├── logging.py          # NEW: configure_logging(), InterceptHandler
├── __init__.py         # MODIFIED: import configure_logging, call on load
├── tests/
│   └── conftest.py     # MODIFIED: add caplog fixture override
└── ...existing modules unchanged...
```

### Pattern 1: Centralized `configure_logging()` with Environment Variables

**What:** Single function configures all loguru sinks based on `MCP_JYT_*` environment variables.
**When to use:** Called once on module import via `__init__.py`.
**Example:**

```python
# Source: loguru official docs (configure method + environment variables)
# packages/mcp_json_yaml_toml/logging.py
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    import loguru

_DEFAULT_LOG_DIR = Path.home() / ".local" / "share" / "mcp-json-yaml-toml" / "logs"
_DEFAULT_LOG_LEVEL = "WARNING"
_CONFIGURED = False


def configure_logging() -> None:
    """Configure loguru with JSONL file sink and optional stderr.

    Environment variables:
        MCP_JYT_LOG_LEVEL: Override default WARNING level
        MCP_JYT_LOG_FILE: Override default log file path
        MCP_JYT_LOG_CONSOLE: Set to "1" to enable stderr console output

    Idempotent -- safe to call multiple times.
    """
    global _CONFIGURED  # noqa: PLW0603
    if _CONFIGURED:
        return
    _CONFIGURED = True

    # Remove loguru's default stderr handler
    logger.remove()

    level = os.environ.get("MCP_JYT_LOG_LEVEL", _DEFAULT_LOG_LEVEL).upper()

    # JSONL file sink (primary)
    log_dir = Path(os.environ.get("MCP_JYT_LOG_FILE", "")).parent if os.environ.get("MCP_JYT_LOG_FILE") else _DEFAULT_LOG_DIR
    log_file = Path(os.environ.get("MCP_JYT_LOG_FILE", "")) if os.environ.get("MCP_JYT_LOG_FILE") else log_dir / "server.jsonl"
    log_dir.mkdir(parents=True, exist_ok=True)

    logger.add(
        log_file,
        level=level,
        serialize=True,       # JSONL output
        rotation="10 MB",     # Size-based rotation
        retention=5,           # Keep 5 backup files
        enqueue=True,         # Thread-safe async writing
        diagnose=False,       # No variable inspection in production
    )

    # Optional stderr console sink (disabled by default -- MCP stdout safety)
    if os.environ.get("MCP_JYT_LOG_CONSOLE", "").strip() in ("1", "true", "yes"):
        logger.add(
            sys.stderr,
            level=level,
            format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan> - <level>{message}</level>",
            colorize=True,
            diagnose=False,
        )

    # Install InterceptHandler on project-namespace stdlib loggers
    _install_intercept_handler()
```

### Pattern 2: InterceptHandler for Namespace-Targeted Interception

**What:** Captures stdlib `logging` calls from `mcp_json_yaml_toml.*` namespace and routes them to loguru sinks.
**When to use:** Installed by `configure_logging()` to bridge existing stdlib logging during migration.
**Example:**

```python
# Source: loguru official README + docs/resources/migration.md
import inspect
import logging

from loguru import logger


class InterceptHandler(logging.Handler):
    """Route stdlib logging records to loguru sinks."""

    def emit(self, record: logging.LogRecord) -> None:
        # Get corresponding loguru level
        try:
            level: str | int = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # Find caller from where the log originated
        frame, depth = inspect.currentframe(), 0
        while frame:
            filename = frame.f_code.co_filename
            is_logging = filename == logging.__file__
            is_frozen = "importlib" in filename and "_bootstrap" in filename
            if depth > 0 and not (is_logging or is_frozen):
                break
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )


def _install_intercept_handler() -> None:
    """Attach InterceptHandler to mcp_json_yaml_toml.* namespace loggers only."""
    handler = InterceptHandler()

    # Target the project namespace logger -- NOT the root logger
    ns_logger = logging.getLogger("mcp_json_yaml_toml")
    ns_logger.handlers = [handler]
    ns_logger.setLevel(logging.DEBUG)  # Let loguru handle filtering
    ns_logger.propagate = False        # Don't bubble to root
```

### Pattern 3: caplog Fixture Override in conftest.py

**What:** Override pytest's caplog fixture to route loguru output to caplog's handler.
**When to use:** Always active in test suite via conftest.py.
**Example:**

```python
# Source: loguru docs/resources/migration.md (Replacing caplog fixture)
# packages/mcp_json_yaml_toml/tests/conftest.py
import pytest
from _pytest.logging import LogCaptureFixture
from loguru import logger


@pytest.fixture
def caplog(caplog: LogCaptureFixture) -> Generator[LogCaptureFixture, None, None]:
    """Override caplog to capture loguru output.

    Routes loguru messages to pytest's caplog handler so that
    caplog.text, caplog.records, and caplog.at_level() work as expected.
    """
    handler_id = logger.add(
        caplog.handler,
        format="{message}",
        level=0,
        filter=lambda record: record["level"].no >= caplog.handler.level,
        enqueue=False,
    )
    yield caplog
    logger.remove(handler_id)
```

### Pattern 4: Auto-Configure on Module Import

**What:** Call `configure_logging()` from `__init__.py` so callers need zero setup.
**When to use:** Always -- makes logging work immediately on any import.
**Example:**

```python
# packages/mcp_json_yaml_toml/__init__.py
from mcp_json_yaml_toml.logging import configure_logging
configure_logging()
```

### Anti-Patterns to Avoid

- **Attaching InterceptHandler to root logger:** Captures ALL stdlib logging from every library (httpx, fastmcp, etc.), creating noise and potential recursion. Target only the `mcp_json_yaml_toml` namespace logger.
- **Using `logger.add(sys.stdout, ...)` anywhere:** stdout is the MCP JSON-RPC protocol channel. ANY log output to stdout will corrupt MCP communication. Always use stderr or file sinks.
- **Calling `logger.remove()` without re-adding in tests:** Leaves loguru with no handlers, silently dropping all log messages for the rest of the test session.
- **Using `diagnose=True` in production sinks:** Leaks local variable values in tracebacks, which could expose sensitive data (credentials, API keys).
- **Naming the module `logging.py` without careful import management:** The new module at `packages/mcp_json_yaml_toml/logging.py` shadows stdlib `logging` within the package. All internal imports of stdlib `logging` must use absolute path: `import logging` at module level before any relative imports, or the InterceptHandler itself must import stdlib logging carefully. This is handled by importing stdlib `logging` at the top of the new module before any loguru imports.

## Don't Hand-Roll

| Problem                | Don't Build             | Use Instead                                       | Why                                                                                                              |
| ---------------------- | ----------------------- | ------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------- |
| JSON log serialization | Custom JSON formatter   | `logger.add(..., serialize=True)`                 | Loguru's serialize handles all record fields, timestamps, exception formatting, thread safety                    |
| Log rotation           | Custom rotation logic   | `logger.add(..., rotation="10 MB", retention=5)`  | Loguru handles atomic rotation, retention cleanup, compression; hand-rolled rotation has race conditions         |
| Stdlib logging bridge  | Custom log dispatcher   | InterceptHandler pattern from loguru docs         | The frame-walking depth calculation is subtle; the official pattern handles importlib bootstrap frames correctly |
| caplog compatibility   | Custom test log capture | Official caplog override pattern from loguru docs | The filter lambda `record["level"].no >= caplog.handler.level` respects `caplog.at_level()` calls                |

**Key insight:** Loguru's `serialize=True` produces JSONL with all standard fields (timestamp, level, module, function, line, message, exception, extra) -- no custom serialization needed. The `configure()` and `add()` APIs handle rotation, retention, and thread safety internally.

## Common Pitfalls

### Pitfall 1: Module Name Shadowing

**What goes wrong:** Creating `logging.py` in the package shadows stdlib `logging`. Any module doing `import logging` within the package may import the project's `logging.py` instead of stdlib.
**Why it happens:** Python's import system resolves relative package imports before stdlib.
**How to avoid:** In the new `logging.py` module, import stdlib `logging` at the top of the file using its absolute name. All other modules in the package that need stdlib `logging` (during the migration period) should continue to work because they import `logging` before any intra-package imports. The `from __future__ import annotations` line is already standard in this codebase. Alternatively, if shadowing causes issues, the module can be named `log_config.py` instead -- but `logging.py` is the user's specified name from the success criteria ("new `logging.py` module").
**Warning signs:** `AttributeError: module 'mcp_json_yaml_toml.logging' has no attribute 'getLogger'` -- this means a module is importing the project's logging.py instead of stdlib.

**CRITICAL MITIGATION:** The InterceptHandler class itself uses `import logging` (stdlib). Since `logging.py` lives at `mcp_json_yaml_toml/logging.py`, the module must use `import logging as _stdlib_logging` or a similar alias at the very top of the file (before the loguru import) to capture the stdlib module reference before Python's import resolver could shadow it. Alternatively, naming the file `_logging.py` or `log_config.py` avoids the issue entirely. The planner should make an explicit decision here.

### Pitfall 2: caplog.at_level() with logger= Parameter

**What goes wrong:** Existing tests use `caplog.at_level("WARNING", logger="mcp_json_yaml_toml.backends.binary_manager")`. After Phase 9, this still works because the InterceptHandler bridges stdlib loggers to loguru. After Phase 10 (migration), the `logger=` parameter becomes meaningless because loguru has one global logger.
**Why it happens:** The `logger=` parameter in `caplog.at_level()` sets the level on a specific stdlib `logging.Logger` instance. Loguru has no concept of named loggers.
**How to avoid:** Phase 9 does NOT need to address this. The InterceptHandler keeps stdlib loggers working. Phase 10 tests will need to adjust assertions to use loguru's `record["name"]` field instead.
**Warning signs:** Tests passing in Phase 9 but failing after Phase 10 migration.

### Pitfall 3: File Sink During Tests

**What goes wrong:** If `configure_logging()` is called during test collection (via `__init__.py` import), it creates a JSONL file sink that writes to disk during every test run, slowing tests and leaving artifacts.
**Why it happens:** `configure_logging()` auto-runs on import, and tests import the package.
**How to avoid:** Detect test environment and skip file sink. Check for `_TESTING` environment variable or detect pytest. The user decision says "file sink disabled during tests." The recommended approach: set `MCP_JYT_LOG_FILE` to a sentinel value (e.g., `/dev/null` or empty string to disable) or use a conftest.py `autouse` fixture that calls `logger.remove()` before re-adding caplog handler. The conftest.py `propagate_logs` fixture from loguru docs handles this by removing all handlers and adding only test handlers.
**Warning signs:** `.jsonl` files appearing in test directories; slow test execution due to file I/O.

### Pitfall 4: Thread Safety with enqueue=True

**What goes wrong:** Using `enqueue=True` (async writing via internal queue) means log messages may not be flushed when the process exits abruptly.
**Why it happens:** The internal queue processes messages asynchronously. If the MCP server crashes, queued messages are lost.
**How to avoid:** Use `enqueue=True` for the file sink (throughput matters, occasional loss acceptable) but `enqueue=False` for stderr sink and test caplog handler (immediate delivery needed).
**Warning signs:** Missing log entries at end of log file after crashes.

### Pitfall 5: loguru Import Side Effects

**What goes wrong:** `from loguru import logger` immediately creates a default stderr handler. If `configure_logging()` hasn't run yet, any log call will write to stderr.
**Why it happens:** loguru auto-initializes with a stderr sink at DEBUG level on first import.
**How to avoid:** `configure_logging()` calls `logger.remove()` first to clear the default handler before adding configured sinks. Since `configure_logging()` is called from `__init__.py`, it runs before any module-level loguru usage.
**Warning signs:** Unexpected log output on stderr during startup.

## Code Examples

Verified patterns from official sources:

### JSONL File Sink with Rotation

```python
# Source: loguru docs (overview.md, API reference)
logger.add(
    "/path/to/server.jsonl",
    serialize=True,          # Outputs one JSON object per line
    rotation="10 MB",        # Rotate when file exceeds 10 MB
    retention=5,             # Keep 5 rotated files
    compression="gz",        # Optional: compress rotated files
    enqueue=True,            # Thread-safe async writing
    level="WARNING",         # Only WARNING and above
    diagnose=False,          # No variable leak in tracebacks
)
```

### Environment Variable Reading Pattern

```python
# Consistent with existing codebase (config.py uses os.environ.get)
import os
from pathlib import Path

level = os.environ.get("MCP_JYT_LOG_LEVEL", "WARNING").upper()
log_file_override = os.environ.get("MCP_JYT_LOG_FILE", "").strip()

if log_file_override:
    log_file = Path(log_file_override)
else:
    log_file = Path.home() / ".local" / "share" / "mcp-json-yaml-toml" / "logs" / "server.jsonl"
```

### Test Environment Detection for File Sink Suppression

```python
# Source: Best practice pattern for configure_logging() test safety
import os
import sys

def _is_testing() -> bool:
    """Detect if running under pytest."""
    return "pytest" in sys.modules or "PYTEST_CURRENT_TEST" in os.environ
```

### caplog Fixture Override (Complete)

```python
# Source: loguru docs/resources/migration.md
from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from loguru import logger

if TYPE_CHECKING:
    from collections.abc import Generator
    from _pytest.logging import LogCaptureFixture


@pytest.fixture
def caplog(caplog: LogCaptureFixture) -> Generator[LogCaptureFixture, None, None]:
    """Override caplog to capture loguru output."""
    handler_id = logger.add(
        caplog.handler,
        format="{message}",
        level=0,
        filter=lambda record: record["level"].no >= caplog.handler.level,
        enqueue=False,
    )
    yield caplog
    logger.remove(handler_id)
```

### Type Checking: loguru Logger Type Hint

```python
# Source: loguru docs/api/type_hints.md
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from loguru import Logger

def my_function(log: Logger) -> None:
    log.info("This is type-safe")
```

## State of the Art

| Old Approach                             | Current Approach                              | When Changed                | Impact                                                          |
| ---------------------------------------- | --------------------------------------------- | --------------------------- | --------------------------------------------------------------- |
| `logging.getLogger(__name__)` per module | `from loguru import logger` (single global)   | loguru 0.1.0 (2018)         | Eliminates per-module logger boilerplate                        |
| Custom JSON formatters                   | `logger.add(..., serialize=True)`             | loguru 0.3.0+               | Native JSONL serialization, no custom code                      |
| `pytest-loguru` plugin for caplog        | Inline fixture in conftest.py (official docs) | loguru docs, stable pattern | Zero extra dependency, full control                             |
| `loguru-mypy` plugin for type checking   | loguru built-in `.pyi` stubs                  | loguru 0.6.0+               | Built-in stubs work with mypy and pyright/basedpyright natively |

**Deprecated/outdated:**

- `loguru-mypy` plugin: Low maintenance activity; loguru's built-in stubs provide sufficient coverage. Only needed for advanced lazy-logging checks.
- `pytest-loguru` as dependency: Useful but unnecessary when using the official inline pattern (15 lines in conftest.py).

## Open Questions

1. **Module naming: `logging.py` vs alternative**
   - What we know: The success criteria reference "new `logging.py` module." However, `logging.py` shadows stdlib `logging` within the package, requiring careful import management.
   - What's unclear: Whether the shadowing will cause issues in practice during Phase 9 (where stdlib `logging` is still actively used by 3 modules via InterceptHandler).
   - Recommendation: Use `logging.py` as specified, but import stdlib `logging` at the very top of the file before any package-relative imports. If issues arise during implementation, fall back to `_logging.py`. The planner should include a verification step for this.

2. **`configure_logging()` auto-call timing**
   - What we know: User wants zero-setup -- `configure_logging()` called automatically on module import.
   - What's unclear: Whether importing `mcp_json_yaml_toml` during test collection triggers the file sink before the conftest caplog fixture can suppress it.
   - Recommendation: Use `_is_testing()` detection inside `configure_logging()` to skip the file sink when running under pytest. The caplog fixture then handles all test logging. The `propagate_logs` autouse fixture pattern from loguru docs (which removes all handlers) is the belt-and-suspenders approach.

3. **Rotation size and retention count (Claude's Discretion)**
   - Recommendation: 10 MB rotation, 5 retained files. This gives ~60 MB max disk usage. MCP servers are long-running but produce modest log volume at WARNING level. The user can override via `MCP_JYT_LOG_FILE` pointing to a custom path with different rotation managed externally.

## Sources

### Primary (HIGH confidence)

- `/delgan/loguru` via Context7 -- InterceptHandler pattern, caplog fixture override, `serialize=True` JSONL, `logger.configure()` API, type hints documentation
- [loguru official migration guide](https://loguru.readthedocs.io/en/stable/resources/migration.html) -- caplog fixture replacement, PropagateHandler, InterceptHandler, `%`-to-`{}` format migration
- [loguru type hints docs](https://loguru.readthedocs.io/en/stable/api/type_hints.html) -- PEP 484 stub file documentation, mypy compatibility verification

### Secondary (MEDIUM confidence)

- [pytest-loguru source](https://github.com/mcarans/pytest-loguru/blob/main/src/pytest_loguru/plugin.py) -- confirmed it's identical to official docs pattern (15 lines)
- [loguru PyPI](https://pypi.org/project/loguru/) -- version 0.7.3 confirmed as latest
- platformdirs 4.5.1 verified as installed transitive dependency via FastMCP

### Tertiary (LOW confidence)

- loguru-mypy maintenance status from web search -- described as inactive, needs validation if considering adoption

## Metadata

**Confidence breakdown:**

- Standard stack: HIGH -- loguru 0.7.3 is the clear choice (user locked decision), API verified via Context7 and official docs
- Architecture: HIGH -- InterceptHandler, caplog override, and configure_logging() patterns are well-documented and widely used; module shadowing risk is documented with mitigation
- Pitfalls: HIGH -- all pitfalls identified from official docs, verified migration guide, and codebase analysis of existing stdlib logging usage

**Research date:** 2026-02-18
**Valid until:** 2026-03-18 (stable -- loguru 0.7.x is mature, unlikely to change)

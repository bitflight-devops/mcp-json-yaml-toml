# Pitfalls Research

**Domain:** Loguru logging replacement and enhanced schema validation in MCP server
**Researched:** 2026-02-17
**Confidence:** HIGH (FastMCP logging internals verified against installed source; jsonschema iter_errors verified against official docs; loguru integration pitfalls verified against official issues and migration guide)

## Critical Pitfalls

### Pitfall 1: FastMCP 3.x Configures Its Own Logging -- Loguru InterceptHandler Will Fight It

**What goes wrong:**
FastMCP 3.x creates its own `logging.Logger` under the `fastmcp` namespace with `RichHandler` handlers and `propagate = False`. If loguru's `InterceptHandler` is installed on the root logger via `logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)`, it will either (a) not capture FastMCP's logs (because `propagate = False` prevents them from reaching the root logger) or (b) cause double logging if the InterceptHandler is added directly to FastMCP's logger alongside its existing RichHandler.

The installed FastMCP logging utility at `.venv/lib/python3.11/site-packages/fastmcp/utilities/logging.py` explicitly:

- Creates a `fastmcp` logger with `propagate = False` (line 57)
- Removes existing handlers before adding its own RichHandler (lines 61-62)
- Adds separate handlers for normal logs and tracebacks (lines 73-107)
- Reconfigures on every `configure_logging()` call, stripping any injected handlers

**Why it happens:**
FastMCP follows the correct library pattern (configure own namespace, don't touch root logger), but this means loguru's standard interception pattern cannot capture FastMCP internal logs without fighting FastMCP's handler management. Every time FastMCP reconfigures (which happens on server start and via `temporary_log_level` context manager), it strips handlers and re-adds its own.

**How to avoid:**
Do NOT intercept FastMCP's logger. Configure loguru only for the project's own loggers (`mcp_json_yaml_toml.*`). Leave FastMCP's `fastmcp` logger alone -- it already writes to stderr with RichHandler formatting. The interception approach should be:

```python
import logging
from loguru import logger

class InterceptHandler(logging.Handler):
    def emit(self, record):
        # Find caller from where the logged message originated
        level = logger.level(record.levelname).name
        frame, depth = logging.currentframe(), 2
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1
        logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())

# Only intercept our own loggers, NOT the root logger
for name in ["mcp_json_yaml_toml"]:
    stdlib_logger = logging.getLogger(name)
    stdlib_logger.handlers = [InterceptHandler()]
    stdlib_logger.propagate = False
```

**Warning signs:**

- Double-formatted log lines (one RichHandler format, one loguru format)
- FastMCP startup logs disappear entirely
- `temporary_log_level` context manager strips the InterceptHandler mid-request
- Test log output changes format between test setup and teardown

**Phase to address:**
Logging phase -- first implementation step. Establish the boundary: "our loggers" vs "FastMCP's loggers" before writing any code.

---

### Pitfall 2: Loguru Breaks pytest caplog Fixture -- 428 Existing Tests at Risk

**What goes wrong:**
pytest's `caplog` fixture works by adding a handler to the root stdlib logger. Loguru bypasses stdlib entirely -- it has its own sink system. After replacing `logging.getLogger(__name__)` with `from loguru import logger`, any test that uses `caplog` to assert log output will silently capture nothing. Tests that previously verified logging behavior (e.g., binary download progress, warning messages about wrong yq version) will pass vacuously -- the assertions on `caplog.text` or `caplog.records` return empty results, which may not fail the test if the assertions are conditional.

**Why it happens:**
Loguru and stdlib logging are separate systems. `caplog` hooks into stdlib's handler chain. Loguru messages never touch stdlib's handler chain unless explicitly propagated. This is the single most common migration pitfall documented in loguru's issue tracker (Issue #59, Issue #602).

**How to avoid:**
Override the `caplog` fixture in `conftest.py` to also capture loguru output:

```python
@pytest.fixture
def caplog(caplog):
    handler_id = logger.add(
        caplog.handler,
        format="{message}",
        level=0,
    )
    yield caplog
    logger.remove(handler_id)
```

Alternatively, use the `pytest-loguru` package which provides this fixture automatically. However, adding `pytest-loguru` is another dev dependency to evaluate.

**Warning signs:**

- Tests that assert on `caplog.text` or `caplog.records` pass but coverage drops (the log calls aren't exercised)
- `caplog.text == ""` in tests that previously had log output
- No test failures after the migration (suspicious -- means log assertions are too weak)

**Phase to address:**
Logging phase -- add the caplog fixture override BEFORE migrating any logger calls. Run the test suite to verify log capture still works, then proceed with the migration.

---

### Pitfall 3: Schema Validation Returns First Error Only -- AI Assistants Need All Errors

**What goes wrong:**
The current `_validate_against_schema()` in `services/schema_validation.py` calls `Draft7Validator(...).validate(data)` or `Draft202012Validator(...).validate(data)`, which raises `ValidationError` on the FIRST error encountered and stops. When an AI assistant sets multiple fields incorrectly, it gets one error, fixes it, calls the tool again, gets the next error, fixes it, and repeats. This creates a frustrating multi-round-trip correction cycle that wastes tokens and time.

**Why it happens:**
The jsonschema `.validate()` method is designed to fail fast. The library provides `iter_errors()` for collecting all errors, but it requires different calling patterns (instantiate the validator, call `iter_errors()`, iterate the results). The current code uses the fail-fast pattern because it was simpler to implement.

**How to avoid:**
Switch from `.validate()` to `.iter_errors()`:

```python
validator = Draft202012Validator(schema, registry=registry)
errors = sorted(validator.iter_errors(data), key=lambda e: list(e.absolute_path))
if errors:
    error_messages = []
    for error in errors:
        path = ".".join(str(p) for p in error.absolute_path) or "$"
        error_messages.append(f"  {error.json_path}: {error.message}")
    return False, f"Schema validation failed ({len(errors)} errors):\n" + "\n".join(error_messages)
```

The `json_path` attribute (available in jsonschema 4.x) provides RFC 9535 JSON Path notation that AI assistants can directly use to locate errors.

**Warning signs:**

- AI assistants make multiple sequential tool calls to fix one-error-at-a-time
- Schema validation response contains only one error when the document has many issues
- Users report "whack-a-mole" validation experience

**Phase to address:**
Schema validation phase -- this is the core feature improvement. Change the validation return type to include a list of all errors with their JSON paths.

---

### Pitfall 4: Pre-Write Validation Gate Can Cause Data Loss on Validation Failure Timing

**What goes wrong:**
The current `_validate_and_write_content()` in `mutation_operations.py` validates content THEN writes to disk. If validation fails, the write is skipped and the original file is preserved -- this is correct. However, the TOML write path in `_set_toml_value_handler()` calls `set_toml_value()` which reads the file, modifies the in-memory document, returns the modified string, and THEN calls `_validate_and_write_content()`. The file on disk is still the original. The danger arises if someone refactors to validate AFTER writing (e.g., for "optimistic write with rollback") -- a validation failure after write leaves the file in a modified-but-invalid state.

For yq operations, `in_place=False` means yq returns the modified content as stdout without touching the file. The validation gate works correctly here. But a future change to `in_place=True` (for performance) would bypass the validation gate entirely.

**Why it happens:**
The validation gate is a wrapper around file write, not a middleware in the mutation pipeline. Its placement depends on developer discipline, not architectural enforcement. There is no test that specifically verifies "file content on disk is unchanged after a failed validation."

**How to avoid:**

1. Add an explicit test: write a value that violates the schema, assert the file content on disk is identical to the original content before the operation.
2. Never use `in_place=True` for yq operations in the mutation path -- always dry-run to stdout, validate, then write.
3. Consider making the validation gate a decorator or context manager that wraps the entire mutation operation, making it impossible to skip.

**Warning signs:**

- File content changes on disk even though the response says "Schema validation failed"
- Tests that verify validation failure don't also verify file content unchanged
- Someone adds `in_place=True` to an `execute_yq()` call in the mutation path

**Phase to address:**
Schema validation phase -- add the atomicity test as a gate before enhancing the validation logic. The test should exist before any changes to the validation pipeline.

---

### Pitfall 5: Loguru Type Checking Incompatibility with mypy Strict Mode and basedpyright

**What goes wrong:**
The project runs both `mypy --strict` and `basedpyright` (basic mode). Loguru's `logger` is a singleton instance of type `loguru.Logger`, but the type information comes from `.pyi` stub files, not runtime code. Several patterns cause type checker complaints:

1. `logger.add(caplog.handler)` -- the handler parameter type may not satisfy mypy's strict checks
2. `from loguru import logger` -- basedpyright may flag the module-level singleton as having an incompatible type
3. `logger.opt(depth=depth, exception=record.exc_info).log(level, msg)` -- the chained method calls in the InterceptHandler involve complex overload resolution
4. The `loguru-mypy` plugin exists but may conflict with the ruff-managed type checking pipeline

The project's `pyproject.toml` enables `ANN` (flake8-annotations) rules in ruff, which require explicit type annotations on function parameters and returns. Functions that accept or return loguru's Logger type need the import to be available at type-checking time only (via `TYPE_CHECKING` guard), but the actual usage is at runtime.

**Why it happens:**
Loguru was designed for simplicity (`from loguru import logger` and go), but strict type checking environments demand precise type declarations. The stub file approach means type checkers see a different interface than runtime code. mypy strict mode flags any untyped usage, and basedpyright flags unclear types.

**How to avoid:**

1. Install `loguru-mypy` plugin and add it to `pyproject.toml` under `[tool.mypy] plugins = ["loguru-mypy"]`
2. For basedpyright, verify loguru's `.pyi` stubs are resolved correctly -- loguru ships with `py.typed` marker and stubs since 0.6.0
3. For the `InterceptHandler` class, explicitly annotate all methods to satisfy `ANN` rules
4. Use `TYPE_CHECKING` guard for Logger type imports:
   ```python
   from __future__ import annotations
   from typing import TYPE_CHECKING
   if TYPE_CHECKING:
       from loguru import Logger
   ```
5. Run both type checkers after adding loguru to verify zero new errors before proceeding with migration

**Warning signs:**

- `mypy` reports new errors after adding loguru dependency
- `basedpyright` reports `reportMissingImports` for loguru types
- `ruff` ANN rules flag loguru-related function signatures
- CI gate failures on type checking steps

**Phase to address:**
Logging phase -- add the loguru dependency and verify type checker compatibility BEFORE migrating any code. This is a gate: if type checkers cannot be satisfied, the migration approach needs adjustment.

---

### Pitfall 6: Loguru's Global Singleton Logger Breaks Test Isolation in pytest-xdist

**What goes wrong:**
The project uses `pytest-xdist` for parallel test execution (`-n auto` in pyproject.toml addopts). Loguru uses a global singleton `logger` with a shared sink list. When tests running in different xdist workers add/remove sinks (e.g., the `caplog` fixture override), they modify the global singleton in their respective worker processes. This is safe because xdist forks separate processes. However, if any test adds a sink with `enqueue=True` (async multiprocess logging), or if tests share state via `scope="session"` fixtures, the global singleton becomes a coordination problem.

More subtly: loguru's default sink (stderr, id=0) is present at import time. If one test calls `logger.remove()` (removing all sinks) and another test in the same worker expects the default sink to exist, the second test's log output disappears. Unlike stdlib logging, where `getLogger(__name__)` creates independent loggers per module, loguru has exactly one logger with one sink list.

**Why it happens:**
Loguru's design philosophy is "one logger, many sinks" rather than stdlib's "many loggers, many handlers." This is simpler for application code but creates shared mutable state in test environments. The `conftest.py` fixture that overrides `caplog` must carefully `logger.add()` and `logger.remove()` without disturbing sinks other tests depend on.

**How to avoid:**

1. Never call `logger.remove()` without arguments (removes ALL sinks) in fixture code -- always remove specific sink IDs
2. Store the sink ID from `logger.add()` and remove only that ID in fixture teardown
3. Do NOT add `enqueue=True` to any sink in the test environment
4. If a test needs a clean logger state, use `logger.remove()` followed by `logger.add(sys.stderr)` in a fixture with function scope, ensuring cleanup restores the previous state

```python
@pytest.fixture(autouse=True)
def _loguru_caplog_handler(caplog):
    handler_id = logger.add(
        caplog.handler,
        format="{message}",
        level=0,
    )
    yield
    logger.remove(handler_id)  # Remove ONLY this handler, not all handlers
```

**Warning signs:**

- Intermittent test failures in CI but not locally (worker process ordering differs)
- Log output from one test appears in another test's captured output
- `caplog.text` is empty in some test runs but populated in others
- Tests pass with `-n 0` (no parallelism) but fail with `-n auto`

**Phase to address:**
Logging phase -- design the test fixture strategy before migrating logger calls. Verify parallel test execution works with the caplog override.

---

### Pitfall 7: Enhanced Validation Error Messages Change the API Contract

**What goes wrong:**
The current `_validate_against_schema()` returns `(False, "Schema validation failed: {e.message}")` -- a tuple of `(bool, str)`. The string contains a single error message. Existing code in `mutation_operations.py` wraps this in `ToolError(f"Schema validation failed: {msg}")`. MCP clients (AI assistants) may parse the error message to extract the validation failure reason. If the format changes from a single-line message to a multi-line list of errors with JSON paths, any client-side parsing breaks.

More critically: the `ValidationResponse` model in `responses.py` has `schema_message: str | None` -- a single string field. Returning multiple errors requires either changing this field to a list (breaking change) or encoding all errors in a formatted string (preserves the type but changes the content format).

**Why it happens:**
Schema validation error format is an implicit API contract. The MCP protocol transports tool results as text content. AI assistants learn to parse error messages through few-shot examples in their context. Changing the error format invalidates their learned parsing patterns.

**How to avoid:**

1. Keep the `(bool, str)` return signature for backward compatibility
2. Add a new optional field `validation_errors: list[dict] | None` to `ValidationResponse` for structured error data
3. The `str` message should have a summary line (`"Schema validation failed (3 errors)"`) followed by individual errors -- this preserves the pattern where the first line is the summary
4. Add the `json_path` to each error in the structured field, not in the message string
5. Test that existing error message parsing patterns still work (e.g., `msg.startswith("Schema validation failed:")`)

**Warning signs:**

- AI assistants start misinterpreting validation errors after the change
- Client-side error handling that parsed the old format breaks
- Tests that assert exact error message strings fail

**Phase to address:**
Schema validation phase -- design the response format change as an additive enhancement (new field) rather than a breaking change (modified field).

---

## Technical Debt Patterns

Shortcuts that seem reasonable but create long-term problems.

| Shortcut                                                        | Immediate Benefit                     | Long-term Cost                                                                             | When Acceptable                                                                     |
| --------------------------------------------------------------- | ------------------------------------- | ------------------------------------------------------------------------------------------ | ----------------------------------------------------------------------------------- |
| Using `logging.basicConfig(force=True)` for loguru interception | Quick setup, intercepts everything    | Conflicts with FastMCP's logging, breaks other library loggers                             | Never in this project -- use targeted logger interception                           |
| Keeping `(bool, str)` return type for validation                | No API change needed                  | Cannot add structured error data; consumers must parse strings                             | Acceptable as transition -- add new return type alongside                           |
| Adding loguru as a required dependency (not optional)           | Simpler imports, no conditional logic | Increases install size for users who don't need structured logging; loguru is ~400KB       | Acceptable -- loguru is lightweight and the server is an application, not a library |
| Validating only the changed subtree instead of full document    | Faster validation for large files     | May miss cross-field validation rules (e.g., `dependencies` keyword in JSON Schema)        | Never -- always validate the full document                                          |
| Suppressing loguru type errors with `# type: ignore`            | Unblocks migration quickly            | Masks real type issues; violates project linting philosophy (CLAUDE.md: "Fix root causes") | Never -- fix type stubs/plugins instead                                             |

## Integration Gotchas

Common mistakes when connecting loguru and enhanced validation to existing systems.

| Integration                    | Common Mistake                                                                                     | Correct Approach                                                                                 |
| ------------------------------ | -------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------ |
| FastMCP logging namespace      | Installing InterceptHandler on root logger, disrupting FastMCP's RichHandler                       | Intercept only `mcp_json_yaml_toml.*` loggers; leave `fastmcp.*` untouched                       |
| pytest caplog                  | Forgetting to add loguru sink to caplog handler                                                    | Override `caplog` fixture in conftest.py to bridge loguru to caplog                              |
| pytest-xdist parallel workers  | Calling `logger.remove()` globally, removing sinks for other tests                                 | Track sink IDs; remove only the specific sink added by each fixture                              |
| jsonschema iter_errors         | Catching `ValidationError` instead of iterating -- `iter_errors()` returns an iterator, not raises | Call `list(validator.iter_errors(data))` or iterate; do not use try/except                       |
| jsonschema json_path attribute | Assuming `error.path` gives JSON Path notation                                                     | Use `error.json_path` (RFC 9535 format like `$.foo.bar[0]`), not `error.path` (deque of keys)    |
| MCP error message format       | Returning multi-line errors that confuse LLM parsing                                               | First line is summary; subsequent lines are details; preserve "Schema validation failed:" prefix |
| loguru serialization           | Using `serialize=True` sink option in production MCP server                                        | MCP stdio transport uses stdout for JSON-RPC; loguru MUST write to stderr, never stdout          |

## Performance Traps

Patterns that work at small scale but fail as usage grows.

| Trap                                                                           | Symptoms                                                                 | Prevention                                                                                              | When It Breaks                                                                       |
| ------------------------------------------------------------------------------ | ------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------ |
| Collecting ALL validation errors on deeply nested schemas with `anyOf`/`oneOf` | Validation takes seconds instead of milliseconds; error list is enormous | Set a `max_errors` limit (e.g., 20); use `by_relevance` sorting to surface important errors first       | Schemas with >50 `anyOf` alternatives (e.g., GitHub Actions workflow schema)         |
| Loguru structured logging with `serialize=True` on every log call              | JSON serialization overhead per log message; stdout pollution            | Use `serialize=True` only on specific sinks (e.g., file sink for log aggregation), not default stderr   | >1000 tool calls/minute with verbose logging enabled                                 |
| Schema re-parsing on every validation call                                     | Schema file read + yq parse + validator construction per validation      | Cache parsed schema objects keyed by file path + mtime                                                  | Burst mutations to the same file (e.g., AI assistant setting 10 fields sequentially) |
| Building JSON paths for all errors in large documents                          | String concatenation and path traversal for thousands of errors          | Use `error.json_path` attribute directly (pre-computed by jsonschema); don't reconstruct paths manually | Documents with >10,000 nodes failing validation                                      |

## Security Mistakes

Domain-specific security issues beyond general web security.

| Mistake                                            | Risk                                                                                                                         | Prevention                                                                                                                                              |
| -------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Loguru writing to stdout instead of stderr         | MCP stdio transport uses stdout for JSON-RPC messages; log output corrupts the protocol stream, causing client disconnection | Configure loguru sinks to write ONLY to stderr: `logger.add(sys.stderr, ...)`. Remove default sink first: `logger.remove(0)` then add stderr explicitly |
| Logging file content or schema data at DEBUG level | Sensitive configuration data (passwords, API keys) appears in log output                                                     | Never log file content; log file paths and operation types only. Set production log level to INFO minimum                                               |
| Validation error messages leaking schema structure | Schema URLs and internal structure visible to MCP clients                                                                    | Error messages should describe what's wrong with the data, not expose schema internals. Redact `$ref` URLs and schema paths from error messages         |

## UX Pitfalls

Common user experience mistakes in this domain.

| Pitfall                                     | User Impact                                               | Better Approach                                                                      |
| ------------------------------------------- | --------------------------------------------------------- | ------------------------------------------------------------------------------------ |
| Returning 50+ validation errors at once     | Overwhelms the AI assistant context window; wastes tokens | Cap at 10-20 most relevant errors using `jsonschema.exceptions.by_relevance` sorting |
| Including JSON path and message only        | AI assistant knows WHERE and WHAT but not HOW to fix      | Include the expected type/value from the schema alongside the error message          |
| Changing log format mid-stream              | Users monitoring stderr see inconsistent output           | Establish log format once at startup; never reconfigure during server lifetime       |
| Validation errors not grouped by path depth | Top-level and deeply nested errors interleaved            | Sort errors by `absolute_path` length -- top-level errors first, nested errors after |

## "Looks Done But Isn't" Checklist

Things that appear complete but are missing critical pieces.

- [ ] **Loguru migration:** Often missing caplog fixture override -- verify `caplog.text` still captures logs in at least 3 test files that previously asserted on log output
- [ ] **Loguru migration:** Often missing stderr-only configuration -- verify zero loguru output reaches stdout by running the server and capturing stdout separately from stderr
- [ ] **Loguru migration:** Often missing type checker verification -- run both `mypy` and `basedpyright` after adding loguru dependency, before migrating any code
- [ ] **Schema validation enhancement:** Often missing backward-compatible error format -- verify old error message prefix `"Schema validation failed:"` still present
- [ ] **Schema validation enhancement:** Often missing `max_errors` cap -- verify behavior with a document that has 1000+ errors (e.g., empty object against a schema with 50 required fields)
- [ ] **Pre-write validation gate:** Often missing atomicity test -- verify file on disk is UNCHANGED after a validation failure in both TOML and YAML/JSON paths
- [ ] **Pre-write validation gate:** Often missing test for `in_place=False` invariant -- verify no `execute_yq()` call in mutation path uses `in_place=True`
- [ ] **Validation response model:** Often missing `validation_errors` field in `ValidationResponse` -- verify the new field is optional and existing consumers work without it

## Recovery Strategies

When pitfalls occur despite prevention, how to recover.

| Pitfall                                                    | Recovery Cost | Recovery Steps                                                                                                                                                                                                          |
| ---------------------------------------------------------- | ------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| FastMCP logging disrupted by root InterceptHandler         | LOW           | Remove `logging.basicConfig(force=True)` call; switch to targeted logger interception; redeploy                                                                                                                         |
| caplog tests silently passing with empty results           | MEDIUM        | Add `caplog` fixture override; re-run tests verifying log assertions are non-vacuous; may need to update test assertions that were secretly broken                                                                      |
| Validation error format change breaks AI assistant parsing | LOW           | The old `schema_message` string field should still contain a human-readable summary; if the format changed, restore the `"Schema validation failed: {first_error}"` prefix and move details to the new structured field |
| Loguru output corrupts MCP stdio transport                 | HIGH          | Immediate fix: add `logger.remove(0)` and `logger.add(sys.stderr)` at startup. If logs have been going to stdout, clients experienced disconnections and lost work. Requires hotfix release                             |
| File modified despite validation failure                   | HIGH          | Cannot recover automatically -- user file was modified with invalid content. The test gap allowed a code path where write precedes validation. Add the atomicity test, fix the code path, notify affected users         |
| Type checker failures blocking CI                          | LOW           | Pin loguru version; add `loguru-mypy` plugin; if basedpyright still fails, add targeted `# pyright: ignore` comments with inline explanations (not blanket suppression)                                                 |

## Pitfall-to-Phase Mapping

How roadmap phases should address these pitfalls.

| Pitfall                       | Prevention Phase                    | Verification                                                                                                  |
| ----------------------------- | ----------------------------------- | ------------------------------------------------------------------------------------------------------------- |
| FastMCP logging conflict      | Logging setup (first step)          | Verify FastMCP startup logs still appear in stderr with RichHandler format after loguru is configured         |
| caplog fixture breakage       | Logging setup (before migration)    | Run full test suite; verify `caplog.text` is non-empty in tests that assert on log output                     |
| pytest-xdist sink isolation   | Logging setup (fixture design)      | Run `uv run pytest -n auto` 5 times; verify zero intermittent failures                                        |
| Type checker incompatibility  | Logging setup (dependency addition) | Run `uv run mypy packages/` and `uv run basedpyright packages/` with loguru installed but no code changes     |
| First-error-only validation   | Schema validation (core change)     | New test: validate document with 5 known errors; assert response contains all 5                               |
| Pre-write atomicity gap       | Schema validation (test-first)      | New test: attempt SET that violates schema; assert file bytes unchanged                                       |
| API contract breakage         | Schema validation (response design) | Verify `"Schema validation failed:"` prefix preserved; new `validation_errors` field is `None` when no schema |
| stdout corruption from loguru | Logging setup (sink configuration)  | Integration test: spawn MCP server, send tool call, verify JSON-RPC response is valid JSON on stdout          |
| Error message overwhelming AI | Schema validation (UX)              | Cap errors at 20; sort by relevance; include fix hints                                                        |

## Sources

- [FastMCP logging utility source](https://github.com/jlowin/fastmcp/blob/main/src/fastmcp/utilities/logging.py) -- HIGH confidence, verified against installed package at `.venv/lib/python3.11/site-packages/fastmcp/utilities/logging.py`
- [FastMCP Issue #1656: FastMCP configures logging on init](https://github.com/modelcontextprotocol/python-sdk/issues/1656) -- HIGH confidence, official issue tracker
- [FastMCP Issue #909: Running FastMCP() overwrites global logging configuration](https://github.com/modelcontextprotocol/python-sdk/issues/909) -- HIGH confidence, official issue tracker
- [Loguru Issue #59: pytest caplog fixture doesn't work](https://github.com/Delgan/loguru/issues/59) -- HIGH confidence, official issue with documented workaround
- [Loguru Issue #78: Proper way to intercept stdlib logging](https://github.com/Delgan/loguru/issues/78) -- HIGH confidence, official recommended pattern
- [Loguru Issue #247: Intercepting logging logs](https://github.com/Delgan/loguru/issues/247) -- HIGH confidence, documents double-logging pitfall
- [Loguru migration guide](https://loguru.readthedocs.io/en/stable/resources/migration.html) -- HIGH confidence, official documentation
- [Loguru type hints documentation](https://loguru.readthedocs.io/en/stable/api/type_hints.html) -- HIGH confidence, official documentation
- [jsonschema error handling docs](https://python-jsonschema.readthedocs.io/en/stable/errors/) -- HIGH confidence, official documentation for `iter_errors`, `json_path`, `by_relevance`
- [jsonschema validation docs](https://python-jsonschema.readthedocs.io/en/latest/validate/) -- HIGH confidence, official documentation
- [pytest-loguru PyPI](https://pypi.org/project/pytest-loguru/) -- MEDIUM confidence, third-party plugin

---

_Pitfalls research for: Loguru logging replacement and enhanced schema validation (mcp-json-yaml-toml)_
_Researched: 2026-02-17_

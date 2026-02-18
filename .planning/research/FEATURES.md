# Feature Research

**Domain:** Loguru logging replacement and enhanced schema validation for MCP JSON/YAML/TOML server
**Researched:** 2026-02-17
**Confidence:** HIGH (verified against installed jsonschema 4.26.x source code and official loguru documentation)

## Current State Inventory

### Logging (stdlib)

The server uses Python stdlib `logging` in three modules:

| Module                       | Usage                                                                                                   |
| ---------------------------- | ------------------------------------------------------------------------------------------------------- |
| `backends/binary_manager.py` | `logging.getLogger(__name__)` with `.info()`, `.debug()`, `.warning()` for yq binary download lifecycle |
| `schemas/manager.py`         | `logging.debug()` for schema config loading failures                                                    |
| `schemas/scanning.py`        | `logging.debug()` for IDE pattern loading failures                                                      |

Total: 3 files with `import logging`, ~15 log call sites. No structured data, no JSON output, no context binding. All messages are positional `%s` format strings.

### Schema Validation (current)

The `_validate_against_schema()` function in `services/schema_validation.py`:

- Uses `Draft7Validator.validate()` or `Draft202012Validator.validate()` (single-call)
- `.validate()` raises on the **first** `ValidationError` only
- Catches `ValidationError` and returns `(False, f"Schema validation failed: {e.message}")`
- Returns a plain string message with no JSON path, no validator keyword, no error count
- No support for collecting all errors

### Pre-Write Validation (partially exists)

The `_validate_and_write_content()` function in `services/mutation_operations.py`:

- Already gates writes behind schema validation when a `schema_path` is available
- Calls `_validate_against_schema()` before `path.write_text()`
- Returns ToolError on failure with the single error message
- **Gap**: No `skip_validation` parameter exposed to tool callers
- **Gap**: Only validates schema, not syntax (syntax is implicitly validated by yq/tomlkit parse)
- **Gap**: Returns only first error, not all errors

GH#1 (open issue) requests: pre-write syntax + schema validation pipeline, atomic operations, `skip_validation` opt-out parameter.

## Feature Landscape

### Table Stakes (Users Expect These)

Features that users of a schema-validating MCP server and well-instrumented Python service assume exist. Missing these makes the product feel incomplete.

| Feature                               | Why Expected                                                                                                                                                                                                 | Complexity | Dependencies                                                                                                                                        |
| ------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ---------- | --------------------------------------------------------------------------------------------------------------------------------------------------- |
| **All-errors schema validation**      | Returning only the first error forces repeated fix-validate cycles. Every IDE, linter, and CI tool reports all errors at once.                                                                               | LOW        | Already installed: `jsonschema>=4.26.0` has `iter_errors()`. Zero new deps.                                                                         |
| **JSON path in validation errors**    | Users need to know WHERE the error is, not just WHAT failed. Every modern validator (ajv, jsonschema-rs, IDE validators) reports paths.                                                                      | LOW        | Already available: `ValidationError.json_path` property exists in installed jsonschema (verified in source). Returns `$.foo.bar[0]` format.         |
| **Validator keyword in error output** | Knowing the keyword (`type`, `required`, `minimum`, `additionalProperties`) tells the caller what kind of fix is needed.                                                                                     | LOW        | Already available: `ValidationError.validator` attribute on every error object.                                                                     |
| **Pre-write validation gate (GH#1)**  | Writing invalid data to config files is the primary risk of a CRUD MCP server. Validation before write is table stakes for data integrity.                                                                   | LOW        | Infrastructure already exists in `_validate_and_write_content()`. Needs: syntax validation step, all-errors reporting, `skip_validation` parameter. |
| **Structured logging (loguru)**       | stdlib logging provides no structured output, no automatic context binding, no serialized JSON format. Production MCP servers need structured, parseable logs for debugging tool calls and binary downloads. | MEDIUM     | New dependency: `loguru>=0.7.3`. Requires InterceptHandler for stdlib compatibility (FastMCP and other deps use stdlib logging).                    |

### Differentiators (Competitive Advantage)

Features that go beyond what users minimally expect. These add value but are not blocking if deferred.

| Feature                                 | Value Proposition                                                                                                                                                                                              | Complexity | Dependencies                                                                                        |
| --------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------- | --------------------------------------------------------------------------------------------------- |
| **Structured validation error objects** | Return errors as typed dicts/Pydantic models with `json_path`, `validator`, `validator_value`, `message`, `schema_path` fields instead of formatted strings. Enables programmatic error handling by AI agents. | LOW        | Pydantic already in deps (via FastMCP). jsonschema error attributes already available.              |
| **best_match error ranking**            | `jsonschema.exceptions.best_match()` identifies the most relevant error from a set. Return both best match (for quick display) and all errors (for complete picture).                                          | LOW        | Already in jsonschema. `best_match(validator.iter_errors(instance))` is a one-liner.                |
| **Contextual logging with bind()**      | Loguru `bind()` attaches operation context (file_path, format, tool_name) to all downstream log calls. Enables filtering/searching logs by file or operation.                                                  | LOW        | Requires loguru. Pattern: `logger.bind(file=path, op="set").info(...)`                              |
| **JSON-serialized log output**          | Loguru `serialize=True` produces JSONL output. Machine-parseable for log aggregation (Grafana Loki, ELK, CloudWatch). Complements existing OpenTelemetry traces.                                               | LOW        | Requires loguru. Configuration-only: `logger.add(sink, serialize=True)`.                            |
| **skip_validation parameter**           | Allow callers to bypass pre-write validation when intentionally fixing invalid files. Without this, the validation gate becomes a trap for repair operations.                                                  | LOW        | Pure parameter threading from `data()` tool through dispatch to `_validate_and_write_content()`.    |
| **Syntax validation before write**      | Explicitly re-parse modified content (JSON/YAML/TOML) before writing to catch cases where yq expression produces syntactically invalid output. Belt-and-suspenders safety.                                     | LOW        | Already have parsers: yq for JSON/YAML, tomlkit for TOML. Re-parse the content string before write. |

### Anti-Features (Explicitly Do NOT Build)

Features to avoid in this milestone. Building these would add complexity without proportional value.

| Anti-Feature                                | Why Avoid                                                                                                                                                                                           | What to Do Instead                                                                                 |
| ------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------- |
| **Custom logging framework**                | Loguru already solves structured logging, context binding, and stdlib interception. Rolling a custom solution is wasted effort.                                                                     | Use loguru as-is with InterceptHandler for stdlib compatibility.                                   |
| **JSON Schema error auto-fix suggestions**  | Generating fix suggestions from validation errors is complex, error-prone, and varies wildly by schema. AI agents can interpret the structured errors themselves.                                   | Return rich structured errors with json_path + validator keyword. Let the AI agent decide the fix. |
| **Async/streaming validation**              | Schema validation of config files is sub-millisecond. Async adds complexity with zero user-visible benefit for typical file sizes (<1MB).                                                           | Keep synchronous validation. Only revisit if profiling shows a bottleneck.                         |
| **Custom log sinks for specific services**  | Building Grafana/ELK/CloudWatch sinks couples the server to specific infrastructure.                                                                                                                | Output JSONL via loguru `serialize=True`. Let the deployment environment handle log routing.       |
| **Replacing jsonschema with jsonschema-rs** | jsonschema-rs (Rust-based) is faster but has a different API. The current jsonschema library is adequate for config file sizes and already installed. Migration risk outweighs marginal speed gain. | Keep python-jsonschema. Validate performance with profiling first.                                 |
| **Log file rotation management**            | The MCP server is a short-lived process per invocation (stdio transport). Log rotation is meaningless for the typical deployment model.                                                             | Use stderr output. Let the host process (Claude Desktop, IDE) manage log capture.                  |

## Feature Dependencies

```
                    loguru installation
                           |
                    +------+------+
                    |             |
            InterceptHandler   logger.bind()
            (stdlib compat)    (context)
                    |             |
                    +------+------+
                           |
                  Structured logging operational
                           |
                  JSON serialization (serialize=True)


            iter_errors() change
                    |
            +-------+-------+
            |               |
    All-errors reporting   JSON path extraction
            |               |
            +-------+-------+
                    |
          Structured error objects
            (Pydantic models)
                    |
          +--------+--------+
          |                 |
    best_match ranking   Pre-write validation
                         (GH#1 complete)
                              |
                    skip_validation parameter
```

Key ordering constraints:

1. `loguru` must be installed before any logging changes (obvious but critical -- don't partially migrate)
2. `InterceptHandler` must be configured before removing stdlib logging calls (FastMCP, httpx, and other deps emit stdlib logs)
3. `iter_errors()` change is prerequisite for all-errors reporting and structured error objects
4. Structured error objects should be defined before updating pre-write validation to use them
5. `skip_validation` depends on pre-write validation being fully implemented first

## Detailed Feature Specifications

### 1. All-Errors Schema Validation

**Current behavior** (verified in codebase):

```python
# services/schema_validation.py line 74-80
Draft202012Validator(schema, registry=registry).validate(data)
# ...
except ValidationError as e:
    return False, f"Schema validation failed: {e.message}"
```

`.validate()` raises on first error. Only `e.message` (string) is captured.

**Target behavior** (verified against installed jsonschema source):

```python
validator = Draft202012Validator(schema, registry=registry)
errors = sorted(validator.iter_errors(data), key=lambda e: list(e.absolute_path))
# Each error has: .json_path, .validator, .validator_value, .message, .schema_path, .instance
```

`iter_errors()` returns a generator of ALL `ValidationError` objects. Each has rich attributes.

**Verified attributes** (tested against jsonschema 4.26.x in this repo's venv):

| Attribute         | Type              | Example Value                                    | Purpose                              |
| ----------------- | ----------------- | ------------------------------------------------ | ------------------------------------ |
| `json_path`       | `str`             | `$.tags[1]`                                      | JSONPath to failing instance element |
| `validator`       | `str`             | `type`, `required`, `minimum`                    | Failed keyword name                  |
| `validator_value` | `Any`             | `"string"`, `["name"]`, `0`                      | Expected value for the keyword       |
| `message`         | `str`             | `42 is not of type 'string'`                     | Human-readable description           |
| `absolute_path`   | `deque[str\|int]` | `deque(['tags', 1])`                             | Path components for sorting          |
| `schema_path`     | `deque[str\|int]` | `deque(['properties', 'tags', 'items', 'type'])` | Path within schema                   |

**Confidence:** HIGH -- tested with `uv run python` in this repo's venv. 4 errors returned for a test instance with type violations, missing required fields, additional properties, and minimum violations.

### 2. Structured Validation Error Response

**Current return type**: `tuple[bool, str]` -- a boolean and a plain message string.

**Target return type**: A structured object that the tool response can include directly.

Proposed error structure per error:

```python
{
    "json_path": "$.tags[1]",
    "validator": "type",
    "validator_value": "string",
    "message": "42 is not of type 'string'",
    "schema_path": "properties.tags.items.type"
}
```

Proposed validation result:

```python
{
    "valid": False,
    "error_count": 4,
    "best_match": { ... },  # Most relevant error via best_match()
    "errors": [ ... ],      # All errors sorted by path
}
```

This replaces the `(bool, str)` return with a richer dict/Pydantic model.

### 3. Loguru Replacement

**Scope of change**: 3 files with stdlib logging, ~15 call sites.

**InterceptHandler requirement**: FastMCP, httpx, and other dependencies use stdlib logging internally. The InterceptHandler routes their messages through loguru so all log output is unified.

**Standard InterceptHandler pattern** (from loguru official docs):

```python
import logging
from loguru import logger

class InterceptHandler(logging.Handler):
    def emit(self, record):
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno
        frame, depth = logging.currentframe(), 2
        while frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1
        logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())

logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)
```

**Migration steps per file**:

1. Replace `import logging` with `from loguru import logger`
2. Replace `logger = logging.getLogger(__name__)` with nothing (loguru has single global logger)
3. Replace `logger.info("msg %s", arg)` with `logger.info("msg {}", arg)` (loguru uses `{}` format)
4. Add `.bind(context_key=value)` where context is useful (e.g., `logger.bind(binary=binary_name)`)

**Production safety**: Set `diagnose=False` in production to prevent leaking sensitive data in tracebacks. Loguru's `diagnose=True` (default) shows local variable values in exceptions.

**Confidence:** HIGH -- loguru 0.7.3 is stable, supports Python 3.11+, the InterceptHandler pattern is well-documented.

### 4. Pre-Write Validation Gate (GH#1)

**Current state** (verified in codebase):

The `_validate_and_write_content()` function in `services/mutation_operations.py` already:

- Accepts `schema_path: Path | None`
- Validates content against schema before writing
- Raises `ToolError` on validation failure
- Writes to file only after validation passes

**What's missing** (per GH#1 analysis):

1. **Syntax validation step**: The content string should be re-parsed to verify syntax before writing. Currently, if yq produces invalid output, it gets written to disk.
2. **All-errors reporting**: Uses `_validate_against_schema()` which returns first error only.
3. **`skip_validation` parameter**: No way to bypass validation for repair operations.
4. **Explicit syntax validation in response**: The `data_schema(action="validate")` tool checks syntax and schema separately, but the write path does not report syntax status independently.

**Implementation approach**:

- Add syntax validation: re-parse content with the appropriate parser (json.loads for JSON, ruamel.yaml for YAML, tomlkit.parse for TOML) before schema validation
- Wire in all-errors `_validate_against_schema()` (from feature #1 above)
- Thread `skip_validation: bool = False` from `data()` tool through dispatch to `_validate_and_write_content()`
- Return structured validation errors in the ToolError message when validation fails

## MVP Recommendation

Prioritize in this order:

1. **All-errors schema validation + JSON paths + validator keywords** -- Highest impact, lowest effort. Changes one function (`_validate_against_schema`). Uses existing library capabilities already verified in the venv.

2. **Structured validation error objects** -- Direct consumer of #1. Define a Pydantic model or TypedDict for validation errors. Changes the return type of `_validate_against_schema` and updates its callers.

3. **Pre-write validation gate completion (GH#1)** -- Builds on #1 and #2. Add syntax validation step, wire through `skip_validation` parameter, update `_validate_and_write_content()` to use structured errors.

4. **Loguru replacement** -- Independent of validation features. Can be done in parallel but is medium complexity due to InterceptHandler setup and ensuring no stdlib logging calls are missed.

Defer:

- **JSON serialized log output**: Configuration-only after loguru is in place. Not worth a separate phase.
- **best_match ranking**: One-liner addition after all-errors is working. Bundle with #2.

## Sources

**Verified against installed source code:**

- jsonschema `ValidationError.json_path` property: `/home/ubuntulinuxqa2/repos/mcp-json-yaml-toml/.venv/lib/python3.11/site-packages/jsonschema/exceptions.py` lines 152-163
- jsonschema `iter_errors` method: verified via `uv run python` against installed jsonschema 4.26.x
- Current validation implementation: `packages/mcp_json_yaml_toml/services/schema_validation.py`
- Current pre-write validation: `packages/mcp_json_yaml_toml/services/mutation_operations.py`
- GH#1 issue: `gh issue view 1` -- pre-write syntax and schema validation for CRUD operations

**Official documentation:**

- [jsonschema Handling Validation Errors (stable)](https://python-jsonschema.readthedocs.io/en/stable/errors/) -- iter_errors, best_match, ValidationError attributes
- [jsonschema Handling Validation Errors (latest)](https://python-jsonschema.readthedocs.io/en/latest/errors/) -- json_path property documentation
- [loguru Overview](https://loguru.readthedocs.io/en/stable/overview.html?highlight=intercept+stdlib) -- InterceptHandler pattern, structured logging
- [loguru Migration Guide](https://loguru.readthedocs.io/en/stable/resources/migration.html) -- stdlib to loguru migration
- [loguru API Reference](https://loguru.readthedocs.io/en/stable/api/logger.html) -- bind(), serialize, diagnose parameters
- [loguru PyPI](https://pypi.org/project/loguru/) -- version 0.7.3, Python >=3.5,<4.0
- [loguru GitHub](https://github.com/Delgan/loguru) -- InterceptHandler reference implementation
- [loguru Issue #78](https://github.com/Delgan/loguru/issues/78) -- canonical InterceptHandler discussion
- [Production Loguru Guide (Dash0)](https://www.dash0.com/guides/python-logging-with-loguru) -- production best practices, diagnose=False

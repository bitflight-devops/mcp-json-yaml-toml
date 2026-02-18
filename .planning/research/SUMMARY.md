# Research Summary: Loguru Logging + Enhanced Schema Validation

**Domain:** MCP server instrumentation and schema validation improvements
**Researched:** 2026-02-17
**Overall confidence:** HIGH

## Executive Summary

This research covers two independent feature areas for a subsequent milestone on the mcp-json-yaml-toml server: replacing stdlib logging with loguru structured logging, and enhancing JSON Schema validation to report all errors with JSON path locations.

The loguru replacement requires adding a single new runtime dependency (`loguru>=0.7.3`) and migrating 3 files with ~18 stdlib logging call sites. The critical integration challenge is FastMCP's independent logging configuration -- FastMCP creates its own `fastmcp` logger namespace with `propagate=False` and `RichHandler` on stderr. The standard loguru InterceptHandler pattern (intercepting the root logger) will NOT capture FastMCP logs and may cause conflicts. The correct approach is targeted interception of only the project's own `mcp_json_yaml_toml` namespace, leaving FastMCP's logging untouched.

The schema validation enhancement requires zero new dependencies. The installed `jsonschema>=4.26.0` already provides `iter_errors()` for collecting all validation errors, `ValidationError.json_path` for RFC 9535 JSON Path notation (e.g., `$.database.port`), and `best_match()` for identifying the most relevant error. All of these were verified by direct execution against the installed package in the project's virtual environment. The implementation changes exactly one core function (`_validate_against_schema`) and updates two callers.

Both features are independent -- they can be built in parallel or either order. However, implementing loguru first provides structured logging for debugging the schema validation changes.

## Key Findings

**Stack:** Add `loguru>=0.7.3` as the sole new runtime dependency. Zero new dependencies for schema validation -- `jsonschema 4.26.0` already has `iter_errors()`, `json_path`, and `best_match()`.

**Architecture:** New `logging.py` module for centralized loguru configuration. Modified `_validate_against_schema()` returning `ValidationResult` dataclass instead of `tuple[bool, str]`. Two callers updated. No architectural changes -- features slot into existing layered structure.

**Critical pitfall:** FastMCP's logging system fights the standard loguru InterceptHandler. FastMCP sets `propagate=False` on its logger and strips injected handlers on reconfiguration. Intercept only the project's own loggers, not the root logger.

## Implications for Roadmap

Based on research, suggested phase structure for this milestone:

1. **Phase 1: Logging Infrastructure** - Create `logging.py` with InterceptHandler and `configure_logging()`. Add loguru dependency. Verify type checkers pass.
   - Addresses: Centralized logging foundation
   - Avoids: FastMCP logging conflict (targeted interception, not root interception)

2. **Phase 2: Stdlib Logging Migration** - Replace `import logging` in 3 files with `from loguru import logger`. Update format strings from `%s` to `{}`.
   - Addresses: Unified structured logging across all modules
   - Avoids: caplog fixture breakage (add loguru-caplog bridge in conftest.py first)

3. **Phase 3: Schema Validation Models** - Create `SchemaValidationError` and `ValidationResult` dataclasses. Update `ValidationResponse` model.
   - Addresses: Structured error output foundation
   - Avoids: API contract breakage (`.message` property preserves backward compatibility)

4. **Phase 4: Enhanced Validation Logic** - Replace `validate()` with `iter_errors()` in `_validate_against_schema()`. Update callers in mutation_operations.py and tools/schema.py.
   - Addresses: All-errors reporting, JSON path in errors, pre-write validation enhancement
   - Avoids: Error message overwhelming (cap at 20 errors, sort by relevance)

**Phase ordering rationale:**

- Phases 1-2 (logging) and Phases 3-4 (schema validation) are independent tracks
- Phase 1 before Phase 2: InterceptHandler must be configured before removing stdlib logging
- Phase 3 before Phase 4: ValidationResult model must exist before the function can return it
- Both tracks can run in parallel

**Research flags for phases:**

- All phases: Standard patterns, no deep research needed
- Phase 1: Verify type checker compatibility after adding loguru dependency (gate)
- Phase 2: Verify caplog fixture override before migrating any logger calls (gate)
- Phase 4: Verify max_errors behavior with deeply nested schemas containing anyOf/oneOf (edge case)

## Confidence Assessment

| Area         | Confidence | Notes                                                                                                                                                                                    |
| ------------ | ---------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Stack        | HIGH       | loguru 0.7.3 verified on PyPI. jsonschema 4.26.0 capabilities verified by direct execution in project venv.                                                                              |
| Features     | HIGH       | All jsonschema APIs (`iter_errors`, `json_path`, `best_match`) tested live. loguru InterceptHandler pattern documented in official issues.                                               |
| Architecture | HIGH       | All modified files identified by codebase analysis. Component boundaries are clear. 2 callers of `_validate_against_schema` confirmed.                                                   |
| Pitfalls     | HIGH       | FastMCP logging internals verified against installed source code. caplog incompatibility documented in loguru Issue #59. Pre-write atomicity verified by reading mutation_operations.py. |

## Gaps to Address

- **Ruff G rules interaction with loguru:** Ruff's G001-G202 rules target stdlib logging format. loguru uses `{}` format syntax. The project already ignores most G rules (only G201/G202 enabled). Verify these don't false-positive on loguru calls during implementation. LOW priority.
- **loguru-mypy plugin decision:** The plugin is effectively unmaintained but loguru's built-in stubs work. If mypy reports issues, consider adding the plugin as a dev dependency. Verify during Phase 1 type checker gate. LOW priority.
- **max_errors cap for deeply nested schemas:** Schemas with many `anyOf`/`oneOf` alternatives (e.g., GitHub Actions workflows) can produce hundreds of errors. A cap at 20 errors is recommended but the exact number should be tuned during implementation. MEDIUM priority.
- **caplog fixture testing with pytest-xdist:** The project runs tests with `-n auto`. The loguru caplog override must be safe for parallel execution. Verify by running full test suite 3 times with `-n auto` after adding the fixture. MEDIUM priority.

## Sources

- [loguru PyPI](https://pypi.org/project/loguru/) -- version 0.7.3 confirmed
- [loguru documentation](https://loguru.readthedocs.io/) -- InterceptHandler, serialize, bind
- [loguru GitHub Issue #78](https://github.com/Delgan/loguru/issues/78) -- canonical InterceptHandler pattern
- [loguru GitHub Issue #59](https://github.com/Delgan/loguru/issues/59) -- pytest caplog incompatibility
- [loguru-mypy GitHub](https://github.com/kornicameister/loguru-mypy) -- maintenance status
- [jsonschema error handling](https://python-jsonschema.readthedocs.io/en/latest/errors/) -- iter_errors, best_match, json_path
- [jsonschema exceptions API](https://python-jsonschema.readthedocs.io/en/stable/api/jsonschema/exceptions/) -- ValidationError attributes
- [FastMCP logging source](https://gofastmcp.com/python-sdk/fastmcp-utilities-logging) -- stdlib logging + RichHandler
- FastMCP installed source (`fastmcp/utilities/logging.py`) -- propagate=False, handler stripping confirmed
- Direct execution in project venv -- all jsonschema API capabilities verified

---

_Research completed: 2026-02-17_
_Ready for roadmap: yes_

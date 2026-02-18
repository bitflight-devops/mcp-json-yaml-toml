# Requirements: mcp-json-yaml-toml

**Defined:** 2026-02-17
**Core Value:** AI assistants can safely read and modify structured configuration files without destroying formatting, comments, or file structure.

## M3 Requirements

Requirements for M3 Logging & Validation milestone. Each maps to roadmap phases.

### Logging

- [ ] **LOG-01**: Application uses loguru for all logging (replaces stdlib logging in 3 files, ~18 call sites)
- [x] **LOG-02**: Centralized logging configuration via `logging.py` module with `configure_logging()`
- [x] **LOG-03**: InterceptHandler captures project-namespace stdlib loggers (`mcp_json_yaml_toml.*`) and routes to loguru
- [ ] **LOG-04**: FastMCP LoggingMiddleware added for MCP request/response protocol logging
- [ ] **LOG-05**: pytest caplog fixture overridden in conftest.py for loguru compatibility
- [x] **LOG-06**: All logging writes to stderr only (MCP stdout protocol safety)

### Schema Validation

- [ ] **SCHV-01**: Schema validation reports all errors (not first-only) using `iter_errors()`
- [ ] **SCHV-02**: Each validation error includes JSON path (RFC 9535), validator keyword, and expected value
- [ ] **SCHV-03**: Structured `ValidationResult` model replaces `tuple[bool, str]` return type
- [ ] **SCHV-04**: Backward-compatible `.message` property preserves existing string format
- [ ] **SCHV-05**: Pre-write validation gate validates syntax and schema before writing to disk (GH#1)
- [ ] **SCHV-06**: `skip_validation` parameter available on CRUD operations to bypass validation gate

## Future Requirements

### Multi-Document YAML (GH#6)

- **YAML-01**: Parse and query multi-document YAML files
- **YAML-02**: Edit individual documents within multi-document files
- **YAML-03**: Per-document schema validation for multi-document files

## Out of Scope

| Feature                            | Reason                                                                          |
| ---------------------------------- | ------------------------------------------------------------------------------- |
| JSON serialization sink for loguru | Human-readable logging sufficient for now; JSON sinks are a config change later |
| loguru-mypy plugin                 | Unmaintained; loguru's built-in stubs work with mypy and basedpyright           |
| Root logger interception           | FastMCP uses `propagate=False`; intercepting root logger causes conflicts       |
| Custom log levels                  | Standard levels (DEBUG/INFO/WARNING/ERROR/CRITICAL) sufficient                  |

## Traceability

| Requirement | Phase    | Status   |
| ----------- | -------- | -------- |
| LOG-01      | Phase 10 | Pending  |
| LOG-02      | Phase 9  | Complete |
| LOG-03      | Phase 9  | Complete |
| LOG-04      | Phase 10 | Pending  |
| LOG-05      | Phase 9  | Pending  |
| LOG-06      | Phase 9  | Complete |
| SCHV-01     | Phase 11 | Pending  |
| SCHV-02     | Phase 11 | Pending  |
| SCHV-03     | Phase 11 | Pending  |
| SCHV-04     | Phase 11 | Pending  |
| SCHV-05     | Phase 12 | Pending  |
| SCHV-06     | Phase 12 | Pending  |

**Coverage:**

- M3 requirements: 12 total
- Mapped to phases: 12
- Unmapped: 0

---

_Requirements defined: 2026-02-17_
_Last updated: 2026-02-17 after roadmap creation_

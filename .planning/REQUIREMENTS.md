# Requirements: mcp-json-yaml-toml

**Defined:** 2026-02-14
**Core Value:** AI assistants can safely read and modify structured configuration files without destroying formatting, comments, or file structure.

## v1 Requirements

Requirements for this milestone. Each maps to roadmap phases.

### Architecture

- [x] **ARCH-01**: Extract pagination utilities from server.py into dedicated module
- [x] **ARCH-02**: Extract format detection and value parsing from server.py into dedicated module
- [x] **ARCH-03**: Decouple yq binary lifecycle management from query execution in yq_wrapper.py
- [x] **ARCH-04**: Create backend abstraction layer with pluggable execution engine interface
- [x] **ARCH-05**: Reduce server.py to tool registration and dispatch only

### FastMCP

- [x] **FMCP-01**: Migrate from FastMCP 2.x to FastMCP 3.x with all tests passing
- [x] **FMCP-02**: Leverage automatic threadpool for sync yq subprocess calls
- [x] **FMCP-03**: Add tool timeout support for long-running operations
- [x] **FMCP-04**: Create Pydantic response models for all tool outputs (structured output)
- [x] **FMCP-05**: Add complete tool annotations (readOnlyHint, destructiveHint, idempotentHint) to all tools

### Safety

- [x] **SAFE-01**: Pin ruamel.yaml to >=0.18.0,<0.19 to prevent 0.19 deployment failures
- [x] **SAFE-02**: Upgrade JSON Schema default validator to Draft 2020-12

### Features

- [ ] **FEAT-01**: Add config file diff tool to compare two configuration files
- [ ] **FEAT-02**: Add OpenTelemetry instrumentation for monitoring and debugging

## v2 Requirements

Deferred to future release. Tracked but not in current roadmap.

### Backend Evolution

- **BACK-01**: Evaluate pure-Python execution backend (jmespath + existing libs) to eliminate yq binary entirely
- **BACK-02**: Implement native Python query execution for simple path traversal patterns
- **BACK-03**: Tool versioning support via FastMCP 3.x capabilities

### Protocol

- **PROT-01**: Elicitation support for interactive user prompts
- **PROT-02**: Async task primitives for long-running operations
- **PROT-03**: Multi-file query support (query across multiple config files)

## Out of Scope

| Feature                                 | Reason                                                                                        |
| --------------------------------------- | --------------------------------------------------------------------------------------------- |
| Switch from yq to dasel                 | Dasel destroys YAML/TOML comments on write and expands anchors — violates core differentiator |
| Rewrite in non-Python language          | Python ecosystem constraint; existing architecture is sound                                   |
| Change existing MCP tool names          | Production clients depend on data, data_query, data_schema, data_convert, data_merge          |
| Native MCP from CLI tools               | yq/dasel are stateless CLI tools with no protocol awareness — Python wrapper IS the server    |
| New file format support (XML, CSV, INI) | Not the focus of this milestone                                                               |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase   | Status  |
| ----------- | ------- | ------- |
| ARCH-01     | Phase 1 | Done    |
| ARCH-02     | Phase 1 | Done    |
| ARCH-03     | Phase 1 | Done    |
| ARCH-04     | Phase 1 | Done    |
| SAFE-01     | Phase 1 | Done    |
| ARCH-05     | Phase 2 | Done    |
| FMCP-04     | Phase 2 | Done    |
| FMCP-05     | Phase 2 | Done    |
| FMCP-01     | Phase 3 | Done    |
| FMCP-02     | Phase 3 | Done    |
| FMCP-03     | Phase 3 | Done    |
| SAFE-02     | Phase 3 | Done    |
| FEAT-01     | Phase 4 | Pending |
| FEAT-02     | Phase 4 | Pending |

**Coverage:**

- v1 requirements: 14 total
- Mapped to phases: 14
- Unmapped: 0

---

_Requirements defined: 2026-02-14_
_Last updated: 2026-02-14 after Phase 2 completion_

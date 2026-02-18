# Roadmap: mcp-json-yaml-toml

## Milestones

- ✅ **v1.0 Layered Architecture** — Phases 1-4 (shipped 2026-02-14)
- ✅ **v1.1 Internal Quality** — Phases 5-8 (shipped 2026-02-17)
- 🚧 **M3 Logging & Validation** — Phases 9-12 (in progress)

## Phases

<details>
<summary>✅ v1.0 Layered Architecture (Phases 1-4) — SHIPPED 2026-02-14</summary>

- [x] Phase 1: Architectural Foundation (4/4 plans) — completed 2026-02-14
- [x] Phase 2: Tool Layer Refactoring (4/4 plans) — completed 2026-02-14
- [x] Phase 3: FastMCP 3.x Migration (2/2 plans) — completed 2026-02-14
- [x] Phase 4: Feature Integration (2/2 plans) — completed 2026-02-14

Full details: [milestones/v1.1-ROADMAP.md](milestones/v1.1-ROADMAP.md)

</details>

<details>
<summary>✅ v1.1 Internal Quality (Phases 5-8) — SHIPPED 2026-02-17</summary>

- [x] Phase 5: Type Safety and DRY Foundation (2/2 plans) — completed 2026-02-15
- [x] Phase 6: Operational Safety (2/2 plans) — completed 2026-02-15
- [x] Phase 7: Architecture Refactoring (2/2 plans) — completed 2026-02-15
- [x] Phase 8: Test Quality (2/2 plans) — completed 2026-02-17

Full details: [milestones/v1.1-ROADMAP.md](milestones/v1.1-ROADMAP.md)

</details>

### M3 Logging & Validation (In Progress)

- [ ] **Phase 9: Logging Infrastructure** - loguru dependency, centralized configuration, InterceptHandler, caplog fixture, stderr safety
- [ ] **Phase 10: Logger Migration** - Replace stdlib logging across codebase, add FastMCP LoggingMiddleware
- [ ] **Phase 11: Validation Models & Logic** - ValidationResult model, backward compat, all-errors reporting with JSON paths
- [ ] **Phase 12: Pre-Write Validation Gate** - Syntax and schema validation before CRUD writes, skip_validation parameter

## Phase Details

### Phase 9: Logging Infrastructure

**Goal**: Loguru is installed, configured, and test-safe -- all infrastructure exists for module-by-module migration
**Depends on**: Phase 8 (v1.1 complete)
**Requirements**: LOG-02, LOG-03, LOG-05, LOG-06
**Success Criteria** (what must be TRUE):

1. `configure_logging()` from new `logging.py` module configures loguru with stderr-only output
2. InterceptHandler captures `mcp_json_yaml_toml.*` namespace stdlib loggers and routes them to loguru (not root logger)
3. `mypy` and `basedpyright` pass cleanly after adding loguru dependency
4. pytest caplog fixture works with loguru -- existing tests that use caplog continue to pass
   **Plans**: 2 plans

Plans:

- [ ] 09-01-PLAN.md -- Install loguru, create logging.py with configure_logging() and InterceptHandler, wire **init**.py, verify type checkers
- [ ] 09-02-PLAN.md -- Override caplog fixture in conftest.py for loguru compatibility, run full quality gate

### Phase 10: Logger Migration

**Goal**: Every logging call in the codebase uses loguru -- stdlib logging fully replaced
**Depends on**: Phase 9
**Requirements**: LOG-01, LOG-04
**Success Criteria** (what must be TRUE):

1. All 3 files with stdlib logging (`import logging`) are migrated to `from loguru import logger` with `{}` format strings
2. FastMCP LoggingMiddleware is configured and logs MCP request/response protocol events
3. Full test suite passes with `-n auto` (parallel safety verified)
   **Plans**: TBD

Plans:

- [ ] 10-01: TBD

### Phase 11: Validation Models & Logic

**Goal**: Schema validation reports all errors with JSON paths and structured output while preserving backward compatibility
**Depends on**: Phase 8 (independent of logging track; can run in parallel with Phases 9-10)
**Requirements**: SCHV-01, SCHV-02, SCHV-03, SCHV-04
**Success Criteria** (what must be TRUE):

1. `ValidationResult` model exists and replaces `tuple[bool, str]` return type from `_validate_against_schema()`
2. Validation collects all errors via `iter_errors()` (not first-only via `validate()`)
3. Each validation error includes JSON path (RFC 9535 `$.database.port` format), validator keyword, and expected value
4. Backward-compatible `.message` property on ValidationResult produces the same string format existing callers expect
5. Both callers of `_validate_against_schema()` updated to use ValidationResult
   **Plans**: TBD

Plans:

- [ ] 11-01: TBD
- [ ] 11-02: TBD

### Phase 12: Pre-Write Validation Gate

**Goal**: CRUD write operations validate syntax and schema before touching disk, with an escape hatch for callers who need to bypass
**Depends on**: Phase 11
**Requirements**: SCHV-05, SCHV-06
**Success Criteria** (what must be TRUE):

1. CRUD operations that write to disk (create, update, delete) validate content against syntax rules and applicable schema before writing
2. Invalid content is rejected with structured error output before any file modification occurs
3. `skip_validation` parameter is available on CRUD operations to bypass the validation gate
   **Plans**: TBD

Plans:

- [ ] 12-01: TBD

## Progress

**Execution Order:**
Phases 9-10 (logging) and 11-12 (validation) are independent tracks. Within each track, phases are sequential.

| Phase                             | Milestone | Plans Complete | Status      | Completed  |
| --------------------------------- | --------- | -------------- | ----------- | ---------- |
| 1. Architectural Foundation       | v1.0      | 4/4            | Complete    | 2026-02-14 |
| 2. Tool Layer Refactoring         | v1.0      | 4/4            | Complete    | 2026-02-14 |
| 3. FastMCP 3.x Migration          | v1.0      | 2/2            | Complete    | 2026-02-14 |
| 4. Feature Integration            | v1.0      | 1/1            | Complete    | 2026-02-14 |
| 5. Type Safety and DRY Foundation | v1.1      | 2/2            | Complete    | 2026-02-15 |
| 6. Operational Safety             | v1.1      | 2/2            | Complete    | 2026-02-15 |
| 7. Architecture Refactoring       | v1.1      | 2/2            | Complete    | 2026-02-15 |
| 8. Test Quality                   | v1.1      | 2/2            | Complete    | 2026-02-17 |
| 9. Logging Infrastructure         | M3        | 0/?            | Not started | -          |
| 10. Logger Migration              | M3        | 0/?            | Not started | -          |
| 11. Validation Models & Logic     | M3        | 0/?            | Not started | -          |
| 12. Pre-Write Validation Gate     | M3        | 0/?            | Not started | -          |

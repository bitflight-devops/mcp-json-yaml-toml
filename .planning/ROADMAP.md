# Roadmap: mcp-json-yaml-toml

## Milestones

- ✅ **v1.0 Layered Architecture** - Phases 1-4 (shipped 2026-02-14)
- 🚧 **v1.1 Internal Quality** - Phases 5-8 (in progress)

## Phases

<details>
<summary>✅ v1.0 Layered Architecture (Phases 1-4) - SHIPPED 2026-02-14</summary>

### Phase 1: Architectural Foundation

**Goal**: Extract core execution layer and establish service boundaries
**Plans**: 4 plans

Plans:

- [x] 01-01: Architecture extraction validation
- [x] 01-02: Pydantic migration for response models
- [x] 01-03: Monolithic server split
- [x] 01-04: Tool handler extraction

### Phase 2: Tool Layer Refactoring

**Goal**: Standardize tool layer with type safety and timeouts
**Plans**: 2 plans

Plans:

- [x] 02-01: Tool timeout defaults and Pydantic schema integration
- [x] 02-02: Unified service injection and error handling

### Phase 3: FastMCP 3.x Migration

**Goal**: Upgrade to FastMCP 3.x structured output with type validation
**Plans**: 2 plans

Plans:

- [x] 03-01: FastMCP 3.x framework upgrade and tool configuration
- [x] 03-02: Backward compatibility layer for DictAccessMixin

### Phase 4: Feature Integration

**Goal**: Ship config diffing and observability capabilities
**Plans**: 1 plan

Plans:

- [x] 04-01: data_diff implementation and OpenTelemetry integration

</details>

### 🚧 v1.1 Internal Quality (In Progress)

**Milestone Goal:** Remediate code review findings — eliminate systemic quality issues, refactor god modules, and improve test standards.

#### Phase 5: Type Safety and DRY Foundation

**Goal**: Establish type safety baseline and eliminate duplicate patterns
**Depends on**: Phase 4
**Requirements**: TYPE-01, TYPE-02, TYPE-03, DRY-01, DRY-02, DRY-03
**Success Criteria** (what must be TRUE):

1. All service handler functions return typed Pydantic models instead of dict[str, Any]
2. Format type checks use FormatType enum consistently across all modules
3. Exception handling uses specific exception types with targeted recovery actions
4. Format-enable checks execute through single shared function (no duplicate implementations)
5. File path resolution and TOML fallback logic extracted to shared utilities
   **Plans**: TBD

Plans:

- [ ] 05-01: DRY utility extraction (require_format_enabled, resolve_file_path, TOML fallback, navigate_to_parent)
- [ ] 05-02: Type safety (Pydantic returns, FormatType enum consistency, specific exception catches)

#### Phase 6: Operational Safety

**Goal**: Replace print() debugging with proper logging and add configuration caching
**Depends on**: Phase 5
**Requirements**: OPS-01, OPS-02, OPS-03, OPS-04
**Success Criteria** (what must be TRUE):

1. binary_manager.py emits structured log records instead of print() to stderr
2. config.py caches parsed environment configuration (no repeated parsing)
3. yaml_optimizer.py validates environment input instead of crashing at import
4. logging.debug() uses lazy %-formatting throughout codebase

**Plans**: 2 plans

Plans:

- [ ] 06-01: binary_manager.py print() to logging migration
- [ ] 06-02: Config caching, env validation, lazy log formatting

#### Phase 7: Architecture Refactoring

**Goal**: Split god modules and migrate off deprecated import shim
**Depends on**: Phase 6
**Requirements**: ARCH-06, ARCH-07, ARCH-08, ARCH-09, ARCH-10
**Success Criteria** (what must be TRUE):

1. data_operations.py split into focused service modules (get, mutation, query)
2. schemas.py split into focused sub-modules (loading, IDE cache, scanning)
3. Production code imports from backends modules instead of yq_wrapper.py shim
4. server.py **all** contains only public API symbols
5. Tools accept schema_manager as parameter instead of using module singleton
   **Plans**: 2 plans

Plans:

- [ ] 07-01: data_operations.py split and yq_wrapper import migration
- [ ] 07-02: schemas.py split, server.py **all** cleanup, schema_manager parameterization

#### Phase 8: Test Quality

**Goal**: Standardize test patterns and add edge case coverage
**Depends on**: Phase 7
**Requirements**: TEST-01, TEST-02, TEST-03, TEST-04, TEST-05
**Success Criteria** (what must be TRUE):

1. Tests verify behavior through public API (no private method testing)
2. Test names follow behavioral pattern (test_what_when_condition_then_outcome)
3. Edge cases covered: permissions, malformed input, resource cleanup
4. Repetitive test data converted to parameterized tests
5. verify_features.py test_hints() contains proper assertions
   **Plans**: TBD

Plans:

- [ ] 08-01: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 5 → 6 → 7 → 8

| Phase                             | Milestone | Plans Complete | Status      | Completed  |
| --------------------------------- | --------- | -------------- | ----------- | ---------- |
| 1. Architectural Foundation       | v1.0      | 4/4            | Complete    | 2026-02-14 |
| 2. Tool Layer Refactoring         | v1.0      | 2/2            | Complete    | 2026-02-14 |
| 3. FastMCP 3.x Migration          | v1.0      | 2/2            | Complete    | 2026-02-14 |
| 4. Feature Integration            | v1.0      | 1/1            | Complete    | 2026-02-14 |
| 5. Type Safety and DRY Foundation | v1.1      | 0/TBD          | Not started | -          |
| 6. Operational Safety             | v1.1      | 0/TBD          | Not started | -          |
| 7. Architecture Refactoring       | v1.1      | 0/TBD          | Not started | -          |
| 8. Test Quality                   | v1.1      | 0/TBD          | Not started | -          |

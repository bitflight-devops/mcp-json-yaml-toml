# Roadmap: mcp-json-yaml-toml

## Overview

This roadmap transforms a production MCP server from architectural technical debt (1880-line god module) into a maintainable, extensible system. The journey progresses from extracting backend abstraction and utilities, through tool layer refactoring and Pydantic response models, to FastMCP 3.x migration unlocking automatic threadpool and structured output, concluding with competitive features (config diffing and observability). The architecture refactoring happens on FastMCP 2.x to reduce migration risk, then upgrades to FastMCP 3.x with a smaller migration surface.

## Phases

**Phase Numbering:**

- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Architectural Foundation** - Extract backend abstraction, utilities, and format handlers (2026-02-14)
- [x] **Phase 2: Tool Layer Refactoring** - Split server.py into thin tool decorators with Pydantic models (2026-02-14)
- [x] **Phase 3: FastMCP 3.x Migration** - Upgrade framework and adopt new capabilities (2026-02-15)
- [ ] **Phase 4: Competitive Features** - Add config diffing and OpenTelemetry observability

## Phase Details

### Phase 1: Architectural Foundation

**Goal**: Reduce server.py complexity by extracting backend abstraction, pagination utilities, and format handlers into dedicated modules
**Depends on**: Nothing (first phase)
**Requirements**: ARCH-01, ARCH-02, ARCH-03, ARCH-04, SAFE-01
**Success Criteria** (what must be TRUE):

1. Pagination logic exists in dedicated services/pagination.py module (no longer scattered in server.py)
2. Format detection and value parsing exist in formats/base.py (extracted from server.py)
3. yq binary lifecycle management is decoupled from query execution (backends/binary_manager.py exists)
4. QueryBackend protocol exists with YqBackend implementation (enables future backend swaps)
5. All existing tests pass without modification (behavior preserved)

**Plans:** 4 plans

Plans:

- [x] 01-01-PLAN.md -- Foundation types, QueryBackend protocol, and SAFE-01 ruamel.yaml pin
- [x] 01-02-PLAN.md -- Extract pagination logic into services/pagination.py
- [x] 01-03-PLAN.md -- Extract binary manager and yq backend, convert yq_wrapper.py to shim
- [x] 01-04-PLAN.md -- Extract format detection into formats/base.py, full verification gate

### Phase 2: Tool Layer Refactoring

**Goal**: Reduce server.py to tool registration and dispatch only, with all business logic delegated to services and complete tool annotations
**Depends on**: Phase 1
**Requirements**: ARCH-05, FMCP-04, FMCP-05
**Success Criteria** (what must be TRUE):

1. server.py contains only FastMCP initialization and tool registration imports (under 100 lines)
2. Each tool exists as thin decorator in tools/ directory (data.py, query.py, schema.py, convert.py, constraints.py)
3. All tool return types use Pydantic response models (foundation for structured output in Phase 3)
4. All tools have complete annotations (readOnlyHint, destructiveHint, idempotentHint where applicable)
5. Existing tool names unchanged (data, data_query, data_schema, data_convert, data_merge remain stable)

**Plans:** 4 plans

Plans:

- [x] 02-01-PLAN.md -- Response models and schema validation service extraction
- [x] 02-02-PLAN.md -- Data operations service layer extraction
- [x] 02-03-PLAN.md -- Tool layer split into tools/ directory
- [x] 02-04-PLAN.md -- Pydantic return types and complete tool annotations

### Phase 3: FastMCP 3.x Migration

**Goal**: Upgrade to FastMCP 3.x unlocking automatic threadpool, tool timeouts, and structured output
**Depends on**: Phase 2
**Requirements**: FMCP-01, FMCP-02, FMCP-03, SAFE-02
**Success Criteria** (what must be TRUE):

1. pyproject.toml pins fastmcp>=3.0.0,<4 and all tests pass on FastMCP 3.x
2. yq subprocess calls execute via automatic threadpool (no manual executor required)
3. Long-running tools have timeout protection (timeout parameter set on decorators)
4. All tools return structured output (outputSchema auto-generated from Pydantic models)
5. JSON Schema validator defaults to Draft 2020-12 (upgraded from Draft 7)

**Plans:** 2 plans

Plans:

- [x] 03-01-PLAN.md -- FastMCP 3.x dependency upgrade and import compatibility (FMCP-01, FMCP-02)
- [x] 03-02-PLAN.md -- Tool timeouts, Draft 2020-12 default, and outputSchema verification (FMCP-03, SAFE-02)

### Phase 4: Competitive Features

**Goal**: Add high-value differentiators with low implementation cost (config diffing and observability)
**Depends on**: Phase 3
**Requirements**: FEAT-01, FEAT-02
**Success Criteria** (what must be TRUE):

1. data_diff tool exists and returns structured diff between two configuration files
2. Users can compare config files of different formats (e.g., JSON vs YAML)
3. OpenTelemetry instrumentation is configured and operational
4. Server operations emit traces to configured OTLP endpoint
   **Plans**: TBD

Plans:

- [ ] TBD - Will be defined during `/gsd:plan-phase 4`

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4

| Phase                       | Plans Complete | Status      | Completed  |
| --------------------------- | -------------- | ----------- | ---------- |
| 1. Architectural Foundation | 4/4            | ✓ Complete  | 2026-02-14 |
| 2. Tool Layer Refactoring   | 4/4            | ✓ Complete  | 2026-02-14 |
| 3. FastMCP 3.x Migration    | 2/2            | ✓ Complete  | 2026-02-15 |
| 4. Competitive Features     | 0/TBD          | Not started | -          |

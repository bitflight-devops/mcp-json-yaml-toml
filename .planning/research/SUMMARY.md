# Project Research Summary

**Project:** mcp-json-yaml-toml MCP server upgrade/enhancement
**Domain:** MCP server for structured data manipulation (JSON/YAML/TOML)
**Researched:** 2026-02-14
**Confidence:** MEDIUM-HIGH

## Executive Summary

This project is an MCP server providing advanced structured data manipulation for JSON, YAML, and TOML files through a unified query interface. The research reveals a mature codebase with strong format preservation capabilities but significant architectural technical debt (1880-line server.py god module, 934-line binary wrapper) and a critical decision point: FastMCP 3.x upgrade and potential backend migration.

The recommended approach is phased architectural refactoring followed by selective feature enhancement. Priority 1 is extracting backend abstraction and splitting the god module into a layered architecture (tools/, services/, backends/, formats/) while maintaining format preservation as the core differentiator. Priority 2 is upgrading to FastMCP 3.x when stable (currently 3.0.0rc2), unlocking automatic threadpool execution, tool timeouts, and structured output. The dasel backend evaluation shows it destroys YAML/TOML comments on write — a dealbreaker that eliminates backend migration as viable. Stay with yq for query/read operations and maintain ruamel.yaml/tomlkit for write operations.

Key risks are comment/anchor destruction during any write-path refactoring, breaking existing client tool names, and expression syntax incompatibility if backend changes are attempted. Mitigation centers on format preservation test gates, tool name stability contracts, and keeping the abstraction layer while maintaining yq as the backend. The architecture research provides a clear six-phase build order with independent deliverables and test gates.

## Key Findings

### Recommended Stack

The current stack is sound and should be maintained with selective upgrades. FastMCP 3.x (when stable) is the only significant upgrade needed. The dasel backend switch is explicitly NOT recommended due to comment preservation failures.

**Core technologies:**

- **FastMCP 2.14.4 → 3.0.0 (when stable):** MCP framework — v3 adds automatic threadpool for sync tools (eliminates subprocess blocking), tool timeouts, component versioning, and structured output support
- **yq (mikefarah) v4.52.2:** Query backend — jq-compatible syntax well-understood by LLMs, mature, stable. Do NOT replace with dasel.
- **ruamel.yaml >=0.18.0,<0.19:** YAML write operations — only Python library preserving comments and anchors. Pin <0.19 to avoid build issues.
- **tomlkit >=0.14.0:** TOML write operations — preserves comments, formatting, and ordering. Required because yq cannot write TOML.
- **orjson >=3.11.6:** JSON parsing — 3-10x faster than stdlib, already in dependencies

**Supporting decisions:**

- Reject dasel as backend (destroys comments/anchors on write)
- Defer pure Python backend to Phase 2 evaluation (requires expression translation layer)
- Maintain binary management pattern (download/verify/cache) for yq
- Keep dual-library write path (ruamel.yaml for YAML, tomlkit for TOML) as correct architecture

### Expected Features

Current server ships 7 tools (data, data_query, data_schema, data_convert, data_merge, constraint_validate, constraint_list) with strong capabilities but incomplete MCP spec compliance and missing competitive features.

**Must have (table stakes):**

- **Structured output (outputSchema)** — MCP 2025-06-18 spec requirement. Clients need typed tool results. FastMCP 3.x auto-generates this from Pydantic response models.
- **Complete tool annotations** — MCP 2025-06-18. Add idempotentHint on GET operations, openWorldHint=False globally. Currently partial (readOnlyHint only).
- **Full bidirectional format conversion** — JSON↔YAML↔TOML. Currently blocked by yq's TOML write limitation. Fix with tomlkit Python-native encoding.
- **JSON Schema 2020-12 as default** — MCP 2025-11-25 spec mandates this. Currently defaults to Draft 7. One-line fix.

**Should have (competitive):**

- **Config file diffing** — New data_diff tool. High user value, no existing MCP server does this. Independent of backend.
- **Expanded format support (INI/HCL)** — DevOps users need these. yq supports HCL/properties. Defer until demand confirmed.
- **Tool versioning** — FastMCP 3.x feature. Serve v1 and v2 tools side-by-side during API evolution (e.g., expression syntax changes).
- **OpenTelemetry observability** — FastMCP 3.x native instrumentation. Production deployments need tracing. Drop-in config.

**Defer (v2+):**

- **Elicitation support** — Human-in-the-loop workflows. FastMCP 3.x supports this, but UX design is complex and protocol adoption is sparse.
- **Async tasks** — Only matters for very large files (>10MB) or directory operations. Current pagination handles typical cases.
- **Multi-file query** — Powerful but requires careful pagination design for cross-file results.
- **Native Python parsing** — Eliminate subprocess overhead by using pure Python. High migration cost, requires expression translation layer.

### Architecture Approach

Current architecture suffers from god module anti-pattern (server.py: 1880 lines, 7 responsibilities) and tight coupling to yq binary. Target architecture separates concerns into five layers: transport (FastMCP), tool registration (thin decorators), service logic (format routing, validation), backend abstraction (query execution), and format handlers (parse/serialize per format).

**Major components:**

1. **tools/ layer (5 files)** — Thin @mcp.tool decorators with parameter validation only. Delegates to services. Under 100 lines per file.
2. **services/ layer** — data_service.py (format routing, schema orchestration), pagination.py (cursor handling), response_builder.py (consistent output). Business logic with zero FastMCP dependency.
3. **backends/ layer** — QueryBackend protocol, YqBackend implementation, BinaryManager (extracted from yq_wrapper.py). Abstraction boundary enabling future backend swaps without touching tools or services.
4. **formats/ layer** — FormatHandler protocol, json_handler.py (orjson), yaml_handler.py (ruamel.yaml + optimizer), toml_handler.py (tomlkit). Centralizes format-specific parsing and serialization logic.
5. **Domain services (unchanged)** — schemas.py (Schema Store), lmql_constraints.py (constraint registry), config.py (environment settings).

**Key patterns:**

- Backend Protocol (Strategy Pattern): QueryBackend interface decouples 14 execute_yq() call sites from implementation
- Format Handler Registry: Each format owns parse/serialize, eliminating scattered if-format-is-toml branching
- Thin Tool Registration: Tool functions contain only validation, business logic lives in services

### Critical Pitfalls

1. **Dasel destroys YAML/TOML comments on write** — dasel uses Go parsers that discard comments. Switching write backend destroys the core differentiator. Avoid by: never using dasel for write operations; keep ruamel.yaml/tomlkit write paths.
2. **Dasel cannot preserve YAML anchors/aliases** — The yaml_optimizer.py module (372 lines) creates anchors to deduplicate structures. dasel expands anchors on write. Avoid by: maintaining YAML write pipeline through ruamel.yaml.
3. **MCP tool name changes cause silent client failures** — Production MCP clients maintain tool allowlists. Renamed tools silently disappear from LLM agent. Avoid by: treating tool names as immutable public API; add new tools, never rename.
4. **yq expression syntax incompatible with dasel selectors** — data_query exposes yq jq-like expressions. dasel uses CSS-like selectors. No automatic translation. Avoid by: if adopting dasel, require expression translation layer; or use dasel only for read/convert, keep yq for queries.
5. **FastMCP 3.0 decorator behavior change breaks tests** — v2.x decorators return FunctionTool objects, v3.x returns functions. Test mocking may break. Avoid by: audit tests for FunctionTool assumptions; use FASTMCP_DECORATOR_MODE=object bridge during migration.

## Implications for Roadmap

Based on research, suggested phase structure follows architectural dependencies with independent deliverables and test gates:

### Phase 1: Extract Utilities & Backend Abstraction

**Rationale:** Foundation for all subsequent work. Reduces server.py complexity without behavior changes. Enables parallel development on services and backends.
**Delivers:**

- services/pagination.py (cursor handling, 130-215 lines extracted)
- services/response_builder.py (consistent responses)
- formats/base.py (FormatType enum, detection logic)
- backends/base.py (QueryBackend protocol)
- backends/binary_manager.py (extracted from yq_wrapper.py)
- backends/yq.py (YqBackend implementing protocol)
- yq_wrapper.py becomes backward-compatible shim
  **Addresses:** Architecture Technical Debt (god module)
  **Avoids:** Pitfall #2 (binary management in execution module)
  **Research needs:** SKIP — well-documented patterns, existing code provides reference

### Phase 2: Format Handlers & Service Layer

**Rationale:** Centralizes format-specific logic scattered across 4+ files. Prerequisite for unified TOML handling and full bidirectional conversion.
**Delivers:**

- formats/json_handler.py, yaml_handler.py, toml_handler.py (FormatHandler implementations)
- services/data_service.py (query, set_value, delete_value, convert, merge functions)
- Absorbs toml_utils.py into formats/toml_handler.py
- Absorbs yaml_optimizer.py into formats/yaml_handler.py
  **Uses:** Backend abstraction from Phase 1
  **Implements:** Format Handler Registry pattern
  **Addresses:** Full Bidirectional Conversion (TOML encoding fix)
  **Avoids:** Pitfall #1 (comment destruction) via explicit format preservation tests
  **Research needs:** SKIP — existing code demonstrates pattern

### Phase 3: Split Tool Registration & Pydantic Models

**Rationale:** Reduces server.py to <50 lines, enables independent tool testing. Pydantic response models are prerequisite for structured output in Phase 5.
**Delivers:**

- tools/data.py, query.py, schema.py, convert.py, constraints.py (thin decorators)
- Pydantic response models for all tool return types
- server.py becomes entry point (FastMCP init + tool registration imports)
  **Uses:** Service layer from Phase 2
  **Implements:** Thin Tool Registration pattern
  **Addresses:** Complete Tool Annotations (idempotentHint, openWorldHint), Structured Output foundation
  **Avoids:** Pitfall #3 (tool name changes) via stability contract test
  **Research needs:** SKIP — FastMCP decorator patterns are established

### Phase 4: FastMCP 3.x Migration

**Rationale:** Unlocks automatic threadpool, tool timeouts, component versioning. Must happen after tool split (Phase 3) to minimize migration surface per file.
**Delivers:**

- pyproject.toml pin update (fastmcp>=3.0.0,<4)
- Removal of .fn extraction patterns from tests
- Addition of timeout=30.0 to tool decorators
- mask_error_details parameter verification/replacement
- ToolAnnotations import updates (if needed)
  **Trigger:** FastMCP 3.0.0 stable release (currently 3.0.0rc2)
  **Avoids:** Pitfall #5 (decorator behavior change), Pitfall #6 (deprecated API removal), Pitfall #7 (import errors)
  **Research needs:** SKIP — official upgrade guide provides checklist

### Phase 5: MCP Spec 2025-11-25 Compliance

**Rationale:** Quick wins for spec compliance after FastMCP upgrade. Structured output auto-wires from Pydantic models (Phase 3). Component icons are cosmetic.
**Delivers:**

- Structured output (outputSchema) enabled via FastMCP 3.x auto-generation
- JSON Schema 2020-12 as default validator
- Component icons for tools/resources/prompts
- Complete tool annotations (from Phase 3 plus verification)
  **Uses:** Pydantic models from Phase 3, FastMCP 3.x from Phase 4
  **Addresses:** Table Stakes features (structured output, annotations, 2020-12 default)
  **Research needs:** SKIP — MCP spec 2025-11-25 is well-documented

### Phase 6: Competitive Features (Config Diff, OpenTelemetry)

**Rationale:** High-value differentiators with low implementation cost. Config diff is independent of backend. OpenTelemetry is drop-in FastMCP 3.x config.
**Delivers:**

- data_diff tool (structured diff using deepdiff library)
- OpenTelemetry instrumentation configuration
- Tool versioning examples (if needed for future API evolution)
  **Uses:** Service layer from Phase 2, FastMCP 3.x from Phase 4
  **Addresses:** Competitive features (diffing, observability)
  **Research needs:** MINOR for deepdiff library integration patterns

### Phase Ordering Rationale

- **Phases 1-3 are independent of FastMCP 3.x.** Architecture refactoring happens on FastMCP 2.x, reducing migration risk.
- **Phase 1 before Phase 2:** Backend abstraction is prerequisite for format handlers (YqBackend dependency)
- **Phase 2 before Phase 3:** Service layer is prerequisite for thin tool wrappers (delegation target)
- **Phase 3 before Phase 4:** Smaller files = smaller migration surface = lower FastMCP upgrade risk
- **Phase 4 before Phase 5:** FastMCP 3.x is prerequisite for auto-generated structured output
- **Phase 6 deferred until after compliance:** Competitive features add value but table stakes come first
- **Backend migration (dasel) REJECTED:** Comment/anchor preservation failures eliminate this path

### Research Flags

Phases with standard patterns (skip research-phase):

- **Phase 1:** Extraction refactoring — existing code provides reference implementation
- **Phase 2:** Service layer — format handler pattern is well-established (similar to adapter pattern)
- **Phase 3:** Tool splitting — FastMCP decorator patterns are documented
- **Phase 4:** FastMCP upgrade — official upgrade guide at gofastmcp.com/development/upgrade-guide
- **Phase 5:** MCP spec compliance — spec 2025-11-25 is ratified and documented

Phases with minor research needs:

- **Phase 6:** Config diffing — research deepdiff vs alternatives (difflib, dictdiffer) for structured data

No phases require deep /gsd:research-phase calls. All patterns are established.

## Confidence Assessment

| Area         | Confidence  | Notes                                                                                                                                                                                              |
| ------------ | ----------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Stack        | HIGH        | Current stack verified against PyPI, yq/dasel capabilities confirmed via official docs. FastMCP 3.x features verified via upgrade guide and release notes.                                         |
| Features     | MEDIUM-HIGH | MCP spec requirements are definitive (HIGH). FastMCP 3.x feature availability is documented (HIGH). Competitive feature value is estimated based on user patterns (MEDIUM).                        |
| Architecture | HIGH        | Current codebase analysis is direct source evidence. Target architecture patterns (Strategy, Registry) are well-established. FastMCP 3.x migration impact verified via official upgrade guide.     |
| Pitfalls     | HIGH        | Dasel comment/anchor limitations confirmed via GitHub issues (#178). FastMCP breaking changes verified via official upgrade guide. MCP tool name stability issues documented in community reports. |

**Overall confidence:** MEDIUM-HIGH

Backend evaluation (yq vs dasel) is definitive: dasel's comment destruction is a documented, unfixable limitation. Architecture refactoring is well-understood (standard extraction patterns). FastMCP migration is low-risk (narrow API surface, official upgrade guide). The main uncertainty is user demand for expanded format support (INI/HCL) and competitive feature prioritization (defer to user feedback during Phase 6).

### Gaps to Address

- **ruamel.yaml 0.19 compatibility:** Pin <0.19 explicitly in pyproject.toml until build toolchain (setuptools-zig vs ruamel.yaml.clib) is validated across deployment targets. LOW priority.
- **FastMCP 3.0.0 stable release timing:** Currently 3.0.0rc2 (2026-02-14). Phase 4 timing depends on stable release (estimated Q1 2026). Monitor github.com/jlowin/fastmcp/releases. MEDIUM priority.
- **mask_error_details parameter in FastMCP 3.x:** Current code uses `FastMCP(mask_error_details=False)`. Upgrade guide does not list this as removed, but verify during Phase 4 testing. Test with 3.0.0rc2 before stable upgrade. LOW priority.
- **Expression translation layer viability:** If future work requires dasel for specific formats (e.g., INI-only operations), expression translation from yq to dasel syntax is HIGH effort (pipes, filters, functions). Defer indefinitely; dasel is NOT recommended. BACKLOG.
- **Pagination cursor format stability:** Current implementation uses base64-encoded JSON with offset field. Ensure backend abstraction (Phase 1) does not change cursor format (breaks existing client state). Add cursor round-trip test as gate. MEDIUM priority.

## Sources

### Primary (HIGH confidence)

- FastMCP Upgrade Guide (<https://gofastmcp.com/development/upgrade-guide>) — breaking changes, migration steps
- FastMCP GitHub Releases (<https://github.com/jlowin/fastmcp/releases>) — v3.0.0rc2, v2.14.x release notes
- FastMCP 3.0 What's New (<https://www.jlowin.dev/blog/fastmcp-3-whats-new>) — new features, rationale
- MCP Specification 2025-11-25 (<https://modelcontextprotocol.io/specification/2025-11-25>) — protocol requirements
- Dasel GitHub Issue #178 (<https://github.com/TomWright/dasel/issues/178>) — comment preservation limitation (confirmed open)
- yq GitHub (<https://github.com/mikefarah/yq>) — current backend capabilities
- Current codebase (direct file reading) — architecture analysis, line counts, dependency patterns

### Secondary (MEDIUM confidence)

- Context7 FastMCP docs (/llmstxt/gofastmcp_llms-full_txt) — migration patterns
- Context7 dasel docs (/websites/daseldocs_tomwright_me) — dasel v3 capabilities
- Dasel documentation (<https://daseldocs.tomwright.me/v3>) — official v3 docs, "in active development" status
- WorkOS MCP spec analysis (<https://workos.com/blog/mcp-2025-11-25-spec-update>) — third-party spec overview
- Cisco MCP elicitation analysis (<https://blogs.cisco.com/developer/whats-new-in-mcp-elicitation-structured-content-and-oauth-enhancements>) — protocol feature analysis

### Tertiary (LOW confidence)

- Bright Coding dasel blog (<https://www.blog.brightcoding.dev/2025/09/09/dasel-the-universal-swiss-army-knife-for-json-yaml-toml-xml-and-csv-on-the-command-line>) — performance claims unverified

---

_Research completed: 2026-02-14_
_Ready for roadmap: yes_

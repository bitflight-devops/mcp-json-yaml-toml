# Codebase Concerns

**Analysis Date:** 2026-02-14

## Tech Debt

### D1. Type Coercion Bug in MCP Protocol Layer

- **Issue:** AI agents naturally send `value="3.12"` to set string values, but MCP protocol strips outer quotes during JSON serialization. Server receives `3.12` (float) instead of `"3.12"` (string).
- **Files:** `packages/mcp_json_yaml_toml/server.py` (line 436), `packages/mcp_json_yaml_toml/tests/test_set_type_preservation.py` (lines 873-920)
- **Impact:** Type coercion occurs when agents set values. Workaround requires double-encoding (`value='"3.12"'`), which is unintuitive and undiscoverable.
- **Root Cause:** `parsed_value = orjson.loads(value)` expects JSON-encoded input but receives partially-parsed values from MCP
- **Fix approach:** Implement type preservation via `value_type` parameter that bypasses JSON parsing when set, or document double-encoding pattern clearly. Currently mitigated by test suite using correct encoding pattern.

### D2. Repeated File Validation Logic

- **Issue:** Seven tool functions (`config_query`, `config_get`, `config_set`, `config_delete`, `config_validate`, `config_convert`, `config_merge`) repeat identical validation pattern
- **Files:** `packages/mcp_json_yaml_toml/server.py` (lines 127-138, 180-191, 234-245, 297-308, 345-356, 419-430, 488-509)
- **Impact:** ~42 lines of duplicated code. DRY violation increases maintenance burden and bug fix complexity
- **Fix approach:** Extract into helper function `_validate_config_file(file_path: str) -> tuple[Path, FormatType]` that returns resolved path and detected format. All tools would call this single function.

### D3. Repeated Format Resolution Logic

- **Issue:** Pattern `output_fmt = input_format if output_format is None else validate_format(output_format).value` appears 4 times
- **Files:** `packages/mcp_json_yaml_toml/server.py` (lines 141, 194, 433, 512-513)
- **Impact:** Duplicated format resolution logic increases inconsistency risk
- **Fix approach:** Extract into `_resolve_output_format(input_format: FormatType, requested_format: str | None) -> FormatType` helper

### D4. Repeated Path Resolution Pattern

- **Issue:** Pattern `Path(file_path).expanduser().resolve()` appears 14+ times throughout codebase
- **Files:** `packages/mcp_json_yaml_toml/server.py` (multiple functions)
- **Impact:** Minor DRY violation, reduces code clarity
- **Fix approach:** Create helper `_resolve_path(file_path: str) -> Path` to consolidate resolution logic

### D5. Missing Logging Configuration

- **Issue:** No logging infrastructure for observability. Errors raised but not logged before raising. No audit trail for destructive operations (`config_set`, `config_delete`)
- **Files:** `packages/mcp_json_yaml_toml/server.py`, `packages/mcp_json_yaml_toml/yq_wrapper.py`
- **Impact:** Production issues difficult to debug. Audit trail missing for compliance. Errors surface only to client, not to server operators
- **Fix approach:** Add logging configuration with structured JSON logs to `~/.local/logs/mcp-json-yaml-toml/server.pid.json`. Add operation logging before/after each tool execution, especially destructive operations. Log schema cache hits/misses for performance analysis.

### D6. Lazy Imports for Circular Dependencies

- **Issue:** Conditional imports at function scope to break circular dependencies (e.g., `toml_utils`, `yaml_optimizer` in `server.py`)
- **Files:** `packages/mcp_json_yaml_toml/server.py` (lines 431, 455, 619)
- **Impact:** Architectural constraint. Code is documented and justified but adds cognitive load. Future maintainers may attempt to "fix" these into top-level imports
- **Fix approach:** Add explicit docstring comments explaining lazy import rationale. Document in `.claude/knowledge/linting-patterns.md`. This is architectural and justified; no code changes needed, only documentation.

## Known Bugs

### B1. Type Coercion Edge Cases in TOML Sets

- **Symptoms:** When setting TOML values via `config_set`, numeric strings may coerce to numbers unintentionally
- **Files:** `packages/mcp_json_yaml_toml/toml_utils.py`, `packages/mcp_json_yaml_toml/tests/test_set_type_preservation.py`
- **Trigger:** Use `value="3.12"` without `value_type="string"` parameter to set a TOML string field
- **Workaround:** Always specify `value_type="string"` when setting string values that look like numbers

## Security Considerations

### S1. Unrestricted File Path Access

- **Risk:** Server accepts any file path via `file_path` parameter. No validation restricts access to specific directories
- **Files:** `packages/mcp_json_yaml_toml/server.py` (all tool functions accept `file_path`)
- **Current mitigation:** MCP server is meant to run in trusted environments (local LLM interactions). No authentication layer in FastMCP
- **Recommendations:** Document security model clearly. Consider adding optional `MCP_ALLOWED_PATHS` environment variable to restrict file access to specific directories if running in multi-user environments

### S2. Arbitrary Schema URL Fetching

- **Risk:** `config_schema` tool fetches schemas from arbitrary URLs provided by users/agents
- **Files:** `packages/mcp_json_yaml_toml/server.py` (line 882)
- **Current mitigation:** Uses `httpx` with `follow_redirects=True` and timeout. No validation of URL scheme or domain
- **Recommendations:** Add URL scheme validation (only `https://` allowed). Consider URL allowlist for trusted schema sources. Add rate limiting for schema fetches to prevent DOS

### S3. Unbounded Cache Growth for Schemas

- **Risk:** Schema cache can grow unbounded if many unique schema URLs are fetched
- **Files:** `packages/mcp_json_yaml_toml/schemas.py` (cache directory: `~/.cache/mcp-json-yaml-toml/schemas`)
- **Current mitigation:** No cache expiration policy. Relies on user manual cleanup
- **Recommendations:** Implement cache eviction policy (LRU or time-based expiration). Add cache size limit with overflow handling

## Performance Bottlenecks

### P1. Schema Cache Invalidation on Every Tool Invocation

- **Problem:** Schema validation checks file modification times on IDE cache directories on every tool call
- **Files:** `packages/mcp_json_yaml_toml/schemas.py` (lines 588-620)
- **Cause:** `_load_ide_schema_index()` scans extension directories for changes every invocation
- **Improvement path:** Implement session-scoped schema caching (v3.0 feature) to cache across multiple tool calls in same session. Add mtime caching with configurable expiration to reduce filesystem I/O

### P2. Multiple Timeouts in Subprocess Execution

- **Problem:** Multiple hardcoded timeouts (5s, 30s, 60s) with no central configuration
- **Files:** `packages/mcp_json_yaml_toml/yq_wrapper.py` (lines 184, 236, 337, 407, 796, 919)
- **Cause:** Different operations have different timeout needs but values not documented or configurable
- **Improvement path:** Extract timeout constants to module level with clear documentation. Make configurable via environment variables. Consider adding per-operation timeout metrics

### P3. Concurrent Executor for IDE Schema Lookups

- **Problem:** Concurrent futures used for IDE cache lookups but may create thread pool overhead for fast-path scenarios
- **Files:** `packages/mcp_json_yaml_toml/schemas.py` (lines 1085-1090)
- **Cause:** All cache lookups run in parallel regardless of number of directories
- **Improvement path:** Add fast-path optimization: if common schema filename found in first 2 locations, return immediately without spawning executor

### P4. Pagination Not Implemented for Large File Contents

- **Problem:** Large YAML/JSON/TOML files may exceed LLM context window when returned as single chunk
- **Files:** `packages/mcp_json_yaml_toml/server.py` (lines 132-133 constants defined but not consistently applied)
- **Cause:** Page size tuning exists but inconsistently applied across all output types
- **Improvement path:** Implement consistent cursor-based pagination for all content-returning tools. Add advisory hints when results span multiple pages

## Fragile Areas

### F1. YAML Optimizer Complexity

- **Files:** `packages/mcp_json_yaml_toml/yaml_optimizer.py` (372 lines)
- **Why fragile:** Complex heuristic-based optimization for YAML readability. Edge cases in nested structure handling. Modifies user data
- **Safe modification:** Add extensive test cases for nested structures, anchors, and aliases before changes. Ensure optimizer preserves all YAML semantics (anchors, comments, custom tags)
- **Test coverage:** Medium - optimize tests exist but edge cases for deeply nested structures may lack coverage

### F2. YQ Binary Management and Version Detection

- **Files:** `packages/mcp_json_yaml_toml/yq_wrapper.py` (lines 100-420)
- **Why fragile:** Platform detection, checksum validation, binary caching, and automatic download logic. Multiple fallback paths for error handling
- **Safe modification:** Test on all supported platforms (Linux amd64/arm64, macOS amd64/arm64, Windows amd64) before deploying binary management changes. Mock network failures
- **Test coverage:** Good - platform-specific tests exist with skip markers

### F3. Schema Validation Integration with jsonschema

- **Files:** `packages/mcp_json_yaml_toml/server.py` (lines 697-703, 1300-1380)
- **Why fragile:** Complex exception hierarchy (ValidationError, SchemaError, NoSuchResource). Multiple schema draft versions (Draft7, Draft202012). Remote reference resolution via `referencing` library
- **Safe modification:** Ensure all schema validation exceptions are explicitly caught. Test with both Draft7 and Draft202012 schemas. Verify remote reference resolution doesn't create security issues
- **Test coverage:** Medium - basic validation tests exist but draft version coverage may be incomplete

### F4. TOML Modification Logic

- **Files:** `packages/mcp_json_yaml_toml/toml_utils.py` (87 lines)
- **Why fragile:** Direct dict manipulation with type preservation. Nested key path handling with string keys
- **Safe modification:** Add tests for deeply nested TOML structures, arrays of tables, inline tables before changes. Verify type preservation doesn't corrupt TOML semantics
- **Test coverage:** Medium - basic set/delete tests exist

## Scaling Limits

### L1. Binary Checksum Validation

- **Current capacity:** 5 checksums bundled in `DEFAULT_YQ_CHECKSUMS` for default version
- **Limit:** If yq releases for 10+ platforms, bundled checksums become unwieldy
- **Scaling path:** Move checksums to external file (`yq_checksums.json`) shipped with package. Add checksum update automation as part of weekly yq version update workflow

### L2. Schema Cache Directory Size

- **Current capacity:** Unbounded growth in `~/.cache/mcp-json-yaml-toml/schemas`
- **Limit:** After ~1000 schemas, directory listing and file searches become slow
- **Scaling path:** Implement cache eviction with LRU policy. Add cache statistics command to monitor disk usage

### L3. IDE Schema Location Scanning

- **Current capacity:** Parallel scan of all IDE schema directories works for <50 directories
- **Limit:** Beyond 50 IDE schema directories, concurrent executor overhead and filesystem I/O become bottleneck
- **Scaling path:** Implement directory mtime-based skip logic. Cache directory scan results for 60 seconds

## Test Coverage Gaps

### T1. Cross-Platform Binary Execution

- **What's not tested:** Full binary execution flow on Windows platform (CI likely runs on Linux)
- **Files:** `packages/mcp_json_yaml_toml/yq_wrapper.py` (binary execution logic)
- **Risk:** Windows-specific subprocess issues may not be caught (e.g., `.exe` extension, path separators, process termination)
- **Priority:** High - affects production deployment on Windows

### T2. LMQL Constraint Validation with Complex Expressions

- **What's not tested:** Complex LMQL constraint expressions with nested conditions and variable scoping
- **Files:** `packages/mcp_json_yaml_toml/lmql_constraints.py` (846 lines)
- **Risk:** Complex expressions may fail validation silently, providing incorrect hints to LLM clients
- **Priority:** Medium - impacts AI agent behavior guidance

### T3. Schema Validation with Circular References

- **What's not tested:** JSON schemas with circular `$ref` declarations
- **Files:** `packages/mcp_json_yaml_toml/server.py` (schema validation logic)
- **Risk:** Circular references may cause infinite loops or memory exhaustion in schema validation
- **Priority:** Medium - potential DOS vector

### T4. Pagination with Very Large Files (>100MB)

- **What's not tested:** Behavior when input files exceed reasonable in-memory limits
- **Files:** `packages/mcp_json_yaml_toml/server.py` (pagination logic)
- **Risk:** Out-of-memory errors on resource-constrained systems. Pagination constants may not handle 100MB+ files
- **Priority:** Low - unlikely in typical use cases, but impacts robustness

## Dependencies at Risk

### D1. FastMCP Version Pinning to v2.14.4

- **Risk:** Pinned to `<3` due to v3.0 being in beta. When v3.0 stabilizes, upgrade path may require significant refactoring
- **Files:** `pyproject.toml` (line 30)
- **Impact:** Missing v3.0 features (session state, transforms, provider architecture) that would improve performance and code organization
- **Migration plan:** Monitor FastMCP v3.0 release. Phase 2.1 (session-scoped schema caching) documented in `/docs/fastmcp-v3-upgrade-plan.md`. Begin migration work after v3.0 stable release (estimated 1-2 weeks effort)

### D2. ruamel.yaml Pinned to 0.18.x

- **Risk:** v0.19.x has different API. v0.18 stability constraint may miss important bugfixes in newer versions
- **Files:** `pyproject.toml` (line 37)
- **Impact:** YAML parsing bugs or security issues in v0.18.x would require manual backport or workaround
- **Migration plan:** Test v0.19 API changes. Create compatibility layer if API differs. Schedule upgrade when v0.19 stabilizes

### D3. tomlkit Nested Structure Support Recently Added

- **Risk:** tomlkit 0.14.0 added nested TOML structure support. May have edge cases with complex nested structures
- **Files:** `pyproject.toml` (line 38), `packages/mcp_json_yaml_toml/tests/test_set_type_preservation.py` (TOML-specific tests)
- **Impact:** Nested TOML operations may fail on unusual edge cases (very deep nesting, unusual ordering)
- **Migration plan:** Comprehensive testing of nested TOML structures with 5+ levels of nesting. Test with real-world configurations

## Missing Critical Features

### M1. Structured Logging for Production Debugging

- **Problem:** No operational logs. Errors surface only to client. No audit trail for destructive operations
- **Blocks:** Production observability. Compliance requirements for audit trails. Root cause analysis for failures
- **Priority:** High - critical for production deployment

### M2. Rate Limiting on Schema Fetches

- **Problem:** No rate limiting for remote schema URL fetching. Potential DOS vector if many different schemas requested
- **Blocks:** Defense against malicious AI agents or accidental infinite loops
- **Priority:** Medium - affects robustness in adversarial environments

### M3. File Access Control / Allowlisting

- **Problem:** No restriction on which files can be accessed. Server can read/write any file the process has permissions for
- **Blocks:** Multi-user or multi-tenant deployments. Security hardening for exposed MCP servers
- **Priority:** Low for typical use (single-user local), High if ever exposed on network

### M4. Configuration File Validation

- **Problem:** No pre-flight validation of configuration files before processing
- **Blocks:** Early detection of malformed files. Better error messages before yq execution
- **Priority:** Low - yq provides error messages but early validation would improve UX

---

_Concerns audit: 2026-02-14_

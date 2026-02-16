# Pitfalls Research

**Domain:** MCP server upgrade/migration (FastMCP 2.x->3.x, yq->dasel backend switch, production refactoring)
**Researched:** 2026-02-14
**Confidence:** HIGH (FastMCP pitfalls verified against official upgrade guide and release notes; dasel pitfalls verified against official docs and GitHub issues; MCP protocol pitfalls verified against spec and community reports)

## Critical Pitfalls

### Pitfall 1: Dasel Destroys YAML/TOML Comments on Write

**What goes wrong:**
Dasel uses Go's standard YAML and TOML parsers which discard comments during write operations. Every `dasel put` call on a YAML or TOML file strips all comments. This project's core differentiator is format preservation (comments, anchors, formatting) -- switching the write backend to dasel would destroy this capability entirely.

**Why it happens:**
Dasel's underlying Go parsers (`gopkg.in/yaml.v3` and `github.com/pelletier/go-toml`) do not implement round-trip comment preservation. This is a known, documented limitation (dasel [Issue #178](https://github.com/TomWright/dasel/issues/178)) with no fix timeline. The current codebase deliberately uses `ruamel.yaml` and `tomlkit` for write operations specifically because they preserve comments and formatting.

**How to avoid:**
Do not replace the write path with dasel. The current architecture already handles this correctly: yq is used for read/query operations and format conversion, while `ruamel.yaml` (YAML writes) and `tomlkit` (TOML writes) handle mutations. If dasel is introduced, it must be limited to read-only operations (queries, conversions, schema introspection). All write paths must remain with the current libraries.

**Warning signs:**

- Tests for comment preservation start failing
- Users report comments disappearing from their config files after set/delete operations
- Diff output shows entire file rewritten (not just the changed value)

**Phase to address:**
Backend evaluation phase -- establish write-path exclusion rule before any dasel integration begins. Create a "format preservation" test suite as a gate before backend changes.

---

### Pitfall 2: Dasel Cannot Create or Preserve YAML Anchors/Aliases

**What goes wrong:**
Dasel can _read_ YAML anchors and aliases (since v2.8.0), but it expands them on write. The YAML anchor optimizer (`yaml_optimizer.py`) creates anchors to deduplicate repeated structures. If dasel is used for any write path, it will expand all anchors into duplicated content, inflating file size and destroying the optimization this project performs.

**Why it happens:**
YAML anchors and aliases are a YAML-specific feature with no equivalent in JSON, TOML, or other formats dasel supports. Dasel's unified data model flattens format-specific features during processing. When writing back to YAML, the anchor/alias relationships are lost.

**How to avoid:**
Keep the YAML write pipeline using `ruamel.yaml` which natively supports anchor/alias round-tripping. The `yaml_optimizer.py` module (372 lines) depends on `ruamel.yaml`'s internal representation to detect duplicates and create anchors. This module has no equivalent in dasel's API. If dasel is introduced for queries, ensure all results that flow back to write paths are re-processed through `ruamel.yaml`.

**Warning signs:**

- YAML files grow significantly after write operations (anchors expanded to full content)
- `test_yaml_optimizer.py` and `test_yaml_optimization_integration.py` tests fail
- `_optimize_yaml_if_needed()` in server.py stops detecting optimization candidates

**Phase to address:**
Backend evaluation phase -- document this as a hard constraint before any dasel integration planning. The anchor optimizer is a differentiator that must survive any backend migration.

---

### Pitfall 3: MCP Tool Name Changes Cause Silent Client Failures

**What goes wrong:**
Production MCP clients (Claude Desktop, Cursor, custom integrations) maintain tool allowlists. If tool names change during a server upgrade (e.g., `data_query` renamed, or new tool names added), clients with allowlists will silently drop the renamed tools. The LLM agent loses access to the tool without any error -- it simply disappears from the available tool list.

**Why it happens:**
The MCP protocol does not enforce tool name stability. Security-conscious clients filter tools through allowlists configured at deployment time. A tool rename looks identical to a tool removal from the client's perspective. There is no MCP mechanism to signal "this tool was renamed from X to Y."

**How to avoid:**
Treat the five existing tool names (`data`, `data_query`, `data_schema`, `data_convert`, `data_merge`, `constraint_validate`, `constraint_list`) as immutable public API. If new tools are needed, add them alongside existing tools, never as replacements. If a tool must be deprecated, keep the old name as an alias for at least one major version cycle. Document all tool names in a stability contract.

**Warning signs:**

- Users report "tool not found" errors after upgrade
- CI integration tests pass (they use the server directly) but production clients fail
- Client logs show fewer available tools after server upgrade

**Phase to address:**
Every phase -- tool name stability must be a constraint on all roadmap phases. Add an integration test that asserts the exact set of tool names exported by the server matches a known list.

---

### Pitfall 4: yq Expression Syntax Not Compatible with Dasel Selectors

**What goes wrong:**
The `data_query` tool exposes yq expression syntax directly to MCP clients. Existing client prompts, cached tool descriptions, and LLM training data all reference yq expressions (e.g., `.users[] | select(.active)`, `.items | length`, `. * overlay`). Dasel uses a completely different selector syntax (e.g., `.users.[0].name`, `filter(equal(name,value))`). Switching backends breaks every existing client query and invalidates the LMQL constraint patterns for `YQ_PATH` and `YQ_EXPRESSION`.

**Why it happens:**
yq uses a jq-like expression language with pipes, filters, and operators. Dasel uses dot-notation selectors with bracket indices. These are fundamentally different query languages with no automatic translation layer. The LMQL constraints in `lmql_constraints.py` encode yq-specific regex patterns (`YQPathConstraint.PATTERN`, `YQExpressionConstraint.PATTERN`) that would be completely wrong for dasel syntax.

**How to avoid:**
If dasel is adopted, it must be behind an abstraction layer that translates yq expressions to dasel selectors. Alternatively, maintain yq for the query interface and use dasel only for operations yq cannot perform. The translation layer must handle: pipes (`|`), array iteration (`[]`), select filters (`select()`), multiplication/merge (`*`), and function calls (`length`, `keys`, `type`). This is a significant engineering effort. The LMQL constraints must also be updated to validate the new syntax.

A phased approach: introduce dasel as an alternative backend with a `backend` parameter, keep yq as default, migrate only after the translation layer is validated.

**Warning signs:**

- `test_lmql_constraints.py` tests fail for expression validation
- Client queries that previously worked start returning parse errors
- Tool descriptions reference syntax that the backend does not understand
- The merge operation (`. * overlay_json`) in `data_merge` stops working

**Phase to address:**
Backend abstraction phase -- build the abstraction layer and expression translator before any backend swap. This is the highest-effort item in the migration.

---

### Pitfall 5: FastMCP 3.0 `get_tools()` -> `list_tools()` Return Type Change

**What goes wrong:**
FastMCP 3.0 renames `get_tools()` to `list_tools()` and changes the return type from `dict` to `list`. Code that accesses tools by name via dictionary lookup (e.g., `tools["my_tool"]`) breaks silently -- instead of a `KeyError`, the code may receive unexpected results or fail in hard-to-trace ways if the dict access pattern is used in test utilities or middleware.

**Why it happens:**
FastMCP 3.0 redesigned the component listing API for consistency across tools, resources, prompts, and resource templates. The v2 dictionary-keyed access pattern was replaced with list iteration. The `from mcp.server.fastmcp import FastMCP` import path also changes to `from fastmcp import FastMCP`.

**How to avoid:**
Before upgrading: grep the entire codebase for `get_tools()`, `get_resources()`, `get_prompts()`, `get_resource_templates()`. The test file `test_fastmcp_integration.py` imports `from fastmcp.client.client import CallToolResult` and `from mcp.types import TextContent` -- these import paths may also change. Create an upgrade branch, update imports, run the full test suite. The v3 upgrade guide at [gofastmcp.com/development/upgrade-guide](https://gofastmcp.com/development/upgrade-guide) documents all breaking changes.

Specific changes needed for this project:

1. Import: `from fastmcp import FastMCP` (already correct in this codebase)
2. `mask_error_details=False` on `FastMCP()` constructor -- verify this parameter still exists in v3
3. `mcp.tool(annotations={"readOnlyHint": True})` -- verify annotation format unchanged
4. `from fastmcp.exceptions import ToolError` -- verify exception module path

**Warning signs:**

- `AttributeError: 'FastMCP' object has no attribute 'get_tools'`
- Tests importing from `mcp.types` fail with `ModuleNotFoundError`
- `DeprecationWarning` messages in test output before the full break

**Phase to address:**
FastMCP upgrade phase -- dedicated phase with full test suite execution. Do not combine with backend changes. The upgrade guide states "most servers need only one change" but edge cases exist around test utilities and middleware.

---

### Pitfall 6: FastMCP 3.0 Decorator Behavior Change Breaks Test Mocking

**What goes wrong:**
In FastMCP 2.x, `@mcp.tool` returns a `FunctionTool` component object. In 3.x, it returns the original function. Code that inspects or mocks the decorated function as a `FunctionTool` (e.g., checking attributes, calling component methods) will fail. This is particularly insidious because the function _still works_ when called -- the failure surfaces only when component-specific operations are attempted.

**Why it happens:**
FastMCP 3.0 changed decorator behavior so decorated functions remain callable for testing. This is actually a quality-of-life improvement, but it breaks code that relied on the old component-object behavior. A compatibility escape hatch exists: set `FASTMCP_DECORATOR_MODE=object` for v2 behavior.

**How to avoid:**
Audit test files for patterns that treat decorated functions as `FunctionTool` objects. In `test_fastmcp_integration.py`, the test pattern uses `Client(mcp)` context manager -- verify this pattern works unchanged in v3. Check if any test utilities or conftest fixtures introspect tool registration objects. The `FASTMCP_DECORATOR_MODE=object` env var provides a compatibility bridge if needed during migration.

**Warning signs:**

- Tests pass locally but fail in CI (different FastMCP version installed)
- `AttributeError` on decorated functions when accessing `.name`, `.description`, or component methods
- Tool registration appears to succeed but tools are not listed

**Phase to address:**
FastMCP upgrade phase -- test suite audit before version bump.

---

### Pitfall 7: FastMCP 3.0 Removes Deprecated APIs Used in v2.14.x Code

**What goes wrong:**
FastMCP 3.0 removes APIs deprecated across the 2.x series. The project pins `fastmcp>=2.14.4,<3`. When upgrading to 3.x, any usage of removed APIs will cause immediate `ImportError` or `TypeError` at startup, not at call time. The server will fail to start entirely.

**Why it happens:**
The FastMCP 3.0 release notes document removal of: `BearerAuthProvider`, `Context.get_http_request()`, `dependencies` parameter, legacy resource prefix formats, `from fastmcp import Image`, `output_schema=False`, `FastMCPProxy(client=...)`, deprecated settings, and deprecated methods. Some of these may have been used transitionally during v2.x development.

**How to avoid:**
Run the codebase with `fastmcp==2.14.5` (latest v2 stable) first, checking for `DeprecationWarning` messages. Every deprecation warning in v2 becomes a hard error in v3. The specific APIs to audit:

- `mount()` with `prefix=` parameter (now `namespace=`)
- `include_tags`/`exclude_tags` on `FastMCP()` (now `disable()`)
- `_fastmcp` metadata namespace (now `fastmcp`)
- `include_fastmcp_meta` parameter (removed entirely)

**Warning signs:**

- `DeprecationWarning` messages when running tests on v2.14.5
- `TypeError: __init__() got an unexpected keyword argument` on FastMCP 3.0
- `ImportError` for removed module paths

**Phase to address:**
Pre-upgrade phase -- run deprecation audit on v2.14.5 before attempting v3 upgrade. Fix all deprecation warnings first.

---

## Technical Debt Patterns

Shortcuts that seem reasonable but create long-term problems.

| Shortcut                                                            | Immediate Benefit                                             | Long-term Cost                                                                                                                        | When Acceptable                                                           |
| ------------------------------------------------------------------- | ------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------- |
| Exposing yq expression syntax directly in tool API                  | Zero abstraction overhead, powerful queries                   | Lock-in to yq; any backend change requires expression translation layer                                                               | Acceptable for v1, must be abstracted before backend switch               |
| Using `ruamel.yaml` and `tomlkit` for writes while yq handles reads | Format preservation maintained                                | Two code paths for read vs write creates maintenance burden and potential inconsistency                                               | Acceptable -- this is the correct architecture for format preservation    |
| Hardcoding yq binary version in `DEFAULT_YQ_VERSION`                | Reproducible builds, bundled checksums avoid network requests | Version staleness; must update manually per release                                                                                   | Acceptable -- weekly update workflow mitigates                            |
| Pinning `fastmcp>=2.14.4,<3`                                        | Stability during v3 beta period                               | Missing v3 features (session state, transforms, provider architecture)                                                                | Acceptable until v3.0.0 stable release                                    |
| Pinning `ruamel.yaml>=0.18.0` without upper bound for 0.19          | API stability                                                 | 0.19.x has different C extension build requirements (`setuptools-zig` instead of `ruamel.yaml.clib`); some deployments fail on 0.19.0 | Should add explicit `<0.19` upper bound until 0.19 migration is validated |

## Integration Gotchas

Common mistakes when connecting to external services.

| Integration                          | Common Mistake                                                                | Correct Approach                                                                            |
| ------------------------------------ | ----------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------- |
| MCP clients (Claude Desktop, Cursor) | Assuming tool names can change freely between versions                        | Treat tool names as immutable public API; add new tools, never rename                       |
| SchemaStore.org                      | Caching schemas without TTL, leading to stale validation                      | Implement 24-hour TTL with stale-while-revalidate pattern (already partially done)          |
| GitHub releases (yq binary)          | Assuming GitHub CDN is always available                                       | Already handled: bundled checksums for default version, fallback to system PATH             |
| FastMCP Client test harness          | Using `from mcp.types import TextContent` which may change in MCP SDK updates | Import from `fastmcp` wrapper types when possible; pin MCP SDK version in test dependencies |
| dasel binary (if adopted)            | Assuming dasel and yq produce identical output for the same query             | Build comparison test suite: run identical queries through both backends and diff outputs   |

## Performance Traps

Patterns that work at small scale but fail as usage grows.

| Trap                                                 | Symptoms                             | Prevention                                                         | When It Breaks                                          |
| ---------------------------------------------------- | ------------------------------------ | ------------------------------------------------------------------ | ------------------------------------------------------- |
| Loading entire file into memory for dasel processing | Works for config files <1MB          | Stream processing or chunked reads for large files                 | Files >50MB; dasel loads entire document into memory    |
| Running yq subprocess per query                      | Acceptable for single queries        | Consider batch mode or persistent process for burst query patterns | >100 queries/second; subprocess fork overhead dominates |
| Schema cache directory scanning on every tool call   | Imperceptible for <10 cached schemas | Implement mtime-based skip logic with 60s TTL                      | >50 cached schemas; filesystem I/O becomes bottleneck   |
| Expression translation layer (if yq->dasel)          | Acceptable for simple paths          | Cache translated expressions; pre-compile regex matchers           | Complex expressions with pipes, filters, and functions  |

## Security Mistakes

Domain-specific security issues beyond general web security.

| Mistake                                                                 | Risk                                                            | Prevention                                                                                                               |
| ----------------------------------------------------------------------- | --------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------ |
| Accepting arbitrary file paths without allowlisting after migration     | Existing behavior, but migration may reset security assumptions | Maintain `file_path` parameter handling unchanged; do not introduce new path resolution logic during backend migration   |
| Executing user-provided expressions in new backend without sanitization | New backend may have different injection vectors than yq        | Validate expressions against LMQL constraints before passing to backend; update constraint patterns for new syntax       |
| Downloading new binary (dasel) without checksum verification            | Supply chain attack vector                                      | Replicate the yq binary management pattern: bundled checksums, lock file coordination, version pinning                   |
| Mixing yq and dasel versions that handle edge cases differently         | Silent data corruption on round-trip                            | Pin both binary versions explicitly; test round-trip fidelity (read with one, write with other, verify identical output) |

## UX Pitfalls

Common user experience mistakes in this domain.

| Pitfall                                                    | User Impact                                                       | Better Approach                                                                                |
| ---------------------------------------------------------- | ----------------------------------------------------------------- | ---------------------------------------------------------------------------------------------- |
| Changing query syntax without migration period             | All existing client prompts and cached tool descriptions break    | Dual-syntax support period: accept both yq and dasel syntax, translate internally              |
| Removing tool annotations (`readOnlyHint`) during refactor | Clients lose safety information about which tools modify files    | Preserve all MCP tool annotations through every refactoring step                               |
| Changing error message format                              | LLM agents trained on error patterns lose ability to self-correct | Keep error message structure stable; add new information, do not restructure existing messages |
| Adding new required parameters to existing tools           | Existing client calls break with missing parameter errors         | New parameters must always have defaults; use Optional types                                   |

## "Looks Done But Isn't" Checklist

Things that appear complete but are missing critical pieces.

- [ ] **Backend migration:** Often missing round-trip fidelity tests -- verify read-modify-write cycle preserves file byte-for-byte (excluding the modified value)
- [ ] **FastMCP upgrade:** Often missing test for `mask_error_details=False` behavior -- verify error details still propagate to clients after upgrade
- [ ] **Tool renaming/addition:** Often missing MCP client integration test -- verify tools appear in client tool list, not just server registration
- [ ] **Expression translation:** Often missing edge cases for yq's multiply operator (`. * overlay`) used in `data_merge` -- verify merge behavior identical in new backend
- [ ] **Binary management:** Often missing concurrent download test -- verify file locking works for new binary (portalocker pattern must be replicated)
- [ ] **LMQL constraints:** Often missing constraint pattern update -- if expression syntax changes, all constraint regex patterns must be updated simultaneously
- [ ] **Pagination:** Often missing pagination cursor compatibility -- verify cursor format unchanged after backend switch (base64-encoded JSON with offset field)
- [ ] **TOML write path:** Often missing nested structure preservation test -- verify `tomlkit` write path still handles arrays-of-tables and inline-tables correctly after any server.py refactoring

## Recovery Strategies

When pitfalls occur despite prevention, how to recover.

| Pitfall                                 | Recovery Cost | Recovery Steps                                                                                                                 |
| --------------------------------------- | ------------- | ------------------------------------------------------------------------------------------------------------------------------ |
| Comments destroyed by backend switch    | HIGH          | Restore from git; cannot recover comments once lost. Requires rollback of the backend change and user notification             |
| Tool names changed, clients broken      | MEDIUM        | Add old tool names as aliases pointing to new implementations; deploy hotfix. Client-side allowlist updates needed             |
| yq expressions broken by backend switch | HIGH          | Revert to yq backend; expression translation layer was insufficient. Requires comprehensive expression audit                   |
| FastMCP 3.0 import errors at startup    | LOW           | Pin back to `fastmcp<3`; fix imports on separate branch; redeploy                                                              |
| LMQL constraints invalid for new syntax | MEDIUM        | Disable constraint validation temporarily (return `valid: True` for all); update patterns; re-enable                           |
| Anchor expansion on write               | MEDIUM        | Re-run YAML optimizer on affected files; anchors can be recreated but user must re-verify                                      |
| ruamel.yaml 0.19 build failure          | LOW           | Pin `ruamel.yaml>=0.18.0,<0.19` explicitly; update when build toolchain (`setuptools-zig`) is available in target environments |

## Pitfall-to-Phase Mapping

How roadmap phases should address these pitfalls.

| Pitfall                            | Prevention Phase      | Verification                                                                                               |
| ---------------------------------- | --------------------- | ---------------------------------------------------------------------------------------------------------- |
| Comment destruction (dasel writes) | Backend evaluation    | Format preservation test suite passes with new backend: write value, verify comments retained              |
| Anchor expansion (dasel writes)    | Backend evaluation    | YAML optimizer integration tests pass: create anchors, write through new backend, verify anchors preserved |
| Tool name changes                  | Every phase           | Automated test asserting exact tool name set matches known list; run on every PR                           |
| Expression syntax incompatibility  | Backend abstraction   | Expression translation test suite: 100+ yq expressions translated and verified against dasel output        |
| FastMCP 3.0 API removals           | Pre-upgrade audit     | Zero `DeprecationWarning` on v2.14.5; zero `ImportError` or `TypeError` on v3.0.0                          |
| FastMCP 3.0 decorator change       | FastMCP upgrade       | Test suite passes with both `FASTMCP_DECORATOR_MODE=object` and default mode                               |
| FastMCP 3.0 deprecated API removal | Pre-upgrade audit     | Grep for all removed API names returns zero hits                                                           |
| MCP client silent failures         | Integration testing   | End-to-end test with real MCP client (Claude Desktop config) verifying all tools visible                   |
| ruamel.yaml 0.19 build breakage    | Dependency management | Pin upper bound; test in Docker with minimal build tools to verify no C extension build surprises          |
| LMQL constraint invalidation       | Backend abstraction   | Constraint validation tests updated for new syntax patterns; partial validation still works                |

## Sources

- [FastMCP 3.0 Upgrade Guide](https://gofastmcp.com/development/upgrade-guide) -- HIGH confidence, official documentation
- [FastMCP GitHub Releases](https://github.com/jlowin/fastmcp/releases) -- HIGH confidence, official release notes for v3.0.0rc2, v3.0.0rc1, v3.0.0b2, v3.0.0b1, v2.14.x
- [Dasel GitHub Repository](https://github.com/TomWright/dasel) -- HIGH confidence, official project
- [Dasel Issue #178: Preserve comments when editing files](https://github.com/TomWright/dasel/issues/178) -- HIGH confidence, confirmed open issue
- [Dasel Supported File Formats](https://daseldocs.tomwright.me/supported-file-formats) -- MEDIUM confidence, official docs
- [YQ to Dasel Migration Guide (v1)](https://daseldocs.tomwright.me/v1/examples/yq-to-dasel) -- MEDIUM confidence, v1 docs (v2 syntax differs)
- [The Silent Breakage: A Versioning Strategy for Production-Ready MCP Tools](https://medium.com/google-cloud/the-silent-breakage-a-versioning-strategy-for-production-ready-mcp-tools-fbb998e3f71f) -- MEDIUM confidence, Google Cloud community article
- [MCP Specification 2025-06-18](https://modelcontextprotocol.io/specification/2025-03-26/basic/lifecycle) -- HIGH confidence, official protocol spec
- [ruamel.yaml PyPI](https://pypi.org/project/ruamel.yaml/) -- HIGH confidence, official package page documenting 0.19 changes
- [ruamel.yaml 0.19 build issue](https://github.com/aws/bedrock-agentcore-starter-toolkit/issues/415) -- MEDIUM confidence, real-world deployment issue

---

_Pitfalls research for: MCP server upgrade/migration (mcp-json-yaml-toml)_
_Researched: 2026-02-14_

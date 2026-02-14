# Stack Research

**Domain:** MCP Server for structured data manipulation (JSON/YAML/TOML)
**Researched:** 2026-02-14
**Confidence:** MEDIUM (FastMCP 3 is RC-stage; dasel v3 is young; core recommendations are well-supported)

---

## 1. FastMCP 2.x to 3.x Migration

### Current State

| Item                      | Value                                   | Source                                                                                                   |
| ------------------------- | --------------------------------------- | -------------------------------------------------------------------------------------------------------- |
| Installed FastMCP         | 2.14.4                                  | `pyproject.toml`, `uv pip show`                                                                          |
| Installed MCP SDK         | 1.25.0                                  | `uv pip show mcp`                                                                                        |
| Latest stable FastMCP 2.x | 2.14.5                                  | [PyPI](https://pypi.org/project/fastmcp/)                                                                |
| Latest FastMCP 3.x        | 3.0.0rc2 (2026-02-14)                   | [PyPI](https://pypi.org/project/fastmcp/), [GitHub Releases](https://github.com/jlowin/fastmcp/releases) |
| FastMCP 3.x stability     | Release Candidate (API believed stable) | [FastMCP Blog](https://www.jlowin.dev/blog/fastmcp-3)                                                    |
| Pin in pyproject.toml     | `fastmcp>=2.14.4,<3`                    | `pyproject.toml` line 30                                                                                 |

**Confidence: HIGH** -- version numbers verified against PyPI and installed packages.

### FastMCP 3.0 Breaking Changes (Impact on This Project)

| Breaking Change                                        | Severity for Us | Action Required                                                                                                                             |
| ------------------------------------------------------ | --------------- | ------------------------------------------------------------------------------------------------------------------------------------------- |
| Decorators return functions (not `FunctionTool`)       | **HIGH**        | Tests extract `.fn` from `FunctionTool` wrappers in ~5 places. Must refactor test helpers or set `FASTMCP_DECORATOR_MODE=object` as bridge. |
| `get_tools()` -> `list_tools()`, returns list not dict | LOW             | Not used in server code; only in integration tests.                                                                                         |
| Context state methods now async                        | NONE            | Project does not use `ctx.get_state()`/`ctx.set_state()`.                                                                                   |
| WSTransport removed                                    | NONE            | Project uses STDIO transport.                                                                                                               |
| Auth provider env vars removed                         | NONE            | Project does not use auth.                                                                                                                  |
| Component `enable()`/`disable()` moved to server       | NONE            | Not used.                                                                                                                                   |
| Prompts use `Message` class                            | LOW             | One prompt defined; trivial change.                                                                                                         |
| Metadata namespace `_fastmcp` -> `fastmcp`             | LOW             | Not referenced in our code.                                                                                                                 |
| `mask_error_details` constructor param                 | **VERIFY**      | We pass `mask_error_details=False`. Verify this param survives in 3.x (it was not listed as removed).                                       |

**Key risk:** The decorator behavior change. Current tests do:

```python
# packages/mcp_json_yaml_toml/tests/test_server.py line 21
data_fn = server.data.fn  # Extracts from FunctionTool wrapper
```

In FastMCP 3.x, `server.data` returns the original function directly. This breaks all test extraction patterns.

### FastMCP 3.0 New Features (Relevant to This Project)

| Feature                                   | Relevance  | Why                                                                                                                                                                          |
| ----------------------------------------- | ---------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Automatic threadpool for sync tools       | **HIGH**   | Our tools call `execute_yq` (sync subprocess). Currently blocks. v3 runs sync tools in threadpool automatically -- parallel tool calls become possible without code changes. |
| Tool timeouts                             | **HIGH**   | yq subprocess can hang on malformed input. `@mcp.tool(timeout=30.0)` adds safety.                                                                                            |
| Component versioning                      | **MEDIUM** | Enables adding v2 tools alongside v1 without breaking existing clients. Useful for gradual API evolution.                                                                    |
| Hot reload (`fastmcp run --reload`)       | **MEDIUM** | Development quality-of-life improvement.                                                                                                                                     |
| Composable lifespans                      | **MEDIUM** | Could cleanly manage yq binary lifecycle (download/verify at startup).                                                                                                       |
| OpenTelemetry tracing                     | LOW        | Nice for production observability, not blocking.                                                                                                                             |
| Server composition (Providers/Transforms) | LOW        | Single-server architecture; composition not needed now.                                                                                                                      |
| Background tasks (SEP-1686)               | LOW        | Our tools are fast (<1s typically).                                                                                                                                          |
| Pagination                                | LOW        | We already implement cursor-based pagination internally.                                                                                                                     |

### Migration Recommendation

**Recommendation: Upgrade to FastMCP 3.x when 3.0.0 stable ships (estimated Q1 2026 based on RC2 timeline).**

**Confidence: MEDIUM** -- RC2 released today (2026-02-14); stable release timing is estimated.

**Rationale:**

1. The automatic threadpool alone justifies the upgrade. Our server currently blocks on `subprocess.run()` calls to yq. FastMCP 3.x runs sync tools in a threadpool, meaning multiple concurrent tool calls execute in parallel instead of sequentially. This is a free performance win.
2. Tool timeouts add a safety net we currently lack. yq subprocess calls can theoretically hang; the `timeout` decorator parameter is cleaner than managing `subprocess.run(timeout=)` ourselves.
3. The breaking changes are well-documented and minimal for our use case. The biggest impact is the decorator behavior change in tests.
4. The `<3` pin in `pyproject.toml` was prudent. Maintain it until 3.0.0 stable ships, then test and upgrade.

**Migration steps (when ready):**

1. Update pin: `fastmcp>=3.0.0,<4`
2. Remove all `.fn` extraction patterns from tests (call decorated functions directly)
3. Add `timeout=30.0` to tool decorators
4. Verify `mask_error_details=False` still works
5. Update any `PromptMessage` usage to `Message`
6. Run full test suite

---

## 2. dasel as yq Alternative or Complement

### Current yq Usage

| Metric                               | Value                                                                                       |
| ------------------------------------ | ------------------------------------------------------------------------------------------- |
| yq_wrapper.py lines                  | 934                                                                                         |
| `execute_yq` call sites in server.py | 13                                                                                          |
| Supported formats via yq             | JSON, YAML, TOML, XML, CSV, TSV, properties                                                 |
| Binary management complexity         | Platform detection, download, checksum verification, version pinning, file locking, cleanup |
| Current yq version                   | v4.52.2 (pinned)                                                                            |
| yq GitHub stars                      | ~12k                                                                                        |

### dasel v3 Assessment

| Criterion                | yq (mikefarah)                                                      | dasel v3                                                                       |
| ------------------------ | ------------------------------------------------------------------- | ------------------------------------------------------------------------------ |
| **Latest version**       | v4.52.2 (2026-01-31)                                                | v3.1.4 (2025-12-18)                                                            |
| **GitHub stars**         | ~12k                                                                | ~7.7k                                                                          |
| **Language**             | Go                                                                  | Go                                                                             |
| **Binary type**          | Static, zero-dep                                                    | Static, zero-dep                                                               |
| **Platforms**            | linux/amd64, linux/arm64, darwin/amd64, darwin/arm64, windows/amd64 | linux/amd64, linux/arm64, linux/386, darwin/amd64, darwin/arm64, windows/amd64 |
| **Checksums**            | SHA256 per-release                                                  | SHA256 per-release                                                             |
| **JSON**                 | Full (jq-like syntax)                                               | Full (CSS-like syntax)                                                         |
| **YAML**                 | Full (primary focus)                                                | Full                                                                           |
| **TOML read**            | Full                                                                | Full                                                                           |
| **TOML write**           | **No** (read-only)                                                  | Full                                                                           |
| **XML**                  | Full                                                                | Full                                                                           |
| **CSV**                  | Full                                                                | Full                                                                           |
| **HCL**                  | Full                                                                | Full                                                                           |
| **Format conversion**    | Via `-o` flag                                                       | Via `-o` flag                                                                  |
| **Query language**       | jq-like expressions                                                 | Custom query language (v3 revamp)                                              |
| **Ecosystem maturity**   | Very mature, extensive docs                                         | v3 is "in active development" per official docs                                |
| **Comment preservation** | Via ruamel.yaml/tomlkit (not yq)                                    | Not guaranteed for round-trip                                                  |

**Confidence: MEDIUM** -- dasel features verified via [Context7 dasel docs](https://daseldocs.tomwright.me) and [GitHub releases](https://github.com/TomWright/dasel/releases). yq verified via project's pinned checksums and usage.

### Key Finding: dasel Does NOT Solve the Core Pain Point

The project's pain points are **binary download reliability and platform complexity** (the 934-line wrapper). Switching from yq to dasel would require:

1. Rewriting all 13 `execute_yq` call sites to use dasel's different query syntax
2. Rewriting the entire binary management layer (same complexity -- download, checksum, platform detection)
3. Rewriting all yq-related tests
4. Learning dasel v3's revamped query syntax (which is still marked "in active development")

The binary management code would be essentially identical in structure -- both tools are single Go binaries downloaded from GitHub releases with SHA256 verification. Switching the binary being managed does not reduce management complexity.

### dasel Advantages Over yq

1. **TOML write support**: dasel can write TOML natively; yq cannot. Our project currently works around this with `tomlkit` for TOML writes (see `toml_utils.py`). However, `tomlkit` preserves comments and formatting, which dasel does not guarantee.
2. **Broader format support**: dasel adds INI format support.

### dasel Disadvantages vs yq

1. **v3 maturity**: Official docs state "Dasel V3 is in active development, alongside this documentation." This is not production-ready language.
2. **Query syntax instability**: v3 revamped the entire query syntax from v2. The `put` and `delete` commands were removed in favor of inline query modifications with `--root`. This is a significant API break that signals the syntax may still evolve.
3. **Smaller ecosystem**: ~7.7k stars vs ~12k for yq. Fewer Stack Overflow answers, fewer examples for LLMs to reference.
4. **jq compatibility**: yq's jq-like syntax is a significant advantage because LLMs (the primary consumers of our tools) are well-trained on jq syntax. dasel's custom syntax has less training data.

### Recommendation: Stay with yq

**Recommendation: Do NOT switch to dasel. Stay with yq (mikefarah).**

**Confidence: HIGH**

**Rationale:**

1. dasel does not reduce binary management complexity (the stated pain point).
2. yq's jq-like syntax is better understood by LLMs (our users).
3. dasel v3 is explicitly "in active development" with recent syntax breaks.
4. The one advantage (TOML write) is already handled cleanly by `tomlkit`.
5. Migration cost is high (13 call sites + tests + new syntax) with no clear payoff.

---

## 3. Eliminating the Python Wrapper Entirely

### Can yq or dasel Serve MCP Natively?

**Verdict: NO**

**Confidence: HIGH** -- searched for "yq MCP server", "dasel MCP server", "yq model context protocol", "dasel model context protocol". Zero results. Neither tool has any MCP awareness.

**Why this is structurally impossible:**

MCP servers must implement the [Model Context Protocol](https://modelcontextprotocol.io/specification/2025-11-25), which requires:

1. JSON-RPC 2.0 message handling over STDIO or HTTP
2. Tool registration with schemas
3. Resource and prompt management
4. Session lifecycle management

yq and dasel are stateless CLI tools that process one input and produce one output. They have no concept of sessions, tool registration, or protocol compliance. Making them serve MCP would require writing a wrapper -- which is exactly what this project is.

### Alternative: Pure Python (Eliminate the Binary Entirely)

The project already depends on `ruamel.yaml` and `tomlkit` for format-preserving operations. A pure-Python approach would:

| Operation         | Current Approach                | Pure Python Alternative                            |
| ----------------- | ------------------------------- | -------------------------------------------------- |
| JSON read/query   | yq subprocess                   | `orjson` (already a dependency) + JSONPath library |
| JSON write        | yq subprocess                   | `orjson`                                           |
| YAML read/query   | yq subprocess                   | `ruamel.yaml` (already a dependency)               |
| YAML write        | yq subprocess + ruamel.yaml     | `ruamel.yaml`                                      |
| TOML read         | yq subprocess                   | `tomlkit` (already a dependency)                   |
| TOML write        | `tomlkit` (yq can't write TOML) | `tomlkit`                                          |
| Format conversion | yq subprocess                   | Parse with source lib, serialize with target lib   |
| jq-like queries   | yq subprocess (jq syntax)       | `python-jq` or `jmespath` or custom JSONPath       |

**Advantages of pure Python:**

1. **Eliminates 934-line binary wrapper entirely** -- the stated pain point
2. **Zero binary downloads** -- no platform detection, no checksums, no file locking, no network requests at install time
3. **Three fewer failure modes** -- no binary-not-found, no download failures, no checksum mismatches
4. **Simpler CI/CD** -- no binary caching, no platform matrix for binary downloads
5. **Libraries already in dependencies** -- `ruamel.yaml`, `tomlkit`, `orjson` are all present

**Disadvantages of pure Python:**

1. **Query language gap**: yq provides jq-like expression evaluation. Replicating this in pure Python requires either `python-jq` (C extension, compilation issues) or `jmespath` (different syntax than jq) or implementing a subset.
2. **Feature parity effort**: 13 `execute_yq` call sites with various expression patterns. Each needs translation.
3. **Performance**: For large files, compiled Go binary (yq) may be faster than Python parsing. Unlikely to matter for typical config file sizes.
4. **Expression flexibility**: yq/jq expressions are powerful and well-known. A pure Python query engine would need to match user expectations.

**Recommendation: Evaluate pure Python as a Phase 2 initiative.**

**Confidence: MEDIUM**

The pure Python path is the only approach that actually eliminates the binary management pain point. However, it requires careful evaluation of query language alternatives. The critical question is: what jq-like query capabilities do we actually use in the 13 call sites, and can `jmespath` or a JSONPath library cover them?

---

## Recommended Stack

### Core Technologies

| Technology     | Version                             | Purpose                        | Why Recommended                                                              |
| -------------- | ----------------------------------- | ------------------------------ | ---------------------------------------------------------------------------- |
| Python         | 3.11-3.12+                          | Runtime                        | Already targeted; 3.11 minimum for `StrEnum`, `tomllib`                      |
| FastMCP        | 2.14.4 (now) -> 3.0.0 (when stable) | MCP server framework           | Only serious Python MCP framework. v3 adds threadpool, timeouts, versioning. |
| MCP SDK        | 1.25.0+                             | Protocol implementation        | Required by FastMCP; tracks MCP spec versions                                |
| yq (mikefarah) | v4.52.2 (pinned)                    | Data query engine              | Mature, jq-compatible syntax, well-understood by LLMs                        |
| ruamel.yaml    | >=0.18.0,<0.19                      | YAML with comment preservation | Only Python YAML library that preserves comments and anchors                 |
| tomlkit        | >=0.14.0                            | TOML with comment preservation | Built for Poetry; preserves style, comments, formatting                      |
| orjson         | >=3.11.6                            | Fast JSON parsing              | 3-10x faster than stdlib `json`; already in dependencies                     |

### Supporting Libraries

| Library     | Version       | Purpose               | When to Use                                |
| ----------- | ------------- | --------------------- | ------------------------------------------ |
| httpx       | >=0.28.1      | HTTP client           | Binary downloads, schema fetching          |
| portalocker | >=3.1.1       | File locking          | Cross-platform lock during binary download |
| jsonschema  | >=4.26.0      | Schema validation     | `data_schema` tool validation              |
| lmql        | >=0.7.3       | Constraint validation | Input constraint system                    |
| pydantic    | (via FastMCP) | Data modeling         | Tool parameters, result types              |

### Development Tools

| Tool                | Purpose              | Notes                                     |
| ------------------- | -------------------- | ----------------------------------------- |
| uv                  | Package management   | Project standard; replaces pip/poetry     |
| ruff                | Linting + formatting | 500+ rules configured in `pyproject.toml` |
| mypy + basedpyright | Type checking        | Dual type checker setup (strict)          |
| pytest + xdist      | Testing              | Parallel test execution                   |
| prek                | Pre-commit runner    | Scoped verification with `--files`        |

## Installation

```bash
# Core (managed by uv)
uv sync

# Pin to FastMCP 2.x (current)
# pyproject.toml: fastmcp>=2.14.4,<3

# When upgrading to FastMCP 3.x:
# pyproject.toml: fastmcp>=3.0.0,<4
```

## Alternatives Considered

| Recommended    | Alternative                                  | When to Use Alternative                                                                                                                          |
| -------------- | -------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------ |
| yq (mikefarah) | dasel v3                                     | Only if you need native TOML write from CLI AND don't need jq syntax compatibility AND are willing to accept v3's "in active development" status |
| yq (mikefarah) | Pure Python (ruamel.yaml + tomlkit + orjson) | When binary management pain exceeds query language migration cost. Evaluate after auditing actual jq expression usage across 13 call sites.      |
| FastMCP        | Raw MCP SDK (`mcp` package)                  | Never for this project. FastMCP provides decorators, error handling, client testing, and now threadpool/timeout that raw SDK lacks.              |
| ruamel.yaml    | PyYAML                                       | Never. PyYAML does not preserve comments, anchors, or formatting.                                                                                |
| tomlkit        | tomllib (stdlib)                             | Never for writes. `tomllib` is read-only (Python 3.11+). Acceptable for read-only validation if tomlkit is too heavy (it isn't).                 |

## What NOT to Use

| Avoid                         | Why                                                                                                             | Use Instead                                       |
| ----------------------------- | --------------------------------------------------------------------------------------------------------------- | ------------------------------------------------- |
| dasel v3 (as yq replacement)  | v3 query syntax is unstable ("in active development"), smaller ecosystem, does not solve binary management pain | yq v4.x (stable, jq-compatible)                   |
| python-jq                     | C extension; fails to compile on many platforms; defeats purpose of eliminating binary deps                     | `jmespath` if going pure Python                   |
| PyYAML                        | Destroys comments, anchors, formatting on round-trip                                                            | `ruamel.yaml`                                     |
| FastMCP 3.0.0b1/b2            | Beta; API changed between b1 and b2 (e.g., `ui=` -> `app=`)                                                     | FastMCP 2.14.x (stable) or 3.0.0rc2+ (if testing) |
| `pip install` / bare `python` | Project convention violation per CLAUDE.md                                                                      | `uv sync`, `uv run`                               |

## Stack Patterns by Variant

**If staying with yq (recommended for now):**

- Keep `fastmcp>=2.14.4,<3` until 3.0.0 stable
- Keep yq v4.52.2 pinned with bundled checksums
- Keep `tomlkit` for TOML writes (yq can't write TOML)
- Keep `ruamel.yaml` for YAML comment preservation

**If migrating to pure Python (Phase 2 evaluation):**

- Replace `execute_yq` calls with direct `ruamel.yaml`/`tomlkit`/`orjson` calls
- Add `jmespath>=1.0.1` for query expressions (different syntax than jq -- requires user-facing documentation)
- Remove `httpx` dependency if only used for binary downloads (verify other uses first)
- Remove `portalocker` dependency entirely
- Delete `yq_wrapper.py` (934 lines) and all binary management code

**If upgrading to FastMCP 3.x:**

- Update pin to `fastmcp>=3.0.0,<4`
- Refactor test helpers that extract `.fn` from decorators
- Add `timeout=30.0` to all `@mcp.tool` decorators
- Remove `FASTMCP_DECORATOR_MODE=object` env var after test refactor
- Verify `mask_error_details=False` parameter compatibility

## Version Compatibility

| Package            | Compatible With                                         | Notes                                    |
| ------------------ | ------------------------------------------------------- | ---------------------------------------- |
| FastMCP 2.14.x     | MCP SDK 1.25.x                                          | Current production combination           |
| FastMCP 3.0.0rc2   | MCP SDK 1.25.x-1.26.x                                   | RC; API believed stable but not GA       |
| ruamel.yaml 0.18.x | Python 3.11-3.12                                        | 0.19.x has different API -- stay on 0.18 |
| yq v4.52.2         | All platforms (linux/darwin amd64+arm64, windows/amd64) | Pinned with bundled SHA256 checksums     |
| dasel v3.1.4       | Same platforms as yq                                    | NOT recommended; listed for reference    |

## Sources

- [FastMCP Upgrade Guide](https://gofastmcp.com/development/upgrade-guide) -- full breaking changes list (HIGH confidence)
- [What's New in FastMCP 3.0](https://www.jlowin.dev/blog/fastmcp-3-whats-new) -- feature overview (HIGH confidence)
- [FastMCP PyPI](https://pypi.org/project/fastmcp/) -- version history (HIGH confidence)
- [FastMCP GitHub Releases](https://github.com/jlowin/fastmcp/releases) -- RC2 release (HIGH confidence)
- [Context7 FastMCP docs](/llmstxt/gofastmcp_llms-full_txt) -- migration patterns (HIGH confidence)
- [Context7 dasel docs](/websites/daseldocs_tomwright_me) -- dasel v3 capabilities (MEDIUM confidence)
- [dasel GitHub](https://github.com/TomWright/dasel) -- release history, stars (MEDIUM confidence)
- [dasel v3 docs](https://daseldocs.tomwright.me) -- "in active development" status (MEDIUM confidence)
- [yq GitHub Releases](https://github.com/mikefarah/yq/releases) -- v4.52.2 release (HIGH confidence)
- [MCP Specification](https://modelcontextprotocol.io/specification/2025-11-25) -- protocol requirements (HIGH confidence)
- [MCP Python SDK PyPI](https://pypi.org/project/mcp/) -- version 1.25.0-1.26.0 (HIGH confidence)

---

_Stack research for: mcp-json-yaml-toml MCP server tooling upgrade_
_Researched: 2026-02-14_

# Phase 3: FastMCP 3.x Migration - Research

**Researched:** 2026-02-14
**Domain:** FastMCP framework migration, async threadpool, structured output, JSON Schema validation
**Confidence:** HIGH

## Summary

FastMCP 3.x represents a major architectural evolution from 2.x, introducing composable providers and transforms, automatic threadpool execution for synchronous functions, native tool timeouts, and automatic outputSchema generation from Pydantic models. The migration path is well-documented and the vast majority of servers require minimal code changes (primarily import updates and async state methods). For this project, the migration unlocks free concurrent execution of yq subprocess calls without manual thread management, structured output schemas for all Pydantic-returning tools, and timeout protection for long-running operations.

**Primary recommendation:** Migrate to FastMCP 3.x after stable release (currently 3.0.0rc2) by updating pyproject.toml dependency, changing import statements, converting state methods to async, and optionally adding timeout parameters to tools. The Phase 2 Pydantic models will automatically generate outputSchema without additional code.

## Standard Stack

### Core

| Library    | Version    | Purpose                               | Why Standard                                                                   |
| ---------- | ---------- | ------------------------------------- | ------------------------------------------------------------------------------ |
| fastmcp    | >=3.0.0,<4 | MCP server framework                  | Official Python framework with composable architecture and production features |
| pydantic   | >=2.0      | Data validation and structured output | FastMCP 3.x auto-generates outputSchema from Pydantic return types             |
| jsonschema | >=4.26.0   | JSON Schema validation (existing)     | Python standard for schema validation, supports Draft 2020-12                  |

### Supporting

| Library           | Version  | Purpose                     | When to Use                                                         |
| ----------------- | -------- | --------------------------- | ------------------------------------------------------------------- |
| httpx             | >=0.28.1 | HTTP client (existing)      | Already used for schema $ref retrieval, compatible with FastMCP 3.x |
| opentelemetry-api | Latest   | Observability tracing       | FastMCP 3.x has native OTEL instrumentation (Phase 4 requirement)   |
| opentelemetry-sdk | Latest   | OTEL exporter configuration | Required for Phase 4 OTEL integration                               |

### Alternatives Considered

| Instead of                       | Could Use                 | Tradeoff                                                                                     |
| -------------------------------- | ------------------------- | -------------------------------------------------------------------------------------------- |
| FastMCP 3.x automatic threadpool | Manual ThreadPoolExecutor | Manual executor is deprecated pattern, FastMCP 3.x handles this transparently                |
| FastMCP 3.x outputSchema         | Manual schema definitions | Manual schemas require maintenance, Pydantic auto-generation is zero-cost                    |
| Draft 2020-12 validator default  | Keep Draft 7 default      | Draft 7 is legacy (2019), Draft 2020-12 is current standard with better array/tuple handling |

**Installation:**

```bash
# Update pyproject.toml dependency
uv remove fastmcp  # Remove old constraint
uv add "fastmcp>=3.0.0,<4"
```

## Architecture Patterns

### Recommended Migration Sequence

```
1. Wait for FastMCP 3.0 stable release (currently 3.0.0rc2)
2. Update import statements (from mcp.server.fastmcp → from fastmcp)
3. Convert Context state methods to async (await ctx.get_state())
4. Test all 393 tests pass unchanged
5. Add timeout parameters to long-running tools (optional enhancement)
6. Verify outputSchema auto-generation for Pydantic models
7. Update JSON Schema default validator to Draft 2020-12
```

### Pattern 1: Import Update (Required)

**What:** Change from legacy mcp.server.fastmcp to new fastmcp top-level import
**When to use:** All servers migrating from 2.x to 3.x
**Example:**

```python
# Source: https://github.com/jlowin/fastmcp/blob/v3.0.0rc2/docs/development/upgrade-guide.mdx

# Before (FastMCP 2.x)
from mcp.server.fastmcp import FastMCP

# After (FastMCP 3.x)
from fastmcp import FastMCP
```

### Pattern 2: Async State Methods (Required if using state)

**What:** State persistence methods are now async for distributed backend support
**When to use:** Any code using ctx.get_state() or ctx.set_state()
**Example:**

```python
# Source: https://github.com/jlowin/fastmcp/blob/v3.0.0rc2/docs/development/upgrade-guide.mdx

# Before (FastMCP 2.x)
ctx.set_state("key", "value")
value = ctx.get_state("key")

# After (FastMCP 3.x)
await ctx.set_state("key", "value")
value = await ctx.get_state("key")
```

### Pattern 3: Automatic Threadpool Execution

**What:** Synchronous tools automatically run in threadpool without blocking event loop
**When to use:** All synchronous functions performing blocking I/O (like subprocess calls)
**Example:**

```python
# Source: https://www.jlowin.dev/blog/fastmcp-3-whats-new

# FastMCP 3.x - automatic threadpool dispatch
@mcp.tool
def data_query(file_path: str, query: str) -> QueryResponse:
    # subprocess.run() executes in threadpool automatically
    # Multiple concurrent calls execute in parallel
    result = execute_yq(query, input_file=file_path)
    return QueryResponse(...)
```

**Impact:** yq subprocess calls in this project will execute concurrently without manual ThreadPoolExecutor management.

### Pattern 4: Tool Timeouts

**What:** Limit foreground execution time with timeout parameter
**When to use:** Tools that may hang or take unbounded time (file operations, subprocess calls)
**Example:**

```python
# Source: https://www.jlowin.dev/blog/fastmcp-3-whats-new

@mcp.tool(timeout=30.0)
def data_convert(file_path: str, output_format: str) -> ConvertResponse:
    """Convert file format with 30-second timeout."""
    # Raises MCP error code -32000 if exceeds timeout
    ...
```

### Pattern 5: Automatic outputSchema from Pydantic

**What:** FastMCP 3.x auto-generates JSON Schema from Pydantic return types
**When to use:** All tools returning Pydantic models (already implemented in Phase 2)
**Example:**

```python
# Source: https://www.jlowin.dev/blog/fastmcp-3-whats-new

# Phase 2 already returns Pydantic models
@mcp.tool
def data_query(...) -> QueryResponse:
    return QueryResponse(...)

# FastMCP 3.x automatically generates outputSchema in tool listing:
# {
#   "name": "data_query",
#   "output_schema": {
#     "type": "object",
#     "properties": {
#       "success": {"type": "boolean"},
#       "result": {...}
#     }
#   }
# }
```

### Pattern 6: JSON Schema Draft 2020-12 Default

**What:** Update validator default from Draft 7 to Draft 2020-12
**When to use:** Schema validation service after migration
**Example:**

```python
# Source: https://json-schema.org/draft/2020-12/release-notes

# Current (Draft 7 default)
schema_dialect = schema.get("$schema", "")
if "draft/2020-12" in schema_dialect:
    Draft202012Validator(schema, registry=registry).validate(data)
else:
    Draft7Validator(schema, registry=registry).validate(data)  # Default

# After (Draft 2020-12 default)
schema_dialect = schema.get("$schema", "")
if "draft-07" in schema_dialect or "draft/7" in schema_dialect:
    Draft7Validator(schema, registry=registry).validate(data)
else:
    Draft202012Validator(schema, registry=registry).validate(data)  # Default
```

### Anti-Patterns to Avoid

- **Manual ThreadPoolExecutor:** FastMCP 3.x handles sync function dispatch automatically - do not add executor boilerplate
- **Manual outputSchema definitions:** Pydantic models auto-generate schemas - do not maintain parallel schema definitions
- **Mixing state serializable modes:** Use serializable=False only for request-scoped non-serializable objects, not session state
- **Setting FASTMCP_DECORATOR_MODE=object:** Only use for v2 compatibility testing, not production (decorators return functions in v3)

## Don't Hand-Roll

| Problem                           | Don't Build                          | Use Instead                      | Why                                                                                            |
| --------------------------------- | ------------------------------------ | -------------------------------- | ---------------------------------------------------------------------------------------------- |
| Concurrent subprocess execution   | Custom ThreadPoolExecutor management | FastMCP 3.x automatic threadpool | FastMCP dispatches sync functions to threadpool transparently, handles pool sizing and cleanup |
| Tool output schemas               | Manual JSON Schema definitions       | Pydantic model auto-generation   | FastMCP 3.x generates outputSchema from return type annotations automatically                  |
| Long-running operation protection | Custom timeout decorator/wrapper     | FastMCP 3.x timeout parameter    | Built-in timeout with standardized MCP error codes, integrates with middleware                 |
| Component visibility control      | Custom filtering logic               | FastMCP 3.x enable()/disable()   | Provider and server-level visibility transforms with tag/name/version filtering                |

**Key insight:** FastMCP 3.x moved to composable provider/transform architecture - features that required custom code in 2.x are now primitives you compose. Fighting the framework by building parallel systems creates maintenance burden and loses framework improvements.

## Common Pitfalls

### Pitfall 1: Migrating Before Stable Release

**What goes wrong:** Pre-release versions (3.0.0rc2) may have breaking changes before stable
**Why it happens:** Desire to get new features immediately
**How to avoid:** Wait for stable 3.0.0 release before production migration (rc2 is for testing)
**Warning signs:** GitHub releases show "rc" or "beta" tags, PyPI shows pre-release version

### Pitfall 2: Forgetting Async State Methods

**What goes wrong:** Runtime errors when calling ctx.get_state() without await
**Why it happens:** State methods were sync in FastMCP 2.x, now async in 3.x
**How to avoid:** Search codebase for all ctx.get_state and ctx.set_state calls, add await
**Warning signs:** TypeError: object dict can't be used in 'await' expression

### Pitfall 3: Assuming Draft 2020-12 is Backward Compatible

**What goes wrong:** Schemas using items/additionalItems (tuple syntax) behave differently
**Why it happens:** Draft 2020-12 renamed items→prefixItems, additionalItems→items for tuples
**How to avoid:** Test schema validation with both drafts, update tuple-based schemas to new syntax
**Warning signs:** Tuple validation passes on Draft 7 but fails on Draft 2020-12

### Pitfall 4: Mixing Decorator Modes

**What goes wrong:** Tests fail because decorated functions return component objects instead of being callable
**Why it happens:** Setting FASTMCP_DECORATOR_MODE=object globally affects all decorators
**How to avoid:** Only use FASTMCP_DECORATOR_MODE=object for v2 compatibility testing, remove for production
**Warning signs:** TypeError: 'Tool' object is not callable

### Pitfall 5: Not Testing Concurrent Execution

**What goes wrong:** Race conditions or resource contention when multiple tools run in parallel
**Why it happens:** FastMCP 2.x tools ran sequentially, FastMCP 3.x automatic threadpool enables concurrency
**How to avoid:** Add concurrent execution tests for tools with shared state or file operations
**Warning signs:** Intermittent test failures, file locking errors, race condition bugs

### Pitfall 6: Timeout Too Aggressive for yq Operations

**What goes wrong:** Large file operations timeout prematurely
**Why it happens:** Default timeout may be too short for production workloads
**How to avoid:** Profile actual yq operation times, set timeout conservatively (60s+), monitor timeout errors
**Warning signs:** MCP error code -32000 (timeout) on legitimate operations

## Code Examples

Verified patterns from official sources:

### FastMCP 3.x Server Initialization

```python
# Source: https://github.com/jlowin/fastmcp/blob/v3.0.0rc2/README.md

from fastmcp import FastMCP

mcp = FastMCP("mcp-json-yaml-toml", mask_error_details=False)

@mcp.tool
def data(file_path: str, operation: str) -> dict[str, Any]:
    """Get, set, or delete data in JSON, YAML, or TOML files."""
    return {...}

if __name__ == "__main__":
    mcp.run()
```

### Sync Tool with Automatic Threadpool

```python
# Source: https://www.jlowin.dev/blog/fastmcp-3-whats-new

import time

@mcp.tool
def slow_tool():
    time.sleep(10)  # No longer blocks other requests
    return "done"

# Three concurrent calls execute in parallel (~10s total)
# instead of sequentially (30s total)
```

### Tool with Timeout

```python
# Source: https://www.jlowin.dev/blog/fastmcp-3-whats-new

@mcp.tool(timeout=30.0)
async def fetch_data(url: str) -> dict:
    """Fetch with 30-second timeout."""
    # Raises MCP error code -32000 if exceeds timeout
    result = await httpx.get(url)
    return result.json()
```

### Pydantic Model Auto-Schema

```python
# Source: https://www.jlowin.dev/blog/fastmcp-3-whats-new
# Combined with Phase 2 implementation

from pydantic import BaseModel, Field

class QueryResponse(BaseModel):
    """Response from data_query tool."""
    success: bool = Field(description="Whether operation succeeded")
    result: Any = Field(description="Query result or error details")
    cursor: str | None = Field(default=None, description="Pagination cursor")

@mcp.tool
def data_query(file_path: str, query: str) -> QueryResponse:
    """Query file with yq expression."""
    result = execute_yq(query, input_file=file_path)
    return QueryResponse(success=True, result=result.data)

# FastMCP 3.x automatically generates outputSchema from QueryResponse
# No manual schema definition required
```

### JSON Schema Draft 2020-12 Tuple Migration

```python
# Source: https://json-schema.org/draft/2020-12/release-notes

# Draft 7 tuple syntax
{
    "items": [
        {"type": "string"},
        {"type": "number"}
    ],
    "additionalItems": false
}

# Draft 2020-12 tuple syntax
{
    "prefixItems": [
        {"type": "string"},
        {"type": "number"}
    ],
    "items": false
}
```

### Enable/Disable Components (replaces enabled parameter)

```python
# Source: https://github.com/jlowin/fastmcp/blob/v3.0.0rc2/v3-notes/visibility.md

# Before (FastMCP 2.x) - BROKEN
@mcp.tool(enabled=False)
def my_tool(): ...

# After (FastMCP 3.x)
@mcp.tool
def my_tool(): ...

mcp.disable(names={"my_tool"})

# Or disable by tag
mcp.disable(tags={"admin"})
```

## State of the Art

| Old Approach                               | Current Approach                           | When Changed                | Impact                                                          |
| ------------------------------------------ | ------------------------------------------ | --------------------------- | --------------------------------------------------------------- |
| Manual ThreadPoolExecutor for sync tools   | Automatic threadpool dispatch              | FastMCP 3.0                 | Zero-cost concurrency for subprocess calls                      |
| Manual outputSchema in @mcp.tool decorator | Auto-generation from Pydantic return types | FastMCP 3.0                 | Eliminates schema maintenance burden                            |
| Draft 7 JSON Schema default                | Draft 2020-12 default                      | JSON Schema 2020-12 release | Better array/tuple syntax, $dynamicRef, format vocabulary split |
| Component-level enable/disable             | Server-level visibility system             | FastMCP 3.0                 | Centralized control, tag-based filtering                        |
| sync ctx.get_state() / ctx.set_state()     | async state methods                        | FastMCP 3.0                 | Enables distributed storage backends                            |
| from mcp.server.fastmcp import             | from fastmcp import                        | FastMCP 3.0                 | Cleaner top-level API                                           |

**Deprecated/outdated:**

- **ThreadPoolExecutor wrappers:** FastMCP 3.x handles this automatically for sync functions
- **enabled parameter on decorators:** Use mcp.enable() / mcp.disable() instead
- **tool.disable() component methods:** Use server.disable(names={...}) instead
- **Draft 7 as default validator:** JSON Schema 2020-12 is current standard
- **Manual schema definitions for Pydantic models:** Auto-generation is zero-cost

## Open Questions

1. **FastMCP 3.0 Stable Release Timeline**
   - What we know: Currently at 3.0.0rc2 (release candidate 2)
   - What's unclear: Estimated stable release date
   - Recommendation: Monitor [FastMCP GitHub releases](https://github.com/jlowin/fastmcp/releases) for 3.0.0 stable, do not migrate until then

2. **Timeout Values for yq Operations**
   - What we know: FastMCP 3.x supports timeout parameter on @mcp.tool
   - What's unclear: Actual timeout needed for large YAML/TOML files in production
   - Recommendation: Profile yq operations during Phase 3 implementation, set conservative values (60s+), monitor timeout errors

3. **JSON Schema Draft 2020-12 Breaking Changes in Existing Schemas**
   - What we know: items/additionalItems syntax changed for tuples
   - What's unclear: Whether project has tuple-based schemas in validation
   - Recommendation: Audit schema files for tuple syntax before changing default validator

4. **OpenTelemetry Configuration**
   - What we know: FastMCP 3.x has native OTEL instrumentation
   - What's unclear: Optimal OTEL configuration for this project's deployment
   - Recommendation: Defer OTEL configuration to Phase 4 (separate from migration)

## Sources

### Primary (HIGH confidence)

- [FastMCP Context7 /jlowin/fastmcp/v3.0.0rc2](https://github.com/jlowin/fastmcp/tree/v3.0.0rc2) - Migration patterns, API changes, feature documentation
- [What's New in FastMCP 3.0](https://www.jlowin.dev/blog/fastmcp-3-whats-new) - Comprehensive feature guide with examples
- [FastMCP 3.0 Upgrade Guide](https://github.com/jlowin/fastmcp/blob/main/docs/development/upgrade-guide.mdx) - Official breaking changes and migration steps
- [JSON Schema 2020-12 Release Notes](https://json-schema.org/draft/2020-12/release-notes) - Draft 2020-12 changes from Draft 7

### Secondary (MEDIUM confidence)

- [Introducing FastMCP 3.0](https://www.jlowin.dev/blog/fastmcp-3) - High-level feature overview
- [FastMCP GitHub Releases](https://github.com/jlowin/fastmcp/releases) - Version history and release notes
- [Tools - FastMCP Documentation](https://gofastmcp.com/servers/tools) - Tool configuration patterns

### Tertiary (LOW confidence)

- [FastMCP 3.0 efficiency article](https://medium.com/@ktg.one/fastmcp-3-0-cuz-were-efficiency-junkies-60a148cb7212) - Community perspective on features
- [Building MCP Server with FastMCP Guide](https://mcpcat.io/guides/building-mcp-server-python-fastmcp/) - General FastMCP patterns

## Metadata

**Confidence breakdown:**

- Standard stack: HIGH - FastMCP 3.x is official framework, Pydantic integration documented in Context7
- Architecture: HIGH - Migration patterns verified in official upgrade guide and Context7 docs
- Pitfalls: HIGH - Breaking changes documented in upgrade guide, tuple syntax changes in JSON Schema spec
- Automatic threadpool: HIGH - Confirmed in "What's New" blog and Context7 documentation
- outputSchema auto-generation: HIGH - Documented in Context7 examples and FastMCP 3.x release notes
- JSON Schema Draft 2020-12: HIGH - Official JSON Schema specification and release notes

**Research date:** 2026-02-14
**Valid until:** 2026-03-14 (30 days for stable framework, FastMCP 3.0 stable may release during this window)

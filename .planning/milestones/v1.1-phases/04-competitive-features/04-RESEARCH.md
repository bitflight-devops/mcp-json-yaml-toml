# Phase 4: Competitive Features - Research

**Researched:** 2026-02-15
**Domain:** Config file diffing (FEAT-01) and OpenTelemetry observability (FEAT-02)
**Confidence:** HIGH

## Summary

Phase 4 adds two independent features that require no architectural changes to the existing codebase. Both build on top of the Phase 1-3 foundation (backends, services, tools architecture, FastMCP 3.x, Pydantic response models).

**FEAT-01 (Config Diff):** A new `data_diff` tool that compares two configuration files and returns a structured diff. The tool follows the same pattern as `data_merge` (two file inputs, cross-format support, Pydantic response model). Implementation uses `deepdiff` (v8.6.1), a mature Python library for deep comparison of nested data structures. The diff result is serializable to JSON via `to_dict()`, fitting directly into the existing response model pattern.

**FEAT-02 (OpenTelemetry):** FastMCP 3.0.0rc2 (already installed) includes native OpenTelemetry instrumentation. The `opentelemetry-api` package (v1.39.1) is already a transitive dependency of FastMCP. Instrumentation is always active as no-ops. Users "bring their own SDK" by installing `opentelemetry-sdk` and `opentelemetry-exporter-otlp` and configuring before server start. The server code requires zero changes for basic tracing -- every tool call, resource read, and prompt render is automatically traced. The only implementation work is: (1) adding optional OTEL SDK dependencies for users who want tracing, (2) documenting the configuration pattern, and (3) optionally adding custom spans for yq subprocess execution visibility.

**Primary recommendation:** Implement FEAT-01 and FEAT-02 as two independent plans. FEAT-01 requires a new dependency (`deepdiff`), a new tool module (`tools/diff.py`), a new service function, a new response model, and tests. FEAT-02 requires optional dependencies, a telemetry configuration module, and integration tests verifying span emission.

## Standard Stack

### Core

| Library           | Version                    | Purpose                                   | Why Standard                                                                                                                                                                                  |
| ----------------- | -------------------------- | ----------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| deepdiff          | >=8.6.1                    | Deep comparison of nested data structures | 8.5k+ GitHub stars, maintained, handles dict/list/set diff with path reporting, JSON-serializable output via `to_dict()` and `to_json()`. Only serious Python library for structured diffing. |
| opentelemetry-api | 1.39.1 (already installed) | OTEL API for trace instrumentation        | Already a FastMCP transitive dependency. Provides tracer, spans, context propagation.                                                                                                         |
| fastmcp.telemetry | (bundled with FastMCP 3.x) | FastMCP native instrumentation            | Provides `get_tracer()`, automatic span creation for all MCP operations, MCP semantic conventions.                                                                                            |

### Supporting (Optional - for OTEL export)

| Library                                | Version  | Purpose                                  | When to Use                                                                 |
| -------------------------------------- | -------- | ---------------------------------------- | --------------------------------------------------------------------------- |
| opentelemetry-sdk                      | >=1.39.0 | OTEL SDK for trace collection and export | Users who want to collect and export traces                                 |
| opentelemetry-exporter-otlp-proto-grpc | >=1.39.0 | OTLP gRPC exporter                       | Users exporting to OTLP-compatible backends (Jaeger, Grafana Tempo, etc.)   |
| opentelemetry-exporter-otlp-proto-http | >=1.39.0 | OTLP HTTP exporter                       | Alternative to gRPC for environments where gRPC is blocked                  |
| opentelemetry-distro                   | >=0.50b0 | Auto-instrumentation bootstrap           | Users who want zero-code instrumentation via `opentelemetry-instrument` CLI |

### Alternatives Considered

| Instead of                       | Could Use             | Tradeoff                                                                                                                                                                             |
| -------------------------------- | --------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| deepdiff                         | dictdiffer            | dictdiffer is simpler but less maintained (last release 2021), no type change detection, no JSON serialization. DeepDiff is actively maintained with 304+ code snippets in Context7. |
| deepdiff                         | jsondiff              | jsondiff only handles JSON dicts, not arbitrary Python objects. DeepDiff handles the parsed output of all three formats uniformly.                                                   |
| deepdiff                         | Manual recursive diff | Reinventing wheel. DeepDiff handles edge cases (list reordering, type changes, nested paths, circular references) that a manual implementation would miss.                           |
| opentelemetry-sdk (optional dep) | Prometheus client     | OTEL is the industry standard and FastMCP has native support. Prometheus is metrics-only, no tracing.                                                                                |

### Installation

```bash
# Required for FEAT-01
uv add deepdiff

# Optional for FEAT-02 (users install these themselves)
# These are NOT project dependencies -- documented for users
# pip install opentelemetry-sdk opentelemetry-exporter-otlp
```

## Architecture Patterns

### Recommended Project Structure (Changes Only)

```
packages/mcp_json_yaml_toml/
├── models/
│   └── responses.py          # ADD: DiffResponse model
├── services/
│   └── diff_operations.py    # NEW: diff business logic
├── tools/
│   └── diff.py               # NEW: data_diff tool decorator
├── telemetry.py              # NEW: optional OTEL configuration helper
└── tests/
    ├── test_diff.py           # NEW: diff tool tests
    └── test_telemetry.py      # NEW: telemetry integration tests
```

### Pattern 1: data_diff Tool (mirrors data_merge pattern)

**What:** A new `data_diff` tool that accepts two file paths and returns structured diff.
**When to use:** Users need to compare configuration files, possibly of different formats.
**Example:**

```python
# Source: Follows existing data_merge pattern in tools/convert.py
from fastmcp.exceptions import ToolError
from pydantic import Field

from mcp_json_yaml_toml.server import mcp
from mcp_json_yaml_toml.models.responses import DiffResponse


@mcp.tool(
    timeout=60.0,
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
def data_diff(
    file_path1: Annotated[str, Field(description="Path to first file (base)")],
    file_path2: Annotated[str, Field(description="Path to second file (comparison)")],
    ignore_order: Annotated[bool, Field(description="Ignore list ordering")] = False,
    output_format: Annotated[
        Literal["structured", "text"] | None,
        Field(description="Output format: 'structured' (dict) or 'text' (human-readable)"),
    ] = "structured",
) -> DiffResponse:
    """Compare two configuration files and return structured differences."""
    ...
```

### Pattern 2: DiffResponse Pydantic Model

**What:** Response model following existing `ToolResponse` base class pattern.
**When to use:** Return type for `data_diff` tool.
**Example:**

```python
# Source: Follows existing models/responses.py patterns
class DiffResponse(ToolResponse):
    """Response for data_diff tool."""

    file1: str = ""
    file2: str = ""
    file1_format: str = ""
    file2_format: str = ""
    has_differences: bool = False
    summary: str = ""
    differences: dict[str, Any] | None = None  # DeepDiff to_dict() output
    statistics: dict[str, int] | None = None   # Count of changes by type
```

### Pattern 3: Diff Service Logic (mirrors data_operations.py)

**What:** Business logic in services/ layer, called by thin tool decorator.
**When to use:** Separation of tool registration from business logic per Phase 2 architecture.
**Example:**

```python
# Source: Follows services/data_operations.py pattern
from deepdiff import DeepDiff

def compute_diff(
    data1: Any,
    data2: Any,
    ignore_order: bool = False,
) -> dict[str, Any]:
    """Compute structured diff between two parsed data structures."""
    diff = DeepDiff(
        data1,
        data2,
        ignore_order=ignore_order,
        verbose_level=2,   # Include old/new values
    )
    return diff.to_dict()
```

### Pattern 4: OpenTelemetry Configuration (FastMCP native)

**What:** FastMCP 3.x provides zero-config OTEL instrumentation.
**When to use:** Always active. Users opt-in by installing SDK and configuring exporter.
**Example:**

```python
# Source: https://gofastmcp.com/servers/telemetry
# Option A: CLI-based (zero code changes)
# opentelemetry-instrument \
#   --service_name mcp-json-yaml-toml \
#   --exporter_otlp_endpoint http://localhost:4317 \
#   mcp-json-yaml-toml

# Option B: Programmatic (configure before FastMCP import)
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

provider = TracerProvider()
processor = BatchSpanProcessor(OTLPSpanExporter(endpoint="http://localhost:4317"))
provider.add_span_processor(processor)
trace.set_tracer_provider(provider)

# THEN import FastMCP -- traces exported automatically
from fastmcp import FastMCP
```

### Pattern 5: Custom Spans for yq Subprocess Visibility

**What:** Add custom spans around `execute_yq` calls for fine-grained tracing.
**When to use:** Users want to see yq execution time separately from tool overhead.
**Example:**

```python
# Source: https://gofastmcp.com/servers/telemetry (Custom Spans section)
from fastmcp.telemetry import get_tracer

def execute_yq_with_tracing(...) -> YQResult:
    tracer = get_tracer()
    with tracer.start_as_current_span("yq.execute") as span:
        span.set_attribute("yq.expression", expression)
        span.set_attribute("yq.input_format", str(input_format))
        span.set_attribute("yq.output_format", str(output_format))
        result = execute_yq(...)
        span.set_attribute("yq.returncode", result.returncode)
        return result
```

### Anti-Patterns to Avoid

- **Making OTEL SDK a required dependency:** FastMCP's design is "bring your own SDK." The `opentelemetry-api` is already a dependency (via FastMCP). The SDK packages should be optional extras, not required dependencies. Adding them as required would bloat the install for users who don't need tracing.
- **Parsing files differently for diff vs. other tools:** Use the same format detection (`_detect_file_format`) and parsing pipeline (yq -> JSON -> Python dict) that all other tools use. Do not introduce a separate parsing path.
- **Returning raw DeepDiff objects:** DeepDiff objects are not JSON-serializable. Always call `to_dict()` before returning. The Pydantic model enforces this.
- **Configuring OTEL inside server.py:** The FastMCP telemetry docs explicitly state "SDK must be configured BEFORE importing FastMCP." Server-side OTEL config would be too late. The server should document the pattern, not implement it.

## Don't Hand-Roll

| Problem                     | Don't Build                            | Use Instead                                                        | Why                                                                                                 |
| --------------------------- | -------------------------------------- | ------------------------------------------------------------------ | --------------------------------------------------------------------------------------------------- |
| Nested dict comparison      | Recursive dict diff function           | `deepdiff.DeepDiff`                                                | Handles type changes, list reordering, nested paths, circular refs, set membership. 15+ edge cases. |
| Diff path notation          | Custom path string builder             | DeepDiff's `root['key']['subkey']` paths                           | Standard notation, well-documented, parseable.                                                      |
| Diff serialization          | Custom JSON encoder for diff results   | `DeepDiff.to_dict()` + `to_json()`                                 | Handles all Python types including sets, classes, datetimes.                                        |
| Trace instrumentation       | Manual span creation around every tool | FastMCP native instrumentation                                     | Already done -- every `@mcp.tool()` call creates spans automatically with MCP semantic conventions. |
| Trace context propagation   | Manual header injection                | `fastmcp.telemetry.inject_trace_context` / `extract_trace_context` | Handles W3C trace context standard automatically.                                                   |
| OTEL exporter configuration | Custom exporter setup code             | `opentelemetry-instrument` CLI wrapper or env vars                 | Standard OTEL approach, zero code changes, works with any backend.                                  |

**Key insight:** Both features leverage existing libraries that handle the hard parts. DeepDiff handles all comparison edge cases. FastMCP handles all OTEL instrumentation. The implementation work is integration and API surface design, not algorithmic complexity.

## Common Pitfalls

### Pitfall 1: DeepDiff Output Size

**What goes wrong:** Comparing two large config files with many differences produces a DeepDiff output that exceeds the 10KB pagination threshold, or worse, the context window.
**Why it happens:** DeepDiff includes old/new values for every change. Large arrays or long strings balloon the output.
**How to avoid:** Add a `max_changes` parameter to the tool that limits the number of reported changes. Use `verbose_level=1` (path only, no values) as a fallback when output is too large. Apply the existing pagination service to the diff result.
**Warning signs:** Diff response exceeds 10KB. Test with large fixture files during development.

### Pitfall 2: Format-Dependent Comparison Artifacts

**What goes wrong:** Comparing JSON vs YAML produces spurious diffs because of format-specific parsing differences (e.g., YAML `true` vs JSON `true`, YAML `null` vs JSON `null`).
**Why it happens:** Both files are parsed through yq into JSON, then into Python dicts. Most format artifacts are normalized by this pipeline. However, TOML has strict typing (integers vs floats, datetime types) that may produce type_changes when compared against JSON equivalents.
**How to avoid:** Parse both files to Python dicts via the same yq -> JSON -> orjson pipeline. Document that comparison is semantic (data-level), not textual.
**Warning signs:** Type changes appearing in diffs between files that have "the same" values in different formats.

### Pitfall 3: OTEL SDK Must Be Configured Before FastMCP Import

**What goes wrong:** User configures OTEL SDK in their application code after importing FastMCP. Traces are not exported.
**Why it happens:** FastMCP initializes its tracer at import time via `get_tracer()`. If no SDK is configured at that point, it gets a no-op tracer and never re-checks.
**How to avoid:** Document this requirement clearly. The `opentelemetry-instrument` CLI wrapper handles this automatically (it configures the SDK before loading the application). For programmatic configuration, users must configure `TracerProvider` before `from fastmcp import FastMCP`.
**Warning signs:** No spans appearing in the OTEL backend despite correct exporter config.

### Pitfall 4: OTEL Dependencies Are Optional Extras

**What goes wrong:** Adding `opentelemetry-sdk` as a required dependency. Users who don't need tracing get a heavier install with packages they never use.
**Why it happens:** Mixing up "API" (always needed, already a FastMCP dep) vs "SDK" (only needed when exporting traces).
**How to avoid:** Use `pyproject.toml` optional dependency groups: `[project.optional-dependencies] telemetry = ["opentelemetry-sdk>=1.39.0", "opentelemetry-exporter-otlp>=1.39.0"]`. Users install with `pip install mcp-json-yaml-toml[telemetry]`.
**Warning signs:** `opentelemetry-sdk` appearing in the main `dependencies` list.

### Pitfall 5: data_diff Tool Name Must Be Unique

**What goes wrong:** Using a name that conflicts with existing tools or common MCP tool names.
**Why it happens:** The MCP protocol requires unique tool names within a server.
**How to avoid:** Use `data_diff` -- follows the existing naming convention (`data`, `data_query`, `data_schema`, `data_convert`, `data_merge`). Consistent with the "unified tools" approach.
**Warning signs:** FastMCP raising duplicate tool name errors at registration time.

## Code Examples

Verified patterns from official sources:

### DeepDiff Basic Usage

```python
# Source: Context7 /seperman/deepdiff -- verified
from deepdiff import DeepDiff

t1 = {"name": "app", "version": "1.0", "database": {"host": "localhost", "port": 5432}}
t2 = {"name": "app", "version": "2.0", "database": {"host": "prod.example.com", "port": 5432}, "logging": True}

diff = DeepDiff(t1, t2, verbose_level=2)
result = diff.to_dict()
# Result keys: 'values_changed', 'dictionary_item_added'
# values_changed: {"root['version']": {"new_value": "2.0", "old_value": "1.0"}, ...}
# dictionary_item_added: {"root['logging']": True}
```

### DeepDiff with Ignore Order

```python
# Source: Context7 /seperman/deepdiff -- verified
from deepdiff import DeepDiff

t1 = {"servers": ["a.com", "b.com", "c.com"]}
t2 = {"servers": ["c.com", "a.com", "b.com"]}

# Without ignore_order: reports iterable_item_moved
diff1 = DeepDiff(t1, t2)

# With ignore_order: no differences
diff2 = DeepDiff(t1, t2, ignore_order=True)
assert diff2 == {}
```

### FastMCP Telemetry Testing Pattern

```python
# Source: https://gofastmcp.com/servers/telemetry -- verified
import pytest
from collections.abc import Generator
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from fastmcp import FastMCP

@pytest.fixture
def trace_exporter() -> Generator[InMemorySpanExporter, None, None]:
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    original_provider = trace.get_tracer_provider()
    trace.set_tracer_provider(provider)
    yield exporter
    exporter.clear()
    trace.set_tracer_provider(original_provider)

async def test_tool_creates_span(trace_exporter: InMemorySpanExporter) -> None:
    mcp = FastMCP("test")

    @mcp.tool()
    def hello() -> str:
        return "world"

    await mcp.call_tool("hello", {})

    spans = trace_exporter.get_finished_spans()
    assert any(s.name == "tools/call hello" for s in spans)
```

### Custom Span with FastMCP Tracer

```python
# Source: https://gofastmcp.com/servers/telemetry -- verified
from fastmcp.telemetry import get_tracer

tracer = get_tracer()

with tracer.start_as_current_span("yq.execute") as span:
    span.set_attribute("yq.expression", expression)
    span.set_attribute("yq.input_format", str(input_format))
    result = execute_yq(expression, ...)
    span.set_attribute("yq.returncode", result.returncode)
```

## State of the Art

| Old Approach                                 | Current Approach                   | When Changed                  | Impact                                                                                      |
| -------------------------------------------- | ---------------------------------- | ----------------------------- | ------------------------------------------------------------------------------------------- |
| Manual trace instrumentation with decorators | FastMCP native OTEL (zero-config)  | FastMCP 3.0.0rc2 (2026-02-14) | No code changes needed for basic tracing. All tool calls auto-traced.                       |
| `opentelemetry-api` as separate install      | Bundled as FastMCP dependency      | FastMCP 3.0.0rc2 (2026-02-14) | API always available. Users only install SDK when they want export.                         |
| DeepDiff 7.x                                 | DeepDiff 8.6.1                     | 2025                          | Added UUID type ignoring, comprehensive type hints, property serialization.                 |
| MCP had no semantic conventions for OTEL     | MCP semantic conventions published | 2025                          | Standardized span names: `tools/call {name}`, `resources/read {uri}`, `prompts/get {name}`. |

**Deprecated/outdated:**

- DeepDiff 7.x: Superseded by 8.x with better serialization and type support
- Manual OTEL instrumentation in MCP servers: FastMCP 3.x makes this unnecessary

## Open Questions

1. **Should `data_diff` support a `key_path` parameter for scoped comparison?**
   - What we know: The `data` tool supports `key_path` for scoped get/set/delete. DeepDiff can compare any two Python objects, including sub-trees.
   - What's unclear: Whether users need to diff sub-sections of files, or if full-file diff is sufficient for v1.
   - Recommendation: Start without `key_path`. Users can always use `data_query` to extract sub-sections first, then diff the resulting files. Add `key_path` in a follow-up if requested.

2. **Should custom OTEL spans be added to `execute_yq` in the backends layer?**
   - What we know: FastMCP auto-traces tool calls, but not the internal subprocess execution. Adding spans to `execute_yq` would show yq execution time separately from tool overhead.
   - What's unclear: Whether the additional span noise is valuable or just pollutes trace output for most users.
   - Recommendation: Add custom spans as an optional enhancement (behind an env var or always-on with low cost). The `get_tracer()` returns a no-op tracer when no SDK is configured, so there is zero overhead for users without OTEL.

3. **Should OTEL SDK packages be declared as optional extras in pyproject.toml?**
   - What we know: FastMCP's design is "bring your own SDK." The API is always available.
   - What's unclear: Whether declaring `[project.optional-dependencies] telemetry = [...]` adds value vs. just documenting "install these packages."
   - Recommendation: Declare as optional extras. It provides a discoverable `pip install mcp-json-yaml-toml[telemetry]` install path and is standard Python packaging practice.

## Sources

### Primary (HIGH confidence)

- [FastMCP OpenTelemetry Documentation](https://gofastmcp.com/servers/telemetry) -- Complete OTEL integration guide, span hierarchy, attributes reference, testing patterns
- [FastMCP Telemetry Python SDK](https://gofastmcp.com/python-sdk/fastmcp-telemetry) -- `get_tracer()`, `inject_trace_context()`, `extract_trace_context()` API reference
- Context7 `/seperman/deepdiff` -- DeepDiff API, `to_dict()`, `to_json()`, type change detection, ignore patterns (304 code snippets, HIGH reputation, benchmark 76.4)
- Context7 `/websites/opentelemetry_io` -- Python OTEL SDK setup, OTLP exporter configuration, auto-instrumentation (8911 code snippets, HIGH reputation, benchmark 85.9)
- [DeepDiff 8.6.1 Documentation](https://zepworks.com/deepdiff/current/) -- Official docs, serialization, FlatDataAction enum
- [DeepDiff PyPI](https://pypi.org/project/deepdiff/) -- Version 8.6.1, Python 3.9+ support

### Secondary (MEDIUM confidence)

- [FastMCP 3.0 What's New](https://www.jlowin.dev/blog/fastmcp-3-whats-new) -- OTEL as one of the new features
- [Distributed Tracing with FastMCP blog](https://timvw.be/2025/06/27/distributed-tracing-with-fastmcp-combining-opentelemetry-and-langfuse/) -- Real-world FastMCP OTEL integration example
- [OpenTelemetry Python Exporters](https://opentelemetry.io/docs/languages/python/exporters) -- OTLP gRPC and HTTP exporter setup
- Installed packages verified: `opentelemetry-api==1.39.1` (via `uv pip show`), `fastmcp==3.0.0rc2` (via `uv run python -c`), `fastmcp.telemetry.get_tracer` available and functional

### Tertiary (LOW confidence)

- None. All findings verified against primary or secondary sources.

## Metadata

**Confidence breakdown:**

- Standard stack: HIGH -- deepdiff is the de facto Python diffing library, FastMCP OTEL is documented and verified in installed version
- Architecture: HIGH -- follows established patterns from Phase 2 (tool/service/model separation) and FastMCP official docs
- Pitfalls: HIGH -- identified from official docs (OTEL import ordering), verified behavior (DeepDiff output size), and existing codebase patterns (format detection pipeline)

**Research date:** 2026-02-15
**Valid until:** 2026-03-15 (stable domain, libraries are mature)

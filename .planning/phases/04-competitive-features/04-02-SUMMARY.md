---
phase: 04-competitive-features
plan: 02
subsystem: telemetry
tags: [opentelemetry, otel, tracing, spans, observability]

# Dependency graph
requires:
  - phase: 04-01
    provides: "Competitive features foundation, backends/yq.py with execute_yq"
provides:
  - "Optional telemetry extras (opentelemetry-sdk, otlp exporter)"
  - "telemetry.py helper module with get_tracer()"
  - "Custom yq.execute spans with expression/format/returncode attributes"
affects: []

# Tech tracking
tech-stack:
  added:
    [
      opentelemetry-sdk (optional),
      opentelemetry-exporter-otlp-proto-grpc (optional),
    ]
  patterns: [no-op tracer pattern, monkeypatch tracer for test isolation]

key-files:
  created:
    - packages/mcp_json_yaml_toml/telemetry.py
    - packages/mcp_json_yaml_toml/tests/test_telemetry.py
  modified:
    - pyproject.toml
    - packages/mcp_json_yaml_toml/backends/yq.py

key-decisions:
  - "Monkeypatch get_tracer in tests instead of global TracerProvider (OTEL allows set_tracer_provider only once per process, breaks xdist parallel)"
  - "opentelemetry-api is transitive dep of FastMCP, no need to declare explicitly"

patterns-established:
  - "No-op tracer pattern: get_tracer() returns no-op when no SDK configured, zero overhead"
  - "Span wrapping: tracer.start_as_current_span('yq.execute') around subprocess calls"
  - "Test isolation: unittest.mock.patch on module-level imports for provider independence"

# Metrics
duration: 7min
completed: 2026-02-15
---

# Phase 4 Plan 2: Telemetry Summary

**Optional OpenTelemetry extras with custom yq.execute spans for subprocess visibility via get_tracer() no-op pattern**

## Performance

- **Duration:** 7 min
- **Started:** 2026-02-15T07:25:10Z
- **Completed:** 2026-02-15T07:32:50Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

- Optional `[telemetry]` extras in pyproject.toml for opentelemetry-sdk and otlp exporter
- `telemetry.py` helper with `get_tracer()` returning no-op tracer when no SDK configured
- Custom `yq.execute` span wrapping subprocess calls in `execute_yq` with expression, format, and returncode attributes
- 5 tests covering tracer creation, SDK span recording, and yq span emission (JSON, YAML, error cases)
- All 415 tests pass, 80% coverage maintained

## Task Commits

Each task was committed atomically:

1. **Task 1: Add optional OTEL extras and create telemetry helper module** - `899ed64` (feat)
2. **Task 2: Add custom spans to yq backend and create telemetry tests** - `55e1cca` (feat)

## Files Created/Modified

- `packages/mcp_json_yaml_toml/telemetry.py` - Telemetry helper with get_tracer() and \_TRACER_NAME constant
- `packages/mcp_json_yaml_toml/tests/test_telemetry.py` - 5 tests for tracer and span verification
- `packages/mcp_json_yaml_toml/backends/yq.py` - Custom yq.execute span around subprocess call
- `pyproject.toml` - Optional telemetry dependency group and dev opentelemetry-sdk

## Decisions Made

- Monkeypatch `get_tracer` in tests instead of setting global TracerProvider -- OTEL SDK only allows `set_tracer_provider` once per process, which breaks pytest-xdist parallel execution
- `opentelemetry-api` is a transitive dependency of FastMCP, no need to declare explicitly in optional-dependencies
- InMemorySpanExporter import path is `opentelemetry.sdk.trace.export.in_memory_span_exporter` (not `in_memory`)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed InMemorySpanExporter import path**

- **Found during:** Task 2 (telemetry tests)
- **Issue:** Plan specified `from opentelemetry.sdk.trace.export.in_memory import InMemorySpanExporter` but the correct module path in opentelemetry-sdk 1.39.1 is `in_memory_span_exporter`
- **Fix:** Updated import to `from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter`
- **Files modified:** packages/mcp_json_yaml_toml/tests/test_telemetry.py
- **Verification:** Tests import and pass
- **Committed in:** 55e1cca (Task 2 commit)

**2. [Rule 1 - Bug] Fixed global TracerProvider race in parallel tests**

- **Found during:** Task 2 (full test suite)
- **Issue:** Plan's fixture used `trace.set_tracer_provider()` which only works once per process. In pytest-xdist parallel execution, tests failed with "Overriding of current TracerProvider is not allowed"
- **Fix:** Changed to monkeypatch approach using `unittest.mock.patch` on `mcp_json_yaml_toml.backends.yq.get_tracer` to inject test tracer directly
- **Files modified:** packages/mcp_json_yaml_toml/tests/test_telemetry.py
- **Verification:** All 415 tests pass in parallel (xdist -n auto)
- **Committed in:** 55e1cca (Task 2 commit)

---

**Total deviations:** 2 auto-fixed (2 bugs)
**Impact on plan:** Both fixes necessary for correctness. No scope creep.

## Issues Encountered

None beyond the auto-fixed deviations above.

## User Setup Required

None - no external service configuration required. Telemetry is opt-in via `pip install mcp-json-yaml-toml[telemetry]`.

## Next Phase Readiness

- Phase 4 is now complete (both plans executed)
- All competitive features delivered: data_diff tool (04-01) and telemetry observability (04-02)
- 415 tests passing, 80% coverage

---

_Phase: 04-competitive-features_
_Completed: 2026-02-15_

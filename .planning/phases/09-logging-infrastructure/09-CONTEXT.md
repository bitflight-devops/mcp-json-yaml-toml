# Phase 9: Logging Infrastructure - Context

**Gathered:** 2026-02-18
**Status:** Ready for planning

<domain>
## Phase Boundary

Install loguru, create centralized logging configuration, implement InterceptHandler for stdlib compatibility within `mcp_json_yaml_toml.*` namespace, ensure pytest caplog works with loguru, and verify mypy/basedpyright pass cleanly. This phase builds infrastructure only — module-by-module migration is Phase 10.

</domain>

<decisions>
## Implementation Decisions

### Log output format

- Structured JSON (JSONL) to file for machine parseability
- Human-readable colored output to console when console mode is explicitly enabled
- Default mode: JSONL to file only, stderr silent
- Minimal fields per JSON entry: timestamp, level, module, message

### Verbosity & filtering

- Default log level: WARNING — quiet by default, users opt into verbosity
- MCP protocol events (request/response) log at DEBUG — hidden unless explicitly enabled
- Business logic (file operations, schema validation) follows standard level hierarchy
- Size-based log rotation for the JSONL file (e.g., 10MB threshold, keep N backups)

### Configuration surface

- Environment variable prefix: `MCP_JYT_` to avoid conflicts with other MCP servers on the same machine
  - `MCP_JYT_LOG_LEVEL` — override default WARNING level
  - `MCP_JYT_LOG_FILE` — override XDG default log file path
- Default log file location: `~/.local/share/mcp-json-yaml-toml/logs/` (XDG data dir)
- `configure_logging()` called automatically on module import — zero setup needed by callers

### caplog integration

- Full caplog support — works naturally for both existing and future tests
- Automatic setup via conftest.py — all tests get loguru-caplog compatibility with zero friction
- File sink disabled during tests — no file I/O, caplog captures everything, tests stay fast and clean
- Tests that verify logging behavior should assert on structured fields (levelname, module, message) — precise, catches regressions

### Claude's Discretion

- Exact rotation size threshold and backup count
- PropagateHandler implementation details for caplog
- Loguru sink configuration internals
- Console output format string (when console mode enabled)

</decisions>

<specifics>
## Specific Ideas

- Env var naming: user noted that generic `MCP_LOG_*` would conflict with ~50 other MCP servers on the machine — `MCP_JYT_` prefix chosen specifically to namespace
- Dual output model: JSONL to file is the primary sink, console/stderr is a secondary mode for debugging — not both simultaneously by default

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

_Phase: 09-logging-infrastructure_
_Context gathered: 2026-02-18_

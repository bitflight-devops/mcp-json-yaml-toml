---
created: 2026-02-15T20:45:37.033Z
title: Integrate loguru for structured logging
area: services
files:
  - packages/mcp_json_yaml_toml/binary_manager.py
  - packages/mcp_json_yaml_toml/yaml_optimizer.py
  - packages/mcp_json_yaml_toml/config.py
---

## Problem

Phase 6 (Operational Safety) requires replacing `print()` to stderr with structured logging. The current codebase uses `print(..., file=sys.stderr)` in `binary_manager.py` for download progress and error reporting. The ROADMAP success criteria specify "binary_manager.py emits structured log records instead of print() to stderr" and "logging.debug() uses lazy %-formatting throughout codebase."

The standard library `logging` module works but `loguru` provides structured output, lazy formatting by default, better exception formatting, and zero-config setup — all aligned with the Phase 6 goals.

## Solution

Evaluate `loguru` as the logging backend for Phase 6 implementation:

- Replace `print(..., file=sys.stderr)` calls in `binary_manager.py` with `loguru.logger` calls
- Use `loguru`'s built-in lazy formatting (eliminates the %-formatting requirement automatically)
- Structured JSON output available via `logger.add(sink, serialize=True)` for observability
- Consider whether `loguru` or stdlib `logging` better fits the project's dependency philosophy (currently zero external runtime deps beyond FastMCP ecosystem)
- If stdlib preferred, use `logging.getLogger(__name__)` pattern instead

TBD: Decision needed on loguru vs stdlib logging during Phase 6 planning.

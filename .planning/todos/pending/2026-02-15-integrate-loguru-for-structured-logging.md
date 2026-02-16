---
created: 2026-02-15T20:45:37.033Z
title: Integrate loguru for structured logging
area: services
files:
  - packages/mcp_json_yaml_toml/binary_manager.py
  - packages/mcp_json_yaml_toml/yaml_optimizer.py
  - packages/mcp_json_yaml_toml/config.py
  - packages/mcp_json_yaml_toml/server.py
---

## Problem

The codebase uses `print(..., file=sys.stderr)` for meta-process tracing (download progress, binary management, error reporting). This conflates user-facing output with internal diagnostic tracing. There is no way to capture, rotate, or analyze operational logs after the fact.

Two distinct output channels are needed:

1. **User/AI-facing output**: `rich.console.print()` — dialog, results, formatted display
2. **Internal tracing**: `loguru` — what happened, when, for later analysis if needed

`print()` should not be used for either purpose going forward.

## Solution

**Decision: Use loguru (not stdlib logging)**

Architecture:

- **loguru** for all internal process tracing (binary downloads, format detection, yq execution, error paths)
- **rich console.print** for user/AI-facing output only
- **print() eliminated** from all meta-process tracking

Logging behavior requirements:

- **Default state**: Logging disabled (no file output, minimal stderr)
- **stderr**: Only ERROR and WARNING level by default; must be squashable (fully silent mode)
- **File logging**: Optional — configurable log folder path via environment variable or config
- **Log rotation**: When file logging enabled, rotate old logs automatically (loguru's `rotation` parameter)
- **Enablement**: Opt-in via environment variable (e.g., `MCP_LOG_LEVEL=DEBUG`, `MCP_LOG_DIR=/path/to/logs`)

Implementation pattern:

```python
from loguru import logger

# Remove default stderr handler, add controlled one
logger.remove()
if log_level := os.getenv("MCP_LOG_LEVEL"):
    logger.add(sys.stderr, level=log_level.upper())
if log_dir := os.getenv("MCP_LOG_DIR"):
    logger.add(f"{log_dir}/mcp-server.log", rotation="10 MB", retention="3 days")
```

This feeds directly into Phase 6 (Operational Safety) planning.

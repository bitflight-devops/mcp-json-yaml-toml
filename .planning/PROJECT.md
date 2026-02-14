# mcp-json-yaml-toml

## What This Is

An MCP (Model Context Protocol) server that gives AI assistants the ability to query and modify JSON, YAML, and TOML configuration files. It uses yq as the underlying transformation engine, runs 100% locally with no API keys, and preserves file formatting (comments, anchors, structure) during edits. Published on PyPI and deployed in production.

## Core Value

AI assistants can safely read and modify structured configuration files without destroying formatting, comments, or file structure.

## Requirements

### Validated

- ✓ Unified data tool for CRUD operations on JSON/YAML/TOML files — existing
- ✓ data_query tool for read-only yq expression evaluation — existing
- ✓ data_schema tool for JSON Schema discovery and validation — existing
- ✓ data_convert tool for format conversion between JSON/YAML/TOML — existing
- ✓ data_merge tool for deep merging files — existing
- ✓ Format-preserving edits via ruamel.yaml and tomlkit — existing
- ✓ Cursor-based pagination for large results (10KB chunks) — existing
- ✓ LMQL constraint validation for AI-safe structured output — existing
- ✓ Schema catalog integration with SchemaStore.org and IDE schema discovery — existing
- ✓ Cross-platform yq binary management with version-aware caching — existing
- ✓ YAML anchor optimization detecting and creating anchors for duplicate structures — existing
- ✓ MCP resources exposing constraint definitions — existing
- ✓ MCP prompts for config analysis and improvement suggestions — existing
- ✓ Environment-based format enablement via MCP_CONFIG_FORMATS — existing
- ✓ Cross-platform CI (Linux, macOS, Windows) — existing

### Active

- [ ] Upgrade from FastMCP 2.x to FastMCP 3.x, leveraging new protocol features
- [ ] Evaluate yq alternatives (dasel, native MCP from CLI tools) to reduce binary management complexity
- [ ] Simplify or replace yq binary management layer (download reliability, platform detection)
- [ ] Implement findings from research — adopt recommended architecture changes

### Out of Scope

- Rewriting the server in a non-Python language — Python ecosystem is the constraint
- Changing existing MCP tool names (data, data_query, data_schema, data_convert, data_merge) — existing clients depend on these
- Adding new file format support beyond JSON/YAML/TOML — not the focus of this milestone

## Context

The project is mature and production-deployed. The current pain points are:

1. **FastMCP version**: Pinned to v2 (`>=2.14.4,<3`) because v3 had breaking changes at beta. FastMCP 3 is now progressing and may offer new capabilities worth adopting.

2. **yq binary management**: The `yq_wrapper.py` module (~760 lines) handles binary detection, downloading, platform selection, checksums, version caching, and file locking. This is the most complex and fragile part of the codebase. GitHub API rate limits and network failures during binary download are ongoing issues.

3. **dasel as alternative**: [dasel](https://github.com/TomWright/dasel) supports JSON, YAML, TOML, XML, CSV and may offer a simpler integration path. Additionally, both yq and dasel could potentially serve MCP directly, eliminating the Python wrapper entirely.

The codebase has ~80% test coverage, comprehensive linting (ruff, mypy, basedpyright), and uses hatchling for builds with hatch-vcs for versioning.

## Constraints

- **Tool API stability**: Existing tool names and parameter interfaces must remain backward-compatible — MCP clients in production depend on them
- **Local-first**: Must continue operating without required API keys or cloud dependencies
- **Python 3.11+**: Must support Python 3.11 through 3.14
- **Format preservation**: Comments, anchors, and formatting must be preserved during edits — this is a core differentiator

## Key Decisions

| Decision                 | Rationale                                                                                                            | Outcome   |
| ------------------------ | -------------------------------------------------------------------------------------------------------------------- | --------- |
| Research before building | Domain is evolving (FastMCP 3, dasel ecosystem) — need current information before committing to architecture changes | — Pending |
| Keep existing tool names | Production clients depend on current API surface                                                                     | ✓ Good    |
| Evaluate yq alternatives | yq binary management is the highest-complexity, most-fragile subsystem                                               | — Pending |

---

_Last updated: 2026-02-14 after initialization_

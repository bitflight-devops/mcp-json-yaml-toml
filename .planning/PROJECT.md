# mcp-json-yaml-toml

## What This Is

An MCP (Model Context Protocol) server that gives AI assistants the ability to query and modify JSON, YAML, and TOML configuration files. It uses yq as the underlying transformation engine, runs 100% locally with no API keys, and preserves file formatting (comments, anchors, structure) during edits. Published on PyPI and deployed in production.

## Core Value

AI assistants can safely read and modify structured configuration files without destroying formatting, comments, or file structure.

## Requirements

### Validated

- ✓ Unified data tool for CRUD operations on JSON/YAML/TOML files — v1.0
- ✓ data_query tool for read-only yq expression evaluation — v1.0
- ✓ data_schema tool for JSON Schema discovery and validation — v1.0
- ✓ data_convert tool for format conversion between JSON/YAML/TOML — v1.0
- ✓ data_merge tool for deep merging files — v1.0
- ✓ data_diff tool for structured cross-format config comparison — v1.0
- ✓ Format-preserving edits via ruamel.yaml and tomlkit — v1.0
- ✓ Cursor-based pagination for large results (10KB chunks) — v1.0
- ✓ LMQL constraint validation for AI-safe structured output — v1.0
- ✓ Schema catalog integration with SchemaStore.org and IDE schema discovery — v1.0
- ✓ Cross-platform yq binary management with version-aware caching — v1.0
- ✓ YAML anchor optimization detecting and creating anchors for duplicate structures — v1.0
- ✓ MCP resources exposing constraint definitions — v1.0
- ✓ MCP prompts for config analysis and improvement suggestions — v1.0
- ✓ Environment-based format enablement via MCP_CONFIG_FORMATS — v1.0
- ✓ Cross-platform CI (Linux, macOS, Windows) — v1.0
- ✓ Layered architecture: backends, formats, models, services, tools — v1.0
- ✓ FastMCP 3.x with structured output, timeouts, automatic threadpool — v1.0
- ✓ OpenTelemetry observability with optional SDK extras — v1.0
- ✓ Pydantic response models with DictAccessMixin backward compat — v1.0
- ✓ JSON Schema Draft 2020-12 default validator — v1.0
- ✓ Service handlers return typed Pydantic response models — v1.1
- ✓ DRY violations eliminated (format-enable-check, TOML fallback, file path resolution) — v1.1
- ✓ Exception patterns use specific catches, not broad except Exception — v1.1
- ✓ binary_manager.py uses logging module instead of print() to stderr — v1.1
- ✓ data_operations.py split into focused service modules (SRP) — v1.1
- ✓ schemas.py split into focused sub-modules — v1.1
- ✓ Production imports migrated off deprecated yq_wrapper.py shim — v1.1
- ✓ config.py caches parsed environment configuration — v1.1
- ✓ Test suite uses behavioral naming and tests public API — v1.1
- ✓ Edge case coverage added: permissions, malformed input, resource cleanup — v1.1

### Active

(No active requirements — run `/gsd:new-milestone` to define next milestone)

### Out of Scope

- Rewriting the server in a non-Python language — Python ecosystem is the constraint
- Changing existing MCP tool names (data, data_query, data_schema, data_convert, data_merge) — existing clients depend on these
- Adding new file format support beyond JSON/YAML/TOML — not the current focus
- Switch from yq to dasel — dasel destroys comments/anchors, violates core differentiator

## Context

The project is mature and production-deployed. Two milestones shipped:

- **v1.0** (2026-02-14): Full architecture refactoring from monolithic server.py to layered architecture with FastMCP 3.x. 4 phases, 12 plans.
- **v1.1** (2026-02-17): Internal quality remediation — type safety, DRY extraction, god module splits, test standardization. 4 phases, 8 plans.

**Codebase:** 14,647 LOC Python, 428 tests at 82.5% coverage. Comprehensive linting (ruff, mypy, basedpyright). Uses hatchling for builds with hatch-vcs for versioning.

**Pending todos:** `.planning/todos/pending/` contains 7 structured todos for future work (loguru evaluation, schema validation errors, pre-write validation, multi-document YAML).

## Constraints

- **Tool API stability**: Existing tool names and parameter interfaces must remain backward-compatible — MCP clients in production depend on them
- **Local-first**: Must continue operating without required API keys or cloud dependencies
- **Python 3.11+**: Must support Python 3.11 through 3.14
- **Format preservation**: Comments, anchors, and formatting must be preserved during edits — this is a core differentiator

## Key Decisions

| Decision                        | Rationale                                                                                    | Outcome |
| ------------------------------- | -------------------------------------------------------------------------------------------- | ------- |
| Research before building        | Domain is evolving (FastMCP 3, dasel ecosystem) — need current information before committing | ✓ Good  |
| Keep existing tool names        | Production clients depend on current API surface                                             | ✓ Good  |
| Stay on yq                      | dasel destroys comments and anchors, eliminating it as backend alternative                   | ✓ Good  |
| Layered architecture            | Extract backends, formats, models, services, tools from monolithic server.py                 | ✓ Good  |
| FastMCP 3.x migration           | Upgrade after architecture refactoring to minimize migration surface                         | ✓ Good  |
| Skip research for v1.1          | Internal quality work — code review reports already document all patterns and locations      | ✓ Good  |
| Selective DRY extraction        | Directory paths and output paths kept inline; only input file paths use resolve_file_path()  | ✓ Good  |
| Facade pattern for splits       | data_operations.py and schemas/ use re-export facades for backward compat                    | ✓ Good  |
| stdlib logging over loguru      | Matches existing architecture for binary_manager.py, no new dependency                       | ✓ Good  |
| Handler dependency injection    | Tool handlers accept schema_manager as parameter for testability                             | ✓ Good  |
| Callable cast for FastMCP tests | FunctionTool not callable in FastMCP 3.x — cast("Callable[..., Any]") pattern                | ✓ Good  |
| Public API tests                | Route through public API (e.g., \_build_ide_schema_index) instead of testing private methods | ✓ Good  |

---

_Last updated: 2026-02-17 after v1.1 milestone completion_

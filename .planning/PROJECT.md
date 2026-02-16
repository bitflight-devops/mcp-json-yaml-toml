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

### Active

<!-- v1.1: Internal Quality — Code review remediation -->

- [ ] Service handlers return typed Pydantic response models instead of dict[str, Any]
- [ ] DRY violations eliminated (format-enable-check, TOML fallback, file path resolution)
- [ ] Exception patterns use specific catches, not broad except Exception
- [ ] binary_manager.py uses logging module instead of print() to stderr
- [ ] data_operations.py split into focused service modules (SRP)
- [ ] schemas.py split into focused sub-modules
- [ ] Production imports migrated off deprecated yq_wrapper.py shim
- [ ] config.py caches parsed environment configuration
- [ ] Test suite uses behavioral naming and tests public API, not private methods
- [ ] Edge case coverage added: permissions, malformed input, resource cleanup

### Out of Scope

- Rewriting the server in a non-Python language — Python ecosystem is the constraint
- Changing existing MCP tool names (data, data_query, data_schema, data_convert, data_merge) — existing clients depend on these
- Adding new file format support beyond JSON/YAML/TOML — not the focus of this milestone

## Current Milestone: v1.1 Internal Quality

**Goal:** Remediate code review findings — eliminate systemic quality issues, refactor god modules, and improve test standards.

**Target improvements:**

- Type safety: dict returns → Pydantic models across all service handlers
- DRY: Extract shared patterns (format checks, file resolution, TOML fallback)
- Architecture: Split 756-line data_operations.py and 1201-line schemas.py
- Correctness: Specific exception catches, logging instead of print()
- Tests: Behavioral naming, public API testing, edge case coverage

## Context

The project is mature and production-deployed. v1.0 milestone completed a full architecture refactoring (4 phases, 12 plans) from a monolithic server.py to layered architecture with FastMCP 3.x. Code review identified systemic patterns that accumulated during the refactoring and need remediation.

**Code review reports:** `.claude/smells/` directory contains detailed findings with file:line references.

**Pending todos:** `.planning/todos/pending/` contains 3 structured todos mapping to the review findings.

The codebase has 415 tests at ~80% coverage, comprehensive linting (ruff, mypy, basedpyright), and uses hatchling for builds with hatch-vcs for versioning.

## Constraints

- **Tool API stability**: Existing tool names and parameter interfaces must remain backward-compatible — MCP clients in production depend on them
- **Local-first**: Must continue operating without required API keys or cloud dependencies
- **Python 3.11+**: Must support Python 3.11 through 3.14
- **Format preservation**: Comments, anchors, and formatting must be preserved during edits — this is a core differentiator

## Key Decisions

| Decision                 | Rationale                                                                                                            | Outcome |
| ------------------------ | -------------------------------------------------------------------------------------------------------------------- | ------- |
| Research before building | Domain is evolving (FastMCP 3, dasel ecosystem) — need current information before committing to architecture changes | ✓ Good  |
| Keep existing tool names | Production clients depend on current API surface                                                                     | ✓ Good  |
| Evaluate yq alternatives | Research concluded dasel destroys comments/anchors — staying with yq                                                 | ✓ Good  |
| Stay on yq               | dasel destroys comments and anchors, eliminating it as backend alternative                                           | ✓ Good  |
| Layered architecture     | Extract backends, formats, models, services, tools from monolithic server.py                                         | ✓ Good  |
| FastMCP 3.x migration    | Upgrade after architecture refactoring to minimize migration surface                                                 | ✓ Good  |
| Skip research for v1.1   | Internal quality work — code review reports already document all patterns and locations                              | ✓ Good  |

---

_Last updated: 2026-02-15 after v1.1 milestone start_

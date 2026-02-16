# Feature Research

**Domain:** MCP server for structured config file manipulation (JSON/YAML/TOML)
**Researched:** 2026-02-14
**Confidence:** MEDIUM (FastMCP 3.x is RC-stage; dasel v3 is in active development; MCP spec 2025-11-25 is ratified)

## Current State Inventory

Before mapping the feature landscape, here is what the server already ships:

| Existing Tool            | Capability                                                  |
| ------------------------ | ----------------------------------------------------------- |
| `data`                   | CRUD on JSON/YAML/TOML via yq + native TOML libs            |
| `data_query`             | Read-only yq expression evaluation                          |
| `data_schema`            | Schema Store discovery, validation, association             |
| `data_convert`           | Format conversion (JSON<->YAML, TOML->JSON/YAML)            |
| `data_merge`             | Deep merge of two files                                     |
| `constraint_validate`    | LMQL constraint checking                                    |
| `constraint_list`        | Constraint catalog                                          |
| Pagination               | Cursor-based 10KB chunking with advisories                  |
| Format preservation      | ruamel.yaml (comments/anchors), tomlkit (comments/ordering) |
| YAML anchor optimization | Post-write deduplication                                    |
| Schema validation        | Draft 7 + Draft 2020-12 with remote $ref resolution         |

### Known Limitations (Current Stack)

| Limitation                               | Root Cause                                                               |
| ---------------------------------------- | ------------------------------------------------------------------------ |
| No JSON/YAML -> TOML conversion          | yq TOML encoder only supports scalar values                              |
| Binary management complexity             | yq auto-download with checksum verification, version pinning, lock files |
| Subprocess overhead                      | Every operation spawns a yq child process                                |
| No INI/HCL/CSV/properties format support | yq supports them but server does not expose them                         |
| YAML anchor optimization is post-hoc     | Write via yq, re-read, optimize -- three I/O passes                      |

## Feature Landscape

### Table Stakes (Users Expect These)

Features users of an MCP config file server assume exist. Missing these = product feels incomplete or falls behind MCP spec evolution.

| Feature                                                            | Why Expected                                                                                                                  | Complexity | Notes                                                                                                                                                                                                              |
| ------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------- | ---------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Structured output (outputSchema)**                               | MCP 2025-06-18 spec. Clients need typed tool results they can validate and deserialize. Without this, clients parse raw text. | MEDIUM     | FastMCP 3.x auto-generates outputSchema from return type annotations. On FastMCP 2.x this requires manual schema attachment. Current server returns `dict[str, Any]` everywhere -- needs Pydantic response models. |
| **Tool annotations (readOnlyHint, idempotentHint, openWorldHint)** | MCP 2025-06-18 spec. Clients use hints for caching, retry, and safety decisions.                                              | LOW        | Already partially implemented (`data_query` and `constraint_*` use `readOnlyHint`). Missing: `idempotentHint` on GET operations, `openWorldHint=False` (local-only server).                                        |
| **Full bidirectional format conversion**                           | Users expect JSON<->YAML<->TOML round-trips. The current TOML encoding limitation blocks this.                                | HIGH       | yq cannot encode complex nested structures to TOML. Switching to dasel or using native Python libs (tomlkit) for the TOML encoding path would fix this.                                                            |
| **MCP spec 2025-11-25 compliance (JSON Schema 2020-12 default)**   | Spec mandates 2020-12 as default dialect. Current server supports it but defaults to Draft 7.                                 | LOW        | Change default validator selection. Already has Draft202012Validator imported.                                                                                                                                     |
| **Component icons**                                                | MCP 2025-11-25. Servers can expose icons for tools, resources, prompts. Visual UIs display them.                              | LOW        | FastMCP 3.x supports icon metadata on components. Pure cosmetic but signals spec compliance.                                                                                                                       |

### Differentiators (Competitive Advantage)

Features that set the product apart. Not required, but valuable for adoption and retention.

| Feature                                                | Value Proposition                                                                                                                                                                                    | Complexity | Notes                                                                                                                                                                                                                   |
| ------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Expanded format support: INI, HCL, CSV, properties** | No competing MCP server handles INI/HCL files. DevOps users edit `.ini` configs, Terraform `.tfvars` (HCL), and `.properties` files regularly. Covering these makes this the one-stop config server. | MEDIUM     | dasel supports JSON/YAML/TOML/XML/CSV/HCL/INI natively. yq supports YAML/JSON/XML/CSV/TOML/HCL/properties. Either backend covers it. Server needs format enum expansion and enablement config.                          |
| **Elicitation support (human-in-the-loop)**            | MCP 2025-06-18. Server can ask user for missing info mid-operation (e.g., "Which section should I merge into?"). Enables guided config workflows.                                                    | HIGH       | Requires FastMCP 3.x or manual protocol handling. The server currently has no conversational flow.                                                                                                                      |
| **Async tasks for large file operations**              | MCP 2025-11-25 experimental Tasks primitive. Large file conversions, multi-file merges, or schema scans across directories could return task handles instead of blocking.                            | HIGH       | FastMCP 3.x has background task support (Docket integration). Not available in 2.x. Only matters for files >10MB or directory-wide operations.                                                                          |
| **Tool versioning**                                    | FastMCP 3.x: serve v1 and v2 of a tool side-by-side. Enables breaking changes (e.g., new query syntax) without disrupting existing clients.                                                          | LOW        | Purely a FastMCP 3.x feature (`@tool(version="2.0")`). No equivalent in 2.x. Useful when migrating from yq expression syntax to dasel selector syntax.                                                                  |
| **OpenTelemetry observability**                        | FastMCP 3.x: native OTEL instrumentation. Every tool call, resource read traced. Production deployments need this for monitoring and debugging.                                                      | LOW        | Drop-in configuration in FastMCP 3.x. No code changes to tools. Not available in 2.x.                                                                                                                                   |
| **Response size limiting**                             | FastMCP 3.x: automatic text truncation at UTF-8 boundaries with metadata. Prevents token budget blowout from large config files.                                                                     | LOW        | Already have cursor-based pagination. FastMCP 3.x adds server-level guardrail as defense-in-depth. These are complementary, not competing.                                                                              |
| **Config file diffing**                                | New tool: compare two versions of a config file, return structured diff. No existing MCP server does this. High value for code review and change validation.                                         | MEDIUM     | Implement using Python `deepdiff` or similar. Not dependent on backend (yq/dasel). Orthogonal to format choice.                                                                                                         |
| **Multi-file query (glob patterns)**                   | Query across multiple config files matching a glob. E.g., "find all services where `port == 8080` across `configs/*.yaml`".                                                                          | MEDIUM     | Requires new tool or parameter. Both yq and dasel support multi-file input. Pagination becomes critical here.                                                                                                           |
| **Native Python parsing (eliminate subprocess)**       | Replace yq subprocess calls with native Python libraries for JSON (orjson), YAML (ruamel.yaml), TOML (tomlkit). Faster, no binary management, better error messages.                                 | HIGH       | Already using ruamel.yaml and tomlkit for format-preserving writes. Could extend to reads/queries, but would need to implement a query/selector engine or adopt a Python query library. Loses yq's expression language. |
| **OAuth / auth support**                               | FastMCP 3.x: CIMD-based OAuth. Enables authenticated access to config servers in enterprise environments.                                                                                            | MEDIUM     | Only matters for remote/shared deployments. Current server is local-only (stdio transport).                                                                                                                             |
| **Provider-based composition**                         | FastMCP 3.x: mount sub-servers, namespace tools. Could expose format-specific sub-servers (e.g., `yaml_*`, `toml_*`) while keeping unified tools as primary.                                         | LOW        | Architectural flexibility. Enables modular deployment where users only load formats they need.                                                                                                                          |

### Anti-Features (Commonly Requested, Often Problematic)

Features that seem good but create problems. Deliberately NOT building these.

| Feature                                                 | Why Requested                                | Why Problematic                                                                                                                                                                                                     | Alternative                                                                                                                                                                     |
| ------------------------------------------------------- | -------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Direct file creation from scratch**                   | "Let me create a new config file."           | MCP tools should transform, not generate. LLMs should write file content; the server should validate and set values. Creating files from nothing invites hallucinated structures with no schema basis.              | Use `data(operation="set")` on an empty file the LLM creates via filesystem tools. Or add a `data_schema(action="scaffold")` that generates a minimal valid file from a schema. |
| **Embedded text editor / full-file rewrite**            | "Replace the entire file content."           | Bypasses format preservation, schema validation, and anchor optimization. A full rewrite tool would be an escape hatch that undermines every safety feature.                                                        | Use `data(operation="set")` at root path (`.`) for bulk updates. Preserves format handling pipeline.                                                                            |
| **Real-time file watching**                             | "Watch config files for changes and notify." | MCP servers are request-response, not event-driven. File watching requires persistent state, OS-specific watchers, and has no MCP protocol support. Adds complexity with no protocol path to deliver notifications. | Clients should poll or use their own filesystem watchers. The server validates on demand.                                                                                       |
| **Remote file access (HTTP/S3/GCS URLs)**               | "Read config from a URL."                    | Adds network dependencies, auth complexity, caching concerns, and security surface. Violates the "100% local processing" principle.                                                                                 | Users download files first using filesystem or HTTP tools, then use this server to manipulate them locally.                                                                     |
| **Custom query language**                               | "Build our own selector syntax."             | Maintenance burden of a custom parser. Users already know yq or jq syntax. Dasel's selector syntax is well-documented. Inventing a new one fragments the ecosystem.                                                 | Adopt an existing query syntax (yq expressions or dasel selectors).                                                                                                             |
| **Automatic backup/versioning**                         | "Keep history of file changes."              | Duplicates git functionality. Adds disk I/O, storage management, and cleanup concerns.                                                                                                                              | Users should use git. The server could optionally report "file modified" in structured output so agents can commit.                                                             |
| **Native MCP from CLI tools (dasel/yq as MCP servers)** | "Can dasel or yq serve MCP directly?"        | Neither tool has MCP support. Wrapping a CLI as an MCP server loses type safety, structured output, pagination, schema validation, and format preservation. The wrapper IS the product.                             | Continue building the Python server that uses these tools as backends. The value is in the orchestration layer, not the CLI.                                                    |

## Feature Dependencies

```
[Structured Output (outputSchema)]
    requires [Pydantic Response Models]
                  enhances [Tool Annotations (complete)]

[Full Bidirectional Conversion]
    requires [TOML Encoding Fix]
                  option-a: [Switch to dasel backend]
                  option-b: [Native Python TOML encoding via tomlkit]

[Expanded Format Support (INI/HCL/CSV)]
    requires [Format Enum Expansion]
    requires [Backend supporting those formats]
                  option-a: [dasel (all formats natively)]
                  option-b: [yq (HCL/CSV/properties already supported)]
                  option-c: [Native Python libs per format]

[Elicitation Support]
    requires [FastMCP 3.x Upgrade]
    enhances [Config File Diffing] (ask user which diff to apply)

[Async Tasks]
    requires [FastMCP 3.x Upgrade]
    enhances [Multi-file Query] (large result sets)

[Tool Versioning]
    requires [FastMCP 3.x Upgrade]
    enhances [Backend Migration] (serve yq-syntax and dasel-syntax tools simultaneously)

[OpenTelemetry]
    requires [FastMCP 3.x Upgrade]

[Provider Composition]
    requires [FastMCP 3.x Upgrade]

[OAuth / Auth]
    requires [FastMCP 3.x Upgrade]
    requires [HTTP/SSE transport] (not stdio)

[Config File Diffing]
    independent (no backend dependency)

[Multi-file Query]
    enhances [Pagination] (already exists)
    requires [Glob pattern support in tool params]

[Native Python Parsing]
    conflicts-with [yq expression language retention]
    enhances [Performance] (no subprocess overhead)
    requires [Query engine replacement or new selector implementation]
```

### Dependency Notes

- **Structured Output requires Pydantic Response Models:** Current tools return `dict[str, Any]`. FastMCP auto-generates outputSchema from typed return annotations. Migrating to Pydantic models is prerequisite regardless of FastMCP version.
- **Full Bidirectional Conversion requires TOML Encoding Fix:** Two paths -- dasel handles this natively; alternatively, use tomlkit in Python to encode complex structures to TOML without yq.
- **Five features require FastMCP 3.x:** Elicitation, async tasks, tool versioning, OpenTelemetry, and provider composition all require upgrading from FastMCP 2.x. This is the single largest dependency.
- **Native Python Parsing conflicts with yq expression language:** If the server drops yq as backend, it loses the jq-like expression language that `data_query` exposes. Would need to either adopt dasel selectors, implement a Python query engine, or accept reduced query power.
- **OAuth requires HTTP transport:** Current server uses stdio. OAuth only matters for remote deployments over HTTP/SSE.

## MVP Definition

### Launch With (v1 -- next milestone, stay on FastMCP 2.x)

These features can ship without the FastMCP 3.x upgrade.

- [ ] **Pydantic Response Models** -- Foundation for structured output. Define typed models for all tool return values. Can be used with FastMCP 2.x and carries forward to 3.x.
- [ ] **Complete Tool Annotations** -- Add `idempotentHint` on read operations, `openWorldHint=False` on all tools. Low effort, high spec compliance signal.
- [ ] **Full Bidirectional Conversion** -- Fix TOML encoding using tomlkit Python-native path. Eliminates the most visible user-facing limitation without switching backends.
- [ ] **Config File Diffing** -- New `data_diff` tool. High user value, independent of backend. Implement with deepdiff library.
- [ ] **JSON Schema 2020-12 as default** -- Flip the default validator. One-line change with test updates.

### Add After Validation (v1.x -- FastMCP 3.x upgrade)

Features to add once FastMCP 3.x reaches stable release and the upgrade is complete.

- [ ] **FastMCP 3.x Upgrade** -- Trigger: FastMCP 3.0.0 stable release (currently RC2). Unlocks five dependent features. Migration requires: namespace changes, enable/disable API migration, provider architecture changes.
- [ ] **Structured Output (outputSchema)** -- Trigger: Pydantic models already in place from v1. FastMCP 3.x auto-wires them.
- [ ] **Tool Versioning** -- Trigger: When planning backend migration (yq -> dasel). Serve both query syntaxes during transition.
- [ ] **OpenTelemetry** -- Trigger: First production deployment request. Drop-in config in 3.x.
- [ ] **Expanded Format Support (INI/HCL)** -- Trigger: User requests for Terraform/Java properties editing. Evaluate dasel vs yq for backend at this point.

### Future Consideration (v2+)

Features to defer until product-market fit is established.

- [ ] **Elicitation Support** -- Defer: Requires significant UX design for guided workflows. Protocol support is new and client implementations vary.
- [ ] **Async Tasks** -- Defer: Only matters for very large files or directory-wide operations. Current pagination handles most cases.
- [ ] **Multi-file Query** -- Defer: Powerful but complex. Needs careful pagination design for cross-file results.
- [ ] **Native Python Parsing (eliminate subprocess)** -- Defer: Major architectural change. yq/dasel backend works. Only pursue if subprocess overhead becomes measurable bottleneck.
- [ ] **OAuth / Auth** -- Defer: Only matters for remote deployments. Current user base is local stdio.
- [ ] **Provider Composition** -- Defer: Architectural flexibility. Not user-facing value until there are multiple deployment patterns.

## Feature Prioritization Matrix

| Feature                                  | User Value | Implementation Cost | Priority |
| ---------------------------------------- | ---------- | ------------------- | -------- |
| Pydantic Response Models                 | HIGH       | MEDIUM              | P1       |
| Complete Tool Annotations                | MEDIUM     | LOW                 | P1       |
| Full Bidirectional Conversion (TOML fix) | HIGH       | MEDIUM              | P1       |
| JSON Schema 2020-12 default              | MEDIUM     | LOW                 | P1       |
| Config File Diffing                      | HIGH       | MEDIUM              | P1       |
| FastMCP 3.x Upgrade                      | HIGH       | HIGH                | P2       |
| Structured Output (outputSchema)         | HIGH       | LOW (after models)  | P2       |
| Tool Versioning                          | MEDIUM     | LOW                 | P2       |
| OpenTelemetry                            | MEDIUM     | LOW                 | P2       |
| Expanded Format Support (INI/HCL)        | MEDIUM     | MEDIUM              | P2       |
| Component Icons                          | LOW        | LOW                 | P2       |
| Elicitation Support                      | MEDIUM     | HIGH                | P3       |
| Async Tasks                              | LOW        | HIGH                | P3       |
| Multi-file Query                         | HIGH       | MEDIUM              | P3       |
| Native Python Parsing                    | MEDIUM     | HIGH                | P3       |
| OAuth / Auth                             | LOW        | MEDIUM              | P3       |
| Provider Composition                     | LOW        | LOW                 | P3       |

**Priority key:**

- P1: Ship in next milestone (no FastMCP 3.x dependency)
- P2: Ship after FastMCP 3.x stable upgrade
- P3: Future consideration, defer until clear demand

## Competitor Feature Analysis

| Feature             | filesystem MCP server | Generic YAML/JSON tools                  | This Server (current)      | This Server (proposed)          |
| ------------------- | --------------------- | ---------------------------------------- | -------------------------- | ------------------------------- |
| Read config files   | Yes (raw text)        | N/A (CLI only)                           | Yes (structured)           | Yes (structured + outputSchema) |
| Modify config files | Yes (full rewrite)    | Yes (CLI)                                | Yes (key-path CRUD)        | Yes (key-path CRUD + diff)      |
| Format preservation | No                    | Varies (yq: partial, dasel: no comments) | Yes (ruamel.yaml, tomlkit) | Yes (maintained)                |
| Schema validation   | No                    | No                                       | Yes (Schema Store)         | Yes (2020-12 default)           |
| Format conversion   | No                    | Yes (CLI)                                | Partial (no X->TOML)       | Full bidirectional              |
| Pagination          | No                    | No                                       | Yes (cursor-based)         | Yes (+ response limiting)       |
| Query language      | No                    | Yes (yq/jq/dasel)                        | Yes (yq expressions)       | Yes (yq or dasel)               |
| Multi-format (>3)   | N/A                   | Yes (7+ formats)                         | 3 (JSON/YAML/TOML)         | 5-7 (+ INI/HCL/CSV)             |
| Structured output   | No                    | N/A                                      | No                         | Yes (outputSchema)              |
| Observability       | No                    | No                                       | No                         | Yes (OTEL)                      |

## Backend Decision: yq vs dasel

This is a critical architectural decision that affects multiple features. Summary based on research:

| Criterion            | yq (mikefarah)                                | dasel (TomWright)                                                                |
| -------------------- | --------------------------------------------- | -------------------------------------------------------------------------------- |
| Format support       | JSON, YAML, XML, CSV, TOML, HCL, properties   | JSON, YAML, TOML, XML, CSV, HCL, INI                                             |
| TOML encoding        | Scalar-only (cannot encode nested structures) | Full support                                                                     |
| Query syntax         | jq-like (widely known)                        | CSS-like selectors (20+ functions)                                               |
| Performance          | Baseline                                      | Up to 3x faster than jq, 15x faster than yq (per dasel benchmarks -- UNVERIFIED) |
| Comment preservation | YAML: partial (via output flags)              | YAML/TOML: comments discarded on write                                           |
| YAML anchors         | Preserved on read, expanded on write          | Not preserved                                                                    |
| Maturity             | v4.52.2 (stable, widely adopted)              | v3 (in active development, syntax revamp)                                        |
| Go module            | Yes                                           | Yes                                                                              |
| Binary size          | ~14MB                                         | ~5MB (UNVERIFIED)                                                                |

**Recommendation:** Do NOT switch wholesale from yq to dasel. The reasons:

1. **Comment preservation is a core differentiator.** dasel discards YAML/TOML comments on write. The current server uses ruamel.yaml and tomlkit specifically to preserve them. Switching to dasel for writes would regress this.
2. **YAML anchor handling matters.** The server has a YAML anchor optimizer. dasel does not preserve anchors.
3. **dasel v3 is in active development.** Its query syntax changed significantly from v2. Betting on a moving target adds risk.
4. **The TOML encoding limitation has a Python-native fix.** Use tomlkit (already a dependency) to encode nested structures to TOML. No need to switch backends for this one issue.

**Where dasel adds value:** If expanding to INI format support (yq does not support INI; dasel does). Could use dasel as a secondary backend for INI-only operations while keeping yq as primary.

## Sources

- [FastMCP 3.0 What's New (blog post by author)](https://www.jlowin.dev/blog/fastmcp-3-whats-new) -- HIGH confidence (primary source)
- [FastMCP changelog](https://gofastmcp.com/changelog) -- HIGH confidence (official)
- [FastMCP v3.0.0rc2 migration notes via Context7](https://github.com/jlowin/fastmcp/blob/v3.0.0rc2/v3-notes/) -- HIGH confidence (source code)
- [FastMCP 3.0 Beta 2 blog](https://www.jlowin.dev/blog/fastmcp-3-beta-2) -- HIGH confidence (primary source)
- [MCP spec 2025-06-18 changelog](https://modelcontextprotocol.io/specification/2025-11-25/changelog) -- HIGH confidence (protocol spec)
- [MCP spec 2025-11-25 overview (WorkOS)](https://workos.com/blog/mcp-2025-11-25-spec-update) -- MEDIUM confidence (third-party analysis)
- [Cisco MCP elicitation analysis](https://blogs.cisco.com/developer/whats-new-in-mcp-elicitation-structured-content-and-oauth-enhancements) -- MEDIUM confidence
- [dasel GitHub repository](https://github.com/TomWright/dasel) -- HIGH confidence (primary source)
- [dasel v3 documentation](https://daseldocs.tomwright.me/v3) -- HIGH confidence (official docs)
- [dasel selector overview](https://daseldocs.tomwright.me/functions/selector-overview) -- HIGH confidence (official docs)
- [yq GitHub repository (mikefarah)](https://github.com/mikefarah/yq) -- HIGH confidence (primary source)
- [yq TOML documentation](https://mikefarah.gitbook.io/yq/usage/toml) -- HIGH confidence (official docs)
- [dasel "swiss army knife" analysis](https://www.blog.brightcoding.dev/2025/09/09/dasel-the-universal-swiss-army-knife-for-json-yaml-toml-xml-and-csv-on-the-command-line) -- LOW confidence (blog, performance claims unverified)

---

_Feature research for: MCP config file server tooling (mcp-json-yaml-toml)_
_Researched: 2026-02-14_

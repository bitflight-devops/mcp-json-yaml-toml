---
created: 2026-02-16T17:49:48.732Z
title: Multi-document YAML file handling
area: services
source: "GitHub issue #6 (bitflight-devops/mcp-json-yaml-toml)"
files:
  - packages/mcp_json_yaml_toml/services/get_operations.py
  - packages/mcp_json_yaml_toml/services/mutation_operations.py
  - packages/mcp_json_yaml_toml/tools/data.py
  - packages/mcp_json_yaml_toml/tools/query.py
  - packages/mcp_json_yaml_toml/schemas/manager.py
---

## Problem

The MCP server does not handle multi-document YAML files (files with multiple `---` separated documents). These are common in:

- Kubernetes manifests (multiple resources in one file)
- Docker Compose overrides
- CI/CD pipeline definitions

## Solution

From GitHub issue #6:

1. **Multi-document reading/querying:** Parse `---` separated documents, allow querying by document index (e.g., `document[0]`), support querying across all documents
2. **Multi-document schema validation:** Validate each document individually, support different schemas per document (K8s resources each have their own schema), report results per-document with index
3. **Multi-document writing/editing:** Modify specific documents without affecting others, preserve separators and structure, allow adding/removing documents

Implementation notes: `ruamel.yaml` already supports `load_all()` / `dump_all()`. Consider adding a `document_index` parameter to existing tools.

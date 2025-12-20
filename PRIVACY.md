# Privacy Policy

## Local Operation

This MCP server has no runtime dependencies on external API services. All configuration files and data are processed entirely **locally** on your machine.

No user data, file contents, or usage telemetry is collected, stored, or transmitted to any external service by this server's primary operations.

## External Network Requests

External network requests occur only in these specific scenarios:

1.  **yq Binary Auto-download**: If the `yq` binary is missing for your platform/architecture, the server **will** download it from [GitHub Releases (mikefarah/yq)](https://github.com/mikefarah/yq/releases) during the first run. This is a one-time JIT (Just-In-Time) operation. These downloads are subject to [GitHub's Privacy Statement](https://docs.github.com/en/site-policy/privacy-policies/github-privacy-statement).
2.  **JSON Schema Downloads**: When an AI agent uses the `data_schema` tool (or other tools with validation enabled), the server **will** automatically download the required JSON schemas from [SchemaStore.org](https://schemastore.org) if they are missing from your local cache and IDE directories. The server also periodically fetches the Schema Store catalog ([catalog.json](https://www.schemastore.org/api/json/catalog.json)) to support automatic schema discovery. Downloads from SchemaStore are subject to their own [privacy considerations](https://schemastore.org).

## Transparency

This project is open-source. You can inspect the source code to verify these claims at:
<https://github.com/bitflight-devops/mcp-json-yaml-toml>

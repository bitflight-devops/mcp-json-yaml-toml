---
paths:
  - "packages/mcp_json_yaml_toml/yq_wrapper.py"
  - "packages/mcp_json_yaml_toml/tests/test_yq*.py"
  - ".github/workflows/yq-*.yml"
---

# yq Wrapper Guidelines

## Version Pinning

This project pins yq to a specific version defined in `DEFAULT_YQ_VERSION` in `yq_wrapper.py`. This ensures:

- Reproducible builds across all environments
- Consistent behavior regardless of GitHub API availability
- Known capabilities and limitations

## Checking yq Capabilities

Before making assumptions about yq limitations, verify against the pinned version:

```bash
# Check current pinned version
grep DEFAULT_YQ_VERSION packages/mcp_json_yaml_toml/yq_wrapper.py

# Test specific behavior
uv run python -c "
from mcp_json_yaml_toml.yq_wrapper import execute_yq, FormatType
# Test nested TOML output (previously limited, now supported in v4.52.2+)
result = execute_yq('.section', input_file='test.toml', input_format=FormatType.TOML, output_format=FormatType.TOML)
print(result.stdout)
"
```

## yq Evolution Notes

- **v4.52.2+**: Supports nested TOML output (earlier versions only supported scalars)
- **TOML bug fixes**: Table scope after comments, subarray parsing

## TOML Output Flow

The server handles TOML output through yq with an auto-fallback mechanism:

```
1. User requests data from TOML file
2. Server calls execute_yq() with output_format=FormatType.TOML
3. yq serializes the result:
   - For scalars: outputs valid TOML key-value
   - For nested structures (v4.52.2+): outputs valid TOML table content
   - For nested structures (older versions): returns error "only scalars..."
4. If YQExecutionError with "only scalars" in stderr AND output_format was auto-selected:
   - Server retries with FormatType.JSON (auto-fallback)
5. If output_format was explicitly requested by user:
   - Server raises ToolError (no fallback)
```

Key code locations:

- `server.py:511-529`: Auto-fallback for `data()` operation
- `server.py:1124-1140`: Auto-fallback for `data_query()` operation

The fallback ONLY triggers when:

1. `output_format_explicit=False` (user didn't explicitly request TOML)
2. `output_fmt == FormatType.TOML` (output was defaulted to TOML from input)
3. `input_format == FormatType.TOML` (input file is TOML)
4. `"only scalars" in str(e.stderr)` (yq returned the specific scalar limitation error)

## Binary Detection and Version Requirements

This project uses the Go-based mikefarah/yq, NOT the Python kislyuk/yq.

**System yq selection logic** (`_find_system_yq()`):

1. Check if yq is in PATH
2. Verify it's mikefarah/yq (contains "mikefarah/yq" in version output)
3. Check version is >= `DEFAULT_YQ_VERSION` (minimum required)
4. If version is older, download the pinned version instead

This ensures reproducible behavior - older system yq versions may lack required
features (e.g., nested TOML output support added in v4.52.2).

Key functions:

- `_get_yq_version_string()`: Extract version from yq binary
- `_version_meets_minimum()`: Compare versions using tuple comparison
- `_find_system_yq()`: Find compatible system yq or return None

## Weekly Update Workflow

The `.github/workflows/yq-update.yml` workflow:

1. Checks for new yq releases weekly
2. Fetches checksums using robust 64-hex extraction (not positional field)
3. Updates both `DEFAULT_YQ_VERSION` and `DEFAULT_YQ_CHECKSUMS`
4. Uses `.github/scripts/update_yq_checksums.py` for reliable updates
5. Script handles CRLF line endings for Windows compatibility

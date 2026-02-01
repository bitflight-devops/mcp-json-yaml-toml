# Testing Best Practices

## Verify Before Assuming

When working with failing tests, always verify the actual behavior before assuming what the code does:

1. **Test actual behavior first**: Before changing tests to expect different behavior, run the actual code path to see what really happens.

   ```bash
   # Example: test yq behavior directly before assuming limitations
   uv run python -c "
   from mcp_json_yaml_toml.yq_wrapper import execute_yq, FormatType
   result = execute_yq('.key', input_file='test.toml', input_format=FormatType.TOML, output_format=FormatType.TOML)
   print(f'stdout: {result.stdout!r}')
   print(f'returncode: {result.returncode}')
   "
   ```

2. **Don't assume tool limitations**: External tools like yq evolve. A limitation in an older version may be resolved in the current version. Check the DEFAULT_YQ_VERSION and test against it.

3. **Check version-specific capabilities**: When tests fail, verify whether the failure is:
   - A bug in the test assertions
   - A bug in the implementation
   - An outdated assumption about tool capabilities

## Test Modification Guidelines

- If tests were previously passing in CI and now fail, the tests are likely correct
- Read test docstrings carefully - they explain what behavior is being tested
- When tests reference "improvements" or version-specific features, verify the current version supports them

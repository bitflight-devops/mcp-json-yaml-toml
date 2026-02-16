---
created: 2026-02-15T15:54:17.756Z
title: Improve test quality and coverage gaps
area: testing
files:
  - packages/mcp_json_yaml_toml/tests/verify_features.py:40-63
  - packages/mcp_json_yaml_toml/tests/test_yq_wrapper.py:186-201,225-342,498-759
  - packages/mcp_json_yaml_toml/tests/test_schemas.py
  - packages/mcp_json_yaml_toml/tests/test_server.py
  - packages/mcp_json_yaml_toml/tests/test_diff.py:126-210
  - packages/mcp_json_yaml_toml/tests/test_set_type_preservation.py
  - packages/mcp_json_yaml_toml/tests/conftest.py
---

## Problem

Test quality audit scored 77/100 with 8 critical test issues:

**T-1. verify_features.py::test_hints() prints without assertions**: Manual verification script masquerading as automated test.

**T-2. Weak type-only assertions**: test_yq_wrapper.py:186-201 checks fields exist but not default values.

**T-3. 15 instances of private method testing**: \_verify_checksum, \_parse_version, \_is_mikefarah_yq, etc. in test_yq_wrapper.py, test_schemas.py, test_server.py (\_encode_cursor, \_decode_cursor, \_paginate_result). Creates brittle tests.

**T-4. Over-mocking**: test_yq_wrapper.py:225-342 tests mock interactions not behavior.

**T-5. Only 35% behavioral naming**: 60% use descriptive pattern instead of test*<what>\_when*<condition>_then_<outcome>.

**T-6. Missing edge case coverage**: No tests for concurrent access, large files/memory limits, malformed input (binary, BOM), subprocess hangs, permission errors.

**T-7. Hard-coded values instead of parametrize**: test_diff.py:126-210 repeats logic for identical/different files.

**T-8. Oversized test files**: test_yq_wrapper.py (1352 lines), test_set_type_preservation.py (1206 lines).

## Solution

1. Add assertions to verify_features.py test_hints()
2. Add value assertions alongside type checks in test_yq_wrapper.py
3. Refactor private method tests to test through public API
4. Balance unit tests with integration tests using real yq binary
5. Standardize naming: test*<what>\_when*<condition>_then_<outcome>
6. Add parametrized edge case tests: permissions, network failures, resource cleanup, malformed input
7. Use @pytest.mark.parametrize for data variations in test_diff.py
8. Split oversized files: test_yq_wrapper.py -> test_yq_binary.py, test_yq_execution.py, test_yq_versioning.py
9. Create tests/helpers.py with common assertion patterns

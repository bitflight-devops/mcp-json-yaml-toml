---
created: 2026-02-16T17:49:48.732Z
title: Improve schema validation error reporting
area: services
files:
  - packages/mcp_json_yaml_toml/services/schema_validation.py:79-80
  - packages/mcp_json_yaml_toml/tools/schema.py:29-76
---

## Problem

`_validate_against_schema()` catches the first `jsonschema.ValidationError` and returns only `e.message` as a string. The `jsonschema.ValidationError` object also carries:

- `.absolute_path` — JSON path to the invalid field (e.g., `deque(['database', 'port'])`)
- `.schema_path` — path within the schema that was violated
- `.context` — list of sub-errors for `anyOf`/`oneOf` failures
- `.validator` — which validator keyword failed (e.g., `type`, `required`, `enum`)

Currently the tool:

1. Reports only the top-level error message
2. Stops at the first `ValidationError` (does not collect all errors)
3. Does not include the JSON path to the offending field

## Solution

1. Replace `Validator.validate(data)` with `Validator(schema, registry=registry).iter_errors(data)` to collect all validation errors
2. For each error, include: JSON path (`.absolute_path`), error message (`.message`), validator keyword (`.validator`)
3. Return structured list of errors in the SchemaResponse instead of a single message string
4. Preserve backward compatibility — `schema_validated` bool and `message` field still present

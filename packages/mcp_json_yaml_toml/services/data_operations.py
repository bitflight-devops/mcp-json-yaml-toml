"""Backward-compatible re-export facade for data operations.

Real implementations live in focused sub-modules:
- get_operations.py: GET dispatch, structure/value/schema handlers
- mutation_operations.py: SET/DELETE dispatch, TOML/yq handlers, validation
- query_operations.py: Query response builder

New code should import directly from the specific sub-module.
"""

from __future__ import annotations

from mcp_json_yaml_toml.services.get_operations import (
    _dispatch_get_operation,
    _handle_data_get_schema,
    _handle_data_get_structure,
    _handle_data_get_value,
    _handle_meta_get,
    is_schema,
)
from mcp_json_yaml_toml.services.mutation_operations import (
    _delete_toml_key_handler,
    _delete_yq_key_handler,
    _dispatch_delete_operation,
    _dispatch_set_operation,
    _handle_data_delete,
    _handle_data_set,
    _optimize_yaml_if_needed,
    _set_toml_value_handler,
    _validate_and_write_content,
)
from mcp_json_yaml_toml.services.query_operations import _build_query_response

__all__ = [
    "_build_query_response",
    "_delete_toml_key_handler",
    "_delete_yq_key_handler",
    "_dispatch_delete_operation",
    "_dispatch_get_operation",
    "_dispatch_set_operation",
    "_handle_data_delete",
    "_handle_data_get_schema",
    "_handle_data_get_structure",
    "_handle_data_get_value",
    "_handle_data_set",
    "_handle_meta_get",
    "_optimize_yaml_if_needed",
    "_set_toml_value_handler",
    "_validate_and_write_content",
    "is_schema",
]

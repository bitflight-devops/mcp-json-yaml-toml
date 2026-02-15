"""Backward-compatible shim. Real implementation in backends/.

This module re-exports all public symbols from the backends/ package
to maintain backward compatibility with existing import paths.
New code should import directly from mcp_json_yaml_toml.backends.
"""

from __future__ import annotations

from mcp_json_yaml_toml.backends.base import (
    FormatType,
    YQBinaryNotFoundError,
    YQError,
    YQExecutionError,
    YQResult,
)
from mcp_json_yaml_toml.backends.binary_manager import (  # noqa: F401
    DEFAULT_YQ_CHECKSUMS,
    DEFAULT_YQ_VERSION,
    _cleanup_old_versions,
    _find_system_yq,
    _get_checksums,
    _get_platform_binary_info,
    _is_mikefarah_yq,
    _parse_version,
    _verify_checksum,
    _version_meets_minimum,
    get_yq_binary_path,
    get_yq_version,
    validate_yq_binary,
)
from mcp_json_yaml_toml.backends.yq import execute_yq, parse_yq_error

__all__ = [
    "DEFAULT_YQ_CHECKSUMS",
    "DEFAULT_YQ_VERSION",
    "FormatType",
    "YQBinaryNotFoundError",
    "YQError",
    "YQExecutionError",
    "YQResult",
    "execute_yq",
    "get_yq_binary_path",
    "get_yq_version",
    "parse_yq_error",
    "validate_yq_binary",
]

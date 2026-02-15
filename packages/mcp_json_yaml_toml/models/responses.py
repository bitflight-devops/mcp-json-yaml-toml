"""Pydantic response models for all MCP tool return shapes.

These models define the typed response contracts for every tool in the server.
They are the foundation for FMCP-04 typed return values.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from mcp_json_yaml_toml.schemas import (
    SchemaInfo,  # noqa: TC001 — Pydantic needs this at runtime for model building
)


class ToolResponse(BaseModel):
    """Base response model for all tool returns."""

    success: bool
    file: str | None = None

    model_config = {"extra": "allow"}


class DataResponse(ToolResponse):
    """Response for data GET and data_query returns."""

    result: Any = None
    format: str = ""
    paginated: bool = False
    nextCursor: str | None = None
    advisory: str | None = None
    schema_info: SchemaInfo | None = None
    structure_summary: str | None = None


class MutationResponse(ToolResponse):
    """Response for data SET/DELETE operations."""

    result: str = ""
    optimized: bool = False
    message: str | None = None
    schema_info: SchemaInfo | None = None


class ValidationResponse(ToolResponse):
    """Response for data_schema validate action."""

    format: str | None = None
    syntax_valid: bool = False
    schema_validated: bool = False
    syntax_message: str | None = None
    schema_message: str | None = None
    schema_file: str | None = None
    overall_valid: bool = False


class SchemaActionResponse(ToolResponse):
    """Response for data_schema non-validate actions."""

    action: str = ""
    message: str | None = None
    schemas: list[dict[str, Any]] | None = None
    directories: list[str] | None = None
    catalogs: list[str] | None = None
    associations: dict[str, Any] | None = None


class ConvertResponse(ToolResponse):
    """Response for data_convert tool."""

    input_file: str = ""
    input_format: str = ""
    output_format: str = ""
    result: str | None = None
    output_file: str | None = None
    message: str | None = None


class MergeResponse(ToolResponse):
    """Response for data_merge tool."""

    file1: str = ""
    file2: str = ""
    output_format: str = ""
    result: str | None = None
    output_file: str | None = None
    message: str | None = None


class ConstraintValidateResponse(BaseModel):
    """Response for constraint_validate tool.

    Does NOT inherit ToolResponse -- different shape from the validation API.
    """

    valid: bool
    constraint: str = ""
    value: str = ""
    error: str | None = None
    is_partial: bool | None = None
    hint: str | None = None


class ConstraintListResponse(BaseModel):
    """Response for constraint_list tool."""

    constraints: list[dict[str, Any]] = []
    usage: str = ""


class SchemaResponse(BaseModel):
    """Response format for schema retrieval.

    Moved from server.py -- preserves the alias for 'schema' field
    to match the existing API contract.
    """

    success: bool
    file: str
    message: str
    schema_: dict[str, Any] | None = Field(default=None, alias="schema")
    schema_info: SchemaInfo | None = None
    schema_file: str | None = None

    model_config = {"populate_by_name": True}


__all__ = [
    "ConstraintListResponse",
    "ConstraintValidateResponse",
    "ConvertResponse",
    "DataResponse",
    "MergeResponse",
    "MutationResponse",
    "SchemaActionResponse",
    "SchemaResponse",
    "ToolResponse",
    "ValidationResponse",
]

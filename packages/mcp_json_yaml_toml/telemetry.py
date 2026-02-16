"""OpenTelemetry helpers for MCP JSON/YAML/TOML server.

Provides a tracer instance and span utilities for yq subprocess visibility.
Uses FastMCP's built-in telemetry when available, falls back to opentelemetry-api
(always available as FastMCP transitive dep). Returns no-op tracer when no SDK configured.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from opentelemetry import trace

if TYPE_CHECKING:
    from opentelemetry.trace import Tracer

# Module-level tracer -- no-op when SDK not configured
_TRACER_NAME = "mcp-json-yaml-toml"


def get_tracer() -> Tracer:
    """Get the package tracer.

    Returns a no-op tracer when no OTEL SDK is configured,
    so there is zero overhead for users without telemetry.
    """
    return trace.get_tracer(_TRACER_NAME)


__all__ = ["get_tracer"]

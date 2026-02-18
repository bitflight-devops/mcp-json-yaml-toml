"""Centralized logging configuration for mcp-json-yaml-toml.

This module configures loguru with a JSONL file sink and optional stderr console
output. It bridges stdlib ``logging`` for the ``mcp_json_yaml_toml.*`` namespace
via :class:`InterceptHandler` so existing code works without modification.

.. important::
    This file is named ``logging.py`` which shadows stdlib ``logging``.
    The stdlib module is imported at the **top** of this file before any
    other imports to capture a reliable reference.
"""

from __future__ import annotations

import inspect

# CRITICAL: Import stdlib logging FIRST, before any package-relative imports,
# to avoid shadowing issues.  Store as module-level reference.
import logging as _stdlib_logging
import os
import sys
from pathlib import Path

from loguru import logger

__all__ = ["configure_logging"]

_DEFAULT_LOG_DIR = Path.home() / ".local" / "share" / "mcp-json-yaml-toml" / "logs"
_DEFAULT_LOG_LEVEL = "WARNING"
_CONFIGURED = False


def _is_testing() -> bool:
    """Detect if running under pytest.

    Checks both ``sys.modules`` for pytest presence and the
    ``PYTEST_CURRENT_TEST`` environment variable that pytest sets
    when a test is actively running.
    """
    return "pytest" in sys.modules or "PYTEST_CURRENT_TEST" in os.environ


def configure_logging() -> None:
    """Configure loguru with JSONL file sink and optional stderr.

    Environment variables:
        MCP_JYT_LOG_LEVEL: Override default WARNING level.
        MCP_JYT_LOG_FILE: Override default log file path.
        MCP_JYT_LOG_CONSOLE: Set to ``"1"``, ``"true"``, or ``"yes"``
            to enable stderr console output.

    Idempotent -- safe to call multiple times.
    """
    global _CONFIGURED  # noqa: PLW0603
    if _CONFIGURED:
        return
    _CONFIGURED = True

    # Remove loguru's default stderr handler
    logger.remove()

    level = os.environ.get("MCP_JYT_LOG_LEVEL", _DEFAULT_LOG_LEVEL).upper()

    # Determine log file path
    log_file_override = os.environ.get("MCP_JYT_LOG_FILE", "").strip()
    log_file = (
        Path(log_file_override)
        if log_file_override
        else _DEFAULT_LOG_DIR / "server.jsonl"
    )

    # JSONL file sink (primary) -- skip when running under pytest
    if not _is_testing():
        log_file.parent.mkdir(parents=True, exist_ok=True)
        logger.add(
            log_file,
            level=level,
            serialize=True,
            rotation="10 MB",
            retention=5,
            enqueue=True,
            diagnose=False,
        )

    # Optional stderr console sink (disabled by default -- MCP stdout safety)
    if os.environ.get("MCP_JYT_LOG_CONSOLE", "").strip().lower() in {
        "1",
        "true",
        "yes",
    }:
        logger.add(
            sys.stderr,
            level=level,
            format=(
                "<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | "
                "<cyan>{name}</cyan> - <level>{message}</level>"
            ),
            colorize=True,
            diagnose=False,
            enqueue=False,
        )

    # Install InterceptHandler on project-namespace stdlib loggers
    _install_intercept_handler()


class InterceptHandler(_stdlib_logging.Handler):
    """Route stdlib logging records to loguru sinks.

    Attached only to the ``mcp_json_yaml_toml`` namespace logger so that
    third-party library logging is unaffected.
    """

    def emit(self, record: _stdlib_logging.LogRecord) -> None:
        """Forward a stdlib log record to loguru."""
        # Map stdlib level name to loguru level
        try:
            level: str | int = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # Walk call frames to find the original caller depth
        frame = inspect.currentframe()
        depth = 0
        while frame is not None:
            filename = frame.f_code.co_filename
            is_logging = filename == _stdlib_logging.__file__
            is_frozen = "importlib" in filename and "_bootstrap" in filename
            if depth > 0 and not (is_logging or is_frozen):
                break
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )


def _install_intercept_handler() -> None:
    """Attach InterceptHandler to ``mcp_json_yaml_toml.*`` namespace loggers only."""
    handler = InterceptHandler()

    # Target the project namespace logger -- NOT the root logger
    ns_logger = _stdlib_logging.getLogger("mcp_json_yaml_toml")
    ns_logger.handlers = [handler]
    ns_logger.setLevel(_stdlib_logging.DEBUG)  # Let loguru handle filtering
    ns_logger.propagate = False  # Don't bubble to root

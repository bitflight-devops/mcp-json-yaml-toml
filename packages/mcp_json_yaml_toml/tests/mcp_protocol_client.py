"""MCP Protocol Client for testing via actual JSON-RPC calls.

This module provides a client that communicates with the MCP server via
subprocess and JSON-RPC protocol, enabling tests that verify actual protocol
behavior rather than direct function calls.

Tests: MCP JSON-RPC protocol communication
How: Spawn subprocess running MCP server, send JSON-RPC messages via stdin/stdout
Why: Direct function calls bypass protocol layer where type coercion bugs may occur
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from typing import Any, Self


@dataclass
class MCPClient:
    """Client for communicating with MCP server via JSON-RPC protocol.

    This client spawns the MCP server as a subprocess and communicates via
    stdin/stdout using the JSON-RPC 2.0 protocol. This allows tests to verify
    actual protocol behavior including serialization/deserialization.

    Attributes:
        process: The subprocess running the MCP server
        _request_id: Counter for generating unique request IDs
        _initialized: Whether the client has completed MCP initialization
    """

    process: subprocess.Popen[str] | None = field(default=None, init=False)
    _request_id: int = field(default=0, init=False)
    _initialized: bool = field(default=False, init=False)

    def start(self) -> None:
        """Start the MCP server subprocess.

        Spawns `uv run mcp-json-yaml-toml` and performs MCP initialization
        handshake.

        Raises:
            RuntimeError: If server fails to start or initialize
        """
        self.process = subprocess.Popen(
            ["uv", "run", "mcp-json-yaml-toml"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,  # Line buffered
        )

        # Perform MCP initialization handshake
        self._perform_initialization()

    def _perform_initialization(self) -> None:
        """Perform MCP protocol initialization handshake.

        Sends initialize request and notifications/initialized notification
        as required by MCP protocol.

        Raises:
            RuntimeError: If initialization fails
        """
        # Send initialize request
        init_response = self._send_request(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "pytest-mcp-client", "version": "1.0.0"},
            },
        )

        if "error" in init_response:
            error_msg = f"MCP initialization failed: {init_response['error']}"
            raise RuntimeError(error_msg)

        # Send initialized notification (no response expected)
        self._send_notification("notifications/initialized", {})

        self._initialized = True

    def _send_request(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        """Send a JSON-RPC request and wait for response.

        Args:
            method: The JSON-RPC method name
            params: Parameters for the method

        Returns:
            The JSON-RPC response as a dictionary

        Raises:
            RuntimeError: If process not started or communication fails
        """
        if (
            self.process is None
            or self.process.stdin is None
            or self.process.stdout is None
        ):
            error_msg = "MCP client not started. Call start() first."
            raise RuntimeError(error_msg)

        self._request_id += 1
        request = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
            "id": self._request_id,
        }

        # Send request
        request_json = json.dumps(request)
        self.process.stdin.write(request_json + "\n")
        self.process.stdin.flush()

        # Read response
        response_line = self.process.stdout.readline()
        if not response_line:
            error_msg = "No response from MCP server"
            raise RuntimeError(error_msg)

        result: dict[str, Any] = json.loads(response_line)
        return result

    def _send_notification(
        self, method: str, params: dict[str, Any] | None = None
    ) -> None:
        """Send a JSON-RPC notification (no response expected).

        Args:
            method: The JSON-RPC method name
            params: Optional parameters for the method

        Raises:
            RuntimeError: If process not started
        """
        if self.process is None or self.process.stdin is None:
            error_msg = "MCP client not started. Call start() first."
            raise RuntimeError(error_msg)

        notification: dict[str, Any] = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            notification["params"] = params

        notification_json = json.dumps(notification)
        self.process.stdin.write(notification_json + "\n")
        self.process.stdin.flush()

    def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Call an MCP tool via JSON-RPC protocol.

        Args:
            tool_name: Name of the tool to call (e.g., "data", "data_query")
            arguments: Tool arguments as a dictionary

        Returns:
            The tool result as a dictionary. Structure depends on tool.

        Raises:
            RuntimeError: If client not initialized or tool call fails
        """
        if not self._initialized:
            error_msg = "MCP client not initialized. Call start() first."
            raise RuntimeError(error_msg)

        response = self._send_request(
            "tools/call", {"name": tool_name, "arguments": arguments}
        )

        if "error" in response:
            error = response["error"]
            error_msg = f"MCP tool call failed: {error}"
            raise RuntimeError(error_msg)

        # Extract result from response
        # MCP tool responses are in result.content[0].text for text responses
        result = response.get("result", {})

        # Parse the content - MCP returns content as array of content blocks
        content = result.get("content", [])
        if content and len(content) > 0:
            first_content = content[0]
            if first_content.get("type") == "text":
                text = first_content.get("text", "{}")
                parsed: dict[str, Any] = json.loads(text)
                return parsed

        # Fallback: return result as-is if format unexpected
        fallback_result: dict[str, Any] = result
        return fallback_result

    def stop(self) -> None:
        """Stop the MCP server subprocess.

        Sends termination signal and waits for process to exit.
        """
        if self.process is not None:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()
            self.process = None
        self._initialized = False

    def __enter__(self) -> Self:
        """Context manager entry - starts the client."""
        self.start()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        """Context manager exit - stops the client."""
        self.stop()


def call_mcp_tool(tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """Convenience function to call an MCP tool via protocol.

    Creates a temporary MCP client, calls the tool, and returns the result.
    Use this for simple one-off calls. For multiple calls, use MCPClient
    context manager directly for efficiency.

    Args:
        tool_name: Name of the tool to call
        arguments: Tool arguments

    Returns:
        Tool result as dictionary
    """
    with MCPClient() as client:
        return client.call_tool(tool_name, arguments)

"""MCP Protocol Client for testing via actual JSON-RPC calls.

This module provides a client that communicates with the MCP server via
subprocess and JSON-RPC protocol, enabling tests that verify actual protocol
behavior rather than direct function calls.

Tests: MCP JSON-RPC protocol communication
How: Spawn subprocess running MCP server, send JSON-RPC messages via stdin/stdout
Why: Direct function calls bypass protocol layer where type coercion bugs may occur

Windows pipe deadlock prevention
---------------------------------
On Windows the OS pipe buffer is ~4 KB. The MCP server writes loguru startup
messages to stderr on import; these can fill the buffer and block the server
before it ever writes a JSON-RPC response to stdout, causing ``readline()`` to
hang forever.

Two daemon threads prevent this:

* **stderr drain thread** — continuously reads ``stderr`` and discards output
  (or accumulates it for diagnostics) so the buffer never fills.
* **stdout reader thread** — reads ``stdout`` into a ``queue.Queue`` so that
  ``_send_request`` can call ``queue.get(timeout=…)`` instead of the blocking
  ``readline()`` that never returns when the server is silent.

Both threads are daemons, so they never prevent process exit.
"""

from __future__ import annotations

import json
import queue
import subprocess
import threading
from dataclasses import dataclass, field
from typing import Any, Self

# Seconds to wait for a JSON-RPC response before raising an error.
_RESPONSE_TIMEOUT: float = 30.0


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
        _stdout_queue: Queue fed by the stdout reader thread
        _stderr_lines: Accumulated stderr output for diagnostics
        _stderr_thread: Daemon thread draining stderr
        _stdout_thread: Daemon thread reading stdout into _stdout_queue
    """

    process: subprocess.Popen[str] | None = field(default=None, init=False)
    _request_id: int = field(default=0, init=False)
    _initialized: bool = field(default=False, init=False)
    _stdout_queue: queue.Queue[str | None] = field(
        default_factory=queue.Queue, init=False
    )
    _stderr_lines: list[str] = field(default_factory=list, init=False)
    _stderr_thread: threading.Thread | None = field(default=None, init=False)
    _stdout_thread: threading.Thread | None = field(default=None, init=False)

    def _drain_stderr(self) -> None:
        """Background thread: drain stderr so the OS pipe buffer never fills.

        Accumulates lines in ``self._stderr_lines`` for diagnostics. Runs
        until the pipe closes (EOF), which happens when the subprocess exits.
        """
        if self.process is None or self.process.stderr is None:
            return
        try:
            for line in self.process.stderr:
                self._stderr_lines.append(line)
        except ValueError:
            # Pipe was closed externally (e.g. during stop()); ignore.
            pass

    def _read_stdout(self) -> None:
        """Background thread: read stdout lines and push them to the queue.

        Pushes ``None`` as a sentinel when EOF is reached so that
        ``_send_request`` can detect server exit instead of blocking forever.
        """
        if self.process is None or self.process.stdout is None:
            self._stdout_queue.put(None)
            return
        try:
            for line in self.process.stdout:
                self._stdout_queue.put(line)
        except ValueError:
            # Pipe closed externally during stop().
            pass
        finally:
            # Sentinel: EOF or error — unblock any waiting _send_request.
            self._stdout_queue.put(None)

    def start(self) -> None:
        """Start the MCP server subprocess.

        Spawns ``uv run mcp-json-yaml-toml`` and performs MCP initialization
        handshake. Background daemon threads are started to drain stderr and
        read stdout so that Windows pipe buffers never fill.

        Raises:
            RuntimeError: If server fails to start or initialize
        """
        self._stdout_queue = queue.Queue()
        self._stderr_lines = []

        self.process = subprocess.Popen(
            ["uv", "run", "mcp-json-yaml-toml"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=0,  # Unbuffered — line-buffered (bufsize=1) not honoured on Windows for pipes
        )

        # Start stderr drain thread first so startup messages never block.
        self._stderr_thread = threading.Thread(
            target=self._drain_stderr, name="mcp-stderr-drain", daemon=True
        )
        self._stderr_thread.start()

        # Start stdout reader thread so _send_request never calls blocking readline().
        self._stdout_thread = threading.Thread(
            target=self._read_stdout, name="mcp-stdout-reader", daemon=True
        )
        self._stdout_thread.start()

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

        Reads the response via the stdout queue with a timeout so that the call
        never blocks forever when the server is unresponsive (Windows pipe
        deadlock scenario or server crash).

        Args:
            method: The JSON-RPC method name
            params: Parameters for the method

        Returns:
            The JSON-RPC response as a dictionary

        Raises:
            RuntimeError: If process not started, communication fails, or
                the server does not respond within ``_RESPONSE_TIMEOUT`` seconds
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

        # Read response via queue with timeout — never blocks forever.
        try:
            response_line = self._stdout_queue.get(timeout=_RESPONSE_TIMEOUT)
        except queue.Empty as err:
            stderr_snippet = "".join(self._stderr_lines[-20:])
            error_msg = (
                f"MCP server did not respond within {_RESPONSE_TIMEOUT}s "
                f"(method={method!r}).\n"
                f"Last stderr output:\n{stderr_snippet}"
            )
            raise RuntimeError(error_msg) from err

        if response_line is None:
            # Sentinel: stdout EOF — server exited unexpectedly.
            stderr_snippet = "".join(self._stderr_lines[-20:])
            error_msg = (
                f"MCP server stdout closed unexpectedly (method={method!r}).\n"
                f"Last stderr output:\n{stderr_snippet}"
            )
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

        Sends termination signal, waits for process to exit, then joins the
        background drain and reader threads with a short timeout.
        """
        if self.process is not None:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()
            self.process = None

        # Join background threads — they are daemons so they won't block exit,
        # but joining ensures clean teardown during normal test runs.
        if self._stderr_thread is not None:
            self._stderr_thread.join(timeout=2)
            self._stderr_thread = None

        if self._stdout_thread is not None:
            self._stdout_thread.join(timeout=2)
            self._stdout_thread = None

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

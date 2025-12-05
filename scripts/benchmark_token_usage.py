"""Benchmark comparing token usage between raw file operations and MCP tools.

This script measures and compares the token efficiency of different approaches
for reading and editing JSON configuration files, including:
- Raw file reads (full file)
- Smart raw reads (grep + context)
- MCP tool reads (specific queries)
- Raw edits (full file rewrite)
- Smart raw edits (sed)
- MCP tool edits (specific updates)
"""

import json
import subprocess
import time
from pathlib import Path
from typing import Any

import tiktoken

from mcp_json_yaml_toml.yq_wrapper import execute_yq

# Setup
TEST_FILE = Path("benchmark_test.json")
NUM_ITEMS = 1000


def setup_test_file() -> dict[str, Any]:
    """Create a test JSON file with sample user data for benchmarking."""
    data = {
        "users": [
            {
                "id": i,
                "name": f"User {i}",
                "email": f"user{i}@example.com",
                "preferences": {
                    "theme": "dark" if i % 2 == 0 else "light",
                    "notifications": True,
                },
            }
            for i in range(NUM_ITEMS)
        ],
        "settings": {"version": "1.0.0", "maintenance": False},
    }
    with Path(TEST_FILE).open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    return data


def count_tokens(text: str) -> int:
    """Count the number of tokens in a text string using cl100k_base encoding."""
    enc = tiktoken.get_encoding("cl100k_base")
    return len(enc.encode(text))


def benchmark_raw_read() -> tuple[int, float]:
    """Benchmark reading an entire file and counting its tokens."""
    start = time.time()
    with Path(TEST_FILE).open(encoding="utf-8") as f:
        content = f.read()
    duration = time.time() - start
    tokens = count_tokens(content)
    return tokens, duration


def benchmark_smart_raw_read() -> tuple[int, float]:
    """Simulate 'grep -n "version" file' then 'read_file(start, end)'."""
    start = time.time()

    # 1. Grep to find line number
    grep_cmd = ["grep", "-n", "version", str(TEST_FILE)]
    grep_result = subprocess.run(grep_cmd, check=False, capture_output=True, text=True)

    if not grep_result.stdout:
        return 0, time.time() - start

    # Parse line number (simplified, assumes first match)
    try:
        line_num = int(grep_result.stdout.split(":")[0])
    except (ValueError, IndexError):
        return 0, time.time() - start

    # 2. Read context (e.g., 10 lines around match)
    # In a real agent scenario, this would be a tool call like read_file(start_line, end_line)
    start_line = max(1, line_num - 5)
    end_line = line_num + 5

    with Path(TEST_FILE).open(encoding="utf-8") as f:
        lines = f.readlines()
        # Adjust for 0-indexing
        context_lines = lines[start_line - 1 : end_line]
        content = "".join(context_lines)

    duration = time.time() - start

    # Tokens:
    # 1. User asking to grep (approx) + Grep output
    grep_tokens = count_tokens(f'grep -n "version" {TEST_FILE}') + count_tokens(
        grep_result.stdout
    )
    # 2. User asking to read file range + File content
    read_tokens = count_tokens(
        f'read_file(path="{TEST_FILE}", start_line={start_line}, end_line={end_line})'
    ) + count_tokens(content)

    return grep_tokens + read_tokens, duration


def benchmark_raw_edit() -> tuple[int, float]:
    """Benchmark editing a file by reading, modifying, and rewriting entirely."""
    tokens_read, _ = benchmark_raw_read()

    # Simulate modification
    with Path(TEST_FILE).open(encoding="utf-8") as f:
        data = json.load(f)
    data["settings"]["maintenance"] = True

    start = time.time()
    new_content = json.dumps(data, indent=2)
    with Path(TEST_FILE).open("w", encoding="utf-8") as f:
        f.write(new_content)
    duration = time.time() - start

    tokens_write = count_tokens(new_content)
    return tokens_read + tokens_write, duration


def benchmark_smart_raw_edit_sed() -> tuple[int, float]:
    """Simulate 'sed -i ...' to replace a value.

    Risk: High (regex fragility). Cost: Low.
    """
    start = time.time()

    # Simulate agent constructing a sed command
    # sed -i 's/"maintenance": false/"maintenance": true/' file
    sed_cmd = [
        "sed",
        "-i",
        's/"maintenance": false/"maintenance": true/',
        str(TEST_FILE),
    ]

    subprocess.run(sed_cmd, check=True)
    duration = time.time() - start

    # Tokens: Just the command execution
    input_str = f'run_command(command="sed -i \'s/"maintenance": false/"maintenance": true/\' {TEST_FILE}")'
    tokens = count_tokens(input_str)
    # Output is usually empty or exit code
    tokens += count_tokens("Exit code: 0")

    return tokens, duration


def benchmark_mcp_read_specific() -> tuple[int, float]:
    """Benchmark reading a specific value using MCP data_query tool."""
    start = time.time()
    # Simulate data_query tool logic
    result = execute_yq(
        ".settings.version",
        input_file=TEST_FILE,
        input_format="json",
        output_format="json",
    )
    duration = time.time() - start

    # Input tokens: Tool call arguments (approx)
    input_str = f'data_query(file_path="{TEST_FILE}", expression=".settings.version")'
    input_tokens = count_tokens(input_str)

    # Output tokens: Result
    # The tool wraps the result in a dict structure
    output_data = {
        "success": True,
        "result": result.data,
        "format": "json",
        "file": str(TEST_FILE),
    }
    output_str = json.dumps(output_data)
    output_tokens = count_tokens(output_str)

    return input_tokens + output_tokens, duration


def benchmark_mcp_edit_specific() -> tuple[int, float]:
    """Benchmark editing a specific value using MCP data tool."""
    start = time.time()
    # Simulate data tool logic for set operation
    # Note: yq expression for setting boolean is just assignment
    execute_yq(
        ".settings.maintenance = true",
        input_file=TEST_FILE,
        input_format="json",
        output_format="json",
        in_place=True,
    )
    duration = time.time() - start

    # Input tokens
    input_str = f'data(file_path="{TEST_FILE}", operation="set", key_path="settings.maintenance", value="true", in_place=True)'
    input_tokens = count_tokens(input_str)

    # Output tokens
    output_data = {
        "success": True,
        "modified_in_place": True,
        "result": "File modified successfully",
        "file": str(TEST_FILE),
    }
    output_str = json.dumps(output_data)
    output_tokens = count_tokens(output_str)

    return input_tokens + output_tokens, duration


def main() -> None:
    """Run all benchmarks and display comparison results."""
    print("Setting up test file...")
    setup_test_file()

    print(f"File size: {Path(TEST_FILE).stat().st_size} bytes")
    print("-" * 80)
    print(
        f"{'Operation':<35} | {'Tokens':<10} | {'Ratio (vs Raw)':<15} | {'Risk/Notes'}"
    )
    print("-" * 80)

    # Raw Read
    raw_read_tokens, _ = benchmark_raw_read()
    print(
        f"{'Raw Read (Full File)':<35} | {raw_read_tokens:<10} | {'1.0x':<15} | {'Baseline'}"
    )

    # Smart Raw Read
    smart_read_tokens, _ = benchmark_smart_raw_read()
    ratio_smart_read = (
        raw_read_tokens / smart_read_tokens if smart_read_tokens > 0 else 0
    )
    print(
        f"{'Smart Raw Read (Grep + Context)':<35} | {smart_read_tokens:<10} | {f'{ratio_smart_read:.1f}x cheaper':<15} | {'Multi-step'}"
    )

    # MCP Read
    mcp_read_tokens, _ = benchmark_mcp_read_specific()
    ratio_read = raw_read_tokens / mcp_read_tokens if mcp_read_tokens > 0 else 0
    print(
        f"{'MCP Read (Specific)':<35} | {mcp_read_tokens:<10} | {f'{ratio_read:.1f}x cheaper':<15} | {'Safe, Structured'}"
    )

    print("-" * 80)

    # Raw Edit
    raw_edit_tokens, _ = benchmark_raw_edit()
    print(
        f"{'Raw Edit (Full Rewrite)':<35} | {raw_edit_tokens:<10} | {'1.0x':<15} | {'High Token Cost'}"
    )

    # Smart Raw Edit (Sed)
    smart_edit_tokens, _ = benchmark_smart_raw_edit_sed()
    ratio_smart_edit = (
        raw_edit_tokens / smart_edit_tokens if smart_edit_tokens > 0 else 0
    )
    print(
        f"{'Smart Raw Edit (Sed)':<35} | {smart_edit_tokens:<10} | {f'{ratio_smart_edit:.1f}x cheaper':<15} | {'High Risk (Regex)'}"
    )

    # MCP Edit
    mcp_edit_tokens, _ = benchmark_mcp_edit_specific()
    ratio_edit = raw_edit_tokens / mcp_edit_tokens if mcp_edit_tokens > 0 else 0
    print(
        f"{'MCP Edit (Specific)':<35} | {mcp_edit_tokens:<10} | {f'{ratio_edit:.1f}x cheaper':<15} | {'Safe, Structured'}"
    )

    print("-" * 80)

    # Cleanup
    if Path(TEST_FILE).exists():
        Path(TEST_FILE).unlink()


if __name__ == "__main__":
    main()

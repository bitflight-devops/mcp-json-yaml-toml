"""Tests for data_diff tool and diff service layer."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, cast

import pytest
from fastmcp.exceptions import ToolError

from mcp_json_yaml_toml import server
from mcp_json_yaml_toml.services.diff_operations import (
    build_diff_statistics,
    build_diff_summary,
    compute_diff,
)

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from mcp_json_yaml_toml.models.responses import DiffResponse

# FastMCP 3.x: decorators return the original function directly (no .fn needed).
# Cast resolves mypy "FunctionTool not callable" when tools/diff.py is in the
# same mypy invocation (prek --files).
data_diff_fn = cast("Callable[..., DiffResponse]", server.data_diff)

# ---------------------------------------------------------------------------
# Unit tests: compute_diff
# ---------------------------------------------------------------------------


class TestComputeDiff:
    """Tests for the compute_diff service function."""

    def test_compute_diff_when_identical_dicts_then_returns_empty(self) -> None:
        """Identical dicts produce an empty diff dict."""
        result = compute_diff({"a": 1, "b": "hello"}, {"a": 1, "b": "hello"})
        assert result == {}

    def test_compute_diff_when_values_differ_then_returns_values_changed(self) -> None:
        """Changed values appear under values_changed."""
        result = compute_diff({"a": 1, "b": 2}, {"a": 1, "b": 99})
        assert "values_changed" in result
        assert len(result["values_changed"]) == 1

    def test_compute_diff_when_keys_added_then_returns_dictionary_item_added(
        self,
    ) -> None:
        """New keys in data2 appear under dictionary_item_added."""
        result = compute_diff({"a": 1}, {"a": 1, "b": 2})
        assert "dictionary_item_added" in result

    def test_compute_diff_when_keys_removed_then_returns_dictionary_item_removed(
        self,
    ) -> None:
        """Keys absent in data2 appear under dictionary_item_removed."""
        result = compute_diff({"a": 1, "b": 2}, {"a": 1})
        assert "dictionary_item_removed" in result

    def test_compute_diff_when_ignore_order_true_then_reordered_lists_match(
        self,
    ) -> None:
        """Reordered lists produce empty diff when ignore_order=True."""
        result = compute_diff(
            {"items": [1, 2, 3]}, {"items": [3, 1, 2]}, ignore_order=True
        )
        assert result == {}

    def test_compute_diff_when_ignore_order_false_then_reordered_lists_differ(
        self,
    ) -> None:
        """Reordered lists produce differences when ignore_order=False."""
        result = compute_diff(
            {"items": [1, 2, 3]}, {"items": [3, 1, 2]}, ignore_order=False
        )
        assert result != {}


# ---------------------------------------------------------------------------
# Unit tests: build_diff_statistics
# ---------------------------------------------------------------------------


class TestBuildDiffStatistics:
    """Tests for the build_diff_statistics service function."""

    def test_build_diff_statistics_when_mixed_changes_then_counts_each_type(
        self,
    ) -> None:
        """Statistics correctly count each change type."""
        diff_dict = {
            "values_changed": {"root['a']": {"old_value": 1, "new_value": 2}},
            "dictionary_item_added": {"root['b']": 3, "root['c']": 4},
        }
        stats = build_diff_statistics(diff_dict)
        assert stats["values_changed"] == 1
        assert stats["dictionary_item_added"] == 2

    def test_build_diff_statistics_when_empty_diff_then_returns_empty(self) -> None:
        """Empty diff dict produces empty statistics."""
        stats = build_diff_statistics({})
        assert stats == {}


# ---------------------------------------------------------------------------
# Unit tests: build_diff_summary
# ---------------------------------------------------------------------------


class TestBuildDiffSummary:
    """Tests for the build_diff_summary service function."""

    def test_build_diff_summary_when_no_differences_then_says_identical(self) -> None:
        """When has_differences is False, summary says files are identical."""
        summary = build_diff_summary({}, has_differences=False)
        assert summary == "Files are identical"

    def test_build_diff_summary_when_has_differences_then_returns_readable_string(
        self,
    ) -> None:
        """Summary produces a comma-separated human-readable string."""
        stats = {"values_changed": 3, "dictionary_item_added": 1}
        summary = build_diff_summary(stats, has_differences=True)
        assert "3 values changed" in summary
        assert "1 items added" in summary


# ---------------------------------------------------------------------------
# Integration tests: data_diff tool
# ---------------------------------------------------------------------------


class TestDataDiffTool:
    """Tests for the data_diff MCP tool."""

    def test_data_diff_when_identical_json_files_then_no_differences(
        self, tmp_path: Path
    ) -> None:
        """Identical JSON files produce has_differences=False."""
        data = {"server": {"host": "localhost", "port": 8080}}
        f1 = tmp_path / "a.json"
        f2 = tmp_path / "b.json"
        f1.write_text(json.dumps(data))
        f2.write_text(json.dumps(data))

        result = data_diff_fn(str(f1), str(f2))
        assert result.success is True
        assert result.has_differences is False
        assert result.differences is None
        assert result.statistics is None
        assert "identical" in result.summary.lower()

    def test_data_diff_when_different_json_files_then_has_differences(
        self, tmp_path: Path
    ) -> None:
        """Different JSON files produce has_differences=True with structured diff."""
        f1 = tmp_path / "a.json"
        f2 = tmp_path / "b.json"
        f1.write_text(json.dumps({"a": 1, "b": 2}))
        f2.write_text(json.dumps({"a": 1, "b": 99, "c": 3}))

        result = data_diff_fn(str(f1), str(f2))
        assert result.success is True
        assert result.has_differences is True
        assert result.differences is not None
        assert result.statistics is not None
        assert result.statistics.get("values_changed", 0) >= 1
        assert result.statistics.get("dictionary_item_added", 0) >= 1

    def test_data_diff_when_cross_format_same_content_then_no_differences(
        self, tmp_path: Path
    ) -> None:
        """Cross-format comparison (JSON vs YAML) with same content -> no diff."""
        f_json = tmp_path / "config.json"
        f_yaml = tmp_path / "config.yaml"
        f_json.write_text(json.dumps({"db": {"host": "localhost", "port": 5432}}))
        f_yaml.write_text("db:\n  host: localhost\n  port: 5432\n")

        result = data_diff_fn(str(f_json), str(f_yaml))
        assert result.success is True
        assert result.has_differences is False
        assert result.file1_format == "json"
        assert result.file2_format == "yaml"

    def test_data_diff_when_cross_format_different_content_then_has_differences(
        self, tmp_path: Path
    ) -> None:
        """Cross-format comparison (JSON vs YAML) with different content -> has diff."""
        f_json = tmp_path / "config.json"
        f_yaml = tmp_path / "config.yaml"
        f_json.write_text(json.dumps({"db": {"host": "localhost", "port": 5432}}))
        f_yaml.write_text("db:\n  host: production\n  port: 5432\n")

        result = data_diff_fn(str(f_json), str(f_yaml))
        assert result.success is True
        assert result.has_differences is True

    @pytest.mark.parametrize("missing", ["first", "second"])
    def test_data_diff_when_missing_file_then_raises_error(
        self, tmp_path: Path, missing: str
    ) -> None:
        """Missing file raises ToolError regardless of position."""
        existing = tmp_path / "exists.json"
        existing.write_text("{}")
        nonexistent = str(tmp_path / "nonexistent.json")

        args = (
            (nonexistent, str(existing))
            if missing == "first"
            else (str(existing), nonexistent)
        )

        with pytest.raises(ToolError, match="File not found"):
            data_diff_fn(*args)

    def test_data_diff_when_ignore_order_true_then_reordered_lists_match(
        self, tmp_path: Path
    ) -> None:
        """ignore_order=True makes reordered lists produce no diff."""
        f1 = tmp_path / "a.json"
        f2 = tmp_path / "b.json"
        f1.write_text(json.dumps({"items": [1, 2, 3]}))
        f2.write_text(json.dumps({"items": [3, 1, 2]}))

        # Without ignore_order -> has differences
        result_ordered = data_diff_fn(str(f1), str(f2), ignore_order=False)
        assert result_ordered.has_differences is True

        # With ignore_order -> no differences
        result_unordered = data_diff_fn(str(f1), str(f2), ignore_order=True)
        assert result_unordered.has_differences is False

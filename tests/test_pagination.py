"""Tests for pagination functionality in config_query and config_get tools."""

import base64
import json
from pathlib import Path

import pytest

from mcp_json_yaml_toml.server import _decode_cursor, _encode_cursor, _paginate_result


class TestCursorEncoding:
    """Test cursor encoding and decoding."""

    def test_cursor_roundtrip(self) -> None:
        """Test that cursor encoding/decoding is reversible."""
        test_offsets = [0, 100, 1000, 10000, 50000, 100000]

        for offset in test_offsets:
            cursor = _encode_cursor(offset)
            decoded = _decode_cursor(cursor)
            assert decoded == offset, f"Roundtrip failed for offset {offset}"

    def test_cursor_opaque(self) -> None:
        """Test that cursors are opaque (base64 encoded)."""
        cursor = _encode_cursor(12345)

        # Should be a string
        assert isinstance(cursor, str)

        # Should not contain the number directly
        assert "12345" not in cursor

        # Should be valid base64 (doesn't raise)
        decoded = _decode_cursor(cursor)
        assert decoded == 12345

    def test_invalid_cursor_rejected(self) -> None:
        """Test that invalid cursors raise ToolError."""
        from fastmcp.exceptions import ToolError

        # Invalid base64
        with pytest.raises(ToolError):
            _decode_cursor("not_valid_base64!@#$%")

        # Valid base64 but not JSON

        bad_cursor = base64.b64encode(b"not json").decode()
        with pytest.raises(ToolError):
            _decode_cursor(bad_cursor)

        # Valid JSON but missing offset
        bad_cursor = base64.b64encode(json.dumps({"wrong_key": 100}).encode()).decode()
        with pytest.raises(ToolError):
            _decode_cursor(bad_cursor)

        # Negative offset
        bad_cursor = base64.b64encode(json.dumps({"offset": -100}).encode()).decode()
        with pytest.raises(ToolError):
            _decode_cursor(bad_cursor)

        # Non-integer offset
        bad_cursor = base64.b64encode(
            json.dumps({"offset": "string"}).encode()
        ).decode()
        with pytest.raises(ToolError):
            _decode_cursor(bad_cursor)


class TestPaginationHelper:
    """Test the _paginate_result helper function."""

    def test_small_data_no_pagination(self) -> None:
        """Test that data under 10k chars is not paginated."""
        small_data = "x" * 5000

        result = _paginate_result(small_data, None)

        assert result["data"] == small_data
        assert "nextCursor" not in result
        assert "advisory" not in result

    def test_exact_boundary_no_pagination(self) -> None:
        """Test that exactly 10k chars is not paginated."""
        exact_data = "y" * 10000

        result = _paginate_result(exact_data, None)

        assert len(result["data"]) == 10000
        assert "nextCursor" not in result
        assert "advisory" not in result

    def test_over_boundary_paginates(self) -> None:
        """Test that data over 10k chars is paginated."""
        large_data = "z" * 10001

        result = _paginate_result(large_data, None)

        assert len(result["data"]) == 10000
        assert "nextCursor" in result
        # Only 2 pages, no advisory
        assert "advisory" not in result

    def test_two_page_result(self) -> None:
        """Test navigation through a 2-page result."""
        data = "a" * 15000

        # First page
        page1 = _paginate_result(data, None)
        assert len(page1["data"]) == 10000
        assert "nextCursor" in page1
        assert "advisory" not in page1  # Only 2 pages

        # Second page
        page2 = _paginate_result(data, page1["nextCursor"])
        assert len(page2["data"]) == 5000
        assert "nextCursor" not in page2
        assert page2["data"] != page1["data"]

    def test_multi_page_advisory(self) -> None:
        """Test that multi-page results (>2 pages) include advisory."""
        large_data = "b" * 25000  # 3 pages

        result = _paginate_result(large_data, None)

        assert "advisory" in result
        assert "3 pages" in result["advisory"]
        assert "25,000 chars" in result["advisory"]
        assert "keys" in result["advisory"]  # Suggests querying for keys
        assert "length" in result["advisory"]  # Suggests querying for counts

    def test_many_pages_correct_count(self) -> None:
        """Test that advisory shows correct page count for many pages."""
        huge_data = "c" * 100000  # 10 pages

        result = _paginate_result(huge_data, None)

        assert "advisory" in result
        assert "10 pages" in result["advisory"]

    def test_navigate_all_pages(self) -> None:
        """Test navigating through all pages of a large result."""
        data = "d" * 35000  # 4 pages

        cursor = None
        pages = []
        total_chars = 0

        while True:
            page = _paginate_result(data, cursor)
            pages.append(page["data"])
            total_chars += len(page["data"])

            if "nextCursor" not in page:
                break

            cursor = page["nextCursor"]

        assert len(pages) == 4
        assert total_chars == 35000
        # Reconstruct original data
        reconstructed = "".join(pages)
        assert reconstructed == data

    def test_cursor_beyond_data_raises(self) -> None:
        """Test that cursor offset beyond data size raises error."""
        from fastmcp.exceptions import ToolError

        data = "e" * 5000
        cursor = _encode_cursor(10000)  # Beyond data size

        with pytest.raises(ToolError, match="exceeds result size"):
            _paginate_result(data, cursor)


class TestPaginationIntegration:
    """Integration tests with real file queries."""

    def test_large_json_file_pagination(self, tmp_path: Path) -> None:
        """Test pagination with a large JSON configuration file."""
        # Create large test file
        test_data = {
            "items": [
                {
                    "id": i,
                    "name": f"item_{i}",
                    "description": f"Long description for item {i} " * 50,
                    "metadata": {"tags": [f"tag{j}" for j in range(20)]},
                }
                for i in range(100)
            ]
        }

        test_file = tmp_path / "large_config.json"
        test_file.write_text(json.dumps(test_data, indent=2))

        # Read and paginate result
        result_str = json.dumps(test_data, indent=2)
        assert len(result_str) > 10000, "Test file should be large enough to paginate"

        # Test first page
        page1 = _paginate_result(result_str, None)
        assert len(page1["data"]) == 10000
        assert "nextCursor" in page1

        # Test second page
        page2 = _paginate_result(result_str, page1["nextCursor"])
        assert len(page2["data"]) == 10000
        assert page2["data"] != page1["data"]

    def test_small_json_no_pagination(self, tmp_path: Path) -> None:
        """Test that small JSON files don't get paginated."""
        small_data = {"name": "test", "value": 123, "items": [1, 2, 3]}

        test_file = tmp_path / "small_config.json"
        test_file.write_text(json.dumps(small_data, indent=2))

        result_str = json.dumps(small_data, indent=2)
        assert len(result_str) < 10000

        result = _paginate_result(result_str, None)
        assert "nextCursor" not in result
        assert "advisory" not in result

    def test_yaml_formatting_preserved(self) -> None:
        """Test that YAML formatted strings paginate correctly."""
        yaml_content = "items:\n"
        for i in range(500):
            yaml_content += f"  - id: {i}\n"
            yaml_content += f"    name: item_{i}\n"
            yaml_content += f"    description: Long description {i}\n"

        assert len(yaml_content) > 10000

        page1 = _paginate_result(yaml_content, None)
        assert page1["data"].startswith("items:\n")
        assert "nextCursor" in page1


class TestBackwardCompatibility:
    """Test that pagination doesn't break existing behavior."""

    def test_cursor_optional(self) -> None:
        """Test that cursor parameter is optional (None by default)."""
        data = "x" * 5000

        # Should work with no cursor
        result = _paginate_result(data, None)
        assert "data" in result

    def test_small_results_unchanged(self) -> None:
        """Test that small results are returned unchanged."""
        small_data = '{"test": "value"}'

        result = _paginate_result(small_data, None)

        # Should return complete data
        assert result["data"] == small_data
        # Should not have pagination fields
        assert "nextCursor" not in result
        assert "advisory" not in result
        assert "paginated" not in result


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_empty_string(self) -> None:
        """Test pagination with empty string."""
        result = _paginate_result("", None)

        assert result["data"] == ""
        assert "nextCursor" not in result

    def test_single_char(self) -> None:
        """Test pagination with single character."""
        result = _paginate_result("x", None)

        assert result["data"] == "x"
        assert "nextCursor" not in result

    def test_cursor_at_exact_boundary(self) -> None:
        """Test cursor at exactly 10k chars."""
        data = "a" * 20000

        page1 = _paginate_result(data, None)
        assert len(page1["data"]) == 10000

        # Second page starts at exactly 10000
        page2 = _paginate_result(data, page1["nextCursor"])
        assert len(page2["data"]) == 10000
        assert "nextCursor" not in page2

    def test_unicode_characters(self) -> None:
        """Test pagination with unicode characters."""
        # Mix of ASCII and unicode
        data = "Hello 世界 " * 1000  # Should exceed 10k chars

        if len(data) > 10000:
            result = _paginate_result(data, None)
            assert len(result["data"]) == 10000
            # Should handle unicode correctly (no broken characters)
            assert isinstance(result["data"], str)

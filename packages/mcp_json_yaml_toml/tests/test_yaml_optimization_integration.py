"""Integration tests for YAML anchor optimization."""

from pathlib import Path

import pytest

from mcp_json_yaml_toml import server


class TestYAMLOptimizationIntegration:
    """Test YAML optimization in the data tool."""

    @pytest.mark.integration
    def test_set_operation_optimizes_yaml(self, tmp_path: Path) -> None:
        """Test that SET operation automatically optimizes YAML files that already use anchors."""
        # Create a YAML file that ALREADY uses anchors
        test_file = tmp_path / "config.yml"
        test_file.write_text("""default: &default_service
  image: nginx
  ports:
    - "80:80"
  restart: always

services:
  web: *default_service
  api: *default_service
""")

        # Add a third service with the same config
        result = server.data.fn(
            file_path=str(test_file),
            operation="set",
            key_path="services.cache",
            value='{"image": "nginx", "ports": ["80:80"], "restart": "always"}',
        )

        # Should succeed
        assert result["success"] is True
        assert result["result"] == "File modified successfully"

        # Should have optimized (file already uses anchors)
        assert result.get("optimized") is True

        # Read the file and check for anchors
        modified_content = test_file.read_text()
        assert "&" in modified_content  # Should have anchor
        assert "*" in modified_content  # Should have alias

    @pytest.mark.integration
    def test_set_operation_preserves_existing_anchors(self, tmp_path: Path) -> None:
        """Test that existing anchors are preserved."""
        # Create a YAML file that already has anchors
        test_file = tmp_path / ".gitlab-ci.yml"
        test_file.write_text("""default: &default
  image: node:18
  cache:
    paths:
      - node_modules/
  timeout: 30m

job1:
  <<: *default
  script:
    - npm test
""")

        # Add another job
        result = server.data.fn(
            file_path=str(test_file),
            operation="set",
            key_path="job2",
            value='{"image": "node:18", "cache": {"paths": ["node_modules/"]}, "timeout": "30m", "script": ["npm build"]}',
        )

        # Should succeed
        assert result["success"] is True

        # Read the file
        modified_content = test_file.read_text()

        # Should still have anchors
        assert "&" in modified_content
        assert "*" in modified_content

    @pytest.mark.integration
    def test_set_operation_no_optimization_for_json(self, tmp_path: Path) -> None:
        """Test that JSON files are not optimized."""
        # Create a JSON file
        test_file = tmp_path / "config.json"
        test_file.write_text('{"job1": {"image": "node:18"}}')

        # Modify it
        result = server.data.fn(
            file_path=str(test_file), operation="set", key_path="job2", value='{"image": "node:18"}'
        )

        # Should succeed
        assert result["success"] is True

        # Should NOT have optimized (JSON doesn't support anchors)
        assert result.get("optimized") is not True

    @pytest.mark.integration
    @pytest.mark.skip(reason="Removed: dry-run mode no longer exists after in_place parameter removal")
    def test_set_operation_no_optimization_when_not_in_place(self, tmp_path: Path) -> None:
        """Test that optimization only happens with in_place=True."""
        # Create a YAML file
        test_file = tmp_path / "config.yml"
        test_file.write_text("""job1:
  image: node:18
  cache:
    paths:
      - node_modules/
  timeout: 30m
""")

        # Modify without in_place
        result = server.data.fn(
            file_path=str(test_file),
            operation="set",
            key_path="job2",
            value='{"image": "node:18", "cache": {"paths": ["node_modules/"]}, "timeout": "30m"}',
        )

        # Should succeed
        assert result["success"] is True
        # Should NOT have optimized
        assert result.get("optimized") is not True

        # Original file should be unchanged
        original_content = test_file.read_text()
        assert "job2" not in original_content

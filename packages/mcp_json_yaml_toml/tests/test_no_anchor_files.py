"""Test that files without anchors are NOT optimized."""

from pathlib import Path

import pytest

from mcp_json_yaml_toml import server


@pytest.mark.integration
def test_no_optimization_for_files_without_anchors(tmp_path: Path) -> None:
    """Test that YAML files without existing anchors are NOT optimized."""
    # Create a YAML file WITHOUT any anchors
    test_file = tmp_path / "config.yml"
    test_file.write_text("""services:
  web:
    image: nginx
    ports:
      - "80:80"
    restart: always
  api:
    image: nginx
    ports:
      - "80:80"
    restart: always
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

    # Should NOT have optimized (file doesn't use anchors)
    assert result.get("optimized") is not True

    # Read the file - should NOT have anchors
    modified_content = test_file.read_text()
    assert "&" not in modified_content  # Should NOT have anchor
    assert "*" not in modified_content  # Should NOT have alias

    # Should have the new service though
    assert "cache:" in modified_content

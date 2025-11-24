import sys
import json
from pathlib import Path

# Add package to path
sys.path.insert(0, str(Path.cwd() / "packages"))

from mcp_json_yaml_toml.server import data_structure, data_query, data_get

def call_tool(tool, *args, **kwargs):
    func = getattr(tool, "fn", tool)
    return func(*args, **kwargs)

def test_structure():
    print("Testing data_structure...")
    claude_json = Path("fixtures/claude.json").resolve()
    
    if not claude_json.exists():
        print(f"Fixture not found: {claude_json}")
        return

    # Test depth 1
    print(f"Analyzing {claude_json} with depth 1")
    result = call_tool(data_structure, str(claude_json), depth=1)
    print("Result keys:", list(result["result"].keys()))
    
    # Test depth 2
    print(f"\nAnalyzing {claude_json} with depth 2")
    result = call_tool(data_structure, str(claude_json), depth=2)
    # Print a summary of the result
    print("Result summary (truncated):")
    print(json.dumps(result["result"], indent=2)[:500])

def test_hints():
    print("\nTesting hints...")
    gitlab_ci = Path("fixtures/gitlab-ci.yml").resolve()
    
    if not gitlab_ci.exists():
        print(f"Fixture not found: {gitlab_ci}")
        return

    # Query that returns the whole file (which is large)
    print(f"Querying {gitlab_ci} as JSON to trigger pagination")
    result = call_tool(data_query, str(gitlab_ci), ".", output_format="json")
    
    if result.get("paginated"):
        print("Pagination active")
        print("Advisory:", result.get("advisory"))
    else:
        print("Result was not paginated (size:", len(str(result.get("result"))), ")")

if __name__ == "__main__":
    try:
        test_structure()
        test_hints()
    except Exception as e:
        print(f"Test failed: {e}")
        import traceback
        traceback.print_exc()

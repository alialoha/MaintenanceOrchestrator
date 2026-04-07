import json

from mcp_operator.suggested_args import (
    sample_json_for_prompt,
    sample_json_for_tool,
    tool_name_from_dropdown,
)


def test_tool_name_from_dropdown():
    assert tool_name_from_dropdown("read_file (allow)") == "read_file"
    assert tool_name_from_dropdown("") == ""


def test_sample_json_for_tool_known_tools():
    for name in (
        "read_file",
        "write_file",
        "list_files",
        "delete_file",
        "execute_command",
        "analyze_code",
        "check_parts_inventory",
        "list_deliveries_at_risk",
    ):
        raw = sample_json_for_tool(name)
        data = json.loads(raw)
        assert isinstance(data, dict)
        assert len(data) >= 1


def test_sample_json_unknown_tool():
    assert sample_json_for_tool("unknown_xyz") == "{}"


def test_sample_json_for_prompt_known():
    for name in ("review_code", "analyze_security", "security_review"):
        raw = sample_json_for_prompt(name)
        data = json.loads(raw)
        assert isinstance(data, dict)
        assert len(data) >= 1


def test_sample_json_unknown_prompt():
    assert sample_json_for_prompt("unknown_prompt") == "{}"

from agent.mcp_llm_host import MCPLLMHost, risk_levels_map


def test_risk_levels_covers_tools():
    r = risk_levels_map()
    for name in (
        "read_file",
        "list_files",
        "write_file",
        "analyze_code",
        "delete_file",
        "execute_command",
    ):
        assert name in r


def test_detect_tool_use_failed_error():
    assert MCPLLMHost._is_tool_use_failed_error(Exception("tool_use_failed"))
    assert MCPLLMHost._is_tool_use_failed_error(Exception("Failed to call a function"))
    assert not MCPLLMHost._is_tool_use_failed_error(Exception("401 unauthorized"))

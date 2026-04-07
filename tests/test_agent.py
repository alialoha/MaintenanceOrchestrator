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

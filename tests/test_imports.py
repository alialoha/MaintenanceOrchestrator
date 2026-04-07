"""Smoke: all packages import without starting servers."""


def test_import_mcp_server():
    import mcp_server.server

    assert mcp_server.server.mcp is not None
    assert mcp_server.server.WORKSPACE.name == "workspace"


def test_import_mcp_client():
    from mcp_client import MCPPermissionHTTPClient

    assert MCPPermissionHTTPClient is not None


def test_import_agent():
    from agent import MCPLLMHost

    assert MCPLLMHost is not None


def test_import_llm_client():
    from agent import llm_client

    assert llm_client.build_llm_client is not None
    assert llm_client.resolved_llm_model() is not None


def test_import_operator_module():
    import mcp_operator.gradio_app

    assert mcp_operator.gradio_app.OperatorApp is not None


def test_import_web_app():
    import web.app

    assert web.app.app is not None

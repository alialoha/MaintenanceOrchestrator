from web.branding import DEFAULT_AUTHOR_NAME, DEFAULT_REPO_URL, get_branding, read_architecture_svg


def test_branding_defaults():
    b = get_branding()
    assert b["author_name"] == DEFAULT_AUTHOR_NAME
    assert b["repo_url"] == DEFAULT_REPO_URL


def test_architecture_svg_loads():
    svg = read_architecture_svg()
    assert "<svg" in svg
    assert "MCP server" in svg
    assert "MCP client + policy" in svg
    assert "Streamable HTTP" in svg

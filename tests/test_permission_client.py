import json
from pathlib import Path

import pytest

from mcp_client.http_permission_client import MCPPermissionHTTPClient


@pytest.fixture
def permissions_file(tmp_path: Path) -> Path:
    p = tmp_path / "permissions.json"
    p.write_text(
        json.dumps(
            {
                "read_file": "deny",
                "write_file": "ask",
            }
        ),
        encoding="utf-8",
    )
    return p


def test_load_permissions_from_file(permissions_file: Path):
    c = MCPPermissionHTTPClient("http://127.0.0.1:9", permissions_file)
    assert c.permissions["read_file"] == "deny"
    assert c.permissions["write_file"] == "ask"


def test_check_permission_tool_level(permissions_file: Path):
    c = MCPPermissionHTTPClient("http://127.0.0.1:9", permissions_file)
    assert c.check_permission("read_file", {}) == "deny"
    assert c.check_permission("write_file", {}) == "ask"


def test_check_permission_defaults_when_missing_file(tmp_path: Path):
    missing = tmp_path / "nope.json"
    c = MCPPermissionHTTPClient("http://127.0.0.1:9", missing)
    assert c.check_permission("read_file", {}) == "allow"


def test_save_permissions_roundtrip(tmp_path: Path, permissions_file: Path):
    c = MCPPermissionHTTPClient("http://127.0.0.1:9", permissions_file)
    c.permissions["read_file"] = "allow"
    c.save_permissions()
    data = json.loads(permissions_file.read_text(encoding="utf-8"))
    assert data["read_file"] == "allow"

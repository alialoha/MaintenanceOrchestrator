import pytest

from web.app import app


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def test_index_ok(client):
    rv = client.get("/")
    assert rv.status_code == 200
    body = rv.data
    assert b"Secure MCP" in body
    assert b"architecture.svg" in body or b"MCP server" in body
    assert b"Ali Mousavi" in body
    assert b"github.com/alialoha" in body


def test_generate_demo(client):
    rv = client.post(
        "/generate",
        json={"message": "test message", "model": "demo"},
        content_type="application/json",
    )
    assert rv.status_code == 200
    body = rv.get_json()
    assert body["mode"] == "demo"
    assert "response" in body
    assert "test message" in body["response"]


def test_generate_missing_message(client):
    rv = client.post("/generate", json={"model": "demo"}, content_type="application/json")
    assert rv.status_code == 400

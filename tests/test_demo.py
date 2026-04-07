from web.demo import demo_reply


def test_demo_reply_basic():
    out = demo_reply("Hello world")
    assert "[Demo mode" in out
    assert "Hello world" in out


def test_demo_reply_with_error_hint():
    out = demo_reply("x", error_hint="connection refused")
    assert "connection refused" in out
    assert "offline demo" in out.lower()

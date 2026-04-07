import pytest

from agent import llm_client as lc


def test_default_provider_openai(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    assert lc.llm_provider() == "openai"


def test_resolved_model_openai_default(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("LLM_MODEL", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    assert lc.resolved_llm_model() == "gpt-4o-mini"


def test_format_llm_error_hint_groq_401(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("LLM_PROVIDER", "groq")
    h = lc.format_llm_error_hint(Exception("401"))
    assert "GROQ_API_KEY" in h


def test_resolved_model_groq_default(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("LLM_PROVIDER", "groq")
    monkeypatch.delenv("LLM_MODEL", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    assert lc.resolved_llm_model() == "llama-3.3-70b-versatile"


def test_groq_ignores_openai_model_env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("LLM_PROVIDER", "groq")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-4o-mini")
    monkeypatch.delenv("LLM_MODEL", raising=False)
    assert lc.resolved_llm_model() == "llama-3.3-70b-versatile"


def test_live_groq_with_key(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("LLM_PROVIDER", "groq")
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test")
    monkeypatch.setenv("WEB_ENABLE_LIVE", "1")
    assert lc.live_llm_configured() is True


def test_live_groq_openai_key_fallback(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("LLM_PROVIDER", "groq")
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-x")
    monkeypatch.setenv("WEB_ENABLE_LIVE", "1")
    assert lc.live_llm_configured() is True


def test_build_groq_client(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("LLM_PROVIDER", "groq")
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test")
    c = lc.build_llm_client()
    assert c is not None
    assert str(c.base_url).rstrip("/").endswith("/openai/v1")


def test_live_cerebras_with_key(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("LLM_PROVIDER", "cerebras")
    monkeypatch.setenv("CEREBRAS_API_KEY", "csk_test")
    monkeypatch.setenv("WEB_ENABLE_LIVE", "1")
    assert lc.live_llm_configured() is True


def test_build_cerebras_client(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("LLM_PROVIDER", "cerebras")
    monkeypatch.setenv("CEREBRAS_API_KEY", "csk_test")
    c = lc.build_llm_client()
    assert "cerebras" in str(c.base_url).lower()


def test_live_custom_requires_base_and_key(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("LLM_PROVIDER", "custom")
    monkeypatch.setenv("OPENAI_BASE_URL", "http://127.0.0.1:9999/v1")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("WEB_ENABLE_LIVE", "1")
    assert lc.live_llm_configured() is False


def test_live_custom_configured(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("LLM_PROVIDER", "custom")
    monkeypatch.setenv("OPENAI_BASE_URL", "http://127.0.0.1:9999/v1")
    monkeypatch.setenv("OPENAI_API_KEY", "x")
    monkeypatch.setenv("WEB_ENABLE_LIVE", "1")
    assert lc.live_llm_configured() is True


def test_llm_model_overrides_groq(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("LLM_PROVIDER", "groq")
    monkeypatch.setenv("LLM_MODEL", "llama-3.1-8b-instant")
    assert lc.resolved_llm_model() == "llama-3.1-8b-instant"


def test_live_openai_requires_key(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("WEB_ENABLE_LIVE", "1")
    assert lc.live_llm_configured() is False


def test_live_openai_with_key(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("WEB_ENABLE_LIVE", "1")
    assert lc.live_llm_configured() is True


def test_live_github_disabled(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("LLM_PROVIDER", "github")
    monkeypatch.setenv("GITHUB_TOKEN", "github_pat_x")
    monkeypatch.setenv("WEB_ENABLE_LIVE", "1")
    assert lc.live_llm_configured() is False


def test_build_github_raises(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("LLM_PROVIDER", "github")
    monkeypatch.setenv("GITHUB_TOKEN", "x")
    with pytest.raises(ValueError, match="not supported"):
        lc.build_llm_client()


def test_build_openai_client_construct_only(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key-for-construct-only")
    c = lc.build_llm_client()
    assert c is not None

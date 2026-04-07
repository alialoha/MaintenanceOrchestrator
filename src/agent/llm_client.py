"""OpenAI SDK clients for Live mode — OpenAI-compatible providers (Groq, Cerebras, custom URL).

Key setup ideas: https://github.com/vossenwout/free-llm-apis
"""
from __future__ import annotations

import os

from openai import OpenAI

GROQ_BASE_URL = "https://api.groq.com/openai/v1"
CEREBRAS_BASE_URL = "https://api.cerebras.ai/v1"


def llm_provider() -> str:
    """openai | groq | cerebras | custom"""
    return os.environ.get("LLM_PROVIDER", "openai").strip().lower()


def default_llm_model() -> str:
    p = llm_provider()
    if p == "groq":
        return (
            os.environ.get("GROQ_DEFAULT_MODEL", "llama-3.3-70b-versatile").strip()
            or "llama-3.3-70b-versatile"
        )
    if p == "cerebras":
        return (
            os.environ.get(
                "CEREBRAS_DEFAULT_MODEL", "llama-4-scout-17b-16e-instruct"
            ).strip()
            or "llama-4-scout-17b-16e-instruct"
        )
    return "gpt-4o-mini"


def resolved_llm_model() -> str:
    """LLM_MODEL → OPENAI_MODEL (openai/custom only) → provider default."""
    p = llm_provider()
    if p in ("groq", "cerebras"):
        raw = os.environ.get("LLM_MODEL", "").strip()
        if raw:
            return raw
        return default_llm_model()
    raw = (
        os.environ.get("LLM_MODEL", "").strip()
        or os.environ.get("OPENAI_MODEL", "").strip()
    )
    if not raw:
        return default_llm_model()
    return raw


def format_llm_error_hint(exc: BaseException) -> str:
    text = str(exc)
    low = text.lower()
    p = llm_provider()
    if "401" in text or "unauthorized" in low:
        if p == "groq":
            return f"{text}\n\nHint: Set GROQ_API_KEY (https://console.groq.com/keys)."
        if p == "cerebras":
            return f"{text}\n\nHint: Set CEREBRAS_API_KEY (https://cloud.cerebras.ai/)."
        return (
            f"{text}\n\n"
            "Hint: Set OPENAI_API_KEY, or LLM_PROVIDER=groq with GROQ_API_KEY, "
            "or LLM_PROVIDER=cerebras with CEREBRAS_API_KEY."
        )
    return text


def build_llm_client() -> OpenAI:
    """OpenAI-compatible client (tool calling for Groq/Cerebras/OpenAI)."""
    p = llm_provider()
    if p == "github":
        raise ValueError(
            "LLM_PROVIDER=github is not supported. Use openai, groq, cerebras, or custom "
            "(see .env.example)."
        )

    if p == "groq":
        key = (
            os.environ.get("GROQ_API_KEY", "").strip()
            or os.environ.get("OPENAI_API_KEY", "").strip()
        )
        if not key:
            raise ValueError(
                "LLM_PROVIDER=groq requires GROQ_API_KEY (or OPENAI_API_KEY) — "
                "https://console.groq.com/keys"
            )
        return OpenAI(api_key=key, base_url=GROQ_BASE_URL)

    if p == "cerebras":
        key = os.environ.get("CEREBRAS_API_KEY", "").strip()
        if not key:
            raise ValueError(
                "LLM_PROVIDER=cerebras requires CEREBRAS_API_KEY — "
                "https://cloud.cerebras.ai/"
            )
        return OpenAI(api_key=key, base_url=CEREBRAS_BASE_URL)

    if p == "custom":
        base = os.environ.get("OPENAI_BASE_URL", "").strip().rstrip("/")
        key = os.environ.get("OPENAI_API_KEY", "").strip()
        if not base or not key:
            raise ValueError(
                "LLM_PROVIDER=custom requires OPENAI_BASE_URL and OPENAI_API_KEY."
            )
        return OpenAI(api_key=key, base_url=base)

    if p not in ("openai", ""):
        raise ValueError(
            f"Unknown LLM_PROVIDER={p!r}. Use openai, groq, cerebras, or custom."
        )

    return OpenAI()


def live_llm_configured() -> bool:
    if os.environ.get("WEB_ENABLE_LIVE", "1") in ("0", "false", "False"):
        return False
    p = llm_provider()
    if p == "github":
        return False
    if p == "groq":
        return bool(
            os.environ.get("GROQ_API_KEY", "").strip()
            or os.environ.get("OPENAI_API_KEY", "").strip()
        )
    if p == "cerebras":
        return bool(os.environ.get("CEREBRAS_API_KEY", "").strip())
    if p == "custom":
        return bool(
            os.environ.get("OPENAI_BASE_URL", "").strip()
            and os.environ.get("OPENAI_API_KEY", "").strip()
        )
    return bool(os.environ.get("OPENAI_API_KEY", "").strip())

"""Deterministic replies when live LLM is unavailable or user selects Demo."""


def demo_reply(user_message: str, error_hint: str | None = None) -> str:
    text = (user_message or "").strip()[:400]
    extra = ""
    if error_hint:
        extra = f"\n\n(Live mode failed: {error_hint}. Showing offline demo.)"
    return (
        "[Demo mode — no live LLM] This is a canned response so the UI stays usable "
        "without API keys or when the model is unreachable.\n\n"
        f"You said: «{text}»\n\n"
        "The full experience uses tool-calling (OpenAI-compatible API) against the MCP HTTP server "
        "(same stack as the Operator console). Set LLM credentials per .env.example (OpenAI, Groq, Cerebras, custom URL, etc.) and choose **Live**."
        f"{extra}"
    )

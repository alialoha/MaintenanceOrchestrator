"""Single chat completion using the same config as Live mode (manual smoke test).

From repo root (with .env configured):

  set PYTHONPATH=src
  python scripts/llm_smoke_test.py

Requires network access and valid credentials for the selected LLM_PROVIDER.
"""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from dotenv import load_dotenv

load_dotenv(_ROOT / ".env")

from agent.llm_client import build_llm_client, llm_provider, resolved_llm_model


def main() -> None:
    p = llm_provider()
    model = resolved_llm_model()
    print(f"LLM_PROVIDER={p}  model={model}", flush=True)
    client = build_llm_client()
    r = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": "Reply with exactly: OK"}],
        max_tokens=32,
    )
    text = (r.choices[0].message.content or "").strip()
    print(text, flush=True)


if __name__ == "__main__":
    main()

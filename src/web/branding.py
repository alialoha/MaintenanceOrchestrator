"""Author, repo URL, and shared architecture asset for Flask + Gradio."""
from __future__ import annotations

import os
from pathlib import Path

DEFAULT_AUTHOR_NAME = "Ali Mousavi"
DEFAULT_REPO_URL = "https://github.com/alialoha/secure-agentic-mcp"
DEFAULT_COMPANY_NAME = "Penske Demo"
DEFAULT_LOGO_PATH = "/static/penske-demo-logo.svg"


def get_branding() -> dict[str, str]:
    return {
        "author_name": os.environ.get("AUTHOR_NAME", DEFAULT_AUTHOR_NAME),
        "repo_url": os.environ.get("REPO_URL", DEFAULT_REPO_URL),
        "company_name": os.environ.get("COMPANY_NAME", DEFAULT_COMPANY_NAME),
        "logo_path": os.environ.get("LOGO_PATH", DEFAULT_LOGO_PATH),
    }


def read_architecture_svg() -> str:
    p = Path(__file__).resolve().parent / "static" / "architecture.svg"
    return p.read_text(encoding="utf-8")

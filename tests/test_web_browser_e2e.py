from __future__ import annotations

import os
import subprocess
import time

import pytest


@pytest.mark.skipif(os.environ.get("RUN_BROWSER_TESTS") != "1", reason="Browser tests disabled unless RUN_BROWSER_TESTS=1")
def test_flask_browser_demo_flow():
    pw = pytest.importorskip("playwright.sync_api")
    sync_playwright = pw.sync_playwright
    env = os.environ.copy()
    env["PYTHONPATH"] = "src"
    env["FLASK_HOST"] = "127.0.0.1"
    env["FLASK_PORT"] = "5005"
    env["WEB_ENABLE_LIVE"] = "0"

    proc = subprocess.Popen(
        [".venv/Scripts/python.exe" if os.name == "nt" else "python", "-m", "web.app"],
        cwd=".",
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        base = "http://127.0.0.1:5005"
        deadline = time.time() + 20
        while time.time() < deadline:
            try:
                import urllib.request

                with urllib.request.urlopen(base, timeout=1):
                    break
            except Exception:
                time.sleep(0.25)
        else:
            raise AssertionError("Flask app did not start for browser e2e")

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(base, wait_until="domcontentloaded")
            assert "secure-agentic-mcp" in page.content().lower()
            page.fill("textarea", "Test browser flow")
            page.click("button[type='submit']")
            page.wait_for_timeout(800)
            content = page.content().lower()
            assert ("response" in content) or ("demo" in content)
            browser.close()
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()

"""Streamable HTTP transport: MCP session, tools/list, and tools/call (in-process uvicorn)."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager, suppress
from typing import Literal

import httpx

from fastmcp import FastMCP
from fastmcp.client import Client, StreamableHttpTransport
from fastmcp.utilities.http import find_available_port

from mcp_server.server import mcp


_QUIET_LOGGERS = (
    "uvicorn",
    "uvicorn.access",
    "uvicorn.error",
    "starlette",
    "fastmcp",
    "mcp",
    "httpx",
    "httpcore",
)


@asynccontextmanager
async def _run_mcp_http_quiet(
    server: FastMCP,
    *,
    port: int | None = None,
    transport: Literal["http", "streamable-http", "sse"] = "http",
    path: str = "/mcp",
    host: str = "127.0.0.1",
) -> AsyncGenerator[str, None]:
    """Like fastmcp's ``run_server_async``, but minimal uvicorn/access + library noise."""
    if port is None:
        port = find_available_port()
    await asyncio.sleep(0.01)

    saved = [(name, logging.getLogger(name).getEffectiveLevel()) for name in _QUIET_LOGGERS]
    for name in _QUIET_LOGGERS:
        logging.getLogger(name).setLevel(logging.CRITICAL)

    server_task = asyncio.create_task(
        server.run_http_async(
            host=host,
            port=port,
            transport=transport,
            path=path,
            show_banner=False,
            log_level="critical",
            uvicorn_config={
                "log_level": "critical",
                "access_log": False,
            },
        )
    )
    try:
        await server._started.wait()
        await asyncio.sleep(0.1)
        yield f"http://{host}:{port}{path}"
    finally:
        server_task.cancel()
        with suppress(asyncio.CancelledError, asyncio.TimeoutError):
            await asyncio.wait_for(server_task, timeout=2.0)
        # Uvicorn may log lifespan CancelledError after the task boundary; drain quietly.
        await asyncio.sleep(0)
        for name, level in saved:
            logging.getLogger(name).setLevel(level)


def _base_url(mcp_url: str) -> str:
    """run_server_async yields `http://host:port/mcp`; root status page is `http://host:port/`."""
    if mcp_url.endswith("/mcp"):
        return mcp_url[: -len("/mcp")] + "/"
    return mcp_url.rstrip("/") + "/"


def test_mcp_streamable_http_session_tools_and_calls():
    phase1_tools = {
        "fetch_vehicle_faults",
        "lookup_fault_resolution",
        "score_fault_severity",
        "get_maintenance_history",
        "predict_maintenance_need",
        "create_work_order",
        "request_approval",
        "record_decision_log",
        "get_audit_trail",
        "estimate_repair_duration",
        "check_parts_inventory",
        "propose_service_appointment",
        "reserve_service_slot",
        "list_deliveries_at_risk",
        "estimate_delay_impact",
        "generate_operator_summary",
        "generate_customer_update",
    }

    async def _run() -> None:
        async with _run_mcp_http_quiet(mcp, path="/mcp", transport="http") as url:
            root = _base_url(url)
            async with httpx.AsyncClient(timeout=10.0) as http:
                r = await http.get(root)
                r.raise_for_status()
                assert b"MCP HTTP server is running" in r.content
                assert b"/mcp" in r.content

            async with Client(StreamableHttpTransport(url)) as client:
                tools = await client.list_tools()
                names = {t.name for t in tools}
                missing = phase1_tools - names
                assert not missing, f"Missing maintenance tools over HTTP: {missing}"

                res = await client.call_tool(
                    "lookup_fault_resolution", {"spn": 102, "fmi": 3}
                )
                assert res.is_error is False
                assert res.data is not None
                payload = res.data if isinstance(res.data, dict) else res.structured_content
                assert payload is not None
                assert payload.get("ok") is True
                assert payload["result"]["spn"] == 102
                assert payload["result"]["fmi"] == 3

                res2 = await client.call_tool(
                    "fetch_vehicle_faults",
                    {"vehicle_id": "64940", "lookback_hours": 720},
                )
                assert res2.is_error is False
                p2 = res2.data if isinstance(res2.data, dict) else res2.structured_content
                assert p2.get("ok") is True
                assert p2["result"]["vehicle_id"] == "64940"
                assert isinstance(p2["result"]["faults"], list)

                # Second session on same server (same asyncio loop — required for FastMCP `_started`)
                async with Client(StreamableHttpTransport(url)) as client2:
                    assert len(await client2.list_tools()) == len(tools)

    # Subprocess lifespan teardown logs CancelledError to stderr after the client disconnects;
    # keep stderr quiet for this run so ``pytest -s`` stays readable.
    with open(os.devnull, "w", encoding="utf-8") as devnull:
        with contextlib.redirect_stderr(devnull):
            asyncio.run(_run())

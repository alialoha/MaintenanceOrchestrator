from __future__ import annotations

import asyncio
import os
import time
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request

from agent.llm_client import (
    format_llm_error_hint,
    live_llm_configured,
    llm_provider,
    resolved_llm_model,
)
from agent.mcp_llm_host import MCPLLMHost
import mcp_server.server as mcp_srv
from web.branding import get_branding
from web.demo import demo_reply

_ROOT = Path(__file__).resolve().parent
_REPO = _ROOT.parents[2]
load_dotenv(_REPO / ".env")

# One-line hint so Live mode shows which provider and model are configured.
def _log_llm_backend() -> None:
    p = llm_provider()
    m = resolved_llm_model()
    labels = {
        "openai": "OpenAI API",
        "groq": "Groq",
        "cerebras": "Cerebras",
        "custom": "Custom OPENAI_BASE_URL",
    }
    label = labels.get(p, p)
    extra = ""
    if p == "github":
        extra = "  (unsupported — set LLM_PROVIDER to openai, groq, cerebras, or custom)"
    elif not live_llm_configured():
        extra = "  credentials=MISSING"
    print(
        f"[secure-agentic-mcp] LLM: {label}  model={m}{extra}",
        flush=True,
    )


_log_llm_backend()

app = Flask(
    __name__,
    template_folder=str(_ROOT / "templates"),
    static_folder=str(_ROOT / "static"),
)


def _live_allowed() -> bool:
    return live_llm_configured()


def _run_chat(message: str) -> str:
    host = MCPLLMHost()
    return asyncio.run(host.chat(message))


def _fleet_vehicle_ids(limit: int = 30) -> list[str]:
    vids = list(mcp_srv._load_vehicles().keys())
    return vids[: max(1, min(limit, len(vids)))]


def _fleet_rows(limit: int = 30) -> list[dict]:
    rows: list[dict] = []
    for vid in _fleet_vehicle_ids(limit):
        pred = mcp_srv.predict_maintenance_need(vid)
        pred_r = pred.get("result") if pred.get("ok") else {}
        prob = float((pred_r or {}).get("maintenance_need_probability", 0.0) or 0.0)
        sev = "high" if prob >= 0.75 else "medium" if prob >= 0.45 else "low"
        risk = mcp_srv.list_deliveries_at_risk(vid, horizon_hours=72)
        risk_count = int(((risk.get("result") or {}).get("count", 0)) if risk.get("ok") else 0)
        maint = mcp_srv.get_maintenance_history(vid, limit=1)
        last_event = ""
        if maint.get("ok"):
            events = (maint.get("result") or {}).get("events", [])
            if events:
                last_event = events[0].get("event_date", "")
        rows.append(
            {
                "vehicle_id": vid,
                "maintenance_need_probability": round(prob, 4),
                "severity_label": sev,
                "deliveries_at_risk_72h": risk_count,
                "last_event_date": last_event,
            }
        )
    rows.sort(key=lambda r: (r["maintenance_need_probability"], r["deliveries_at_risk_72h"]), reverse=True)
    return rows


def _fleet_map_points(limit: int = 50) -> list[dict]:
    points: list[dict] = []
    vids = _fleet_vehicle_ids(limit)
    for idx, vid in enumerate(vids):
        slice_rows = mcp_srv._risk_rows_for_vehicle(vid)
        if not slice_rows:
            continue
        row = slice_rows[-1]
        lat = float(row.get("vehicle_gps_latitude", 0.0) or 0.0)
        lon = float(row.get("vehicle_gps_longitude", 0.0) or 0.0)
        if not lat or not lon:
            continue
        pred = mcp_srv.predict_maintenance_need(vid)
        prob = float(((pred.get("result") or {}).get("maintenance_need_probability", 0.0)) if pred.get("ok") else 0.0)
        severity = "high" if prob >= 0.75 else "medium" if prob >= 0.45 else "low"
        points.append(
            {
                "vehicle_id": vid,
                "lat": lat,
                "lon": lon,
                "severity": severity,
                "maintenance_need_probability": round(prob, 4),
                "label": f"{vid} | {severity}",
                "order": idx,
            }
        )
    return points


@app.route("/")
def index():
    b = get_branding()
    return render_template(
        "index.html",
        live_available=_live_allowed(),
        author_name=b["author_name"],
        repo_url=b["repo_url"],
    )


@app.route("/generate", methods=["POST"])
def generate():
    data = request.get_json(silent=True) or {}
    user_message = data.get("message")
    mode = data.get("model", "demo")

    if not user_message:
        return jsonify({"error": "Missing message"}), 400

    start = time.time()

    if mode == "demo":
        return jsonify(
            {
                "response": demo_reply(user_message),
                "duration": time.time() - start,
                "mode": "demo",
            }
        )

    if mode == "live":
        if not _live_allowed():
            return jsonify(
                {
                    "response": demo_reply(
                        user_message,
                        error_hint="No LLM credentials for the selected LLM_PROVIDER (see .env.example) or WEB_ENABLE_LIVE=0",
                    ),
                    "duration": time.time() - start,
                    "mode": "demo",
                }
            )
        try:
            text = _run_chat(user_message)
            return jsonify(
                {
                    "response": text,
                    "duration": time.time() - start,
                    "mode": "live",
                }
            )
        except Exception as e:
            hint = format_llm_error_hint(e)
            return jsonify(
                {
                    "response": demo_reply(user_message, error_hint=hint),
                    "duration": time.time() - start,
                    "mode": "demo",
                    "error": hint,
                }
            )

    return jsonify({"error": "Invalid mode; use demo or live"}), 400


@app.route("/api/fleet_overview")
def fleet_overview():
    rows = _fleet_rows(limit=30)
    pending = len([r for r in mcp_srv._read_jsonl(mcp_srv.APPROVALS_FILE) if (r.get("status") or "") == "pending"])
    open_work_orders = len(mcp_srv._read_jsonl(mcp_srv.WORK_ORDERS_FILE))
    high_risk = len([r for r in rows if r["severity_label"] == "high"])
    return jsonify(
        {
            "vehicles_in_view": len(rows),
            "high_risk_vehicles": high_risk,
            "open_work_orders": open_work_orders,
            "pending_approvals": pending,
        }
    )


@app.route("/api/vehicles")
def vehicles():
    return jsonify({"rows": _fleet_rows(limit=50)})


@app.route("/api/map_points")
def map_points():
    return jsonify({"rows": _fleet_map_points(limit=50)})


@app.route("/api/approvals")
def approvals():
    rows = mcp_srv._read_jsonl(mcp_srv.APPROVALS_FILE)[-100:]
    rows.reverse()
    return jsonify({"rows": rows[:50]})


@app.route("/api/audit")
def audit():
    line_rows: list[dict] = []
    if mcp_srv.AUDIT_LOG.exists():
        for line in mcp_srv.AUDIT_LOG.read_text(encoding="utf-8", errors="ignore").splitlines()[-200:]:
            line_rows.append({"line": line})
    return jsonify({"rows": line_rows[-100:]})


if __name__ == "__main__":
    mcp_url = os.environ.get("MCP_SERVER_URL", "http://127.0.0.1:8000")
    print("=" * 64)
    print("secure-agentic-mcp | User UI (Flask)")
    print(f"  MCP_SERVER_URL (for Live mode): {mcp_url}")
    print(f"  LLM_PROVIDER: {llm_provider()}  model: {resolved_llm_model()}")
    print("=" * 64)
    app.run(
        host=os.environ.get("FLASK_HOST", "0.0.0.0"),
        port=int(os.environ.get("FLASK_PORT", "5000")),
        debug=os.environ.get("FLASK_DEBUG", "0") == "1",
    )

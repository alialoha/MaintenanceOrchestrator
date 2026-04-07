"""
Unified MCP server: workspace file tools + security-tier tools, HTTP transport.
Resources and prompts for operator visibility; audit log under data/.
"""
from __future__ import annotations

import csv
import json
import os
from datetime import datetime, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any

import warnings

from fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import HTMLResponse

warnings.filterwarnings("ignore", category=DeprecationWarning)

_DATA = Path(os.environ.get("MCP_DATA_DIR", Path(__file__).resolve().parents[2] / "data")).resolve()
WORKSPACE = _DATA / "workspace"
WORKSPACE.mkdir(parents=True, exist_ok=True)
PERMISSIONS_FILE = _DATA / "permissions.json"
AUDIT_LOG = _DATA / "audit.log"
RAW_DIR = _DATA / "raw"
REFERENCE_DIR = _DATA / "reference"
NORMALIZED_DIR = _DATA / "normalized"
OPERATIONS_DIR = _DATA / "operations"
OPERATIONS_DIR.mkdir(parents=True, exist_ok=True)
WORK_ORDERS_FILE = OPERATIONS_DIR / "work_orders.jsonl"
APPROVALS_FILE = OPERATIONS_DIR / "approvals.jsonl"
DECISIONS_FILE = OPERATIONS_DIR / "decisions.jsonl"

mcp = FastMCP("Secure MCP — workspace + governance")


def _audit(line: str) -> None:
    with open(AUDIT_LOG, "a", encoding="utf-8") as f:
        f.write(line)


def _within_workspace(path: Path) -> bool:
    try:
        path.resolve().relative_to(WORKSPACE.resolve())
        return True
    except ValueError:
        return False


def _response(
    result: Any,
    *,
    confidence: float = 1.0,
    assumptions: list[str] | None = None,
    next_actions: list[str] | None = None,
    requires_approval: bool = False,
    approval_reason: str | None = None,
) -> dict[str, Any]:
    return {
        "ok": True,
        "result": result,
        "confidence": max(0.0, min(1.0, float(confidence))),
        "assumptions": assumptions or [],
        "next_actions": next_actions or [],
        "requires_approval": requires_approval,
        "approval_reason": approval_reason,
    }


def _parse_date(value: str | None) -> datetime | None:
    s = (value or "").strip()
    if not s:
        return None
    for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def _now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def _append_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=True) + "\n")


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    out: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            s = line.strip()
            if not s:
                continue
            try:
                out.append(json.loads(s))
            except json.JSONDecodeError:
                continue
    return out


@lru_cache(maxsize=1)
def _load_j1939_catalog() -> dict[str, Any]:
    path = REFERENCE_DIR / "j1939_top_faults.json"
    if not path.exists():
        return {"spn_catalog": [], "fmi_catalog": []}
    return json.loads(path.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _load_vehicles() -> dict[str, dict[str, Any]]:
    path = NORMALIZED_DIR / "vehicles.csv"
    out: dict[str, dict[str, Any]] = {}
    if not path.exists():
        return out
    with path.open("r", encoding="utf-8", newline="", errors="ignore") as f:
        for row in csv.DictReader(f):
            vid = (row.get("vehicle_id") or "").strip()
            if vid:
                out[vid] = row
    return out


@lru_cache(maxsize=1)
def _load_maintenance_events() -> dict[str, list[dict[str, Any]]]:
    path = NORMALIZED_DIR / "maintenance_events.csv"
    out: dict[str, list[dict[str, Any]]] = {}
    if not path.exists():
        return out
    with path.open("r", encoding="utf-8", newline="", errors="ignore") as f:
        for row in csv.DictReader(f):
            vid = (row.get("vehicle_id") or "").strip()
            if not vid:
                continue
            out.setdefault(vid, []).append(row)
    for vid in out:
        out[vid].sort(
            key=lambda r: (
                _parse_date(r.get("event_date")) or datetime.min,
                int((r.get("event_id") or "ME-0").split("-")[-1] or 0),
            ),
            reverse=True,
        )
    return out


@lru_cache(maxsize=1)
def _load_risk_rows() -> list[dict[str, Any]]:
    path = NORMALIZED_DIR / "risk_observations.csv"
    out: list[dict[str, Any]] = []
    if not path.exists():
        return out
    with path.open("r", encoding="utf-8", newline="", errors="ignore") as f:
        for row in csv.DictReader(f):
            out.append(row)
    return out


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _pick_spn_fmi(vehicle_id: str, event_id: str, maintenance_required: int, anomalies: int) -> tuple[int, int]:
    catalog = _load_j1939_catalog()
    spns: list[dict[str, Any]] = catalog.get("spn_catalog", [])
    fmis: list[dict[str, Any]] = catalog.get("fmi_catalog", [])
    if not spns:
        return 102, 3
    try:
        base = int(vehicle_id) + int((event_id or "ME-0").split("-")[-1] or 0)
    except ValueError:
        base = sum(ord(c) for c in (vehicle_id + event_id))
    spn = int(spns[base % len(spns)].get("spn", 102))
    if maintenance_required or anomalies:
        return spn, 3
    if not fmis:
        return spn, 1
    fmi = int(fmis[base % len(fmis)].get("fmi", 1))
    return spn, fmi


@mcp.tool()
def read_file(filepath: str) -> str:
    """Read a file from the workspace. (Risk: LOW)"""
    path = WORKSPACE / filepath
    if not _within_workspace(path):
        return "Error: Access denied — path outside workspace"
    if not path.is_file():
        return f"Error: File not found: {filepath}"
    return path.read_text(encoding="utf-8")


@mcp.tool()
def write_file(filepath: str, content: str) -> str:
    """Write a file under the workspace. (Risk: MEDIUM)"""
    path = WORKSPACE / filepath
    if not _within_workspace(path):
        return "Error: Access denied — path outside workspace"
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        _audit(f"[{datetime.now().isoformat()}] WRITE: {filepath}\n")
        return f"Successfully wrote {len(content)} characters to {filepath}"
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def list_files(directory: str = ".") -> str:
    """List files in a workspace directory. (Risk: LOW)"""
    path = WORKSPACE / directory
    if not _within_workspace(path):
        return "Error: Access denied — path outside workspace"
    if not path.exists():
        return f"Error: Directory not found: {directory}"
    if not path.is_dir():
        return f"Error: Not a directory: {directory}"
    lines = []
    for item in sorted(path.iterdir()):
        rel = item.relative_to(WORKSPACE)
        kind = "DIR" if item.is_dir() else "FILE"
        size = item.stat().st_size if item.is_file() else 0
        lines.append(f"{kind}: {rel} ({size} bytes)")
    return "\n".join(lines) if lines else "Directory is empty"


@mcp.tool()
def delete_file(filepath: str) -> str:
    """Delete a file in the workspace. (Risk: HIGH)"""
    path = WORKSPACE / filepath
    if not _within_workspace(path):
        return "Error: Access denied — path outside workspace"
    if not path.is_file():
        return f"Error: Not a file or missing: {filepath}"
    try:
        path.unlink()
        _audit(f"[{datetime.now().isoformat()}] DELETE: {filepath}\n")
        return f"Successfully deleted {filepath}"
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def execute_command(command: str) -> str:
    """Simulated shell command — no real execution. (Risk: CRITICAL)"""
    _audit(f"[{datetime.now().isoformat()}] EXECUTE (simulated): {command}\n")
    return (
        f"Simulated execution of: {command}\n"
        "(Real execution disabled; configure policy in data/permissions.json.)"
    )


@mcp.tool()
def analyze_code(code: str, focus: str = "quality") -> str:
    """Preview-only code review stub; the operator host normally runs the model with tool results."""
    return (
        f"Preview for focus “{focus}” ({len(code)} characters of code).\n\n"
        "In deployments that use MCP client-side sampling, the LLM would run in the host "
        "and return a full review; this endpoint only echoes a short summary."
    )


@mcp.tool()
def fetch_vehicle_faults(vehicle_id: str, lookback_hours: int = 24) -> dict[str, Any]:
    """Fetch synthesized vehicle SPN/FMI faults from recent maintenance signals. (Risk: LOW)"""
    events = _load_maintenance_events().get(vehicle_id, [])
    if not events:
        return _response(
            {"vehicle_id": vehicle_id, "faults": []},
            confidence=0.3,
            assumptions=["No maintenance history found for vehicle_id."],
        )
    cutoff = datetime.utcnow() - timedelta(hours=max(1, min(168, lookback_hours)))
    faults: list[dict[str, Any]] = []
    for ev in events[:200]:
        dt = _parse_date(ev.get("event_date"))
        if dt and dt < cutoff:
            continue
        mr = int(_to_float(ev.get("maintenance_required")))
        an = int(_to_float(ev.get("anomalies_detected")))
        fh = int(_to_float(ev.get("failure_history")))
        if mr == 0 and an == 0 and fh == 0:
            continue
        spn, fmi = _pick_spn_fmi(vehicle_id, ev.get("event_id", ""), mr, an)
        faults.append(
            {
                "event_time": (ev.get("event_date") or "").strip(),
                "spn": spn,
                "fmi": fmi,
                "occurrence_count": max(1, fh + mr + an),
                "source_address": "engine_ecu",
                "from_event_id": ev.get("event_id"),
            }
        )
        if len(faults) >= 25:
            break
    return _response(
        {"vehicle_id": vehicle_id, "faults": faults},
        confidence=0.7 if faults else 0.4,
        assumptions=["SPN/FMI are inferred from normalized maintenance signals for demo realism."],
        next_actions=["Run lookup_fault_resolution(spn, fmi) for top faults."],
    )


@mcp.tool()
def lookup_fault_resolution(spn: int, fmi: int) -> dict[str, Any]:
    """Lookup fault meaning, severity, and default actions by SPN/FMI. (Risk: LOW)"""
    catalog = _load_j1939_catalog()
    spn_row = next((x for x in catalog.get("spn_catalog", []) if int(x.get("spn", -1)) == int(spn)), None)
    fmi_row = next((x for x in catalog.get("fmi_catalog", []) if int(x.get("fmi", -1)) == int(fmi)), None)
    if not spn_row:
        return _response(
            {
                "spn": spn,
                "fmi": fmi,
                "fault_name": "Unknown SPN",
                "fmi_meaning": fmi_row.get("meaning") if fmi_row else "Unknown FMI",
                "default_severity": (fmi_row or {}).get("default_severity", "medium"),
                "recommended_actions": ["Escalate to diagnostic technician for manual triage."],
                "required_parts": [],
                "estimated_labor_hours": 1.0,
            },
            confidence=0.5,
            assumptions=["SPN not found in local demo catalog."],
        )
    return _response(
        {
            "spn": int(spn_row.get("spn", spn)),
            "fmi": int(fmi),
            "fault_name": spn_row.get("name", "Unknown"),
            "fmi_meaning": (fmi_row or {}).get("meaning", "Unknown FMI"),
            "default_severity": (fmi_row or {}).get("default_severity", "medium"),
            "recommended_actions": spn_row.get("common_actions", []),
            "required_parts": [str(spn_row.get("name", "generic_part")).lower().replace(" ", "_")],
            "estimated_labor_hours": 1.5,
        },
        confidence=1.0,
    )


@mcp.tool()
def score_fault_severity(vehicle_id: str, spn: int, fmi: int, context: dict | None = None) -> dict[str, Any]:
    """Score fault severity using fault mapping + vehicle maintenance trends. (Risk: MEDIUM)"""
    context = context or {}
    base = lookup_fault_resolution(spn, fmi)["result"]
    events = _load_maintenance_events().get(vehicle_id, [])[:50]
    if events:
        avg_predictive = sum(_to_float(e.get("predictive_score")) for e in events) / len(events)
        req_ratio = sum(int(_to_float(e.get("maintenance_required"))) for e in events) / len(events)
        fail_ratio = sum(int(_to_float(e.get("failure_history"))) for e in events) / len(events)
    else:
        avg_predictive = 0.0
        req_ratio = 0.0
        fail_ratio = 0.0
    sev_weight = {"low": 0.35, "medium": 0.55, "high": 0.75}.get(base.get("default_severity", "medium"), 0.55)
    context_boost = _to_float(context.get("operational_criticality"), 0.0) * 0.15
    score = min(1.0, sev_weight + avg_predictive * 0.5 + req_ratio * 0.2 + fail_ratio * 0.2 + context_boost)
    label = "high" if score >= 0.75 else "medium" if score >= 0.45 else "low"
    drivers = [
        f"default severity={base.get('default_severity', 'medium')}",
        f"avg_predictive={avg_predictive:.2f}",
        f"maintenance_required_ratio={req_ratio:.2f}",
        f"failure_history_ratio={fail_ratio:.2f}",
    ]
    return _response(
        {
            "vehicle_id": vehicle_id,
            "spn": int(spn),
            "fmi": int(fmi),
            "severity_score": round(score, 4),
            "severity_label": label,
            "drivers": drivers,
        },
        confidence=0.78,
        assumptions=["Scoring uses normalized maintenance signals and simple weighted heuristics."],
        next_actions=["If high severity, create_work_order and request_approval."],
    )


@mcp.tool()
def get_maintenance_history(vehicle_id: str, limit: int = 20) -> dict[str, Any]:
    """Get recent maintenance events for a vehicle. (Risk: LOW)"""
    rows = _load_maintenance_events().get(vehicle_id, [])
    out = rows[: max(1, min(200, limit))]
    return _response(
        {"vehicle_id": vehicle_id, "events": out, "count": len(out)},
        confidence=1.0 if out else 0.5,
    )


@mcp.tool()
def predict_maintenance_need(vehicle_id: str) -> dict[str, Any]:
    """Predict near-term maintenance need probability from recent event trends. (Risk: MEDIUM)"""
    rows = _load_maintenance_events().get(vehicle_id, [])[:60]
    if not rows:
        return _response(
            {
                "vehicle_id": vehicle_id,
                "maintenance_need_probability": 0.2,
                "recommended_window_hours": 72,
                "top_features": ["no_recent_history"],
            },
            confidence=0.35,
            assumptions=["Fallback probability because no history exists for vehicle."],
        )
    avg_predictive = sum(_to_float(r.get("predictive_score")) for r in rows) / len(rows)
    req_ratio = sum(int(_to_float(r.get("maintenance_required"))) for r in rows) / len(rows)
    fail_ratio = sum(int(_to_float(r.get("failure_history"))) for r in rows) / len(rows)
    probability = min(1.0, avg_predictive * 0.6 + req_ratio * 0.3 + fail_ratio * 0.1)
    window = 8 if probability >= 0.85 else 24 if probability >= 0.65 else 72
    return _response(
        {
            "vehicle_id": vehicle_id,
            "maintenance_need_probability": round(probability, 4),
            "recommended_window_hours": window,
            "top_features": [
                f"avg_predictive_score={avg_predictive:.2f}",
                f"maintenance_required_ratio={req_ratio:.2f}",
                f"failure_history_ratio={fail_ratio:.2f}",
            ],
        },
        confidence=0.82,
    )


@mcp.tool()
def create_work_order(vehicle_id: str, issue_summary: str, priority: str) -> dict[str, Any]:
    """Create a maintenance work order for a vehicle. (Risk: HIGH)"""
    p = (priority or "").strip().lower()
    if p not in ("low", "medium", "high", "critical"):
        return {
            "ok": False,
            "error": "priority must be one of: low, medium, high, critical",
        }
    if vehicle_id not in _load_vehicles():
        return {"ok": False, "error": f"Unknown vehicle_id: {vehicle_id}"}
    work_order_id = f"WO-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}-{vehicle_id}"
    rec = {
        "work_order_id": work_order_id,
        "vehicle_id": vehicle_id,
        "issue_summary": issue_summary.strip(),
        "priority": p,
        "status": "created",
        "created_at": _now_iso(),
    }
    _append_jsonl(WORK_ORDERS_FILE, rec)
    _audit(f"[{datetime.now().isoformat()}] WORK_ORDER_CREATE: {work_order_id} vehicle={vehicle_id} priority={p}\n")
    needs_approval = p in ("high", "critical")
    return _response(
        rec,
        confidence=1.0,
        requires_approval=needs_approval,
        approval_reason="High/critical work order priority requires operator approval."
        if needs_approval
        else None,
        next_actions=["propose_service_appointment", "check_parts_inventory"],
    )


@mcp.tool()
def request_approval(action_type: str, payload: dict, reason: str, estimated_cost: float = 0.0) -> dict[str, Any]:
    """Create a pending approval request for a high-impact action. (Risk: HIGH)"""
    approval_id = f"APR-{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}"
    rec = {
        "approval_id": approval_id,
        "action_type": action_type,
        "payload": payload or {},
        "reason": reason.strip(),
        "estimated_cost": round(float(estimated_cost or 0.0), 2),
        "status": "pending",
        "created_at": _now_iso(),
    }
    _append_jsonl(APPROVALS_FILE, rec)
    _audit(f"[{datetime.now().isoformat()}] APPROVAL_REQUEST: {approval_id} action={action_type}\n")
    return _response(
        rec,
        confidence=1.0,
        requires_approval=True,
        approval_reason="Approval request is pending operator decision.",
    )


@mcp.tool()
def record_decision_log(
    actor: str,
    action: str,
    outcome: str,
    rationale: str,
    entity_type: str,
    entity_id: str,
) -> dict[str, Any]:
    """Record a governance decision entry. (Risk: MEDIUM)"""
    rec = {
        "decision_id": f"DEC-{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}",
        "actor": actor.strip(),
        "action": action.strip(),
        "outcome": outcome.strip(),
        "rationale": rationale.strip(),
        "entity_type": entity_type.strip(),
        "entity_id": entity_id.strip(),
        "created_at": _now_iso(),
    }
    _append_jsonl(DECISIONS_FILE, rec)
    _audit(
        f"[{datetime.now().isoformat()}] DECISION: {rec['decision_id']} entity={entity_type}:{entity_id} outcome={outcome}\n"
    )
    return _response(rec, confidence=1.0)


@mcp.tool()
def get_audit_trail(entity_type: str, entity_id: str, limit: int = 100) -> dict[str, Any]:
    """Get consolidated audit trail entries by entity. (Risk: LOW)"""
    lim = max(1, min(500, int(limit)))
    key = f"{entity_type}:{entity_id}"
    entries: list[dict[str, Any]] = []

    for rec in _read_jsonl(DECISIONS_FILE):
        if rec.get("entity_type") == entity_type and rec.get("entity_id") == entity_id:
            entries.append({"source": "decisions", **rec})
    for rec in _read_jsonl(WORK_ORDERS_FILE):
        if entity_type == "work_order" and rec.get("work_order_id") == entity_id:
            entries.append({"source": "work_orders", **rec})
        if entity_type == "vehicle" and rec.get("vehicle_id") == entity_id:
            entries.append({"source": "work_orders", **rec})
    for rec in _read_jsonl(APPROVALS_FILE):
        payload = rec.get("payload") or {}
        if payload.get("entity_type") == entity_type and payload.get("entity_id") == entity_id:
            entries.append({"source": "approvals", **rec})

    if AUDIT_LOG.exists():
        for line in AUDIT_LOG.read_text(encoding="utf-8", errors="ignore").splitlines():
            if entity_id in line or key in line:
                entries.append({"source": "audit.log", "line": line})
    entries = entries[-lim:]
    return _response(
        {"entity_type": entity_type, "entity_id": entity_id, "entries": entries, "count": len(entries)},
        confidence=1.0,
    )


@mcp.resource("file://workspace/{filename}")
def resource_workspace_file(filename: str) -> str:
    path = WORKSPACE / filename
    if not _within_workspace(path) or not path.is_file():
        raise ValueError("Invalid or missing file")
    return path.read_text(encoding="utf-8")


@mcp.resource("file://audit/log")
def resource_audit_log() -> str:
    if not AUDIT_LOG.exists():
        return "No audit entries yet."
    return AUDIT_LOG.read_text(encoding="utf-8")


@mcp.resource("file://config/permissions")
def resource_permissions() -> str:
    if not PERMISSIONS_FILE.exists():
        return json.dumps(
            {
                "read_file": "allow",
                "write_file": "ask",
                "list_files": "allow",
                "delete_file": "deny",
                "execute_command": "deny",
                "analyze_code": "ask",
            },
            indent=2,
        )
    return PERMISSIONS_FILE.read_text(encoding="utf-8")


@mcp.resource("file://data/j1939_fault_catalog")
def resource_j1939_fault_catalog() -> str:
    return json.dumps(_load_j1939_catalog(), indent=2)


@mcp.resource("file://data/vehicle/{vehicle_id}")
def resource_vehicle_profile(vehicle_id: str) -> str:
    rec = _load_vehicles().get(vehicle_id)
    if not rec:
        raise ValueError(f"Unknown vehicle_id: {vehicle_id}")
    return json.dumps(rec, indent=2)


@mcp.resource("file://data/maintenance/{vehicle_id}")
def resource_vehicle_maintenance_recent(vehicle_id: str) -> str:
    rows = _load_maintenance_events().get(vehicle_id, [])[:20]
    return json.dumps({"vehicle_id": vehicle_id, "events": rows}, indent=2)


@mcp.prompt()
def review_code(filename: str) -> str:
    return f"""Review the code in workspace file '{filename}' for clarity, bugs, and security."""


@mcp.prompt()
def analyze_security(filename: str) -> str:
    return f"""Security review of '{filename}': validation, auth, injection, and logging."""


@mcp.prompt()
def security_review(operation: str, risk_level: str) -> list[dict]:
    return [
        {
            "role": "user",
            "content": f"""Review this operation:
Operation: {operation}
Risk: {risk_level}
Cover impact, safeguards, approval, and audit logging.""",
        }
    ]


@mcp.prompt()
def prompt_incident_triage(vehicle_id: str, spn: int, fmi: int) -> str:
    return (
        "Triage this maintenance incident.\n"
        f"- vehicle_id: {vehicle_id}\n"
        f"- spn/fmi: {spn}/{fmi}\n"
        "Steps: fetch_vehicle_faults -> lookup_fault_resolution -> score_fault_severity -> "
        "predict_maintenance_need -> decide if create_work_order is required. "
        "Highlight if approval is needed."
    )


@mcp.prompt()
def prompt_work_order_review(work_order_id: str) -> str:
    return (
        f"Review work order {work_order_id}.\n"
        "Summarize priority, expected impact, approval requirement, and next actions for operator."
    )


@mcp.prompt()
def prompt_customer_update(delivery_id: str, issue_summary: str = "") -> str:
    return (
        f"Draft a customer-safe status update for delivery {delivery_id}.\n"
        f"Issue summary: {issue_summary or 'maintenance delay risk under review'}.\n"
        "Tone: professional, concise, no internal-only technical details."
    )


_MCP_HTTP_PATH = "/mcp"


@mcp.custom_route("/", methods=["GET"])
async def _http_root(_request: Request) -> HTMLResponse:
    """Human-friendly page; MCP JSON-RPC is on /mcp (browsers should not use 0.0.0.0)."""
    port = int(os.environ.get("MCP_HTTP_PORT", "8000"))
    mcp_url = f"http://127.0.0.1:{port}{_MCP_HTTP_PATH}"
    body = f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><title>secure-agentic-mcp</title></head>
<body>
  <h1>MCP HTTP server is running</h1>
  <p>This process is an MCP endpoint, not a full web app. Connection is healthy.</p>
  <p>MCP URL (for clients): <a href="{mcp_url}">{mcp_url}</a></p>
  <p><strong>Do not use</strong> <code>http://0.0.0.0</code> in a browser — use <code>127.0.0.1</code> or <code>localhost</code> instead.</p>
</body>
</html>"""
    return HTMLResponse(body)


def main() -> None:
    host = os.environ.get("MCP_HTTP_HOST", "0.0.0.0")
    port = int(os.environ.get("MCP_HTTP_PORT", "8000"))
    display_host = "127.0.0.1" if host in ("0.0.0.0", "::", "[::]") else host
    data_abs = _DATA.resolve()
    workspace_abs = WORKSPACE.resolve()
    sep = "=" * 64
    print(sep)
    print("server is running. you can now run the client")
    # print("secure-agentic-mcp | MCP HTTP server (this repository)")
    # print(f"  Listen (bind): {host}:{port}")
    # print(f"  MCP URL (browsers & clients): http://{display_host}:{port}{_MCP_HTTP_PATH}")
    # if host in ("0.0.0.0", "::", "[::]"):
    #     print("  Note: http://0.0.0.0/... is not valid in browsers — use the line above.")
    # print(f"  Status page: http://{display_host}:{port}/  (GET / confirms the server is up)")
    # print(f"  MCP_DATA_DIR: {data_abs}")
    # print(f"  Workspace:    {workspace_abs}")
    # print("  Tools read/write files under Workspace above — not other projects.")
    print(sep)
    mcp.run(
        transport="http",
        host=host,
        port=port,
        path=_MCP_HTTP_PATH,
        show_banner=False,
        log_level="warning",
        uvicorn_config={"log_level": "warning"},
    )


if __name__ == "__main__":
    main()

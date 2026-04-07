"""Default JSON examples for Tools / Prompts tabs (no Gradio import — safe for unit tests)."""
from __future__ import annotations

import json
from typing import Any


def tool_name_from_dropdown(selection: str) -> str:
    """Strip ` (allow)`-style suffix from the Tools dropdown value."""
    if not selection:
        return ""
    return selection.split(" (", 1)[0].strip()

# When prompts/list has not been run yet, or the server omits `required` flags.
REQUIRED_PROMPT_ARG_KEYS: dict[str, list[str]] = {
    "review_code": ["filename"],
    "analyze_security": ["filename"],
    "security_review": ["operation", "risk_level"],
    "prompt_incident_triage": ["vehicle_id", "spn", "fmi"],
    "prompt_work_order_review": ["work_order_id"],
    "prompt_customer_update": ["delivery_id"],
}


def sample_json_for_tool(tool_name: str) -> str:
    """Editable example arguments for the Tools tab (paths are under the server workspace)."""
    samples: dict[str, dict] = {
        "read_file": {"filepath": "README.md"},
        "write_file": {"filepath": "notes.txt", "content": "Hello"},
        "list_files": {"directory": "."},
        "delete_file": {"filepath": "old.txt"},
        "execute_command": {"command": "echo ok"},
        "analyze_code": {
            "code": "def add(a, b):\n    return a + b",
            "focus": "readability",
        },
        "fetch_vehicle_faults": {"vehicle_id": "64940", "lookback_hours": 24},
        "lookup_fault_resolution": {"spn": 102, "fmi": 3},
        "score_fault_severity": {
            "vehicle_id": "64940",
            "spn": 102,
            "fmi": 3,
            "context": {"operational_criticality": 0.9},
        },
        "get_maintenance_history": {"vehicle_id": "64940", "limit": 20},
        "predict_maintenance_need": {"vehicle_id": "64940"},
        "create_work_order": {
            "vehicle_id": "64940",
            "issue_summary": "Boost pressure voltage above normal with recurrence.",
            "priority": "high",
        },
        "request_approval": {
            "action_type": "create_work_order",
            "payload": {"entity_type": "vehicle", "entity_id": "64940"},
            "reason": "High-priority maintenance may impact active deliveries.",
            "estimated_cost": 850.0,
        },
        "record_decision_log": {
            "actor": "operator",
            "action": "approve_work_order",
            "outcome": "approved",
            "rationale": "Risk score high and fault recurring",
            "entity_type": "vehicle",
            "entity_id": "64940",
        },
        "get_audit_trail": {"entity_type": "vehicle", "entity_id": "64940", "limit": 50},
    }
    if tool_name not in samples:
        return "{}"
    return json.dumps(samples[tool_name], indent=2)


def sample_json_for_prompt(prompt_name: str) -> str:
    """Editable example arguments for the Prompts tab (matches server prompt parameters)."""
    samples: dict[str, dict] = {
        "review_code": {"filename": "README.md"},
        "analyze_security": {"filename": "README.md"},
        "security_review": {
            "operation": "deploy to production",
            "risk_level": "high",
        },
        "prompt_incident_triage": {"vehicle_id": "64940", "spn": 102, "fmi": 3},
        "prompt_work_order_review": {"work_order_id": "WO-20260407010101-64940"},
        "prompt_customer_update": {
            "delivery_id": "DEL-1001",
            "issue_summary": "Vehicle maintenance event under active mitigation.",
        },
    }
    if prompt_name not in samples:
        return "{}"
    return json.dumps(samples[prompt_name], indent=2)


def format_prompt_list_line(p: Any) -> str:
    """One prompt as a bullet; no trailing ': ' when the server sends an empty description."""
    name = getattr(p, "name", "?")
    desc = (getattr(p, "description", None) or "").strip()
    if desc:
        return f"- {name}\n  {desc}"
    return f"- {name}"

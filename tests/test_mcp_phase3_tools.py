"""Phase 3: communication tools + materialized synthetic overlays."""

from __future__ import annotations

import json
from pathlib import Path

import mcp_server.server as srv
from scripts.materialize_phase3_data import materialize


def _vehicle() -> str:
    return "64940"


def _new_work_order(monkeypatch, tmp_path: Path) -> str:
    monkeypatch.setattr(srv, "WORK_ORDERS_FILE", tmp_path / "work_orders.jsonl")
    monkeypatch.setattr(srv, "AUDIT_LOG", tmp_path / "audit.log")
    created = srv.create_work_order(_vehicle(), "Brake + sensor check", "high")
    assert created.get("ok") is True
    return created["result"]["work_order_id"]


def test_generate_operator_summary(monkeypatch, tmp_path):
    wo_id = _new_work_order(monkeypatch, tmp_path)
    out = srv.generate_operator_summary(wo_id)
    assert out["ok"] is True
    assert wo_id in out["result"]["summary_text"]
    assert out["requires_approval"] is True


def test_generate_customer_update():
    risks = srv.list_deliveries_at_risk(_vehicle(), horizon_hours=168)
    assert risks["ok"] is True
    assert risks["result"]["count"] >= 1
    delivery_id = risks["result"]["deliveries"][0]["delivery_id"]
    out = srv.generate_customer_update(delivery_id, tone="empathetic")
    assert out["ok"] is True
    assert out["result"]["delivery_id"] == delivery_id
    assert out["result"]["tone"] == "empathetic"
    assert isinstance(out["result"]["customer_message"], str)


def test_generate_customer_update_bad_tone():
    out = srv.generate_customer_update("RS-1", tone="casual")
    assert out.get("ok") is False


def test_materialize_phase3_data(tmp_path):
    data_dir = tmp_path / "data"
    normalized = data_dir / "normalized"
    normalized.mkdir(parents=True, exist_ok=True)
    (data_dir / "synthetic").mkdir(parents=True, exist_ok=True)
    (normalized / "maintenance_events.csv").write_text(
        "event_id,vehicle_id,event_date,maintenance_type\n"
        "ME-1,1,2024-01-01,Oil Change\n"
        "ME-2,2,2024-01-02,Brake Inspection\n",
        encoding="utf-8",
    )
    (normalized / "vehicles.csv").write_text(
        "vehicle_id,vehicle_type\n1,Truck\n2,Van\n3,Truck\n",
        encoding="utf-8",
    )

    summary = materialize(data_dir)
    assert summary["parts_rows"] >= 2
    assert summary["slots"] >= 8
    parts = json.loads((data_dir / "synthetic" / "parts_inventory.json").read_text(encoding="utf-8"))
    shops = json.loads((data_dir / "synthetic" / "shop_and_slots.json").read_text(encoding="utf-8"))
    assert "LOC-MAIN" in parts
    assert "slots" in shops

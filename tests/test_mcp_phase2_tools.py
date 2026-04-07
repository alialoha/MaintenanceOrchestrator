"""Phase 2: shop/parts, scheduling, logistics impact (synthetic data + operations ledger)."""

from __future__ import annotations

import json

import pytest

import mcp_server.server as srv


def _sample_vehicle_id() -> str:
    return "64940"


@pytest.fixture(autouse=True)
def clear_data_caches():
    srv._load_j1939_catalog.cache_clear()
    srv._load_vehicles.cache_clear()
    srv._load_maintenance_events.cache_clear()
    srv._load_risk_rows.cache_clear()
    srv._load_parts_inventory_by_location.cache_clear()
    srv._load_shop_slots_document.cache_clear()
    yield
    srv._load_j1939_catalog.cache_clear()
    srv._load_vehicles.cache_clear()
    srv._load_maintenance_events.cache_clear()
    srv._load_risk_rows.cache_clear()
    srv._load_parts_inventory_by_location.cache_clear()
    srv._load_shop_slots_document.cache_clear()


def test_estimate_repair_duration_unknown():
    out = srv.estimate_repair_duration("WO-DOES-NOT-EXIST")
    assert out.get("ok") is False


def test_estimate_repair_duration_known(monkeypatch, tmp_path):
    wo = tmp_path / "work_orders.jsonl"
    monkeypatch.setattr(srv, "WORK_ORDERS_FILE", wo)
    monkeypatch.setattr(srv, "AUDIT_LOG", tmp_path / "audit.log")
    created = srv.create_work_order(_sample_vehicle_id(), "Turbo boost sensor fault", "high")
    assert created.get("ok") is True
    wid = created["result"]["work_order_id"]
    out = srv.estimate_repair_duration(wid)
    assert out.get("ok") is True
    assert out["result"]["estimated_labor_hours"] >= 8.0


def test_check_parts_inventory():
    out = srv.check_parts_inventory("LOC-MAIN", ["FLT-OIL-01", "UNKNOWN-PN"])
    assert out["ok"] is True
    parts = out["result"]["parts"]
    assert parts[0]["qty_on_hand"] == 12
    assert parts[1].get("not_stocked") is True


def test_propose_service_appointment():
    out = srv.propose_service_appointment("LOC-MAIN", 4.0, "high")
    assert out["ok"] is True
    assert out["result"]["count"] >= 1


def test_reserve_service_slot_roundtrip(monkeypatch, tmp_path):
    rs_f = tmp_path / "slot_reservations.jsonl"
    monkeypatch.setattr(srv, "WORK_ORDERS_FILE", tmp_path / "work_orders.jsonl")
    monkeypatch.setattr(srv, "SLOT_RESERVATIONS_FILE", rs_f)
    monkeypatch.setattr(srv, "AUDIT_LOG", tmp_path / "audit.log")
    c = srv.create_work_order(_sample_vehicle_id(), "Brake inspection required", "low")
    wid = c["result"]["work_order_id"]
    before = srv.propose_service_appointment("LOC-NORTH", 3.0, "medium")
    slot_id = before["result"]["candidates"][0]["slot_id"]
    r = srv.reserve_service_slot(wid, slot_id)
    assert r["ok"] is True
    after = srv.propose_service_appointment("LOC-NORTH", 3.0, "medium")
    taken = {slot_id}
    ids_after = {c["slot_id"] for c in after["result"]["candidates"]}
    assert slot_id not in ids_after


def test_list_deliveries_at_risk():
    out = srv.list_deliveries_at_risk("64940", horizon_hours=168)
    assert out["ok"] is True
    assert out["result"]["count"] >= 1
    ids = {d["delivery_id"] for d in out["result"]["deliveries"]}
    assert any(i.startswith("RS-") for i in ids)


def test_estimate_delay_impact():
    out = srv.estimate_delay_impact("64940", "repair_now")
    assert out["ok"] is True
    r = out["result"]
    assert r["scenario"] == "repair_now"
    assert "estimated_delay_hours" in r
    assert "sla_breach_probability" in r
    assert "estimated_cost_impact" in r


def test_estimate_delay_impact_bad_scenario():
    out = srv.estimate_delay_impact("64940", "wait_forever")
    assert out.get("ok") is False


def test_phase2_resources():
    parts = json.loads(srv.resource_parts_inventory_snapshot())
    assert "LOC-MAIN" in parts
    shop = json.loads(srv.resource_shop_capacity_snapshot())
    assert "slots" in shop
    d = json.loads(srv.resource_deliveries_demo())
    assert isinstance(d, dict)
    assert "deliveries" in d

"""Exercise Phase 1 MCP tools against bundled normalized data (no HTTP server)."""

from __future__ import annotations

import json

import pytest

import mcp_server.server as srv


def _sample_vehicle_id() -> str:
    """A vehicle that appears in both vehicles.csv and maintenance_events.csv in the demo bundle."""
    return "64940"


def _assert_tool_envelope(d: dict, expect_ok: bool = True) -> None:
    assert isinstance(d, dict)
    assert d.get("ok") is expect_ok
    if expect_ok:
        assert "result" in d
        assert "confidence" in d
        assert "assumptions" in d
        assert "requires_approval" in d


@pytest.fixture(autouse=True)
def clear_data_caches():
    srv._load_j1939_catalog.cache_clear()
    srv._load_vehicles.cache_clear()
    srv._load_maintenance_events.cache_clear()
    srv._load_risk_rows.cache_clear()
    yield
    srv._load_j1939_catalog.cache_clear()
    srv._load_vehicles.cache_clear()
    srv._load_maintenance_events.cache_clear()
    srv._load_risk_rows.cache_clear()


def test_phase1_fetch_vehicle_faults():
    vid = _sample_vehicle_id()
    out = srv.fetch_vehicle_faults(vid, lookback_hours=24 * 90)
    _assert_tool_envelope(out)
    body = out["result"]
    assert body["vehicle_id"] == vid
    assert isinstance(body["faults"], list)


def test_phase1_lookup_fault_resolution():
    out = srv.lookup_fault_resolution(102, 3)
    _assert_tool_envelope(out)
    r = out["result"]
    assert r["spn"] == 102
    assert r["fmi"] == 3
    assert "fault_name" in r


def test_phase1_score_fault_severity():
    vid = _sample_vehicle_id()
    out = srv.score_fault_severity(
        vid, 102, 3, context={"operational_criticality": 0.5}
    )
    _assert_tool_envelope(out)
    r = out["result"]
    assert r["vehicle_id"] == vid
    assert 0.0 <= float(r["severity_score"]) <= 1.0
    assert r["severity_label"] in ("low", "medium", "high")


def test_phase1_get_maintenance_history():
    vid = _sample_vehicle_id()
    out = srv.get_maintenance_history(vid, limit=5)
    _assert_tool_envelope(out)
    r = out["result"]
    assert r["count"] <= 5
    assert len(r["events"]) == r["count"]


def test_phase1_predict_maintenance_need():
    vid = _sample_vehicle_id()
    out = srv.predict_maintenance_need(vid)
    _assert_tool_envelope(out)
    r = out["result"]
    assert 0.0 <= float(r["maintenance_need_probability"]) <= 1.0
    assert isinstance(r["recommended_window_hours"], int)


def test_phase1_create_work_order_validation():
    bad = srv.create_work_order(_sample_vehicle_id(), "unit test", priority="urgent")
    assert bad.get("ok") is False


def test_phase1_create_work_order_writes(monkeypatch, tmp_path):
    wo = tmp_path / "work_orders.jsonl"
    audit = tmp_path / "audit.log"
    monkeypatch.setattr(srv, "WORK_ORDERS_FILE", wo)
    monkeypatch.setattr(srv, "AUDIT_LOG", audit)

    out = srv.create_work_order(_sample_vehicle_id(), "Phase 1 integration test", "low")
    _assert_tool_envelope(out)
    assert wo.is_file()
    line = wo.read_text(encoding="utf-8").strip().splitlines()[0]
    rec = json.loads(line)
    assert rec["vehicle_id"] == _sample_vehicle_id()
    assert rec["priority"] == "low"


def test_phase1_request_approval_writes(monkeypatch, tmp_path):
    apr = tmp_path / "approvals.jsonl"
    monkeypatch.setattr(srv, "APPROVALS_FILE", apr)
    monkeypatch.setattr(srv, "AUDIT_LOG", tmp_path / "audit.log")

    out = srv.request_approval(
        "create_work_order",
        {"entity_type": "vehicle", "entity_id": _sample_vehicle_id()},
        "regulatory threshold",
        500.0,
    )
    _assert_tool_envelope(out)
    assert apr.read_text(encoding="utf-8").strip()


def test_phase1_record_decision_log_writes(monkeypatch, tmp_path):
    dec = tmp_path / "decisions.jsonl"
    monkeypatch.setattr(srv, "DECISIONS_FILE", dec)
    monkeypatch.setattr(srv, "AUDIT_LOG", tmp_path / "audit.log")

    out = srv.record_decision_log(
        "operator",
        "approve",
        "approved",
        "ok for test",
        "vehicle",
        _sample_vehicle_id(),
    )
    _assert_tool_envelope(out)
    assert "decision_id" in out["result"]


def test_phase1_get_audit_trail():
    out = srv.get_audit_trail("vehicle", _sample_vehicle_id(), limit=20)
    _assert_tool_envelope(out)
    r = out["result"]
    assert r["entity_type"] == "vehicle"
    assert isinstance(r["entries"], list)
    assert r["count"] == len(r["entries"])


def test_phase1_resources_vehicle_and_j1939():
    cat = json.loads(srv.resource_j1939_fault_catalog())
    assert "spn_catalog" in cat

    prof = json.loads(srv.resource_vehicle_profile(_sample_vehicle_id()))
    assert prof.get("vehicle_id") == _sample_vehicle_id()

    maint = json.loads(srv.resource_vehicle_maintenance_recent(_sample_vehicle_id()))
    assert maint["vehicle_id"] == _sample_vehicle_id()
    assert "events" in maint

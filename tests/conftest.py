from __future__ import annotations

import pytest

import mcp_server.server as srv


@pytest.fixture(autouse=True)
def clear_server_data_caches():
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

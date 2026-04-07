"""
Materialize Phase 3 synthetic overlays from normalized data.

Outputs:
- data/synthetic/parts_inventory.json
- data/synthetic/shop_and_slots.json
"""
from __future__ import annotations

import csv
import json
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path


def _to_float(v: str | None, default: float = 0.0) -> float:
    try:
        return float(v or "")
    except ValueError:
        return default


def _project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="", errors="ignore") as f:
        return list(csv.DictReader(f))


def materialize(data_dir: Path) -> dict[str, int]:
    normalized = data_dir / "normalized"
    synthetic = data_dir / "synthetic"
    synthetic.mkdir(parents=True, exist_ok=True)

    maint_rows = _read_csv_rows(normalized / "maintenance_events.csv")
    vehicles_rows = _read_csv_rows(normalized / "vehicles.csv")

    maint_types = Counter((r.get("maintenance_type") or "Generic Service").strip() for r in maint_rows)
    top_maint = [m for m, _ in maint_types.most_common(8)]

    part_map = {
        "Oil Change": "FLT-OIL-01",
        "Tire Rotation": "TIRE-AG-22",
        "Brake Inspection": "BRK-PAD-F150",
        "Engine Check": "SENS-BOOST-102",
        "Battery Replacement": "BAT-12V-STD",
    }

    parts_main: list[dict[str, object]] = []
    parts_north: list[dict[str, object]] = []
    for i, mt in enumerate(top_maint):
        checksum = sum(ord(ch) for ch in mt) % 10000
        pn = part_map.get(mt, f"PART-{checksum:04d}")
        qty = max(2, 18 - i * 2)
        row = {"part_number": pn, "qty_on_hand": qty, "description": f"{mt} kit"}
        (parts_main if i % 2 == 0 else parts_north).append(row)

    if not parts_main:
        parts_main.append({"part_number": "FLT-OIL-01", "qty_on_hand": 10, "description": "Oil filter"})
    if not parts_north:
        parts_north.append({"part_number": "SENS-BOOST-102", "qty_on_hand": 5, "description": "Boost sensor"})

    parts_payload = {"LOC-MAIN": parts_main, "LOC-NORTH": parts_north}

    vehicle_count = max(1, len(vehicles_rows))
    heavy_ratio = sum(1 for r in vehicles_rows if (r.get("vehicle_type") or "").lower() == "truck") / vehicle_count
    main_capacity = max(4, int(round(6 + heavy_ratio * 4)))
    north_capacity = max(3, int(round(4 + (1.0 - heavy_ratio) * 3)))

    base = datetime.now(UTC).replace(minute=0, second=0, microsecond=0) + timedelta(hours=2)
    slots: list[dict[str, object]] = []
    for day in range(3):
        for idx, loc in enumerate(("LOC-MAIN", "LOC-NORTH"), start=1):
            for block in range(2):
                start = base + timedelta(days=day, hours=block * (4 + idx))
                sid = f"SL-{loc.split('-')[-1]}-{day + 1}-{block + 1}"
                dur = 3.0 + block * 1.5 + (0.5 if loc == "LOC-MAIN" else 0.0)
                slots.append(
                    {
                        "slot_id": sid,
                        "location_id": loc,
                        "start_iso": start.isoformat() + "Z",
                        "duration_hours": round(dur, 1),
                    }
                )

    shops_payload = {
        "locations": {
            "LOC-MAIN": {
                "name": "Main Service Center",
                "daily_capacity_jobs": main_capacity,
                "address_hint": "Metro hub",
            },
            "LOC-NORTH": {
                "name": "Northern Depot",
                "daily_capacity_jobs": north_capacity,
                "address_hint": "I-95 corridor",
            },
        },
        "slots": slots,
    }

    (synthetic / "parts_inventory.json").write_text(json.dumps(parts_payload, indent=2), encoding="utf-8")
    (synthetic / "shop_and_slots.json").write_text(json.dumps(shops_payload, indent=2), encoding="utf-8")

    return {"parts_locations": len(parts_payload), "parts_rows": len(parts_main) + len(parts_north), "slots": len(slots)}


def main() -> None:
    root = _project_root()
    data_dir = root / "data"
    summary = materialize(data_dir)
    print(json.dumps({"ok": True, "materialized": summary}, indent=2))


if __name__ == "__main__":
    main()

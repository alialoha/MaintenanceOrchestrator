"""Create cleaned v2 copies from normalized seed data.

Input:
  data/normalized/

Output:
  data/normalized_v2/

Rules:
- Keep only strictly positive integer `vehicle_id` values.
- Enforce referential integrity: maintenance events must reference a kept vehicle.
- Normalize risk labels to: low|moderate|high.
- Preserve original raw and normalized inputs (read-only workflow).
"""
from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _to_positive_vehicle_id(raw: str | None) -> str | None:
    s = (raw or "").strip()
    if not s:
        return None
    try:
        iv = int(float(s))
    except Exception:
        return None
    if iv <= 0:
        return None
    return str(iv)


def _normalize_risk_label(raw: str | None) -> str:
    s = (raw or "").strip().lower()
    if "high" in s:
        return "high"
    if "moderate" in s or "medium" in s:
        return "moderate"
    if "low" in s:
        return "low"
    return "unknown"


def _clean_vehicles(in_path: Path, out_path: Path) -> tuple[set[str], dict[str, Any]]:
    kept_ids: set[str] = set()
    before = 0
    dropped_bad_id = 0

    with in_path.open("r", newline="", encoding="utf-8", errors="ignore") as fin, out_path.open(
        "w", newline="", encoding="utf-8"
    ) as fout:
        reader = csv.DictReader(fin)
        writer = csv.DictWriter(fout, fieldnames=reader.fieldnames or [])
        writer.writeheader()
        for row in reader:
            before += 1
            vid = _to_positive_vehicle_id(row.get("vehicle_id"))
            if vid is None:
                dropped_bad_id += 1
                continue
            row["vehicle_id"] = vid
            if vid in kept_ids:
                # Should not happen in current data, but if it does, keep first and skip duplicates.
                continue
            kept_ids.add(vid)
            writer.writerow(row)

    return kept_ids, {
        "input_rows": before,
        "output_rows": len(kept_ids),
        "dropped_bad_or_nonpositive_vehicle_id": dropped_bad_id,
    }


def _clean_events(
    in_path: Path, out_path: Path, valid_vehicle_ids: set[str]
) -> dict[str, Any]:
    before = 0
    kept = 0
    dropped_bad_id = 0
    dropped_unknown_vehicle = 0

    with in_path.open("r", newline="", encoding="utf-8", errors="ignore") as fin, out_path.open(
        "w", newline="", encoding="utf-8"
    ) as fout:
        reader = csv.DictReader(fin)
        writer = csv.DictWriter(fout, fieldnames=reader.fieldnames or [])
        writer.writeheader()
        for row in reader:
            before += 1
            vid = _to_positive_vehicle_id(row.get("vehicle_id"))
            if vid is None:
                dropped_bad_id += 1
                continue
            if vid not in valid_vehicle_ids:
                dropped_unknown_vehicle += 1
                continue
            row["vehicle_id"] = vid
            writer.writerow(row)
            kept += 1

    return {
        "input_rows": before,
        "output_rows": kept,
        "dropped_bad_or_nonpositive_vehicle_id": dropped_bad_id,
        "dropped_unknown_vehicle_id": dropped_unknown_vehicle,
    }


def _clean_risk(in_path: Path, out_path: Path) -> dict[str, Any]:
    before = 0
    unknown_count = 0

    with in_path.open("r", newline="", encoding="utf-8", errors="ignore") as fin, out_path.open(
        "w", newline="", encoding="utf-8"
    ) as fout:
        reader = csv.DictReader(fin)
        writer = csv.DictWriter(fout, fieldnames=reader.fieldnames or [])
        writer.writeheader()
        for row in reader:
            before += 1
            label = _normalize_risk_label(row.get("risk_classification"))
            if label == "unknown":
                unknown_count += 1
            row["risk_classification"] = label
            writer.writerow(row)

    return {
        "input_rows": before,
        "output_rows": before,
        "normalized_risk_labels": ["low", "moderate", "high", "unknown"],
        "unknown_risk_label_rows": unknown_count,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--in-dir", default="data/normalized")
    parser.add_argument("--out-dir", default="data/normalized_v2")
    args = parser.parse_args()

    in_dir = Path(args.in_dir)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    in_vehicles = in_dir / "vehicles.csv"
    in_events = in_dir / "maintenance_events.csv"
    in_risk = in_dir / "risk_observations.csv"
    for p in (in_vehicles, in_events, in_risk):
        if not p.exists():
            raise FileNotFoundError(f"Missing required input file: {p.as_posix()}")

    out_vehicles = out_dir / "vehicles.csv"
    out_events = out_dir / "maintenance_events.csv"
    out_risk = out_dir / "risk_observations.csv"

    valid_vehicle_ids, vehicles_report = _clean_vehicles(in_vehicles, out_vehicles)
    events_report = _clean_events(in_events, out_events, valid_vehicle_ids)
    risk_report = _clean_risk(in_risk, out_risk)

    report = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "input_dir": in_dir.as_posix(),
        "output_dir": out_dir.as_posix(),
        "vehicles": vehicles_report,
        "maintenance_events": events_report,
        "risk_observations": risk_report,
    }
    (out_dir / "quality_report.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )

    print(json.dumps(report, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

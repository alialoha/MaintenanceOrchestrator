"""Normalize Kaggle raw seed data into MCP-friendly tables.

This script never mutates raw files. It reads from:
  data/raw/kaggle/

And writes normalized copies to:
  data/normalized/
"""
from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _as_int(val: str | None) -> int | None:
    if val is None:
        return None
    s = str(val).strip()
    if not s:
        return None
    try:
        return int(float(s))
    except Exception:
        return None


def _as_float(val: str | None) -> float | None:
    if val is None:
        return None
    s = str(val).strip()
    if not s:
        return None
    try:
        return float(s)
    except Exception:
        return None


def _as_date(val: str | None) -> str:
    s = (val or "").strip()
    if not s:
        return ""
    # keep ISO-like yyyy-mm-dd only; otherwise raw text
    try:
        datetime.strptime(s, "%Y-%m-%d")
        return s
    except Exception:
        return s


def _normalize_maintenance(
    in_csv: Path, out_vehicles: Path, out_events: Path
) -> dict[str, Any]:
    vehicles: dict[str, dict[str, Any]] = {}
    event_count = 0

    out_events.parent.mkdir(parents=True, exist_ok=True)
    with in_csv.open("r", newline="", encoding="utf-8-sig", errors="ignore") as fin, out_events.open(
        "w", newline="", encoding="utf-8"
    ) as fev:
        reader = csv.DictReader(fin)
        event_fields = [
            "event_id",
            "vehicle_id",
            "event_date",
            "maintenance_type",
            "maintenance_required",
            "maintenance_level",
            "severity_score",
            "predictive_score",
            "failure_history",
            "anomalies_detected",
            "engine_temperature",
            "tire_pressure",
            "fuel_consumption",
            "battery_status",
            "vibration_levels",
            "oil_quality",
            "brake_condition",
            "weather_conditions",
            "road_conditions",
            "delivery_times",
            "downtime_maintenance",
            "impact_on_efficiency",
            "maintenance_cost",
            "source_dataset",
        ]
        w = csv.DictWriter(fev, fieldnames=event_fields)
        w.writeheader()

        for row in reader:
            raw_vid = (row.get("Vehicle_ID") or "").strip()
            if not raw_vid:
                continue
            vid = str(_as_int(raw_vid) or raw_vid)
            event_date = _as_date(row.get("Last_Maintenance_Date"))

            # Keep latest seen row metadata for vehicle master.
            prev = vehicles.get(vid)
            candidate = {
                "vehicle_id": vid,
                "make_and_model": (row.get("Make_and_Model") or "").strip(),
                "year_of_manufacture": _as_int(row.get("Year_of_Manufacture")),
                "vehicle_type": (row.get("Vehicle_Type") or "").strip(),
                "route_info": (row.get("Route_Info") or "").strip(),
                "load_capacity": _as_float(row.get("Load_Capacity")),
                "latest_usage_hours": _as_float(row.get("Usage_Hours")),
                "latest_maintenance_date": event_date,
            }
            if prev is None:
                vehicles[vid] = candidate
            else:
                prev_date = prev.get("latest_maintenance_date", "")
                if event_date and (not prev_date or event_date >= prev_date):
                    vehicles[vid] = candidate

            event_count += 1
            w.writerow(
                {
                    "event_id": f"ME-{event_count}",
                    "vehicle_id": vid,
                    "event_date": event_date,
                    "maintenance_type": (row.get("Maintenance_Type") or "").strip(),
                    "maintenance_required": _as_int(row.get("Maintenance_Required")),
                    "maintenance_level": (row.get("Maintenance_Level") or "").strip(),
                    "severity_score": _as_float(row.get("Severity_Score")),
                    "predictive_score": _as_float(row.get("Predictive_Score")),
                    "failure_history": _as_int(row.get("Failure_History")),
                    "anomalies_detected": _as_int(row.get("Anomalies_Detected")),
                    "engine_temperature": _as_float(row.get("Engine_Temperature")),
                    "tire_pressure": _as_float(row.get("Tire_Pressure")),
                    "fuel_consumption": _as_float(row.get("Fuel_Consumption")),
                    "battery_status": _as_float(row.get("Battery_Status")),
                    "vibration_levels": _as_float(row.get("Vibration_Levels")),
                    "oil_quality": _as_float(row.get("Oil_Quality")),
                    "brake_condition": (row.get("Brake_Condition") or "").strip(),
                    "weather_conditions": (row.get("Weather_Conditions") or "").strip(),
                    "road_conditions": (row.get("Road_Conditions") or "").strip(),
                    "delivery_times": _as_float(row.get("Delivery_Times")),
                    "downtime_maintenance": _as_float(row.get("Downtime_Maintenance")),
                    "impact_on_efficiency": _as_float(row.get("Impact_on_Efficiency")),
                    "maintenance_cost": _as_float(row.get("Maintenance_Cost")),
                    "source_dataset": in_csv.name,
                }
            )

    with out_vehicles.open("w", newline="", encoding="utf-8") as fv:
        fields = [
            "vehicle_id",
            "make_and_model",
            "year_of_manufacture",
            "vehicle_type",
            "route_info",
            "load_capacity",
            "latest_usage_hours",
            "latest_maintenance_date",
        ]
        w = csv.DictWriter(fv, fieldnames=fields)
        w.writeheader()
        for _, rec in sorted(vehicles.items(), key=lambda kv: _as_int(kv[0]) or 0):
            w.writerow(rec)

    return {
        "vehicles_rows": len(vehicles),
        "maintenance_events_rows": event_count,
        "maintenance_source_file": in_csv.as_posix(),
    }


def _normalize_supply_chain(in_csv: Path, out_csv: Path) -> dict[str, Any]:
    count = 0
    with in_csv.open("r", newline="", encoding="utf-8-sig", errors="ignore") as fin, out_csv.open(
        "w", newline="", encoding="utf-8"
    ) as fout:
        reader = csv.DictReader(fin)
        fields = [
            "observation_id",
            "timestamp",
            "vehicle_gps_latitude",
            "vehicle_gps_longitude",
            "traffic_congestion_level",
            "eta_variation_hours",
            "weather_condition_severity",
            "route_risk_level",
            "delay_probability",
            "risk_classification",
            "disruption_likelihood_score",
            "driver_behavior_score",
            "fatigue_monitoring_score",
            "shipping_costs",
            "lead_time_days",
            "delivery_time_deviation",
            "source_dataset",
        ]
        w = csv.DictWriter(fout, fieldnames=fields)
        w.writeheader()
        for row in reader:
            count += 1
            w.writerow(
                {
                    "observation_id": f"RS-{count}",
                    "timestamp": (row.get("timestamp") or "").strip(),
                    "vehicle_gps_latitude": _as_float(row.get("vehicle_gps_latitude")),
                    "vehicle_gps_longitude": _as_float(row.get("vehicle_gps_longitude")),
                    "traffic_congestion_level": _as_float(row.get("traffic_congestion_level")),
                    "eta_variation_hours": _as_float(row.get("eta_variation_hours")),
                    "weather_condition_severity": _as_float(
                        row.get("weather_condition_severity")
                    ),
                    "route_risk_level": _as_float(row.get("route_risk_level")),
                    "delay_probability": _as_float(row.get("delay_probability")),
                    "risk_classification": (row.get("risk_classification") or "").strip(),
                    "disruption_likelihood_score": _as_float(
                        row.get("disruption_likelihood_score")
                    ),
                    "driver_behavior_score": _as_float(row.get("driver_behavior_score")),
                    "fatigue_monitoring_score": _as_float(row.get("fatigue_monitoring_score")),
                    "shipping_costs": _as_float(row.get("shipping_costs")),
                    "lead_time_days": _as_float(row.get("lead_time_days")),
                    "delivery_time_deviation": _as_float(row.get("delivery_time_deviation")),
                    "source_dataset": in_csv.name,
                }
            )
    return {
        "risk_observations_rows": count,
        "risk_source_file": in_csv.as_posix(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--raw-dir",
        default="data/raw/kaggle",
        help="Input directory containing raw Kaggle downloads.",
    )
    parser.add_argument(
        "--out-dir",
        default="data/normalized",
        help="Output directory for normalized copies.",
    )
    args = parser.parse_args()

    raw_dir = Path(args.raw_dir)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    maintenance_src = raw_dir / "vehicle_maintenance_history" / "revised_logistics_dataset_V2.csv"
    supply_src = (
        raw_dir
        / "logistics_and_supply_chain"
        / "dynamic_supply_chain_logistics_dataset.csv"
    )
    if not maintenance_src.exists():
        raise FileNotFoundError(f"Missing source: {maintenance_src.as_posix()}")
    if not supply_src.exists():
        raise FileNotFoundError(f"Missing source: {supply_src.as_posix()}")

    vehicles_csv = out_dir / "vehicles.csv"
    maintenance_csv = out_dir / "maintenance_events.csv"
    risk_csv = out_dir / "risk_observations.csv"

    summary = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "input_raw_dir": raw_dir.as_posix(),
        "output_dir": out_dir.as_posix(),
    }
    summary.update(_normalize_maintenance(maintenance_src, vehicles_csv, maintenance_csv))
    summary.update(_normalize_supply_chain(supply_src, risk_csv))

    summary_path = out_dir / "manifest.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print("Normalization complete.", flush=True)
    print(json.dumps(summary, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

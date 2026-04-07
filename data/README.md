## Data Bundle

This folder contains public and synthetic-ready data inputs for the Maintenance Orchestrator demo.

### Raw downloads

- `raw/ai4i2020.csv`
  - Source: UCI AI4I 2020 Predictive Maintenance Dataset
  - URL: https://archive.ics.uci.edu/ml/machine-learning-databases/00601/ai4i2020.csv
  - License: CC BY 4.0 (per UCI dataset page)
  - Use in demo: failure-risk scoring and maintenance triage simulations.

- `raw/kaggle/logistics_and_supply_chain/*`
  - Source: Kaggle `datasetengineer/logistics-and-supply-chain-dataset`
  - Download via: `python scripts/download_kaggle_seed.py --dataset logistics_and_supply_chain`
  - Use in demo: shipment flow, route/timing context, and operational risk features.

- `raw/kaggle/vehicle_maintenance_history/*`
  - Source: Kaggle `datasetengineer/logistics-vehicle-maintenance-history-dataset`
  - Download via: `python scripts/download_kaggle_seed.py --dataset vehicle_maintenance_history`
  - Use in demo: recurring faults, maintenance history, and work-order signals.

### Synthetic demo overlays (Phase 2)

- `synthetic/parts_inventory.json`, `synthetic/shop_and_slots.json` — small bundles used by shop/scheduling MCP tools (not raw downloads). Logistics-style “deliveries at risk” come from `normalized/risk_observations.csv` via tools, not a separate JSON bundle.

### Reference mappings

- `reference/j1939_top_faults.json`
  - Practical SPN/FMI starter map for diagnostics workflows.
  - Seeded from public explanatory references, then normalized into structured JSON.

### Full-size local copies (>10 MB)

- Git excludes `data/full/`: place full CSV mirrors here when you have them locally (for example after download or normalization).
- The `normalized/*.csv` files committed in this repository are truncated copies suitable for demos and CI; replace them with the files from `data/full/` if you need the complete dataset for local runs.

### Notes

- Kaggle downloads require credentials/API access in your local environment.
- Run `python scripts/download_kaggle_seed.py` to fetch both recommended Kaggle datasets.
- `raw/` contains original downloaded files (never modified).
- `normalized/` contains cleaned, canonical copies used by the MCP tools.
- Historically we used `data/seed/`; now the same idea is flattened directly under `data/`.
- In this project, "seed" means bootstrapping/demo data (not production master data).
- This data bundle is intentionally "demo-safe" and can be transformed into
  business-domain entities (`vehicles`, `work_orders`, `telematics_events`, `parts`, `shops`).

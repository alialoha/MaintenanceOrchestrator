## Raw -> Normalized Transformation

This folder is the canonical cleaned dataset for the maintenance orchestrator demo.

### Pipeline summary

1. Download raw inputs into `data/raw/kaggle/`:
   - `python scripts/download_kaggle_seed.py --method auto --dataset all`
2. Build stage-1 normalized tables:
   - `python scripts/normalize_kaggle_seed.py`
3. Run quality pass:
   - `python scripts/quality_pass_normalized_seed.py --in-dir data/normalized --out-dir data/normalized_v2`
4. Promote cleaned output:
   - replace `data/normalized` with `data/normalized_v2`

### Cleaning rules applied

- Keep only strictly positive integer `vehicle_id`.
- Drop maintenance events with invalid/nonpositive `vehicle_id`.
- Enforce referential integrity: each maintenance event must reference a kept vehicle.
- Normalize `risk_classification` labels to `low|moderate|high|unknown`.

### Before/after statistics

- Vehicles: `92,284 -> 92,147` (dropped `137`)
- Maintenance events: `250,000 -> 249,819` (dropped `181`)
- Risk observations: `32,065 -> 32,065` (no row drops, labels standardized)

See `quality_report.json` for machine-readable stats.

### Data safety policy

- `data/raw/` is immutable source data.
- `data/normalized/` is derived data and may be regenerated at any time.

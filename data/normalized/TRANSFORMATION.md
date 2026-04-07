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
## Raw -> Normalized Transformation (Current Canonical Dataset)

This directory is the canonical cleaned dataset used by the project.

### Pipeline used

1. Raw Kaggle downloads were fetched into `data/raw/kaggle/` using:
   - `python scripts/download_kaggle_seed.py --method auto --dataset all`
2. Stage-1 normalization created structured tables from raw:
   - `vehicles.csv`
   - `maintenance_events.csv`
   - `risk_observations.csv`
3. Quality pass (stage-2) applied cleaning rules:
   - Keep only strictly positive integer `vehicle_id`
   - Drop maintenance events with bad/nonpositive `vehicle_id`
   - Enforce referential integrity for events -> vehicles
   - Normalize `risk_classification` labels to `low|moderate|high|unknown`
4. Consolidation:
   - Stage-1 normalized data was deleted.
   - Cleaned stage-2 output (`normalized_v2`) was promoted to this directory (`normalized`).

### Change statistics

From quality pass report (`quality_report.json`):

- Vehicles:
  - Input: `92,284`
  - Output: `92,147`
  - Dropped: `137` bad/nonpositive `vehicle_id`
- Maintenance events:
  - Input: `250,000`
  - Output: `249,819`
  - Dropped: `181` bad/nonpositive `vehicle_id`
  - Dropped for unknown vehicle link: `0`
- Risk observations:
  - Input: `32,065`
  - Output: `32,065`
  - Unknown risk labels after normalization: `0`

### Why raw is preserved

All source files under `data/raw/` remain untouched for traceability and reproducibility.

# Operator Runbook

## Purpose

Practical checklist for operating the Maintenance Orchestrator safely and consistently.

## Startup order

1. Start MCP server (`scripts/01-mcp-server.ps1`).
2. Start Operator UI (`scripts/02-operator.ps1`).
3. (Optional) Start Flask user UI (`scripts/03-web.ps1`).

## Pre-flight checks

- Verify MCP endpoint: `http://127.0.0.1:8000/mcp`.
- Verify `MCP_DATA_DIR` points to this repo's `data`.
- Verify `LLM_PROVIDER` credentials are set when using Live mode.
- Regenerate overlays after normalized data changes:
  - `python scripts/materialize_phase3_data.py`

## Standard incident workflow

1. `fetch_vehicle_faults`
2. `lookup_fault_resolution`
3. `score_fault_severity`
4. `predict_maintenance_need`
5. If needed: `create_work_order`
6. For high/critical: `request_approval`
7. `estimate_repair_duration`
8. `propose_service_appointment`
9. `reserve_service_slot`
10. `estimate_delay_impact`
11. `generate_operator_summary`
12. `generate_customer_update`

## Approval policy

- Any high/critical action path should explicitly invoke `request_approval`.
- Record outcomes using `record_decision_log`.
- Use `get_audit_trail` for review and postmortem.

## Common failure modes

- Wrong MCP server on port: ensure no other server uses `8000`.
- Empty/weak logistics results: confirm `data/normalized/risk_observations.csv` exists.
- Stale parts/slots: rerun materializer script.
- LLM unavailable: fallback to Demo mode until credentials are fixed.

## End-of-shift checklist

- Ensure decision logs were written for significant approvals/denials.
- Confirm no unexpected pending approvals remain.
- Capture key incident IDs and work order IDs for handoff.

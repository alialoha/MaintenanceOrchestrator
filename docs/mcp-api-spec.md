# MaintenanceOrchestrator MCP API Spec (Draft v0.1)

This document defines the first implementation contract for MCP tools, resources, and prompts.

## Scope

- Domain: fleet maintenance + operational risk orchestration
- Data backing: `data/normalized/*`, `data/reference/*`, synthetic tables for work orders/slots/parts/deliveries
- Goal: deterministic tool outputs that LLMs can chain safely under policy controls

## Conventions

### Naming

- Tools: `snake_case`, action-first (`create_work_order`, `estimate_delay_impact`)
- Resources: noun-first (`vehicle_profile`, `shop_capacity_snapshot`)
- Prompts: `prompt_*`

### Cross-cutting response envelope

All tool responses should include:

```json
{
  "ok": true,
  "result": {},
  "confidence": 0.0,
  "assumptions": [],
  "next_actions": [],
  "requires_approval": false,
  "approval_reason": null
}
```

Notes:
- `confidence` is required for predictive/ranking outputs; use `1.0` for deterministic lookups.
- `requires_approval` should be set by tool logic when action impact is above thresholds.

### Risk tiers (for MCP policy)

- `low`: read-only, summary, listing
- `medium`: recommendation/planning, no state mutation
- `high`: mutating operations (`create_*`, `reserve_*`, dispatch-impacting actions)

---

## 1) Diagnostics Module

### Tool: `fetch_vehicle_faults` (risk: low)

Input:
```json
{
  "type": "object",
  "properties": {
    "vehicle_id": { "type": "string" },
    "lookback_hours": { "type": "integer", "minimum": 1, "maximum": 168, "default": 24 }
  },
  "required": ["vehicle_id"],
  "additionalProperties": false
}
```

Result shape:
```json
{
  "vehicle_id": "64940",
  "faults": [
    { "event_time": "2026-04-07T02:10:00Z", "spn": 102, "fmi": 3, "occurrence_count": 4, "source_address": "engine_ecu" }
  ]
}
```

### Tool: `lookup_fault_resolution` (risk: low)

Input:
```json
{
  "type": "object",
  "properties": {
    "spn": { "type": "integer" },
    "fmi": { "type": "integer" }
  },
  "required": ["spn", "fmi"],
  "additionalProperties": false
}
```

Result shape:
```json
{
  "spn": 102,
  "fmi": 3,
  "fault_name": "Boost Pressure",
  "fmi_meaning": "Voltage above normal",
  "default_severity": "high",
  "recommended_actions": ["Inspect boost pressure sensor and connector", "Check charge-air piping for leaks"],
  "required_parts": ["boost_pressure_sensor"],
  "estimated_labor_hours": 1.5
}
```

### Tool: `score_fault_severity` (risk: medium)

Input:
```json
{
  "type": "object",
  "properties": {
    "vehicle_id": { "type": "string" },
    "spn": { "type": "integer" },
    "fmi": { "type": "integer" },
    "context": { "type": "object" }
  },
  "required": ["vehicle_id", "spn", "fmi"],
  "additionalProperties": false
}
```

Result shape:
```json
{
  "vehicle_id": "64940",
  "spn": 102,
  "fmi": 3,
  "severity_score": 0.86,
  "severity_label": "high",
  "drivers": ["high predictive score", "recent recurrence", "high delay probability"]
}
```

---

## 2) Maintenance Planning Module

### Tool: `get_maintenance_history` (risk: low)

Input:
```json
{
  "type": "object",
  "properties": {
    "vehicle_id": { "type": "string" },
    "limit": { "type": "integer", "minimum": 1, "maximum": 200, "default": 20 }
  },
  "required": ["vehicle_id"],
  "additionalProperties": false
}
```

### Tool: `predict_maintenance_need` (risk: medium)

Input:
```json
{
  "type": "object",
  "properties": {
    "vehicle_id": { "type": "string" }
  },
  "required": ["vehicle_id"],
  "additionalProperties": false
}
```

Result includes:
- `maintenance_need_probability`
- `recommended_window_hours`
- `top_features`

### Tool: `create_work_order` (risk: high)

Input:
```json
{
  "type": "object",
  "properties": {
    "vehicle_id": { "type": "string" },
    "issue_summary": { "type": "string", "minLength": 5, "maxLength": 1000 },
    "priority": { "type": "string", "enum": ["low", "medium", "high", "critical"] }
  },
  "required": ["vehicle_id", "issue_summary", "priority"],
  "additionalProperties": false
}
```

Result includes:
- `work_order_id`
- `status` (created)
- `priority`
- `requires_approval` true when `priority in ["high","critical"]`

### Tool: `estimate_repair_duration` (risk: medium)

Input:
```json
{
  "type": "object",
  "properties": {
    "work_order_id": { "type": "string" }
  },
  "required": ["work_order_id"],
  "additionalProperties": false
}
```

---

## 3) Shop and Parts Module

### Tool: `check_parts_inventory` (risk: low)

Input:
```json
{
  "type": "object",
  "properties": {
    "location_id": { "type": "string" },
    "part_numbers": { "type": "array", "items": { "type": "string" }, "minItems": 1, "maxItems": 50 }
  },
  "required": ["location_id", "part_numbers"],
  "additionalProperties": false
}
```

### Tool: `propose_service_appointment` (risk: medium)

Input:
```json
{
  "type": "object",
  "properties": {
    "location_id": { "type": "string" },
    "duration_hours": { "type": "number", "minimum": 0.5, "maximum": 24 },
    "priority": { "type": "string", "enum": ["low", "medium", "high", "critical"] }
  },
  "required": ["location_id", "duration_hours", "priority"],
  "additionalProperties": false
}
```

### Tool: `reserve_service_slot` (risk: high)

Input:
```json
{
  "type": "object",
  "properties": {
    "work_order_id": { "type": "string" },
    "slot_id": { "type": "string" }
  },
  "required": ["work_order_id", "slot_id"],
  "additionalProperties": false
}
```

---

## 4) Logistics Impact Module

### Tool: `list_deliveries_at_risk` (risk: low)

Input:
```json
{
  "type": "object",
  "properties": {
    "vehicle_id": { "type": "string" },
    "horizon_hours": { "type": "integer", "minimum": 1, "maximum": 168, "default": 48 }
  },
  "required": ["vehicle_id"],
  "additionalProperties": false
}
```

### Tool: `estimate_delay_impact` (risk: medium)

Input:
```json
{
  "type": "object",
  "properties": {
    "vehicle_id": { "type": "string" },
    "scenario": { "type": "string", "enum": ["repair_now", "defer_24h", "swap_vehicle"] }
  },
  "required": ["vehicle_id", "scenario"],
  "additionalProperties": false
}
```

Result includes:
- `estimated_delay_hours`
- `sla_breach_probability`
- `estimated_cost_impact`

---

## 5) Communications Module

### Tool: `generate_operator_summary` (risk: low)

Input:
```json
{
  "type": "object",
  "properties": {
    "work_order_id": { "type": "string" }
  },
  "required": ["work_order_id"],
  "additionalProperties": false
}
```

### Tool: `generate_customer_update` (risk: low)

Input:
```json
{
  "type": "object",
  "properties": {
    "delivery_id": { "type": "string" },
    "tone": { "type": "string", "enum": ["professional", "concise", "empathetic"], "default": "professional" }
  },
  "required": ["delivery_id"],
  "additionalProperties": false
}
```

---

## 6) Governance and Audit Module

### Tool: `request_approval` (risk: high)

Input:
```json
{
  "type": "object",
  "properties": {
    "action_type": { "type": "string" },
    "payload": { "type": "object" },
    "reason": { "type": "string" },
    "estimated_cost": { "type": "number", "minimum": 0 }
  },
  "required": ["action_type", "payload", "reason"],
  "additionalProperties": false
}
```

### Tool: `record_decision_log` (risk: medium)

Input:
```json
{
  "type": "object",
  "properties": {
    "actor": { "type": "string" },
    "action": { "type": "string" },
    "outcome": { "type": "string" },
    "rationale": { "type": "string" },
    "entity_type": { "type": "string" },
    "entity_id": { "type": "string" }
  },
  "required": ["actor", "action", "outcome", "entity_type", "entity_id"],
  "additionalProperties": false
}
```

### Tool: `get_audit_trail` (risk: low)

Input:
```json
{
  "type": "object",
  "properties": {
    "entity_type": { "type": "string" },
    "entity_id": { "type": "string" },
    "limit": { "type": "integer", "minimum": 1, "maximum": 500, "default": 100 }
  },
  "required": ["entity_type", "entity_id"],
  "additionalProperties": false
}
```

---

## Resources (initial)

- `j1939_fault_catalog` -> `data/reference/j1939_top_faults.json`
- `vehicle_profile` -> from `data/normalized/vehicles.csv`
- `maintenance_events_recent` -> from `data/normalized/maintenance_events.csv`
- `risk_observations_recent` -> from `data/normalized/risk_observations.csv`
- `shop_capacity_snapshot` -> `data/synthetic/shop_and_slots.json` (resource URI `file://data/synthetic/shop_capacity`)
- `parts_inventory_snapshot` -> `data/synthetic/parts_inventory.json` (resource URI `file://data/synthetic/parts_inventory`)
- `deliveries_demo` -> `data/synthetic/deliveries.json` (resource URI `file://data/synthetic/deliveries`)

## Prompts (initial)

- `prompt_incident_triage`
- `prompt_work_order_review`
- `prompt_customer_update`

Each prompt should include:
- required tool sequence hints
- approval checkpoints
- output format expectations

---

## Phase Plan

### Phase 1 (implement first)

- Diagnostics: `fetch_vehicle_faults`, `lookup_fault_resolution`, `score_fault_severity`
- Planning: `get_maintenance_history`, `predict_maintenance_need`, `create_work_order`
- Governance: `request_approval`, `record_decision_log`, `get_audit_trail`

### Phase 2 (implemented)

- Shop/parts/scheduling: `check_parts_inventory`, `propose_service_appointment`, `reserve_service_slot`
- Planning: `estimate_repair_duration` (see §2 Maintenance Planning)
- Logistics impact: `list_deliveries_at_risk`, `estimate_delay_impact`
- Synthetic seed data: `data/synthetic/*.json`; slot ledger: `data/operations/slot_reservations.jsonl`
- Resources: `file://data/synthetic/parts_inventory`, `file://data/synthetic/shop_capacity`, `file://data/synthetic/deliveries`

### Phase 3

- Communication tools and richer prompt packs
- Additional synthetic data generators for shops, parts, deliveries

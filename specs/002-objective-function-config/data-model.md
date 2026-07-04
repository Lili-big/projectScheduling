# Data Model: Objective Function Configuration

## ObjectiveTermId

Stable ids for editable refinement soft objectives:

- `control_node_late`
- `control_buffer_risk`
- `risk_related_control_wait`
- `resource_workload_balance`
- `resource_idle`
- `resource_path_continuity`
- `makespan_and_soft_milestone`

## ObjectiveTermConfig

Represents one requested objective term configuration.

| Field | Type | Rule |
| --- | --- | --- |
| `enabled` | boolean | Defaults to true for all terms unless compatibility rules say otherwise |
| `weight` | integer | Requested display/solve weight, valid range `1..1_000_000_000` |

Validation:

- Unknown term ids are rejected.
- Legacy `spatial_resource_assignment`, `same_structure_craft_split`, and `normal_balance` inputs are ignored as deprecated terms.
- Enabled term weights outside range are rejected.
- Disabled terms retain their stored weight for display.
- At least one term must be enabled.

## ObjectiveTermUsed

Result metadata emitted after refinement.

| Field | Type | Rule |
| --- | --- | --- |
| `enabled` | boolean | Requested enabled state |
| `weight` | integer | Requested/display weight |
| `effective_weight` | integer | `weight` when enabled; `0` when disabled |
| `label` | string | Human-readable label for diagnostics |

## ScheduleStrategyConfig

Existing scenario-level strategy object gains:

| Field | Type | Rule |
| --- | --- | --- |
| `objective_terms` | map from `ObjectiveTermId` to `ObjectiveTermConfig` | Optional on input; backend merges defaults |

Compatibility:

- Existing `enable_balance_objective` remains accepted.
- `enable_balance_objective` no longer enables a current objective term and is normalized to false.
- If `objective_terms.normal_balance` is present in a legacy payload, it is filtered out and does not appear in normalized objective terms.

## ScheduleResult objective metadata

`objective_breakdown` includes:

| Field | Meaning |
| --- | --- |
| `objective_terms_used` | Rich per-term requested and effective configuration |
| `objective_weights` | Effective weights map kept for compatibility |

No database or local scenario persistence model changes are required in this phase.

# Contract: Objective Function Configuration

## Request Contract

The existing scheduling endpoints continue to accept `ScenarioInput`.

Impacted endpoints:

- `POST /api/generate-schedule-input`
- `POST /api/solve-scenario`
- `POST /api/solve-min-resources`
- `POST /api/solve-resource-cost`

`ScenarioInput.schedule_strategy.objective_terms` is optional.

```json
{
  "schedule_strategy": {
    "strategy": "comprehensive",
    "enable_balance_objective": false,
    "objective_terms": {
      "control_node_late": { "enabled": true, "weight": 1000000000 },
      "resource_idle": { "enabled": true, "weight": 1000 }
    }
  }
}
```

Missing current terms are filled with defaults. Unknown terms or invalid enabled weights reject the request. Legacy `normal_balance` is accepted for compatibility but filtered out.

## Result Contract

Refinement results include effective objective metadata:

```json
{
  "objective_breakdown": {
    "objective_weights": {
      "control_node_late": 1000000000,
      "resource_idle": 1000
    },
    "objective_terms_used": {
      "control_node_late": {
        "label": "控制节点迟延",
        "enabled": true,
        "weight": 1000000000,
        "effective_weight": 1000000000
      },
      "resource_idle": {
        "label": "资源空闲",
        "enabled": true,
        "weight": 1000,
        "effective_weight": 1000
      }
    }
  }
}
```

## Frontend Contract

The full "模拟求解" page shows the objective controls in the existing "模拟参数" area. The "模拟求解-MVP" page does not render these controls.

User edits update `ScenarioInput.schedule_strategy.objective_terms`, so the existing scenario fingerprint mechanism treats old generated and solved results as stale.

## Netlify Demo Contract

The demo surface accepts the same request field and may echo/default `objective_terms_used`, but it does not claim Python CP-SAT objective parity.

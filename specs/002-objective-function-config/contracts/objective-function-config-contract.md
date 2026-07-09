# Contract: Objective Function Configuration

> 当前实现校正（2026-07-09）：`resource_path_continuity` 已从当前目标项体系中移除；旧输入字段仅作为废弃兼容字段被忽略。当前目标项为 `control_node_late`、`makespan_and_soft_milestone`、`resource_idle`。第一阶段路径连续性、无窗口候选路径和资源路径罚分均为历史设计，不再建路径 circuit 或产生路径罚分；机械钻组聚合、组内升序和同组同资源保留为基础规则。

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
      "control_node_late": { "enabled": true, "weight": 10000000000 },
      "makespan_and_soft_milestone": { "enabled": true, "weight": 5000000 },
      "resource_path_continuity": { "enabled": true, "weight": 50000 },
      "resource_idle": { "enabled": true, "weight": 50000 }
    }
  }
}
```

Missing current terms are filled with defaults. Unknown terms or invalid enabled weights reject the request. Deprecated terms such as `control_buffer_risk`, `risk_related_control_wait`, `resource_workload_balance`, `unconfigured_normal_balance`, and `normal_balance` are accepted for compatibility but filtered out.

## Result Contract

Refinement results include effective objective metadata:

```json
{
  "objective_breakdown": {
    "objective_weights": {
      "control_node_late": 10000000000,
      "makespan_and_soft_milestone": 5000000,
      "resource_path_continuity": 50000,
      "resource_idle": 50000
    },
    "objective_terms_used": {
      "control_node_late": {
        "label": "控制节点迟延",
        "enabled": true,
        "weight": 10000000000,
        "effective_weight": 10000000000
      },
      "resource_idle": {
        "label": "资源空闲",
        "enabled": true,
        "weight": 50000,
        "effective_weight": 50000
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

# 契约：目标指标建模门控

## 请求契约

请求字段沿用既有 `ScenarioInput.schedule_strategy.objective_terms`，不新增目标项 ID。

受影响接口：

- `POST /api/solve-scenario`
- `POST /api/solve-min-resources`
- `POST /api/generate-schedule-input`

示例：

```json
{
  "schedule_strategy": {
    "strategy": "comprehensive",
    "objective_terms": {
      "control_node_late": { "enabled": true, "weight": 10000000000 },
      "makespan_and_soft_milestone": { "enabled": true, "weight": 5000000 },
      "resource_path_continuity": { "enabled": false, "weight": 50000 },
      "resource_idle": { "enabled": false, "weight": 50000 }
    }
  }
}
```

规则：

- 缺失目标项继续按默认值补齐。
- 未知目标项按现有规则拒绝或兼容过滤废弃项。
- 所有当前目标项都关闭时继续拒绝请求。
- 关闭项的展示权重可保留，但有效权重为 0。

## 结果契约

精排结果继续返回 `objective_breakdown.objective_terms_used` 和 `objective_breakdown.objective_weights`。

允许新增 `objective_modeling_gates` 用于解释建模门控：

```json
{
  "objective_breakdown": {
    "objective_modeling_gates": {
      "control_node_late": {
        "modeling_enabled": true,
        "status": "enabled",
        "reason": "objective term enabled"
      },
      "resource_path_continuity": {
        "modeling_enabled": false,
        "status": "not_enabled",
        "reason": "effective weight is 0"
      }
    }
  }
}
```

资源路径连续性关闭时，诊断字段必须表达未评价并清空建模规模：

```json
{
  "stats": {
    "continuity_objective": {
      "resource_path_status": "not_evaluated",
      "resource_path_node_count": 0,
      "resource_path_transition_arc_count": 0
    },
    "resource_organization_analysis": {
      "resource_balance_status": "not_evaluated",
      "resource_idle_status": "not_evaluated",
      "resource_path_status": "not_evaluated"
    }
  }
}
```

## 前端契约

- 目标函数配置区继续展示 4 个当前目标项：`control_node_late`、`makespan_and_soft_milestone`、`resource_path_continuity`、`resource_idle`。
- 关闭项的结果展示必须根据 `effective_weight = 0` 和状态字段表达为未启用或未评价。
- 已启用但罚分为 0 的指标必须和关闭项区分。
- 若后端未返回 `objective_modeling_gates`，前端仍可依据 `objective_terms_used` 和既有诊断字段兼容展示。

## 最佳努力契约

严格精排失败后进入最佳努力分支时，目标放松迟延作为 `best_effort_refinement` 诊断展示。

要求：

- 不把最佳努力放松迟延误报为用户关闭的常规目标项已启用。
- `relaxed_target_penalty_days`、`relaxed_constraints` 和 `schedule_source` 保持现有兼容路径。
- 页面应继续提示“该结果不代表目标已全部满足”。

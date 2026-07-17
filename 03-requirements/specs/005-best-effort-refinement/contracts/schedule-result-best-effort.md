# 接口契约：最佳努力精排结果

## 适用接口

- `POST /api/solve-scenario`
- `POST /api/solve-min-resources`

## 后端返回契约

### 当前资源目标未满足结果（当前口径）

```json
{
  "result": {
    "status": "FEASIBLE",
    "objective_days": 126,
    "stats": {
      "schedule_source": "current_resources_target_failed",
      "performance_path": "current_resources_full_objective_target_failed_resource_recommendation",
      "target_achievement": {
        "target_status": "current_resources_target_failed",
        "business_success": false,
        "target_lateness_days": 8,
        "fixed_duration_overrun_days": 0
      }
    },
    "objective_breakdown": {
      "schedule_source": "current_resources_target_failed",
      "target_achievement": {
        "target_status": "current_resources_target_failed",
        "business_success": false
      }
    }
  }
}
```

### 最少资源候选最佳努力精排

```json
{
  "result": {
    "status": "FEASIBLE",
    "stats": {
      "schedule_source": "minimum_resources_best_effort_refinement",
      "recommended_schedule_source": "minimum_resources_best_effort_refinement",
      "best_effort_refinement": {
        "enabled": true,
        "fallback_from": "minimum_resources_control_priority_balanced",
        "strict_refinement_status": "UNKNOWN",
        "strict_refinement_failure_reason": "time_limit_without_strict_solution",
        "objective_status": "FEASIBLE",
        "target_lateness_days": 3,
        "fixed_duration_overrun_days": 3,
        "relaxed_constraints": [
          {
            "type": "fixed_duration",
            "name": "固定工期目标",
            "target": 120,
            "actual": 123,
            "lateness_days": 3
          }
        ]
      }
    }
  }
}
```

## 前端展示契约

- `current_resources_best_effort_refinement` 仅作为历史兼容来源显示，不作为当前固定资源主链路的新结果来源。
- `current_resources_target_failed` 显示为“当前资源目标未满足”，并展示目标达成诊断与资源建议。
- `minimum_resources_best_effort_refinement` 显示为“最少资源候选最佳努力精排”。
- 当 `best_effort_refinement.enabled = true` 时，精排诊断必须显示：
  - 严格精排状态；
  - 放松的目标类型；
  - 强制节点迟延天数或固定工期超期天数；
  - “该结果不代表目标已满足”的提示。
- 里程碑表仍按真实迟延状态展示，不因最佳努力来源而改为满足。

## 兼容性

- 旧前端若不认识最佳努力来源，仍可根据 `milestones`、`validation` 和 `objective_days` 展示基础结果。
- 新元数据放在 `stats` 和 `objective_breakdown`，不要求旧 payload 新增顶层字段。
- 既有来源 `current_resources_control_priority_balanced`、`current_resources_target_failed`、`minimum_resources_control_priority_balanced`、`minimum_resources_best_effort_refinement`、`minimum_resources_refinement_fallback` 语义保持不变；`current_resources_capacity_shortest_fallback` 仅为历史兼容或内部诊断辅助，不作为当前资源失败后的主展示来源。

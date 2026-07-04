# 接口契约：最佳努力精排结果

## 适用接口

- `POST /api/solve-scenario`
- `POST /api/solve-min-resources`

## 后端返回契约

### 当前资源最佳努力精排

```json
{
  "result": {
    "status": "FEASIBLE",
    "objective_days": 126,
    "stats": {
      "schedule_source": "current_resources_best_effort_refinement",
      "performance_path": "capacity_fast_path_best_effort_refinement",
      "best_effort_refinement": {
        "enabled": true,
        "schedule_source": "current_resources_best_effort_refinement",
        "fallback_from": "current_resources_control_priority_balanced",
        "strict_refinement_status": "INFEASIBLE",
        "strict_refinement_failure_reason": "hard_milestone_or_fixed_duration_not_satisfied",
        "objective_status": "FEASIBLE",
        "target_lateness_days": 8,
        "fixed_duration_overrun_days": 0,
        "best_effort_score": 12345,
        "relaxed_constraints": [
          {
            "type": "hard_milestone",
            "id": "bridge_completion",
            "name": "桥梁完成",
            "target": "2026-10-01",
            "actual": "2026-10-09",
            "lateness_days": 8,
            "scope": "左11#墩"
          }
        ]
      }
    },
    "objective_breakdown": {
      "schedule_source": "current_resources_best_effort_refinement",
      "best_effort_refinement": {
        "enabled": true,
        "target_lateness_days": 8,
        "fixed_duration_overrun_days": 0
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

- `current_resources_best_effort_refinement` 显示为“最佳努力精排”。
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
- 既有来源 `current_resources_control_priority_balanced`、`current_resources_capacity_shortest_fallback`、`minimum_resources_control_priority_balanced`、`minimum_resources_refinement_fallback` 语义保持不变。

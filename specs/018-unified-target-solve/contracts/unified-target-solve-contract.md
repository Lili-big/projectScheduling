# 契约：统一目标函数求解与资源分支重构

本契约描述后端排程结果与前端展示之间的字段口径。实现阶段可以保留旧字段用于兼容，但新增统一目标达成语义必须使用本契约指定的稳定字段路径。

## 受影响接口

- `POST /api/solve-scenario`
- `POST /api/solve-min-resources`
- `POST /api/generate-schedule-input`
- 前端调度结果展示和资源推荐展示入口
- Netlify 演示接口如暴露同类结果，必须对齐或明确降级

## 请求契约

### 固定资源求工期

请求继续沿用现有 `ScenarioInput` 和资源池字段：

```json
{
  "solve_mode": "fixed_resources",
  "resources": [
    {
      "type": "rotary_drill",
      "quantity": 1,
      "max_quantity": 3
    }
  ],
  "schedule_strategy": {
    "objective_terms": {
      "control_node_late": {
        "enabled": true,
        "weight": 10000000000
      }
    }
  }
}
```

规则：

- `quantity` 是当前默认资源数量。
- `max_quantity` 是新增资源分支上限。
- 固定资源入口必须先使用 `quantity` 运行完整目标函数。
- 当前资源目标失败后，新增资源分支只能在 `quantity` 到 `max_quantity` 范围内搜索。

### 固定工期求资源

请求继续沿用现有固定工期/目标日期输入：

```json
{
  "solve_mode": "fixed_duration",
  "target_duration_days": 120,
  "resources": [
    {
      "type": "rotary_drill",
      "quantity": 1,
      "max_quantity": 3
    }
  ]
}
```

规则：

- 固定工期入口必须先用 `max_quantity` 运行硬里程碑和固定工期窗口快速预检，不得先运行完整目标函数预检。
- 最大资源快速预检通过后，才进入候选资源搜索。
- 最大资源快速预检不可行时，返回最大资源不满足目标的可解释结果。
- 最大资源预检 `UNKNOWN` 或预算耗尽时，返回未确认状态，不得返回资源上限不足。

## 结果契约

### 统一目标达成字段

后端结果必须在 `stats.target_achievement` 返回以下语义字段：

```json
{
  "stats": {
    "target_achievement": {
      "business_success": false,
      "target_status": "current_resources_target_failed",
      "solver_status": "FEASIBLE",
      "hard_milestone_late_days": 8,
      "fixed_duration_overrun_days": 0,
      "failure_reasons": ["hard_milestone_late"],
      "time_budget_seconds": 15,
      "time_budget_exhausted": false,
      "evaluated_at_source": "current_resources"
    }
  }
}
```

字段规则：

- `business_success` 表示业务目标是否达成，不等同于 `solver_status`。
- `target_status` 必须使用稳定枚举，前端不得通过中文文案反推状态。
- `hard_milestone_late_days` 和 `fixed_duration_overrun_days` 必须分别输出。
- `failure_reasons` 可包含 `hard_milestone_late`、`fixed_duration_overrun`、`physical_infeasible`、`max_resources_target_failed`、`time_budget_exhausted`、`unconfirmed`。
- `time_budget_seconds` 默认为 15。

### 目标函数贡献

`objective_breakdown` 必须能解释硬里程碑目标项：

```json
{
  "objective_breakdown": {
    "objective_terms_used": {
      "control_node_late": {
        "enabled": true,
        "effective_weight": 10000000000
      }
    },
    "objective_contributions": {
      "control_node_late": {
        "raw_value": 8,
        "unit": "days",
        "weight": 10000000000,
        "weighted_value": 80000000000
      }
    }
  }
}
```

规则：

- 硬里程碑晚点必须作为可解释目标贡献输出。
- 原始天数和加权贡献必须分开。
- 若固定工期超期作为目标项建模，也必须按同一结构输出；若只作为业务判定指标，也必须在 `target_achievement.fixed_duration_overrun_days` 输出。

### 当前资源失败结果

固定资源入口中，当前资源可排程但目标失败时，必须保留当前资源结果：

```json
{
  "schedule_source": "current_resources_target_failed",
  "stats": {
    "target_achievement": {
      "business_success": false,
      "target_status": "current_resources_target_failed",
      "solver_status": "FEASIBLE",
      "hard_milestone_late_days": 8,
      "fixed_duration_overrun_days": 0
    }
  },
  "scheduled_tasks": []
}
```

规则：

- `scheduled_tasks` 不得因业务失败被清空，除非 CP-SAT 本身没有物理可行排程。
- 页面必须展示当前资源失败原因和可查看排程。
- 若同时存在候选资源结果，当前资源失败结果仍必须可识别。

### 候选资源结果

新增资源分支和固定工期求资源候选必须返回搜索边界与复排结果：

```json
{
  "recommended_resources": {
    "candidate_quantities": {
      "rotary_drill": 2
    },
    "added_quantities": {
      "rotary_drill": 1
    },
    "search_range": [
      {
        "resource_type": "rotary_drill",
        "current_quantity": 1,
        "max_quantity": 3,
        "lower_bound": 1,
        "upper_bound": 3
      }
    ],
    "verification_result_source": "candidate_resources_full_objective",
    "target_achievement": {
      "business_success": true,
      "target_status": "candidate_resources_target_met",
      "hard_milestone_late_days": 0,
      "fixed_duration_overrun_days": 0
    }
  }
}
```

规则：

- 候选资源必须经过完整目标函数复排。
- 候选资源数量不得低于当前默认数量，不得超过最大数量。
- 候选复排目标未达成时，不得展示为推荐成功。

### 最大资源预检结果

固定工期入口最大资源仍未达成目标时，返回：

```json
{
  "schedule_source": "max_resources_target_failed",
  "stats": {
    "target_achievement": {
      "business_success": false,
      "target_status": "max_resources_target_failed",
      "solver_status": "FEASIBLE",
      "hard_milestone_late_days": 3,
      "fixed_duration_overrun_days": 2,
      "failure_reasons": ["hard_milestone_late", "fixed_duration_overrun"]
    }
  }
}
```

规则：

- 前端文案应表达“当前最大资源不满足目标”。
- 不得继续推荐超过最大资源上限的数量。
- 必须展示晚点或超期天数。

### 未确认结果

预算耗尽或 `UNKNOWN` 时，返回：

```json
{
  "schedule_source": "target_unconfirmed",
  "stats": {
    "target_achievement": {
      "business_success": false,
      "target_status": "unconfirmed",
      "solver_status": "UNKNOWN",
      "hard_milestone_late_days": 0,
      "fixed_duration_overrun_days": 0,
      "failure_reasons": ["unconfirmed", "time_budget_exhausted"],
      "time_budget_seconds": 15,
      "time_budget_exhausted": true
    }
  }
}
```

规则：

- 前端不得显示“无解”。
- 前端不得显示“最大资源不满足目标”。
- 前端应显示“限时内无法确认”或等价业务文案。

## 前端展示契约

- 主入口文案不再把“精排/粗排”作为核心结果分类。
- 结果页必须同时显示求解器状态和业务目标达成状态。
- 当前资源失败、候选资源成功、候选资源失败、最大资源不满足、限时未确认必须使用不同状态。
- 硬里程碑晚点天数和固定工期超期天数必须分开展示。
- 旧结果缺少 `target_achievement` 时，前端可以按旧字段兼容展示，但不得把旧口径结果误标为新目标达成成功。

## 兼容规则

- 旧 `schedule_source` 可保留，但新字段优先。
- 旧目标配置缺少 `10000000000` 权重时，后端按本期默认补齐。
- 旧结果没有固定工期超期字段时，前端展示为未评估，而不是 0。
- Netlify 演示接口无法提供完整字段时，必须隐藏冲突的目标达成结论或显示能力受限。

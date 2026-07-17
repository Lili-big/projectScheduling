# 接口契约：AI 方案严格固定资源单次求解

## `POST /api/ai-resource-assistant/solve-plan`

**用途**：严格按一个 AI 资源方案当前数量执行一次完整目标排程；不生成比较、推荐解释或新增资源候选。

### 请求

继续使用 `ResourceAssistantSingleSolveRequest`，外形不变：

```json
{
  "scenario": { "...": "沿用 ScenarioInput" },
  "resource_plan": {
    "scenario_id": "ai-resource-balanced",
    "profile": "balanced",
    "resource_pools": [
      { "type": "rotary_drill", "quantity": 4, "max_quantity": 8, "enabled": true }
    ]
  }
}
```

`quantity` 是本次求解唯一数量来源；`max_quantity` 只保留为场景配置信息，不得进入本次资源展开或搜索。

### 成功响应

继续使用 `ResourceAssistantSingleSolveResponse`，在 `plan_result` 增加向后兼容字段：

```json
{
  "resource_plan": {
    "scenario_id": "ai-resource-balanced",
    "solve_status": "feasible"
  },
  "plan_result": {
    "scenario_id": "ai-resource-balanced",
    "plan_status": "unconfirmed",
    "solver_status": "FEASIBLE",
    "input_resource_quantities": {
      "rotary_drill": 4,
      "manual_excavation": 0
    },
    "resource_expansion_attempted": false,
    "generated": { "...": "命名资源和任务图" },
    "result": {
      "status": "FEASIBLE",
      "tasks": [],
      "milestone_results": [],
      "stats": {
        "solver_call_count": 1,
        "performance_path": "ai_strict_fixed_resource_one_pass",
        "baseline_status": "not_evaluated",
        "target_achievement": {
          "business_success": false,
          "target_status": "unconfirmed",
          "solver_status": "FEASIBLE",
          "target_present": true,
          "has_schedule": true,
          "optimality_proven": false,
          "hard_milestone_late_days": 12,
          "fixed_duration_overrun_days": 0,
          "failure_reasons": ["hard_milestone_late", "optimality_unproven"],
          "evaluated_at_source": "ai_strict_fixed_resources"
        }
      }
    },
    "metrics": { "target_status": "unconfirmed" },
    "diagnostics": [],
    "generated_at": "2026-07-13T10:00:00+08:00",
    "input_fingerprint": "..."
  },
  "diagnostics": []
}
```

### 状态契约

| plan_status | 必须保留排程 | 推荐资格 | 说明 |
|---|---|---|---|
| `met` | 是 | 有 | 目标已满足；`OPTIMAL` 或 `FEASIBLE` 均可 |
| `not_met` | 是 | 无 | `OPTIMAL` 且目标延期 |
| `unconfirmed` | 有 incumbent 时保留 | 无 | `FEASIBLE` 且延期、`UNKNOWN` 或缺少目标 |
| `infeasible` | 通常无 | 无 | 资源覆盖错误或已证明物理不可行 |

### 技术失败

- 请求结构、负数量或非法资源数据由现有请求校验返回 422。
- 模型构建错误、运行环境缺少求解能力或未捕获异常不转换成 `infeasible`；页面按单方案请求失败处理并允许重试。
- 技术失败不得沿用上一轮 `plan_status`、排程或延期数据。

## `POST /api/ai-resource-assistant/batch-solve`

保留兼容。若被调用，每个方案必须独立应用同一严格固定资源规则；不得在批量编排中调用通用自动增配流程。页面仍以逐方案 `solve-plan` 为主。

## `POST /api/ai-resource-assistant/compare-results`

不运行 CP-SAT。对比列和指标行增加或使用 `plan_status`，允许展示四种业务结果及延期信息。

## `POST /api/ai-resource-assistant/generate-recommendation`

不运行 CP-SAT。候选集只包含 `plan_status=met` 的方案：

- 至少一个 `met`：沿用现有确定性评分，在 `met` 集合内选择。
- 没有 `met`：`recommended_scenario_id=null`，返回 `insufficient_results` 或等价的“暂无满足目标方案”状态。
- LLM 继续只解释后端确定性结论，不得将其他状态方案加入候选集。

## 兼容性

- 不修改 `ResourceAssistantSingleSolveRequest`。
- 新响应字段为附加字段，旧客户端可忽略。
- `metrics.target_status` 在 AI 新结果中归一为四种业务状态；历史结果读取可保留兼容映射。
- 通用 `POST /api/solve-scenario` 的资源增量候选和 `alternative_results` 行为不变。

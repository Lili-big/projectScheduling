# 接口契约：AI 固定资源两阶段 60 秒预算

## 1. 接口范围

保持现有接口及请求结构：

- `POST /api/ai-resource-assistant/solve-plan`
- `POST /api/ai-resource-assistant/batch-solve`

请求继续提交当前 `scenario` 和 `resource_plan`。不新增用户可传的阶段时限、权重或连续性参数。

## 2. 新求解响应口径

`ResourceAssistantPlanResult.optimization_stages` 结构不变。实施后的默认 AI 单方案响应示例：

```json
{
  "optimization_stages": {
    "primary": {
      "attempted": true,
      "solver_status": "OPTIMAL",
      "max_target_delay_days": 0,
      "makespan_days": 579,
      "optimality_proven": true,
      "elapsed_seconds": 18.6,
      "configured_budget_seconds": 60.0
    },
    "secondary": {
      "attempted": true,
      "solver_status": "FEASIBLE",
      "resource_idle_days": 900,
      "continuity_penalty": 420,
      "optimality_proven": false,
      "elapsed_seconds": 39.8,
      "configured_budget_seconds": 40.1,
      "skipped_reason": null,
      "validation_failure_reason": null
    },
    "selected_stage": "secondary",
    "fallback_reason": null,
    "total_budget_seconds": 60.0,
    "total_elapsed_seconds": 59.2
  }
}
```

示例数字只说明字段关系，不构成固定求解结果。必须满足：

- `primary.configured_budget_seconds=60.0`；
- `secondary.configured_budget_seconds` 来自第一阶段结束后的剩余预算，并扣除现有模型构建预留；
- `optimization_stages.total_budget_seconds=60.0`；
- 不得出现两个阶段各配置 60.0 秒。

## 3. 现有字段语义保持不变

- `solver_status`：最终选中排程对应阶段的原始状态。
- `schedule_outcome_status` / `schedule_outcome_reason`：继续表达工期三态及原因。
- `plan_status`：继续作为历史四状态兼容字段。
- `input_resource_quantities`：两个阶段共同使用的固定资源快照。
- `resource_expansion_attempted`：固定为 `false`。
- `result.stats.solver_call_count`：第二阶段启动时为 2，否则为 1。
- `result.stats.performance_path`：继续为 `ai_strict_fixed_resource_two_stage`。

## 4. 批量与单方案边界

- `solve-plan` 的每次请求获得一份 60 秒预算。
- `batch-solve` 内每个方案分别按现有流程获得 60 秒预算，不把三案合并为一份 60 秒预算。
- 接口端到端响应可以包含模型构建、结果诊断和序列化开销，不能把 `total_elapsed_seconds` 机械解释为 HTTP 超时。

## 5. 错误与兼容

- 第一阶段无排程、第二阶段未启动、超时、失败、越界或无严格改善时，状态码、诊断和回退行为保持现有实现。
- 历史结果中的 30 秒值继续原样读取，不迁移。
- 旧前端忽略阶段摘要时仍可展示原有工期状态、指标和排程详情。
- LLM 调用超时与非 AI 求解入口不属于本契约变更。

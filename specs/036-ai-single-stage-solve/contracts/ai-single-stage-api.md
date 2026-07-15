# 接口契约：AI 固定资源单阶段求解

## 1. 接口范围

保持现有接口路径和请求不变：

- `POST /api/ai-resource-assistant/solve-plan`
- `POST /api/ai-resource-assistant/batch-solve`
- `POST /api/ai-resource-assistant/compare-results`
- `POST /api/ai-resource-assistant/generate-recommendation`

不新增阶段开关、权重或时限字段。

## 2. 新结果阶段摘要

```json
{
  "optimization_stages": {
    "primary": {
      "attempted": true,
      "solver_status": "FEASIBLE",
      "max_target_delay_days": 0,
      "makespan_days": 887,
      "optimality_proven": false,
      "elapsed_seconds": 60.0,
      "configured_budget_seconds": 60.0
    },
    "secondary": {
      "attempted": false,
      "solver_status": null,
      "resource_idle_days": null,
      "continuity_penalty": null,
      "optimality_proven": false,
      "elapsed_seconds": 0.0,
      "configured_budget_seconds": 0.0,
      "skipped_reason": "not_applicable",
      "validation_failure_reason": null
    },
    "selected_stage": "primary",
    "fallback_reason": null,
    "total_budget_seconds": 60.0,
    "total_elapsed_seconds": 60.0
  }
}
```

## 3. 结果事实

- `solver_call_count=1`。
- `performance_path=ai_strict_fixed_resource_single_stage`。
- `resource_expansion_attempted=false`。
- 工期状态、最大延期、任务和资源分配直接来自唯一阶段。
- 资源空闲和连续性仍位于现有统计/指标字段中，仅供诊断。

## 4. 历史兼容

- 不删除任何现有阶段字段或原因枚举。
- 历史 `selected_stage=secondary` 继续可解析。
- 历史结果缺少阶段摘要时继续走既有兼容分支。
- 不修改状态码、请求校验或错误响应结构。

## 5. 页面契约

- 新结果只显示工期排程说明。
- 新结果不显示“第二阶段未执行”或“资源空闲回退”。
- 历史结果实际包含第二阶段执行事实时，可继续显示历史阶段详情。
- 顶部说明统一为单阶段固定资源求解，最长 60 秒。

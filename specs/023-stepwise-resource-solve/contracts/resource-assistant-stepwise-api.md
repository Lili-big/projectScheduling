# 接口契约：资源助手分步求解

## `POST /api/ai-resource-assistant/solve-plan`

**用途**：只求解一个资源方案；不生成比较或推荐解释。

**请求**：`ResourceAssistantSingleSolveRequest`

```json
{
  "scenario": { "...": "沿用 ScenarioInput" },
  "resource_plan": { "scenario_id": "ai-resource-balanced", "...": "沿用 ResourceAssistantPlan" }
}
```

**响应**：`ResourceAssistantSingleSolveResponse`

```json
{
  "resource_plan": { "scenario_id": "ai-resource-balanced", "solve_status": "feasible" },
  "plan_result": { "scenario_id": "ai-resource-balanced", "result": {}, "metrics": {}, "diagnostics": [] },
  "diagnostics": []
}
```

## `POST /api/ai-resource-assistant/compare-results`

**用途**：根据已完成方案刷新指标对比；不运行 CP-SAT，不调用 LLM。

**请求**：`ResourceAssistantResultsRequest`，包含 `resource_plans` 和当前 `plan_results`。

**响应**：`ResourceAssistantComparison`。

## `POST /api/ai-resource-assistant/generate-recommendation`

**用途**：在 A/B/C 均完成后生成完整对比、确定性推荐和 LLM/本地解释。

**请求**：`ResourceAssistantResultsRequest`；服务端必须校验恰好包含三个当前方案的结果，缺少时返回 422。

**响应**：`ResourceAssistantRecommendationResponse`，包含 `comparison`、`recommendation` 和 `diagnostics`。

## 兼容性与错误

- 既有 `POST /api/ai-resource-assistant/batch-solve` 保持不变，但资源助手页面不再使用。
- `solve-plan` 内部异常转换为该方案的 `failed` 业务结果，避免覆盖其他方案。
- `generate-recommendation` 的外部 LLM 异常必须回退为本地解释；只有请求字段缺失、方案标识不匹配或未齐三条结果时返回 422。

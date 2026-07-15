# 接口契约：AI 资源方案 30 秒求解预算

## 适用接口

- `POST /api/ai-resource-assistant/solve-plan`
- `POST /api/ai-resource-assistant/batch-solve`（兼容入口，内部复用单方案处理）

## 请求

请求结构保持不变：

- `scenario`：页面当前 `ScenarioInput`。
- `resource_plan` 或 `resource_plans`：LLM 推荐或用户调整后的资源方案。

调用方无需把 30 秒写入请求；AI 资源方案求解流程统一应用专项预算。

## 响应

响应结构保持不变。以下现有字段用于验收：

| 字段 | AI 方案预期值或规则 |
| --- | --- |
| `plan_result.generated.schedule_input.time_limit_seconds` | `30.0` |
| `plan_result.result.stats.configured_time_limit_seconds` | `30.0`，获得排程并进入求解器时 |
| `plan_result.result.stats.target_achievement.time_budget_seconds` | `30.0` |
| `plan_result.result.stats.solver_call_count` | `1` |
| `plan_result.resource_expansion_attempted` | `false` |
| `plan_result.result.stats.resource_expansion_attempted` | `false` |
| `plan_result.input_resource_quantities` | 与方案资源池数量一致 |

## 兼容规则

- 不新增必填字段，不修改状态码和错误结构。
- 求解提前结束时，`wall_time_seconds` 可小于 30 秒。
- 30 秒到期返回 `FEASIBLE` 或 `UNKNOWN` 时，继续使用现有业务状态和原因。
- 资源覆盖失败可在进入完整求解前返回，其实际耗时不要求接近 30 秒。
- 非 AI 求解接口不适用该专项预算。

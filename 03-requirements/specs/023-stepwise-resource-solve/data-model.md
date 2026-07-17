# 数据模型：AI资源助手分步求解与独立推荐

## 单方案求解请求

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `scenario` | `ScenarioInput` | 当前项目场景，沿用现有字段。 |
| `resource_plan` | `ResourceAssistantPlan` | 本次唯一要执行的方案。 |

## 单方案求解响应

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `resource_plan` | `ResourceAssistantPlan` | 更新后的方案状态。 |
| `plan_result` | `ResourceAssistantPlanResult` | 当前方案的最新结果、指标与诊断。 |
| `diagnostics` | `ValidationMessage[]` | 服务级诊断。 |

## 对比请求与响应

请求携带 `resource_plans` 与 `plan_results`。响应为已有的 `ResourceAssistantComparison`，允许只包含已完成结果的指标值；页面列仍固定显示 A/B/C，缺少值按“待求解”展示。

## 推荐请求与响应

请求同样携带完整 `resource_plans` 与三条当前 `plan_results`。响应包含 `comparison` 和 `recommendation`。服务端先计算确定性推荐与证据，再调用 LLM 仅生成解释；失败时返回本地解释。

## 前端状态转换

```text
draft / ready_to_solve / stale
  -> solving
  -> optimal | feasible | infeasible | unknown | model_invalid | failed
```

- “已完成”指已收到单方案业务响应，状态可以是任一终态。
- 资源编辑：目标方案变为 `stale`，移除该方案结果，清空比较和推荐。
- 重新生成或切换场景：清空全部结果、比较和推荐。

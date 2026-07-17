# 接口契约：AI 单方案稳定求解

## 接口

`POST /api/ai-resource-assistant/solve-plan`

## 请求

```json
{
  "scenario": "现有 ScenarioInput",
  "resource_plan": "现有 ResourceAssistantPlan",
  "previous_plan_result": "可选的现有 ResourceAssistantPlanResult"
}
```

兼容规则：

- `previous_plan_result` 缺省或为 `null` 时按首次求解处理。
- 后端不信任客户端关于“同输入”的判断，必须重新计算指纹并验证任务集合。

## 成功响应

继续返回现有 `ResourceAssistantSingleSolveResponse`：

```json
{
  "resource_plan": "求解后的 ResourceAssistantPlan",
  "plan_result": "最终保留的 ResourceAssistantPlanResult",
  "diagnostics": []
}
```

`plan_result.result.stats.stability_selection` 提供稳定性事实：

```json
{
  "previous_result_provided": true,
  "previous_result_eligible": true,
  "previous_result_rejection_reason": null,
  "warm_start_used": true,
  "current_candidate_status": "FEASIBLE",
  "current_candidate_max_target_delay_days": 0,
  "current_candidate_makespan_days": 610,
  "previous_max_target_delay_days": 0,
  "previous_makespan_days": 592,
  "selected_source": "previous_result",
  "selection_reason": "current_worse",
  "solver_call_count": 1,
  "interchangeable_resource_group_count": 4,
  "symmetry_breaking_constraint_count": 29
}
```

## 状态与错误

- HTTP 状态码沿用现有接口。
- 本轮正常返回 `UNKNOWN/INFEASIBLE` 且旧结果有效：响应成功，最终结果为旧结果，稳定性记录保留本轮状态。
- 请求处理抛出接口级异常：沿用现有错误响应，前端恢复请求前的旧结果并提示失败。
- 旧结果指纹不匹配：不报错，忽略旧结果并按首次求解；记录 `previous_result_rejection_reason=input_fingerprint_mismatch`。

## 页面契约

- 请求前保存同方案旧结果，不把它永久删除。
- 求解中不使用旧结果刷新推荐或基准结论。
- 成功后只展示后端最终保留结果。
- `selection_reason=current_worse/current_no_schedule` 时显示“本轮未改善，已保留同输入上次较优排程”。
- `selection_reason=current_improved` 时显示“已基于上次排程继续优化并获得更优结果”。
- 缺少 `stability_selection` 时保持历史展示，不报错。

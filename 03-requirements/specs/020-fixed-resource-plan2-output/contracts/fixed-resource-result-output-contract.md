# 契约：固定资源结果输出

## 适用范围

适用于固定资源模拟求解返回的 `ScenarioSolveResult`。本契约不改变请求输入，不改变求解器硬约束，不新增持久化字段。

## 主结果

`result` 表示方案1当前资源结果。

当当前资源可查看但业务目标未满足时：
- `result.status` 应为可查看排程状态。
- `result.stats.target_achievement.business_success` 应为 `false`。
- `result.stats.target_achievement.target_status` 应表达当前资源目标未满足。
- `result.stats.schedule_source` 或 `result.objective_breakdown.schedule_source` 应表达当前资源目标未满足来源。
- `result.stats.alternative_output_status` 和 `result.objective_breakdown.alternative_output_status` 应存在。

## 候选结果

`alternative_results` 表示方案2及后续候选。本期只要求最多一个新增资源候选。

当新增资源分支形成可展示候选时：
- `alternative_results.length` 应为 `1`。
- `alternative_results[0].role` 应表达新增资源候选角色。
- `result.stats.alternative_output_status` 应为 `output`。
- `result.stats.alternative_output_message` 应说明已输出方案2。

当新增资源分支没有可展示候选时：
- `alternative_results.length` 应为 `0`。
- `result.stats.alternative_output_status` 应为 `not_output`。
- `result.stats.alternative_output_message` 应明确提示方案2未输出。
- `result.stats.alternative_output_reason` 应记录原因类别。

当当前资源目标已满足、当前资源未确认或当前资源物理不可行时：
- `alternative_results.length` 应为 `0`。
- `result.stats.alternative_output_status` 应为 `not_applicable`。
- 页面不应展示方案2未输出提示。

## 前端展示约定

- 方案输出区必须始终能展示方案1当前资源。
- 当 `alternative_output_status=output` 时，展示方案2切换入口。
- 当 `alternative_output_status=not_output` 时，展示用户可见提示，并不展示空方案2切换入口。
- 当 `alternative_output_status=not_applicable` 时，按当前资源成功、未确认或物理不可行状态展示，不追加方案2未输出提示。
- 页面文案应区分“当前资源目标未满足”和“方案2未输出”，避免把新增资源失败误解成当前资源无结果。

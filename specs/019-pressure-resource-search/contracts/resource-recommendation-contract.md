# 契约：资源建议压力搜索诊断

## 适用范围

本契约描述固定资源主入口在进入新增资源分支后，结果中需要补充的压力搜索诊断字段。它不新增独立 API，不改变用户提交的场景输入。

## 输出位置

字段应同时出现在可供前端读取的结果诊断中：

- `ScheduleResult.stats`
- `ScheduleResult.objective_breakdown`

如现有代码只在其中一个位置维护资源建议元数据，实施时需要保持当前前端读取兼容策略。

## 新增或补充字段

### `pressure_search_status`

资源建议压力搜索总体状态。

允许值：
- `not_run`：未进入压力搜索。
- `searching`：压力搜索已执行但未形成最终结论。
- `candidate_verified`：已找到新增资源候选，并通过原始目标完整精排。
- `candidate_failed`：候选出现但完整精排未满足原始目标。
- `same_as_lower_bounds_exhausted`：多轮压力搜索仍返回当前下限。
- `critical_path_floor_reached`：压力目标已达到工艺关键路径理论最短边界。
- `unconfirmed`：求解限时内无法确认。
- `upper_bound_infeasible`：资源上限内不可满足。

### `pressure_search_stop_reason`

压力搜索停止原因。用于解释为什么推荐成功、继续搜索或停止。

示例值：
- `candidate_verified_original_target`
- `candidate_failed_attempt_limit`
- `same_as_lower_bounds_attempt_limit`
- `critical_path_floor_reached`
- `resource_upper_bound_infeasible`
- `solver_unconfirmed`

### `pressure_search_attempts`

压力搜索轮次数组。

每一项包含：

| 字段 | 含义 |
| --- | --- |
| `attempt_index` | 轮次，从 1 开始 |
| `overdue_days` | 用于本轮压缩的超期天数 |
| `original_target_days` | 原始目标工期窗口 |
| `pressure_target_days` | 本轮内部压力目标工期 |
| `pressure_target_date` | 本轮内部压力目标日期 |
| `critical_path_floor_days` | 工艺关键路径理论最短工期边界 |
| `clamped_by_critical_path` | 是否被关键路径边界截断 |
| `search_lower_bounds` | 本轮资源搜索下限 |
| `candidate_quantities` | 本轮容量模型返回数量 |
| `added_quantities` | 相对当前资源的新增数量 |
| `resource_solver_status` | 容量搜索状态 |
| `capacity_verification_status` | 容量结果验证状态 |
| `full_objective_status` | 完整精排状态，未运行时为空 |
| `full_objective_target_status` | 完整精排目标达成状态，未运行时为空 |
| `stop_reason` | 本轮停止或继续原因 |

## 兼容规则

- 现有 `resource_recommendation_status` 仍是页面判断资源建议主状态的首选字段。
- 现有 `recommended_resource_counts` 和 `recommended_resources` 保持含义不变。
- 没有进入新增资源分支时，`pressure_search_status` 可为 `not_run` 或不返回；前端必须兼容缺失。
- 旧结果中没有压力搜索字段时，前端应按现有资源建议展示逻辑工作。

## 成功推荐判定

成功推荐必须同时满足：

1. 至少一个资源池 `added_quantity > 0`。
2. 候选资源完整精排状态为可用排程。
3. 完整精排的 `target_achievement.business_success` 为 `true`。
4. 验证目标是原始业务目标，不是内部压力目标。

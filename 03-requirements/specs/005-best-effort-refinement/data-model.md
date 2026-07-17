# 数据模型：精排失败最佳努力方案

## BestEffortRefinementMetadata

描述最佳努力精排的来源、严格失败原因和目标放松情况。当前实现仅在最少资源候选复排链路中产生 `minimum_resources_best_effort_refinement`；`current_resources_best_effort_refinement` 仅作为历史兼容来源保留，不再由固定资源主链路产生。建议承载在 `ScheduleResult.stats.best_effort_refinement`，并在 `objective_breakdown.best_effort_refinement` 中保留同源摘要，便于前端兼容读取。

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `enabled` | boolean | 是 | 当前主结果是否为最佳努力精排 |
| `schedule_source` | string | 是 | 当前有效值为 `minimum_resources_best_effort_refinement`；`current_resources_best_effort_refinement` 仅用于历史结果兼容 |
| `fallback_from` | string | 是 | 触发最佳努力前的严格精排来源或链路 |
| `strict_refinement_status` | string | 是 | 严格精排返回状态，如 `INFEASIBLE`、`UNKNOWN` |
| `strict_refinement_failure_reason` | string | 是 | 可展示的失败原因 |
| `relaxed_constraints` | RelaxedConstraint[] | 是 | 被放松的目标类约束清单 |
| `target_lateness_days` | number | 否 | 强制里程碑迟延天数汇总 |
| `fixed_duration_overrun_days` | number | 否 | 固定工期超期天数 |
| `best_effort_score` | number | 否 | 最佳努力排序分值 |
| `objective_status` | string | 是 | 放松求解状态，如 `OPTIMAL` 或 `FEASIBLE` |
| `wall_time_seconds` | number | 否 | 最佳努力求解耗时 |

## RelaxedConstraint

描述一个从硬约束转为软目标的目标项。

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `type` | string | 是 | `hard_milestone` 或 `fixed_duration` |
| `id` | string | 否 | 里程碑 ID 或内部目标 ID |
| `name` | string | 是 | 用户可读名称 |
| `target` | string 或 number | 是 | 目标日期或目标工期天数 |
| `actual` | string 或 number | 否 | 实际完成日期或实际工期天数 |
| `lateness_days` | number | 是 | 迟延或超期天数，未迟延为 0 |
| `scope` | string | 否 | 桥梁、工点或任务范围说明 |

## ScheduleResult 扩展口径

本功能优先使用现有 `stats` 和 `objective_breakdown` 承载元数据，避免新增顶层 API 破坏兼容。

### 固定资源目标未满足结果（当前口径）

- `stats.schedule_source = "current_resources_target_failed"`
- `objective_breakdown.schedule_source = "current_resources_target_failed"`
- `stats.target_achievement.business_success = false`
- 结果保留可查看任务、资源分配、硬里程碑晚点或固定工期超期信息，并可进入资源建议分支
- 不输出新的 `stats.best_effort_refinement.enabled = true`

### 最少资源候选最佳努力结果

- `stats.schedule_source = "minimum_resources_best_effort_refinement"`
- `stats.recommended_schedule_source = "minimum_resources_best_effort_refinement"`
- `objective_breakdown.schedule_source = "minimum_resources_best_effort_refinement"`
- `stats.best_effort_refinement.enabled = true`
- 保留候选资源推荐数量、验证状态和候选来源字段

## 状态流转

```text
严格精排成功
  -> 返回严格精排结果

当前资源目标未达成
  -> 返回 current_resources_target_failed，并保留排程与资源建议

最少资源候选严格复排未达成目标 + 最佳努力成功
  -> 返回 minimum_resources_best_effort_refinement

最少资源候选最佳努力失败
  -> 返回 minimum_resources_refinement_fallback 或容量模型已验证候选
```

## 验证规则

- `enabled = true` 时，`schedule_source` 必须是当前有效最佳努力来源 `minimum_resources_best_effort_refinement`，或历史兼容来源。
- `enabled = true` 时，必须存在 `strict_refinement_status` 和 `relaxed_constraints`。
- `hard_milestone` 放松项的 `lateness_days` 必须与里程碑结果中的迟延天数一致。
- `fixed_duration` 放松项的 `lateness_days` 必须等于实际工期超过目标工期的天数。
- 最佳努力结果不得出现资源占用重叠、禁用资源使用或同结构同工序绑定违规。

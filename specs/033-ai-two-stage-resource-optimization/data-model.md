# 数据模型：AI 固定资源两阶段排程优化

## 1. 工期优先阶段摘要 `ResourceAssistantPrimaryStageSummary`

表示第一阶段固定资源工期求解事实。

| 字段 | 类型 | 规则 |
|---|---|---|
| `attempted` | `bool` | 第一阶段固定为 `true` |
| `solver_status` | `OPTIMAL/FEASIBLE/INFEASIBLE/UNKNOWN/MODEL_INVALID` | 原始求解状态 |
| `max_target_delay_days` | `int \| null` | 有排程和目标时不小于 0；缺少目标时为空 |
| `makespan_days` | `int \| null` | 有排程时为正整数 |
| `optimality_proven` | `bool` | 仅第一阶段 `OPTIMAL` 为 `true` |
| `elapsed_seconds` | `float` | 包含第一阶段建模和搜索时间 |
| `configured_budget_seconds` | `float` | 第一阶段启动时可使用的最大预算 |

## 2. 资源组织阶段摘要 `ResourceAssistantSecondaryStageSummary`

表示第二阶段是否启动及资源组织改进事实。

| 字段 | 类型 | 规则 |
|---|---|---|
| `attempted` | `bool` | 剩余预算足够且第一阶段有排程时为 `true` |
| `solver_status` | 求解状态或 `null` | 未启动时为空 |
| `resource_idle_days` | `int \| null` | 第二阶段有排程时不小于 0 |
| `continuity_penalty` | `int \| null` | 与页面转场罚分一致，不小于 0 |
| `optimality_proven` | `bool` | 仅第二阶段 `OPTIMAL` 为 `true` |
| `elapsed_seconds` | `float` | 未启动时为 0 |
| `configured_budget_seconds` | `float` | 第二阶段启动时的剩余预算 |
| `skipped_reason` | 枚举或 `null` | `primary_no_schedule/time_budget_exhausted/insufficient_remaining_budget/not_applicable` |
| `validation_failure_reason` | 枚举或 `null` | `primary_bounds_exceeded/resource_snapshot_changed/task_set_changed/no_secondary_improvement/model_error` |

## 3. 两阶段选择摘要 `ResourceAssistantOptimizationStages`

| 字段 | 类型 | 规则 |
|---|---|---|
| `primary` | `ResourceAssistantPrimaryStageSummary` | 必填 |
| `secondary` | `ResourceAssistantSecondaryStageSummary` | 必填，即使未启动也返回摘要 |
| `selected_stage` | `primary/secondary` | 默认 `primary`；只有第二阶段通过全部校验且严格改善时为 `secondary` |
| `fallback_reason` | `string \| null` | 选择第一阶段且第二阶段启动过时说明原因 |
| `total_budget_seconds` | `float` | AI 单方案固定为 30 秒 |
| `total_elapsed_seconds` | `float` | 两阶段实际总耗时 |

`ResourceAssistantPlanResult.optimization_stages` 为可选字段。历史结果没有该字段时继续使用现有状态字段。

## 4. 第一阶段目标实体

### 最大目标延期

```text
max_target_delay_days = max(
  所有强制里程碑 lateness_days,
  fixed_duration_overrun_days
)
```

- 无延期时为 0。
- 缺少任何可评估目标时为空，第一阶段只比较总工期。
- 不替代现有逐里程碑明细、强制里程碑累计延期和固定工期超期字段。

### 第一阶段状态转换

```text
未启动 -> 求解中 -> OPTIMAL / FEASIBLE / INFEASIBLE / UNKNOWN / MODEL_INVALID
```

第一阶段无 `OPTIMAL/FEASIBLE` 排程时，第二阶段固定为未启动。

## 5. 第二阶段次目标实体

### 累计资源空闲

单台已使用资源：

```text
idle_days = last_finish - first_start - assigned_workload
```

累计值为所有已使用命名资源之和。未使用资源为 0。

### 资源连续性罚分

```text
continuity_penalty =
  jump_pier_count * 4
  + side_switch_count * 2
  + cross_side_jump_count * 6
  + path_group_switch_count
```

缺失空间信息的转移不计空间分项；可判定的路径组切换仍可计分。

### 第二阶段采用规则

第二阶段必须同时满足：

1. 状态为 `OPTIMAL` 或 `FEASIBLE`；
2. 最大延期不超过第一阶段；
3. 总工期不超过第一阶段；
4. 输入资源类型和数量与第一阶段完全一致；
5. 任务 ID 集合完整且一致；
6. 次目标向量 `(resource_idle_days, continuity_penalty)` 严格优于第一阶段诊断向量。

否则 `selected_stage=primary`。

## 6. 工期状态与阶段状态关系

- `schedule_outcome_status` 仍只有 `duration_target_met`、`duration_target_not_met`、`no_feasible_schedule`。
- “是否证明工期最优/延期”读取第一阶段 `solver_status` 和最大延期事实。
- “资源组织是否证明最优”读取第二阶段状态。
- 第二阶段 `FEASIBLE` 不得把第一阶段 `OPTIMAL` 的工期证明降级。
- 最终排程仍需重新计算里程碑延期和总工期，作为选择校验而非新的业务状态来源。

# 数据模型：AI 第二阶段仅优化资源空闲

## 1. 第一阶段排程摘要

继续使用现有第一阶段摘要，字段和语义不变：

| 字段 | 规则 |
|---|---|
| `solver_status` | 第一阶段原始求解状态 |
| `max_target_delay_days` | 第二阶段不可恶化上限 |
| `makespan_days` | 第二阶段不可恶化上限 |
| `optimality_proven` | 仅第一阶段 `OPTIMAL` 为真 |
| `elapsed_seconds` | 第一阶段实际耗时 |
| `configured_budget_seconds` | 第一阶段可用预算 |

第一阶段无可行排程时，第二阶段不启动。

## 2. 第二阶段排程摘要

继续使用现有 `ResourceAssistantSecondaryStageSummary`，不新增必填字段。

| 字段 | 本功能后的语义 |
|---|---|
| `attempted` | 第一阶段有排程、空闲大于 0 且剩余预算足够时为真 |
| `solver_status` | 第二阶段资源空闲求解状态 |
| `resource_idle_days` | 唯一第二阶段优化指标 |
| `continuity_penalty` | 求解后诊断值，不参与优化或采用判断 |
| `optimality_proven` | 仅表示资源空闲目标是否证明最优 |
| `skipped_reason` | 未启动原因，包括第一阶段无排程、预算不足或空闲已为 0；空闲为 0 使用 `idle_already_zero` |
| `validation_failure_reason` | 无排程、工期越界、任务/资源变化或空闲无严格改善 |

## 3. 累计资源空闲

单台已使用资源：

```text
idle_days = last_end - first_start - assigned_workload
```

全方案：

```text
total_resource_idle_days = sum(所有已使用命名资源的 idle_days)
```

规则：

- 未使用资源记 0；
- 首项任务前和末项任务后的等待不计入；
- 值域为非负整数；
- 第一阶段值为第二阶段严格改善基线。

## 4. 第二阶段目标与边界

目标：

```text
minimize(total_resource_idle_days)
```

硬边界：

```text
secondary.max_target_delay_days <= primary.max_target_delay_days
secondary.makespan_days <= primary.makespan_days
secondary.resource_idle_days <= primary.resource_idle_days - 1
```

当 `primary.resource_idle_days == 0` 时不启动第二阶段。

## 5. 资源路径连续性诊断

以下指标继续从最终排程派生：

- `jump_pier_count`
- `side_switch_count`
- `cross_side_jump_count`
- `direction_reversal_count`
- `path_group_switch_count`
- `continuity_score`
- `continuity_penalty`

这些字段不再影响第二阶段模型、结果采用、工期三态或推荐。

## 6. 阶段状态转换

```text
第一阶段无排程 -> 第二阶段未启动 -> 返回第一阶段诊断
第一阶段空闲为 0 -> `skipped_reason=idle_already_zero` -> 第二阶段未启动 -> 返回第一阶段排程
第一阶段有排程且有剩余预算 -> 第二阶段求解
第二阶段空闲严格下降且边界通过 -> 采用第二阶段
第二阶段空闲未下降或其他校验失败 -> 回退第一阶段
```

## 7. 历史兼容

- 历史 `optimization_stages` 中的 `continuity_penalty` 继续可读。
- 历史 `no_secondary_improvement` 继续可解析；新页面统一解释为当前目标未严格改善。
- `secondary.skipped_reason` 新增 `idle_already_zero`，不删除或重命名任何历史枚举值。
- 不迁移或重写基准计划版本。
- 工期三态和 `plan_status` 兼容字段不变。

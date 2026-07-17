# 数据模型：AI 方案状态三态化与最大延期口径优化

## 1. 三态主状态

`ResourceAssistantScheduleOutcomeStatus`：

| 值 | 中文显示 | 含义 |
|---|---|---|
| `duration_target_met` | 工期目标已满足 | 已有排程、有目标且最大延期为 0 |
| `duration_target_not_met` | 工期目标未满足 | 已有排程、有目标且最大延期大于 0 |
| `no_feasible_schedule` | 当前资源未获得可行排程 | 当前没有可用排程 |

字段可为空；为空仅用于技术失败或 `target_missing`，不构成第四种正常业务状态。

## 2. 状态原因

`ResourceAssistantScheduleOutcomeReason`：

| 值 | 主状态 | 规则 |
|---|---|---|
| `target_met` | `duration_target_met` | 所有可评估目标无延期 |
| `proven_late` | `duration_target_not_met` | `OPTIMAL` 且存在延期 |
| `late_unconfirmed` | `duration_target_not_met` | `FEASIBLE` 且存在延期 |
| `time_limit_no_schedule` | `no_feasible_schedule` | `UNKNOWN` 且无排程 |
| `proven_infeasible` | `no_feasible_schedule` | 求解器证明不可行 |
| `resource_coverage_missing` | `no_feasible_schedule` | 有效任务缺少兼容资源或数量为 0 |
| `target_missing` | 空 | 有排程但没有可评估工期目标 |

## 3. 目标评估字段

现有 `TargetAchievement` 增加：

| 字段 | 类型 | 规则 |
|---|---|---|
| `schedule_outcome_status` | 三态或空 | 新用户可见主状态 |
| `schedule_outcome_reason` | 原因或空 | 解释证明状态与失败来源 |
| `max_target_delay_days` | 非负整数 | 强制里程碑单项延期与固定总工期超期的最大值 |

继续保留：

| 字段 | 语义 |
|---|---|
| `target_status` | 旧四状态兼容值 |
| `hard_milestone_late_days` | 所有强制里程碑延期合计 |
| `fixed_duration_overrun_days` | 固定总工期超期 |
| `target_present` | 是否有可评估强制目标 |
| `has_schedule` | 是否有排程任务 |
| `optimality_proven` | 是否已证明最优 |

## 4. 方案结果

`ResourceAssistantPlanResult` 增加默认可空字段：

| 字段 | 类型 | 说明 |
|---|---|---|
| `schedule_outcome_status` | 三态或空 | 与 `TargetAchievement` 一致 |
| `schedule_outcome_reason` | 原因或空 | 与 `TargetAchievement` 一致 |

旧 `plan_status`、`solver_status`、排程结果和诊断不删除。

## 5. 映射矩阵

| solver_status | 有排程 | 有目标 | 最大延期 | 新主状态 | 原因 |
|---|---:|---:|---:|---|---|
| `OPTIMAL` / `FEASIBLE` | 是 | 是 | 0 | `duration_target_met` | `target_met` |
| `OPTIMAL` | 是 | 是 | >0 | `duration_target_not_met` | `proven_late` |
| `FEASIBLE` | 是 | 是 | >0 | `duration_target_not_met` | `late_unconfirmed` |
| `UNKNOWN` | 否 | 任意 | 不适用 | `no_feasible_schedule` | `time_limit_no_schedule` |
| `INFEASIBLE` | 否 | 任意 | 不适用 | `no_feasible_schedule` | `proven_infeasible` 或 `resource_coverage_missing` |
| `OPTIMAL` / `FEASIBLE` | 是 | 否 | 不适用 | 空 | `target_missing` |
| 技术失败 | 任意 | 任意 | 不适用 | 空 | 空 |

## 6. 历史回退

历史结果缺少新字段时：

```text
met -> duration_target_met / target_met
not_met -> duration_target_not_met / proven_late
unconfirmed + 有排程 + 有目标 -> duration_target_not_met / late_unconfirmed
unconfirmed + 无排程 -> no_feasible_schedule / time_limit_no_schedule
unconfirmed + 目标缺失 -> 空 / target_missing
infeasible -> no_feasible_schedule / proven_infeasible
```

映射只在内存和展示中完成，不写回历史快照。

## 7. 状态生命周期

```text
方案待求解
  -> 求解成功 -> 三态或目标缺失
  -> 技术失败 -> 三态为空

资源或项目变化
  -> 旧结果、三态、最大延期、对比和推荐全部失效

重新求解
  -> 使用本次结果重新计算全部字段
```

# 数据模型：进度锁定重排三步闭环

## 1. 兼容原则

- 复用 `PlanVersion`、`ProgressSnapshot`、`ForecastSchedule`、`ForecastTaskState` 和 `AdjustmentProposal`。
- 新增字段均提供默认值，历史 `plan-control/v1` 文件无需迁移。
- 页面步骤状态为派生展示状态，不写入持久化文件。

## 2. ProgressWorkflowStep（前端派生）

表示三步闭环中某一步的当前状态。

| 字段 | 类型 | 说明 |
|---|---|---|
| `step` | `progress` / `reschedule` / `warning` | 步骤标识 |
| `status` | `blocked` / `ready` / `running` / `complete` / `failed` / `stale` | 展示状态 |
| `title` | string | 业务名称 |
| `message` | string | 当前状态和下一步说明 |
| `reference_id` | string / null | 快照或预测标识，仅用于追溯 |

### 状态转换

```text
无活动计划 → progress.blocked
活动计划 + 未保存输入 → progress.ready
保存成功 → progress.complete + reschedule.ready
进度编辑未保存 → reschedule.stale + warning.stale
重排成功 → reschedule.complete + warning.complete
重排无可行结果 → reschedule.failed + warning.blocked/insufficient
快照修订或计划切换 → 旧预测 stale
```

## 3. ProgressEntryIssue（前端派生）

用于保存前行级校验，不进入持久化。

| 字段 | 类型 | 说明 |
|---|---|---|
| `task_id` | string | 稳定任务标识 |
| `field` | string / null | 可定位字段；跨字段问题可为空 |
| `severity` | `error` / `warning` | 阻断或提示 |
| `code` | string | 稳定错误码 |
| `message` | string | 中文业务提示 |

主要规则：实际日期不得晚于状态日期；完成不得早于开始；五类状态执行各自必填规则；工程量、比例和剩余工期保持一致；暂停任务缺少恢复日期时记录警告而不是拒绝现场事实。

## 4. ForecastTaskExecutionState（新增枚举）

| 值 | 业务含义 |
|---|---|
| `completed_locked` | 已完成，实际日期锁定，不进入剩余求解 |
| `cancelled_excluded` | 已取消，不进入剩余求解，但依赖影响必须诊断 |
| `in_progress_remaining` | 进行中，保留实际开始与原资源，只排剩余工作 |
| `paused_remaining` | 暂停，保留原资源并遵守恢复条件 |
| `not_started_future` | 未开始，在状态日期后按当前趋势安排 |

## 5. ForecastTaskState（扩展）

保留现有日期和资源类型字段，新增：

| 字段 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `progress_status` | `ProgressTaskStatus` / null | null | 生成预测时的进度状态 |
| `execution_state` | `ForecastTaskExecutionState` / null | null | 锁定或重排策略 |
| `assigned_resource_id` | string / null | null | 实际锁定或预测分配的命名资源 |
| `remaining_days` | int / null | null | 进入预测的剩余工期 |
| `related_diagnostics` | string[] | [] | 取消、暂停或数据质量诊断 |

## 6. ForecastExecutionSummary（新增）

| 字段 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `completed_locked_count` | int | 0 | 已完成锁定数量 |
| `cancelled_excluded_count` | int | 0 | 已取消数量 |
| `in_progress_remaining_count` | int | 0 | 进行中剩余段数量 |
| `paused_remaining_count` | int | 0 | 暂停剩余段数量 |
| `not_started_future_count` | int | 0 | 未开始未来任务数量 |
| `resource_policy` | string | `baseline_fixed` | 当前趋势资源口径 |
| `sequence_policy` | string | `baseline_order` | 当前趋势顺序口径 |

## 7. CriticalNodeEvidence（新增）

| 字段 | 类型 | 说明 |
|---|---|---|
| `type` | `driving_task` / `bottleneck_resource` / `precedence_wait` / `data_quality` / `solver` | 证据类型 |
| `message` | string | 业务说明 |
| `task_ids` | string[] | 关联任务，可为空 |
| `resource_types` | string[] | 关联资源类型，可为空 |
| `variance_days` | int / null | 证据相关偏差 |

## 8. CriticalNodeForecast（新增）

| 字段 | 类型 | 说明 |
|---|---|---|
| `node_id` | string | `project-finish` 或里程碑 ID |
| `name` | string | 项目完工或里程碑名称 |
| `node_type` | `project_finish` / `milestone` | 节点类型 |
| `level` | string / null | 里程碑级别 |
| `mode` | string / null | 强制或软性口径 |
| `target_date` | date | 目标日期；项目完工使用活动计划基准完成日期，里程碑使用配置目标日期 |
| `evaluated_date` | date / null | 实际或预测得到的节点日期 |
| `date_source` | `actual` / `predicted` / `combined` / `unavailable` | 日期来源 |
| `variance_days` | int / null | `evaluated_date - target_date`；正数为延期 |
| `buffer_days` | int / null | `target_date - evaluated_date`；正数为缓冲 |
| `status` | `on_track` / `at_risk` / `late` / `insufficient_data` | 节点状态 |
| `related_task_ids` | string[] | 节点范围任务 |
| `evidence` | `CriticalNodeEvidence[]` | 确定性原因证据 |

### 节点状态规则

- `evaluated_date` 不可得：`insufficient_data`。
- `variance_days > 0`：`late`。
- `variance_days` 为 `-3` 至 `0`：`at_risk`。
- `variance_days < -3`：`on_track`。

节点范围全部完成时使用实际日期；全部未完成时使用预测日期；同时包含两类任务时使用合并日期并标记 `combined`。

## 9. ForecastSchedule（扩展）

| 字段 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `execution_summary` | `ForecastExecutionSummary` | 空计数对象 | 锁定与重排摘要 |
| `critical_nodes` | `CriticalNodeForecast[]` | [] | 结构化关键节点结果 |

现有 `risk_status`、`risk_evidence`、`confidence`、`metrics` 和 `diagnostics` 保留。项目级 `risk_status` 应由 `critical_nodes` 和求解状态汇总，确保摘要与明细一致。

## 10. 关系与唯一性

- 一个 `ForecastSchedule` 仍唯一关联一个 `PlanVersion` 和一个当前 `ProgressSnapshot`。
- 一个预测包含一份 `ForecastExecutionSummary`、多个 `ForecastTaskState` 和多个 `CriticalNodeForecast`。
- `CriticalNodeForecast.node_id` 在单个预测内唯一；项目完工节点固定使用 `project-finish`。
- 快照修订或活动计划变化后，相关预测继续使用现有 `stale` 生命周期。

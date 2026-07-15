# 数据模型：基准计划、进度反馈与滚动预测

## 1. PlanVersion

| 字段 | 类型 | 说明 |
|---|---|---|
| `plan_version_id` | string | 稳定唯一 ID |
| `project_id` / `project_name` | string | 项目归属 |
| `plan_type` | enum | MVP 固定 `master` |
| `version_no` | integer | 项目内递增版本号 |
| `version_kind` | enum | `baseline`、`execution` |
| `status` | enum | `draft`、`active`、`superseded` |
| `parent_version_id` | string/null | 新执行版本的父版本 |
| `source_scenario_id` | string | 来源资源方案 |
| `scenario_snapshot` | ScenarioInput | 项目与规则快照 |
| `generated_snapshot` | GeneratedScheduleInput | 任务和逻辑快照 |
| `schedule_result_snapshot` | ScheduleResult | 求解结果快照 |
| `resource_plan_snapshot` | ResourceAssistantPlan | 资源方案快照 |
| `input_fingerprint` | string | 来源输入指纹 |
| `confirmed_by` / `confirmed_at` | string/datetime | 确认信息 |
| `confirmation_reason` | string | 选择或采用原因 |

### 状态转换

```text
draft → active → superseded
```

激活新版本时，原 `active` 自动转为 `superseded`；历史版本只读。

## 2. TaskExecutionConstraint

| 字段 | 类型 | 说明 |
|---|---|---|
| `task_id` | string | 关联任务 |
| `earliest_start_offset` | integer/null | 最早开始偏移 |
| `fixed_start_offset` | integer/null | 固定开始偏移 |
| `fixed_resource_id` | string/null | 固定物理资源 |
| `source` | string | 约束来源，如 `progress_snapshot` |

校验：固定开始不得早于最早开始；任务和资源必须存在；默认无约束时不改变求解。

## 3. ProgressSnapshot

| 字段 | 类型 | 说明 |
|---|---|---|
| `progress_snapshot_id` | string | 快照 ID |
| `plan_version_id` | string | 关联计划版本 |
| `status_date` | date | 数据截止日期 |
| `revision_no` | integer | 同状态日期修订号 |
| `is_current` | boolean | 是否当前修订 |
| `entries` | ProgressEntry[] | 任务实绩 |
| `data_quality_status` | enum | `valid`、`warning`、`invalid` |
| `submitted_by` / `submitted_at` | string/datetime | 提交信息 |
| `correction_reason` | string/null | 修订原因 |

## 4. ProgressEntry

| 字段 | 类型 | 说明 |
|---|---|---|
| `task_id` | string | 必须存在于计划版本 |
| `status` | enum | `not_started`、`in_progress`、`completed`、`paused`、`cancelled` |
| `actual_start_date` | date/null | 实际开始 |
| `actual_finish_date` | date/null | 实际完成 |
| `percent_complete` | number | 0–100 |
| `completed_quantity` / `remaining_quantity` | number/null | 工程量实绩 |
| `actual_productivity` | number/null | 单位/有效作业日 |
| `estimated_remaining_days` | integer/null | 人工剩余工期 |
| `remaining_days` | integer | 最终采用的剩余工期 |
| `remaining_days_source` | enum | `calculated`、`manual`、`baseline`、`none` |
| `expected_resume_date` | date/null | 暂停任务预计恢复 |
| `reason` | string/null | 暂停或取消原因 |
| `notes` | string | 备注 |

## 5. ProgressCorrectionRecord

保存 `plan_version_id`、状态日期、前后快照 ID、字段级 `old_value/new_value`、更正原因、更正人和时间。

## 6. ForecastSchedule

| 字段 | 类型 | 说明 |
|---|---|---|
| `forecast_id` | string | 预测 ID |
| `plan_version_id` / `progress_snapshot_id` | string | 输入版本 |
| `status_date` | date | 预测起点 |
| `strategy` | enum | `as_is` 或调整策略 |
| `status` | enum | `ready`、`solving`、`feasible`、`infeasible`、`failed`、`stale` |
| `input_fingerprint` | string | 输入指纹 |
| `historical_tasks` | ForecastTaskState[] | 冻结实际 |
| `predicted_tasks` | ForecastTaskState[] | 剩余预测 |
| `schedule_result` | ScheduleResult/null | 残余求解结果 |
| `risk_status` | enum | `on_track`、`at_risk`、`late`、`insufficient_data` |
| `risk_evidence` | list | 任务、里程碑、资源和数据证据 |
| `confidence` | enum | `high`、`medium`、`low` |
| `metrics` | object | 工期、里程碑、资源、成本、等待、转场 |
| `created_at` | datetime | 生成时间 |

## 7. AdjustmentProposal

关联一个 `as_is` 预测，策略仅限 `as_is`、`add_bottleneck_resources`、`prioritize_critical_tasks`；保存策略参数、独立求解状态、指标、诊断、推荐标识和解释。

## 8. PlanChangeRecord

保存来源版本、来源预测、采用方案、新版本、采用原因、确认人和确认时间。

## 9. PlanControlStore

顶层包含 `schema_version`、`plan_versions`、`progress_snapshots`、`correction_records`、`forecasts`、`adjustment_proposals`、`plan_change_records`。写入前整体校验，写入采用临时文件替换；损坏文件返回服务不可用，不静默清空历史。

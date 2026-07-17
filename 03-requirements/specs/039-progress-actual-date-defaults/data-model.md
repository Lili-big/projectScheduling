# 数据模型：实际进度日期默认赋值

## 1. 既有权威实体（字段不变）

### PlanVersion

- `schedule_result_snapshot.tasks[]`：活动执行计划的已求解任务快照。
- 关联键：`ScheduledTask.id == ProgressEntry.task_id`。
- 本功能使用字段：`id`、`start_date`、`finish_date`。
- 约束：只读，不重算、不修改、不写回。

### ProgressEntry

- `task_id`：任务标识。
- `status`：`not_started | in_progress | completed | paused | cancelled`。
- `actual_start_date`、`actual_finish_date`：可空 ISO 本地日期字符串。
- 其他工程量、工效和备注字段保持现有语义。
- 约束：本功能不新增来源字段；保存后仍由后端归一化和校验。

### ProgressSnapshot

- `status_date`：本次进度数据截止日期。
- `entries[]`：经用户确认和后端校验后的实际事实。
- 约束：历史加载时不自动补日期；同日修订和审计规则不变。

## 2. 新增前端会话实体

### PlannedTaskDates

| 字段 | 类型 | 来源 | 说明 |
|---|---|---|---|
| `taskId` | `string` | `ScheduledTask.id` | 任务关联键 |
| `plannedStartDate` | `string` | `ScheduledTask.start_date` | 计划开始 |
| `plannedFinishDate` | `string` | `ScheduledTask.finish_date` | 计划完成 |

校验：两项均需是可比较的 `YYYY-MM-DD`；缺失、格式无效或完成早于开始时，不生成建议并显示计划日期不可用提示。

### ActualDateSuggestionState

按 `task_id` 存储，字段如下：

| 字段 | 类型 | 说明 |
|---|---|---|
| `actualStartSuggested` | `boolean` | 当前实际开始仍是本次会话自动建议且未被人工修改 |
| `actualFinishSuggested` | `boolean` | 当前实际完成仍是本次会话自动建议且未被人工修改 |

该实体只存在于 React 状态中，不进入 API、JSON 持久化或历史快照。

## 3. 派生值

### localToday

从浏览器本地 `Date` 的年、月、日生成 `YYYY-MM-DD`，不使用 UTC `toISOString()`。

### cutoff

```text
cutoff = min(statusDate, localToday)
```

状态日期或本地日期无效时不生成建议。

### 默认实际开始

```text
suggestedActualStart = min(plannedStartDate, cutoff)
```

仅当状态需要实际开始、字段为空且计划日期可用时生成。

### 默认实际完成

```text
suggestedActualFinish = max(actualStartDate, min(plannedFinishDate, cutoff))
```

仅已完成状态、字段为空且实际开始及计划日期可用时生成。

## 4. 状态转换

| 目标状态 | 实际开始 | 实际完成 | 建议标记 |
|---|---|---|---|
| `not_started` | 清空 | 清空 | 两项清除 |
| `in_progress` | 空值时建议 | 清空 | 新建议开始为 true；完成清除 |
| `paused` | 空值时建议 | 清空 | 新建议开始为 true；完成清除 |
| `completed` | 空值时建议 | 空值时建议 | 仅新建议字段为 true |
| `cancelled` | 保留已有值，不新增 | 不新增；沿用既有非完成状态清理语义 | 不新增标记 |

补充规则：

- 已有人工或历史值保持不变。
- 用户编辑某个日期（包括主动清空）后，对应建议标记设为 false。
- 从已完成切换到非完成状态时，实际完成及其建议标记清除。
- 状态日期变化时，只重算标记为 true 的字段；人工字段即使变为非法也不覆盖，由保存校验提示。
- 保存成功、服务端快照加载、刷新或项目变化时，全部建议标记清空。

## 5. 后端权威不变量（既有）

- `status_date` 不早于项目开始且不晚于后端系统当前日期。
- `actual_start_date`、`actual_finish_date` 不晚于 `status_date`。
- `actual_finish_date >= actual_start_date`。
- `in_progress` 必须有实际开始且完成比例在 0 与 100 之间。
- `completed` 必须有实际开始、实际完成且完成比例为 100%。
- `paused` 必须有实际开始、原因和人工剩余天数。

## 6. 兼容性

- API 请求与响应字段不变。
- 历史 `ProgressSnapshot` 无需迁移或重写。
- 没有 `ScheduledTask` 对应项或计划日期异常时，继续允许人工填写，后端按既有规则校验。
- 工程量联动、滚动预测、调整方案和 CP-SAT 输入输出不变。

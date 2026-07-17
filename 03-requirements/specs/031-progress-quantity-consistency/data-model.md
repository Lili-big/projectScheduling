# 数据模型：实际进度工程量一致性

## 1. PlanTaskQuantity（只读引用）

该概念不新增持久化实体，引用活动计划版本中已有任务字段。

| 字段 | 来源 | 说明 |
|---|---|---|
| `task_id` | `Task.id` | 与进度项稳定关联 |
| `total_quantity` | `Task.quantity` | 总工程量的唯一计算基准，必须大于 0 才能启用数量联动 |
| `quantity_label` | `Task.quantity_label` | 计划确认时冻结的总工程量展示文本，当前新任务为纯数值和单位 |
| `plan_version_id` | `PlanVersion.plan_version_id` | 说明该总量属于哪个不可变计划版本 |

关系：一个活动 `PlanVersion` 包含多个计划任务；一个 `ProgressEntry` 通过 `task_id` 引用其中一个任务的总工程量。

## 2. ProgressEntry（现有实体，强化不变量）

不新增字段，继续使用现有结构。

| 字段 | 类型 | 本功能语义 |
|---|---|---|
| `task_id` | string | 必须存在于当前计划版本 |
| `status` | enum | `not_started`、`in_progress`、`completed`、`paused`、`cancelled` |
| `percent_complete` | number | 实际完成比例，范围 0–100 |
| `completed_quantity` | number/null | 实际已完工程量；总量有效的新记录中必须可归一 |
| `remaining_quantity` | number/null | 物理剩余工程量；总量有效的新记录中必须等于总量减已完量 |
| `actual_productivity` | number/null | 实际单位工程量/有效作业日 |
| `estimated_remaining_days` | integer/null | 无法按工程量和工效计算或暂停时的人工剩余工期 |
| `remaining_days` | integer | 归一后的排程剩余工期 |
| `remaining_days_source` | enum | `calculated`、`manual`、`baseline`、`none` |
| 其他实际日期、原因、备注字段 | 现有类型 | 继续沿用 Spec 027 规则 |

### 数量不变量

当 `total_quantity > 0`：

```text
completed_quantity = total_quantity × percent_complete / 100
remaining_quantity = total_quantity - completed_quantity
completed_quantity + remaining_quantity = total_quantity
```

范围：

```text
0 ≤ percent_complete ≤ 100
0 ≤ completed_quantity ≤ total_quantity
0 ≤ remaining_quantity ≤ total_quantity
```

新保存请求的三项值必须在允许的浮点容差内满足公式；冲突请求返回校验错误。历史快照不因读取而重新校验写回。

## 3. 状态矩阵

| 状态 | 完成比例 | 已完工程量 | 剩余工程量 | 编辑规则 | 剩余工期 |
|---|---:|---:|---:|---|---|
| `not_started` | 0 | 0 | 总量 | 三项只读自动值 | 基准任务工期 |
| `in_progress` | 大于 0 且小于 100 | 按公式 | 按公式 | 比例或已完量可编辑；剩余量只读 | 剩余量/实际工效向上取整，或人工值 |
| `completed` | 100 | 总量 | 0 | 三项只读自动值 | 0 |
| `paused` | 0–小于 100 | 按公式 | 按公式 | 比例或已完量可编辑；剩余量只读 | 人工值，并保留恢复日期规则 |
| `cancelled` | 0–小于 100 | 按公式 | 按公式 | 保存取消前实绩；必须填写原因 | 0，不进入剩余排程 |

总量无效时：数量字段保持空值，页面禁用数量入口；进行中或暂停任务继续使用有效比例和人工剩余工期兼容路径。

## 4. ProgressQuantityView（前端派生视图）

该视图不持久化，用于把计划任务和进度项合并成一行可展示数据。

| 字段 | 说明 |
|---|---|
| `total_quantity` / `total_quantity_label` | 来自计划任务 |
| `percent_complete` | 当前编辑值或历史值 |
| `completed_quantity` | 当前编辑值；历史缺失时可由比例派生 |
| `remaining_quantity` | 总量减已完量；历史冲突时保留原值并标记警告 |
| `quantity_consistency_status` | `valid`、`derived`、`conflict`、`unavailable`，仅页面使用 |
| `quantity_consistency_message` | 数据来源或冲突说明，仅页面使用 |

## 5. ProgressSnapshot 与修订

- 新快照保存归一后的 `ProgressEntry`，服务响应直接返回同一组值。
- 同一状态日期再次保存仍创建递增 `revision_no`，原快照转为非当前修订。
- 历史缺失或冲突数据在只读加载时不写回；用户更正时必须提供更正原因，并由现有字段级变化记录保存差异。
- 新快照保存后，引用旧快照的滚动预测和调整方案继续变为过期状态。

## 6. 兼容性

- `ProgressEntry` 字段形状、请求路径和响应路径不变，不需要存储 schema 迁移。
- 缺少 `completed_quantity` 或 `remaining_quantity` 的历史 JSON 继续通过可空字段加载。
- 历史 `quantity_label` 只作为原样展示文本，不参与数量计算；所有公式只使用 `Task.quantity`。
- 旧客户端提交不一致的新请求将收到明确校验错误，需要按本契约同步三个进度字段。

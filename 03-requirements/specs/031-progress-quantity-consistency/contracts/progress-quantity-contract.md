# 接口契约：实际进度工程量一致性

## 1. 适用接口

- `GET /api/plan-control/projects/{project_id}`：活动计划任务提供总工程量，当前进度快照提供实绩。
- `POST /api/plan-control/progress-snapshots`：保存并返回归一后的进度快照。
- 现有预测和调整接口路径不变，只消费归一后的当前进度快照。

本功能不新增接口，不改变请求与响应的顶层结构。

## 2. 总工程量来源

客户端必须通过当前活动计划的：

```text
active_plan.generated_snapshot.schedule_input.tasks[].quantity
active_plan.generated_snapshot.schedule_input.tasks[].quantity_label
```

取得总工程量数值和显示文本。`ProgressEntry` 不携带独立总工程量。

## 3. 保存请求语义

请求继续使用现有 `CreateProgressSnapshotRequest`：

```json
{
  "plan_version_id": "plan-example",
  "status_date": "2026-07-13",
  "entries": [
    {
      "task_id": "task-example",
      "status": "in_progress",
      "actual_start_date": "2026-07-10",
      "percent_complete": 40,
      "completed_quantity": 4,
      "remaining_quantity": 6,
      "actual_productivity": 2,
      "estimated_remaining_days": null,
      "remaining_days": 0,
      "remaining_days_source": "none",
      "notes": ""
    }
  ],
  "submitted_by": "本地计划工程师",
  "correction_reason": null,
  "expected_revision_no": null
}
```

对总工程量为 `10` 的任务，上述三项进度值必须一致。服务端不得静默选择某一个冲突字段覆盖其他字段。

## 4. 成功响应

HTTP 200 响应继续使用 `CreateProgressSnapshotResponse`。返回的 `progress_snapshot.entries` 已完成归一，可直接回显：

```json
{
  "progress_snapshot": {
    "entries": [
      {
        "task_id": "task-example",
        "status": "in_progress",
        "percent_complete": 40,
        "completed_quantity": 4,
        "remaining_quantity": 6,
        "actual_productivity": 2,
        "remaining_days": 3,
        "remaining_days_source": "calculated"
      }
    ]
  },
  "stale_forecast_ids": [],
  "diagnostics": []
}
```

未开始和已完成任务由服务端返回对应状态的自动数量；暂停和取消任务保留物理进度数量，并分别使用人工剩余工期或 0 天。

## 5. 校验失败

沿用现有计划管控错误映射，业务校验失败返回 HTTP 422。至少覆盖：

- 已完工程量或剩余工程量为负数；
- 已完工程量或剩余工程量超过计划总工程量；
- 完成比例超出 0–100%；
- 已完量加剩余量不等于总量；
- 比例与已完工程量不一致；
- 总工程量无效但仍提交数量型实绩；
- 状态要求的实际日期、原因或剩余工期缺失。

错误消息必须通过 `task_id` 或请求中的进度项索引定位到具体任务，并说明冲突字段或关系；不得返回凭据或内部堆栈。

## 6. 历史兼容

- GET 响应可包含缺少 `completed_quantity` 或 `remaining_quantity` 的历史进度项；客户端按数据模型派生展示，不据此写回。
- 历史关系冲突时客户端显示质量提示；更正仍通过 POST 创建新修订。
- 旧快照文件和历史计划版本不迁移、不重写。

## 7. 下游失效

成功保存新进度快照后：

- 响应继续返回 `stale_forecast_ids`；
- 关联旧快照的滚动预测标记为 `stale`；
- 基于旧预测的调整方案不得继续作为当前可采用结果。

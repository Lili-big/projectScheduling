# 接口契约：进度锁定重排三步闭环

## 兼容策略

- 不新增独立下载或持久化端点。
- 复用现有计划摘要、进度快照保存和滚动预测端点。
- 请求结构保持不变；预测响应只新增带默认值的字段。
- 历史预测缺少新增字段时，前端按空摘要和空节点列表兼容展示。

## 1. 保存进度快照

`POST /api/plan-control/progress-snapshots`

请求继续使用：

- `plan_version_id`
- `status_date`
- `entries`
- `submitted_by`
- `correction_reason`
- `expected_revision_no`

成功响应继续返回：

- `progress_snapshot`
- `stale_forecast_ids`
- `diagnostics`

### 错误语义

| 场景 | 状态 | 页面行为 |
|---|---|---|
| 实绩字段或日期无效 | 422 | 显示业务错误；可定位时映射到任务行；不解锁第二步 |
| 快照修订冲突 | 409 | 提示重新加载最新修订；不覆盖当前数据 |
| 计划或任务不存在 | 404 | 提示当前计划已变化并刷新摘要 |
| 存储失败 | 503 | 提示未形成快照，可保留填写态重试 |
| 网络不可达/超时 | 客户端错误 | 提示后端不可达或超时，明确“未保存、未重排” |

## 2. 生成滚动预测

`POST /api/plan-control/forecasts`

请求保持：

```json
{
  "plan_version_id": "plan-...",
  "progress_snapshot_id": "progress-..."
}
```

响应在现有 `ForecastSchedule` 上新增：

```json
{
  "forecast_id": "forecast-...",
  "plan_version_id": "plan-...",
  "progress_snapshot_id": "progress-...",
  "status_date": "2026-07-14",
  "strategy": "as_is",
  "status": "feasible",
  "execution_summary": {
    "completed_locked_count": 3,
    "cancelled_excluded_count": 0,
    "in_progress_remaining_count": 2,
    "paused_remaining_count": 1,
    "not_started_future_count": 345,
    "resource_policy": "baseline_fixed",
    "sequence_policy": "baseline_order"
  },
  "critical_nodes": [
    {
      "node_id": "milestone-control-1",
      "name": "控制墩完成",
      "node_type": "milestone",
      "level": "control",
      "mode": "hard",
      "target_date": "2026-12-23",
      "evaluated_date": "2026-12-28",
      "date_source": "combined",
      "variance_days": 5,
      "buffer_days": -5,
      "status": "late",
      "related_task_ids": ["task-1", "task-2"],
      "evidence": [
        {
          "type": "driving_task",
          "message": "1#墩盖梁预测完成决定该节点日期。",
          "task_ids": ["task-2"],
          "resource_types": ["盖梁模板"],
          "variance_days": 5
        }
      ]
    }
  ]
}
```

### 响应一致性

- `status` 非 `feasible` 时允许返回已锁定历史，但不得伪造未来日期。
- `critical_nodes` 中无法计算的节点使用 `insufficient_data` 和 `evaluated_date=null`。
- 项目级 `risk_status` 必须与节点明细一致：任一强制节点或项目完工 `late` 时为 `late`；否则存在 `at_risk` 时为 `at_risk`；求解不可用或关键节点无法判断时为 `insufficient_data`；其余为 `on_track`。
- 现有 `risk_evidence` 保留为节点证据摘要，避免旧前端失效。

## 3. 查询计划管控摘要

`GET /api/plan-control/projects/{project_id}`

`latest_forecast` 可能是：

- `null`：尚未执行第二步；
- 当前预测：可用于第三步；
- `status=stale`：只作为历史提示，不得作为当前关键节点结论。

前端必须同时检查活动计划、当前快照、最新预测和本地未保存修改后再推导步骤状态。

## 4. 调整方案兼容

现有：

- `POST /api/plan-control/forecasts/{forecast_id}/adjustments`
- `POST /api/plan-control/adjustments/{proposal_id}/adopt`

保持请求、策略数量和推荐规则不变。第三步只增加从风险节点进入该流程的入口，不新增第四种策略。

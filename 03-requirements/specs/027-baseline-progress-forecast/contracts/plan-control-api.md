# 接口契约：计划执行与进度管控

## 通用错误

| 状态码 | 场景 |
|---|---|
| 404 | 计划版本、快照、预测或方案不存在 |
| 409 | 活动版本冲突、修订冲突、输入已过期或重复采用 |
| 422 | 业务字段、任务状态、日期、工程量或求解前置条件不合法 |
| 503 | 本地存储损坏、无法写入或底层服务不可用 |

## 1. 创建基准计划

`POST /api/plan-control/baselines`

请求包含 `scenario`、`resource_plan`、`plan_result`、`confirmed_by`、`confirmation_reason`。仅接受可行/最优结果且方案 ID 与结果 ID 一致。

响应：`PlanVersion`。

## 2. 查询项目计划管控摘要

`GET /api/plan-control/projects/{project_id}`

响应包含活动版本、历史版本摘要、当前进度快照、最新预测和过期状态。无计划时返回成功空态，不返回 404。

## 3. 创建或更正进度快照

`POST /api/plan-control/progress-snapshots`

请求包含 `plan_version_id`、`status_date`、`entries`、`submitted_by`；同版本同状态日期已有快照时必须带 `correction_reason` 和期望修订号。

响应包含新 `ProgressSnapshot`、校验消息和被标记过期的预测 ID。

## 4. 生成当前趋势预测

`POST /api/plan-control/forecasts`

请求包含 `plan_version_id`、`progress_snapshot_id`。响应为 `ForecastSchedule`；数据不足时业务状态为 `insufficient_data`，接口仍可返回 200 和诊断；非法输入返回 422。

## 5. 生成调整方案

`POST /api/plan-control/forecasts/{forecast_id}/adjustments`

请求可包含瓶颈资源增量上限。响应恰好包含三类 `AdjustmentProposal`，每类具有独立状态和诊断；接口整体成功不要求三类全部可行。

## 6. 采用调整方案

`POST /api/plan-control/adjustments/{proposal_id}/adopt`

请求包含 `confirmed_by`、`adoption_reason` 和来源版本指纹。仅可采用未过期且可行的非 `as_is` 或 `as_is` 方案。

响应包含新活动 `PlanVersion`、原版本新状态和 `PlanChangeRecord`。

## 兼容性

- 现有 `/api/ai-resource-assistant/*` 请求响应不移除字段、不改变语义。
- `ScheduleInput.execution_constraints` 为默认空数组；旧请求解析和求解结果不变。
- Netlify 演示 API 本期不复制持久化能力；部署形态继续使用 FastAPI 后端。

## 页面契约

- AI 多方案页面：仅已求解可行方案显示“设为基准计划”，提交中禁止重复点击，成功后显示版本号并提供进入计划执行页入口。
- 计划执行页：无基准为空态；加载失败可重试；保存进度后旧预测立即标记过期；预测和三策略分别显示加载与失败状态。
- 项目场景变化：页面临时选择清空，按新项目 ID 重新加载持久化计划，不沿用旧项目结果。

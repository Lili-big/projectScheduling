# Contract: AI 参数助手

## 目标

提供两个后端接口和一组前端交互契约：

- 解析接口：上传资料并生成参数建议，不修改方案。
- 应用接口：用户确认后，把选中建议应用到当前 `ScenarioInput`。
- 前端契约：展示建议、来源、置信度和冲突，支持局部应用。

## POST `/api/ai-parameter-assistant/parse`

### 请求

`multipart/form-data`

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `scenario` | JSON string | 是 | 当前 `ScenarioInput` 快照 |
| `files[]` | File[] | 否 | Word、Excel、PDF、图片或文本文件，最多 10 个 |
| `text_inputs[]` | string[] | 否 | 用户粘贴的文本资料 |
| `source_labels[]` | string[] | 否 | 可选来源标签，与文件或文本对应 |

约束：

- `files[]` 和 `text_inputs[]` 至少提供一种。
- 单次文件数量最多 10。
- 单次文件总大小最多 50MB。
- 支持类型：文本、Word、Excel、PDF、图片。

### 响应：200

```json
{
  "run_id": "run_20260701_001",
  "status": "completed",
  "expires_at": "2026-07-01T10:30:00+08:00",
  "material_summaries": [
    {
      "material_id": "mat_001",
      "file_name": "资源计划表.xlsx",
      "kind": "excel",
      "size_bytes": 20480,
      "parse_status": "parsed",
      "source_summary": "包含主要机械和班组资源数量",
      "error_message": null
    }
  ],
  "suggestions": [
    {
      "suggestion_id": "sug_001",
      "category": "resource_pool",
      "target_ref": {
        "resource_id": "crane_team"
      },
      "parameter_key": "resource.capacity",
      "current_value": 1,
      "proposed_value": 2,
      "unit": "台",
      "confidence_label": "High",
      "confidence_score": 88,
      "source_refs": [
        {
          "material_id": "mat_001",
          "excerpt": "汽车吊 2 台",
          "page_or_sheet": "资源计划",
          "cell_or_region": "B12:C12",
          "note": "表格明确给出数量"
        }
      ],
      "conflict_group_id": null,
      "status": "suggested",
      "validation_messages": []
    }
  ],
  "conflict_groups": [],
  "manual_completion_count": 0,
  "warnings": [],
  "errors": []
}
```

### 错误

| 状态码 | 场景 | 行为 |
|--------|------|------|
| 400 | 缺少 `scenario`、无资料、文件数量或大小超限 | 返回错误，当前方案不变 |
| 415 | 文件类型不支持 | 返回资料级错误，当前方案不变 |
| 422 | 资料可读但无法形成有效建议 | 返回空建议和说明，当前方案不变 |
| 503 | AI 服务不可用或超时 | 返回服务错误，当前方案不变 |

### 行为规则

- 解析接口不得修改当前方案。
- 原始上传文件不得持久化。
- 后端必须把本次建议、冲突组、候选新增项和资料摘要写入短期 suggestion store，并通过 `run_id` 供应用接口读取。
- 短期 suggestion store 不保存上传原文件、完整原文或图片内容；过期后用户需要重新解析或重新上传。
- 图片建议默认保守处理；没有清晰证据时应为 `Low`。
- 同一参数多来源不一致时必须生成 `conflict_groups`。
- 高置信建议可以由前端默认勾选，但仍需用户点击应用。

## POST `/api/ai-parameter-assistant/apply`

### 请求

`application/json`

```json
{
  "scenario": {},
  "run_id": "run_20260701_001",
  "selected_suggestion_ids": ["sug_001"],
  "conflict_resolutions": [],
  "manual_values": []
}
```

字段说明：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `scenario` | ScenarioInput | 是 | 当前方案快照 |
| `run_id` | string | 是 | 解析流程 ID |
| `selected_suggestion_ids` | string[] | 是 | 用户确认应用的建议 ID |
| `conflict_resolutions` | ConflictGroup[] | 否 | 用户选择、手填或保留当前值的冲突处理 |
| `manual_values` | object[] | 否 | 用户为低置信或不完整建议补充的字段 |

实现说明：

- 服务端必须通过 `run_id` 从短期 suggestion store 取回已展示的建议、冲突组和候选项。
- 服务端必须以请求中的 `scenario` 为应用基准，并重新校验建议是否可落入现有模型。
- 应用请求不得携带上传原文件，也不得绕过短期 suggestion store 直接提交任意建议对象。

### 响应：200

```json
{
  "scenario": {},
  "application_summary": {
    "applied_count": 1,
    "skipped_count": 0,
    "failed_count": 0,
    "manual_pending_count": 0,
    "applied_items": [
      {
        "suggestion_id": "sug_001",
        "category": "resource_pool",
        "target_ref": {
          "resource_id": "crane_team"
        },
        "parameter_key": "resource.capacity",
        "old_value": 1,
        "new_value": 2
      }
    ],
    "failed_items": [],
    "stale_result_reason": "AI 参数助手已更新当前方案参数，任务视图和求解结果需要重新生成。"
  },
  "stale_results": true
}
```

### 错误

| 状态码 | 场景 | 行为 |
|--------|------|------|
| 400 | 未选择建议或冲突未解决 | 不应用任何变更 |
| 409 | 请求基准方案与建议目标不兼容 | 不应用冲突项，可返回可恢复说明 |
| 410 | `run_id` 不存在或短期 suggestion store 已过期 | 不应用任何变更，提示重新解析或重新上传 |
| 422 | 建议值无法通过模型校验 | 跳过失败项，返回失败明细 |

### 行为规则

- 只应用用户选择或手动确认的项。
- 不自动覆盖未选择参数。
- 不自动保存项目级配置。
- 对有效建议支持局部应用，失败项进入结果摘要。
- 只要成功应用任一项，前端必须将任务视图、求解结果和方案对比标记为过期。

## 前端交互契约

前端助手面板至少包含：

- 上传区：支持文件和文本输入，展示数量、大小和类型限制。
- 解析状态：展示解析中、部分失败、失败和完成状态。
- 建议表：按工艺工效、资源数量、里程碑分组。
- 置信度：展示等级和 0-100 分。
- 来源证据：展示文件名、页码或 Sheet、短摘录和说明。
- 冲突处理：展示当前值、候选值和来源，允许选择一个值、保留当前值或手动填写。
- 待完善区：集中展示低置信和字段不完整建议。
- 应用按钮：仅在存在可应用选择且冲突已解决时启用。

应用后的前端状态：

- 更新当前 `ScenarioInput`。
- 清空或标记旧任务视图、求解结果和方案对比为过期。
- 保留应用摘要，供用户检查本次变更。
- 不触发项目级保存动作。

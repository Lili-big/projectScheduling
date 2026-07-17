# 数据模型：AI 参数输入助手

## 现有模型映射

本功能不替换现有排程模型，而是生成可审阅的建议并最终更新当前 `ScenarioInput`。

- `ScenarioInput`：应用建议后的当前方案容器。
- `ProcessTemplate`：工艺模板，承接工效类建议。
- `ProductivityOption`：工效选项，承接标准工效、班组和单位等建议。
- `ResourcePool`：资源池，承接资源数量、容量和可用性建议。
- `MilestoneConstraint`：里程碑约束，承接日期、类型和说明建议。
- `ValidationMessage`：可复用为建议级校验提示和应用失败原因。

## ExtractionRun

表示一次 AI 参数解析流程。它不是长期持久化记录。

| 字段 | 类型 | 说明 |
|------|------|------|
| `run_id` | string | 本次解析流程 ID，用于前端关联建议和应用请求 |
| `status` | enum | `ready`、`extracting`、`completed`、`partially_failed`、`failed` |
| `material_count` | number | 已接收资料数量，最大 10 |
| `total_size_bytes` | number | 已接收资料总大小，最大 50MB |
| `suggestion_count` | number | 可展示建议数量，最大 100 |
| `material_summaries` | UploadedMaterialSummary[] | 资料解析摘要 |
| `errors` | ValidationMessage[] | 解析级错误 |
| `warnings` | ValidationMessage[] | 解析级警告 |
| `expires_at` | datetime | 短期 suggestion store 过期时间 |

规则：

- 不保存上传原文件。
- `run_id` 必须能在短期 suggestion store 中取回本次建议，直到过期或用户开始新的解析流程。
- 当所有资料都无法解析时，状态为 `failed`。
- 当部分资料失败但仍生成建议时，状态为 `partially_failed`。

## UploadedMaterialSummary

表示上传资料的可追溯摘要，不包含原始文件内容。

| 字段 | 类型 | 说明 |
|------|------|------|
| `material_id` | string | 资料摘要 ID |
| `file_name` | string | 用户上传文件名或文本输入标题 |
| `kind` | enum | `text`、`word`、`excel`、`pdf`、`image` |
| `size_bytes` | number | 文件大小或文本估算大小 |
| `parse_status` | enum | `parsed`、`partially_parsed`、`failed` |
| `source_summary` | string | 资料内容摘要，用于用户判断来源 |
| `error_message` | string? | 失败原因 |

规则：

- 图片资料可解析但默认置信度偏保守。
- 不可读资料不阻断其他资料解析。

## ParameterSuggestion

用户确认前的核心建议对象。

| 字段 | 类型 | 说明 |
|------|------|------|
| `suggestion_id` | string | 建议 ID |
| `category` | enum | `process_productivity`、`resource_pool`、`milestone` |
| `target_ref` | object | 目标对象引用，例如工艺 ID、资源池 ID、里程碑名称 |
| `parameter_key` | string | 具体参数键，例如 `productivity.daily_output`、`resource.capacity`、`milestone.date` |
| `current_value` | any | 当前方案中的值，可为空 |
| `proposed_value` | any | AI 建议值 |
| `unit` | string? | 单位，例如 `m/day`、`台`、`人`、日期 |
| `confidence_label` | enum | `High`、`Medium`、`Low` |
| `confidence_score` | number | 0-100 |
| `source_refs` | SourceEvidence[] | 来源证据 |
| `conflict_group_id` | string? | 冲突组 ID |
| `status` | enum | `suggested`、`selected`、`needs_manual_input`、`conflict`、`ignored`、`applied`、`failed` |
| `validation_messages` | ValidationMessage[] | 建议级校验信息 |

规则：

- `High` 且无冲突且字段完整的建议可默认勾选。
- `Medium` 默认不勾选。
- `Low` 默认进入待人工完善。
- `proposed_value` 不能绕过现有模型校验。
- 指向不存在对象时必须以候选新增形式展示。

## SourceEvidence

建议的来源证据。

| 字段 | 类型 | 说明 |
|------|------|------|
| `material_id` | string | 来源资料 ID |
| `excerpt` | string | 可展示的短引用或摘要，不保存大段原文 |
| `page_or_sheet` | string? | PDF 页码、Word 页段或 Excel Sheet |
| `cell_or_region` | string? | 表格单元格、图片区域或段落位置 |
| `note` | string? | AI 对证据的解释 |

规则：

- 证据用于用户确认，不作为长期原文归档。
- 单条证据引用应保持简短，避免在响应中复制完整资料。

## ConflictGroup

表示同一参数的多个候选值或建议值与当前值冲突。

| 字段 | 类型 | 说明 |
|------|------|------|
| `conflict_group_id` | string | 冲突组 ID |
| `parameter_key` | string | 冲突参数 |
| `target_ref` | object | 冲突目标 |
| `suggestion_ids` | string[] | 相关建议 |
| `current_value` | any | 当前值 |
| `resolution_status` | enum | `unresolved`、`selected_suggestion`、`manual_value`、`keep_current` |
| `selected_suggestion_id` | string? | 用户选择的建议 |
| `manual_value` | any? | 用户手动填写值 |

规则：

- 未解决冲突不能应用。
- 用户可以保留当前值，此时相关建议记为跳过。

## CandidateAddition

表示 AI 识别出的新工艺、新资源或新里程碑候选项。

| 字段 | 类型 | 说明 |
|------|------|------|
| `candidate_id` | string | 候选项 ID |
| `category` | enum | `process_productivity`、`resource_pool`、`milestone` |
| `display_name` | string | 展示名称 |
| `proposed_fields` | object | 新增对象字段 |
| `confidence_label` | enum | `High`、`Medium`、`Low` |
| `confidence_score` | number | 0-100 |
| `source_refs` | SourceEvidence[] | 来源证据 |
| `validation_status` | enum | `valid`、`needs_manual_input`、`invalid` |

规则：

- 候选项默认不是正式配置。
- 只有用户确认后，才加入当前 `ScenarioInput`。

## SuggestionStoreEntry

表示服务端短期保存的解析建议状态，用于支持 `/apply` 通过 `run_id` 找回用户刚审阅过的建议。它不是数据库记录，不包含上传原文件。

| 字段 | 类型 | 说明 |
|------|------|------|
| `run_id` | string | 解析流程 ID |
| `created_at` | datetime | 创建时间 |
| `expires_at` | datetime | 过期时间 |
| `scenario_id` | string | 发起解析时的当前方案 ID |
| `suggestions` | ParameterSuggestion[] | 本次解析建议 |
| `conflict_groups` | ConflictGroup[] | 本次冲突组 |
| `candidate_additions` | CandidateAddition[] | 本次候选新增项 |
| `material_summaries` | UploadedMaterialSummary[] | 资料摘要 |
| `application_status` | enum | `pending`、`partially_applied`、`applied`、`expired` |

规则：

- 不保存上传原文件、完整原文或图片内容。
- 过期后应用请求必须失败，并提示用户重新解析或重新上传。
- 同一用户开始新的解析流程时，可让旧 `run_id` 过期或被替换。
- `/apply` 必须从该 store 读取建议，再按用户选择和冲突解决结果应用到请求中的 `ScenarioInput`。

## ApplicationRequest

表示用户确认后的应用请求。

| 字段 | 类型 | 说明 |
|------|------|------|
| `scenario` | ScenarioInput | 当前方案快照 |
| `run_id` | string | 解析流程 ID |
| `selected_suggestion_ids` | string[] | 用户勾选建议 |
| `conflict_resolutions` | ConflictGroup[] | 已解决冲突 |
| `manual_values` | object[] | 用户手动补充值 |

规则：

- 请求必须包含当前方案快照，应用结果以该快照为基准。
- `run_id` 只用于取回短期 suggestion store 中的建议，不允许凭 `run_id` 自动应用全部建议。
- 如果 `run_id` 不存在或已过期，应用请求必须失败并保持当前方案不变。
- 请求不得携带上传原文件；手动补充值只能补齐被用户确认的建议字段。

## ApplicationSummary

表示应用结果。

| 字段 | 类型 | 说明 |
|------|------|------|
| `applied_count` | number | 成功应用数量 |
| `skipped_count` | number | 用户跳过或保留当前值数量 |
| `failed_count` | number | 应用失败数量 |
| `manual_pending_count` | number | 仍需人工完善数量 |
| `applied_items` | object[] | 成功应用明细 |
| `failed_items` | ValidationMessage[] | 失败明细 |
| `stale_result_reason` | string | 旧任务视图或求解结果过期原因 |

规则：

- 部分建议失败不影响其他有效建议应用。
- 只要有成功应用项，就必须返回更新后的 `ScenarioInput`。
- 应用后前端必须清空或标记任务视图、求解结果和方案对比为过期。

## 状态流转

```text
ExtractionRun:
ready -> extracting -> completed
ready -> extracting -> partially_failed
ready -> extracting -> failed

ParameterSuggestion:
suggested -> selected -> applied
suggested -> ignored
suggested -> needs_manual_input
suggested -> conflict -> selected -> applied
suggested -> conflict -> ignored
suggested -> selected -> failed
```

## 校验规则

- 单次最多 10 个文件。
- 单次总大小不超过 50MB。
- 前端最多展示 100 条建议，超出部分应合并为提示或要求拆分资料。
- 所有建议必须有来源摘要；无来源的建议不得默认勾选。
- 冲突未解决时禁止应用相关建议。
- 低置信度建议不得默认勾选。
- 里程碑无明确合同或控制性语义时，默认内部软里程碑。
- `run_id` 不存在或短期 suggestion store 已过期时，应用请求不得修改当前方案。
- 应用只更新当前方案，不触发项目级保存。

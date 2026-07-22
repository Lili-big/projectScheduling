# 数据模型：AI 批量初始化工点工装资源

## 1. AI 工点资源初始化请求

| 字段 | 类型 | 规则 |
|---|---|---|
| `scenario` | `ScenarioInput` | 必填；包含 `project_data_version_id`、当前工艺库和当前完整资源池快照 |

请求不接收前端自定义工点、结构汇总或候选资源；这些输入由后端根据当前项目版本重新生成。

## 2. 工点结构汇总

| 字段 | 类型 | 规则 |
|---|---|---|
| `workpoint_id` | string | 当前项目版本中的稳定桥梁工点 ID |
| `workpoint_name` | string | 权威名称，仅用于模型理解和用户摘要 |
| `structures` | array | 按结构物/构件类型、工艺和关键参数签名聚合并稳定排序 |
| `structure_type` | string | 系统投影后的结构类型 |
| `component_type` | string | 系统投影后的构件类型 |
| `quantity` | number | 聚合工程量，必须大于 0 |
| `unit` | string | 原始或投影单位 |
| `process_id` | string/null | 明确工艺；缺失时记录诊断而非猜测 |
| `parameter_summary` | object | 仅保留资源判断需要的稳定参数摘要 |

一个工点没有可用结构汇总时不进入模型推荐，并产生阻断诊断。

## 3. 工点候选资源

| 字段 | 类型 | 规则 |
|---|---|---|
| `workpoint_id` | string | 与结构汇总一致 |
| `resource_type` | string | 来自后端资源目录和该工点工艺需求的交集 |
| `label` | string | 系统中文标签 |
| `default_calendar_id` | string | 后端用于构造资源池，模型不可修改 |
| `applicable_process_ids` | string[] | 稳定去重排序 |

候选集合排除已有 `工点 ID + 资源类型`、共享资源、停用/不支持目录项和 `precast_beam_team`。候选为空表示该工点无需补充，不创建占位资源。

## 4. LLM 工点资源推荐

| 字段 | 类型 | 规则 |
|---|---|---|
| `workpoint_id` | string | 必须与待推荐工点精确匹配 |
| `resources` | array | 允许为空；不得重复资源类型 |
| `resource_type` | string | 必须属于该工点候选集合 |
| `quantity` | integer | `>= 1` |
| `max_quantity` | integer | `>= quantity` |
| `reason` | string | 简短推荐理由，不参与资源池属性构造 |

模型输出不包含资源池 ID、标签、作用域、模式、状态、日历、适用工艺、成本或共享范围。

## 5. 待新增工点资源池

后端在模型结果完全合法后构造现有 `ResourcePool`：

| 字段 | 来源/规则 |
|---|---|
| `id` | 按现有 `workpoint-<encoded workpoint id>-<encoded resource type>` 稳定规则生成 |
| `type` | 已验证的候选 `resource_type` |
| `label` | 后端资源目录 |
| `resource_mode` | 固定 `LIMITED` |
| `scope_mode` | 固定 `WORKPOINT_EXCLUSIVE` |
| `workpoint_id` | 推荐所属工点 |
| `quantity` | 已验证 LLM 数量 |
| `max_quantity` | 已验证 LLM 上限 |
| `enabled` | 固定 `true` |
| `authorized_workpoint_ids` | 固定 `null` |
| `workpoint_overrides` | 固定空数组 |
| `calendar_id` | 候选资源默认日历 |
| `compatible_process_ids` | 候选资源适用工艺 |
| 成本/并行扩展字段 | 沿用 `ResourcePool` 安全默认值，不由模型决定 |

## 6. 批量推荐摘要

| 字段 | 类型 | 规则 |
|---|---|---|
| `project_data_version_id` | string | 响应对应的权威版本 |
| `input_fingerprint` | string | 覆盖版本、工艺和完整资源池语义 |
| `provider` | string | 不含凭据 |
| `model` | string/null | 当前模型名称 |
| `workpoint_count` | integer | 本次检查的可排程桥梁工点数 |
| `recommended_workpoint_count` | integer | 新增至少一个资源的工点数 |
| `unchanged_workpoint_ids` | string[] | 无缺失资源或模型合法返回空建议的工点 |
| `added_resource_count` | integer | `resource_pools_to_add` 长度 |
| `diagnostics` | `ValidationMessage[]` | 缺结构、无候选、校验失败等，不含密钥 |

## 7. 初始化响应

| 字段 | 类型 | 规则 |
|---|---|---|
| `project_data_version_id` | string | 必填 |
| `input_fingerprint` | string | 必填；前端落地前再次核对 |
| `resource_pools_to_add` | `ResourcePool[]` | 只含新增本地池；整批成功后返回 |
| `summary` | 批量推荐摘要 | 用户提示和诊断 |
| `llm_config_status` | 现有资源助手模型状态 | 不包含 endpoint 完整值或 Key |

## 状态转换

```text
idle
  -> validating_input
  -> calling_llm
  -> validating_response
  -> ready_to_apply
  -> applied_to_unsaved_page_state
  -> saved_by_existing_save_action
```

失败转换：

```text
validating_input/calling_llm/validating_response
  -> failed_without_changes

ready_to_apply
  -> stale_discarded_without_changes  (项目版本或资源输入已变化)
```

## 不变量

- 响应资源池集合与请求前资源池集合的 ID、`工点 ID + 资源类型` 均无交集。
- 请求前已有资源池在 AI 合并后逐字段一致。
- 任一非法 LLM 记录导致返回的待新增池数量为 0。
- AI 推荐成功不等于已保存；持久化只能由现有保存操作触发。
- API Key 不属于任何请求、响应、摘要或诊断实体。

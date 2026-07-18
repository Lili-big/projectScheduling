# 数据模型：统一桥台任务生成、工期与资源规则

**日期**：2026-07-17

## 1. 模型关系

```text
ProjectMasterVersion（confirmed）
  -> ProjectMasterStructure(structure_type=bridge_abutment)
      -> ProjectMasterComponent
          -> CanonicalProjectedComponent(component_type=abutment_body 或 pile)
              -> ProcessTemplate(abutment_body_standard)
                  -> Task(duration_days=15, compatible_resource_types=[])
                      -> ScheduleResult(无桥台具名资源分配)
```

## 2. 项目主数据结构物

| 字段 | 类型/枚举 | 规则 |
| --- | --- | --- |
| `structure_id` | string | 稳定且不可为空，重新投影时保持不变 |
| `structure_type` | string | 桥台必须为 `bridge_abutment`；这是桥台上下文唯一判定依据 |
| `side` | enum | 沿用项目主数据左右幅/共用语义 |
| `section_code` | string | 桥梁排程必填，沿用现有校验 |
| `components` | list | 包含源构件；历史记录可以仍为 `cap_beam` |

## 3. 项目主数据构件

| 字段 | 类型/枚举 | 规则 |
| --- | --- | --- |
| `component_id` | string | 稳定标识，投影后仍写入来源引用 |
| `component_type` | string | 新桥台非桩数据写 `abutment_body`；历史可为 `cap_beam`；桩基为 `pile` |
| `quantity` | number | 不小于 0；0 值沿用通用跳过/诊断规则 |
| `unit` | string | `abutment_body` 推荐“个”或现有项目允许的结构工程量单位 |
| `enabled` | boolean | 禁用构件不生成任务 |
| `parameters` | list | 原样保留，不用参数文本识别桥台 |

### 类型定义变化

- 项目主数据 `COMPONENT_TYPES` 增加 `abutment_body`，显示名“桥台”，推荐单位至少包含“个”。
- `cap_beam` 继续存在，显示名“盖梁”，用于非桥台结构。
- 工作簿数据验证列表同步包含 `abutment_body`，不删除 `cap_beam`。

## 4. 规范投影构件

规范投影不是新的持久化表，而是生成/求解请求中的确定性派生对象。

| 来源条件 | 规范 `component_type` | 保留字段 |
| --- | --- | --- |
| `bridge_abutment` 且源类型为 `pile` | `pile` | ID、名称、数量、单位、方法、参数、来源引用 |
| `bridge_abutment` 且源类型不是 `pile` | `abutment_body` | ID、名称、数量、单位、启用状态、参数、来源引用 |
| `bridge_pier` 且源类型为 `cap_beam` | `cap_beam` | 现有字段全部保留 |
| 其他结构/构件 | 现有映射 | 不受本功能改变 |

### 投影来源元数据

| 键 | 示例 | 作用 |
| --- | --- | --- |
| `project_data_version_id` | `pmv-...` | 关联已确认源版本 |
| `content_fingerprint` | `...` | 保留源数据指纹 |
| `source_batch_id` | `batch-...` | 关联导入批次 |
| `scheduling_projection_version` | `project-master-scheduling/v2` | 识别规范投影规则版本 |

## 5. 工艺模板与工效

| 字段 | 规范值 |
| --- | --- |
| `id` | `abutment_body_standard` |
| `component_type` | `abutment_body` |
| `process_name` | 桥台施工 |
| `duration_method` | `fixed_days` |
| `quantity_source` | `count` |
| `productivity_value` | `15` |
| `productivity_unit` | 天/个 |
| `resource_type` | `abutment_team` |
| `is_default` | `true` |

默认工期计算：

```text
桥台任务默认工期 = 15 天/个 × 构件数量
```

当数量为 1 个时，`duration_days=15`。不在投影层或前端重复计算该规则。

## 6. 资源配置

| 字段 | 规范值/规则 |
| --- | --- |
| 默认资源池集合 | 不新增 `type=abutment_team` 的资源池 |
| 工艺资源类型元数据 | `abutment_body_standard.resource_type=abutment_team` 可继续保留 |
| 任务兼容资源 | 由资源池缺失的通用路径清空为 `[]` |
| 数量与上限 | 不创建桥台资源池，因此不存在桥台池的 `quantity` / `max_quantity` |

状态语义：

```text
未配置 abutment_team 资源池
  -> 不展开 Resource 实例
  -> Task.compatible_resource_types=[]
  -> 求解器不创建资源选择变量
  -> ScheduleResult.resource_allocations 不含 abutment_team
```

## 7. 生成任务

| 字段 | 规范值/规则 |
| --- | --- |
| `component_type` | `abutment_body` |
| `process_name` | 桥台施工 |
| `productivity_rule_id` | 指向 `abutment_body_standard` 的默认工效选项 |
| `quantity` | 来自规范投影构件 |
| `quantity_label` | 来自规范投影构件，不用前端补造 |
| `duration_days` | 数量 1 时为 15 |
| `compatible_resource_types` | `[]` |
| `properties.project_master_structure_id` | 源结构物 ID |
| `properties.project_master_component_id` | 源构件 ID |

## 8. 生成结果摘要与当前性

`GeneratedScheduleInput.source_summary` 增加：

| 键 | 规则 |
| --- | --- |
| `project_data_version_id` | 使用项目主数据生成时必填 |
| `scheduling_projection_version` | 使用当前规范投影版本 |
| `abutment_body_task_count` | 可选诊断计数，不参与业务规则 |

当前性判断：

- 源版本或投影版本变化，派生任务和求解结果必须重新生成。
- 缺少投影版本的历史派生结果视为旧版本证据，不作为当前规范结果。
- 历史源快照本身不因重新投影变为失效。

## 9. 状态转换

```text
项目主数据草稿
  -> 校验通过
  -> confirmed
  -> 按 scheduling_projection_version 重新投影
  -> 生成任务
  -> 求解结果

投影版本变化
  -> 旧派生结果 stale
  -> 重新投影/生成/求解
  -> 新派生结果 current
```

## 10. 工作台权威显示映射

显示映射是任务视图的通用派生状态，不改变任务或项目主数据实体。

| 字段 | 类型/示例 | 规则 |
| --- | --- | --- |
| `project_data_version_id` | string | 必须与当前规范任务引用的版本一致 |
| `workpoint_ids` | sorted unique string list | 来自当前任务 `bridge_id` 引用集合，不根据 ID 格式解释业务含义 |
| `request_key` | stable string | 仅由版本 ID 与规范化 workpoint ID 集合生成 |
| `status` | `loading / ready / error` | 未 ready 时不得渲染权威名称 rows |
| `workpoints` | complete list | 只有当前身份的全部请求成功后一次性提交 |
| `error` | optional generic error | 失败时提供通用错误/不可用态与重试 |
| `retry_key` | request identity/generation | 重试仍绑定同一当前身份，版本切换后旧重试失效 |

状态转换：

```text
任务或版本身份变化
  -> loading(current request_key)
      -> 全部成功且 request_key 仍当前 -> ready(atomic maps)
      -> 任一失败且 request_key 仍当前 -> error(retry available)
      -> 响应身份已过期 -> ignore

error(current request_key)
  -> retry
  -> loading(current request_key, new generation)
```

可见性规则：

- `loading`：只显示通用加载态/骨架态，不构建含原始 ID 的可见 rows。
- `ready`：只使用完整权威 `workpoint_name`、`section_name` 与 side label。
- `error`：只显示通用错误/不可用态与重试，不显示部分映射、原始 ID 或 `"-"` 作为名称。
- 相同 `request_key` 的 ready 映射允许缓存复用；不同 key 绝不共享当前可见结果。

## 11. 校验规则

- `bridge_abutment` 判定只看规范结构类型，不看名称、ID、排序和参数文本。
- 桥台 `pile` 必须通过原有桩基路径。
- 桥台非桩构件必须通过规范投影得到 `abutment_body`。
- `abutment_body` 必须能在工艺库中找到唯一默认工艺。
- 默认资源池集合不得新增 `abutment_team`；资源池缺失时不得展开或补造具名桥台资源。
- 任务空兼容资源不产生资源缺失错误；仍可受非资源约束限制。
- `bridge_pier + cap_beam` 必须保持原行为。
- `bridge_abutment` 下只有 `pile` 时不得补造 `abutment_body`。
- 工艺库缺少 `abutment_body_standard` 时必须走通用工艺缺失错误，不得回退 `cap_beam_standard`。
- 项目主数据派生结果缺少或不匹配当前 `scheduling_projection_version` 时不得作为 current 结果复用。
- 工作台显示映射未 ready 或加载失败时不得以 `bridge_id`、`work_section_id`、`"-"` 或部分映射生成可见名称。
- 任何异步映射响应提交前必须校验当前 `request_key`；过期响应只能忽略。

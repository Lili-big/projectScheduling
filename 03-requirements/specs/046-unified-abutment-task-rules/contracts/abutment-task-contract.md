# 桥台规范任务共享契约

**契约版本**：`abutment-task/v1`

**适用入口**：现有 `/api/generate-schedule-input`、`/api/solve-scenario`、`/api/solve-min-resources`、`/api/solve-resource-cost`；不新增 HTTP 路径。

## 1. 输入契约

### 1.1 项目主数据

```json
{
  "structure_id": "ST-DEMO-L-AB0",
  "structure_type": "bridge_abutment",
  "components": [
    {
      "component_id": "CP-DEMO-L-AB0-PILE-01",
      "component_type": "pile",
      "quantity": 1,
      "unit": "根",
      "enabled": true
    },
    {
      "component_id": "CP-DEMO-L-AB0-BODY",
      "component_type": "cap_beam",
      "quantity": 1,
      "unit": "个",
      "enabled": true
    }
  ]
}
```

说明：示例中的 `cap_beam` 代表历史已确认来源事实；规范投影必须根据父结构物 `bridge_abutment` 修正为 `abutment_body`。不得使用构件名称或 ID 判断。

### 1.2 资源配置

- 默认场景和部署配置不新增 `type=abutment_team` 的资源池。
- `abutment_body_standard.resource_type=abutment_team` 作为工艺元数据保留。
- 任务生成必须通过资源池缺失的现有通用路径得到空 `compatible_resource_types`，不得据此自动补造资源池。

## 2. 规范投影契约

| 父结构类型 | 源构件类型 | 规范构件类型 | 说明 |
| --- | --- | --- | --- |
| `bridge_abutment` | `pile` | `pile` | 桩基规则完全保持 |
| `bridge_abutment` | 非 `pile` | `abutment_body` | 桥台非桩构件统一规范化 |
| `bridge_pier` | `cap_beam` | `cap_beam` | 桥墩盖梁不受影响 |

规范化必须保持 `component_id`、结构物/构件来源引用、数量、单位、启用状态和参数。

## 3. 任务输出契约

```json
{
  "component_id": "CP-DEMO-L-AB0-BODY",
  "structure_id": "ST-DEMO-L-AB0",
  "structure_type": "abutment",
  "component_type": "abutment_body",
  "process_name": "桥台施工",
  "productivity_rule_id": "abutment_body_standard:abutment_body_standard-default",
  "quantity": 1,
  "quantity_label": "1个",
  "duration_days": 15,
  "compatible_resource_types": [],
  "properties": {
    "project_master_structure_id": "ST-DEMO-L-AB0",
    "project_master_component_id": "CP-DEMO-L-AB0-BODY"
  }
}
```

允许 `productivity_rule_id` 的连接格式沿用现有实现，但必须能追溯到 `abutment_body_standard` 的默认工效选项。

## 4. 求解输出契约

- `ScheduleInput.resources` 不包含 `type=abutment_team` 的具名资源实例。
- `ScheduleResult.resource_allocations` 不包含 `resource_type=abutment_team`。
- 不产生由 `abutment_team` 容量引起的资源等待或互斥串行。
- 前置关系、里程碑、日历及其他资源约束仍可影响桥台任务日期。

## 5. 来源与版本契约

新生成结果的 `source_summary` 必须至少能表达：

```json
{
  "project_data_version_id": "pmv-demo",
  "scheduling_projection_version": "project-master-scheduling/v2"
}
```

- 版本值为示例；实现时使用单一稳定常量。
- 源项目主数据版本相同但投影版本不同时，旧任务/求解结果必须视为过期。
- 缺少投影版本的历史派生结果可以保留查看，但不能标记为当前规范结果。

## 6. 前端展示契约

- 构件标签由共享 `component_type=abutment_body` 映射为“桥台”。
- 工艺名称直接使用 `process_name=桥台施工`。
- 工期直接使用 `duration_days=15`，不根据名称或旧类型改写。
- 空 `compatible_resource_types` 使用通用默认充足/无受限资源显示，不虚构班组编号。
- 空任务与错误响应使用通用空态和错误态。
- 工点、桥梁、工区和幅别名称只来自当前 `project_data_version_id` 对应的完整项目主数据映射。
- 映射未就绪时显示通用加载态/骨架态，不把 `bridge_id`、`work_section_id` 或 `"-"` 作为最终名称。
- 任一映射请求失败时不提交部分映射，显示通用错误/不可用态并提供重试。
- 版本或 workpoint ID 集合变化后，旧映射和旧请求晚到响应不得驱动当前任务 rows。

### 6.1 显示映射请求身份

```json
{
  "project_data_version_id": "pmv-demo",
  "workpoint_ids": ["WP-BRIDGE-01", "WP-BRIDGE-02"]
}
```

- `workpoint_ids` 必须去重并稳定排序后参与请求/缓存身份。
- 该身份只解决通用异步当前性，不解释 ID 业务含义。
- 相同身份的 complete ready 映射可以复用；不同身份不得共享当前可见结果。

### 6.2 显示状态契约

| 状态 | 可见内容 | 禁止内容 |
| --- | --- | --- |
| `loading` | 通用加载态或骨架态 | 任务名称 rows、原始 ID、`"-"` 冒充名称 |
| `ready` | 当前身份的完整权威名称映射与任务 rows | 部分映射、旧版本映射 |
| `error` | 通用错误/不可用态、重试入口 | 静默吞错、部分映射、原始 ID 兜底 |

## 7. 异常与兼容契约

| 场景 | 预期 |
| --- | --- |
| 项目主数据版本未确认 | 沿用现有版本冲突错误，不生成任务 |
| 桥台构件禁用或数量为 0 | 沿用通用跳过/诊断规则 |
| 工艺库缺少 `abutment_body_standard` | 产生通用工艺缺失错误，不回退到盖梁施工 |
| 默认配置不含 `abutment_team` 资源池 | 正常生成任务并清空兼容资源 |
| 桥墩 `cap_beam` | 继续盖梁施工、10 天/个及现有资源语义 |
| 桥台 `pile` | 继续原桩基工艺、工期、资源和前置规则 |
| 历史派生结果缺少当前投影版本 | 标记过期并要求重新生成 |
| 桥台只有桩基 | 只生成原桩基任务，不补造桥台主体 |
| 权威显示映射部分请求失败 | 整批进入通用错误态，不提交部分映射 |
| 版本切换后旧请求晚到 | 忽略旧响应，继续使用新身份状态 |

## 8. 禁止项

- 禁止 `if name contains 桥台/台帽`、ID 前缀判断或固定 10/15 值修正。
- 禁止前端新增 `cap_beam → abutment_body` 兜底。
- 禁止为满足桥台默认充足语义补造资源池或使用极大资源数量模拟无限。
- 禁止直接批量改写历史确认快照。
- 禁止为桥台跳过统一任务生成或资源处理链路。
- 禁止在映射加载中或失败后用 `bridge_id`、`work_section_id`、`"-"` 或部分成功结果冒充权威名称。
- 禁止按桥台/桥墩类型、名称或 ID 格式决定是否等待映射。

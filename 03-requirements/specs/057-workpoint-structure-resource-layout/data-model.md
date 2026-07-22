# 数据模型：工点结构物汇总与数量派生资源

本功能新增前端只读派生对象，并收紧现有工点独享资源的规范化规则；不新增后端模型、API 字段、数据库表或迁移。

## 1. 结构物汇总分类 `WorkpointStructureSummaryGroup`

| 字段 | 类型 | 说明 |
|---|---|---|
| `componentType` | 六类目标构件联合类型 | 稳定分类标识 |
| `label` | `string` | 桩基、承台、柱系梁、墩身、桩系梁或盖梁 |
| `sortOrder` | `number` | 固定 1–6 |
| `items` | `WorkpointStructureSummaryItem[]` | 该类非空汇总项，按稳定签名排序 |

空分类不进入输出数组。

## 2. 结构物汇总项 `WorkpointStructureSummaryItem`

| 字段 | 类型 | 来源/规则 |
|---|---|---|
| `signature` | `string` | 构件类型、规范化参数、工艺身份和单位组成的确定性内部键 |
| `componentType` | 目标构件类型 | 当前分类 |
| `processId` | `string \| null` | 显式匹配或唯一默认工艺；无法匹配时为空 |
| `processLabel` | `string \| null` | 工艺库中文名称、原始标识或诊断文案 |
| `parameterSegments` | `string[]` | 已知物理/形式参数的紧凑可读片段 |
| `quantity` | `number` | 同签名构件 `quantity` 合计 |
| `unit` | `string` | 构件单位；不同单位不合并 |
| `displayText` | `string` | 工艺、参数和 `quantity + unit` 拼成的页面文本 |

### 有效性规则

- 来源构件必须属于六类目标类型、`enabled=true` 且 `quantity>0`。
- `quantity` 必须是有限非负数；等价输入不得因结构或参数数组顺序不同而改变输出。
- 参数值按类型规范化：数值去无意义尾零，数组保持值顺序但统一数值格式，布尔/日期/文本转为稳定字符串，空值不进入展示。
- 工艺参数代码包括 `method_id`、`process_method_id`、`pile_method`、`construction_method`，不再作为普通结构参数重复显示。
- 相同 `signature` 累加数量；不同单位、工艺或参数必须产生不同项。

### 关系

```text
ProjectMasterWorkpoint
  └─ ProjectMasterStructure
       └─ ProjectMasterComponent(enabled, quantity, unit, parameters)
            + structure.parameters
            + ProcessTemplate[]
                 └─ WorkpointStructureSummaryGroup[]
                      └─ WorkpointStructureSummaryItem[]
```

## 3. 工艺解析结果 `ResolvedStructureProcess`

| 字段 | 类型 | 说明 |
|---|---|---|
| `identity` | `string` | 用于汇总签名的稳定工艺身份；未知显式值也保留 |
| `label` | `string \| null` | 页面可读工艺名称 |
| `source` | `component_explicit \| structure_explicit \| unique_default \| unknown_explicit \| missing` | 解析来源 |

### 优先级

1. 构件参数中非空显式工艺；
2. 所属结构参数中非空显式工艺；
3. 当前工艺库中同构件类型唯一 `is_default=true` 的工艺；
4. 多默认或无默认时为 `missing`。

显式值存在但未匹配工艺库时为 `unknown_explicit`，不得继续降级到默认工艺。

## 4. 工点资源配置视图

沿用 `ResourceCatalogItem` 和 `ResourcePool`，不新增持久化字段。页面可见类型仍为：

```text
visibleTypes = unique(matchedSuggestionTypes ∪ configuredLocalPoolTypes)
```

| 业务字段 | 来源 | 规则 |
|---|---|---|
| 中文名称 | `resourceTypeLabel` | 已配置中文标签优先，其次内置中文名 |
| 当前投入 | `quantity` | 整数且不小于 0 |
| 可增上限 | `max_quantity` | 整数且不小于当前投入 |
| 启用状态 | 派生值 | `quantity > 0`；不作为独立 UI 输入 |

虚拟建议项仍是 `quantity=0`、`max_quantity=0`，仅在用户编辑或添加时生成当前工点唯一 `WORKPOINT_EXCLUSIVE` 记录。

## 5. 工点独享资源规范化

对 `scope_mode=WORKPOINT_EXCLUSIVE` 且 `workpoint_id` 非空的规范记录：

```text
normalizedQuantity = max(0, trunc(quantity or 0))
normalizedMaxQuantity = max(normalizedQuantity, trunc(max_quantity or normalizedQuantity))
enabled = normalizedQuantity > 0
```

- 该规则覆盖读取、添加、编辑和后续场景规范化。
- 数量为 0 不删除资源记录。
- `PROJECT_SHARED` 和没有规范工点身份的旧兼容记录保留现有 `enabled` 读取语义。
- 不批量重写历史存储；下一次相关保存自然持久化规范结果。

## 6. 页面详情状态

沿用现有 `ResourceWorkpointDetailState`：`idle`、`loading`、`ready`、`error`。`ready` 状态下由同一个 `workpoint` 同时生成左侧结构汇总和右侧资源建议；请求身份不匹配时不更新任一侧。

窄屏布局只改变排列方式，不创建新的业务状态。

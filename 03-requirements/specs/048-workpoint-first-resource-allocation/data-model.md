# 数据模型：工点主导资源配置与范围共享流转

## 1. 模型原则

- `ScenarioInput.resource_pools` 继续是唯一资源配置权威集合。
- `ResourcePool.id` 是配置记录和共享池的唯一身份；`type` 只表示任务需求匹配类型，不再唯一定位配置。
- 新工点本地资源和新共享池使用同一 `ResourcePool` 契约，通过 `scope_mode + workpoint_id` 区分。
- `WorkpointResourceOverride` 仅保留为 047 历史输入兼容，不用于 048 新写入。
- `ScheduleInput.resources` 保存已解析的实例来源和合法工点，求解器不回读页面状态。

## 2. 枚举

```text
ResourceScopeMode = PROJECT_SHARED | WORKPOINT_EXCLUSIVE
ResourceMode = LIMITED | UNLIMITED
ResourcePoolRecordKind = WORKPOINT_LOCAL | RANGE_SHARED | LEGACY_EXCLUSIVE
```

`ResourcePoolRecordKind` 是标准化阶段的派生分类，不要求新增持久化枚举字段。

## 3. ResourcePool

在现有字段基础上增加 `workpoint_id`：

| 字段 | 类型 | 默认 | 规则 |
| --- | --- | --- | --- |
| `id` | string | 无 | 全场景唯一且稳定；任何更新、建议、结果和指纹均以此定位 |
| `type` | string | 无 | 标准资源类型；允许多个池相同 |
| `label` | string | 无 | 展示名称；不得作为合并或定位依据 |
| `resource_mode` | `LIMITED \| UNLIMITED` | `LIMITED` | 新工点本地和范围共享记录默认 `LIMITED` |
| `scope_mode` | `PROJECT_SHARED \| WORKPOINT_EXCLUSIVE` | 旧数据缺失时 `PROJECT_SHARED` | 共享或工点本地作用域 |
| `workpoint_id` | `string \| null` | `null` | 048 工点本地记录必填；共享记录必须为 `null` |
| `quantity` | `integer >= 0 \| null` | `0` | 当前投入；0 表示当前没有实例 |
| `max_quantity` | `integer >= 0 \| null` | 标准化为不小于 `quantity` | 增配/最少资源分析上限 |
| `enabled` | boolean | `true` | 是否允许作为受限资源参与当前候选 |
| `authorized_workpoint_ids` | `string[] \| null` | `null` | 共享池专用；`null`=当前全部桥梁工点，显式非空数组=固定范围 |
| `workpoint_overrides` | `WorkpointResourceOverride[]` | `[]` | 047 legacy 专用；048 新记录必须为空 |
| `calendar_id` | string | `continuous` | 沿用现有资源日历 |
| `cost_type` 等 | 既有类型 | 既有默认 | 沿用成本、计费和同结构绑定字段 |

### 3.1 新工点本地记录不变量

```text
scope_mode == WORKPOINT_EXCLUSIVE
workpoint_id != null
authorized_workpoint_ids == null
workpoint_overrides == []
(workpoint_id, type) 在所有新工点本地记录中唯一
```

- 工点必须属于当前 `project_data_version_id` 的桥梁工点。
- `quantity=0` 时记录仍可保留，但不展开当前命名资源。
- 目录补充为当前工点创建此类记录；移除本地资源优先保留数量 0 的显式状态，是否物理删除由页面动作明确决定。

### 3.2 新范围共享池不变量

```text
scope_mode == PROJECT_SHARED
workpoint_id == null
workpoint_overrides == []
authorized_workpoint_ids == null OR 非空且全部属于当前桥梁工点
```

- 同一 `type` 可有任意多个共享池。
- `authorized_workpoint_ids=null` 是动态全项目共享；不得序列化成当前工点列表快照后丢失语义。
- 显式空数组是无可用范围，保存必须阻断。
- 同一工点可以属于同类型多个共享池。

### 3.3 047 legacy 独享输入

```text
scope_mode == WORKPOINT_EXCLUSIVE
workpoint_id == null
authorized_workpoint_ids 为 null 或多工点集合
workpoint_overrides 可非空
```

该形态只允许进入统一兼容解析器，不允许新页面继续写出。解析器计算各工点有效值后生成新工点本地记录；无法无损展开时保持原载荷并阻断保存。

## 4. ResourceCatalogProjection（派生）

```text
resource_type: string
label: string
source: process_requirement | default_pool_metadata | configured_pool
default_calendar_id: string
default_max_quantity: integer >= 0
applicable_process_ids: list[string]
```

- 不作为独立持久化权威。
- 同一资源类型只形成一个目录项，稳定优先级为现有正式元数据 > 工艺映射 > 配置回填。
- “该工点任务可能使用”由当前工点任务/工艺需求与目录项匹配得到；用户仍可从完整目录补充。

## 5. EffectiveResourcePool（内部派生）

```text
effective_pool_id: string
source_pool_id: string
source_legacy_pool_id: string | null
resource_type: string
scope_mode: ResourceScopeMode
workpoint_id: string | null
eligible_workpoint_ids: list[string]
enabled: boolean
quantity: integer >= 0
max_quantity: integer >= quantity
calendar_id: string
cost fields: existing values
```

派生规则：

- 新工点本地记录产生一个有效池，`effective_pool_id=id`，eligible 仅含 `workpoint_id`。
- 每个新共享池产生一个有效池，`effective_pool_id=id`，eligible 为动态全部或显式集合。
- 旧共享池产生一个有效池，ID、数量和范围保持。
- 047 legacy 独享池无损展开时，每个工点产生一个有效池及一个规范新记录；迁移 ID 稳定可复现。
- 所有有效池按 `(resource_type,source_pool_id,workpoint_id,effective_pool_id)` 稳定排序。

## 6. Resource（ScheduleInput 命名实例）

沿用现有字段：

```text
id: string
type: string
pool_id: string
pool_label: string
scope_mode: ResourceScopeMode
eligible_workpoint_ids: list[string]
exclusive_workpoint_id: string | null
calendar_id: string
```

不变量：

- 工点本地实例 `pool_id` 指向本地记录 ID，eligible 仅含所属工点，`exclusive_workpoint_id` 等于所属工点。
- 共享实例 `pool_id` 指向独立共享池 ID，`exclusive_workpoint_id=null`，eligible 为池范围。
- 实例 ID 在场景中唯一稳定，但候选和求解不得解析该字符串判断作用域。
- 当前模式按 `quantity` 展开；最大模式按 `max_quantity` 展开。

## 7. Task 与候选关系

任务沿用 `bridge_id` 作为桥梁工点身份，先从工艺获得 `compatible_resource_types`。

```text
resource.type in task.compatible_resource_types
AND task.bridge_id in resource.eligible_workpoint_ids
AND (
  resource.scope_mode == PROJECT_SHARED
  OR resource.exclusive_workpoint_id == task.bridge_id
)
```

候选集合是所有满足条件的本地和共享实例并集，不设置本地优先硬规则。

## 8. ResourceGapDiagnostic

建议使用现有 `ValidationMessage` 承载稳定字段：

```text
code: RESOURCE_ALLOCATION_NO_LEGAL_CANDIDATE
level: error
subject_id: task_id
entity_refs: [task_id, workpoint_id, resource_type, ...relevant_pool_ids]
details:
  task_id: string
  workpoint_id: string | null
  resource_type: string
  relevant_pool_ids: list[string]
  reason: LOCAL_QUANTITY_ZERO
        | LOCAL_DISABLED
        | SHARED_DISABLED
        | SHARED_SCOPE_MISMATCH
        | WORKPOINT_ID_INVALID
        | RESOURCE_TYPE_UNCONFIGURED
```

若现有 `ValidationMessage` 不扩展 `details`，上述字段必须进入 `source_summary` 或稳定的结果诊断对象，不得只存在于中文消息文本。

## 9. ScopedResourceQuantityUpdate

沿用并强化现有结构：

```text
resource_pool_id: string
workpoint_id: string | null
quantity: integer >= 0
```

- 共享池：`workpoint_id=null`，按 `resource_pool_id` 更新唯一池。
- 工点本地池：`workpoint_id` 必须等于池的 `workpoint_id`。
- 旧 `resource_updates: map[type,quantity]` 只在类型唯一对应一个旧共享池时解析；其他情况返回歧义错误。
- 所有建议不得修改 `scope_mode/workpoint_id/authorized_workpoint_ids`。

## 10. 结果与计划身份

资源数量结果由类型级 map 迁移为逐池列表：

```text
ResourcePoolQuantityResult:
  resource_pool_id: string
  resource_type: string
  workpoint_id: string | null
  scope_mode: ResourceScopeMode
  current_quantity: integer
  recommended_quantity: integer
  max_quantity: integer
  eligible_workpoint_ids: list[string]
```

旧 `input_resource_quantities: map[type,quantity]` 可保留兼容展示，但同类型多池时不得作为权威结果；新逻辑只读取逐池列表。

## 11. 标准化与迁移状态

```text
raw legacy pools
  -> validate ids/types/quantities
  -> preserve PROJECT_SHARED as one pool
  -> resolve legacy WORKPOINT_EXCLUSIVE effective values
      -> lossless: materialize workpoint-local pools
      -> not lossless: migration_blocked + preserve raw payload
  -> canonical resource_pools
  -> effective pools
  -> named resources
  -> task candidates
  -> solve result + pool diagnostics
```

配置编辑状态：

```text
loaded -> editing -> validating -> saving -> saved
                                -> error -> retry
saved semantic change -> generated/solve/AI/comparison/forecast stale
project version change -> old requests ignored
```

## 12. 指纹规范

- 资源池先按 `id` 排序。
- `authorized_workpoint_ids` 去重排序；`null` 保持为 `null`，不得转成列表。
- legacy overrides 按 `workpoint_id` 排序，仅用于兼容输入指纹。
- 保留 `id/type/scope_mode/workpoint_id/quantity/max_quantity/enabled/calendar_id/cost/same_structure` 等求解相关字段。
- 资源池列表顺序变化不得改变指纹；单池身份、工点、范围或数量语义变化必须改变指纹。

## 13. 容量与互斥不变量

- 每个命名实例同一时间最多分配一个任务。
- 每个有效池的容量只来自自身数量，不与同类型其他池相加后回写。
- 固定资源当前模式的无候选判断以实际 `quantity` 实例为准。
- 增配/最少资源模式以每池 `max_quantity` 为上界，推荐结果按池返回。
- 多池重叠范围的容量下界不得把同一任务重复计入每个池；只对唯一候选池任务做逐池下界或使用候选池集合联合下界。
- 跨工点共享不新增转场持续时间、费用、人工顺序或隐藏优先级。

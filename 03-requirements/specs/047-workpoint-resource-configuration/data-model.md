# 数据模型：工点级资源配置

## 1. 枚举

```text
ResourceScopeMode = PROJECT_SHARED | WORKPOINT_EXCLUSIVE
```

兼容默认：字段缺失时为 `PROJECT_SHARED`。

## 2. ResourcePool

在现有字段上增加：

| 字段 | 类型 | 默认 | 校验 |
| --- | --- | --- | --- |
| `scope_mode` | `ResourceScopeMode` | `PROJECT_SHARED` | 必须是枚举值 |
| `authorized_workpoint_ids` | `list[str] \| null` | `null` | `null`=当前版本全部桥梁工点；数组去重排序且 ID 必须存在 |
| `workpoint_overrides` | `list[WorkpointResourceOverride]` | `[]` | 同一 `workpoint_id` 最多一条；按 ID 稳定排序 |

既有 `quantity/max_quantity` 校验保持：非负整数，标准化后 `max_quantity >= quantity`。不新增 `min_quantity`。

## 3. WorkpointResourceOverride

```text
workpoint_id: string
enabled: boolean | null
quantity: integer >= 0 | null
max_quantity: integer >= 0 | null
```

规则：

- `null` 字段继承所属 `ResourcePool`；
- 覆盖有效值标准化后满足 `max_quantity >= quantity`；
- ID 必须属于同一项目主数据版本的桥梁工点；
- 恢复继承时删除覆盖记录或把所有可覆盖字段归一为空，不能复制全局值伪装覆盖。

## 4. EffectiveResourcePool（内部派生）

```text
effective_pool_id: string
source_pool_id: string
resource_type: string
scope_mode: ResourceScopeMode
workpoint_id: string | null
eligible_workpoint_ids: list[string]
enabled: boolean
quantity: integer >= 0
max_quantity: integer >= quantity
calendar_id: string
inheritance_source: global | overridden | legacy_migrated
```

派生基数：

- 共享模式：每个源池 0 或 1 个有效池；
- 独享模式：每个获准桥梁工点 0 或 1 个有效池。

显式 `UNLIMITED`、停用或有效上限为 0 不展开命名资源，并沿用既有统一默认充足 warning；已启用、`LIMITED`、正上限的有效池却无合法候选是错误。未配置工点必须先继承，不能被归为上述显式状态。

## 5. Resource（ScheduleInput）

新增：

```text
scope_mode: ResourceScopeMode
eligible_workpoint_ids: list[string]
exclusive_workpoint_id: string | null
```

不变量：

- 共享实例 `exclusive_workpoint_id=null`，eligible 为获准集合；
- 独享实例 eligible 仅有一个 ID，且等于 `exclusive_workpoint_id`；
- `id` 唯一稳定，但求解不解析它。

## 6. Task 与候选关系

任务沿用 `bridge_id` 作为桥梁工点身份。候选关系：

```text
resource.type in task.compatible_resource_types
AND task.bridge_id in resource.eligible_workpoint_ids
AND (resource.scope_mode != WORKPOINT_EXCLUSIVE
     OR resource.exclusive_workpoint_id == task.bridge_id)
```

任务缺 `bridge_id` 或受限任务候选为空时产生阻断诊断。

## 7. AI 结构化数量更新

建议新增兼容字段：

```text
ScopedResourceQuantityUpdate:
  resource_pool_id: string
  workpoint_id: string | null
  quantity: integer >= 0

ResourceAssistantUpdatePlanRequest:
  resource_updates: map[string, integer]       # 旧共享格式，保留
  scoped_resource_updates: list[ScopedResourceQuantityUpdate] = []
```

共享更新 `workpoint_id=null`；独享更新必须带工点 ID。AI 方案内的 `ResourcePool.workpoint_overrides` 保存建议值或使用等价明确结构，但不得丢失原作用域。

## 8. 标准化与状态转换

```text
legacy raw pool
  -> scope_mode=PROJECT_SHARED
  -> authorized_workpoint_ids=null
  -> workpoint_overrides=[]
  -> normalized ResourcePool
  -> EffectiveResourcePool(s)
  -> named Resource(s)
  -> candidate map
  -> ScheduleResult + diagnostics
```

配置状态：

```text
loaded -> editing -> saving -> saved
                   -> error -> retry
saved semantic change -> generated/solve/AI/comparison stale
```

项目数据版本变化时，旧工点覆盖先进入 `version_mismatch` 诊断，不能自动重绑定。

## 9. 指纹规范

指纹输入使用标准化后的资源池：

- pools 按 `id` 排序；
- `authorized_workpoint_ids` 去重排序；
- overrides 按 `workpoint_id` 排序；
- 保留 `scope_mode/enabled/quantity/max_quantity/calendar_id` 及现有求解相关字段；
- 等价顺序不得改变指纹，语义变化必须改变指纹。

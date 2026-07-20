# 数据模型：结构物匹配的中文资源目录

本功能新增的对象均为前端只读派生状态，不新增后端表、Pydantic 模型、持久化字段或迁移。

## 1. 中文资源目录项 `ResourceCatalogItem`

沿用现有前端目录项并收紧名称规则。

| 字段 | 类型 | 来源 | 规则 |
|---|---|---|---|
| `type` | `string` | 工艺 `resource_type` 或既有资源池 | 稳定技术标识；排除架桥机、梁场及生产线类型 |
| `label` | `string` | 已配置中文池名或内置中文名称 | 主显示名称必须含中文；未知自定义类型显示中文未命名提示 |
| `defaultCalendarId` | `string` | 既有目录投影 | 新增建议时沿用，不影响未配置建议 |
| `defaultMaxQuantity` | `number` | 既有池投影 | 虚拟建议行展示固定为 0；用户明确添加后才使用实际输入 |
| `applicableProcessIds` | `string[]` | 当前工艺库 | 去重、稳定排序 |

### 名称解析规则

1. 当前资源类型已配置池存在非空且含中文的 `label`：使用该名称。
2. 命中内置中文名称表：使用内置名称。
3. 未命中：主名称为“未命名资源”，并在次级位置展示 `type`。

## 2. 工点结构资源建议 `WorkpointResourceSuggestion`

实现可直接输出资源类型数组，也可在领域函数内部形成以下逻辑对象。

| 字段 | 类型 | 说明 |
|---|---|---|
| `workpointId` | `string` | 当前工点 ID |
| `resourceType` | `string` | 匹配后的资源类型 |
| `sourceComponentTypes` | `string[]` | 触发该建议的构件类型，用于测试/诊断，可不进入 UI 状态 |
| `sourceProcessIds` | `string[]` | 采用的显式或默认工艺，用于确定性测试，可不进入 UI 状态 |

### 验证规则

- 只读取当前工点内启用构件；禁用构件不产生建议。
- `continuous_unit` 等上部结构按现有排程投影映射为资源构件类型。
- 显式有效工艺优先；没有显式工艺时只使用同构件类型的唯一默认工艺。
- 工艺没有资源类型时不产生建议。
- 以 `resourceType` 去重，并按稳定顺序输出。
- 建议不包含数量、上限、启用状态或资源实例 ID。

## 3. 工点详情加载状态 `ResourceWorkpointDetailState`

| 状态 | 必需字段 | 页面行为 |
|---|---|---|
| `idle` | 无 | 尚无可选工点，不请求详情 |
| `loading` | `versionId`、`workpointId` | 清空上一工点建议，显示加载态 |
| `ready` | `versionId`、`workpointId`、`workpoint` | 计算并展示建议与已配置资源并集 |
| `error` | `versionId`、`workpointId`、`message` | 显示失败和重试，不用全目录填充 |

### 状态转换

```text
idle ──选择工点──> loading ──详情成功且身份仍匹配──> ready
                         └──详情失败且身份仍匹配──> error
error ──重试──> loading
ready/error/loading ──切换版本或工点──> loading
任意状态 ──没有可选工点──> idle
```

旧请求响应的 `versionId + workpointId` 与当前身份不一致时不得触发状态转换。

## 4. 页面可见资源行

页面可见类型集合：

```text
visibleTypes = unique(matchedSuggestionTypes ∪ configuredLocalPoolTypes)
```

- 命中已配置池：展示并编辑该池保存的 `quantity`、`max_quantity`、`enabled`、日历和成本字段。
- 仅命中建议：展示 `quantity=0`、`max_quantity=0`、未配置，不写入场景。
- 仅命中已配置池：即使当前结构不再匹配也继续展示，直到用户明确移除。
- 添加建议：为当前工点和类型创建唯一 `WORKPOINT_EXCLUSIVE` 池；不创建 `PROJECT_SHARED`。

## 5. 关系与兼容边界

```text
ProjectMasterWorkpoint(version)
  └─ structures/components(enabled)
       └─ ProcessTemplate(explicit/default)
            └─ resource type
                 ├─ Chinese catalog item
                 └─ virtual suggestion row

ResourcePool(WORKPOINT_EXCLUSIVE)
  └─ overrides virtual row when workpoint + type match
```

求解器只读取已保存且现有规则认定有效的资源池；虚拟建议不会进入 API 请求或候选生成。现有显式共享输入兼容逻辑不在本功能中修改。

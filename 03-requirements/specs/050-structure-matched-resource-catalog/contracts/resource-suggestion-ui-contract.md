# 工点结构资源建议 UI 契约

## 1. 目标

定义资源配置页面如何复用当前项目主数据工点详情、推导建议资源并呈现中文名称。本契约不新增公共 API，不改变现有后端 response schema。

## 2. 权威读取接口

```http
GET /api/project-master/versions/{version_id}/workpoints/{workpoint_id}
```

页面只在以下条件同时满足时接受响应：

- `version_id` 等于当前场景的 `project_data_version_id`；
- `workpoint_id` 等于资源页当前选中的桥梁工点；
- 该请求仍是当前身份的最新请求。

页面使用响应中的以下既有字段：

- 工点：`workpoint_id`、`workpoint_type`、`structures`；
- 结构：`structure_id`、`structure_type`、`parameters`、`components`；
- 构件：`component_id`、`component_type`、`enabled`、`parameters`；
- 参数：`parameter_code`、`value`。

工点列表接口继续只用于导航和排序，不能替代详情作为结构匹配输入。

## 3. 结构到资源的投影契约

### 3.1 输入

- 当前版本的单个桥梁工点详情；
- 当前 `scenario.process_library`；
- 内置结构类型、桩基方法和资源类型映射。

### 3.2 工艺选择

对每个有效构件类型：

1. 若构件或结构参数提供有效的 `method_id` 或等价工艺标识，选择 `process.id` 或 `process.method_id` 匹配的工艺；
2. 否则选择该构件类型中唯一 `is_default=true` 的工艺；
3. 没有可确定工艺时不产生资源类型，不选择任意第一条工艺。

桩基方法必须通过现有桩基方法映射得到旋挖、回旋、冲击或人工挖孔资源，不能一次加入全部方法。

### 3.3 上部结构映射

至少保持与现有项目主数据排程投影一致：

| 项目主数据结构类型 | 资源匹配构件类型 |
|---|---|
| `continuous_unit` | `cast_in_place_continuous_beam` |
| `cast_in_place_unit` | `cast_in_place_box_beam` |
| `simple_span` | 仅在存在允许配置且未被排除的资源映射时匹配 |

下部结构使用启用构件的投影类型；桥台等既有特殊投影沿用当前排程映射，不自行发明资源。

### 3.4 输出

- 输出资源类型字符串集合；
- 相同类型去重；
- 等价输入输出顺序固定；
- 排除 `girder_erector`、`beam_yard`、`beam_yard_production_line`；
- 结果不包含资源数量、上限、启用状态或实例。

## 4. 中文名称契约

标准内置类型主名称必须来自统一中文名称表，包括但不限于：

| 资源类型 | 中文主名称 |
|---|---|
| `rotary_drill` | 旋挖钻机 |
| `circulation_drill` | 回旋钻机 |
| `impact_drill` | 冲击钻机 |
| `manual_pile_team` | 人工挖孔班组 |
| `cap_team` | 承台模板 |
| `pier_body_team` | 墩柱模板 |
| `cap_beam_team` | 盖梁模板 |
| `cast_in_place_continuous_beam_team` | 连续梁班组 |

名称解析优先级：

1. 同类型已配置资源池的非空中文 `label`；
2. 内置中文名称；
3. “未命名资源”，同时次级显示类型代码。

补充资源下拉框、默认建议行、已配置资源行和资源助手不得各自维护含义冲突的标准名称。

## 5. 页面状态契约

- **加载**：选择或版本变化后清空上一身份的建议，显示“正在加载当前工点结构”。
- **失败**：显示错误与重试；不得展示全项目工艺目录作为建议。
- **空结构/无映射**：显示“当前工点没有匹配到待配置资源”；完整目录仍可用于人工补充。
- **就绪**：显示匹配建议和当前工点已配置资源的并集。
- **乱序响应**：旧版本或旧工点响应必须丢弃。

## 6. 编辑与持久化契约

- 建议行初始 `quantity=0`、`max_quantity=0`、状态“未配置”。
- 只查看、切换工点或保存其他配置不得创建建议资源记录。
- 用户添加或编辑后，只创建当前工点的 `WORKPOINT_EXCLUSIVE` 记录。
- 已配置但不再匹配的资源继续显示并保留原字段。
- 不创建或恢复 `PROJECT_SHARED`，不改变求解器对显式共享输入的兼容读取。

## 7. 兼容与验证

- 后端和 Demo API 镜像的工点详情接口保持原样；本功能只验证其现有响应能支撑前端投影。
- 领域样例必须覆盖四种桩基方法、连续梁、普通下部结构、禁用构件、重复类型、未知自定义类型和空资源项目。
- 页面样例必须覆盖工点/版本快速切换、详情失败、无结构空态、建议不持久化及已配置资源保留。

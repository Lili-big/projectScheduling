# 数据模型：架梁双幅线路拓扑

## 1. ProjectMasterRoutePlacement（项目主数据线路落位）

表示一个项目工点在某一幅别线路上的可追溯位置。一工点可以有左、右各一条落位；单侧互通工点只有一条。

| 字段 | 类型 | 规则 |
| --- | --- | --- |
| `placement_id` | string | 项目版本内稳定唯一，不依赖显示名称 |
| `workpoint_id` | string | 必须引用同一快照中的工点 |
| `side` | `left/right` | 必填；不得使用 `shared/none/unknown` |
| `mileage_prefix` | string | 必填并标准化大写；主线左幅 `ZK`、右幅 `K`，互通可为 `AK/BK/B1K` |
| `start_mileage_m` | number? | 以米计；显式数据用于严格校验，缺失时生成诊断 |
| `end_mileage_m` | number? | 以米计；不得小于起点 |
| `spatial_group_id` | string | 必填；源 Excel 同行或等价已确认关系的稳定组标识 |
| `display_order` | integer | 非负；同一项目版本内决定空间组和组内稳定展示顺序 |
| `source` | SourceEvidence? | 工作表、行、列区块或其他来源证据 |

### 验证不变量

- 同一项目版本中 `placement_id` 唯一。
- 同一工点同一 `side` 最多一条落位；重复记录阻断导入。
- `start_mileage_m/end_mileage_m` 必须同时存在或同时缺失。
- 同一 `side + mileage_prefix` 的显式记录可执行区间重叠和间隙校验；跨 side 或跨 prefix 不直接比较。
- 相同 `spatial_group_id` 可以一对一、一对空或一对多；一对多保留全部节点并提示，不丢弃。

## 2. ProjectMasterSnapshot（扩展）

| 新字段 | 类型 | 规则 |
| --- | --- | --- |
| `route_placements` | `ProjectMasterRoutePlacement[]` | 默认空；旧数据库和旧 1.0 模板保持可加载 |

### 持久化与模板

- SQLite schema v2 新增 `route_placements` 表，以 `version_id + placement_id` 为主键并外键引用 `workpoints`。
- 新版 Excel 导出增加可选工作表“线路关系”。解析器接受既有 1.0 模板；没有该表时返回空集合，由线路图投影负责兼容推断。
- 确认版本内容不原地补写。显式线路落位只能随新导入版本进入主数据。

## 3. LineGraphNode（双幅线路节点 v2）

| 字段 | 类型 | 规则 |
| --- | --- | --- |
| `node_id` | string | 桥梁继续为 `<workpoint_id>:<side>`；非桥梁同样按 side 生成 |
| `project_master_workpoint_id` | string | 引用原工点 |
| `name` | string | 显示名称；不得用于业务匹配 |
| `node_type` | enum | 沿用 bridge/roadbed/tunnel/culvert/access/connection |
| `side` | `left/right` | v2 可计算节点必须属于两条主轴之一 |
| `alignment_code` | string? | 兼容字段，v2 表示原始里程前缀，不表示展示线路 |
| `start_mileage_m/end_mileage_m` | number? | 对应幅别落位里程；不得使用左右合并区间替代显式分幅值 |
| `spatial_group_id` | string | 空间对应组；兼容投影使用明确的 `inferred:*` 标识，不伪造 Excel 行号 |
| `display_order` | integer | 决定两条线路共享栅格序位 |
| `placement_source` | `explicit/inferred` | 标记线路落位证据等级 |
| 其他既有字段 | 原类型 | `sort_order/requires_erection/beam_demands/source_refs/current_plan_finish_date` 保留 |

## 4. LineGraphSnapshot（升级）

| 字段 | 类型 | 规则 |
| --- | --- | --- |
| `projection_version` | `girder-plan-line-graph/v2` | 固定值并进入输入指纹 |
| `nodes` | LineGraphNode[] | 仅含 left/right 可投影节点；无法归属对象以诊断保留，不伪造 unknown 节点 |
| `edges` | LineGraphEdge[] | 同幅自动相邻边和已确认人工边；空间对应组本身不生成边 |
| `diagnostics` | SimulationDiagnostic[] | 包括显式数据错误、兼容推断提示和连接阻断 |

### 自动投影优先级

1. 使用 `ProjectMasterRoutePlacement` 显式落位。
2. 缺少显式落位时，从该工点结构物的 `left/right` 集合生成兼容落位。
3. `alignment_code=ZK/K` 时分别映射左 `ZK`、右 `K`；单前缀保持原值。
4. 兼容落位使用工点 `sort_order` 作为显示顺序并标记 `inferred`；不进行基于合并里程的严格重叠阻断。
5. 无法得到 left/right 时生成 `ROUTE_SIDE_MISSING` 阻断诊断。

## 5. BeamYardPlan（兼容扩展）

| 新字段 | 类型 | 规则 |
| --- | --- | --- |
| `deployment_node_id` | string? | 新保存方案必须写入稳定双幅节点 ID；旧方案可为空并走兼容解析 |

### 梁场定位规则

- 有 `deployment_node_id` 时必须精确引用当前 v2 图节点。
- 旧方案无节点 ID 时，用原 `alignment_code + mileage_m` 匹配；唯一匹配则可迁移使用，多匹配或无匹配时阻断并要求重新选择。
- 兼容解析不原地覆盖历史方案；用户再次保存新版本时写入节点 ID。

## 6. 状态与失效

```text
v1 线路图/旧运行
        │ 投影规则或线路落位变化
        ▼
      stale ──重新校验/计算──> v2 calculated ──确认──> confirmed
```

- 方案的桥梁目标 ID 可唯一映射时保留；非桥梁路径和自动边重新展开。
- v1 运行快照保留历史可读性，但不得作为当前结果。
- 线路落位、项目版本、投影版本、人工连接或梁场部署变化都进入输入指纹并触发失效。

## 7. 诊断编码

| 编码 | 默认级别 | 触发条件 |
| --- | --- | --- |
| `ROUTE_SIDE_MISSING` | blocking | 无显式落位且结构物不能确定 left/right |
| `ROUTE_PLACEMENT_INFERRED` | warning | 旧版本使用结构物幅别/稳定排序兼容投影 |
| `ROUTE_SPATIAL_GROUP_MISSING` | warning | 显式落位缺少可追溯空间组 |
| `ROUTE_PLACEMENT_DUPLICATE` | blocking | 同一工点同一幅别存在多条冲突落位 |
| `ROUTE_MILEAGE_MISSING` | blocking | 显式落位缺少起点或终点 |
| `ROUTE_MILEAGE_RANGE_INVALID` | blocking | 显式落位终点小于起点 |
| `MILEAGE_OVERLAP` | blocking | 同幅、同前缀、显式落位的真实区间重叠 |
| `LINE_GRAPH_GAP` | blocking | 同幅可比较序列或明确连接链存在未确认断点 |
| `YARD_DEPLOYMENT_AMBIGUOUS` | blocking | 旧梁场部署无法唯一映射到双幅节点 |


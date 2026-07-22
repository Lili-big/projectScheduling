# 数据模型：连续结构桥梁三段式线路节点

## 1. 输入事实（复用项目主数据）

本功能不新增项目主数据实体或持久化字段，仅读取以下现有事实：

| 输入 | 单位/类型 | 规则 |
| --- | --- | --- |
| `ProjectMasterRoutePlacement.side` | `left/right` | 每个桥梁幅别独立分段 |
| `start_mileage_m/end_mileage_m` | 米 | 必须同时存在且终点大于起点 |
| `ProjectMasterStructure.structure_type` | string | `continuous_unit` 为连续结构权威类型 |
| `side` | `left/right` | 必须与线路落位幅别一致 |
| `span_index` | 正整数 | 决定上部结构先后顺序 |
| `span_length_m` | 正数米 | 累计计算区段边界 |
| `components/beam_count_per_span` | 片 | 只汇总至所属引桥段 |
| `current_plan_finish_date/planned_finish_date` | 日期 | 只汇总所属区段结构 |

## 2. BridgeRouteSegmentProjection（内部派生）

表示一个桥梁幅别在生成线路图前的区段结果，不持久化。

| 字段 | 类型 | 规则 |
| --- | --- | --- |
| `kind` | enum | `approach_small/continuous/approach_large` |
| `start_mileage_m/end_mileage_m` | number | 首尾连续、长度大于 0 |
| `structures` | ProjectMasterStructure[] | 按跨序连续且不跨区段复用 |
| `source_refs` | string[] | 区段结构稳定 ID，至少一个 |

### 生成不变量

1. 一个符合条件的桥梁幅别恰好有三个区段。
2. `small.end == continuous.start`，`continuous.end == large.start`。
3. 首段起点等于线路落位起点，末段终点等于线路落位终点。
4. 每个结构只属于一个区段；三区段结构并集等于该幅参与分段的有序上部结构集合。
5. 累计结构总长与落位总长差值 `<= 1m`；超过则无可计算分段输出。

## 3. LineGraphNodeV3（共享契约）

| 字段 | 类型 | 规则 |
| --- | --- | --- |
| `node_id` | string | 未分段沿用 `<workpoint_id>:<side>`；分段为 `<workpoint_id>:<side>:<bridge_segment_kind>` |
| `project_master_workpoint_id` | string | 三区段均引用原桥梁工点 |
| `name` | string | `原工点名·左/右幅·小里程引桥段/连续结构段/大里程引桥段` |
| `node_type` | enum | 三区段均为 `bridge` |
| `bridge_segment_kind` | enum? | 分段节点必填；普通节点为空 |
| `side` | `left/right` | 与线路落位一致 |
| `alignment_code` | string | 保留 ZK/K/AK/BK/B1K 等原始前缀 |
| `start_mileage_m/end_mileage_m` | number | 区段真实起终里程 |
| `spatial_group_id` | string | 三区段沿用父工点空间对应组，不拆伪组 |
| `display_order` | integer | 三区段沿用父工点空间序位；段内按里程排序 |
| `requires_erection` | boolean | 仅有预制梁需求的引桥段为 true；连续段固定 false |
| `beam_demands` | BeamDemand[] | 只来自本区段结构；连续段为空 |
| `source_refs` | string[] | 只引用本区段结构 |
| `current_plan_finish_date` | date? | 本区段结构计划完成日期最大值；无值则 null |

## 4. LineGraphSnapshotV3

| 字段 | 类型 | 规则 |
| --- | --- | --- |
| `projection_version` | `girder-plan-line-graph/v3` | 固定并进入指纹 |
| `nodes` | LineGraphNodeV3[] | 普通节点、未分段桥梁和三段节点集合 |
| `edges` | LineGraphEdge[] | 同幅同前缀按真实里程相邻；三区段内部自然相邻 |
| `status` | `ready/warning/blocking` | 分段证据冲突时 blocking |
| `diagnostics` | SimulationDiagnostic[] | 对象级分段诊断 |

### 路线行为

```text
人工顺序：approach_small ───────────────────> approach_large
自动展开：approach_small → continuous → approach_large
```

- `ManualRoutePlan.target_node_ids` 只允许 `requires_erection=true` 的引桥段。
- `continuous` 可作为梁场到首个目标、相邻目标间或目标后的中间通行节点。
- 经过连续段时沿用桥梁中间节点的 `post_erection_passage_buffer_days` 控制规则；本功能不新增缓冲参数。

## 5. 兼容和状态转换

```text
v2 整桥目标方案/运行
        │ v3 投影产生新的节点 ID 和指纹
        ▼
      stale ──用户重新选择两个引桥目标──> v3 draft/ready ──计算──> calculated
```

- 非连续结构桥梁节点 ID 不变，既有顺序可继续匹配。
- 分段桥梁旧 `<workpoint_id>:<side>` 不映射到任何一个新目标。
- 旧运行保留历史可读，不得确认或复用为 v3 当前成果。

## 6. 诊断编码

| 编码 | 级别 | 触发条件 |
| --- | --- | --- |
| `BRIDGE_SEGMENT_STRUCTURE_DATA_MISSING` | blocking | 参与分段结构缺 `span_index`、正数 `span_length_m` 或源引用 |
| `BRIDGE_SEGMENT_CONTINUOUS_BLOCK_AMBIGUOUS` | blocking | 同幅出现两个及以上不相邻连续区块 |
| `BRIDGE_SEGMENT_APPROACH_MISSING` | blocking | 连续区块前或后没有正长度引桥 |
| `BRIDGE_SEGMENT_LENGTH_MISMATCH` | blocking | 结构累计长度与落位长度相差超过 1 米 |
| `BRIDGE_SEGMENT_PRECAST_CONFLICT` | blocking | 连续结构区块含启用预制梁需求 |

异常时可返回旧整桥节点便于页面定位，但快照状态必须为 `blocking`，不得计算或确认。

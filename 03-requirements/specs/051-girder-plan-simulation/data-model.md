# 数据模型：架梁计划推演

## 1. 标识与共同约定

- 所有日期使用项目时区下的 ISO `YYYY-MM-DD` 自然日。
- 梁片数量使用非负整数“片”；生产与架设能力使用正数或零的“片/天”。
- 桥梁排序目标使用稳定键 `(project_master_workpoint_id, side)`；`side` 正式计算只允许 `left` 或 `right`。
- 项目、工点、结构、梁型、梁场、线路、方案和快照均使用稳定 ID，不以显示名称匹配。
- 所有版本化写入携带 `input_fingerprint`；结果快照携带创建时的项目版本和方案指纹。

## 2. LineGraphSnapshot（线路图快照）

表示一个已确认项目主数据版本派生的只读线路拓扑。

| 字段 | 类型 | 规则 |
|---|---|---|
| `line_graph_id` | string | 由项目版本内容和投影版本生成稳定 ID |
| `project_master_version_id` | string | 必须引用 `confirmed` 项目主数据版本 |
| `project_id` | string | 与项目版本一致 |
| `projection_version` | string | 首版固定为 `girder-plan-line-graph/v1` |
| `status` | enum | `ready/warning/blocking`，存在关键投影错误时阻断 |
| `nodes` | `LineGraphNode[]` | 按走廊、里程、稳定 ID 排序 |
| `edges` | `LineGraphEdge[]` | 自动相邻边和人工确认边的集合 |
| `diagnostics` | `SimulationDiagnostic[]` | 缺失、冲突、多义和断点诊断 |
| `input_fingerprint` | string | 项目版本和投影规则的稳定指纹 |

### LineGraphNode

| 字段 | 类型 | 规则 |
|---|---|---|
| `node_id` | string | 工点节点使用 `workpoint_id:side` 或 `workpoint_id:unknown` |
| `project_master_workpoint_id` | string? | 权威工点引用；纯连接节点可为空 |
| `name` | string | 仅显示，不参与匹配 |
| `node_type` | enum | `yard/bridge/roadbed/tunnel/culvert/access/connection` |
| `side` | enum | `left/right/unknown` |
| `alignment_code` | string? | 计算要求必填；缺失时保留空值并阻断，不伪造默认线路 |
| `start_mileage_m` | number? | 计算要求必填且不大于结束里程；缺失时保留空值诊断 |
| `end_mileage_m` | number? | 计算要求必填且不小于开始里程；缺失时保留空值诊断 |
| `sort_order` | integer | 仅用于确定性并列排序 |
| `requires_erection` | boolean | 只有具备片级需求的桥梁幅别为 true |
| `beam_demands` | `BeamDemand[]` | 非待架节点为空 |
| `source_refs` | string[] | 指向项目主数据结构/构件稳定 ID |

### BeamDemand

| 字段 | 类型 | 规则 |
|---|---|---|
| `beam_type_id` | string | 梁型稳定编码；不得为空 |
| `beam_type_name` | string | 显示名 |
| `span_count` | integer | 大于 0 |
| `beam_count` | integer | 大于 0，表示该桥梁幅别该梁型总片数 |
| `span_refs` | string[] | 可追溯到分跨/上部结构 ID |

### LineGraphEdge

| 字段 | 类型 | 规则 |
|---|---|---|
| `edge_id` | string | 稳定 ID |
| `from_node_id` / `to_node_id` | string | 必须引用同一快照节点 |
| `direction` | enum | `forward/reverse/bidirectional` |
| `source` | enum | `alignment_adjacency/manual_connection` |
| `transfer_days` | integer | 大于等于 0；缺失时使用方案默认值 |
| `confirmation` | `ConnectionConfirmation?` | 人工连接必填 |

### ConnectionConfirmation

| 字段 | 类型 | 规则 |
|---|---|---|
| `reason` | string | 必填非空 |
| `confirmed_by` | string | 必填非空 |
| `confirmed_at` | datetime | 必填 |

## 3. GirderPlanScenarioVersion（计划推演方案版本）

表示用户保存的一次独立策划输入。

| 字段 | 类型 | 规则 |
|---|---|---|
| `scenario_version_id` | string | 稳定 ID |
| `scenario_id` | string | 同一方案族稳定 ID |
| `project_id` | string | 必填 |
| `project_master_version_id` | string | 必须为已确认版本 |
| `line_graph_id` | string | 必须与项目版本匹配 |
| `version_no` | integer | 同方案族从 1 递增 |
| `status` | enum | `draft/ready/calculated/confirmed/stale/blocked` |
| `beam_yards` | `BeamYardPlan[]` | 至少一个启用梁场才能 ready |
| `erection_lines` | `ErectionLinePlan[]` | 每个启用梁场恰好一个 |
| `route_plans` | `ManualRoutePlan[]` | 每个启用梁场恰好一个 |
| `connection_overrides` | `LineGraphEdge[]` | 仅人工确认连接边 |
| `parameters` | `GirderPlanSimulationParameters` | 计算口径 |
| `input_fingerprint` | string | 项目、线路、能力、顺序、参数的稳定指纹 |
| `created_by` / `created_at` | string/datetime | 必填 |
| `confirmed_by` / `confirmed_at` / `confirmation_reason` | nullable | 只有 confirmed 时必填 |

### 状态转换

```text
draft --校验通过--> ready --计算成功--> calculated --独立确认--> confirmed
  |                    |                  |                   |
  +--校验阻断--------> blocked <---------+                   |
                       ^                                      |
                       +---------- 输入或项目版本变化 --------+--> stale
```

- `blocked` 可通过创建新版本修复，不覆盖原版本。
- `calculated` 和 `confirmed` 对应的运行快照输入变化后转为 `stale`。
- 独立确认不触发任何现有专项或计划发布状态转换。

### BeamYardPlan

| 字段 | 类型 | 规则 |
|---|---|---|
| `beam_yard_id` | string | 方案内唯一且版本间稳定 |
| `name` | string | 必填 |
| `alignment_code` | string | 必须存在线路图 |
| `mileage_m` | number | 必须位于或可连接到所属走廊 |
| `production_start_date` | date | 必填 |
| `capacities` | `BeamTypeProductionCapacity[]` | 梁型不可重复 |
| `enabled` | boolean | 默认 true |

### BeamTypeProductionCapacity

| 字段 | 类型 | 规则 |
|---|---|---|
| `beam_type_id` | string | 必填 |
| `daily_capacity_pieces` | number | 大于等于 0 |
| `initial_inventory_pieces` | integer | 大于等于 0 |
| `max_inventory_pieces` | integer? | 若填写，必须大于等于期初库存 |

### ErectionLinePlan

| 字段 | 类型 | 规则 |
|---|---|---|
| `erection_line_id` | string | 方案内唯一 |
| `beam_yard_id` | string | 每个启用梁场恰好一条 |
| `available_date` | date | 必填 |
| `daily_erection_capacity_pieces` | number | 必须大于 0 |
| `first_erection_preparation_days` | integer | 大于等于 0 |
| `bridge_transfer_days` | integer | 大于等于 0 |
| `side_switch_days` | integer | 大于等于 0 |
| `enabled` | boolean | 与梁场有效性一致 |

### ManualRoutePlan

| 字段 | 类型 | 规则 |
|---|---|---|
| `route_plan_id` | string | 方案内唯一 |
| `beam_yard_id` | string | 每个启用梁场恰好一个 |
| `erection_line_id` | string | 必须属于同一梁场 |
| `name` | string | 必填 |
| `target_node_ids` | string[] | 只允许待架桥梁左右幅节点，顺序不可重复 |
| `confirmed_paths` | `ConfirmedPathSegment[]` | 相邻目标的自动/人工路径确认 |
| `confirmed` | boolean | false 时方案不能计算 |

### ConfirmedPathSegment

| 字段 | 类型 | 规则 |
|---|---|---|
| `from_target_node_id` / `to_target_node_id` | string | 必须是相邻目标；首段允许梁场节点作为起点 |
| `edge_ids` | string[] | 连续有向路径，不得断裂或循环 |
| `source` | enum | `unique_auto_path/user_selected_path` |

### GirderPlanSimulationParameters

| 字段 | 类型 | 默认/规则 |
|---|---|---|
| `default_transfer_days` | integer | 默认 0，非负 |
| `bridge_readiness_buffer_days` | integer | 默认值由方案显式保存，非负 |
| `roadbed_passage_buffer_days` | integer | 默认值由方案显式保存，非负 |
| `tunnel_passage_buffer_days` | integer | 默认值由方案显式保存，非负 |
| `access_passage_buffer_days` | integer | 默认值由方案显式保存，非负 |
| `post_erection_passage_buffer_days` | integer | 默认值由方案显式保存，非负 |
| `planning_horizon_end_date` | date | 必须晚于全部梁场投产/作业线可用日期 |
| `same_day_production_available` | literal false | 首期固定 false |

## 4. GirderPlanReadiness（方案就绪度）

| 字段 | 类型 | 规则 |
|---|---|---|
| `status` | enum | `ready/warning/blocking` |
| `checks` | `ReadinessCheck[]` | 每项有 code、status、message、entity_refs |
| `diagnostics` | `SimulationDiagnostic[]` | 可定位对象和修复建议 |
| `expanded_routes` | map<string, string[]> | 每条人工线路自动补齐后的完整节点顺序 |

阻断检查至少覆盖：项目版本、线路图、桥梁幅别/梁型/片数、梁场唯一作业线、分梁型能力、路线确认、唯一分配、路径连续、零架梁能力和循环依赖。

## 5. GirderPlanSimulationRun（计算快照）

| 字段 | 类型 | 规则 |
|---|---|---|
| `run_id` | string | 稳定 ID |
| `scenario_version_id` | string | 必填 |
| `project_master_version_id` | string | 与方案一致 |
| `status` | enum | `calculated/blocked/stale/confirmed` |
| `started_at` / `finished_at` | datetime | 必填 |
| `input_fingerprint` | string | 用于幂等复用和失效 |
| `result_fingerprint` | string | 对不含运行 ID 和时间戳的业务结果生成稳定指纹，用于确定性验收 |
| `reused_from_run_id` | string / nullable | 复用相同输入结果时标识来源运行；新计算为空 |
| `bridge_schedules` | `BridgeErectionSchedule[]` | 成功时覆盖全部目标 |
| `inventory_ledger` | `YardInventoryLedgerEntry[]` | 逐日、逐梁型 |
| `route_runs` | `PlannedRouteRun[]` | 每个有效梁场一条 |
| `workpoint_controls` | `WorkpointDeliveryControl[]` | 覆盖全部被使用工点 |
| `diagnostics` | `SimulationDiagnostic[]` | 阻断、警告和说明 |
| `confirmed_by` / `confirmed_at` / `confirmation_reason` | nullable | confirmed 时必填 |

### BridgeErectionSchedule

| 字段 | 类型 | 规则 |
|---|---|---|
| `target_node_id` | string | 桥梁＋幅别稳定节点 |
| `beam_yard_id` / `route_plan_id` | string | 唯一归属 |
| `sequence_index` | integer | 与人工顺序一致 |
| `start_date` / `finish_date` | date | 第一片开架至最后一片完成 |
| `total_beam_count` | integer | 等于各梁型需求合计 |
| `beam_type_counts` | map<string, integer> | 与主数据一致 |
| `daily_erection` | `DailyBeamConsumption[]` | 每日合计不超过片日能力 |
| `controlling_factors` | enum[] | `line_available/supply/transfer/side_switch/cross_route_passage` |

### YardInventoryLedgerEntry

| 字段 | 类型 | 规则 |
|---|---|---|
| `date` | date | 自然日 |
| `beam_yard_id` / `beam_type_id` | string | 组合唯一 |
| `opening_inventory_pieces` | integer | 非负 |
| `produced_pieces` | integer | 不超过当日产能和库存上限 |
| `erected_pieces` | integer | 不超过日初库存；当日产梁不可同日消耗 |
| `closing_inventory_pieces` | integer | `opening + produced - erected`，非负 |

### PlannedRouteRun

| 字段 | 类型 | 规则 |
|---|---|---|
| `route_plan_id` / `beam_yard_id` | string | 必填 |
| `start_date` / `finish_date` | date | 必填 |
| `expanded_node_ids` | string[] | 目标和自动补齐通行节点的完整顺序 |
| `waiting_days_by_reason` | map<string, integer> | 供应、通行等可解释等待 |

### WorkpointDeliveryControl

| 字段 | 类型 | 规则 |
|---|---|---|
| `node_id` / `project_master_workpoint_id` | string | 必填 |
| `side` | enum | `left/right/unknown` |
| `first_required_date` | date | 所有线路使用中的最早日期 |
| `latest_delivery_date` | date | 首次使用日减相应缓冲 |
| `buffer_days` | integer | 非负 |
| `controlling_source` | enum | `erection_start/roadbed_passage/tunnel_passage/access_passage/post_erection_passage` |
| `route_requirements` | `RouteDeliveryRequirement[]` | 保留全部线路明细 |
| `current_plan_finish_date` | date? | 若可从当前项目计划读取则填充 |
| `late_days` | integer? | 当前完成日晚于控制日时为正数 |
| `risk_status` | enum | `unknown/on_time/late` |

## 6. SimulationDiagnostic（诊断）

| 字段 | 类型 | 规则 |
|---|---|---|
| `level` | enum | `info/warning/error` |
| `code` | string | 稳定机器码 |
| `message` | string | 简体中文说明 |
| `subject_id` | string? | 首要对象 |
| `subject_type` | string? | 首要对象类型 |
| `entity_refs` | string[] | 全部受影响对象 |
| `suggestion` | string? | 可执行修复方向 |

核心错误码至少包括：

- `PROJECT_MASTER_VERSION_NOT_CONFIRMED`
- `LINE_GRAPH_MILEAGE_REQUIRED`
- `LINE_GRAPH_PATH_AMBIGUOUS`
- `LINE_GRAPH_PATH_UNREACHABLE`
- `BRIDGE_SIDE_OR_QUANTITY_REQUIRED`
- `BEAM_TYPE_CAPACITY_MISSING`
- `ERECTION_CAPACITY_INVALID`
- `TARGET_ASSIGNMENT_MISSING`
- `TARGET_ASSIGNMENT_DUPLICATE`
- `ROUTE_NOT_CONFIRMED`
- `CROSS_ROUTE_DEPENDENCY_CYCLE`
- `INVENTORY_CANNOT_BALANCE`
- `PLANNING_HORIZON_EXCEEDED`
- `INPUT_FINGERPRINT_STALE`

## 7. GirderPlanSimulationStore（本地持久状态）

| 字段 | 类型 | 规则 |
|---|---|---|
| `schema_version` | literal | `girder-plan-simulation/v1` |
| `scenario_versions` | `GirderPlanScenarioVersion[]` | 历史版本不可覆盖 |
| `runs` | `GirderPlanSimulationRun[]` | 只读快照，允许状态转为 stale/confirmed |

写入必须使用进程内锁和原子替换；读取旧/损坏结构时返回明确仓储错误，不得清空持久状态。

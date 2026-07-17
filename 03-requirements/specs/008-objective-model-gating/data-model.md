# 数据模型：目标指标建模门控

> 当前实现校正（2026-07-09）：`resource_path_continuity` 已从当前目标项体系中移除；旧输入字段仅作为废弃兼容字段被忽略。当前目标项为 `control_node_late`、`makespan_and_soft_milestone`、`resource_idle`。第一阶段路径连续性、无窗口候选路径和资源路径罚分均为历史设计，不再建路径 circuit 或产生路径罚分；机械钻组聚合、组内升序和同组同资源保留为基础规则。

## 实体：目标建模门控

| 字段 | 类型 | 规则 |
| --- | --- | --- |
| `term_id` | string | 使用既有目标项 ID |
| `requested_enabled` | boolean | 用户请求或默认合并后的启用状态 |
| `requested_weight` | integer | 用户请求或默认合并后的展示权重 |
| `effective_weight` | integer | 启用时等于权重，关闭时为 0 |
| `modeling_enabled` | boolean | 是否构建该目标专属优化模型 |
| `status` | string | `enabled`、`not_enabled` 或 `not_evaluated` |
| `reason` | string | 用于解释未建模或未评价原因 |

校验规则：

- `effective_weight = 0` 时，`modeling_enabled` 必须为 `false`，除非该数据是最佳努力放松诊断的一部分。
- `modeling_enabled = false` 时，不得产生该目标的专属罚分贡献。
- 所有目标项都关闭时继续拒绝请求。

## 实体：目标支持数据

| 字段 | 类型 | 规则 |
| --- | --- | --- |
| `support_key` | string | 支持数据名称 |
| `required_by` | string[] | 依赖该支持数据的启用目标项 |
| `built` | boolean | 本次是否构建 |
| `evaluated_terms` | string[] | 该支持数据最终服务的目标项 |

关系：

- 一个支持数据可以被多个启用目标复用。
- 支持数据被构建不等于同名或相邻目标项已评价。

## 实体：资源组织门控

| 字段 | 类型 | 规则 |
| --- | --- | --- |
| `idle_enabled` | boolean | `resource_idle` 是否建模 |
| `path_continuity_enabled` | boolean | `resource_path_continuity` 是否建模 |
| `resource_path_node_count` | integer | 路径连续性关闭时必须为 0 |
| `resource_path_transition_arc_count` | integer | 路径连续性关闭时必须为 0 |

规则：

- 两个当前资源目标全关时，不构建资源组织优化模型。
- 命名资源互斥仍属于硬约束，不受资源组织门控影响。
- 历史 `resource_workload_balance` 已不是当前可配置目标项，不再作为资源组织门控字段。

## 实体：目标评价状态

| 状态 | 含义 |
| --- | --- |
| `not_enabled` | 用户关闭该目标项，未建模 |
| `not_evaluated` | 该指标未参与本次评价，或当前结果来源不支持该评价 |
| `ok` | 已评价且无明显风险 |
| `warning` | 已评价且存在轻度风险 |
| `danger` | 已评价且存在明显风险 |

兼容规则：

- 若前端暂不支持 `not_enabled`，可先使用 `not_evaluated`，并通过 `objective_terms_used.effective_weight = 0` 判断关闭状态。
- 不得把关闭项展示为已评价 0 分。

## 实体：目标拆解结果

字段沿用现有 `objective_breakdown` 和 `stats` 字典，允许新增兼容字段：

| 字段 | 含义 |
| --- | --- |
| `objective_terms_used` | 每个目标项的启用状态、展示权重和有效权重 |
| `objective_weights` | 有效权重映射 |
| `objective_modeling_gates` | 可选，记录每个目标项是否建模 |
| `resource_organization_analysis` | 资源组织诊断和状态 |
| `continuity_objective` | 连续性和资源路径建模诊断 |

## 实体：最佳努力放松诊断

| 字段 | 类型 | 规则 |
| --- | --- | --- |
| `relaxed_constraints` | array | 被放松目标清单 |
| `relaxed_target_penalty_days` | integer | 放松目标迟延罚分 |
| `source` | string | `best_effort_refinement` 或现有来源值 |
| `reason` | string | 说明该建模来自最佳努力分支 |

规则：

- 最佳努力放松诊断不得把 `control_node_late` 的关闭状态改写为已启用。
- 结果必须让用户理解：该分支是在严格精排失败后，为返回可用方案而最小化目标放松迟延。

# Phase 1 数据模型：精排目标指标前端全量展示与配置

## ObjectiveMetricDefinition（目标指标定义）

表示后端权威目标指标目录中的一项。

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `term_id` | string | 是 | 稳定指标标识，用于请求、响应和前端映射 |
| `label` | string | 是 | 面向业务用户的名称 |
| `group` | string | 是 | 分组，如控制优先、工期、资源组织、普通工程均衡 |
| `description` | string | 是 | 指标衡量什么、罚分含义、权重调高的影响 |
| `default_weight` | integer | 是 | 默认权重 |
| `configurable` | boolean | 是 | 是否允许用户配置启用状态和权重 |
| `source` | enum | 是 | `objective`、`derived_objective`、`diagnostic` |
| `applies_to` | string[] | 是 | 生效分支或策略，如 `control_priority`、`best_effort_refinement` |
| `legacy_fields` | string[] | 否 | 旧结果字段映射 |
| `parent_term_id` | string | 否 | 当实现仍继承父项权重时，记录父项 |

### 初始目录范围

| `term_id` | 来源 | 默认口径 |
|-----------|------|----------|
| `control_node_late` | objective | 当前默认权重 1,000,000,000 |
| `control_buffer_risk` | objective | 当前默认权重 5,000,000 |
| `risk_related_control_wait` | objective | 当前默认权重 1,000,000 |
| `makespan_and_soft_milestone` | objective | 当前默认权重 10,000 |
| `resource_path_continuity` | objective | 当前默认权重 3,000 |
| `resource_idle` | objective | 当前默认权重 1,000 |
| `resource_workload_balance` | objective | 当前默认权重 100 |
| `target_relaxation` | derived_objective | 最佳努力分支目标放松罚分；默认应等价于当前与 `control_node_late` 共权重行为 |
| `resource_slot_balance` | derived_objective | 当前作为 `resource_path_continuity` 路径项组成部分并单独输出罚分 |
| `unconfigured_normal_balance` | objective | 当前固定后端权重 10，需变为可见配置 |

诊断项不进入可配置目标项目录，但可进入只读诊断目录。

## ObjectiveTermConfig（目标项配置）

用户提交给后端的目标项配置。

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `enabled` | boolean | 是 | 是否启用该目标项 |
| `weight` | integer | 是 | 权重；启用时必须大于等于 1 |

### 校验规则

- 未提交的目标项自动使用目录默认配置。
- 未知 `term_id` 返回校验错误。
- 启用项权重必须在后端允许范围内。
- 至少一个可配置目标项必须启用。
- 已废弃目标项按现有兼容策略处理，不参与新贡献计算。

## ObjectiveContribution（目标贡献项）

单次求解结果中对目标函数的贡献解释。

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `term_id` | string | 是 | 目标项标识 |
| `label` | string | 是 | 展示名称 |
| `source` | enum | 是 | `objective` 或 `derived_objective` |
| `enabled` | boolean | 是 | 配置中是否启用 |
| `active` | boolean | 是 | 本次分支是否实际参与求解 |
| `configured_weight` | integer | 是 | 用户配置或默认权重 |
| `effective_weight` | integer | 是 | 本次实际用于目标函数的权重 |
| `raw_penalty` | integer | 是 | 未乘权重的罚分 |
| `weighted_contribution` | integer | 是 | `raw_penalty * effective_weight` 或等价贡献 |
| `applies_to` | string[] | 是 | 适用分支 |
| `notes` | string | 否 | 继承父权重、分支不适用等说明 |

## ObjectiveMetricBreakdown（目标分解）

统一承载结果解释。

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `weighted_objective` | integer | 是 | 统一贡献求和后的目标值 |
| `objective_contributions` | ObjectiveContribution[] | 是 | 目标贡献列表 |
| `objective_terms_used` | object | 是 | 兼容既有配置回显 |
| `objective_weights` | object | 是 | 兼容既有权重字典 |
| `diagnostic_metrics` | DiagnosticMetric[] | 否 | 只读诊断指标 |

## DiagnosticMetric（只读诊断指标）

不参与权重配置，但可用于解释结果质量。

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `metric_id` | string | 是 | 诊断指标标识 |
| `label` | string | 是 | 展示名称 |
| `value` | number/string | 是 | 指标值 |
| `unit` | string | 否 | 单位 |
| `source_path` | string | 是 | 来源字段，如 `stats.continuity_metrics.jump_pier_count` |
| `read_only` | boolean | 是 | 固定为 `true` |

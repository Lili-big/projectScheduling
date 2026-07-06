# 数据模型：移除同类资源工作量均衡目标

## ObjectiveTermId

| 字段 | 当前状态 | 目标状态 |
|------|----------|----------|
| `resource_workload_balance` | 当前有效目标项 | 从有效目标项中移除，转入废弃输入 |
| `resource_idle` | 有效目标项 | 保持不变 |
| `resource_path_continuity` | 有效目标项 | 保持不变 |
| `resource_slot_balance` | 有效目标项 | 保持不变 |
| `unconfigured_normal_balance` | 有效目标项 | 保持不变 |

## DEFAULT_OBJECTIVE_TERM_WEIGHTS

- 删除键：`resource_workload_balance`。
- 其他键和默认权重保持不变。
- `OBJECTIVE_TERM_IDS` 应随默认权重自动更新，不再包含被删除目标。

## DEPRECATED_OBJECTIVE_TERM_IDS

- 新增废弃 ID：`resource_workload_balance`。
- 已有废弃 ID `normal_balance`、`spatial_resource_assignment`、`same_structure_craft_split` 保持不变。
- 废弃 ID 在请求解析时被过滤，不进入有效配置。

## OBJECTIVE_METRIC_DEFINITIONS

- 删除 `resource_workload_balance` 定义。
- `OBJECTIVE_METRIC_DEFINITIONS` 的 key 集合必须与有效 `objective_terms` 一致。

## ScheduleStrategyConfig.objective_terms

- 默认生成时不包含 `resource_workload_balance`。
- 请求传入 `resource_workload_balance` 时忽略。
- 如果过滤后没有任何有效启用目标项，沿用现有校验失败。

## Solver Objective Terms

| 变量/字段 | 目标状态 |
|-----------|----------|
| `resource_workload_balance_enabled` | 删除或固定为 `False`，不得来自目标权重 |
| `include_workload_balance` | 调用资源组织建模时传 `False` |
| `workload_balance_terms` | 允许作为空列表存在，但不得加入 `model.Minimize(...)` |
| `resource_workload_balance_penalty` | 不再作为目标贡献原始罚分；如保留仅为兼容诊断 |
| `resource_balance_weight` | 不再输出当前目标权重 |

## ObjectiveContribution

- `objective_contributions[*].term_id` 不得出现 `resource_workload_balance`。
- 旧结果 fallback 不得从 `resource_workload_balance_penalty` 合成当前贡献。
- `weighted_objective` 只汇总有效目标项贡献。

## ResourceOrganizationAnalysis

- 保留 `resources` 和 `resource_types` 中的工作量统计字段。
- 如果聚合均衡状态依赖已移除目标，应展示为 `not_evaluated` 或诊断态。
- `workload_balance_enabled` 应反映当前目标未启用，不得显示为目标启用。

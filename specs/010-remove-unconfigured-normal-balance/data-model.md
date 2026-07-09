# 数据模型：移除未配置资源普通工程均衡目标

> 当前实现校正（2026-07-09）：`resource_path_continuity` 已从当前目标项体系中移除；旧输入字段仅作为废弃兼容字段被忽略。当前目标项为 `control_node_late`、`makespan_and_soft_milestone`、`resource_idle`。第一阶段路径连续性、无窗口候选路径和资源路径罚分均为历史设计，不再建路径 circuit 或产生路径罚分；机械钻组聚合、组内升序和同组同资源保留为基础规则。

## ObjectiveTermId

| 字段 | 当前状态 | 目标状态 |
|------|----------|----------|
| `unconfigured_normal_balance` | 当前有效目标项 | 从有效目标项中移除，转入废弃输入 |
| `resource_workload_balance` | 009 后已废弃 | 保持废弃，不恢复 |
| `resource_idle` | 有效目标项 | 保持不变 |
| `resource_path_continuity` | 有效目标项 | 保持不变 |
| 槽位均衡诊断 | 有效目标项 | 保持不变 |

## DEFAULT_OBJECTIVE_TERM_WEIGHTS

- 删除键：`unconfigured_normal_balance`。
- 其他键和默认权重保持不变。
- `OBJECTIVE_TERM_IDS` 应随默认权重自动更新，不再包含被删除目标。

## DEPRECATED_OBJECTIVE_TERM_IDS

- 新增废弃 ID：`unconfigured_normal_balance`。
- 保持 `resource_workload_balance` 废弃状态。
- 废弃 ID 在请求解析时被过滤，不进入有效配置。

## OBJECTIVE_METRIC_DEFINITIONS

- 删除 `unconfigured_normal_balance` 定义。
- `OBJECTIVE_METRIC_DEFINITIONS` 的 key 集合必须与有效 `objective_terms` 一致。

## ScheduleStrategyConfig.objective_terms

- 默认生成时不包含 `unconfigured_normal_balance`。
- 请求传入 `unconfigured_normal_balance` 时忽略。
- 如果过滤后没有任何有效启用目标项，沿用现有校验失败。

## Solver Objective Terms

| 变量/字段 | 目标状态 |
|-----------|----------|
| `unconfigured_normal_balance_enabled` | 删除或固定为 `False`，不得来自目标权重 |
| `_build_unconfigured_normal_balance_terms()` | 不再用于 CP-SAT 目标构建；可删除或仅保留非目标诊断用途 |
| `unconfigured_normal_balance_terms` | 不得加入 `model.Minimize(...)` |
| `unconfigured_normal_balance_penalty` | 不再作为目标贡献原始罚分；如保留仅为兼容诊断 |
| `unconfigured_normal_balance_weight` | 不再输出当前目标权重 |

## ObjectiveContribution

- `objective_contributions[*].term_id` 不得出现 `unconfigured_normal_balance`。
- 旧结果 fallback 不得从 `unconfigured_normal_balance_penalty` 或 `normal_balance_penalty` 合成当前贡献。
- `weighted_objective` 只汇总有效目标项贡献。

## NormalBalanceMetrics

- 保留 `stats.normal_balance_metrics`。
- 继续展示普通工程任务数、已配置/未配置任务数、桶分布、峰值/低谷和评分。
- 评分和桶分布为只读诊断，不代表目标函数贡献。

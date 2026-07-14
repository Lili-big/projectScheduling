# 数据模型：AI 两阶段排程 60 秒预算

## 1. 模型变更结论

本功能不新增、不删除、不迁移字段。继续复用 033 已实现的 `ResourceAssistantOptimizationStages` 及其两个阶段摘要，只更新 AI 单方案入口的预算不变量。

## 2. AI 单方案求解预算

| 属性 | 类型 | 本功能规则 |
|---|---|---|
| `total_budget_seconds` | `float` | AI 单方案两阶段共享固定为 `60.0` |
| 适用范围 | 枚举语义 | AI 多方案比选中的单方案严格固定资源求解 |
| 计时起点 | 行为 | 两阶段编排启动，包含第一阶段建模与搜索 |
| 分配方式 | 行为 | 第一阶段先使用；第二阶段获得扣除第一阶段墙钟耗时及模型构建预留后的剩余预算 |

三套方案连续求解时，每套方案拥有独立的 `60.0` 秒预算，不共享一个三方案总预算。

## 3. 第一阶段摘要

现有 `ResourceAssistantPrimaryStageSummary` 保持不变：

| 字段 | 本功能期望 |
|---|---|
| `attempted` | 固定为 `true` |
| `configured_budget_seconds` | 默认 AI 入口为 `60.0` |
| `elapsed_seconds` | 第一阶段实际墙钟耗时 |
| `solver_status` | 保持现有状态枚举 |
| `max_target_delay_days` / `makespan_days` | 保持现有工期目标口径 |
| `optimality_proven` | 仅 `OPTIMAL` 为 `true` |

## 4. 第二阶段摘要

现有 `ResourceAssistantSecondaryStageSummary` 保持不变：

```text
remaining_seconds = max(0, 60 - primary_elapsed_seconds)
secondary_budget = max(0, remaining_seconds - model_build_reserve_seconds)
```

| 字段 | 本功能期望 |
|---|---|
| `configured_budget_seconds` | 不大于计算出的 `secondary_budget` |
| `attempted` | 第一阶段有排程且剩余预算达到现有启动阈值时为 `true` |
| `skipped_reason` | 继续使用现有原因，如 `time_budget_exhausted`、`insufficient_remaining_budget` |
| `resource_idle_days` / `continuity_penalty` | 计算和采用规则不变 |

## 5. 两阶段选择摘要

`ResourceAssistantOptimizationStages` 的结构和状态转换不变：

```text
primary 启动
  -> 无排程或无剩余预算：selected_stage=primary
  -> secondary 启动
       -> 通过不退化与严格改善校验：selected_stage=secondary
       -> 失败、越界或无改善：selected_stage=primary
```

本功能下 `total_budget_seconds=60.0`。`total_elapsed_seconds` 可以因模型构建、校验和结果组装开销略高于 60 秒，不等同于两个求解器配置时限之和。

## 6. 固定资源不变量

- `input_resource_quantities` 与提交方案逐类型一致。
- 两个阶段使用相同的命名资源集合。
- `resource_expansion_attempted=false`。
- 工作量为 0 的工艺资源保持 0，不因时限增加而扩充。

## 7. 兼容性

- 历史响应缺少 `optimization_stages` 时继续按现有兜底展示。
- 历史响应中的 `total_budget_seconds=30.0` 是当时求解事实，不重写为 60.0。
- 本功能实施后的新求解返回 60.0；现有前后端字段类型无需调整。

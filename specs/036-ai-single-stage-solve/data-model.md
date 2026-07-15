# 数据模型：AI 固定资源单阶段求解

## 1. 单阶段工期摘要

继续复用 `ResourceAssistantPrimaryStageSummary`：

| 字段 | 新结果语义 |
|---|---|
| `attempted` | 固定为 `true` |
| `solver_status` | 唯一排程调用的原始状态 |
| `max_target_delay_days` | 最终排程最大目标延期 |
| `makespan_days` | 最终总工期 |
| `optimality_proven` | 唯一阶段为 `OPTIMAL` 时为真 |
| `elapsed_seconds` | 唯一阶段实际耗时 |
| `configured_budget_seconds` | 完整单方案时限，当前为 60 秒 |

## 2. 第二阶段兼容摘要

继续复用 `ResourceAssistantSecondaryStageSummary`，新结果固定为：

```text
attempted = false
solver_status = null
resource_idle_days = null
continuity_penalty = null
optimality_proven = false
elapsed_seconds = 0
configured_budget_seconds = 0
skipped_reason = not_applicable
validation_failure_reason = null
```

该对象只表达结构兼容，不代表存在第二阶段。

## 3. 阶段选择记录

新结果固定为：

```text
selected_stage = primary
fallback_reason = null
total_budget_seconds = 60
total_elapsed_seconds = 唯一阶段实际总耗时
solver_call_count = 1
performance_path = ai_strict_fixed_resource_single_stage
```

## 4. 诊断摘要

以下数据继续从最终任务排程派生：

- 累计资源内部空闲；
- 跳墩、换幅、跨幅跳墩；
- 方向反转、路径组切换；
- 连续性得分及资源路径明细。

诊断不参与目标函数、工期三态、方案推荐或阶段选择。

## 5. 状态转换

```text
开始 -> 唯一固定资源工期求解
OPTIMAL/FEASIBLE -> 生成排程、三态和诊断 -> selected_stage=primary
UNKNOWN/INFEASIBLE/MODEL_INVALID -> 返回失败事实和诊断 -> 不重试
场景变化 -> 清除求解结果、对比和推荐
```

## 6. 历史兼容

- 历史缺少 `optimization_stages` 时继续按旧结果读取。
- 历史 `secondary.attempted=true` 或 `selected_stage=secondary` 时保留原值。
- 不删除历史原因枚举，不迁移基准计划文件。
- 工期三态和旧 `plan_status` 兼容字段保持不变。

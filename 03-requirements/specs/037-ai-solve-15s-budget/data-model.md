# 数据模型：AI 单方案 15 秒求解预算

## 1. 单方案求解预算

继续使用现有数值字段，默认关系如下：

```text
AI 单方案最大时限 = 15.0 秒
optimization_stages.total_budget_seconds = 15.0
optimization_stages.primary.configured_budget_seconds = 15.0
target_achievement.time_budget_seconds = 15.0
```

三处预算必须来源一致。实际耗时独立记录，不要求等于 15 秒。

## 2. 单阶段兼容摘要

阶段结构不变：

```text
primary.attempted = true
secondary.attempted = false
secondary.skipped_reason = not_applicable
selected_stage = primary
solver_call_count = 1
```

本次只改变新结果的配置预算，不改变阶段状态或诊断字段。

## 3. 方案范围

- 经济方案：独立 15 秒。
- 平衡方案：独立 15 秒。
- 抢工方案：独立 15 秒。
- 用户手动调整资源后的重算：独立 15 秒。
- 批量求解：按方案逐套配置 15 秒，不共享总预算。

## 4. 状态转换

```text
开始 -> 配置 15 秒 -> 唯一固定资源工期求解
OPTIMAL/FEASIBLE -> 返回排程、三态和诊断
UNKNOWN/INFEASIBLE/MODEL_INVALID -> 返回现有失败事实和诊断
任一结果 -> 不重试、不延时、不增配资源
```

## 5. 历史兼容

- 历史结果保留其原始 `total_budget_seconds` 和 `configured_budget_seconds`。
- 不迁移基准计划快照，不增加版本字段。
- 页面展示历史阶段详情时使用历史对象中的预算，不用当前 15 秒覆盖。

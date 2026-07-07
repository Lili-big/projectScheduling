# 契约：第二阶段相对工期诊断

## 目标

在不改变既有任务输出粒度和目标贡献结构的前提下，为两阶段精排结果增加可选诊断字段，解释第二阶段相对第一阶段的工期变化。

## 诊断字段

诊断字段应出现在现有两阶段精排诊断结构中，例如 `stats.drill_group_refinement` 和对应的 `objective_breakdown.drill_group_refinement`。

```json
{
  "stage1_makespan_days": 1490,
  "stage2_makespan_days": 1493,
  "stage2_makespan_delta_days": 3
}
```

## 字段说明

- `stage1_makespan_days`：第一阶段总工期 `M1`。
- `stage2_makespan_days`：第二阶段总工期 `M2`。
- `stage2_makespan_delta_days`：`M2 - M1`。

## 兼容规则

- 字段为可选字段，旧结果缺失时前端和结果消费者不得报错。
- 目标贡献中不新增独立 `M2 - M1` 目标项。
- 既有 `makespan_days`、`objective_contributions`、`drill_group_refinement_status` 语义保持兼容。
- 不再使用 `stage2_makespan_exceeded` 表示单纯晚于第一阶段的回退。

## 硬约束规则

- 未启用目标放松时，硬里程碑迟延仍代表结果不可作为正常硬约束满足结果接受。
- 真实固定工期上限配置存在且未放松时，仍应按既有语义执行。

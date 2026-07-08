# 数据模型：桩基钻机墩组两阶段精排

## 实体：原任务

| 字段 | 类型 | 规则 |
| --- | --- | --- |
| `task_id` | string | 使用现有任务 ID，最终输出保持不变 |
| `structure_id` | string | 用于归属墩组和区分左右幅、墩号等结构边界 |
| `component_type` | string | 第一版仅聚合 `pile` |
| `process_name` | string | 用于区分旋挖钻、冲击钻、回旋钻等施工工艺 |
| `duration_days` | integer | 组内展开时参与串行求和 |
| `compatible_resource_types` | string[] | 用于识别对应钻机资源组 |
| `properties` | object | 保持现有透传，不作为第一版必需聚合字段 |

规则：

- 原任务是最终 `ScheduleResult.tasks` 的唯一输出粒度。
- 原任务不得因为被聚合而丢失 ID、名称、结构归属、构件类型、工艺名称、数量和诊断引用。

## 实体：机械钻机墩组

| 字段 | 类型 | 规则 |
| --- | --- | --- |
| `group_id` | string | 由聚合 key 稳定生成 |
| `resource_group_key` | string | 对应机械钻机资源组 |
| `structure_id` | string | 同一结构物内聚合 |
| `component_type` | string | 第一版为 `pile` |
| `process_name` | string | 同一施工工艺内聚合 |
| `child_task_ids` | string[] | 组内原任务 ID，至少 1 个 |
| `duration_days` | integer | `child_task.duration_days` 之和 |
| `sequence_order` | integer | 用于线路排序，取组内代表任务或结构顺序 |
| `eligible_resource_ids` | string[] | 可施工该墩组的命名资源 |
| `assigned_resource_id` | string/null | 粗排确定后写入 |

校验规则：

- 不再依赖资源池 `same_structure_parallel_limit = 1` 启用单机聚合。
- 旋挖钻、冲击钻、回旋钻机械桩基墩组默认执行“组内原任务同一台命名资源负责”。
- 组内单资源规则必须由墩组资源选择变量或等价约束显式表达，避免资源池参数缺省、为 0 或大于 1 时失效。
- 人工挖孔桩不得形成机械钻机墩组。
- 人工挖孔桩不得被组内单资源规则限制，允许沿用原任务粒度的多资源并行。
- 不同钻机资源组、不同工艺、不同结构物不得合并为同一墩组。

## 实体：线路序列

| 字段 | 类型 | 规则 |
| --- | --- | --- |
| `sequence_key` | string | 桥梁、工区、幅别、结构类型、施工工艺、钻机资源组的组合 |
| `group_ids` | string[] | 当前实际存在的墩组，按结构顺序或墩号排序 |
| `adjacent_pairs` | pair[] | 相邻换资源惩罚使用 |
| `hole_triples` | triple[] | `1-0-1` 洞洞惩罚使用 |

规则：

- 序列只包含实际存在的墩组，不补造缺失墩号。
- 左右幅、不同钻机资源组、不同结构类型、不同施工工艺不得混入同一序列。

## 实体：第一阶段结果

| 字段 | 类型 | 规则 |
| --- | --- | --- |
| `status` | string | 可行、不可行或超时状态 |
| `group_assignments` | object | `group_id -> resource_id` |
| `group_start_end` | object | `group_id -> start/end` |
| `baseline_makespan_days` | integer | 第一阶段总工期 |
| `hard_milestone_feasible` | boolean | 硬里程碑是否满足 |
| `adjacent_resource_switch_penalty` | integer | 相邻墩换资源原始惩罚 |
| `hole_jump_penalty` | integer | 洞洞式跳墩原始惩罚 |
| `entered_from_capacity_sort` | boolean | 固定资源主链路是否由外层池级排序进入；MVP 简化后主链路应为 `false` |

规则：

- 当前常规自动流程中，第一阶段可行结果即为最终主结果。
- 第一阶段不得建立全量路径环路。
- 固定资源主链路应直接产生第一阶段精排结果；若第一阶段不可行或超时，当前资源主结果保持失败语义，并尝试资源建议。
- 池级最短工期结果只能用于资源建议测算或明确标记的内部诊断辅助，不得作为固定资源失败后的兜底展示结果。

## 实体：细排结果（历史兼容）

| 字段 | 类型 | 规则 |
| --- | --- | --- |
| `status` | string | 可行、不可行、超时或跳过 |
| `resource_routes` | object | `resource_id -> ordered group_ids` |
| `stage2_node_count` | integer | 实际参与路径排序的墩组节点数 |
| `stage2_arc_count` | integer | 实际路径转移弧数量 |
| `path_distance_penalty` | integer | 墩号距离原始惩罚 |
| `side_switch_penalty` | integer | 左右幅切换原始惩罚 |
| `makespan_tolerance` | integer | 历史字段；当前常规自动流程不再运行第二阶段 |
| `fallback_reason` | string/null | 细排失败或跳过时填写 |

规则：

- `resource_routes` 只包含第一阶段实际分配给该资源的墩组。
- 细排不得重新选择资源。
- 当前常规自动流程不再依赖细排结果作为主排程；该实体仅用于历史兼容或显式诊断路径。

## 实体：展开结果

| 字段 | 类型 | 规则 |
| --- | --- | --- |
| `task_id` | string | 原任务 ID |
| `start_offset` | integer | 由墩组时间和组内顺序展开 |
| `end_offset` | integer | `start_offset + duration_days` |
| `assigned_resource_id` | string | 继承墩组资源 |
| `group_id` | string/null | 可选诊断引用，不作为正式任务身份 |

规则：

- 组内展开优先满足内部前后置；无内部前后置时按任务顺序和任务 ID 稳定排序。
- 展开后同一命名资源不得出现时间重叠。
- 展开后硬里程碑不得迟延。

## 实体：两阶段诊断

| 字段 | 类型 | 规则 |
| --- | --- | --- |
| `drill_group_refinement_status` | string | 当前主口径包含 `stage1_final`、`not_applicable`、`coarse_only`、`coarse_infeasible`；`stage2_refined`、`stage2_fallback` 为历史兼容 |
| `coarse_group_count` | integer | 粗排墩组数量 |
| `coarse_child_task_count` | integer | 被聚合的原任务数量 |
| `stage2_node_count` | integer | 当前常规流程通常为 0；历史细排实际路径节点数量 |
| `stage2_arc_count` | integer | 当前常规流程通常为 0；历史细排实际路径弧数量 |
| `baseline_candidate_arc_count` | integer | 用于对比的全候选路径弧估算 |
| `arc_reduction_ratio` | number | 路径弧减少比例 |
| `adjacent_resource_switch_penalty` | integer | 粗排相邻换资源惩罚 |
| `hole_jump_penalty` | integer | 粗排洞洞跳墩惩罚 |
| `fallback_reason` | string/null | 回退或跳过原因 |

关系：

- 两阶段诊断可放入现有 `stats.continuity_objective` 或 `objective_breakdown` 的兼容扩展字段。
- 前端可以选择展示或忽略新增字段，但不得因此影响原任务展示。

# 数据模型：第一阶段钻机组路径连续性优化

## 机械钻机组

**含义**：第一阶段内部粗粒度路径节点，由同资源组、同结构物、同构件类型、同施工工艺的机械钻任务聚合而成。

**关键属性**：
- `group_id`：钻机组内部标识。
- `resource_group_key`：资源池或资源类型分组。
- `bridge_id`：桥梁标识。
- `side`：幅别，通常为左幅或右幅。
- `support_index`：墩号或支点序号。
- `structure_id`：结构物标识。
- `component_type`：构件类型，桩基场景通常为 `pile`。
- `process_name`：施工工艺，如旋挖钻成孔。
- `child_task_ids`：组内原始任务 ID。
- `eligible_resource_ids`：可执行该组的命名机械钻资源。

**校验规则**：
- 缺少 `side` 或 `support_index` 的组不得参与同幅/跨幅路径窗口。
- 只有机械钻资源类型进入本规则；人工挖孔桩不进入。
- 最终排程不输出虚拟组任务，仍展开原任务。

## 可施工序列

**含义**：同桥梁、同工艺、同幅别、同资源候选范围内，当前机械钻资源实际可施工钻机组按墩号排序后的序列。

**关键属性**：
- `scope_key`：桥梁、工艺、幅别和资源范围组成的统计范围。
- `ordered_group_ids`：按 `support_index` 排序后的钻机组 ID。
- `position_by_group_id`：每个钻机组在可施工序列中的序号。

**校验规则**：
- 序列只包含当前资源实际可施工的组。
- 同幅距离使用序列位置差，不使用自然墩号差。

## 第一阶段候选转移

**含义**：第一阶段路径选择中允许某台钻机从一个钻机组转向另一个钻机组的候选边。

**关键属性**：
- `from_group_id` / `to_group_id`：转移两端钻机组。
- `transition_kind`：`same_side` 或 `cross_side`。
- `same_side_sequence_distance`：同幅可施工序列距离，仅同幅时有效。
- `cross_side_support_gap`：跨幅真实墩号差，仅跨幅时有效。
- `penalty`：未加权连续性惩罚。
- `allowed`：是否允许进入第一阶段候选路径。
- `rejection_reason`：拒绝原因，如 `same_side_window_exceeded`、`cross_side_gap_exceeded`、`missing_location`。

**校验规则**：
- 同幅：`same_side_sequence_distance <= 2` 才允许，惩罚为 `max(0, same_side_sequence_distance - 1)`。
- 跨幅：`cross_side_support_gap <= 1` 才允许，惩罚为 1。
- 不生成窗口外兜底候选边。

## 第一阶段路径诊断

**含义**：用于解释第一阶段路径窗口、候选弧、惩罚和失败原因的结构化诊断。

**关键属性**：
- `stage1_route_status`：`not_enabled`、`enabled`、`infeasible`、`not_applicable`。
- `stage1_route_node_count`：第一阶段路径节点数。
- `stage1_route_candidate_arc_count`：允许进入模型的候选弧数。
- `stage1_route_rejected_arc_counts`：按拒绝原因统计的拒绝弧数。
- `stage1_same_side_penalty`：同幅惩罚合计。
- `stage1_cross_side_penalty`：跨幅惩罚合计。
- `stage1_route_penalty`：第一阶段路径惩罚合计。
- `stage1_route_failure_reason`：不可行或未建模原因。

**兼容规则**：
- 字段可作为 `drill_group_refinement` 或 `continuity_objective` 的可选扩展。
- 旧结果缺少这些字段时，前端应显示未评估或不展示，不得报错。

# 数据模型：resource_path_continuity 候选路径无窗口化

> 当前实现校正（2026-07-09）：`resource_path_continuity` 已从当前目标项体系中移除；旧输入字段仅作为废弃兼容字段被忽略。当前目标项为 `control_node_late`、`makespan_and_soft_milestone`、`resource_idle`。第一阶段路径连续性、无窗口候选路径和资源路径罚分均为历史设计，不再建路径 circuit 或产生路径罚分；机械钻组聚合、组内升序和同组同资源保留为基础规则。

## 机械钻机组节点

**含义**：第一阶段内部路径节点，由同资源组、同结构物、同构件类型、同施工工艺的机械桩基任务聚合而成。

**关键属性**：
- `group_id`：钻机组内部标识。
- `resource_group_key`：资源池或资源类型分组。
- `bridge_id`：桥梁标识。
- `structure_id`：结构物标识。
- `component_type`：构件类型，本功能聚焦 `pile`。
- `process_name`：施工工艺。
- `side`：幅别，通常为左幅或右幅。
- `support_index`：墩号或支点序号。
- `child_task_ids`：组内原始桩基任务 ID。
- `eligible_resource_ids`：可执行该组的命名机械钻资源。

**校验规则**：
- 仅 `rotary_drill`、`circulation_drill`、`impact_drill` 进入机械钻机组路径规则。
- 同一结构物内多根桩基必须保留在同一组内并连续施工。
- 最终结果不得输出虚拟钻机组任务。

## 无窗口候选转移

**含义**：同一机械资源可施工的两个合法钻机组节点之间的有向路径候选。

**关键属性**：
- `from_group_id` / `to_group_id`：转移两端钻机组。
- `transition_kind`：`same_side` 或 `cross_side`。
- `same_side_sequence_distance`：同幅可施工序列距离，仅同幅有效。
- `cross_side_support_gap`：跨幅真实墩号差，仅跨幅有效。
- `penalty`：顺序罚分，当前固定为 0，仅保留字段兼容。
- `allowed`：是否允许进入第一阶段路径模型。
- `rejection_reason`：仅用于非距离合法性拒绝，如 `missing_location`、`scope_mismatch`。

**校验规则**：
- 同幅距离为任意正整数时均允许。
- 跨幅真实墩号差为任意非负整数时均允许。
- 自身到自身不作为候选转移。
- 缺少位置或范围不一致仍不允许。

## 同幅距离诊断

**含义**：同幅候选转移根据当前资源实际可施工节点序列计算出的路径距离，仅用于诊断，不进入目标罚分。

**计算规则**：
- 相邻可施工节点：`same_side_sequence_distance = 1`，罚分为 0。
- 跳过 1 个可施工节点：`same_side_sequence_distance = 2`，罚分仍为 0。
- 更远距离：继续记录距离，罚分仍为 0。

## 跨幅距离诊断

**含义**：跨幅候选转移的切幅和距离解释，仅用于诊断，不进入目标罚分。

**计算规则**：
- 同墩跨幅：`cross_side_support_gap = 0`，罚分为 0。
- 邻墩跨幅：`cross_side_support_gap = 1`，罚分为 0。
- 更远跨幅：继续记录 `cross_side_support_gap`，罚分仍为 0。

## 第一阶段路径诊断

**含义**：用于解释第一阶段路径候选模式、候选弧、0 罚分和拒绝原因的结构化诊断。

**关键属性**：
- `stage1_route_status`：`not_enabled`、`enabled`、`infeasible`、`not_applicable`。
- `stage1_route_candidate_mode`：建议值 `unbounded`，表示不再按窗口硬过滤。
- `stage1_route_node_count`：第一阶段路径节点数。
- `stage1_route_candidate_arc_count`：允许进入模型的候选弧数。
- `stage1_route_rejected_arc_counts`：按拒绝原因统计的拒绝弧数。
- `stage1_same_side_penalty`：同幅罚分合计，当前应为 0。
- `stage1_cross_side_penalty`：跨幅罚分合计，当前应为 0。
- `stage1_route_penalty`：第一阶段路径罚分合计，当前应为 0。
- `stage1_route_failure_reason`：不可行或未建模原因。

**兼容规则**：
- `same_side_window_exceeded`、`cross_side_gap_exceeded` 可保留为兼容字段，但本功能生效时不再因距离超限增加。
- `stage1_route_sparse_same_side_window`、`stage1_route_sparse_cross_side_window` 可保留为历史字段，但不得作为当前拒绝窗口解释。
- 旧结果缺少 `stage1_route_candidate_mode` 时，前端按历史结果处理。

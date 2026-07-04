# 数据模型：精排里程碑与工期目标函数调整

## 实体：硬里程碑

**含义**：`mode="hard"` 且能够匹配到任务范围的里程碑。

**关键属性**：

- `id`：里程碑唯一标识。
- `mode`：必须为 `hard`。
- `scope_type` / `scope_id` / `related_structure_ids`：确定受影响任务范围。
- `target_event`：判断开始或完成事件。
- `target_date`：必须满足的日期。

**规则**：

- 精排阶段中，匹配到任务的硬里程碑事件不得晚于目标日期。
- 硬里程碑不进入目标函数迟延项。
- 未匹配到任务时保持未评估/告警，不新增阻断规则。

## 实体：软控制节点

**含义**：允许迟延但具备控制属性的软里程碑。

**关键属性**：

- `mode`：必须为 `soft`。
- `level`：为 `control` 时属于软控制节点。
- `related_structure_ids`：存在显式关联控制范围时属于软控制节点。
- `target_date`：用于计算迟延天数。

**规则**：

- 软控制节点迟延进入 `control_node_late` 目标项。
- 软控制节点使用最高权重压低迟延，但不作为硬约束。
- 结果中保留迟延天数和控制诊断。

## 实体：普通软里程碑

**含义**：`mode="soft"` 且不属于软控制节点的提醒节点。

**关键属性**：

- `penalty_per_day`：保留为诊断罚分口径。
- `lateness_days`：展示迟延天数。
- `penalty`：展示诊断罚分。

**规则**：

- 普通软里程碑不参与精排目标函数。
- 普通软里程碑迟延不进入总工期目标或 `weighted_objective`。
- 前端仍可展示迟延天数和罚分，帮助用户复核提醒节点。

## 实体：总工期目标项

**含义**：用户可配置的工期目标，内部 ID 保持为 `makespan_and_soft_milestone`，业务名称改为“总工期”。

**关键属性**：

- `enabled`：是否启用目标项。
- `weight`：目标项权重。
- `objective_days` / `makespan_days`：项目完工跨度。

**规则**：

- 目标贡献只按项目完工跨度计算。
- 不叠加软里程碑迟延罚分。
- 前端和文档不得再把该目标项描述为“总工期及软节点偏差”。

## 实体：目标拆解结果

**含义**：用于解释本次精排目标函数和诊断字段。

**关键字段**：

- `objective_terms_used`：本次启用状态和有效权重。
- `objective_weights`：实际参与计算的权重。
- `control_lateness_days`：软控制节点迟延天数。
- `soft_control_lateness_penalty`：软控制节点迟延诊断值。
- `soft_milestone_penalty`：普通软里程碑诊断罚分。
- `weighted_objective`：按当前目标项口径计算的解释性加权汇总。

**规则**：

- `weighted_objective` 中的工期项必须使用总工期贡献。
- `soft_milestone_penalty` 可保留展示，但不进入目标贡献。
- 硬里程碑迟延不应出现在成功精排结果中。

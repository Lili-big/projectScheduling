# 数据模型：AI资源配置与排程优化助手

## 工程画像

描述导入或当前选择项目的摘要状态，用于让用户确认系统理解了项目范围。

字段：
- `project_name`：项目名称。
- `start_date`：计划开工日期。
- `bridge_count`：桥梁或工点数量。
- `work_section_count`：工区/左右幅数量。
- `structure_count`：下部结构数量。
- `task_count`：生成任务数量。
- `control_piers`：控制墩摘要列表。
- `resource_types`：主要资源类型列表。
- `continuous_beam_groups`：连续梁组摘要。
- `critical_path_candidates`：关键线路候选摘要。
- `constraint_hints`：供 LLM 生成资源方案时使用的约束提示，如可用资源类型、控制墩优先、连续梁展开关注点。
- `reference_examples`：A/B/C 三类方案的参考样例，不作为固定方案。
- `data_quality_messages`：数据完整性提示。

校验规则：
- `control_piers` 来源必须标识为 `control_level`、连续梁主墩关系或二者共同识别。
- 无法识别控制墩时，`control_piers` 为空并给出 `data_quality_messages`。
- 工程画像不得作为排程结果；只作为求解前确认和解释材料。
- `reference_examples` 只用于 LLM 生成提示和本地回退，不作为必须完全采用的资源数量。

## 控制墩摘要

描述一个被识别为控制墩的结构物。

字段：
- `structure_id`：结构物 ID。
- `structure_name`：结构物名称。
- `bridge_id`：桥梁 ID。
- `work_section_id`：工区/幅别 ID。
- `side`：幅别。
- `support_no`：墩台号。
- `recognition_sources`：识别来源，如 `control_level`、`continuous_main_pier`。
- `related_continuous_beam_group_ids`：关联连续梁组。

校验规则：
- 同一个结构物可有多个识别来源，但在画像中只展示一次。
- 不通过里程碑新增控制墩识别。

## 资源方案

描述由 AI 生成的经济、平衡、抢工或用户调整后的资源投入组合。

字段：
- `scenario_id`：方案 ID，例如 `resource-plan-a`。
- `scenario_name`：方案名称，例如“方案A 经济方案”。
- `profile`：枚举，`economy`、`balanced`、`crash`、`custom`。
- `positioning`：方案定位。
- `generation_source`：生成来源，`llm`、`local_fallback` 或 `user_adjusted`。
- `generation_rationale`：AI 或本地回退给出的生成依据。
- `reference_example_used`：生成时参考的样例摘要，可为空。
- `organization_strategy`：施工组织策略摘要。
- `validation_messages`：资源类型、数量、趋势和可求解性相关的校验提示。
- `applicable_scenarios`：适用场景说明。
- `expected_risks`：预期风险说明。
- `resource_pools`：本方案使用的资源池配置。
- `changed_from_standard`：是否已被用户调整。
- `solve_status`：本方案当前求解状态。
- `stale_reason`：结果失效原因。

状态规则：
- 初始状态为 `draft` 或 `ready_to_solve`。
- 用户修改资源数量后，若已有结果，状态转为 `stale`。
- 求解中为 `solving`。
- 求解完成后映射为 `optimal`、`feasible`、`infeasible`、`unknown`、`failed` 或 `model_invalid`。

校验规则：
- `max_quantity` 不得小于 `quantity`。
- AI 输出资源类型必须来自当前项目资源类型或被标识为不适用，不得凭空新增求解器无法识别的资源类型。
- AI 输出数量必须是非负整数；经济、平衡、抢工之间同类关键资源投入趋势必须可解释。
- AI 输出可偏离参考样例，但必须提供生成依据；偏离过大时系统应给出校验提示而不是静默通过。
- 桩机资源按实际资源类型分别配置。
- 不适用于当前项目的资源类型必须有状态说明，不能参与利用率排名。

## 方案求解结果

描述单个资源方案的排程结果和派生指标。

字段：
- `scenario_id`：对应资源方案 ID。
- `generated`：求解前任务图摘要。
- `result`：排程求解结果。
- `metrics`：核心指标。
- `diagnostics`：诊断信息。
- `generated_at`：结果生成时间。
- `input_fingerprint`：输入指纹，用于判断结果是否失效。

校验规则：
- `metrics` 必须与同一个 `result` 派生。
- `result` 不可用时，`metrics` 中指标必须给出不可用原因。
- 输入指纹变化后结果必须标记为失效。

## 核心指标

描述三方案对比表使用的统一指标。

字段：
- `total_days`：总工期天数。
- `plan_finish_date`：预计完工日期。
- `control_pier_release_dates`：控制墩释放时间列表。
- `first_continuous_beam_start_date`：首个连续梁开工日期。
- `all_continuous_beams_started_date`：全部连续梁展开日期。
- `resource_utilization_by_type`：资源类型利用率列表。
- `average_wait_days`：平均等待时间。
- `max_wait_days`：最大等待时间。
- `control_pier_wait_days`：控制墩相关等待。
- `continuous_beam_wait_days`：连续梁相关等待。
- `transfer_penalty`：转场惩罚摘要。
- `demo_cost`：演示成本估算。
- `target_status`：目标达成状态。
- `not_available_reasons`：不可用原因。

指标口径：
- 总工期来自求解结果。
- 控制墩释放时间来自控制墩下部结构完成并具备上部相关任务开工条件的时间。
- 连续梁开工时间区分首个 0 号块或相关上部任务开工，以及全部连续梁组已开始。
- 资源利用率按资源类型统计，不展示单一总利用率作为决策依据。
- 平均等待时间综合资源空闲等待和前置满足后的开工等待。
- 转场惩罚为演示诊断，来自跳墩、换幅、跨幅跳转、路径组切换等连续性信号。
- 成本估算为演示默认价格估算，必须带有演示标识。

## 资源类型利用率

字段：
- `resource_type`：资源类型。
- `resource_label`：资源名称。
- `resource_count`：资源数量。
- `used_resource_count`：实际使用数量。
- `active_days`：占用天数合计。
- `idle_days`：空闲天数合计。
- `project_utilization`：项目周期利用率。
- `utilization_within_span`：资源投入窗口内利用率。
- `status`：利用状态，如 `balanced`、`under_used`、`idle_risk`。

校验规则：
- 未参与本项目任务的资源类型不应被计入瓶颈或过配判断。
- 利用率口径必须在前端展示说明中可解释。

## 转场惩罚摘要

字段：
- `penalty_score`：演示惩罚分。
- `jump_pier_count`：跳墩次数。
- `side_switch_count`：换幅次数。
- `cross_side_jump_count`：跨幅跳转次数。
- `path_group_switch_count`：路径组切换次数。
- `max_jump_distance`：最大跳墩距离。
- `details`：典型转场明细。

校验规则：
- 不使用真实 GIS 距离。
- 不进入 CP-SAT 目标函数，除非后续另行确认算法变更。

## 演示成本估算

字段：
- `total_cost`：总演示成本。
- `work_cost`：资源作业成本。
- `idle_cost`：资源待机或空闲成本。
- `mobilization_cost`：进出场成本。
- `transfer_cost`：转场相关成本。
- `resource_costs`：分资源类型成本。
- `price_source`：默认值为 `demo_default_price`。
- `disclaimer`：演示估算说明。

校验规则：
- 必须标识为演示默认价格。
- 默认价格不能从真实密钥或私密配置读取。
- 缺少单价时可使用 0 或默认价，并在诊断中说明。

## 推荐解释

字段：
- `recommended_scenario_id`：推荐方案 ID，可为空。
- `recommendation_status`：`recommended`、`no_recommendation`、`insufficient_results`。
- `rule_reason`：确定性推荐规则命中的原因。
- `evidence`：指标证据列表。
- `risk_notes`：风险说明。
- `marginal_benefit_notes`：边际收益说明。
- `ai_explanation`：面向用户的解释文本。
- `explanation_source`：`local` 或 `llm`。
- `llm_status`：外部大模型状态。

状态规则：
- 没有可比较结果时，`recommended_scenario_id` 为空。
- 只有一个可用方案时，可以解释该方案可用，但不应伪装为多方案最优。
- 外部大模型失败时，`explanation_source=local`。

## 大模型配置状态

字段：
- `provider`：配置的提供方，默认 `local`。
- `model`：模型名，可为空。
- `endpoint_configured`：是否配置 endpoint。
- `api_key_configured`：是否配置密钥，仅返回布尔值。
- `timeout_seconds`：调用超时。
- `status`：`local_fallback`、`configured`、`failed`。
- `warning`：配置或调用警告。

校验规则：
- 不返回真实密钥。
- 前端只展示配置状态和告警，不展示敏感值。

## AI 方案生成记录

字段：
- `generation_id`：本次生成 ID。
- `source`：`llm` 或 `local_fallback`。
- `input_fingerprint`：工程画像、资源类型和关键参数指纹。
- `prompt_summary`：发送给 LLM 的摘要，不包含密钥。
- `reference_examples_used`：本次生成使用的 A/B/C 参考样例。
- `constraint_hints_used`：本次生成使用的约束提示。
- `raw_output_available`：是否保留原始输出用于调试，默认不在前端展示。
- `parsed_plan_ids`：成功解析出的方案 ID。
- `validation_status`：`valid`、`partially_valid`、`invalid`。
- `fallback_reason`：触发本地回退的原因，可为空。

校验规则：
- 方案生成记录不得包含真实密钥。
- 生成记录只证明资源方案来源，不替代 CP-SAT 求解结果。
- 当工程画像或资源类型变化时，关联资源方案和求解结果必须失效。

## 资源方案参考样例

字段：
- `profile`：`economy`、`balanced` 或 `crash`。
- `resource_quantities`：参考资源数量，按资源类型或资源类别表达。
- `description`：样例说明。
- `is_hard_constraint`：固定为 `false`。

默认样例：
- `economy`：4 台对应工艺桩机、6 套墩柱模板、2 套盖梁模板、2 组连续梁班组。
- `balanced`：4 台对应工艺桩机、8 套墩柱模板、2 套盖梁模板、4 组连续梁班组。
- `crash`：6 台对应工艺桩机、10 套墩柱模板、3 套盖梁模板、4 组连续梁班组。

校验规则：
- 样例中的“桩机”必须在传给 LLM 前按当前项目实际桩基工艺资源类型展开。
- 样例只用于提示 LLM 和本地回退，不作为 CP-SAT 求解约束。

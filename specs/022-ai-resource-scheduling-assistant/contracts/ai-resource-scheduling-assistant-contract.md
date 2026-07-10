# 契约：AI资源配置与排程优化助手

## 目标

定义前后端围绕“工程画像、AI 三方案生成、批量求解、指标对比、推荐解释”的交互契约。契约描述业务字段和状态，不限定具体实现文件。

## 1. 获取助手初始数据

### 请求

输入：
- 当前 `ScenarioInput` 或可加载的当前项目场景。
- 可选 `generation_mode`：`llm_first` 或 `local_fallback_only`，默认 `llm_first`。

### 响应

字段：
- `project_profile`：工程画像。
- `resource_plans`：A/B/C 三个 AI 初始资源方案。
- `plan_generation`：方案生成记录，包含来源、校验状态和回退原因。
- `reference_examples`：传给 LLM 的 A/B/C 参考样例，标识为非硬约束。
- `constraint_hints`：传给 LLM 的约束提示摘要。
- `llm_config_status`：大模型配置状态。
- `diagnostics`：初始化诊断。

验收：
- 响应必须包含 3 个初始方案，分别对应经济、平衡、抢工定位。
- 三个初始方案必须来自同一次 LLM 生成或同一次本地回退生成。
- 方案中的资源类型必须来自当前项目资源类型或明确标识为不适用。
- 方案必须展示生成来源：外部 LLM 或本地回退。
- 参考样例不得被前端展示为固定方案或最终配置。
- 控制墩识别来源必须可见。
- 未配置外部大模型时，`llm_config_status.status=local_fallback`。

## 2. 更新资源方案

### 请求

字段：
- `plan_id`：被调整的方案 ID。
- `resource_updates`：资源类型到数量的变更。

### 响应

字段：
- `resource_plan`：更新后的方案。
- `invalidated_result_ids`：被标记失效的结果。
- `generation_source`：更新后方案来源，应变为 `user_adjusted`。
- `diagnostics`：数量校验或不适用资源提示。

验收：
- `max_quantity` 必须随 `quantity` 保持合法。
- 被调整方案已有结果时必须失效。
- 未调整方案不应被错误失效。

## 3. 批量求解三方案

### 请求

字段：
- `scenario`：当前项目场景。
- `resource_plans`：待求解方案列表。
- `solve_scope`：默认 `all_plans`，可选单个方案重算。

### 响应

字段：
- `project_profile`：工程画像。
- `plan_results`：每个资源方案的求解结果。
- `comparison`：指标对比。
- `recommendation`：推荐解释。
- `diagnostics`：批量求解诊断。

状态：
- `pending`：待求解。
- `solving`：求解中。
- `optimal`：求得最优解。
- `feasible`：求得可行解。
- `infeasible`：不可行。
- `unknown`：限时内未知。
- `model_invalid`：模型无效。
- `failed`：执行失败。

验收：
- 每个方案必须有独立状态。
- 任一方案失败不得覆盖其他方案结果。
- 没有可比较结果时不得输出推荐方案。

## 4. 指标对比

字段：
- `scenario_columns`：参与对比的方案列。
- `metric_rows`：指标行。
- `best_scenario_id`：推荐方案 ID，可为空。
- `comparison_notes`：对比说明。

每个指标行：
- `metric_id`：指标 ID。
- `metric_name`：中文名称。
- `unit`：单位。
- `values`：各方案值。
- `source_type`：`solver_result`、`derived_diagnostic`、`demo_estimate`。
- `description`：口径说明。

必须支持的指标：
- `total_days`
- `plan_finish_date`
- `control_pier_release_dates`
- `first_continuous_beam_start_date`
- `all_continuous_beams_started_date`
- `resource_utilization_by_type`
- `average_wait_days`
- `max_wait_days`
- `transfer_penalty`
- `demo_cost`

验收：
- 指标不可用时必须给出原因。
- 演示成本和转场惩罚必须标识来源。
- 资源利用率必须按资源类型展开。

## 5. 推荐解释

字段：
- `recommendation_status`
- `recommended_scenario_id`
- `rule_reason`
- `evidence`
- `risk_notes`
- `marginal_benefit_notes`
- `ai_explanation`
- `explanation_source`
- `llm_status`

推荐规则：
- 强节点满足优先。
- 方案 C 边际收益不足时不推荐 C。
- 方案 A 控制墩等待过长时不推荐 A。
- 方案 B 满足节点且成本明显低于 C 时优先推荐 B。
- 无可比较结果时不推荐。

验收：
- AI 解释必须引用指标证据。
- 推荐结论不得由外部大模型直接决定。
- 外部大模型失败时必须回退本地解释。

## 6. 结果失效

触发条件：
- 项目结构变化。
- 工艺工效变化。
- 工艺逻辑变化。
- 资源方案数量变化。
- 计划开始日期变化。
- 求解策略变化。
- 大模型解释输入所依赖的指标变化。

响应要求：
- 失效方案显示待重新求解。
- 对比表标记部分或全部失效。
- 推荐解释标记待更新。

验收：
- 前端不得继续把旧结果展示为当前有效结果。

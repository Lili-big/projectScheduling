# 数据模型：新增资源压力工期搜索

## 固定资源精排结果

代表当前资源数量下的主排程结果。

**关键属性**
- `status`：求解状态，只有可用排程才进入压力搜索。
- `target_achievement`：业务目标达成信息。
- `milestone_results`：硬里程碑实际完成日期和迟延天数。
- `objective_days`：当前资源排程总工期。

**规则**
- `FEASIBLE` 或 `OPTIMAL` 且业务目标未满足时，才允许进入压力搜索。
- `UNKNOWN`、物理不可行、目标无法确认时，不进入压力搜索。

## 原始业务目标

代表用户配置或当前求解入口确定的正式工期目标。

**关键属性**
- `target_date` 或 `target_days`：正式目标。
- `target_source`：硬里程碑或固定工期。
- `required_for_success`：是否作为成功推荐的验收条件。

**规则**
- 成功推荐必须满足原始业务目标。
- 内部压力目标不能覆盖原始业务目标。

## 内部压力目标

代表某一轮资源容量搜索使用的临时目标。

**关键属性**
- `attempt_index`：压力搜索轮次，从 1 开始。
- `overdue_days`：上一轮固定资源精排目标超期天数。
- `original_target_days`：原始目标工期窗口。
- `pressure_target_days`：本轮内部压力目标工期。
- `pressure_target_date`：本轮内部压力目标日期。
- `critical_path_floor_days`：工艺关键路径理论最短工期边界。
- `clamped_by_critical_path`：是否因关键路径边界被截断。

**规则**
- `pressure_target_days = original_target_days - overdue_days * attempt_index`。
- `pressure_target_days` 不得小于 `critical_path_floor_days`。
- 当 `overdue_days <= 0` 时不生成压力目标。

## 压力搜索轮次

代表一次内部压力目标下的最少资源容量搜索和候选判断。

**关键属性**
- `attempt_index`
- `search_lower_bounds`
- `pressure_target_days`
- `pressure_target_date`
- `candidate_quantities`
- `added_quantities`
- `resource_solver_status`
- `capacity_verification_status`
- `full_objective_status`
- `full_objective_target_status`
- `stop_reason`

**状态转换**
1. `searching`：开始本轮压力容量搜索。
2. `same_as_lower_bounds`：返回资源数量仍等于下限，进入下一轮。
3. `candidate_found`：至少一个资源池数量高于下限。
4. `verified`：候选通过原始目标完整精排。
5. `candidate_failed`：候选完整精排未满足原始目标。
6. `stopped`：达到关键路径边界、轮次上限、资源上限不可行或求解未确认。

## 新增资源候选

代表压力搜索返回且至少一个资源池新增的组合。

**关键属性**
- `resource_pool_id`
- `label`
- `resource_type`
- `current_quantity`
- `recommended_quantity`
- `added_quantity`
- `max_quantity`

**规则**
- `recommended_quantity >= current_quantity`。
- `recommended_quantity <= max_quantity`。
- 至少一个 `added_quantity > 0` 才能视为新增资源候选。

## 资源建议结果

代表最终返回给页面和方案对比的资源建议状态。

**关键属性**
- `resource_recommendation_status`
- `resource_recommendation_message`
- `recommended_resource_counts`
- `recommended_resources`
- `resource_recommendation_attempts`
- `pressure_search_attempts`
- `pressure_search_status`
- `pressure_search_stop_reason`

**规则**
- `recommended_resources_verified` 只能在候选完整精排满足原始目标时出现。
- 压力搜索失败时必须保留当前资源主排程。
- 页面展示时必须区分原始目标和内部压力目标。

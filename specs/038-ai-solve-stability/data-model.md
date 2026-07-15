# 数据模型：AI 固定资源排程结果稳定化

## 1. 单方案改进请求

在现有单方案求解请求上增加可选的上一版结果。

- `scenario`：当前完整项目场景。
- `resource_plan`：当前待求解资源方案。
- `previous_plan_result`：可选，页面当前持有的同方案上一版结果；历史请求可缺省。

校验规则：

- 后端必须根据 `scenario + resource_plan` 重新计算当前输入指纹。
- `previous_plan_result.input_fingerprint` 必须与当前指纹完全一致。
- 上一版内部结果必须为 `OPTIMAL/FEASIBLE`，包含非空任务集合，且任务 ID 集合与当前生成任务一致。
- 任一校验失败均不得作为 warm start 或最终兜底。

## 2. 可互换资源组

描述可安全消除编号置换的命名资源集合。

- `equivalence_signature`：由除资源 ID/展示名称外的业务属性、日历、并行规则和候选任务集合构成。
- `resource_ids`：按稳定规则排序的命名资源 ID。
- `assignment_task_ids`：该组资源共同可承担的任务集合。
- `constraint_count`：为该组建立的相邻工作量顺序约束数。

校验规则：

- 组内资源的候选任务集合必须完全相同。
- 能力、启用状态、日历、成本及影响施工规则的字段必须相同。
- 少于 2 台或没有通用 assignment 变量的组不建立约束。

## 3. 稳定性选择记录

存放于最终 `ScheduleResult.stats.stability_selection`。

- `previous_result_provided`：请求是否携带旧结果。
- `previous_result_eligible`：旧结果是否通过复用门禁。
- `previous_result_rejection_reason`：未通过门禁时的原因。
- `warm_start_used`：本轮是否使用旧排程提示。
- `current_candidate_status`：本轮候选求解状态。
- `current_candidate_max_target_delay_days`：本轮候选最大目标延期。
- `current_candidate_makespan_days`：本轮候选总工期。
- `previous_max_target_delay_days`：旧结果最大目标延期。
- `previous_makespan_days`：旧结果总工期。
- `selected_source`：`current_candidate` 或 `previous_result`。
- `selection_reason`：`first_solve`、`current_improved`、`current_equal`、`current_worse`、`current_no_schedule`、`previous_optimal_reused` 或 `previous_ineligible`。
- `solver_call_count`：本次请求实际求解调用次数，0 或 1。
- `interchangeable_resource_group_count`：可互换资源组数。
- `symmetry_breaking_constraint_count`：新增对称性约束数。
- `current_objective_value`：本轮原始目标值，可选。
- `current_best_objective_bound`：本轮原始最优界，可选。

## 4. 结果状态转换

```text
无旧结果/旧结果无效
  -> 独立求解一次
  -> 返回本轮结果

同输入旧结果 FEASIBLE
  -> 旧结果作为 warm start
  -> 求解一次
  -> 新结果严格更优或相等：返回新结果
  -> 新结果更差/无排程：返回旧结果

同输入旧结果 OPTIMAL
  -> 不重复求解
  -> 直接返回旧结果并记录复用

输入变化
  -> 旧结果立即无效
  -> 独立求解一次
```

## 5. 兼容性

- `previous_plan_result` 为可选字段，旧客户端请求无需迁移。
- 历史响应没有 `stability_selection` 时按首次求解展示。
- 不修改历史基准计划文件，不新增数据库或本地持久化文件。

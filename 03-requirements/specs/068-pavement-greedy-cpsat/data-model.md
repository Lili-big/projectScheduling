# 数据模型：路面混合求解

日期：2026-09-26。输入、主数据和配置不新增字段、不迁移存储。

## 内部候选（不公开、不持久化）

PavementCandidate包含：按task_id索引的整数start/end、按核心任务索引的resource_id、各命名机组的有序任务列表、makespan=max(end)、greedy策略ID或cp_sat来源。配套任务无主机组。候选只包含本次输入任务，不能复用过期版本。

校验失败候选不得进入提示、上界、最终结果；贪心失败记录只是构造诊断，不是业务INFEASIBLE证明。三策略有固定执行顺序和平局ID排序。

## 新增公开PavementOptimization

挂载于ScheduleResult.pavement_optimization，可选、缺省省略。类型定义位于后端contracts/pavement.py和前端contracts/pavement.ts。

| 字段 | 类型/缺省 | 含义 |
|---|---|---|
| method | literal greedy_cpsat | 算法标识 |
| initial_strategy | earliest_start / longest_chain / least_transfer / null | 选中初解策略；无初解为null |
| valid_candidate_count | 非负整数 | 已完成且通过校验的贪心候选数 |
| initial_days | 正整数或null | 最好合法初解的max(end)，从计划第0天计 |
| final_days | 正整数或null | 最终可展示计划的max(end)；无计划为null |
| improvement_days | 非负整数或null | 初步与最终均存在时initial_days-final_days，否则null |
| selected_source | greedy / cp_sat / null | 最终方案来源；无计划为null |
| optimizer_status | 原5种状态或null | CP-SAT原始返回状态；没有调用为null |
| optimizer_not_run_reason | budget_exhausted / null | 无剩余预算而未运行；其余为null |
| outcome | improved / initial_retained / cp_sat_only / no_plan / inconsistent | 混合求解整体过程结果 |
| initial_plan_seconds | 非负浮点 | 贪心构造与候选数值校验耗时 |
| model_build_seconds | 非负浮点 | CP-SAT建模/提示耗时 |
| cp_sat_seconds | 非负浮点 | 实际调用求解器耗时 |
| total_seconds | 非负浮点 | 路面入口到结果完成的总耗时 |

输入校验在混合流程启动前失败时允许省略整个对象，沿用原错误契约。初解不存在时initial_strategy/initial_days为null，不能填0天。无最终计划时final_days/improvement_days/selected_source为null。

## 状态不变量

- FEASIBLE或OPTIMAL必须有完整任务和pavement_summary；新元数据final_days与objective_days一致。
- greedy来源可标FEASIBLE；只有CP-SAT对同一模型和目标值给出最优证明时，才允许把同工期greedy候选标OPTIMAL。
- initial_retained包括正常无改善、UNKNOWN优化及未运行；必须有合法初解。此时improvement_days=0。
- cp_sat_only表示贪心无合法初解而求解成功；improvement_days=null，不能说缩短0天。
- improved表示最终工期严格小于初步工期且来自cp_sat。
- no_plan与UNKNOWN/INFEASIBLE等无计划状态一致；inconsistent与MODEL_INVALID及明确诊断一致。
- 只有成功结果才生成待移交需移交日/预计完成日；使用最终选中方案，不拼接两种来源的日期。
- 统计总耗时与原stats.wall_time_seconds的含义区分：旧字段继续表示CP-SAT实际耗时；新total_seconds用于整体预算与用户诊断。

## 兼容

旧路面结果缺pavement_optimization时原样展示；桥梁响应省略该字段；请求中省略新字段不影响现有调用。工期仍为整数自然日、施工末日为start_date+end_offset-1；不调整现有ready_date历史边界字段。无自动保存、无本地配置schema升级。


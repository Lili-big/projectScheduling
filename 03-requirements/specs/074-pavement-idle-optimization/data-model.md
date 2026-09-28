# 数据模型

## 输入：PavementIdleOptimizeRequest

在后端 `contracts/_models.py` 的 ScenarioSolveResult 定义之后、前端 `contracts/scheduler.ts` 定义请求：

- `scenario: ScenarioInput`：当前用户场景，包含本轮使用的有限 time_limit_seconds。
- `baseline: ScenarioSolveResult`：被选中结果及其 generated 输入快照。不是新持久化对象。
- 范围沿用 URL 的可选 `workpoint_id`，不另设可任意填写的工期上限。

服务端装载主数据后生成当前输入，与基准 generated.schedule_input 规范化序列化内容完全比较，并核对 solve_scope、scenario_id、计划开始日期、版本及摘要 input_fingerprint。沿用 `json.dumps(model_dump(mode="json"), sort_keys=True, ensure_ascii=False)` 的 SHA-256，不新造第二种指纹口径。预算亦属于当前完整快照；当前输入有变化时先重新常规求解。

基准结果需为 FEASIBLE/OPTIMAL、任务集合完整唯一。以当前任务/资源定义和基准 start/end/assigned_resource_id 重建 Candidate；日期、duration、工期/摘要一致，候选数值校验无违规，现行 per_fleet_last 标识有效。所有派生统计在服务端重算，不信任提交的 idle/transfer 聚合数字。

## 内部计算

复用 Candidate，不改变 duration、assigned resource 候选集和后置类别。内部指标由每条实际路线的相邻任务计算：`Σ(start[next] − end[prev] − transfer(prev,next))`。结果应与首尾跨度减工作减转场公式相等。

无任务路线贡献 0、单任务贡献 0；兼容准备任务未分配机组不贡献空闲。重复/负值/冲突路线由既有校验拒绝，不能靠 max(0, value) 掩盖违规。

## 输出：PavementIdleOptimization

定义在后端 `contracts/pavement.py`、前端 `contracts/pavement.ts`。通过可选 `ScheduleResult.pavement_idle_optimization` 引入，无字段时兼容旧结果。

| 字段 | 类型/规则 | 含义 |
| --- | --- | --- |
| goal | 常量 min_idle_with_makespan_cap | 本次独立求解目标 |
| metric | 常量 fleet_internal_idle_v1 | 首末作业之间扣除真实转场的口径 |
| baseline_input_fingerprint | 非空字符串 | 基准和本次结果对应的相同权威输入指纹 |
| makespan_cap_days | 正整数 | 基准任务真实完工边界 D，本轮固定 |
| baseline_idle_days / final_idle_days | 非负整数 | 机组·天；相同快照下的前后合计 |
| improvement_idle_days | 非负整数 | baseline_idle_days − final_idle_days |
| baseline_transfer_days / final_transfer_days | 非负整数 | 机组·天；相邻真实转场前后合计 |
| improvement_count | 非负整数 | 本轮严格减少空闲的已验证更新次数 |
| selected_source | baseline / cp_sat | 当前方案来自基准或本轮求解 |
| outcome | baseline_retained / improved / inconsistent | 本轮采用情况；错误不能冒充改善 |
| optimizer_status | 可空，沿用求解器五种状态 | 只记录本轮真实求解状态；未运行时空 |
| optimizer_not_run_reason | 可空，budget_exhausted / zero_idle | 建模预算耗尽或基准已达零下界 |
| proved_optimal | 布尔 | 在 D 和全部当前硬约束下窝工最优；不表示工期最短 |
| search_workers / lns_enabled | 可空 | 本轮真实运行配置；未运行空 |
| time_budget_seconds | 有限正数 | 本轮独立使用的当前预算 |
| model_build_seconds / cp_sat_seconds / total_seconds | 非负有限数 | 本轮耗时；total 包括基准数值检查/建模/优化 |

原 `pavement_optimization` 作为第一阶段来源元数据保留；若基准已是窝工优化结果，其更早的第一阶段证据仍保留，而本轮 idle 元数据只对本次点击的基准负责。不新增递归方案历史或持久库。

`objective_days` 与 `pavement_summary.construction_finish_offset` 继续是本次实际工期。`objective_breakdown.objective = min_idle_with_makespan_cap`；结果展示按此模式解释 OPTIMAL。流式所有中间解为 FEASIBLE、proved_optimal=false；零窝工下界/求解器证明只在完整结束时标为 true。

## 状态转换

可用基准 → running（保留基准）→ initial（附本轮元数据的基准）→ 零或多个 improvement → complete；任意运行态可 interrupted/error，保留最后合法快照。

未通过基准检查：HTTP 422，前端仍保留原结果但不能宣称完成窝工优化。没有输入变化时，本轮结果可再次作为下一次点击的基准；任何参数/范围/版本变化令入口失效。未知统计不补 0，无任务资源继续显示无任务。

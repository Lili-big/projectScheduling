# 接口契约：贪心初解与 CP-SAT 优化

## 接口与输入

沿用POST /api/solve-scenario与POST /api/solve，两者走相同路面入口。ScenarioInput/ScheduleInput不增加必填或可选输入参数；time_limit_seconds在路面领域用作本次混合计算总预算。任务生成/主数据加载仍属接口准备阶段，计时另列。

直接/场景入口既有输入错误的HTTP422或MODEL_INVALID规则保持；桥梁行为不变。演示镜像仍用PAVEMENT_FEATURE_NOT_SUPPORTED拒绝路面，不新增假数据。

## 响应

ScheduleResult增加可选pavement_optimization，字段见[数据模型](../data-model.md)。原任务、资源分配、里程碑、summary、stats.pavement_handover及objective_breakdown保持结构与意义。

| 初解 | CP-SAT结果 | 整体status | 输出 |
|---|---|---|---|
| 合法 | FEASIBLE且更短 | FEASIBLE | 校验后的优化计划，outcome=improved |
| 合法 | OPTIMAL且不长于初解 | OPTIMAL | 更短优化计划或同工期保留初解 |
| 合法 | FEASIBLE且同工期 | FEASIBLE | 初解，outcome=initial_retained |
| 合法 | UNKNOWN | FEASIBLE | 初解，保留optimizer_status=UNKNOWN |
| 合法 | 未运行/无剩余预算 | FEASIBLE | 初解，原始状态null、未运行原因为budget_exhausted |
| 无 | FEASIBLE/OPTIMAL | 原成功状态 | 校验后的CP-SAT计划，outcome=cp_sat_only |
| 无 | UNKNOWN/无剩余预算 | UNKNOWN | 空计划，仍保留待移交范围和原因 |
| 无 | INFEASIBLE | INFEASIBLE | 空计划，不伪造日期 |
| 合法 | INFEASIBLE/MODEL_INVALID，或解违约/比初解更长 | MODEL_INVALID | PAVEMENT_OPTIMIZER_INCONSISTENT，空成功摘要 |
| 无 | MODEL_INVALID或返回解违约 | MODEL_INVALID | 明确模型/结果诊断，空成功摘要 |

输入校验失败优先于上表，不构造初解或使用缓存计划。

## 页面契约

- 整体FEASIBLE/OPTIMAL继续决定是否展示计划；不得用optimizer_status覆盖整体状态。
- 有初解时展示“初步计划X天 → 最终计划Y天，缩短Z天”；初解采用时显示“采用初步计划”，优化改善显示“采用优化计划”。
- UNKNOWN优化有初解显示“限时内未获得更好方案，采用初步计划”；不能沿用“未找到可行计划”警告。只有未找到任何计划时使用原失败提示。
- 贪心无解、CP-SAT成功时显示“采用CP-SAT方案”，初步工期与改善不填0。
- 优化状态/阶段耗时在结果详情或诊断可读，主表仍为施工任务和日期。
- 主数据、工效、资源、工序或日期改变后沿用现有结果失效，不把旧输入的初解当作新输入回退。
- 历史响应没有新字段时不补造初解/改善；任务、转场、等待与pending条件日期来源一致。


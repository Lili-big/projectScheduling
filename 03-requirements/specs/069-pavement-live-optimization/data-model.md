# 数据与状态

## 既有实体

ScenarioInput、ScheduleInput、GeneratedScheduleInput、ScheduleResult和ScenarioSolveResult保持既有业务含义。`time_limit_seconds`继续为正有限秒数，缺省15；直接与场景入口使用同一个混合求解实现。输出施工日期仍为连续日历天，层间间歇、待移交条件日期与末层规则不变。

## PavementOptimization新增可选诊断

| 字段 | 类型/缺省 | 含义 |
|---|---|---|
| search_workers | int/null，>=1 | 本次为CP-SAT选定的worker配置；未启动优化为null |
| lns_enabled | bool/null | 本次CP-SAT的use_lns配置；未启动为null，不代表LNS一定实际被调度 |
| time_budget_seconds | float/null，>0且有限 | 本次混合计算配置的总预算，历史结果缺省null |
| improvement_count | int/null，>=0 | 已接受的严格工期改善次数，新计算从0开始；历史缺省null |

既有initial_days、final_days、improvement_days、selected_source、optimizer_status及阶段耗时继续复用。中间快照的final_days表示“截至该事件的最好工期”，页面依据事件状态显示“当前最好”，不将其当作已完成结果；中间optimizer_status为null，计划本身为FEASIBLE。最终快照填入实际优化状态。无初解时第一次CP-SAT可行方案是首解，不计改善；后续严格缩短才累加。

## PavementSolveEvent（新增，不持久化）

公共字段：`type`（started/solution/complete/error）、`sequence`（从1开始严格递增，可跳号）、`elapsed_seconds`（>=0，单调；从流运行启动计，不等同于纯计算耗时）。

- started：`time_budget_seconds`；无结果。每次成功建立流先有一个started。
- solution：`solution_kind`（initial/improvement）、`solved`（完整ScenarioSolveResult）。第一次可来自贪心或CP-SAT；后续必须严格改善。
- complete：`solved`（同一次求解最终ScenarioSolveResult）。可为OPTIMAL/FEASIBLE/UNKNOWN/INFEASIBLE/MODEL_INVALID；业务失败仍是一个实际求解终态。
- error：`code`和面向用户的`message`，无伪造成功结果；内部堆栈只进入诊断日志。

事件类型使用判别联合，禁止缺少对应载荷；后端独立contracts/pavement_stream.py，前端contracts/pavementStream.ts，避免现有模型导入循环。

## 请求内状态

idle → running_without_plan → running_with_plan → complete；两个running状态均可到error或连接取消。若存在首解，后续方案工期严格下降；complete在正常情况下不大于已接受best；MODEL_INVALID等错误终态不得伪造日期或最优性。

服务端持有不可变输入、best候选、改善计数、固定容量邮箱、停止信号、当前solver引用；没有数据库记录。所有终态释放监听器及引用，连接取消时请求停止计算，不复用旧solver。

## 前端状态与兼容

前端另外保存request token、输入/范围fingerprint、last sequence、运行状态及最后收到的合法方案。只有匹配token和fingerprint的事件可更新当前结果，错误/finally同样受保护；输入变化后的原方案只能标记为历史。

EOF没有complete/error属于连接中断；保留已收到方案供查看，显示未完成。收到MODEL_INVALID时显示该诊断，之前方案只作为带错误标记的参考。旧结果无新增字段仍走原展示，不推断线程数和改善次数；旧同步API没有事件外壳。

# 窝工优化接口与显示契约

## POST /api/solve-scenario/idle/stream

- 可选查询参数：workpoint_id，沿用现有全部/单工点范围口径。
- 请求：PavementIdleOptimizeRequest `{ scenario, baseline }`，baseline 为完整 ScenarioSolveResult。字段类型及约束见 [数据模型](../data-model.md)。不接受独立可填写的工期上限。
- 预算：scenario.time_limit_seconds，必须有限且 >0；本次独立使用，不能无期限运行。
- 服务端在开始流之前装载主数据、生成同范围输入、核对基准身份及合法性；不能仅依赖客户端 stale 状态。之后复用请求级 mailbox/取消机制。

## 前置错误

沿用 HTTP422 的 `detail: {code, message}`：

| code | 使用条件 |
| --- | --- |
| PAVEMENT_IDLE_UNSUPPORTED_DOMAIN | 请求不是路面 |
| PAVEMENT_BASELINE_OUTDATED | 当前输入/版本/范围与基准不同，提示重新常规求解 |
| PAVEMENT_BASELINE_INVALID | 无可行基准、任务不全、指标/时刻/分配/硬约束违规 |
| PAVEMENT_INPUT_OUTDATED | 基准或生成任务仍为旧整体后置等被现行规则拒绝的输入 |
| 既有预算/主数据诊断 | 沿用原错误代码与信息，不吞掉读取/引用错误 |

请求结构错误仍按 FastAPI/Pydantic 原有422格式，不强改其他API。

## NDJSON事件

复用既有 PavementSolveEvent：started(time_budget_seconds) → solution(initial, solved) → solution(improvement, solved)* → complete(solved)，内部异常可终止为 error；断开请求取消本轮求解。所有 solution 为 FEASIBLE；完整结束证明由本轮 idle 元数据给出。

- initial 是基准的权威重建快照，包含本轮 cap、初始指标和目标标识，不是新的贪心初解。
- improvement 的 final_idle_days 必须严格下降，工期不得超过启动时 cap。相同指标不作为改善事件。cap/基准指纹/基准指标不能在事件之间改变。
- complete 的 idle 不得劣于已发布 best，可与 best 相同；若 solver 已证明 best 的窝工值最优，按条件范围标识。
- 合法基准存在但模型无解/无效或候选违反约束，作为不一致错误，不能以一般 complete 覆盖可行结果。前端保留最后合法方案并显示失败/未完成。
- 缺少 terminal、重复/逆序事件、指标缺失/冲突、过期请求一律不能把本轮伪装为成功。

## 结果/界面

- 新字段可选，旧数据维持工期目标展示；新窝工 objective 标识属于当前施工完成口径，不能触发“旧交付口径”提示。
- 同工期且空闲下降被接受；在固定cap内允许更少空闲的方案工期高于上一中间解。只比较本轮目标，不沿用“天数必须严格下降”。
- 按钮“优化窝工”；运行期间禁用并显示“窝工优化中…”；普通求解与本轮互斥。
- 摘要“工期上限 D 天 · 当前工期 M 天 · 窝工 X → Y 机组·天 · 减少 Z 机组·天”；同时提供转场前后值。
- OPTIMAL/零下界说明“在 D 天工期上限及现有约束下，窝工已最小”；FEASIBLE/限时说明尚未证明；错误/中断保留原有合法图表。
- 资源图与当前结果generated快照对应，原参数变更后该结果仍为历史视图，不回算为新口径。

## 兼容与能力边界

普通 /api/solve、/api/solve-scenario、/api/solve-scenario/stream 的请求/目标保持。不向桥梁接口扩展窝工模式，不添加数据库字段或自动保存。演示镜像对新endpoint显式422/PAVEMENT_FEATURE_NOT_SUPPORTED，不模拟本地CP-SAT能力。

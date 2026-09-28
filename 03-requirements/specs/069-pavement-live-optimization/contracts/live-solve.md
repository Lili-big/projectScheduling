# 路面实时求解接口契约

## 新增接口

`POST /api/solve-scenario/stream?workpoint_id=<可选工点ID>`

- 请求：`Content-Type: application/json`，既有ScenarioInput，engineering_domain必须为pavement。时限读取既有time_limit_seconds，缺省15秒，不通过新的协议字段修改用户配置。
- 响应：HTTP 200、`Content-Type: application/x-ndjson`、`Cache-Control: no-cache`，每行一个UTF-8 JSON事件，字段遵循[data-model.md](../data-model.md)。配置禁用代理缓冲提示，但验收以真实首包到达为准。
- 一次请求启动一次混合求解，支持原工点范围与主数据版本校验；服务器端不通过另一次同步HTTP请求求解。
- 桥梁输入在开流前422明确拒绝（`PAVEMENT_STREAM_UNSUPPORTED_DOMAIN`）；非法非有限/非正预算422。既有主数据/范围HTTP错误沿用原码及诊断，开流后业务模型错误通过complete(MODEL_INVALID)返回，运行时异常通过error返回。

## 事件顺序

正常有解：started → solution(initial) → 零至多次solution(improvement) → complete。正常无解/未知/输入业务错误：started → complete。异常：started → 零至多次solution → error。断连可能没有终态，不得当成complete。

每个solution的solved包含完整generated、result、milestone_results、diagnostics及原metrics，所有方案对应同一输入；当前result.status固定为FEASIBLE。最终complete.result.status采用实际求解语义。

同工期不生成新的solution，最终complete必须生成，即使没有改善。服务端可合并中间改善，保证首个方案及最新best在正常终态前可交付；sequence因此允许跳号。improvement_count统计算法实际接受次数，可高于客户端收到的improvement事件数。

无初解情况下，第一份CP-SAT合法方案仍标solution_kind=initial；pavement_optimization.initial_days继续表示贪心初解，保持null，不冒充存在贪心初解。原selected_source区分greedy/cp_sat。

## 生命周期

- 回调只向请求内有界邮箱发布，不等待网络；网络读取速度不得控制CP-SAT搜索进度。
- 连接关闭、请求超时或前端取消均触发该请求停止标记及已绑定solver.StopSearch，关闭消费者后仍完成必要线程收尾，避免新请求叠加旧计算。
- 不自动重连或重试，不存在持久job_id、跨请求恢复或后台无限续算。
- 后端JSON序列化错误、回调异常及异常EOF不能被成功终态吞掉。已发HTTP200时不得再试图更改HTTP状态，而用error事件（连接仍可写时）。

## 兼容与页面

- `/api/solve`、`/api/solve-scenario`的请求及最终JSON响应外形不变，路面获得相同并行限时执行；桥梁原行为不变。
- 历史结果新诊断字段可缺省；不新增配置版本或自动持久化。
- `04-demo/tools/demo-api-mirror/api.mts`延续422/PAVEMENT_FEATURE_NOT_SUPPORTED，新增路径明确拒绝路面流式能力，不返回假进度。
- 页面运行中显示当前最好方案、初解与改善；完成后显示最终方案和最优证明状态。流错误保留最后收到方案并标记未完成；输入已变化时标记历史，旧事件不得覆盖新计算。

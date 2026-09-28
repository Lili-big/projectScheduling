# 实施计划：路面限时并行优化与实时最好方案

**工作分支**：`codex/road-pavement-engineering` | **功能目录**：`069-pavement-live-optimization` | **日期**：2026-09-27  
**规格**：[spec.md](./spec.md)；状态：用户已确认，实施及核心验收已完成；证据见tasks。

## 概要

沿用068的贪心、完整提示、有效上界和原CP-SAT模型，设置最多8worker、内置LNS和既有有限总预算。添加一次POST的NDJSON结果流，先发送合法初解，再发送严格改善和最终结果；路面页面增量接收。保留同步API与桥梁路径，不建立持久后台任务服务。

## 技术上下文

- 环境：Python 3.12.14、OR-Tools 9.15.6755、FastAPI；TypeScript 5.7、React 19、Vite 6、Node 24.18.0。
- 存储：无新持久化；只使用请求内输入、候选、事件和连接状态。
- 测试：pytest、node:test、TypeScript构建、真实HTTP流式读与100任务只读试算。
- 性能：15秒计算预算，当前100任务收尾总计不超过17秒；有初解时计算启动后2秒内可读到方案。加载、序列化和网络耗时分别记录。
- 范围：仅路面混合求解执行、API反馈与页面；无新增依赖、资源业务规则或目标。
- 来源决策见[research.md](./research.md)，字段与状态见[data-model.md](./data-model.md)，协议见[contracts/live-solve.md](./contracts/live-solve.md)。

## 生命周期归属

沿用[spec生命周期归属](./spec.md#生命周期归属)。规格位于03-requirements，代码与测试在既有04-demo目录，性能证据在`.local-data/logs/`。不迁移或清理任何资产。

## Constitution检查

- 研究前：用户选定范围、来源、目标、预算、硬约束、单位、失败态和验收明确，无阻塞澄清。
- 设计后：共享事件、旧接口、字段缺省、断连、输入失效、镜像拒绝均明确；没有引入业务新目标或修改客户数据。
- 研究与设计门禁通过；正式实施门禁已由用户确认满足。不存在复杂度豁免。

## 设计决策

### 1. 同一个混合求解入口

`strategies/pavement.py`保留现有求解流程，增加可选的当前方案通知和停止信号；同步调用省略通知仍返回ScheduleResult。

- `num_search_workers = min(8, max(1, os.cpu_count() or 1))`，seed0，显式`use_lns=True`；不设置`use_lns_only`，保留OR-Tools组合搜索。低核心机器不强行超配8worker，不承诺所有worker数量都会实际调度LNS。
- 使用既有单调时钟deadline；在路面入口检查时限有限且大于0。构造、建模、候选校验及优化消耗同一预算；CP-SAT只接收正剩余秒数。传输不在预算内，但转换与通知开销计入计算诊断，不用回调重置计时。
- 选定合法贪心初解后、建模前发布完整快照；`CpSolverSolutionCallback`仅对严格优于当前best的目标提取数值，复用`validate_candidate`及`result_from_candidate`。
- 回调结果使用不可变快照；best、改善计数及通知按顺序更新。回调不执行网络IO、数据库读写或等待客户端。完整记录每次合法改善，传输层可以合并中间通知。
- 最终选择保留所有已接受候选中的最好者，包括回调候选；终态工期不得反退。等值保留已有方案，若求解器真实证明同目标值最优，可将最终状态升级为OPTIMAL。
- 有合法候选却得到INFEASIBLE/MODEL_INVALID，或任何候选校验失败，沿用MODEL_INVALID/PAVEMENT_OPTIMIZER_INCONSISTENT，不能当作正常超时。真正内部异常终止为错误，不吞异常。
- `constraints/pavement.py`、贪心选序、任务生成及业务主数据不改；只在现有循环检查点观察停止标记。构造本就至多占1秒，停止信号最迟在阶段边界生效；建模内部检查点与CP-SAT StopSearch缩短断连后的收尾。

### 2. 请求内流式执行

新增`POST /api/solve-scenario/stream?workpoint_id=...`，请求仍为ScenarioInput，只支持pavement。保留`/api/solve`与`/api/solve-scenario`。

- 复用现有主数据物化、范围校验与诊断合并，输入快照只生成一次。避免复制同步端点整段业务逻辑；必要时在现有路由/路面应用层提取小函数。
- 在`application/pavement.py`透传方案通知并转换为完整ScenarioSolveResult，每次通知都对应同一generated快照；无额外求解。
- 新增紧邻API路由的`api/pavement_stream.py`，只负责请求内线程、停止控制、事件交付与释放。CPU求解不占ASGI事件循环。
- 使用有界邮箱：started/首个方案保序，后续方案仅保存待交付的最新best，终态单独保留且最后交付；最多固定数量待交付快照，不积压全部历史，序号严格递增但可跳号。
- 正常连接恰有一个complete或error终态；complete载荷是同一求解的最终ScenarioSolveResult。业务UNKNOWN/INFEASIBLE/MODEL_INVALID通过complete载荷如实返回，运行时异常通过error返回。
- 断连或取消设置停止信号，并对该请求持有的solver调用StopSearch；绑定solver时再次检查信号，消除“断连发生在绑定前”的竞态。所有退出路径释放线程/监听器引用；不得按全局PID终止服务，也不自动重启求解。
- 不提供作业ID查询、重连重放、持久队列、后台续算或自动重试。客户端断连后保留其最后已收到结果，服务端没有义务保证客户端收到终态。

### 3. 前端实时显示与输入隔离

- `api/client.ts`添加流式POST读取能力，复用base URL及错误格式；独立保留外部AbortSignal和贯穿整个流的超时（预算+30秒宽限），不改变旧请求的90秒规则。正确处理UTF-8跨块、半行、多行、末尾换行、空行、异常EOF和终态重复；不在重试中启动第二份求解。
- `_schedulerApi.ts`封装路面场景流式函数；事件类型在共享契约中定义。工作流层新增本次调用的流状态处理，既有同步`solveScenarioWorkflow`保持兼容。
- `Workspace.tsx`只接路面工作区：以请求token和输入/范围fingerprint双重校验所有事件、错误及finally；新求解、输入变化、卸载时abort旧连接。旧输入的最后结果可继续按现有历史标记显示，但不能成为当前计划。
- `PavementScheduleResults`复用完整任务及摘要呈现，新增可选运行状态参数。运行中显示“当前最好”而非“最终”；完成后正常显示最终值。正在寻找首解、无改善、错误/中断均有明确状态；不加线程或LNS操作面板。
- 内部一致性错误时显示诊断，已发布快照仅可作为标明未完成/内部错误的参考，不作为成功最终计划。

### 4. 契约与兼容

- 仅新增可选诊断字段和新的流式事件契约，不变更已保存场景结构及版本。
- 避免`contracts/pavement.py`反向导入ScenarioSolveResult造成循环：流式事件在独立`contracts/pavement_stream.py`引用既有模型，通过`contracts/__init__.py`导出；前端对应`contracts/pavementStream.ts`及index导出。
- 演示镜像现有pavement请求统一422拒绝保持有效；新路径也显式覆盖。历史缺字段不填造执行配置，桥梁不切换流式入口。
- LNS字段仅表明启用设置，不能解释为本次某次改善来自LNS；实际调度用诊断搜索日志验证。

## 项目结构与精确修改边界

后端前缀`04-demo/backend/`：

- 修改`app/scheduling/solver/strategies/pavement.py`、`app/scheduling/application/pavement.py`、`app/api/routers/scheduling.py`。
- 修改`app/contracts/pavement.py`、`app/contracts/__init__.py`；新增`app/contracts/pavement_stream.py`、`app/api/pavement_stream.py`。
- 扩展`tests/test_pavement_hybrid.py`、`tests/test_pavement_api.py`、`tests/test_pavement_contracts.py`；新增`tests/test_pavement_stream.py`。

前端前缀`04-demo/frontend/`：

- 修改`src/api/client.ts`、`src/api/_schedulerApi.ts`、`src/api/schedulingApi.ts`（既有领域API导出入口）、`src/app/workflows/solveWorkflow.ts`、`src/app/Workspace.tsx`。
- 修改`src/contracts/pavement.ts`、`src/contracts/index.ts`；新增`src/contracts/pavementStream.ts`。
- 修改`src/features/scheduleResults/presenter.ts`、`src/features/scheduleResults/ScheduleResultsWorkspace.tsx`。
- 新增`tests/pavementLiveSolve.test.mjs`；扩展`tests/pavementResults.test.mjs`、`tests/contractsCompatibility.test.mjs`。

其他：`04-demo/tools/demo-api-mirror/api.mts`新路径拒绝覆盖；`03-requirements/specs/README.md`、`agent.md`、`04-demo/README.md`按实际完成状态更新；本目录记录实施证据。需要架构快照更新时，仅记录本次公开字段/路由变化，允许范围为两端`tests/fixtures/architecture/*baseline.json`，不重录无关基线漂移。

## 验证与完成

按[quickstart.md](./quickstart.md)完成有针对性的算法、流、状态与兼容测试。真实100任务只做有限预算验证，保留原输入哈希与原试算日志；失败先诊断，不反复拉长时限或放宽模型。真实HTTP首包证明必须通过实际增量读取，不能用TestClient一次性缓冲响应替代。结果日志不足以证明页面已更新，还需浏览器检查运行中与结束后完整结果。

Agent上下文脚本`.specify/scripts/powershell/update-agent-context.ps1`不存在，已确认；不创建替代脚本。仅在`agent.md`标注规划状态，实施完成后再更新行为事实。

## 复杂度跟踪

无违反项。请求内线程及有界邮箱直接服务于当前实时返回要求，不扩成持久任务系统。

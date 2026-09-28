# 实施计划：贪心初步计划与 CP-SAT 限时优化

**功能目录**：`068-pavement-greedy-cpsat` | **日期**：2026-09-26 | **规格**：[spec.md](./spec.md)  
**实际Git分支**：`codex/road-pavement-engineering`，保留现有工作树。  
**状态**：已按用户确认完成实施，13/13核心任务验收完成；性能、页面与保留例外见[tasks.md](./tasks.md)。

## 概要

现有路面固定机组流程前置三种确定性贪心构造，数值校验后选择最短完整计划。CP-SAT使用该计划的日期、分配及路线提示，在同一预算内继续最小化全部任务max(end)。超时/未改善时保留合法初解；统一生成任务、资源、等待、转场、里程碑及待移交日期结果。保留全部现有业务约束和桥梁路径。

## 技术上下文

- 语言/平台：现有Python 3.12、TypeScript 5.7、React 19、FastAPI与本地浏览器；以实施环境实际版本记录为准。
- 主要依赖：现有OR-Tools、Pydantic、pytest、Node测试及Vite；无新增依赖。
- 存储：不迁移或写入project-master.db及scheduler-config.json；新字段只存在求解响应，历史字段缺省兼容。
- 规模：真实25段100核心任务；需兼容已有多机组、配套工序、四种关系和执行约束。
- 性能：贪心构造与校验目标1秒；time_limit_seconds沿用现值，作为整个路面混合求解预算。预算记时从路面求解入口开始，API加载/任务生成/传输另外报告，不混入性能口径。
- 验证：指定路面后端、前端契约/结果测试，真实输入只读试算、构建和必要的仓库/架构检查。步骤见quickstart。
- 当前运行：主服务只按04-demo/runtime/README.md操作；规划阶段不重启服务或执行求解。
- 预算策略：贪心软预算min(1秒, 总预算的10%)，在策略/候选循环检查截止；保留所有已完成且通过校验的候选。CP-SAT只取校验/贪心/建模后的正剩余时间，剩余<=0直接结束优化。收尾结果转换纳入总耗时并记录容差。
- 默认行为：仍一次同步返回，无后台任务；单worker和随机种子0继续保留，首版不加入独立局部搜索或优化权重。

## 生命周期归属

见[spec.md#生命周期归属](./spec.md#生命周期归属)。只在现有03-requirements规格目录和04-demo排程、契约、页面及测试路径内实现，无资产迁移。

## Constitution检查

- 用户已选定组合算法；本计划未据此跳过最终tasks实施确认。
- 输入/输出、四类关系、目标、硬条件、状态及预算口径已定义；数值校验与结果展示有验收覆盖。
- 性能数值是本次待验证验收目标，不伪装为既有实测能力。
- 本地状态及既有未提交改动保持；无新增依赖或持久化迁移。
- Phase 0前与Phase 1后检查通过，无需豁免或新增业务澄清。
- 仓库没有update-agent-context.ps1；不创建替代脚本。在agent.md仅增加“待实施规格”引用，保持已实现描述不变。

## 设计

### 1. 构造与独立数值校验

新增内部模块`04-demo/backend/app/scheduling/solver/strategies/pavement_heuristic.py`，承载小型候选值对象、构造函数及纯数值计划校验。接收现有validate_pavement_schedule得到的合法任务与资源候选，不重复生成工期、不读数据库、不调用CP-SAT来“生成贪心初解”。

每个候选记录starts/ends、核心任务到命名机组的分配、各机组任务路线、max(end)及策略ID。配套任务不占主机组，但仍受日期、关系和pending边界约束。所有有效任务需恰好出现一次。

从前置任务已赋值的集合中选择下一任务与候选机组组合。各策略独立状态，固定优先元组：
- earliest_start：(最早start，end，转场天数，task_id，resource_id)。
- longest_chain：(-剩余工序链估计长度，最早start，转场天数，稳定ID)。
- least_transfer：(转场天数，最早start，-剩余链估计，稳定ID)。

剩余链估计只用于贪心排序，不是硬约束或新增目标；四类关系下可使用后继工期/正间歇的保守排序指标，不把它冒充理论下界。同目标值保留先完成的候选，不加入转场或均衡次级目标。

时间按[S,E)、E=S+d计算。已知前序i及后序j的开始下界为：
- FS：S_i+d_i+lag。
- SS：S_i+lag。
- FF：S_i+d_i+lag-d_j。
- SF：S_i+lag-d_j。

同时取计划0、路床边界、execution最早时间、真实层间/验收边界及所选机组末任务end+相邻转场的最大值。固定开始满足所有下界才接受，固定资源只在其有效候选内选择。不同机组上的后序可早于前序实际开始，不能以算法处理顺序额外加强SS/FF/SF。

正常任务先构造，pending只能在全部正常任务赋值后构造，且start>=正常max(end)，包括配套任务。此构造限制若使某个有效复杂场景无法产生候选，只标记贪心失败，由原CP-SAT继续搜索，不判业务无解。

数值校验覆盖：ID和完整性；整数非负时间及固定工期；所有前置关系；roadbed/earliest/fixed开始；主机组资格/唯一性/固定机组；路线覆盖/无重叠/实际相邻转场；真实wait/accepted边界；严格后置；现有硬里程碑的start/min或finish/max口径。末层不加养生；软里程碑仍只计算展示。输入错误、构造未成功和候选违反条件分开记录。

### 2. 混合编排与状态

保留`strategies/pavement.py`的权威入口和现有模型。校验输入→构造/选择初解→建模→添加提示与上界→限时优化→数值校验→选择→统一结果转换。

- 初解无效/不存在：不加任何基于它的提示或上界，CP-SAT可用剩余时间冷启动。
- 初解合法：添加whole_ready<=初解max(end)；允许所有合法路线和分配继续变化，不能固定初解任务日期或路线。
- CP-SAT成功：将solver数值提取为相同内部候选，校验后取较短者；同工期保留初解。若CP-SAT证明该工期最优，即使保留同值初解，也可将最终结果标为OPTIMAL。
- CP-SAT UNKNOWN或未启动（剩余预算耗尽）：已有合法初解返回FEASIBLE，否则UNKNOWN；记录原始优化状态/未运行原因。
- CP-SAT INFEASIBLE且无初解：保留INFEASIBLE。
- 有已校验初解却得到INFEASIBLE/MODEL_INVALID，或返回的解违反硬约束/初解上界：返回MODEL_INVALID与PAVEMENT_OPTIMIZER_INCONSISTENT，不能伪装为正常无改善。不给矛盾结果填成功日期；保留诊断元数据。
- 参数校验失败仍沿用原接口错误行为；不捕获并吞掉所有异常。

把现有ScheduledTask、ResourceAllocation、PavementSummary、MilestoneResult和转场/等待/条件日期生成提取成此文件内的公共转换函数，使用最终选中的数值候选。两种来源走同一路径，防止只回退任务列表而丢失摘要。保留solve_mode=pavement_fixed_resources、objective=earliest_construction_finish。

### 3. CP-SAT提示及保守剪枝

在`constraints/pavement.py`扩展内部变量收集结果，供调用者取得assignment、相邻arc、first/last/empty等变量。给日期、分配及路线关键变量加一致提示，辅助变量按候选计算值补齐；不用fix_variables_to_their_hinted_value。

只进行有证明依据的剪枝：
- 删除pending任务回到正常任务的路线边。
- 删除由现有FS非负间歇链可证明“前者结束后后者才能开始”的逆向边。
- 对SS/FF/SF、只有日期下界的任务以及跨机组跳层，不按拓扑祖先关系推断实际时间先后，不做不安全删边。

保留AddCircuit和AddNoOverlap。提示路线必须仍存在；不存在说明剪枝/候选逻辑不一致，不能静默丢弃整个初解来隐藏错误。first/last边先保持现状；非必需的跳层边剪枝和线程调优留待实测后另评估。

模型horizon仍至少覆盖全部硬日期/固定开始和有效初解；已有合法初解可通过总工期上界缩小搜索，不以未经验证的贪心估计裁剪可行域。

### 4. 共享响应与页面

新增可选`ScheduleResult.pavement_optimization`，类型PavementOptimization；旧结果/桥梁缺省省略，不新增请求参数或配置版本。字段与状态矩阵见[data-model.md](./data-model.md)及[contracts/hybrid-solve.md](./contracts/hybrid-solve.md)。

在现有结果presenter与PavementScheduleResults中显示一条简明结果说明：初步X天→最终Y天、缩短Z天，来源及未改善原因。UNKNOWN优化有合法初解时仍显示完整结果和条件日期；不把原始优化失败诊断误显示成“无可行计划”。耗时放现有诊断或详情中。旧结果仍按其旧字段处理，输入修改沿用现有失效机制。

FastAPI的场景和直接求解都使用同一个路面入口。演示镜像当前拒绝路面请求，继续拒绝，不伪造混合结果。

## 项目结构与精确边界

- 新增：`04-demo/backend/app/scheduling/solver/strategies/pavement_heuristic.py`、`04-demo/backend/tests/test_pavement_hybrid.py`。
- 后端修改：`app/scheduling/solver/strategies/pavement.py`、`app/scheduling/solver/constraints/pavement.py`、`app/contracts/pavement.py`、`app/contracts/_models.py`、`app/contracts/__init__.py`。
- 前端修改：`src/contracts/pavement.ts`、`src/contracts/scheduler.ts`、`src/contracts/index.ts`、`src/features/scheduleResults/presenter.ts`、`src/features/scheduleResults/ScheduleResultsWorkspace.tsx`。
- 测试：现有`test_pavement_solver.py`、`test_pavement_contracts.py`、`test_pavement_api.py`、`frontend/tests/pavementResults.test.mjs`、`pavementWorkflow.test.mjs`、`contractsCompatibility.test.mjs`；保留相关生成/机组测试。导出入口只在新类型引用必需时变更。
- API/应用层/任务生成、演示镜像无需改业务行为，以现有测试证明接入与拒绝策略；不无故改路由。
- 证据与现行说明：本目录、规格索引、agent.md、04-demo/README.md；架构基线仅更新本规格造成的共享字段差异，保留无关漂移。

## 验证原则与复杂度

测试先证明缺失，再实现；一次相关批次后仅重跑受影响失败项。真实输入按只读方式试算，记录版本、配置、阶段耗时、初步/最终工期及校验结果；不反复调大时限来获得漂亮结果。一个内部构造/校验模块足够，不新增通用算法框架、求解服务或策略配置面板。没有复杂度豁免。


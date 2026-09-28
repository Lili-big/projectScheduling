# 实施计划：既有工期上限内的资源窝工优化

**目录**：`074-pavement-idle-optimization` | **日期**：2026-09-28 | **规格**：[spec.md](./spec.md)  
**分支**：沿用当前工作树，不切换分支。  
**状态**：用户确认后实施完成，证据见tasks.md。

## 概要

在当前可行结果旁增加独立“优化窝工”入口。服务端重新生成当前范围输入并验证基准，将基准工期 D 作为不可放宽的上限，保留全部现行硬约束，最小化各机组内部空闲合计。复用现有资源路径、数值校验、有限预算、CP-SAT 多线程/LNS、请求级取消和 NDJSON 交付；不改变常规工期求解。

## 技术上下文

- Python 沿用 `.venv`、OR-Tools、FastAPI/Pydantic；TypeScript/React/Vite 沿用仓库已装版本，无依赖变更。
- 平台：本地 FastAPI 与路面 Web 工作区；只有结果内存状态和请求内求解，不增加持久化、数据库迁移或后台任务。
- 测试：pytest 合成模型/契约/API/流式，Node 工作流与结果渲染，前端构建；只读状态哈希和定义的仓库校验。
- 性能：当前 19 段约 95 任务为场景背景，不写死规模；每次窝工优化使用当前有限 time_limit_seconds，校验/建模计入计算预算，CP-SAT 只使用剩余时间；HTTP 读取/主数据装载耗时单独于求解预算，不虚报为优化器耗时。
- 范围：一个新路面优化流式接口、现有模型局部扩展、工作区按钮及指标文案。不开新常驻服务、不另设成本或最长空闲目标。

## 生命周期归属

遵循 [spec.md](./spec.md) 的唯一阶段归属。实现留在现有 `04-demo/backend/app/` 与 `04-demo/frontend/src/` 领域模块，测试留在邻近 tests；无目录迁移。

## 设计决策

### 1. 基准核验和入口

新增 `POST /api/solve-scenario/idle/stream`，参数为当前 scenario、被选中的完整 baseline（ScenarioSolveResult）及沿用的 workpoint_id 查询参数。调用现有主数据实例化与任务生成，比较当前生成的 ScheduleInput、范围和基准输入快照，使用既有 JSON 排序 SHA-256 算法核验 input_fingerprint。

从服务端权威任务与基准时刻/分配重建 Candidate，拒绝缺失、重复、错误资源、错误日期/时长/完工边界与硬约束冲突。D 必须是该 Candidate 的真实 makespan，并与基准 objective_days、施工完成摘要一致。前端指纹只作禁用与过期事件防护，不代替服务端验证。旧 strict_last 输入拒绝并提示先重算。

新接口仅对路面生效，错误在流开始前返回 422。合法基准首个 solution 即可回传；不调用第一阶段贪心去替换用户基准。普通 /solve 与 /solve-scenario(/stream) 保持原目标。

### 2. 复用路径建立窝工目标

`constraints/pavement.py` 已返回 assignments、实际相邻 arcs、first/last/empty route_vars，不新增两两任务顺序模型。

对每个有候选任务的机组 r，利用现有 first/last 选择变量约束首开工 S_r 和末完工 E_r，empty 时二者为 0；其他首尾条件仅对相应选中弧生效。

- W_r = Σ(任务时长 × assignment[t,r])。
- T_r = Σ(真实相邻转场常量 × selected_arc[r,a,b])。
- I_r = E_r − S_r − W_r − T_r，整数且非负；最小化 ΣI_r。
- 增加 whole_ready ≤ D，D 在本次请求内不变；不将中间更短工期变为新的上限。
- 保留资源互斥、按实际机组后置、全部真实前置/日期/养生/硬里程碑。相邻转场数值只取现有 transfer_days 逻辑，不让模型拉长它。

复用 `_build_model` 的大部分约束与 hints，通过明确的可选窝工模式/基准参数切换目标，默认分支原样最小化工期。约束只使用 O(资源数) 个首尾/空闲聚合变量及已有弧，不为每个弧另建空闲变量。

### 3. 数值校验、保底和最优说明

在 `pavement_heuristic.py` 增加从合法 Candidate 的实际路线独立重算各资源空闲/转场总量的小函数；不依赖模型目标值或前端汇总。所有候选先走现有硬约束校验，再检查工期 ≤ D 和数值空闲；模型目标与重算指标应相等。

基准作为 warm start 与 best，发布 improvement 必须空闲严格下降。相同指标保持旧方案，工期小于 D 不构成优先于空闲的第二目标。结束时即使求解器目标相同也验证最终值；相等时保留 best 但可据 solver OPTIMAL 对该空闲值证明。

基准空闲为 0 时以非负下界证明该目标已达最小并保留方案；求解器状态为未运行，不能伪造 CP-SAT OPTIMAL。预算耗尽/UNKNOWN 返回最后 best；已有可行基准但报告 INFEASIBLE/MODEL_INVALID、hint 缺失或数值不一致时发出错误/不一致诊断，保留上次合法方案，不能伪装普通无改善。

### 4. 共享契约与历史兼容

新增可选 `ScheduleResult.pavement_idle_optimization`，内容详见 [data-model.md](./data-model.md)。原 `pavement_optimization` 保留第一阶段来源信息，不能拿窝工次数/耗时覆盖它。新的 objective_breakdown.objective 为 `min_idle_with_makespan_cap`，但 objective_days 始终仍是施工工期，不能改成窝工。

复用既有 NDJSON 事件结构：started / initial solution / improvement solution / complete / error。窝工目标由新接口及结果元数据判别，前端请求上下文在首结果前提供目标与基准，不必扩展通用 started 事件。缺少新元数据的老结果保持旧解释；窝工结果不被误判成旧交付口径。

### 5. 前端流程与指标

在 PavementWorkspace 结果工具栏新增按钮；仅输入指纹一致、有合法基准、非忙碌时启用。请求时保留当前结果，保存基准引用，不清空图表；取消/过期响应使用现有 requestToken、AbortController 和 fingerprint 机制。

扩展现有 solve controller 的明确模式/基准上下文，工期模式保持严格更短工期；窝工模式校验固定 D、指标单位/口径与基准身份，接受工期 ≤ D 且总空闲严格下降，即使工期与上条相同或在 D 内略增。初始、完整结束与更好事件分别校验，错误不能覆盖上次合法结果。

结果区展示工期上限、实际工期、窝工前后/减少量、转场前后和本轮预算/耗时/次数；第一阶段证据保持为第一阶段。进度文案明确“保持工期上限、减少窝工”。资源图继续按结果配套输入快照计算，各行指标之和与新摘要一致，不拿修改后的资源配置回算历史结果。

### 6. 验证与边界

按 quickstart 的单次相关批次验证；只有相关失败修复后重跑受影响检查。架构新增接口和模型必须审阅并选择性更新基线，保留现有其他差异。API 镜像对新 endpoint 显式返回 422 不支持，避免变成 404 或意外模拟求解。完成时记录用户数据哈希；不在用户页面自动运行本次真实优化。

## 实施路径

- 后端模型：`04-demo/backend/app/contracts/pavement.py`、`contracts/_models.py`；现有 `contracts/__init__.py` 通配导出无需新增门面。
- 后端求解：`04-demo/backend/app/scheduling/solver/strategies/pavement.py`、`pavement_heuristic.py`；现有 `solver/constraints/pavement.py` 返回量已够用，原则上不改建弧规则。
- 后端应用/API：`04-demo/backend/app/scheduling/application/pavement.py`、`api/routers/scheduling.py`；复用 `api/pavement_stream.py` 与 `contracts/pavement_stream.py`，不改传输协议。
- 前端契约/API：`04-demo/frontend/src/contracts/pavement.ts`、`contracts/scheduler.ts`、`api/_schedulerApi.ts`、`api/schedulingApi.ts`；现有 index 通配导出不增门面。
- 前端工作流/UI：`04-demo/frontend/src/app/workflows/solveWorkflow.ts`、`app/Workspace.tsx`、`features/scheduleResults/presenter.ts`、`ScheduleResultsWorkspace.tsx`、`PavementSolveProgress.tsx`。现有 `pavementViewModel.ts` / `PavementResourceTimeline.tsx` 的口径复用，通过测试确认而不重复实现新图。
- 测试沿用 `04-demo/backend/tests/test_pavement_hybrid.py`、`test_pavement_solver.py`、`test_pavement_contracts.py`、`test_pavement_api.py`、`test_pavement_stream.py`；前端 `04-demo/frontend/tests/pavementLiveSolve.test.mjs`、`pavementResults.test.mjs`、`pavementWorkflow.test.mjs`、`pavementVisualization.test.mjs`。
- 镜像 `04-demo/tools/demo-api-mirror/api.mts`；前后端既有架构基线和规格 README 按实际范围更新。

## Constitution 检查

研究前、设计后均核对通过：用户目标及触发方式明确，指标沿用既有口径；硬工期上限与单一软目标、单位、输入/输出/错态、历史兼容、API 边界、可复现场景均定义；无资产迁移、依赖或持久化改动。新增共享字段与端点在计划和契约中成对覆盖，不引入审批例外。

代理上下文更新脚本：已在 `.specify/scripts` 和 `.agents` 搜索，未发现相应脚本；沿用仓库现状，不创建替代脚本或修改 agent.md。

## 复杂度跟踪

无宪章违反项，无新增常驻任务、状态库、通用多目标框架或冗余排序模型。计划阶段未改源码或运行用户求解。

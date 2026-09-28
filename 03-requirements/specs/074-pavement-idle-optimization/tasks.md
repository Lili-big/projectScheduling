# 任务清单：既有工期上限内的资源窝工优化

**日期**：2026-09-28  
**状态**：11/11，用户确认后已实施，核心验收通过；既有全库校验差异已留证。  
**输入**：[规格](./spec.md)、[计划](./plan.md)、[研究](./research.md)、[数据模型](./data-model.md)、[接口契约](./contracts/idle-optimization.md)、[验证指南](./quickstart.md)。

## 用户故事1：在既有工期内单独优化窝工（6项）

- [x] T001 [US1] 在 `04-demo/backend/tests/test_pavement_hybrid.py`、`04-demo/backend/tests/test_pavement_solver.py` 增加基准 D=10、窝工4→0的合成用例、固定/强制等待不可消除、真实转场扣除、正常/待移交按实际机组顺序、多实例/零或单任务/无主机组兼容任务用例；独立重算路线和硬约束验证。补充 cap 不因中间更短方案改变、同窝工不替换、零下界证明、极小预算保底及异常一致性断言。编写前的源码已证实当前只有工期目标，记录缺失而不重复跑旧测试。
- [x] T002 [US1] 在 `04-demo/backend/app/scheduling/solver/strategies/pavement_heuristic.py` 增加纯数值的实际路线窝工/转场指标计算；在 `04-demo/backend/app/scheduling/solver/strategies/pavement.py` 复用 `_build_model` 与 `add_pavement_fleet_paths` 已有首尾/empty/相邻弧，增加可选窝工模式的每资源跨度/作业/转场/空闲聚合及 whole_ready≤D。默认模式继续最小化工期，所有硬约束保留，不增加冗余两两排序或可拉长的转场变量。（依赖T001）
- [x] T003 [US1] 在 `04-demo/backend/app/contracts/pavement.py`、`04-demo/backend/app/contracts/_models.py` 与 `04-demo/frontend/src/contracts/pavement.ts`、`04-demo/frontend/src/contracts/scheduler.ts` 成对增加请求类型及可选窝工结果元数据；在 `04-demo/backend/tests/test_pavement_contracts.py` 覆盖默认兼容、非负/有限单位边界和序列化。保持 objective_days 为施工工期，原第一阶段元数据不被覆写，复用原NDJSON结构。（依赖T002）
- [x] T004 [US1] 在 `04-demo/backend/app/scheduling/solver/strategies/pavement.py` 接入经过验证的基准 Candidate 和独立有限预算，复用 hints、多线程/LNS、回调/取消与结果转换。只接受硬约束合法、工期≤D、窝工严格改善的更新；保留基准/最好值，核对模型目标与独立指标，正确区分零下界证明、CP-SAT证明、预算耗尽、无改善及模型不一致。本轮工期上限不变化，第一阶段普通求解不变。（依赖T003）
- [x] T005 [US1] 在 `04-demo/backend/tests/test_pavement_api.py`、`04-demo/backend/tests/test_pavement_stream.py` 增加新接口基准快照/指纹/范围/主数据版本核验、篡改任务/日期/资源/摘要和旧strict_last拒绝、有限预算、完整/改善/异常/取消/无改善事件测试；合成API请求覆盖端到端10天样例及持久状态不变，补充镜像新路径拒绝证据。（依赖T004）
- [x] T006 [US1] 在 `04-demo/backend/app/scheduling/application/pavement.py` 与 `04-demo/backend/app/api/routers/scheduling.py` 实现 `/api/solve-scenario/idle/stream`，先主数据实例化/重新生成、快照一致性及基准数值验证，再按权威工期和指标启动本轮；正确计入校验/建模的计算时间并只给求解器剩余预算。沿用 `api/pavement_stream.py` mailbox与取消，不创建持久任务。修改 `04-demo/tools/demo-api-mirror/api.mts` 对新路径明确返回既有422不支持。（依赖T005）

## 用户故事2：可见、可靠的窝工改善过程（3项）

- [x] T007 [US2] 在 `04-demo/frontend/tests/pavementLiveSolve.test.mjs`、`04-demo/frontend/tests/pavementResults.test.mjs`、`04-demo/frontend/tests/pavementWorkflow.test.mjs`、`04-demo/frontend/tests/pavementVisualization.test.mjs` 增加独立入口与禁用条件、保留基准、同工期窝工下降、工期在cap内变化、更差/超cap/元数据缺失或漂移拒绝、取消/输入变更/迟到事件不覆盖、零下界/限时/模型异常文案测试；核对资源图各行合计与摘要及转场变化，保留普通工期模式与旧结果测试。（依赖T006）
- [x] T008 [US2] 在 `04-demo/frontend/src/api/_schedulerApi.ts`、`04-demo/frontend/src/api/schedulingApi.ts` 增加窝工流式调用；在 `04-demo/frontend/src/app/workflows/solveWorkflow.ts` 以明确目标模式和基准上下文复用控制器，初始状态保留基准、所有事件校验本轮固定cap/基准身份/指标及sequence。窝工比较从天数下降切换为cap内空闲下降，普通求解分支保持原行为；错误或终止不丢最后合法结果。（依赖T007）
- [x] T009 [US2] 在 `04-demo/frontend/src/app/Workspace.tsx` 的路面结果工具栏接入独立“优化窝工”，沿用请求token/指纹/取消并阻止与普通求解并发；在 `04-demo/frontend/src/features/scheduleResults/presenter.ts`、`04-demo/frontend/src/features/scheduleResults/ScheduleResultsWorkspace.tsx`、`04-demo/frontend/src/features/scheduleResults/PavementSolveProgress.tsx` 展示cap/实际工期/窝工前后/减少量/转场前后、本轮进度和耗时，第一阶段证据另按其原口径显示。新目标不触发旧交付提示，最优明确限定窝工；历史、空态、失败/中断均保留，资源横道复用匹配输入快照。（依赖T008）

## 闭环（2项）

- [x] T010 使用 `04-demo/backend/scripts/capture_architecture_baseline.py` 与 `04-demo/frontend/scripts/captureArchitectureBaseline.mjs` 捕获候选，审阅新接口/共享模型/API导出变化，选择性更新 `04-demo/backend/tests/fixtures/architecture/backend-baseline.json`、`04-demo/frontend/tests/fixtures/architecture/frontend-baseline.json`。不吸收范围外差异，记录保留项；检查镜像新增路径的不支持行为与本地接口边界一致。（依赖T009）
- [x] T011 按 `03-requirements/specs/074-pavement-idle-optimization/quickstart.md` 运行相关pytest、前端测试、构建与架构/仓库/文档校验批次；比较 `.local-data/state/project-master.db`、`.local-data/state/scheduler-config.json`、`.local-data/state/plan-control-store.json` 哈希，使用合成输入验证，不自动运行用户真实方案或保存结果。按 `04-demo/runtime/README.md` 必要时重载精确本地服务；将实际命令、结果、指标/硬约束证据、范围外失败及风险记入本文件，并更新 `03-requirements/specs/README.md`。相关失败只修根因并重跑受影响检查。（依赖T010）

## 依赖与执行方式

顺序T001→T002→T003→T004→T005→T006→T007→T008→T009→T010→T011。共11项：US1六项、US2三项、闭环两项。共享文件密集，顺序实施，不分派代理；相关验证批次内互不依赖的命令可同时执行。不另开独立审查/重复验证阶段。

## 一致性核对

2026-09-28核对规格、计划、数据模型、接口及本任务清单：

| 来源 | 覆盖 |
| --- | --- |
| FR-001、US1场景1/5、US2场景5 | T005/T006/T007/T008/T009：手动触发、基准可用性、范围/过期校验 |
| FR-002、SC-003、篡改/旧规则边界 | T001/T005/T006：权威输入、指纹与全部候选不变量 |
| FR-003、US1场景1/2/3、SC-001/002 | T001/T002/T004：工期硬上限及窝工单目标、条件最优 |
| FR-004、同机组及固定/养生/前置边界 | T001/T002/T004：原约束完整复用 |
| FR-005、窝工单位及空/单/无主机组、SC-001/004 | T001/T002/T007/T009：模型/独立数值/图表一致 |
| FR-006、US1场景4、零下界/预算/取消/异常 | T001/T004/T005/T006/T008：独立预算、保底、流式与请求取消 |
| FR-007、契约新旧兼容、转场前后 | T003/T004/T006/T007/T009/T010 |
| FR-008、US2场景1/2/3/4/5、SC-002/003/004 | T007/T008/T009：同工期改善、不倒退、证明范围、历史/错态 |
| FR-009、SC-004、数据安全/镜像 | T005/T006/T010/T011 |
| plan决策1/2/3/4/5/6 | 分别T005/006、T001/002、T004、T003/010、T007/008/009、T010/011 |
| 代理上下文脚本 | 已搜索未发现；不虚构脚本或改agent.md |

结论：无未覆盖验收点、无相互冲突的目标/单位/状态或范围外任务。工期上限固定为启动基准，窝工合计为唯一新目标；空闲相同保持原方案。新增字段与接口成对覆盖，第一阶段证明不会被第二阶段误解释。转场按实扣除，可能随顺序变化；不承诺真实项目的改善幅度。

## 实施门禁

用户在本对话明确回复“确认执行”，已满足任务确认门禁。按已确认清单顺序实施完成，未分派代理，未自动运行用户真实排程或保存替代方案。

## 规划产物校验记录

2026-09-28，创建本功能资产后运行一次仓库校验批次：

- `.venv/Scripts/python.exe 00-governance/repository-tools/validate_docs.py`：退出0，14个文档链接及API事实检查通过。
- `.venv/Scripts/python.exe 00-governance/repository-tools/validate_repository.py`：退出1，`requirements.txt changed without architecture dependency approval`，与073完成记录一致；本次未改依赖和审批文件，不扩修。
- `.venv/Scripts/python.exe 00-governance/repository-tools/validate_lifecycle_workspace.py --json`：退出1，9个既有 `missing-workpackage-reference`，为客户验证成果和standalone/json-task-viewer输入输出引用，未指向本功能目录；与073规划记录一致。本次不清理或迁移这些文件。
- 一致性核对无需求覆盖缺口；未运行求解/前端代码测试或构建，因为本阶段只产出规格、计划和任务。上述既有校验差异不阻塞本次规划确认，但不宣称全库检查通过。


## 实施完成证据（2026-09-28）

### 已交付行为

- T001/T002/T004：复用机组路线的 first/last/empty/实际相邻弧建立非负空闲目标，原基准 makespan 为固定上限。独立数值指标重算，不依赖目标值代替校验；原工期求解分支、养生/前置/转场/按实际机组后置等硬约束保留。
- T003/T005/T006：新增 `PavementIdleOptimizeRequest` 和可选 `pavement_idle_optimization`，接口 `/api/solve-scenario/idle/stream` 先服务端重新生成、核验范围/版本/指纹/任务定义/时刻/日期/分配，再用基准 warm start 及保底。第一阶段元数据保留，objective_days 始终是实际工期。镜像显式拒绝新路径。
- T007/T008/T009：结果页独立“优化窝工”按钮，输入失效和忙碌时禁用；请求期间保留基准，支持原cap内同工期/不同工期的窝工下降；指标/基准身份漂移、超上限、逆序/更差和过期事件不覆盖合法结果。展示工期上限、实际工期、窝工/转场前后、本轮耗时，最优说明限定本轮窝工目标。
- 现有 `api/pavement_stream.py` 增加 HintInconsistent 的专用错误代码与文案，复用原 error 事件结构；必要的局部补充确保“已有合法基准但模型无解”准确说明为模型不一致。运行时异常仍用原有内部错误信息，私有栈不发到页面。
- 新数值验收集中在 `test_pavement_hybrid.py`，复用既有 `test_pavement_solver.py` 硬约束验收；入口/失效测试集中在 `pavementLiveSolve.test.mjs`，复用 `pavementWorkflow.test.mjs` 参数指纹测试，避免重复同一断言。

### 数值与流式验收

- 固定 R2 C[0,10)，R1 A[0,2)、B[6,8) 基准：D=10、I=4。优化得到工期≤10且I=0；固定A时I=4，强制4天等待时I=4，固定日期且跨位置转场1天时I=3。均为真正CP-SAT求解及独立校验。
- 候选选择模拟依次返回 (工期10,窝工4) → (8,2) → (10,0)，全部合法更新，cap始终10；重复同指标不计改善。证明没有将中间更短工期错误收紧成新上限。
- API内存合成输入的10天基准，窝工8→0，经过服务端生成、基准核验、NDJSON initial/improvement/complete，任务/配置及测试状态文件内容不变。
- 旧strict_last、错范围、有效机组参数变化、版本/指纹不符、缺失/重复任务、错误时刻/日期/时长/资源/工期摘要均有拒绝用例。
- 零窝工基准通过非负下界直接证明，optimizer_status为空、reason为zero_idle；预算耗尽保留基准；模型不一致发布原合法方案后终止为 PAVEMENT_OPTIMIZER_INCONSISTENT；普通异常及请求取消行为保持。
- 相同资源图口径测试合计为空闲0、转场1机组·天，未分配机组仍显示无任务/空值，首末作业外时间不计。未运行用户真实项目优化，不宣称实际项目必降多少或预算内必证明最优。

### 实际命令和结果

1. 按 quickstart 执行5个后端文件的pytest批次：初次140通过、1失败，失败是新API测试修改了停用的机组池，生成的有效排程输入未改变。改为修改在用机组池后，仅重跑 `test_pavement_api.py::test_idle_api_rejects_stale_and_corrupt_baselines_before_streaming`，退出0、1通过。
2. 新增边界用例后单独运行 `test_pavement_hybrid.py::test_idle_incumbent_comparison_does_not_tighten_original_cap`、`test_pavement_hybrid.py::test_idle_still_enforces_real_fleet_pending_order_and_supports_preparation`，退出0、2通过。
3. 补充具体不一致诊断后运行 `test_pavement_stream.py::test_idle_model_inconsistency_is_named_and_keeps_the_published_baseline` 和受影响的既有 `test_pavement_stream.py::test_runtime_error_is_terminal_and_does_not_claim_success`，退出0、2通过。累计144个不同后端用例验收通过，未重复跑已通过的完整套件。
4. `node --test 04-demo/frontend/tests/pavementLiveSolve.test.mjs 04-demo/frontend/tests/pavementResults.test.mjs 04-demo/frontend/tests/pavementWorkflow.test.mjs 04-demo/frontend/tests/pavementVisualization.test.mjs`：退出0，47通过。
5. `npm run build`：首次退出2，定位为对同名solveCurrent的编辑误落在桥梁工作区。已还原桥梁函数并将逻辑限定于PavementWorkspace；重跑退出0，TypeScript与Vite通过。保留大于500kB的常规打包提示。
6. 后端、前端 capture_architecture_baseline --check：各退出1；选择性更新后剩余差异仍是既有工作树项，分类见下，无新增窝工字段/接口遗漏。
7. `validate_repository.py`：退出1，既有requirements.txt缺少架构依赖审批；本次未改依赖。`validate_docs.py`：退出0，14个文档链接及API事实通过。

### 契约基线和范围外失败

本轮修改前后均捕获live基线，并保存原fixture；三方差分仅纳入本功能40个后端变化路径和3个前端公共契约变化路径（API、请求/结果模型及函数导出）。未覆盖无关字段、依赖和历史导出。

后端剩余46处既有差异：process_id、compatible_process_ids模型字段、apply_unified_target_achievement导出、task-view-display-map路由及计数、requirements哈希。前端公共契约检查仍缺少既有MinimumResourceVerification/UnifiedSolveMetadata导出；快照另有根样式行数、当前构建体积两项诊断差异，前端检查脚本并不以体积/行数作失败判据。无窝工相关字段/端点残留差异。

这些失败不影响本次核心数值与API/前端验收，不扩修或通过整份刷新快照掩盖。规划阶段9处历史资产引用问题亦未扩修。不能宣称全仓库校验通过。

全部基线、差分、测试/构建/检查日志与服务只读检查记录保存在 `.local-data/logs/20260928-idle-optimization/`；这些是本地诊断资料，不作为正式资产提交。

### 服务和用户数据保护

- 按运行规范只重载已核实的8000后端及其启动器，最终启动器PID43848、服务PID31872，日志 `.local-data/logs/20260928-014915-919/`。
- `/api/health` 为ok；OpenAPI包含新接口及PavementIdleOptimization；根页面提供新构建 `index-DsBS3-UZ.js`。用户浏览器未刷新，未自动发起真实项目求解或保存结果。
- 主数据和持久配置SHA-256与本次实施开始时相同：project-master.db为 `6E224DE570974B9BD17B58F81FBD7D5FE12B0DF73A7D4A65F1540B232821FE9B`；scheduler-config.json为 `380F35F738A7DC718858438E6738618598FF2C2C20239DCB150CD516F10128A1`；plan-control-store.json为 `18941FC0E540FF7784A77195348B49AAB2B60DFBB211470BFAD8A5BF62A30B0C`。当前配置哈希相较073已不同，采用本轮起点比对，未回滚用户中间修改。
- 用户需刷新加载新页面并获得与当前输入一致的工期方案，再主动点击“优化窝工”。既有页面结果保留在其当前内存中，本次没有为此扩展结果持久化。

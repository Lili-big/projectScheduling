# 任务清单：路面限时并行优化与实时最好方案

**状态**：用户已确认实施，14/14完成；核心验收通过，既有非核心基线例外见下。  
**输入**：[spec.md](./spec.md)、[plan.md](./plan.md)、[research.md](./research.md)、[data-model.md](./data-model.md)、[协议](./contracts/live-solve.md)、[验收指南](./quickstart.md)。

仅交付并行搜索、内置LNS、有限预算和实时最好方案。无自动下界、专项310规则、模型替换、独立局部搜索或业务数据改动。

## 共享契约（2项）

- [x] T001 在`04-demo/backend/tests/test_pavement_contracts.py`与`04-demo/frontend/tests/contractsCompatibility.test.mjs`补充可选优化诊断、事件判别载荷、完整ScenarioSolveResult往返和旧字段缺省测试；实施前确认新能力缺失。
- [x] T002 在`04-demo/backend/app/contracts/pavement.py`、新增`04-demo/backend/app/contracts/pavement_stream.py`及`04-demo/backend/app/contracts/__init__.py`定义/导出诊断与事件；同步`04-demo/frontend/src/contracts/pavement.ts`、新增`04-demo/frontend/src/contracts/pavementStream.ts`及`04-demo/frontend/src/contracts/index.ts`，遵循data-model且避免循环导入。

## US1：有限预算并行优化（2项，P1）

**独立验收**：小样例13天最优、低核参数、剩余预算、正常保留最好结果与异常区别。

- [x] T003 在`04-demo/backend/tests/test_pavement_hybrid.py`扩展CPU数1/4/28/未知、最多8worker、use_lns、seed0、非有限时限、剩余预算耗尽、真实改善和原失败语义测试；不要求跨次路线或日期完全一致。
- [x] T004 在`04-demo/backend/app/scheduling/solver/strategies/pavement.py`设置CPU适配worker与内置LNS，保留组合搜索、原deadline和数值校验，补有限时限检查与实际执行诊断；不修改约束/目标/贪心规则，同步入口自动复用。

## US2：持续返回当前最好完整方案（5项，P1）

**独立验收**：初解在建模/优化结束前发布，受控改善单调、正常终态不丢最好方案，页面结束前可展示任务。

- [x] T005 在`04-demo/backend/tests/test_pavement_hybrid.py`补回调首解/改善/等值/无初解/不合法候选/终态选优用例；新增`04-demo/backend/tests/test_pavement_stream.py`验证事件序列、单次调用、有界合并、终态交付和同步/流式诊断一致性。
- [x] T006 在`04-demo/backend/app/scheduling/solver/strategies/pavement.py`增加可选通知与CP-SAT解回调，先发布合法初解，逐次校验严格改善并复用完整结果转换，计数和快照不可互相污染，最终保留所有已接受方案的最好者；中间不标OPTIMAL。
- [x] T007 在`04-demo/backend/app/scheduling/application/pavement.py`透传同一generated快照的完整场景结果；新增`04-demo/backend/app/api/pavement_stream.py`实现请求内执行线程、有界邮箱、停止控制与释放；在`04-demo/backend/app/api/routers/scheduling.py`接入路面专用POST流，复用物化/范围/错误逻辑并保留同步入口。
- [x] T008 在`04-demo/frontend/src/api/client.ts`、`04-demo/frontend/src/api/_schedulerApi.ts`、`04-demo/frontend/src/api/schedulingApi.ts`（领域导出）及`04-demo/frontend/src/app/workflows/solveWorkflow.ts`实现NDJSON增量读取和流状态，复用base URL/错误格式，处理UTF-8跨块、半行、多行、缺终态、贯穿流的超时与外部abort；新增`04-demo/frontend/tests/pavementLiveSolve.test.mjs`覆盖解析和正常序列。
- [x] T009 在`04-demo/frontend/src/app/Workspace.tsx`仅接入路面实时求解；调整`04-demo/frontend/src/features/scheduleResults/presenter.ts`、`04-demo/frontend/src/features/scheduleResults/ScheduleResultsWorkspace.tsx`和`04-demo/frontend/tests/pavementResults.test.mjs`，展示当前最好/最终、改善、寻找首解及无改善状态，保持完整任务与日期展示，诊断配置只放详情。

## US3：输入隔离、断连和兼容（3项，P2）

**独立验收**：旧事件不覆盖新输入，中断不冒充成功，断连计算释放，桥梁/同步/历史/镜像行为明确。

- [x] T010 在`04-demo/backend/tests/test_pavement_stream.py`和`04-demo/backend/tests/test_pavement_api.py`补断连在solver绑定前/后、异常、校验失败、无解/未知/不一致、非法预算/域、一次请求一次求解及原同步范围兼容测试；在`04-demo/frontend/tests/pavementLiveSolve.test.mjs`补过期token/fingerprint、乱序/重复终态、EOF/异常、重算和卸载测试。
- [x] T011 在`04-demo/frontend/src/app/workflows/solveWorkflow.ts`与`04-demo/frontend/src/app/Workspace.tsx`完成请求token+输入/范围指纹隔离、变更/重算/卸载abort及受保护的catch/finally；在`04-demo/backend/app/api/pavement_stream.py`和`04-demo/backend/app/scheduling/solver/strategies/pavement.py`闭合停止信号、绑定竞态、建模检查点/StopSearch与收尾；错误时保留可查看的最后快照并明确未完成，不自动重启。
- [x] T012 在`04-demo/tools/demo-api-mirror/api.mts`明确新流路径的422拒绝，扩展`04-demo/backend/tests/test_pavement_api.py`的镜像拒绝与同步入口/只读事实验证；核对`04-demo/frontend/tests/contractsCompatibility.test.mjs`的历史字段缺省及桥梁接口兼容。

## 验收与证据（2项）

- [x] T013 按`03-requirements/specs/069-pavement-live-optimization/quickstart.md`运行一批相关测试、前端build及仓库验证；只读V26的100任务快照做15秒验证，核对LNS实际调度、初解/改善/最终合法性与<=17秒耗时；进行真实HTTP首包、页面运行中/结束后及断连收尾检查，在本文件记录命令/退出码和实际结果，诊断保存到新的`.local-data/logs/<本次时间>/`。失败只重跑受影响项，不启无限试算、不改客户配置。
- [x] T014 按实际验收更新`03-requirements/specs/069-pavement-live-optimization/spec.md`及本文件、`03-requirements/specs/README.md`、`agent.md`、`04-demo/README.md`；核对diff保持选定范围。如新增公开契约确实导致架构快照差异，仅更新`04-demo/backend/tests/fixtures/architecture/backend-baseline.json`、`04-demo/frontend/tests/fixtures/architecture/frontend-baseline.json`中本次项并记录证据，保留无关漂移和已知基线问题。

## 依赖与执行顺序

T001→T002为共享契约基础；T003→T004交付US1；T005→T006→T007→T008→T009交付US2；T010→T011→T012闭合US3；最后T013→T014。测试先证明缺失，再实现并进行一次相关批次验证。同一策略、工作区、工作流多次修改有依赖，不标[P]；默认当前会话顺序执行，不要求额外代理。全部三故事为本次范围，不以US1代替实时交付验收。

## 单次跨产物一致性检查

| 来源 | 覆盖任务/证据 |
|---|---|
| FR-001 原模型/目标/数据不变 | T004、T006、T012、T013 diff及硬约束验证 |
| FR-002 worker/LNS/seed与CPU适配 | T003、T004、T013 |
| FR-003 单份有限预算/不改保存配置 | T003、T004、T010、T012、T013 |
| FR-004 完整候选校验及输出 | T005、T006、T007、T009 |
| FR-005 首解/严格改善/最终/无初解 | T005—T009 |
| FR-006 实时显示和最优语义 | T006、T009、T013 |
| FR-007 token/指纹/停止与无自动重算 | T007、T008、T010、T011 |
| FR-008 输入/搜索/一致性/传输错误 | T003、T005、T007、T010、T011 |
| FR-009 同步/桥梁/历史/镜像/共享契约 | T001、T002、T010、T012 |
| FR-010 参数诊断与真实只读效果 | T002、T004、T006、T013 |
| SC-001 100任务15秒改善与耗时 | T013真实快照证据；不承诺310 |
| SC-002 完成前首解可读 | T005、T007、T009、T013真实HTTP/页面 |
| SC-003 单调性、计数及异常 | T005、T006、T010、T011 |
| SC-004 边界/兼容/数据不变 | T001、T003、T008、T010、T012、T013 |
| US1验收1—4 | T003、T004、T013 |
| US2验收1—4 | T005—T011、T013 |
| US3验收1—3 | T001、T002、T010—T013 |
| 计划1：统一入口、执行参数、回调与预算 | T003—T006、T011 |
| 计划2：POST流、有界邮箱、停止释放 | T005、T007、T010、T011 |
| 计划3：解析、展示与输入隔离 | T008—T011、T013 |
| 计划4：字段、循环导入、旧协议 | T001、T002、T012 |
| 资产归属、证据与现行说明 | T013、T014；规格准备阶段仓库检查见下 |

一致性结论：FR、SC、用户故事和设计决策均覆盖，0缺口；无游离任务、重复全量验证或超出计划路径；用“LNS启用配置”区别“实际子策略调度”，用“计算预算”区别“HTTP耗时”。共14项：共享2、US1 2、US2 5、US3 3、验收与证据2。无阻塞澄清；用户随后明确“确认”，已完成speckit-implement。

## 规格准备阶段检查

2026-09-27：仅创建规格/设计/任务和更新索引、规划状态；未改运行代码、业务数据或用户保存配置，不作为应用实现通过声明。

- `.venv/Scripts/python.exe 00-governance/repository-tools/validate_repository.py`：退出1，现有`requirements.txt changed without architecture dependency approval`；本次未改requirements或架构快照。
- `.venv/Scripts/python.exe 00-governance/repository-tools/validate_lifecycle_workspace.py`：退出1，9处`missing-workpackage-reference`，位于历史客户验证汇报与standalone/json-task-viewer工作包；无069路径报错。本轮不修复无关历史引用。
- Spec creator、setup-plan、setup-tasks均只运行一次且退出0；保持工作分支`codex/road-pavement-engineering`，没有创建新分支或动无关工作树改动。
- 未运行应用测试或性能试算，因为正式实施尚未开始；旧不限时搜索不重启，原通知任务保持停用。


## 实施验收证据（2026-09-27）

- `check-prerequisites.ps1 -Json -RequireTasks -IncludeTasks`运行一次，退出0。先新增事件契约及方案通知测试，确认因缺失能力失败（2项）；再实现，不增加依赖。
- 后端相关批次：`python -m pytest test_pavement_hybrid.py test_pavement_stream.py test_pavement_api.py test_pavement_contracts.py test_pavement_solver.py -q`（完整路径见quickstart），退出0，111项通过。最初测试客户端依赖httpx2缺失，改用仓库现有ASGI测试器指定2.4协议，未安装新依赖；随后批次全部执行成功。
- 前端相关批次：`node --test --test-concurrency=1`执行pavementLiveSolve、pavementResults、contractsCompatibility，退出0，25项通过。
- `npm run build`首次runner输出管道中断、没有成功结果；恢复后执行完成，退出0，TypeScript及Vite构建通过。Vite仍提示单包超过500kB，未为此扩大重构。
- 完善OpenAPI的application/x-ndjson声明及镜像路径断言后，仅重跑两个受影响用例，2项通过。没有重复运行无关整套测试。
- 源文件`strategies/pavement.py`与API/前端工作流实现本次执行与通知；资源路径约束、贪心优先规则、目标、任务生成与用户数据没有改动。新增`src/api/schedulingApi.ts`一项领域导出是接入所必需，已同步plan，非新增业务范围。

### 真实规模与实时交付

证据根：`.local-data/logs/20260927-193733-pavement-live/`，全部为本次独立证据，旧不限时试算不重启。

| 验证 | 实际结果 |
|---|---|
| 原V26快照 | SHA256 `83d619b0f18809779aa3f984e2c5eb26741d4f301037bc4d06e41f115524616b`，100任务、共享1机组，源文件哈希未变 |
| 15秒混合计算 | 首解324天，0.0269秒发布；2.1151秒318天、2.6647秒314天、4.2572秒311天、6.3148秒310天 |
| 阶段耗时 | 贪心0.017376秒、建模0.140543秒、CP-SAT14.868985秒、计算合计15.051245秒 |
| 最终方案 | 310天，比324天缩短14天，施工完成2027-07-29，FEASIBLE，未证明最优 |
| 配置与策略 | 8worker、seed0、use_lns=true；search.log实际记录graph_cst_lns、scheduling_intervals_lns、graph_var_lns等调度与改善 |
| 合法性 | 初解、全部已发布改善及最终方案均经独立数值硬约束校验通过；完整100任务及4段条件日期保留 |
| 真实HTTP | started 0.2734秒、首解0.3405秒、依次318/314/311天，complete 15.3305秒；计算本身15.046203秒 |
| HTTP终态 | 311天、缩短13天、FEASIBLE；独立重跑结果有波动，未承诺必达310。generated与每份计划一致，保存的场景请求前后完全相同 |
| 真实页面 | 运行中显示“当前最好324天/正在优化”和完整任务/条件日期；本次页面最终310天、缩短14天，明确尚未证明最优；截图page-final.png |
| 断连 | 另一独立请求收到初解后主动关闭socket；服务PID15472在断开后第1与第3秒CPU均220.359375秒，增量0。测试同时证明worker join、绑定前后取消竞态及异常释放 |

summary.json、result.json、search.log、http-summary.json、http-final.json、disconnect.json、disconnect-cpu.json和page-final.png保留完整证据。真实HTTP用逐行读取而非缓冲TestClient证明提前交付。页面验收完成后保留最终方案，没有点击保存配置。

### 基线与非核心例外

- 更新架构快照仅限069新增路由、4个可选诊断字段（含引用它的18份schema）及前端流式API导出；未把全部当前快照覆盖为基线。`baseline-scope-check.json`确认新增字段、路由和API导出与当前捕获一致。
- 两端架构`--check`仍退出1。后端保留既有task-view-display-map路由、process_id/资源字段、apply_unified_target_achievement导出及requirements基线差异；前端保留既有MinimumResourceVerification、UnifiedSolveMetadata类型导出差异。它们不是069引入，相关核心契约及功能验证已通过，不扩修。
- `validate_repository.py`仍退出1：requirements依赖基线不一致。本次没有修改requirements或安装依赖。
- 规格阶段生命周期检查的9处历史工作包引用缺失保留，无069路径问题。未做清理或迁移。
- `git diff --check`针对本次关键路由/前端实现通过；只有仓库既有LF/CRLF提示。
- 当前服务启动时旧8000端口不可用，按runtime脚本恢复并验证health=ok；最终仅重启本次启动且身份核对的服务进程以加载OpenAPI声明，服务端仍绑定127.0.0.1:8000，不公开部署。

### 完成边界

本次核心目标已交付；并行优化仍可能停在不同可行工期，15秒预算不等于最优证明。原业务模型、下界和主数据未更改。多线程低核适配由参数测试覆盖，未在多种物理硬件上跑性能基准；旧架构/依赖/历史引用问题仍存在。

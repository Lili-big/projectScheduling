# 实施任务：贪心初步计划与 CP-SAT 限时优化

**日期**：2026-09-26  
**状态**：13/13，用户已确认实施，核心验收完成；既有非核心仓库检查差异见下方记录。  
**输入**：[规格](./spec.md)、[计划](./plan.md)、[决策](./research.md)、[数据模型](./data-model.md)、[接口契约](./contracts/hybrid-solve.md)、[验证指南](./quickstart.md)。

## Phase 1：共享结果契约

- [x] T001 在`04-demo/backend/tests/test_pavement_contracts.py`与`04-demo/frontend/tests/contractsCompatibility.test.mjs`加入PavementOptimization字段往返、缺省省略、合法状态组合、旧结果及桥梁不受影响的验收，先确认现有实现缺失。
- [x] T002 在`04-demo/backend/app/contracts/pavement.py`、`contracts/_models.py`及`04-demo/frontend/src/contracts/pavement.ts`、`contracts/scheduler.ts`实现data-model.md的可选结果对象及挂载；按实际引用调整两端`contracts/__init__.py`和`contracts/index.ts`导出。保留原请求/配置结构，不写持久化兼容迁移。

## Phase 2：US1 合法初步计划（P1）

**独立验证**：调用初解构造器获得完整数值计划；用输入硬规则逐项检查，无需等待CP-SAT。

- [x] T003 [US1] 新增`04-demo/backend/tests/test_pavement_hybrid.py`的贪心与校验用例，复用现有合成数据构造方法，覆盖三策略/平局确定性、25段100任务、单/多共享或专用机组、配套不占主机组、三态移交/全待定/严格后置、实际相邻转场、FS/SS/FF/SF、固定顺序/开始/机组、硬里程碑、缺资源/缺项及预算中断。逐项篡改候选的日期、分配、路线和完整性，证明数值校验能拒绝违约。先证明当前功能缺失。
- [x] T004 [US1] 在`04-demo/backend/app/scheduling/solver/strategies/pavement_heuristic.py`实现内部候选、三种贪心、稳定平局、截止检查及纯数值硬约束校验。以当前生成任务为唯一输入，不重算工效、不写数据、不调用CP-SAT生成初解；正确处理四类关系及不同机组可重叠时间，贪心失败只返回构造失败而非INFEASIBLE。
- [x] T005 [US1] 在`04-demo/backend/app/scheduling/solver/strategies/pavement.py`提取统一数值结果转换，贪心/求解器候选共用任务、资源分配、转场/等待、里程碑和pending条件日期生成。在`04-demo/backend/tests/test_pavement_hybrid.py`核对转换与原直接求解成功结果语义一致，尤其E边界/最后施工日、配套最早任务及不计末尾养生。

## Phase 3：US2 提示优化与安全回退（P1）

**独立验证**：16天合法种子经真实CP-SAT可改善到13天；受控UNKNOWN/剩余预算耗尽仍返回完整合法种子。

- [x] T006 [US2] 在`04-demo/backend/tests/test_pavement_hybrid.py`和`test_pavement_solver.py`添加状态矩阵、无初解冷启动、较短/同工期选择、提示不锁定路线、种子上界、预算分配、贪心/建模循环截止及内部不一致验收；覆盖FS安全剪枝、SS/FF/SF不得按祖先关系误剪、pending逆向边及单/多机组。使用可控时钟/求解返回测试超时分支，另保留真实小样例验证，不用mock替代实际约束正确性。
- [x] T007 [US2] 在`04-demo/backend/app/scheduling/solver/constraints/pavement.py`暴露提示所需内部路线变量，保留AddCircuit和AddNoOverlap；仅删除可证明的FS逆向与pending→normal边。同步调整`strategies/pavement.py`的内部调用及提示映射，确保合法种子完整映射，不能固定其路线/分配，不做跨机组跳层或SS/FF/SF不安全剪枝。
- [x] T008 [US2] 在`04-demo/backend/app/scheduling/solver/strategies/pavement.py`接入共享总预算、三规则初解选择、AddHint与合法上界、剩余时间求解、优化结果数值校验和最终方案选择；填充新元数据。按契约实现UNKNOWN/未运行回退、无初解原路径、输入错误及PAVEMENT_OPTIMIZER_INCONSISTENT，消除已回退成功时原“无可行计划”误导诊断；不改变目标、worker、随机种子或客户配置。

## Phase 4：US3 清晰展示来源及改善（P2）

**独立验证**：固定响应样例即可核对页面，真实结果无需人为改日期。

- [x] T009 [US3] 在`04-demo/frontend/tests/pavementResults.test.mjs`补充元数据presenter与组件SSR用例，覆盖初步/最终/改善、greedy回退且optimizer UNKNOWN、CP-SAT单独成功、最优、未启动、内部错误、历史缺字段和pending日期，先确认当前页面缺失。
- [x] T010 [US3] 在`04-demo/frontend/src/features/scheduleResults/presenter.ts`和`ScheduleResultsWorkspace.tsx`接入简明的初步→最终工期/缩短天数及来源文案；整体计划状态优先，详情可读阶段耗时。旧响应原样显示，失败不填日期，不把原始CP-SAT UNKNOWN覆盖为整体未知，也不把greedy方案冒充已证明最优。

## Phase 5：接口、实际验收与完成证据

- [x] T011 在`04-demo/backend/tests/test_pavement_api.py`验证场景/直接求解接口同一回退语义、字段序列化、原HTTP错误及主数据不变；在`04-demo/frontend/tests/pavementWorkflow.test.mjs`验证输入变化失效及桥梁/镜像现有支持边界。API/应用层只检查接入，现有分派有效则不改路由；不伪造镜像成功响应。
- [x] T012 按`03-requirements/specs/068-pavement-greedy-cpsat/quickstart.md`运行一次相关测试批次及构建，修复本功能失败后仅重跑受影响部分。按`04-demo/runtime/README.md`更新本地构建/服务，完成当前输入只读试算、3次初解性能与1次完整混合求解、页面验收和数据前后指纹核对；将版本、环境、初解/最终工期、各阶段耗时、状态与规则检查结果写入本目录`tasks.md`。若SC性能或正确性不满足，修复本功能并重新测受影响指标，不能把未达标写成完成。
- [x] T013 执行quickstart中的文档/仓库/生命周期与两端架构检查；仅更新`04-demo/backend/tests/fixtures/architecture/backend-baseline.json`、`04-demo/frontend/tests/fixtures/architecture/frontend-baseline.json`中本规格引入的共享字段/导出差异，保留既有漂移。把实际证据与例外记录在本目录`tasks.md`，更新本目录`spec.md`、`plan.md`、`03-requirements/specs/README.md`以及`agent.md`、`04-demo/README.md`中确有变化的当前能力，不修改历史063—067完成证据。

## 依赖与执行顺序

顺序：T001→T002→T003→T004→T005→T006→T007→T008→T009→T010→T011→T012→T013。

测试先确认功能缺失再实现；结果契约是共享前置，US2依赖US1数值候选和转换，US3依赖契约/状态语义，可先用固定样例验证。任务涉及共享文件，默认顺序实施，不安排并行代理。共13项：基础2项、US1 3项、US2 3项、US3 2项、综合验收3项。

## 一次跨产物一致性检查

| 需求/验收 | 设计决策 | 任务覆盖 |
|---|---|---|
| US1-1/2；FR-001/002/004/012；SC-001 | D1/D5，完整输入、三规则、约束保持 | T003、T004、T012 |
| US1-2/3；FR-003/004；SC-002 | D5/D7，数值校验及统一结果 | T003—T005、T006、T011 |
| US1-4；FR-007/011 | D4/D5，无初解冷启动、不得误判无解 | T003、T006、T008、T011 |
| US2-1/2；FR-005；SC-003 | D2/D6，提示、上界、保守剪枝 | T006—T008、T012 |
| US2-3/4/5；FR-006/010/011；SC-002/003 | D4，状态矩阵/不退化/不伪造最优 | T006、T008—T011 |
| FR-008/013；SC-001/004/006 | D3/D7，整体预算和真实性能口径 | T004、T006、T008、T012 |
| US3-1/2/4；FR-009；SC-005 | D3/D4，新元数据和结果展示 | T001、T002、T009、T010 |
| US3-3；FR-010；SC-005 | D4/D8，失败/历史/桥梁/失效兼容 | T001、T006、T009—T011、T013 |
| FR-004/013；SC-005/006 | D8，不放宽规则/不修改主数据/不新增局部搜索 | T003、T006、T011—T013 |

核对结论：13项FR、6项SC、3个故事全部验收条目和8项决策有实现/证据覆盖；没有独立局部搜索、线程面板或异步接口等未授权扩展。全部任务有精确目标路径，依赖无冲突。一次核对已修正前端验证命令为仓库现有Node测试方式，未引入tsx。无剩余阻塞项；本清单及一致性结论已获用户确认实施。

## 规划阶段校验记录

2026-09-26已完成一次跨产物核对与资产验证：

- create-new-feature、setup-plan、setup-tasks均退出0，目录由官方脚本解析为068-pavement-greedy-cpsat；Git分支仍为codex/road-pavement-engineering。
- validate_docs.py退出0，14份受管文档链接/API事实通过。
- validate_repository.py退出1，仍为既有requirements.txt依赖审批差异，与067记录一致；本轮没有改依赖文件。
- validate_lifecycle_workspace.py退出1，仍为9项历史工作包引用缺失；没有本次目录的新违规。
- 规格索引及agent.md仅增加待实施引用，不宣称算法已上线。未修改业务代码、运行服务或客户状态。
- 算法测试、真实试算、页面更新及性能指标留待用户确认实施后执行；1秒初解和15秒总预算效果尚未实测。

## 实施验收记录（2026-09-26）

用户本轮“确认实施”作为授权；沿用 codex/road-pavement-engineering，未覆盖原有工作树变更。没有新增依赖、修改客户数据、改工效/机组数量/移交状态或扩大求解时限。

### 交付与测试证据

- 新增数值候选、earliest_start/longest_chain/least_transfer 三规则及独立硬约束检查；统一结果转换覆盖任务、资源、等待、实际相邻转场、里程碑和待移交条件日期。
- 完整提示覆盖日期、资源分配、路线首尾/空路线/相邻边、ready、里程碑及总工期。保留 AddCircuit、AddNoOverlap；仅裁剪非负 FS 链逆向与 pending→normal 边。没有固定初解路线或分配。
- 同一总预算覆盖输入校验、构造、建模和优化；模型内部循环检查截止。无剩余时间不调用求解器。合法初解+UNKNOWN/预算耗尽保留 FEASIBLE；合法初解却模型报无解/无效或优化结果违约则明确 MODEL_INVALID/PAVEMENT_OPTIMIZER_INCONSISTENT。
- 新增可选 PavementOptimization，不改变请求/存储结构。页面显示初步→最终工期、改善、来源和阶段耗时；整体可行状态不会被优化器 UNKNOWN 覆盖。
- 测试先行的缺失证据：契约测试 ImportError/缺少 TypeScript 字段；初解模块测试 ModuleNotFoundError；混合测试缺 generate_initial_candidates；页面测试缺 optimizationText。均先确认缺失，再完成实现。
- `.venv/Scripts/python.exe -m pytest 04-demo/backend/tests/test_pavement_hybrid.py 04-demo/backend/tests/test_pavement_solver.py 04-demo/backend/tests/test_pavement_contracts.py 04-demo/backend/tests/test_pavement_api.py 04-demo/backend/tests/test_pavement_generation.py -q`：首次 115 通过、1 失败；失败为新增测试误把正常待移交 info 诊断当作应为空。修正为仅允许该 info，定向重跑 `test_pavement_api.py -k hybrid -q` 退出0、1通过；116项验收最终均通过。
- `node --test --test-concurrency=1 04-demo/frontend/tests/pavementResults.test.mjs 04-demo/frontend/tests/pavementWorkflow.test.mjs 04-demo/frontend/tests/contractsCompatibility.test.mjs`：首次25通过、1失败；原因是新类型实际由 contracts/index.ts 导出，测试基线误加到旧 scheduler.ts 导出。移除错误基线增量并验证真实入口，定向重跑 contractsCompatibility.test.mjs 退出0、11通过；26项验收最终均通过。未吸收旧导出漂移。
- 确定样例：共享1套、跨段1天、A两道3天工序 FS+7、B一道2天；合法16天种子经真实 CP-SAT 调整路线成为13天且 OPTIMAL。受控UNKNOWN保留16天及完整摘要；无初解冷启动、同值保留、预算中断、非法优化结果与模型矛盾均有验收。
- `npm.cmd run build` 退出0，TypeScript及Vite通过；保留已有主包大于500kB提示，无新增依赖。
- `git diff --check` 退出0。桥梁结果可选字段缺省省略；原失效机制和演示镜像拒绝路面边界仍有效。

### 当前客户100任务实测

环境：Windows、Python 3.12.14、OR-Tools 9.15.6755、Pydantic 2.13.5、Node v24.18.0。版本 `pmv-975eba0fd297417586cb4798f74efd6c`（V26），25段100任务，18有日期+3已移交+4待定；共享1套，跨段转场1天，当前各工效800m/天，FS+0/7/7，计划起点2026-09-23，总预算15秒。API读取和任务生成在求解计算计时之外。

| 仅初解构造＋校验（预热后） | 耗时 | 合法候选数 | 选中策略 | 总工期 |
| --- | ---: | ---: | --- | ---: |
| 第1次 | 0.018486秒 | 3 | earliest_start | 324天 |
| 第2次 | 0.018220秒 | 3 | earliest_start | 324天 |
| 第3次 | 0.018269秒 | 3 | earliest_start | 324天 |

完整混合求解：初解0.018296秒、建模0.140626秒、CP-SAT 13.688245秒、总计13.860589秒（含校验和收尾）。CP-SAT返回FEASIBLE，同值未改善；整体FEASIBLE，采用greedy初解，324→324天、改善0天。未声称当前大样例已证明最优。最后施工日2027-08-12，无末尾养生；完整计划再次通过数值硬约束检查。

| 待移交段 | 按本计划需移交日 | 预计施工完成日 |
| --- | --- | --- |
| 05 左幅 K671+440-K672+000 | 2027-07-15 | 2027-08-02 |
| 11 右幅 K666+910-K667+200 | 2027-07-18 | 2027-08-06 |
| 15 右幅 K671+551-K672+200 | 2027-07-21 | 2027-08-08 |
| 25 平果互通连接线 LK0+000-LK0+454.768 | 2027-07-26 | 2027-08-12 |

所有16个待移交任务严格排在其余84任务全部完成之后，以上为以届时路床移交为前提的计划日期，未回写实际移交事实。

只读校验前后、浏览器求解后均相同：scheduler-config.json SHA256 `84e758f26c50e86052653502414b14fe726e8892852c51de9f98a321e6359976`；project-master.db SHA256 `6ae8fa69b78937d217ff5c934137c40412dd349aa5090278c4a31820419a9b50`。本地原始验收输出位于 `.local-data/logs/pavement-validation/068/`，不提交客户快照。

### 运行服务与页面

按 runtime/README.md 构建并更新8000服务。首次普通权限停止旧服务未成功，启动发生端口冲突；核实PID21532及父PID4488的路径/命令属于当前项目后，以授权的进程操作完成重启。最终启动器PID27344，服务PID4608，日志 `.local-data/logs/20260926-104413-284/`，health返回ok。没有按名称批量终止其他进程。

独立浏览器标签页 `http://127.0.0.1:8000/?engineering_domain=pavement` 使用当前配置点击“按固定机组求解”，实际显示“路面排程结果·可行”“初步324天→最终324天·缩短0天·采用初步计划”，25段100层、4个待移交段条件日期及2027-08-12完成日均可见；原页面及未保存草稿未触碰。UNKNOWN回退页面由受控接口及SSR验收，不伪造真实试算的优化器状态。

### 仓库检查与保留例外

- validate_docs.py：退出0，14份受管文档链接及API事实通过。
- validate_repository.py：退出1，仍为规划/067已记录的 requirements.txt 依赖审批哈希差异，本次未改依赖。
- validate_lifecycle_workspace.py：退出1，仍为9条旧工作包引用缺失（7条2026年7月资料、2条json-task-viewer旧输入输出），无068新违规。
- 后端架构检查：退出1。仅增量更新 PavementOptimization、新 ScheduleResult 字段及17个嵌套引用、对应app.models导出。剩余46处差异为既有路由/导出、process_id、compatible_process_ids及固定场景哈希，保留原漂移，未全量刷新基线。
- 前端架构检查：退出1。旧scheduler入口没有新增本类型导出，基线无需改变；差异仍为 MinimumResourceVerification、UnifiedSolveMetadata 两个先前导出。新contracts入口有直接测试。

上述例外不影响068核心正确性、性能和页面验收，未扩展修理历史治理问题。算法仍为启发式初解＋限时优化，复杂约束可能使三种构造均失败，此时冷启动CP-SAT；不保证任意输入必有初解或15秒内证明全局最优。用户页面仍等待一次同步请求完成，0.018秒是内部初解时间。

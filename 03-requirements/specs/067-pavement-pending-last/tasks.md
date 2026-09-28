# 实施任务：待移交施工段后置排程与日期提示

**日期**：2026-09-25  
**状态**：11/11，已完成。用户于2026-09-25确认实施；实际证据见文末。  
**输入**：[规格](./spec.md)、[计划](./plan.md)、[决策](./research.md)、[数据模型](./data-model.md)、[接口契约](./contracts/pending-handover.md)、[验收指南](./quickstart.md)。

## Phase 1：契约基础

- [x] T001 在`04-demo/backend/tests/test_pavement_contracts.py`和`04-demo/frontend/tests/contractsCompatibility.test.mjs`补充可选规则/待定范围/日期字段的往返与缺省序列化验收，覆盖旧路面及桥梁字段不变；先确认当前实现缺失。
- [x] T002 在`04-demo/backend/app/contracts/pavement.py`与`04-demo/frontend/src/contracts/pavement.ts`新增pending_policy、pending_sections、pending_section_dates及其明细类型，按data-model实现缺省省略。沿用`04-demo/backend/app/contracts/_models.py`、`04-demo/frontend/src/contracts/scheduler.ts`及各自`contracts`导出入口的既有挂载；仅在实际引用需要时调整导出，不改主数据/配置持久化结构。

## Phase 2：US1 全部任务纳入并严格后置（P1）

**独立验证**：小规模混合三态输入可生成全部任务；任意机组配置下pending任务start不早于正常任务最大end，原容量/转场/日期/关系仍满足。

- [x] T003 [US1] 在`04-demo/backend/tests/test_pavement_master.py`、`test_pavement_generation.py`、`test_pavement_solver.py`、`test_pavement_api.py`补充生成与后置验收，并替换064中已被本规格取代的“pending排除/全待定不可排”断言。覆盖单/多机组、养生空档、正工期配套、全待定/无待定、停用/全空、缺量/工效/资源、固定顺序和硬里程碑冲突、直接solve省略或篡改scope、旧blocked输入；先确认新行为缺失或失败。
- [x] T004 [US1] 修改`04-demo/backend/app/scheduling/generation/pavement.py`与`04-demo/backend/app/project_master/validation.py`：pending按原工艺/工效生成完整施工及配套任务，保留真实属性，恢复执行参数校验，附条件调用可取计划相对下界0，输出统一新scope。检查`04-demo/backend/app/project_master/scheduling_adapter.py`中的段级投影/诊断升级，仅修改妨碍pending合法生成的相关分支；保留主数据待完善保存能力和空态。
- [x] T005 [US1] 在`04-demo/backend/app/scheduling/solver/strategies/pavement.py`从任务事实分组，校验或推导scope，实施B=max正常end及全部pending start>=B；全pending取B=0。保留原机组路线、目标、关系、转场和硬约束。在`04-demo/backend/app/scheduling/application/pavement.py`与`04-demo/backend/app/api/routers/scheduling.py`统一新旧输入与失败范围行为，确保两条求解入口一致且不能绕过；不改`solver/constraints/pavement.py`的机组路线模型。

## Phase 3：US2 条件日期与清晰标记（P1）

**独立验证**：用可行结果样例核对段级两类日期与全部任务起止一致；用失败及历史样例证明不会显示假日期或改写原范围。

- [x] T006 [US2] 在`04-demo/backend/tests/test_pavement_solver.py`和`test_pavement_api.py`加入两任务确定日期、配套任务日期聚合及失败无日期验收；在`04-demo/frontend/tests/pavementTaskPreview.test.mjs`、`pavementWorkflow.test.mjs`、`pavementResults.test.mjs`、`pavementMaster.test.mjs`加入附条件组/原因/日期、旧结果兼容、输入变动失效、主数据事实保留的验收，先确认当前展示缺失。
- [x] T007 [US2] 在`04-demo/backend/app/scheduling/solver/strategies/pavement.py`仅对FEASIBLE/OPTIMAL聚合pending段的最小start_date和最大finish_date，写入pending_section_dates；成功/失败结果携带对应范围，失败不创建日期。保证结构ID唯一、配套任务计入、序列化沿用现有结果路径，不写入主数据。
- [x] T008 [US2] 在`04-demo/frontend/src/domain/pavement.ts`、`features/taskView/TaskViewWorkspace.tsx`和`features/logic/LogicTab.tsx`显示全部生成段，取消pending过滤及“待定段不排程”提示，显示“待移交·附条件排程”和原原因；固定顺序预览包括现纳入段。检查`04-demo/frontend/src/app/Workspace.tsx`现有生成/结果失效接入，仅修复本变更导致的旧结果残留，不增加自动保存。
- [x] T009 [US2] 在`04-demo/frontend/src/features/scheduleResults/presenter.ts`及`ScheduleResultsWorkspace.tsx`显示含假设的实际范围与完成日期，并展示“施工段、待移交原因、按本计划需移交日期、预计施工完成日期”表及移交前提。失败不显示日期；历史只读自身scope/summary，不关联当前主数据重算。复用现有表格布局。

## Phase 4：验证与完成证据

- [x] T010 按`03-requirements/specs/067-pavement-pending-last/quickstart.md`运行一次相关后端/前端批次和构建，修复本次失败后仅重跑受影响部分；运行`00-governance/repository-tools/validate_docs.py`、`validate_repository.py`、`validate_lifecycle_workspace.py`，区分新增问题与已知基线。共享契约造成架构快照差异时，通过`04-demo/backend/scripts/capture_architecture_baseline.py`与`04-demo/frontend/scripts/captureArchitectureBaseline.mjs`核对，只更新各自`tests/fixtures/architecture/`中067能解释的差异，不吸收无关漂移。
- [x] T011 按`04-demo/runtime/README.md`更新本地服务并进行quickstart的实际25段页面与一次真实求解检查，前后只读比较`.local-data/state/project-master.db`和`scheduler-config.json`中的主数据/配置，确认未写入假移交日或改资源。把实测状态、日期核对或UNKNOWN限制、刷新/序列化结果、测试与未覆盖风险记录在本文件；更新`03-requirements/specs/README.md`、本目录spec/plan状态，以及`agent.md`、`04-demo/README.md`中确实受本规则改变影响的现行说明。核心验收未通过不得勾选完成，不改历史064—066证据。

## 依赖与执行顺序

T001→T002→T003→T004→T005→T006→T007→T008→T009→T010→T011。测试先确认新增行为缺失，再实现；不重复执行无变化的完整测试。US2页面可用固定结果样例独立验证，实际日期输出依赖US1的可行解。任务涉及共享文件，默认顺序执行，不安排并行代理。

两项P1故事均为本次交付范围，不以只完成纳入排程替代日期提示。无新增依赖、主数据迁移、机组增配、算法目标调整或独立性能优化。

## 一次跨文档一致性检查

| 规格 | 设计决策 | 实施/验收 |
|---|---|---|
| US1；FR-001、FR-010；SC-001、SC-004 | D1、D7：完整生成，事实不变 | T003、T004、T011 |
| US1；FR-002、FR-003；SC-002 | D2、D3：正常max end硬边界，原资源及约束保持 | T003、T005；单/多机组与转场样例 |
| US1；FR-008 | D5：接口一致，scope不覆盖事实 | T001—T005；直接输入与旧输入样例 |
| US2；FR-004 | D4：附条件范围与原因 | T006、T008、T009 |
| US2；FR-005、FR-006；SC-003、SC-004 | D4、D7：可行日期聚合，不回写事实 | T006、T007、T009、T011 |
| US1/US2；FR-007；SC-005 | D4、D5：失败、空态与输入失效 | T003、T005—T010 |
| US2；FR-009；SC-005 | D6：历史从自身结果读取 | T001、T006、T009 |

结论：10项FR、5项SC、2项P1故事、7项设计决策均有实现及验收覆盖；后置范围包含正工期配套，末日/边界无额外一天，当前客户UNKNOWN未误写为功能出解承诺。无阻塞冲突或未覆盖需求。共11项任务，基础2项、US1 3项、US2 4项、收尾2项。

## 规划校验与实施证据

2026-09-25规划校验：validate_docs.py通过（14份受管文档）；validate_repository.py仍报告既有requirements.txt依赖审批差异；validate_lifecycle_workspace.py仍为既有9项历史工作包引用缺失，没有本次目录违规。两项全仓基线问题未纳入本功能修复。

用户已确认本清单，按speckit-implement完成实施；未改变经确认的业务口径。


### 2026-09-25实施证据

- 前置命令：check-prerequisites.ps1 -Json -RequireTasks -IncludeTasks退出0。
- T001/T003/T006的新验收先在旧行为上失败：缺少契约字段、pending任务被排除、缺少条件日期/前端标识，证明覆盖到了本次行为变化。
- 后端：quickstart指定的5个pytest文件首次74通过、1失败。唯一失败是新增API用例假定None字段必定输出；现有序列化会省略该字段，修正为get判空后，仅重跑test_pending_direct_and_scenario_solve_have_same_dates_and_keep_facts，1通过。累计75项均有通过证据，未重复全量测试。
- 前端：quickstart的5个Node文件37项全通过；另增加并执行结果组件SSR用例1项通过，验证两类日期列、实际移交仍待确认，以及失败结果不泄露成功日期。累计38项通过。
- npm.cmd run build退出0，包含TypeScript检查；Vite仍有大于500kB的既有分包提示，无构建失败。发布到本地的JS为index-AO7meQh1.js。
- 单/多机组、正常段养生空档、正工期配套任务均验证pending最早start不小于正常任务最大end；全pending可从计划起点条件起排。原FS/SS/FF/SF、机组能力/范围、实际转场、硬里程碑及无末尾养生用例通过。
- 两任务样例：正常A为2026-09-23—24，转场25日，pending B需移交26日、预计完成27日；结果JSON往返一致，场景对象及真实pending属性不变。直接solve省略scope仍强制后置，伪造scope及旧blocked输入被拒绝。
- 主数据适配器和API现有流程可复用，无需改路由；直接solve的输入错误继续HTTP 422，场景结果继续MODEL_INVALID，契约已说明传输区别。
- 实际数据：确认版本V26（pmv-975eba0fd297417586cb4798f74efd6c），25段100核心任务，正常21段84任务、待定4段16任务。新页面任务视图和结果页均显示“其中4段待移交，附条件排程”，并保留5/11/15/25段的原原因。
- 实际试算采用已保存的2026-09-23计划起点、1套共享机组、跨段转场1天、15秒时限；结果仍UNKNOWN，页面未填造交付日期。未增加机组、延长时限或重试搜索来掩盖此限制；成功日期以可行合成用例和SSR验证。
- 浏览器验证页已刷新确认加载新构建，截图检查表格与提示可见。原用户页面有未保存的2026-09-01起点，原页未刷新、未保存，草稿保留；另保留更新后的验证页。没有承诺用户当前未保存方案已得到可行解。
- 后端按runtime/README.md重启，已核实旧监听进程属于当前项目；新启动PID25284、服务PID10344，日志在.local-data/logs/20260925-143143-744/，health返回ok。
- 启动/求解前后project-master.db SHA256均为6AE8FA69B78937D217FF5C934137C40412DD349AA5090278C4A31820419A9B50；scheduler-config.json均为2F63F318668C7F2F8C376C48D1B5815FAD16FA7BA29C5C97BC33BB6CFE212B83。未写回预测移交日或改变主数据/配置。

### 校验例外与剩余限制

- validate_docs.py退出0。validate_repository.py退出1，仍为既有requirements依赖审批哈希差异；validate_lifecycle_workspace.py退出1，仍为原有9项历史工作包引用缺失。本次未新增同类问题，不影响路面业务验收。
- 两端architecture --check初次退出1。后端只补齐067新增模型/字段对应的84处schema定义，递归比较剩余差异仍是既有路由、process_id、compatible_process_ids、app.scenario/app.solver导出和requirements哈希；未整体覆盖快照。前端差异仅既有MinimumResourceVerification和UnifiedSolveMetadata导出，无067新增差异。
- 当前客户100任务在15秒内尚无可行解，因此没有真实客户交付日期可报告；本次核心规则及成功/失败显示由自动化和实际页面证明，搜索性能按规格留在本次范围之外。
- 既有全仓校验未全部通过，未执行无关全量测试；上面的已知基线问题保留。没有修改历史064—066完成证据。

# 实施任务：公路路面首版适配

**状态**：用户已于 2026-09-22 确认并完成首版实施；T001～T028 完成，T029 待客户数据。实际验证及既有失败见 quickstart.md。

**输入**：[spec.md](./spec.md)、[plan.md](./plan.md)、[research.md](./research.md)、[data-model.md](./data-model.md)、[接口与页面契约](./contracts/pavement-contract.md)、[验证指南](./quickstart.md)。

**执行规则**：维持当前分支及既有 README 修改；先完成用户确认，再使用 speckit-implement。默认串行，不派生子任务或新分支。代码所有权、完整边界和已知环境失败见 plan/research。

**2026-09-22 用户浏览器批注细化**：T005/T006/T008/T009范围内接入段级水稳厚度、密度及吨位表格，保留Excel往返；T023范围内精简顶部说明并修复控件裁切。用户明确确认0.76m、2.38t/m³与吨位公式；规格、设计及数据模型同步，复用通用参数与既有版本流程，不改变组件工期模型。验证证据见quickstart.md，T029状态不变。

## 共享契约（3 项）

### 2026-09-23 用户故事3增量：工序关系（5项，串行）

- [x] T039 [US3] 在 `04-demo/backend/app/contracts/pavement.py`、`04-demo/frontend/src/contracts/pavement.ts`、`04-demo/frontend/src/domain/pavement.ts`定义规则及稳定槽位、生效优先级与恢复继承，兼容旧配置；覆盖R1/R2/R4。
- [x] T040 [US3] 在 `04-demo/backend/app/scheduling/generation/pavement.py`生成显式关系并验证引用、重复、缺N及停用；在 `04-demo/backend/app/scheduling/solver/strategies/pavement.py`启用四类关系并移除重复FS，保留其他硬条件；覆盖R2/R3/R4。
- [x] T041 [US3] 在 `04-demo/frontend/src/features/logic/LogicTab.tsx`及 `04-demo/frontend/src/styles/domain-editors.css`实现统一/单段关系编辑和来源显示，保留末层/配套设置；在 `04-demo/frontend/src/features/taskView/TaskViewWorkspace.tsx`显示真实关系；覆盖R1/R2/R3。
- [x] T042 [US3] 扩展 `04-demo/backend/tests/test_pavement_generation.py`、`test_pavement_solver.py`、`test_pavement_config.py`、`test_pavement_contracts.py`和 `04-demo/frontend/tests/pavementWorkflow.test.mjs`，一次执行关系生成/四类求解/继承/配置回读/旧行为/无效输入与前端同例测试及build；覆盖R1～R5。
- [x] T043 [US3] 在当前8000页面验证编辑、保存、统一继承/单段覆盖，真实配置不写演示值；将证据写入本目录 `quickstart.md` 并核对文档及本次嵌套契约基线；覆盖R4/R5。

一致性检查：R1→T039/T041/T042；R2→T039～T042；R3→T040～T042；R4→T039/T040/T042/T043；R5→T042/T043。无新增目录/接口/资源目标、未覆盖验收或重复全套验证。依赖T039→T040→T041→T042→T043。沿用用户已确认的063实施及本轮“关系与间歇可维护、统一工艺关系允许分段调整”的明确授权；本批为同一功能修订，不另设重复确认。

## 原共享契约（3 项）

- [x] T001 在 `04-demo/backend/app/contracts/pavement.py` 新增 typed 路面设置、任务上下文、readiness 和结果摘要，在 `04-demo/backend/app/contracts/_models.py`、`04-demo/backend/app/contracts/project_master.py`、`04-demo/backend/app/contracts/__init__.py` 增加领域、类型与兼容导出；旧字段缺省和序列化保持桥梁行为，正式路面输入不能静默采用未确认等待/转场值。（FR-001、004、008～018；D1、D4、D5）
- [x] T002 在 `04-demo/frontend/src/contracts/pavement.ts`、`04-demo/frontend/src/contracts/scheduler.ts`、`04-demo/frontend/src/contracts/projectMaster.ts`、`04-demo/frontend/src/contracts/index.ts` 同步 T001 字段、单位、状态和领域区分。（FR-016～018）
- [x] T003 在 `04-demo/backend/tests/test_pavement_contracts.py` 和 `04-demo/frontend/tests/contractsCompatibility.test.mjs` 增加旧请求/旧 dump 兼容、新字段往返、非法枚举/数值及时间边界契约验收；运行本批最小契约检查。（SC-005、007）

## US1：用户数据形成路面主数据（6 项）

**可独立演示**：导入路段/幅/层，预览冲突，确认并重新读取版本；此时尚不要求能求解。

- [x] T004 [US1] 在 `04-demo/backend/tests/test_pavement_master.py` 增加两段左右幅、净长与桩号不同、单位/层序缺失、重复 ID、旧模板兼容和重新导入的验收；先确认当前缺少路面支持。（FR-001～003、016～017；US1.1～4）
- [x] T005 [US1] 在 `04-demo/backend/app/project_master/definitions.py` 增加 pavement 工点、分幅施工段、三类层及其参数定义；核对 `04-demo/backend/app/project_master/schema.py`、`04-demo/backend/app/project_master/repository.py` 与 `04-demo/backend/app/project_master/diff.py` 的保存/回读/版本行为，只修改实际必要项，保留旧主数据和指纹。（FR-001～003、017；D1）
- [x] T006 [US1] 在 `04-demo/backend/app/project_master/workbook.py` 实现兼容 1.0/1.1 的 1.2 路面模板与参数导入导出，在 `04-demo/backend/app/project_master/service.py`、`04-demo/backend/app/api/routers/project_master.py` 接入领域模板参数和现有导入流程，保留来源行、原始桩号与净量。（FR-001～003；D6）
- [x] T007 [US1] 在 `04-demo/backend/app/project_master/validation.py` 分离身份/格式阻断与排程缺项，校验几何单位、同幅重复/重叠及数量依据确认；在 `04-demo/backend/app/project_master/scheduling_adapter.py` 增加显式路面投影与对象级诊断，禁止以桥梁占位或静默丢段。（FR-001～003、005、016）
- [x] T008 [US1] 在 `04-demo/frontend/src/domain/projectMaster.ts`、`04-demo/frontend/src/api/projectMasterApi.ts`、`04-demo/frontend/src/features/projectMasterData/ProjectMasterDataWorkspace.tsx`、`04-demo/frontend/src/features/projectMasterData/WorkPointList.tsx`、`04-demo/frontend/src/features/projectMasterData/WorkPointDetail.tsx`、`04-demo/frontend/src/features/projectMasterData/ImportPreview.tsx` 接入路面展示/模板/问题定位，保留旧版本确认与空态。（FR-001～003、016、018）
- [x] T009 [US1] 在 `04-demo/frontend/tests/pavementMaster.test.mjs` 验证空态、来源与问题映射；运行 `04-demo/backend/tests/test_pavement_master.py` 及相关现有主数据测试，确认 US1.1～4 与旧数据兼容。（SC-001 的主数据部分、005、007）

## US2：三类工艺工效（4 项）

**可独立演示**：生成并解释三类核心层施工天数，保存刷新后仍可复算。

- [x] T010 [US2] 在 `04-demo/backend/tests/test_pavement_generation.py` 建立样例 A、m/m2/m3/t 单位匹配、零工程量、非法工效、层级方案选择的验收；在 `04-demo/backend/tests/test_pavement_config.py` 建立路面按项目保存且不覆盖桥梁的回读验收。（FR-004～006、017；US2.1～3）
- [x] T011 [US2] 在 `04-demo/backend/app/process_library_defaults.py`、`04-demo/backend/app/scenario_data.py` 增加三类路面核心工艺与空主数据入口；在 `04-demo/backend/app/scheduling/generation/pavement.py` 实现数量依据校验、工效选择和核心任务生成，复用现有工期计算，真实缺参不套演示默认值。（FR-004～006；D2）
- [x] T012 [US2] 在 `04-demo/backend/app/local_scenario_config.py`、`04-demo/backend/app/services/process_library_service.py`、`04-demo/backend/app/api/routers/system.py` 实现 v5 路面按项目配置保存/读取、领域查询与旧版兼容，连同 task_overrides、pavement_settings 和资源配置完整往返；失败保留旧值。（FR-016～017；D5）
- [x] T013 [US2] 在 `04-demo/frontend/src/domain/pavement.ts`、`04-demo/frontend/src/domain/productivity.ts`、`04-demo/frontend/src/domain/labels.ts`、`04-demo/frontend/src/domain/constants.ts`、`04-demo/frontend/src/domain/scenarioMutations.ts`、`04-demo/frontend/src/features/process/ProcessTab.tsx`、`04-demo/frontend/src/api/_schedulerApi.ts`、`04-demo/frontend/src/api/scenarioApi.ts` 接入三类工艺、单位、层级选择及保存；在 `04-demo/frontend/tests/pavementWorkflow.test.mjs` 增加工效验收，运行 T010 的工效/保存用例。（SC-002、005、006）

## US3：工序逻辑、等待与可用条件（3 项）

**可独立演示**：不依赖求解即可核对完整任务链、日期下限与末层交付条件。

- [x] T014 [US3] 在 `04-demo/backend/app/scheduling/generation/pavement.py` 生成实际层序、配套步骤、零天条件转接、养生 lag、移交/验收最早开工约束、显式固定顺序及末层 readiness；循环/失效引用阻断，显示排序不升级为施工约束。（FR-003、007～009、013、015～016；D3、D4）
- [x] T015 [US3] 在 `04-demo/frontend/src/domain/logic.ts`、`04-demo/frontend/src/domain/pavement.ts`、`04-demo/frontend/src/features/logic/LogicTab.tsx`、`04-demo/frontend/src/features/taskView/TaskViewWorkspace.tsx` 展示/维护路面层序、配套工期、养生和可用日期，标记配套资源充足假设；在 `04-demo/frontend/tests/pavementWorkflow.test.mjs` 验证改动使旧任务和结果过期。（FR-007～009、015～018）
- [x] T016 [US3] 在 `04-demo/backend/tests/test_pavement_generation.py` 补齐样例 B～D 的图约束、0天不增任务、末层等待、缺日期、循环及配套顺序测试，运行 US3 最小图生成与前端领域验证。（SC-003 的约束部分、004、005、006）

## US4：机组、转场与排程结果（9 项）

**可独立演示**：三类机组分别配置，输出真实资源顺序、养生穿插和可交付日期。

- [x] T017 [US4] 在 `04-demo/backend/app/scheduling/domain/resource_scope.py` 与 `04-demo/backend/app/scheduling/application/_scenario.py` 增加显式路面资源作用域、单工点选择和三类命名机组展开，携带确认的转场参数；零数量和不匹配资源不回退无限容量，桥梁范围保持原行为。（FR-010～013、016；D2）
- [x] T018 [US4] 在 `04-demo/frontend/src/domain/resources.ts`、`04-demo/frontend/src/features/resources/ResourcesTab.tsx` 适配三类机组数量、范围和转场天数，禁用路面关键资源无限模式及跨类别混配；在 `04-demo/frontend/tests/pavementWorkflow.test.mjs` 验证配置含义和指纹变化。（FR-010～012、017～018）
- [x] T019 [US4] 在 `04-demo/backend/app/scheduling/solver/constraints/pavement.py` 实现机组分配绑定的实际相邻路径和跨位置转场硬约束，覆盖原位换层、往返、初次/末尾无自动转场及机组空闲；不引入桥梁距离惩罚。（FR-011～013；D3）
- [x] T020 [US4] 在 `04-demo/backend/app/scheduling/solver/strategies/pavement.py`、`04-demo/backend/app/scheduling/application/pavement.py` 实现固定资源路面求解、充分时间上界、readiness 完成目标和状态/诊断；在 `04-demo/backend/app/scheduling/solver/engine.py`、`04-demo/backend/app/scheduling/solver/results.py`、`04-demo/backend/app/scheduling/application/_scenario.py` 接入领域分派和结果组装，保留桥梁算法。（FR-003、008、011～016）
- [x] T021 [US4] 在 `04-demo/backend/app/api/routers/scheduling.py`、`04-demo/backend/app/api/routers/assistants.py`、`04-demo/backend/app/api/errors.py` 接入路面 materialize/生成/求解及不适用入口拒绝，复核 `04-demo/backend/app/scheduling/domain/milestone_scope.py` 与前端 `04-demo/frontend/src/domain/milestones.ts` 不误用桥梁交付目标；在 `04-demo/tools/demo-api-mirror/api.mts` 明确拒绝路面新领域而非桥梁回退。（FR-013、016～018；契约 HTTP 表）
- [x] T022 [US4] 在 `04-demo/frontend/src/features/scheduleResults/presenter.ts`、`04-demo/frontend/src/features/scheduleResults/ScheduleResultsWorkspace.tsx` 呈现施工/养生/配套/转场、机组路径、来源与末层可用日期；在 `04-demo/frontend/tests/pavementResults.test.mjs` 验证日期边界不多加1天、demo标记和非最优状态。（FR-014～016；SC-004）
- [x] T023 [US4] 在 `04-demo/frontend/src/app/Workspace.tsx`、`04-demo/frontend/src/app/useWorkspaceController.ts`、`04-demo/frontend/src/app/workflows/scenarioWorkflow.ts`、`04-demo/frontend/src/app/workflows/solveWorkflow.ts`、`04-demo/frontend/src/features/layout/WorkspaceNavigation.tsx`、`04-demo/frontend/src/api/schedulingApi.ts` 装配路面入口、保存回读、主数据版本引用、求解状态/失效及不适用模块说明；桥梁旧入口与历史成果保留，扩展 `04-demo/frontend/tests/pavementWorkflow.test.mjs` 覆盖闭环。（FR-016～018；SC-006～007）
- [x] T024 [US4] 在 `04-demo/backend/tests/test_pavement_solver.py` 验证样例 B～D、数量1/2/0、转场仅计实际相邻边、往返与同位换层、远期移交上界、末层交付、无解/限时状态和无硬约束放宽；检查结果中的转场与资源占用一致。（SC-003～005）
- [x] T025 [US4] 在 `04-demo/backend/tests/test_pavement_api.py` 验证新旧领域 HTTP、直接 /api/solve 不绕过校验、模板导入→版本→生成→求解、配置损坏/缺数据/不支持策略及镜像拒绝；运行本批 solver/API 与相关前端结果检查。（SC-001、005～007）

## 收敛与真实数据验证（4 项）

- [x] T026 以 `04-demo/backend/scripts/capture_architecture_baseline.py` 和 `04-demo/frontend/scripts/captureArchitectureBaseline.mjs` 检查本次共享字段差异；仅在差异可由本规格解释时更新 `04-demo/backend/tests/fixtures/architecture/backend-baseline.json`、`04-demo/frontend/tests/fixtures/architecture/frontend-baseline.json`，在 `03-requirements/specs/063-road-pavement-adaptation/quickstart.md` 记录变化，不将既有依赖哈希/无关路由漂移一并吞入。（FR-017；SC-007）
- [x] T027 按 `03-requirements/specs/063-road-pavement-adaptation/quickstart.md` 执行一次最终后端/前端/构建、真实 HTTP/浏览器、架构和生命周期检查，记录实际退出结果及既有失败对比；SC-001～007 的本次核心检查全部通过才宣称自动样例闭环完成。
- [x] T028 根据实际完成情况更新 `README.md`、`agent.md`、`04-demo/README.md`、`03-requirements/specs/README.md` 和 `03-requirements/specs/063-road-pavement-adaptation/tasks.md`，只描述已实现范围，保留未覆盖的配套资源、天气与真实数据验证边界。（FR-018；SC-001～007）
- [ ] T029 用户真实数据提供后，在 `03-requirements/specs/063-road-pavement-adaptation/quickstart.md` 的客户验证段记录字段映射依据和至少两个实际施工段的人工核对结果；原始文件只引用其正式主归属。未提供数据则保留本项未完成并记录“待客户数据”，不得阻止独立开发验证，也不得将整项真实案例验收宣称完成。（SC-008；D6）

## 依赖与执行顺序

### 用户要求层级密度/吨位与紧凑页面（2026-09-23）

- [x] T036 扩展已有层编辑模型、服务和Excel字段，持久化可选密度，兼容字段省略/显式清空；一次迁移现有水稳密度到45层，移除当前段级旧统计参数，保留厚度与停用沥青。
- [x] T037 主数据表移除3个水稳统计列，结构层编辑增加密度和实时吨位；表头单位同行、隐藏路面版本历史、精简说明及行高，保持原排程数量单位。
- [x] T038 验证密度保存/回读/往返、负值拒绝、清空及按层数量公式，测试/构建后在用户当前8000页面核对紧凑布局与数据；记录验证及剩余未填密度。

本批按用户明确修订实施，沿用已确认FR-001/002/005/016/017/018，T036→T037→T038。规格、数据模型、计划与任务一致；无新增算法或资源假定，密度仅继承已确认水稳值，未知字段允许用户补填，无需额外确认。

### 用户要求默认挂接并按段本地编辑（后续修订）

- [x] T033 在后端主数据模型/服务/接口实现默认5层初始化、按段编辑保存、空厚度存储、稳定ID/来源保留、历史回改和陈旧基线保护；沿用SQLite版本、校验及引用保护，不改排程算法。
- [x] T034 在项目主数据施工段行下提供层编辑器及本地保存，初始化空段，保存后回读并保留当前展开段；历史只读；移除工艺逻辑模板入口，保留工序说明及逻辑配置。
- [x] T035 定向验证默认初始化/重读/重复请求、独立编辑/新增删除/排序停用、空厚度诊断、回改/并发及前端展示；初始化实际15段，验证75层本地回读与页面，记录证据。

本批根据用户明确的修订继续实施，替代T030～032中的模板入口和必须填完厚度才可创建层的交互限制。T033→T034→T035；一致性核对：对应FR-001/004/007/016/017，厚度仍未确认但保存空值不改变工程语义，默认三类机组/工效/养生规则不变。规格、方案与接口已同步，无额外业务确认。

### 用户要求继续推进的结构层补齐（2026-09-22）

- [x] T030 在 `contracts/project_master.py`、`project_master/service.py`、`project_master/repository.py`、`api/routers/project_master.py` 实现按当前版本创建结构层模板草稿；复用版本校验/确认，保留原快照和来源，拒绝覆盖已有层及陈旧基线，稳定标识及重复预览不产生重复层。
- [x] T031 在 `frontend/src/contracts/projectMaster.ts`、`api/projectMasterApi.ts`、`features/logic/PavementLayerTemplate.tsx`、`LogicTab.tsx`、`app/Workspace.tsx` 接入模板编辑、选择施工段、预览/取消/确认、版本回读及按工艺补齐缺失等待条件；层厚未填不提交，原有条件和资源参数不自动覆盖。
- [x] T032 在 `backend/tests/test_pavement_layer_template.py` 和前端路面测试验证申请→确认→回读→生成、净长/层序/旧数据保留、重复及陈旧请求；执行相关测试与构建，在 quickstart.md 记录结果与尚待用户提供的实际参数。

本批沿用已确认用户故事1、3和用户“继续推进下一步”的执行授权。T030→T031→T032；无新增算法、资源假设或存储表。实际客户层厚未确认不阻止功能实现，但阻止把假定层厚应用到真实15段。一次一致性核对：本批全部任务对应 FR-001/004/007/016/017，缺失参数仍按既有诊断；新接口/模型和验证见 plan.md、data-model.md。

- 共享：T001→T002→T003。
- US1：T003→T004→T005→T006→T007→T008→T009。
- US2：T009→T010→T011→T012→T013。
- US3：T013→T014→T015→T016。
- US4：T016→T017→T018→T019→T020→T021→T022→T023→T024→T025。
- 收敛：T025→T026→T027→T028；T029 还依赖真实客户数据到位。
- 默认不标 [P]：本轮多个阶段会触及同一生成/领域/装配文件，串行更容易保持契约一致。此任务表不授权自动创建多个代理或常驻任务。
- T010、T014、T016 共享生成文件但逐阶段扩展行为，不是重复实现；T003/T009/T013/T016/T025 是各批最小验证，T027 是唯一最终全量检查。

## 一致性检查结果（任务生成时）

### 需求与成功标准覆盖

| 来源 | 任务 |
| --- | --- |
| FR-001～003 | T001～T009、T014、T020 |
| FR-004～006 | T001～T003、T010～T013 |
| FR-007～009 | T001、T014～T016、T020、T022、T024 |
| FR-010～012 | T001、T002、T012、T017～T020、T024 |
| FR-013～015 | T014～T016、T019～T022、T024～T025 |
| FR-016～018 | T001～T003、T007～T009、T012～T013、T015、T018、T021～T023、T025～T028 |
| SC-001 | T004～T009、T025、T027 |
| SC-002 | T010～T013 |
| SC-003 | T014～T020、T024、T027 |
| SC-004 | T014～T016、T020、T022、T024 |
| SC-005 | T003～T010、T014～T018、T024～T025 |
| SC-006 | T010、T012～T013、T015、T018、T023、T025、T027 |
| SC-007 | T003～T009、T012、T017、T020～T021、T023、T025～T027 |
| SC-008 | T029（真实数据条件任务） |
| US1.1～4 | T004～T009 |
| US2.1～3 | T010～T013 |
| US3.1～4 | T014～T016、T020、T022、T024 |
| US4.1～4 | T017～T025 |
| D1～D6 / plan 主数据、场景、任务、求解、UI、验证决策 | T001～T029，各项见任务括注及分组 |

### 结论与确认范围

- 共 **29 项**：共享 3、US1 6、US2 4、US3 3、US4 9、收敛/客户验证 4。
- FR、SC、用户故事验收、数据/接口和研究决策均有任务覆盖，无未解释任务或规划外路径；时间边界在 spec、data-model、样例和结果任务间一致。
- 无阻塞实施的范围问题；T029 等待用户提供真实数据。未开展实际代码验证，文档一致性不代表功能通过。
- 仓库已有治理失败独立记录在 research.md，不新增清理/依赖变更任务。
- **实施确认已取得：用户回复“确认，继续执行”；已按 speckit-implement 执行。**

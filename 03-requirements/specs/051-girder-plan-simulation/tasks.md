# 任务清单：架梁计划推演

**输入**：`03-requirements/specs/051-girder-plan-simulation/` 下的 `spec.md`、`plan.md`、`research.md`、`data-model.md`、`contracts/` 和 `quickstart.md`

**实施门槛**：本清单需经用户确认后才能执行。实现必须保留现有架梁专项页面、`GirderPlanningConfig`、专项联算、综合排程快照及发布行为。

**测试策略**：算法、持久化、共享契约和跨前后端行为均先建立可失败的定向测试，再实现对应能力；最后执行性能、兼容、类型、构建和架构验证。

## 格式

- `[P]`：与相邻任务使用不同文件且没有未完成依赖，可并行。
- `[USn]`：任务追溯到对应用户故事。
- 每项任务均列出具体目标文件；未列出的现有架梁专项文件不得顺带修改。

## Phase 1：准备共享契约与固定样例

**目标**：先固定跨层字段、单位、状态和可复现输入，避免实现期间产生第二套口径。

- [x] T001 在 `04-demo/backend/tests/fixtures/girder_plan_simulation/linear-two-yard.json`、`cycle.json`、`performance.json` 建立双梁场混合梁型正常样例、循环依赖样例和 500/10/300 性能样例，显式记录自然日、片、片/天以及“当日产梁次日可用”的预期不变量。
- [x] T002 [P] 按 `contracts/girder-plan-simulation.openapi.yaml` 在 `04-demo/backend/app/contracts/girder_plan_simulation.py` 建立线路图、方案版本、梁场分梁型能力、架梁线路、运行快照、交付控制和结构化诊断 Pydantic 契约，并在 `04-demo/backend/app/contracts/__init__.py` 显式导出。
- [x] T003 [P] 在 `04-demo/frontend/src/contracts/girderPlanSimulation.ts` 建立与后端同名同枚举的 TypeScript 契约，并在 `04-demo/frontend/src/contracts/index.ts` 显式导出，不把新字段并入现有 `GirderPlanningConfig`。

**检查点**：固定样例和前后端共享字段可用于后续测试，且单位、默认值、状态和稳定标识已明确。

---

## Phase 2：建立独立版本仓储与应用边界

**目标**：建立所有故事共同依赖的独立存储、服务组合和 API 命名空间；不得接入现有专项存储或发布服务。

- [x] T004 在 `04-demo/backend/tests/test_girder_plan_simulation_repository.py` 先编写失败测试，覆盖 `.local-data/state/girder-plan-simulation-store.json` 的方案版本递增、乐观版本校验、只读快照、稳定输入指纹和临时仓储隔离。
- [x] T005 在 `04-demo/backend/app/girder_plan_simulation/repository.py` 和 `__init__.py` 实现独立 JSON 仓储、原子保存和不可变运行快照，复用 `state_path()` 与稳定指纹工具，但不调用现有 plan-control 或 girder-planning 仓储。
- [x] T006 在 `04-demo/backend/app/girder_plan_simulation/service.py` 建立服务组合根，注入现有项目主数据仓储和新仓储，并统一实现项目版本引用、输入指纹、并发冲突及领域错误到 API 错误的映射。
- [x] T007 在 `04-demo/backend/app/api/routers/girder_plan_simulation.py`、`04-demo/backend/app/api/routers/__init__.py` 和 `04-demo/backend/app/bootstrap.py` 注册独立 `/api/girder-plan-simulation` 路由边界；此时只完成依赖注入和错误壳，不改现有架梁专项路由。

**检查点**：新领域拥有独立命名、存储和生命周期，后续故事可以在该边界内实现。

---

## Phase 3：用户故事 1——建立线路图和梁场能力（P1）

**目标**：从已确认项目主数据形成可追溯线路图，并能保存、重载梁场部署位置和分梁型产能/库存。

**独立测试**：载入 `linear-two-yard.json`，选择已确认项目版本，线路图正确区分路桥隧与左右线；两个梁场的分梁型能力保存后重载一致；缺里程、断点和多义路径被对象级诊断阻断。

### 测试

- [x] T008 [P] [US1] 在 `04-demo/backend/tests/test_girder_plan_simulation_topology.py` 编写线路/里程排序、桥梁＋幅别目标聚合、唯一通路自动补齐、缺里程不默认为 0、断点和多义路径确认测试。
- [x] T009 [P] [US1] 在 `04-demo/backend/tests/test_girder_plan_simulation_api.py` 编写已确认项目版本门禁、线路图查询、方案创建、梁场分梁型数据保存重载及对象级 4xx 诊断契约测试。
- [x] T010 [P] [US1] 在 `04-demo/frontend/tests/girderPlanSimulation.test.mjs` 编写项目版本选择、线路图空态/阻断态、梁场分梁型编辑及保存重载的组件旅程测试。

### 实现

- [x] T011 [US1] 在 `04-demo/backend/app/girder_plan_simulation/topology.py` 从原始 `ProjectMasterSnapshot` 按 `alignment_code + start/end mileage + sort_order` 构建线路图，生成桥梁＋幅别梁型需求，支持方案级人工连接和唯一通路展开，并为缺失/重叠/断开/多义情况保留证据。
- [x] T012 [US1] 在 `04-demo/backend/app/girder_plan_simulation/validation.py` 实现已确认项目版本、梁场稳定标识、部署节点、投产日、分梁型片日产能、期初/最大库存和线路图就绪度校验，返回稳定诊断编码、级别、对象类型、对象标识和修正说明。
- [x] T013 [US1] 在 `04-demo/backend/app/girder_plan_simulation/service.py` 实现线路图生成/读取和方案版本创建/查询用例，保存项目版本稳定引用、拓扑引用与输入指纹。
- [x] T014 [US1] 在 `04-demo/backend/app/api/routers/girder_plan_simulation.py` 实现线路图、方案列表、方案创建和方案详情端点，并与 OpenAPI 的加载、空态、失败态及并发冲突保持一致。
- [x] T015 [P] [US1] 在 `04-demo/frontend/src/api/girderPlanSimulationApi.ts` 和 `04-demo/frontend/src/features/girderPlanSimulation/adapter.ts` 实现线路图/方案 API 客户端、后端字段适配和错误诊断适配。
- [x] T016 [P] [US1] 在 `04-demo/frontend/src/features/girderPlanSimulation/LineGraphView.tsx` 实现按线路与里程展示路基、桥梁、隧道、连接点和梁场的线性拓扑视图，以及断点、多义路径和人工连接确认入口。
- [x] T017 [P] [US1] 在 `04-demo/frontend/src/features/girderPlanSimulation/YardPlanEditor.tsx` 实现梁场部署位置、投产日期、分梁型片日产能、分梁型期初/最大库存和片日架梁能力编辑，禁止跨梁型替代和非法数值。
- [x] T018 [US1] 在 `04-demo/frontend/src/features/girderPlanSimulation/GirderPlanSimulationPanel.tsx`、`styles.css`、`index.ts`、`04-demo/frontend/src/contracts/scheduler.ts`、`04-demo/frontend/src/features/layout/WorkspaceNavigation.tsx` 和 `04-demo/frontend/src/app/Workspace.tsx` 增加独立页面入口并组合项目版本、线路图和梁场编辑；不修改 `04-demo/frontend/src/features/girderPlanning/`。

**检查点**：US1 可独立演示并通过 T008–T010；尚未校验人工顺序或生成日期。

---

## Phase 4：用户故事 2——人工顺序下生成最早可行架梁计划（P1）

**目标**：用户只排序待架桥梁幅别，系统补齐中间节点并在固定顺序、库存、能力和通行依赖下生成确定性的最早可行计划。

**独立测试**：两个梁场并行、每条线路串行；桥梁顺序不变；每日库存守恒且不为负；当日产梁次日可用；不可达、重复/漏分配、能力缺失、循环依赖和时域超限均阻断。

### 测试

- [x] T019 [P] [US2] 在 `04-demo/backend/tests/test_girder_plan_simulation_validation.py` 编写一场一线、目标唯一分配、人工顺序、路径确认、梁型能力、零架梁能力、不可达和循环依赖的阻断测试。
- [x] T020 [P] [US2] 在 `04-demo/backend/tests/test_girder_plan_simulation_simulator.py` 编写分梁型逐日生产/库存守恒、次日可用、片日架设上限、同线不并行、跨场并行、转场/换幅及最早可行日期的精确不变量测试。
- [x] T021 [P] [US2] 在 `04-demo/backend/tests/test_girder_plan_simulation_api.py` 增加校验、运行、结果查询、重复输入复算和规划时域阻断端到端测试。
- [x] T022 [P] [US2] 在 `04-demo/frontend/tests/girderPlanSimulation.test.mjs` 增加拖拽桥梁幅别顺序、中间节点只读补齐、路径歧义确认、阻断诊断定位和计算触发旅程测试。

### 实现

- [x] T023 [US2] 在 `04-demo/backend/app/girder_plan_simulation/validation.py` 完成一场一线、目标恰好一次分配、固定人工顺序、确认路径、分梁型供应、架梁能力、跨线路通行依赖图和循环链检测，任何阻断均不得进入仿真。
- [x] T024 [US2] 在 `04-demo/backend/app/girder_plan_simulation/simulator.py` 实现确定性逐日事件仿真：按片和自然日维护分梁型期初/生产/架设/期末库存，执行次日可用、单线片日能力、同线串行、跨场并行、准备/转场/换幅和通行依赖，并以固定顺序下最早完成为唯一排程目标。
- [x] T025 [US2] 在 `04-demo/backend/app/girder_plan_simulation/service.py` 实现方案就绪校验、运行编排、相同指纹结果复用、规划时域终止及只读运行快照生成。
- [x] T026 [US2] 在 `04-demo/backend/app/api/routers/girder_plan_simulation.py` 实现方案校验、创建运行和查询运行端点，返回桥梁起止日、逐日库存、展开线路、等待原因和结构化诊断。
- [x] T027 [P] [US2] 在 `04-demo/frontend/src/features/girderPlanSimulation/RouteSequenceEditor.tsx` 实现每场一线的待架桥梁幅别选择与人工排序、自动补齐中间节点只读展示及多义路径人工确认，页面不得提供自动优化顺序动作。
- [x] T028 [P] [US2] 在 `04-demo/frontend/src/features/girderPlanSimulation/SimulationResultPanel.tsx` 实现梁场甘特、桥梁日期表和分梁型库存序列的基础结果视图，明确展示梁场、线路顺序、梁型片数和控制因素。
- [x] T029 [US2] 在 `04-demo/frontend/src/features/girderPlanSimulation/GirderPlanSimulationPanel.tsx` 和 `04-demo/frontend/src/api/girderPlanSimulationApi.ts` 串联顺序保存、就绪校验、运行、复用、重试和结果加载状态，并从诊断跳转到具体梁场、线路或桥梁幅别。

**检查点**：US1+US2 构成首个推荐 MVP，能够独立生成固定人工顺序下的可解释架梁计划。

---

## Phase 5：用户故事 3——倒排工点最晚交付日期并识别风险（P1）

**目标**：把架梁结果转化为待架桥梁及沿途路桥隧工点的最晚具备架梁/通行条件日期，并与当前计划日期比较。

**独立测试**：待架桥梁按架梁开始日扣减架前缓冲；路基、隧道、便道和已架桥梁通道按首次通行日扣减各自缓冲；同一工点多线路取最早要求；无当前计划日期时显示材料不足而不虚构晚交。

### 测试

- [x] T030 [P] [US3] 在 `04-demo/backend/tests/test_girder_plan_simulation_simulator.py` 增加各工点类型缓冲倒排、共享工点多线路取最早日期、控制来源追溯、晚交天数和缺计划日期风险未知测试。
- [x] T031 [P] [US3] 在 `04-demo/backend/tests/test_girder_plan_simulation_api.py` 增加工点交付控制字段、线路明细、稳定工点关联和不写回项目主数据的契约测试。
- [x] T032 [P] [US3] 在 `04-demo/frontend/tests/girderPlanSimulation.test.mjs` 增加工点交付控制表、风险筛选、控制来源展开及从诊断/甘特定位工点的旅程测试。

### 实现

- [x] T033 [US3] 在 `04-demo/backend/app/girder_plan_simulation/simulator.py` 基于首次架梁或通行使用日期按工点类型倒排缓冲，汇总多线路最早需求并输出每条线路明细、控制来源、当前计划完成日、晚交天数和风险状态。
- [x] T034 [US3] 在 `04-demo/backend/app/girder_plan_simulation/service.py` 和 `04-demo/backend/app/api/routers/girder_plan_simulation.py` 将交付控制并入只读运行快照，保留项目版本、工点、幅别、梁型、梁场、线路和运行的稳定标识，不调用项目计划写接口。
- [x] T035 [US3] 在 `04-demo/frontend/src/features/girderPlanSimulation/SimulationResultPanel.tsx` 和 `LineGraphView.tsx` 增加工点交付控制表、线路图风险着色、来源/缓冲/线路明细和对象间联动定位；缺当前计划日期时显示“材料不足”。

**检查点**：US3 可从任一控制日期追溯到首次使用、缓冲和控制线路，且不会自动修改项目计划。

---

## Phase 6：用户故事 4——保存和确认独立策划成果（P2）

**目标**：支持方案版本、结果复用、输入失效和独立确认，同时证明现有专项与发布链路未被写入。

**独立测试**：确认一次运行后修改任一输入，旧结果转为失效；原快照仍可追溯；相同指纹可复用；现有架梁专项配置、联合快照和计划版本前后完全一致。

### 测试

- [x] T036 [P] [US4] 在 `04-demo/backend/tests/test_girder_plan_simulation_repository.py` 增加草稿/可计算/已计算/已确认/已失效/已阻断状态转换、输入变更失效、快照保留和相同指纹复用测试。
- [x] T037 [P] [US4] 在 `04-demo/backend/tests/test_girder_plan_simulation_api.py` 增加确认人/原因门禁、陈旧指纹 409、确认结果查询及现有专项配置/联合快照/计划版本零写入回归测试。
- [x] T038 [P] [US4] 在 `04-demo/frontend/tests/girderPlanSimulation.test.mjs` 增加独立成果标识、确认动作、失效提示、加载/空态/失败/重试和禁止显示为正式基线的旅程测试。

### 实现

- [x] T039 [US4] 在 `04-demo/backend/app/girder_plan_simulation/repository.py` 实现完整状态转换、项目/拓扑/梁场/库存/能力/顺序/缓冲变更失效、历史快照保留和确认审计字段。
- [x] T040 [US4] 在 `04-demo/backend/app/girder_plan_simulation/service.py` 实现结果复用、陈旧指纹防护、独立确认和失效原因计算，明确禁止写入 `GirderPlanningConfig`、专项结果、综合联算快照或计划版本。
- [x] T041 [US4] 在 `04-demo/backend/app/api/routers/girder_plan_simulation.py` 实现运行确认端点和 404/409/422 状态映射，并返回确认人、时间、原因及当前有效性。
- [x] T042 [US4] 在 `04-demo/frontend/src/features/girderPlanSimulation/GirderPlanSimulationPanel.tsx` 和 `SimulationResultPanel.tsx` 实现版本切换、结果复用提示、独立确认、失效原因、加载/空态/失败/重试，并持续显示“独立策划成果，非综合排程或执行基线”。

**检查点**：四个故事全部可独立验证；新路径已形成可追溯的独立策划成果，但仍未接入综合排程。

---

## Phase 7：跨层同步、性能与回归收敛

**目标**：验证契约镜像、性能、现有行为保护和仓库级质量门槛。

- [x] T043 [P] 在 `04-demo/tools/demo-api-mirror/api.mts` 增加与权威 FastAPI 一致的架梁计划推演端点和状态语义，并保持独立状态，不复用现有架梁专项结果对象。
- [x] T044 [P] 在 `04-demo/tools/demo-api-mirror/verify.mjs` 增加 OpenAPI/后端/前端/演示镜像字段、枚举、错误状态和日界口径一致性校验，覆盖 7 个端点及全部共享结果模型。
- [x] T045 [P] 在 `04-demo/backend/tests/test_girder_plan_simulation_performance.py` 使用 `performance.json` 连续运行三次完整校验和仿真，断言每次不超过 10 秒且结果指纹一致，不得绕过路径、库存、能力和交付控制计算。
- [x] T046 在 `04-demo/frontend/tests/featureBoundaries.test.mjs` 增加双路径边界回归：新 feature 不导入现有 `features/girderPlanning/`，现有专项不导入新领域，新确认动作不进入计划发布链路；并复核 `04-demo/backend/tests/test_girder_plan_simulation_api.py` 的零写入断言。
- [x] T047 按 `03-requirements/specs/051-girder-plan-simulation/quickstart.md` 依次运行定向 pytest、前端 Node 测试、TypeScript typecheck、Vite build 和 `npm.cmd run verify:architecture`，记录实际命令、退出码、性能耗时、结果指纹及未覆盖风险后停止。

**最终检查点**：功能需求、成功标准、OpenAPI、后端、前端和演示镜像一致；现有专项行为未变；性能与确定性达到门槛。

---

## 依赖与执行顺序

### 阶段依赖

1. Phase 1 固定契约和样例，无前置依赖。
2. Phase 2 依赖 Phase 1，并阻塞所有用户故事。
3. US1 依赖 Phase 2；US2 依赖 US1 的线路图和梁场输入；US3 依赖 US2 的运行结果；US4 依赖 US1–US3 的方案与运行快照。
4. Phase 7 依赖四个故事完成。

### 故事内部顺序

- 每个故事先完成该阶段全部测试任务，并确认测试因能力缺失而失败，再开始实现。
- 后端顺序为拓扑/校验或仿真 → 服务 → API；前端顺序为 API/适配 → 组件 → 页面组合。
- 任一阻断诊断不得以 UI 警告替代后端门禁。

### 可并行批次

- Phase 1：T002 与 T003 可并行；T001 可由测试负责人同步准备。
- US1：T008–T010 可并行；T015–T017 在 T013–T014 的契约稳定后可并行。
- US2：T019–T022 可并行；T027 与 T028 在 T024–T026 完成后可并行。
- US3：T030–T032 可并行；后端 T033–T034 与前端 T035 不并行修改共享契约。
- US4：T036–T038 可并行；实现按 T039 → T040 → T041/T042 收敛。
- Phase 7：T043–T045 使用不同文件可并行；T046 在它们完成后做边界回归，T047 最后执行。

### 推荐交付切片

- **推荐 MVP**：Phase 1–4（US1+US2），交付固定人工顺序下的独立最早可行架梁计划。
- **业务闭环**：继续完成 US3，把架梁日期转化为工点最晚交付控制。
- **可复核成果**：最后完成 US4 和 Phase 7，提供版本、失效、确认、性能和兼容证据。

---

## 需求覆盖矩阵

### 功能需求

| 需求 | 实施任务 | 主要验证证据 |
|---|---|---|
| FR-001 | T007, T018, T046 | 独立入口、命名空间和双路径边界测试 |
| FR-002 | T006, T009, T012–T014 | 已确认项目版本门禁及稳定指纹 API 测试 |
| FR-003 | T008, T011, T016 | 线路图拓扑测试和视图 |
| FR-004 | T008, T011–T012, T016 | 缺失、断点、多义路径对象级诊断 |
| FR-005 | T002–T003, T009, T017 | 分梁型产能/库存保存重载测试 |
| FR-006 | T002–T003, T017, T020 | 架梁能力与时间参数契约及仿真测试 |
| FR-007 | T019, T023–T024, T027 | 一场一线校验与跨场并行测试 |
| FR-008 | T008, T011, T022, T027 | 仅排序目标、自动补齐中间节点测试 |
| FR-009 | T019, T023 | 重复/漏分配阻断测试 |
| FR-010 | T019–T020, T023–T024, T027 | 固定顺序不变量和无自动改序 UI |
| FR-011 | T020, T024 | 自然日逐日分梁型台账测试 |
| FR-012 | T020, T024 | 库存守恒、非负和梁型隔离断言 |
| FR-013 | T020, T024 | 片日能力及同线不并行断言 |
| FR-014 | T020, T023–T025 | 生产、可用日、转场、拓扑和跨线依赖测试 |
| FR-015 | T020, T024 | 固定顺序下最早可行且风险不参与目标 |
| FR-016 | T021, T026, T028 | 桥梁结果契约和日期表/甘特视图 |
| FR-017 | T030–T035 | 工点首次使用与交付控制结果 |
| FR-018 | T030, T033 | 分工点类型缓冲倒排测试 |
| FR-019 | T030, T033–T035 | 多线路取最早并保留明细测试 |
| FR-020 | T030–T035 | 晚交天数、来源和零写回测试 |
| FR-021 | T019, T021, T023, T026, T029 | 全类阻断诊断及对象定位 |
| FR-022 | T004–T005, T036, T039 | 多版本和只读快照持久化测试 |
| FR-023 | T036–T042 | 状态转换及加载/空态/失败/重试测试 |
| FR-024 | T036, T039–T042 | 全输入变更失效测试 |
| FR-025 | T037, T040, T046 | 现有配置、联算和计划版本零写入回归 |
| FR-026 | T016, T028–T029, T032, T035 | 线路图、甘特、日期表、控制表、库存和定位旅程 |
| FR-027 | T002–T006, T031, T034, T044 | 全链路稳定标识和契约一致性校验 |

### 成功标准

| 标准 | 验证任务 | 通过证据 |
|---|---|---|
| SC-001 | T020, T021, T028 | 两场并行、同线串行、唯一起止日 |
| SC-002 | T020, T024 | 每日库存公式成立且不为负 |
| SC-003 | T020, T029 | 能力 8→4 后日期、库存和控制结果确定性变化 |
| SC-004 | T019–T020, T022–T024 | 输出顺序与人工顺序逐项一致 |
| SC-005 | T019, T021, T023, T029 | 五类阻断定位全部直接对象 |
| SC-006 | T030–T035 | 首次使用、缓冲、控制线路可追溯 |
| SC-007 | T036–T040, T046 | 输入变更立即失效且现有三类数据不变 |
| SC-008 | T010, T018, T022, T029, T032, T038, T042 | 新页面内完成全旅程 |
| SC-009 | T001, T045, T047 | 500/10/300 在 10 秒内返回终态 |
| SC-010 | T038, T042, T046 | 页面持续显示独立成果且不冒充正式基线 |

### 用户故事验收场景

| 场景 | 任务与证据 |
|---|---|
| US1-1 完整主数据形成线路图 | T008, T011, T016 |
| US1-2 缺里程或无法连接时阻断 | T008, T011–T012, T016 |
| US1-3 分梁型能力和库存独立保存 | T009, T012–T014, T017 |
| US2-1 固定顺序生成最早可行起止日 | T020–T026, T027–T029 |
| US2-2 库存不足时等待后续生产且不为负 | T020, T024 |
| US2-3 重复或漏分配阻断 | T019, T023, T029 |
| US2-4 多路径要求人工确认 | T008, T011, T022–T023, T027 |
| US2-5 循环依赖返回完整依赖链 | T001, T019, T023, T026 |
| US3-1 待架桥梁按架前缓冲倒排 | T030, T033–T035 |
| US3-2 共享工点取多线路最早需求 | T030–T035 |
| US3-3 晚交显示但不修改项目计划 | T031, T034–T035, T046 |
| US4-1 相同指纹复用并显示来源 | T036, T039–T042 |
| US4-2 输入变化后旧结果失效并保留 | T036, T039–T042 |
| US4-3 确认不改变专项或发布流程 | T037, T040–T042, T046 |

### 研究与设计决策

| 决策 | 落地任务 | 验证证据 |
|---|---|---|
| D-01 两条计算路径并存 | T007, T018, T040, T046 | 独立边界与零写入回归 |
| D-02 只引用已确认项目主数据 | T006, T009, T012–T014 | 项目版本门禁测试 |
| D-03 里程相邻图＋人工连接覆盖 | T008, T011–T012, T016 | 拓扑、歧义与确认测试 |
| D-04 桥梁＋幅别目标并区分梁型 | T002–T003, T008, T011, T017 | 目标聚合和梁型隔离测试 |
| D-05 确定性逐日仿真而非 CP-SAT | T020, T024, T045 | 不变量、指纹和性能测试 |
| D-06 当日产梁次日可用 | T001, T020, T024 | 日界精确断言 |
| D-07 最晚交付日期是输出而非排程目标 | T030, T033–T035 | 先排程后倒排及来源追溯 |
| D-08 独立 JSON 版本仓储 | T004–T006, T036, T039 | 仓储隔离和快照测试 |
| D-09 独立契约/API 命名空间 | T002–T003, T007, T044 | 跨层契约校验 |
| D-10 独立前端 feature 页面 | T010, T015–T018, T046 | 单页旅程和静态边界测试 |

## 一致性结论

- 27/27 条功能需求均有实施任务和验证证据。
- 10/10 条成功标准均有可运行测试或明确性能门槛。
- 14/14 个用户故事验收场景均已映射到测试与实现任务。
- 10/10 项研究/设计决策均有落地点和回归证据。
- 未发现待澄清标记、共享字段缺口或 Constitution MUST 违反项。
- 用户已于 2026-07-20 确认全量实施；T001–T047 已按本清单完成并在 `quickstart.md` 记录验证证据。

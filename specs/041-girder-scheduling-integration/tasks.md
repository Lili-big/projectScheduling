---

description: "架梁专项与综合排程融合实施任务"
---

# 任务清单：架梁专项与综合排程融合

**输入**：来自 `specs/041-girder-scheduling-integration/` 的 `spec.md`、`plan.md`、`research.md`、`data-model.md`、`contracts/` 和 `quickstart.md`

**前置条件**：`plan.md`、`spec.md`、`research.md`、`data-model.md`、`contracts/girder-scheduling-api.yaml`

**测试要求**：本功能改变任务生成、架梁算法、库存与通道硬约束、共享字段、版本持久化、计划发布和滚动预测，所有用户故事均必须先补可复现测试，再实现代码。

**组织方式**：任务按用户故事分组。US1 建立统一项目和专项方案；US2 形成联合计算；US3 统一确认与发布；US4 接入实绩滚动；US5 完成影子验证、只读归档和正式入口关闭。

## Phase 1：准备（共享基础）

**目标**：建立架梁领域包、测试夹具和前端功能模块的最小目录，不新增第三方依赖。

- [X] T001 创建架梁领域包入口并声明公开边界：`backend/app/girder_planning/__init__.py`
- [X] T002 创建黄金样例约定文档并定义夹具命名、来源和敏感数据处理规则：`backend/tests/fixtures/girder_planning/fixture-conventions.md`
- [X] T003 [P] 创建版本化 JSON 夹具加载、指纹和断言辅助函数：`backend/tests/girder_fixture_helpers.py`
- [X] T004 [P] 创建前端架梁专项功能模块导出入口：`frontend/src/features/girderPlanning/index.ts`
- [X] T005 [P] 建立黄金样例清单，标记 `legacy_parity` 与 `confirmed_rule_change`，并登记 50 个桥梁幅别节点、300 个架梁分跨、2 个梁场、2 条启用路线和 800 个综合任务的固定性能夹具：`backend/tests/fixtures/girder_planning/fixture-manifest.json`

---

## Phase 2：基础能力（阻塞前置）

**目标**：完成全部用户故事共享的模型、版本存储、指纹、诊断和旧场景兼容基础；本阶段完成前不得开始用户故事实现。

- [X] T006 在共享模型中增加项目版本、方案版本、架梁配置、联合快照、结果状态和架梁实绩 DTO，并保持新增字段可选兼容：`backend/app/models.py`
- [X] T007 在领域内部模型中定义路线经过、唯一归属、库存日序列、通道释放、分跨计划和迭代状态：`backend/app/girder_planning/models.py`
- [X] T008 实现项目/方案/联合快照的稳定规范化与输入、归属、日期状态指纹：`backend/app/girder_planning/fingerprints.py`
- [X] T009 实现统一的 `blocked`、`infeasible`、`not_converged` 和字段定位诊断构造器：`backend/app/girder_planning/diagnostics.py`
- [X] T010 将计划管控存储升级为 `plan-control/v2` 并兼容读取 v1、新集合默认值和原子写入：`backend/app/services/plan_control_repository.py`
- [X] T011 [P] 增加 v1 读取、v2 写入、并发版本冲突和旧计划可空字段回归测试：`backend/tests/test_plan_control_repository.py`
- [X] T012 [P] 增加架梁 DTO 校验、序列化、状态枚举和指纹稳定性测试：`backend/tests/test_girder_models.py`
- [X] T013 [P] 同步新增共享类型、可选字段、结果状态和实绩结构：`frontend/src/types/scheduler.ts`
- [X] T014 [P] 为项目版本、方案版本、专项校验、联合计算和扩展实绩定义 API 客户端函数：`frontend/src/api/schedulerApi.ts`
- [X] T015 增加未启用 `girder_planning` 时任务图、求解结果和计划管控行为不变的回归测试：`backend/tests/test_scheduler.py`

**检查点**：v1 数据可读、旧场景可解、新 DTO 可序列化，所有后续故事可依赖稳定的版本和诊断基础。

---

## Phase 3：用户故事 1 - 建立统一架梁专项方案（优先级：P1）

**目标**：导入并合并结构与架梁工点数据，保存项目/方案版本，配置梁场、设备和路线，得到明确的专项就绪状态。

**独立测试**：导入包含两类来源、字段冲突、两个梁场、多条路线和共享桥梁的数据；验证来源追踪、冲突阻断、漏分配阻断、多路线经过允许、版本隔离和专项草稿/确认状态。

### 用户故事 1 的测试

- [X] T016 [P] [US1] 为旧工点 Excel 解析、桥梁幅别稳定 ID 映射、`both` 展开、三类数据权威矩阵、来源证据、稳定通行条件引用和粗粒度模式增加测试：`backend/tests/test_girder_import.py`
- [X] T017 [P] [US1] 为桥梁覆盖、每梁场一条启用线、路线节点、资源引用和缓冲确认增加就绪度测试：`backend/tests/test_girder_readiness.py`
- [X] T018 [P] [US1] 为项目版本、方案版本的创建、列表、不可变更新、项目数据确认门禁和专项确认冲突增加仓储测试：`backend/tests/test_girder_version_repository.py`
- [X] T019 [P] [US1] 为导入、版本创建、项目数据确认和专项校验接口的 200/201/409/422 契约增加测试：`backend/tests/test_girder_planning_api.py`
- [X] T020 [P] [US1] 为前端导入映射、草稿失效、冲突确认和路线配置状态转换增加 Node 测试：`frontend/tests/girderPlanningWorkflow.test.mjs`

### 用户故事 1 的实现

- [X] T021 [US1] 实现旧工点输入规范化、桥梁/幅别/里程候选匹配、`both` 展开、三类数据权威矩阵、稳定通行条件引用、来源证据和冲突预览：`backend/app/girder_planning/import_service.py`
- [X] T022 [US1] 实现项目与方案级完整性校验、桥梁覆盖校验、路线/梁场/设备引用校验和发布前缓冲确认校验：`backend/app/girder_planning/validation.py`
- [X] T023 [US1] 在仓储中实现项目版本、方案版本的创建、查询、递增版本号、指纹冲突、无阻断冲突时的项目数据确认和专项确认：`backend/app/services/plan_control_repository.py`
- [X] T024 [US1] 实现项目版本创建/查询/确认、方案版本、工点导入和专项校验 API 入口：`backend/app/main.py`
- [X] T025 [P] [US1] 实现前端统一模型与页面编辑状态之间的纯函数适配、指纹和失效判断：`frontend/src/features/girderPlanning/adapter.ts`
- [X] T026 [P] [US1] 实现梁场、产能、库存和架桥机配置组件及字段级校验提示：`frontend/src/features/girderPlanning/YardMachineEditor.tsx`
- [X] T027 [P] [US1] 实现固定路线节点编辑、共享桥梁经过、人工通道调整和同梁场启用线限制：`frontend/src/features/girderPlanning/RouteEditor.tsx`
- [X] T028 [P] [US1] 实现映射冲突、阻断、警告、来源证据和修复建议展示：`frontend/src/features/girderPlanning/GirderDiagnostics.tsx`
- [X] T029 [US1] 组合专项导入、项目数据确认、配置、校验和专业确认状态：`frontend/src/features/girderPlanning/GirderPlanningPanel.tsx`
- [X] T030 [US1] 将“架梁专项策划”接入主应用导航、场景状态和输入变化失效链路：`frontend/src/app/App.tsx`
- [X] T031 [US1] 执行并修复 US1 目标测试与前端构建，记录结果到：`specs/041-girder-scheduling-integration/quickstart.md`

**检查点**：用户能够在一个项目内形成可追溯、可校验、可独立保存的架梁专项方案；此时尚不能发布执行计划。

---

## Phase 4：用户故事 2 - 生成架梁与综合施工统一计划（优先级：P1）

**目标**：完成产存运架、唯一归属、通道释放、分跨任务适配、CP-SAT 联合求解和收敛判断，返回一份统一且可解释的计算快照。

**独立测试**：使用多梁场、多路线、共享桥梁、同日归属冲突、通道等待、库存不足、结构未就绪、状态循环和硬约束无解夹具，验证四类终态与完整迭代证据。

### 用户故事 2 的测试

- [X] T032 [P] [US2] 为逐日产量、期初库存、梁型隔离、库存容量、短缺等待和库存非负增加测试：`backend/tests/test_girder_supply.py`
- [X] T033 [P] [US2] 为固定路线推进、转场、最早到达唯一归属、同日歧义和人工归属增加测试：`backend/tests/test_girder_routes.py`
- [X] T034 [P] [US2] 为架后缓冲、明确开放日、关联任务完成日取最大值和跨路线等待增加测试：`backend/tests/test_girder_passage.py`
- [X] T035 [P] [US2] 为桥梁幅别到分跨任务、下构前置、资源绑定、梁片工程量和倒排软控制适配增加测试：`backend/tests/test_girder_schedule_adapter.py`
- [X] T036 [P] [US2] 为收敛、指纹循环、迭代上限、求解无解和数据阻断增加联合编排测试：`backend/tests/test_integrated_schedule.py`
- [X] T037 [P] [US2] 为专项预览、联合计算创建/复用/查询接口和状态响应增加 API 契约测试：`backend/tests/test_integrated_schedule_api.py`

### 用户故事 2 的实现

- [X] T038 [P] [US2] 实现按梁场、梁型、日历和实绩基准生成生产与库存日序列：`backend/app/girder_planning/supply_simulator.py`
- [X] T039 [P] [US2] 实现固定节点顺序、设备可用、转场、换幅和通道控制下的路线推进：`backend/app/girder_planning/route_simulator.py`
- [X] T040 [US2] 实现全局唯一架梁归属、最早实际到达判定、同日依赖判序和人工覆盖：`backend/app/girder_planning/ownership.py`
- [X] T041 [P] [US2] 将稳定 `PassageConditionRef` 解析为当前方案任务 ID，并实现通行释放日期、控制来源、未解析阻断和跨路线硬依赖计算：`backend/app/girder_planning/passage_service.py`
- [X] T042 [P] [US2] 实现下构、路基、隧道和通道建议最迟日期与风险诊断：`backend/app/girder_planning/backward_scheduler.py`
- [X] T043 [US2] 将唯一归属结果转换为稳定 ID 的分跨 `beam_erection` 任务、资源需求、时间窗和前后置：`backend/app/services/girder_schedule_adapter.py`
- [X] T044 [US2] 用专项适配结果替换启用架梁场景中的简支梁跳过逻辑，并保留未启用专项的兼容分支：`backend/app/scenario.py`
- [X] T045 [US2] 实现最多 10 轮的专项模拟、任务重建、综合求解、日期反馈、精确收敛和循环检测：`backend/app/services/integrated_schedule.py`
- [X] T046 [US2] 在仓储中保存只读联合计算快照、按输入指纹复用结果并在输入变化时标记失效：`backend/app/services/plan_control_repository.py`
- [X] T047 [US2] 实现专项预览、联合计算创建与查询 API，并统一映射 `converged/not_converged/infeasible/blocked`：`backend/app/main.py`
- [X] T048 [P] [US2] 实现路线运行、库存、架梁归属、分跨日期、通道等待、倒排和迭代诊断结果面板：`frontend/src/features/girderPlanning/GirderResultPanel.tsx`
- [X] T049 [US2] 接入专项预览，并将联合求解替换为架梁启用场景的正式求解入口，同时保持旧求解模式兼容：`frontend/src/app/App.tsx`
- [X] T050 [US2] 执行并修复 US2 目标测试、旧求解回归和前端构建，记录结果到：`specs/041-girder-scheduling-integration/quickstart.md`

**检查点**：用户可获得已收敛统一计划或明确的未收敛、无解、数据阻断结果；US1＋US2 构成最小可演示融合 MVP。

---

## Phase 5：用户故事 3 - 比较、确认并发布统一计划（优先级：P1）

**目标**：支持专项确认、方案隔离与比较，只允许已确认且收敛的联合快照原子发布为唯一执行基线。

**独立测试**：构造专项未确认、结果未收敛、结果失效、全部通过和输入随后变化五类场景，验证发布门禁、版本引用、原子快照、旧结果失效和方案间不串数据。

### 用户故事 3 的测试

- [ ] T051 [P] [US3] 为专项确认指纹、收敛状态、结果失效和统一基线发布门禁增加测试：`backend/tests/test_integrated_plan_publish.py`
- [ ] T052 [P] [US3] 为多方案共享项目版本、配置隔离、结果比较和输入变化失效增加仓储测试：`backend/tests/test_girder_version_repository.py`
- [ ] T053 [P] [US3] 为前端专项确认、比较、发布禁用原因和输入变更失效增加 Node 测试：`frontend/tests/girderPlanPublish.test.mjs`

### 用户故事 3 的实现

- [X] T054 [US3] 扩展基线创建逻辑，校验专项确认、联合快照状态/指纹并原子冻结架梁与综合结果：`backend/app/services/progress_forecast.py`
- [X] T055 [US3] 实现方案版本与联合快照失效传播、当前版本选择和多方案查询：`backend/app/services/plan_control_repository.py`
- [X] T056 [US3] 完成专项确认和扩展统一基线发布接口的 409/422 错误映射：`backend/app/main.py`
- [ ] T057 [US3] 在方案比较中展示架梁完工、等待、库存峰值、关键通道、综合工期和结果状态：`frontend/src/app/App.tsx`
- [X] T058 [US3] 在专项面板中增加专业确认、发布前检查点、失效提示和统一发布跳转：`frontend/src/features/girderPlanning/GirderPlanningPanel.tsx`
- [X] T059 [US3] 扩展计划管控面板展示项目/方案/联合快照引用及不可发布原因：`frontend/src/features/planControl/PlanControlPanel.tsx`
- [ ] T060 [US3] 执行并修复 US3 发布、版本、比较测试和前端构建，记录结果到：`specs/041-girder-scheduling-integration/quickstart.md`

**检查点**：系统只存在一套可发布执行计划，任何架梁或综合输入变化都会使旧联合结果失效。

---

## Phase 6：用户故事 4 - 基于架梁实绩滚动重排（优先级：P1）

**目标**：采集梁场、架梁、设备和通道实绩，执行物料平衡，锁定历史事实并联合重排剩余工作。

**独立测试**：对已发布计划保存有效实绩、计划偏差、负库存、重复实际架梁和带原因修订，验证事实优先、矛盾阻断、旧预测失效和剩余计划更新。

### 用户故事 4 的测试

- [X] T061 [P] [US4] 为期初库存、累计生产、修订量、实际消耗和当前库存恒等式增加测试：`backend/tests/test_girder_material_balance.py`
- [ ] T062 [P] [US4] 为已完成事实锁定、实际归属覆盖、剩余库存基准和联合滚动计算增加测试：`backend/tests/test_girder_progress_forecast.py`
- [X] T063 [P] [US4] 为同状态日期修订、并发版本冲突、旧预测/联合快照失效增加仓储测试：`backend/tests/test_plan_control_repository.py`
- [ ] T064 [P] [US4] 为前端实绩草稿、物料平衡提示、修订原因和重排解锁增加 Node 测试：`frontend/tests/girderProgressWorkflow.test.mjs`

### 用户故事 4 的实现

- [ ] T065 [US4] 实现架梁实绩规范化、物料恒等式、重复架梁和实际日期校验：`backend/app/services/girder_progress.py`
- [X] T066 [P] [US4] 实现架梁实绩 Excel 解析与字段级错误报告：`backend/app/girder_planning/progress_import_service.py`
- [X] T067 [US4] 扩展进度快照保存、修订记录和联合快照失效传播：`backend/app/services/plan_control_repository.py`
- [X] T068 [US4] 将梁场库存、已架分跨、设备位置和通道事实纳入剩余任务构造与联合预测：`backend/app/services/progress_forecast.py`
- [X] T069 [US4] 扩展实绩保存、Excel 导入和滚动联合计算接口及错误响应：`backend/app/main.py`
- [X] T070 [P] [US4] 实现梁场库存、已架分跨、设备位置、通道状态和修订原因编辑区：`frontend/src/features/girderPlanning/GirderProgressEditor.tsx`
- [X] T071 [US4] 将架梁实绩编辑、保存状态、物料平衡和滚动重排接入现有三步计划管控闭环：`frontend/src/features/planControl/PlanControlPanel.tsx`
- [ ] T072 [US4] 执行并修复 US4 物料、修订、预测测试和前端构建，记录结果到：`specs/041-girder-scheduling-integration/quickstart.md`

**检查点**：已发生事实不会被改写，物理矛盾不会生成未来计划，状态日之后的架梁和综合任务能够统一重排。

---

## Phase 7：用户故事 5 - 完成旧系统影子验证与归档（优先级：P2）

**目标**：用旧输入、黄金样例和真实项目验证迁移差异；门禁通过并取得外部仓库操作授权后，完成旧系统只读归档和正式入口关闭。

**独立测试**：运行全部 `legacy_parity` 与 `confirmed_rule_change` 夹具，并对一个脱敏真实项目记录输入规模、差异、性能、业务确认和是否满足归档门槛。

### 用户故事 5 的测试与验证

- [ ] T073 [P] [US5] 将旧系统单梁场、多梁场、库存、路线、通道和倒排输入转为稳定 JSON 黄金夹具：`backend/tests/fixtures/girder_planning/`
- [ ] T074 [P] [US5] 增加旧规则一致性和确认变更规则差异测试，禁止未登记差异通过：`backend/tests/test_girder_legacy_parity.py`
- [ ] T075 [P] [US5] 增加共享桥梁、同日冲突、架后通行和粗粒度兼容的确认新规则夹具：`backend/tests/fixtures/girder_planning/fixture-manifest.json`

### 用户故事 5 的实现与切换

- [ ] T076 [US5] 在导入结果中增加旧字段到统一字段映射报告、缺失字段和重新计算提示：`backend/app/girder_planning/import_service.py`
- [ ] T077 [US5] 建立真实项目影子验证记录模板并填写自动测试、性能和待业务确认项：`specs/041-girder-scheduling-integration/shadow-validation.md`
- [ ] T078 [US5] 执行脱敏真实项目联算并记录新旧差异、规则归因、业务确认人与归档结论：`specs/041-girder-scheduling-integration/shadow-validation.md`
- [ ] T079 [US5] 在影子验证门禁通过并取得外部仓库操作授权后，将旧项目运行入口改为只读归档提示、关闭正式创建入口，并把归档状态和入口关闭证据回填影子验证记录：`D:/codex_workspace/架梁倒排/index.html`、`D:/codex_workspace/架梁倒排/package.json`、`specs/041-girder-scheduling-integration/shadow-validation.md`

**检查点**：黄金样例全部通过且至少一个真实项目获得业务确认后，取得外部仓库操作授权并完成只读归档和正式入口关闭；未获得授权时，T079 保持未完成且不得宣称融合项目已完成下线切换。

---

## Phase 8：收尾与横切事项

**目标**：完成性能、全量回归、代码清理、文档交底和 Spec Kit 实现前后门禁验证。

- [X] T080 [P] 增加联合计算轮次、循环检测，以及 50 个桥梁幅别节点、300 个架梁分跨、2 个梁场、2 条启用路线、800 个综合任务在 10 分钟内返回明确终态的性能回归测试：`backend/tests/test_girder_performance.py`
- [X] T081 [P] 更新当前算法交底，明确架梁硬约束、软控制、四类终态和联合迭代：`docs/排程算法当前实现交底文档_v1.2.md`
- [X] T082 [P] 更新系统整体说明中的统一项目、架梁专项、版本、发布和实绩闭环：`docs/项目排程系统整体说明_v1.1.md`
- [ ] T083 清理已迁移的前端重复计算入口，确保正式结果只来自后端 API：`frontend/src/features/girderPlanning/`
- [X] T084 复核 OpenAPI 契约与后端/前端共享字段、状态码和可空兼容一致：`specs/041-girder-scheduling-integration/contracts/girder-scheduling-api.yaml`
- [X] T085 运行全部后端测试并修复回归，记录命令和结果：`specs/041-girder-scheduling-integration/quickstart.md`
- [X] T086 运行前端 Node 测试、TypeScript 构建和页面手工旅程验证，记录结果：`specs/041-girder-scheduling-integration/quickstart.md`
- [X] T087 执行 `git diff --check`、敏感文件检查和生成物检查，记录未覆盖风险：`specs/041-girder-scheduling-integration/quickstart.md`
- [ ] T088 对照 `spec.md`、`plan.md`、`tasks.md` 和 Constitution 完成实现后收敛审计：`specs/041-girder-scheduling-integration/tasks.md`

---

## 依赖与执行顺序

### 阶段依赖

- **Phase 1 准备**：无依赖，可立即开始。
- **Phase 2 基础能力**：依赖 Phase 1，阻塞全部用户故事。
- **US1（Phase 3）**：依赖 Phase 2，先建立可保存、可校验的统一专项方案。
- **US2（Phase 4）**：依赖 US1 的有效项目与方案版本；完成后形成最小可演示融合 MVP。
- **US3（Phase 5）**：依赖 US2 的联合快照，完成唯一计划发布。
- **US4（Phase 6）**：依赖 US3 的已发布计划，完成实绩滚动闭环。
- **US5（Phase 7）**：黄金夹具工作可在 US2 后开始，最终只读归档和正式入口关闭依赖 US1～US4、真实项目验证和外部仓库操作授权全部完成。
- **Phase 8 收尾**：依赖目标用户故事完成；T088 必须最后执行。

### 用户故事依赖图

```text
Phase 1 -> Phase 2 -> US1 -> US2 -> US3 -> US4 -> Phase 8
                              \                 /
                               ------ US5 ------
```

### 单个故事内部顺序

- 测试任务先创建并确认在缺少实现时失败或覆盖缺口。
- 共享模型和领域模型先于服务。
- 确定性领域服务先于任务适配器。
- 任务适配器先于联合编排。
- 服务先于 API 和页面接入。
- 每个故事的检查点验证通过后再进入下一故事。

### 并行机会

- Phase 1 的后端夹具辅助与前端模块入口可并行。
- Phase 2 的仓储测试、DTO 测试、前端类型/API 客户端可在共享模型落定后并行。
- US1 的导入、就绪度、仓储、API 和前端状态测试可并行；三个前端编辑/诊断组件可并行。
- US2 的供梁、路线、通道、适配器和编排测试可并行；供梁、路线、通道、倒排实现可在模型稳定后并行。
- US3 的发布、版本和前端测试可并行。
- US4 的物料、滚动、仓储和前端测试可并行；Excel 导入与页面编辑可并行。
- US5 的旧规则夹具、新规则夹具和差异测试可并行。

## 并行示例

### US1

```text
T016 旧工点导入测试
T017 专项就绪度测试
T018 版本仓储测试
T020 前端状态测试
```

### US2

```text
T032 供梁库存测试      -> T038 supply_simulator.py
T033 路线归属测试      -> T039 route_simulator.py、T040 ownership.py
T034 通道释放测试      -> T041 passage_service.py
T035 任务适配测试      -> T043 girder_schedule_adapter.py
```

### US4

```text
T061 物料平衡测试      -> T065 girder_progress.py
T062 滚动联算测试      -> T068 progress_forecast.py
T064 前端实绩状态测试  -> T070 GirderProgressEditor.tsx
```

---

## 实施策略

### 最小可演示 MVP（US1＋US2）

1. 完成 Phase 1 和 Phase 2。
2. 完成 US1，验证统一导入、配置、版本和专项就绪度。
3. 完成 US2，验证分跨任务、唯一归属、库存、通道和联合收敛。
4. 停下运行黄金样例和旧非架梁回归，演示统一计算结果。

US1 单独完成只能证明数据融合，不能证明两个项目的核心联合价值，因此不作为完整 MVP。

### 业务闭环增量

1. MVP 通过后完成 US3，形成唯一发布基线。
2. 完成 US4，接入实绩和滚动重排。
3. 完成 US5，执行真实项目影子验证，并在取得外部仓库操作授权后完成旧系统只读归档和正式入口关闭。
4. 完成 Phase 8 全量回归和收敛审计。

### 实施门禁

- 本 `tasks.md` 和后续 `$speckit-analyze` 结果必须由用户确认后，才能运行 `$speckit-implement`。
- 实施中任何新业务口径冲突必须回写 `spec.md` 并重新分析，不能通过代码默认值绕过。
- 算法与共享字段改动必须同步后端模型、前端类型、接口契约、测试和失效逻辑。
- 外部旧仓库的只读归档属于影子验收后的受控操作；实施 T079 前必须取得外部仓库操作授权，完成后必须保留归档和入口关闭证据。

## 备注

- `[P]` 仅用于不同文件或可独立准备的任务；同一共享文件的任务按阶段顺序执行。
- 所有任务均包含具体文件路径，实施时不得扩大到无关重构。
- 不修改 `README.md`，不提交、不推送、不部署，除非用户另行明确要求。

## Phase 9：收敛补充

- [X] T089 根据 FR-007、T044 补齐简支梁任务生成边界：让统一任务生成入口在启用架梁专项时只生成一次分跨 `beam_erection` 任务，并补齐未启用专项的兼容回归：`backend/app/scenario.py`、`backend/app/services/girder_schedule_adapter.py`、`backend/tests/test_girder_schedule_adapter.py`（partial）
- [ ] T090 根据 FR-024～027、FR-034 和 T051～T060 完成方案比较、统一基线发布、发布引用展示和失效跳转闭环：`backend/app/services/progress_forecast.py`、`backend/app/main.py`、`frontend/src/features/girderPlanning/GirderPlanningPanel.tsx`、`frontend/src/features/planControl/PlanControlPanel.tsx`、`frontend/tests/girderPlanPublish.test.mjs`（partial）
- [ ] T091 根据 FR-028～033 和 T061～T072 完成架梁实绩 Excel 导入、状态日后剩余任务联合重排、事实优先校验和前端编辑闭环：`backend/app/girder_planning/progress_import_service.py`、`backend/app/services/girder_progress.py`、`backend/app/services/progress_forecast.py`、`frontend/src/features/girderPlanning/GirderProgressEditor.tsx`、`frontend/tests/girderProgressWorkflow.test.mjs`（partial）
- [ ] T092 根据 FR-035～036、SC-007～008 和 T073～T079 建立黄金样例新旧对照、脱敏真实项目影子验证记录，并在取得授权后完成旧项目只读归档与正式入口关闭：`backend/tests/test_girder_legacy_parity.py`、`specs/041-girder-scheduling-integration/shadow-validation.md`、`D:/codex_workspace/架梁倒排/index.html`、`D:/codex_workspace/架梁倒排/package.json`（missing）
- [X] T093 根据 SC-003 和 T080 生成不少于 50 个桥梁幅别节点、300 个分跨、2 个梁场、2 条启用路线、800 个综合任务的固定性能夹具，并验证 10 分钟内返回明确终态：`backend/tests/fixtures/girder_planning/performance-benchmark-v1.json`、`backend/tests/test_girder_performance.py`
- [X] T094 根据 FR-018～023、FR-029～032 和 T081～T082 更新算法交底、系统整体说明和结果状态解释，确保硬约束、软控制、事实优先和四类终态与实现一致：`docs/排程算法当前实现交底文档_v1.2.md`、`docs/项目排程系统整体说明_v1.1.md`
- [X] T095 根据 F6 补齐供梁、路线、通行、适配和联合循环的独立领域回归测试，并将异常样例接入黄金夹具清单：`backend/tests/test_girder_supply.py`、`backend/tests/test_girder_routes.py`、`backend/tests/test_girder_passage.py`、`backend/tests/test_integrated_schedule.py`、`backend/tests/fixtures/girder_planning/fixture-manifest.json`（missing）

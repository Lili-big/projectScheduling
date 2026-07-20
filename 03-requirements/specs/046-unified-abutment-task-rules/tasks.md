# 任务清单：统一桥台任务生成、工期、资源与权威显示规则

**输入**：`03-requirements/specs/046-unified-abutment-task-rules/` 下的 `spec.md`、`plan.md`、`research.md`、`data-model.md`、`contracts/abutment-task-contract.md` 与 `quickstart.md`

**状态**：已完成（`completed`，40/40；T001～T040 全部完成）

**测试要求**：本功能影响项目主数据投影、任务生成、工期、资源模型、求解、派生结果当前性和前端异步显示契约。所有故事均先补失败/缺失测试，再实施；禁止以桥台名称、ID、特殊字符串、10/15 特殊值或原始 ID 显示兜底修正结果。

## 格式说明

- `[P]`：可与同阶段其他 `[P]` 任务并行，前提是修改文件不冲突。
- `[US1]`～`[US4]`：追溯到 `spec.md` 的对应用户故事。
- 每个任务描述中的 `(D01)`、`(D02)`、`(D06)`、`(D05)` 表示主责 Demo 角色，不改变 G00 的跨角色协调权。

## Phase 1：准备固定样例与测试基线

**目标**：建立贯穿映射、工期、资源、历史兼容和工作台验收的确定性输入，避免不同角色各造一套桥台测试数据。

- [X] T001 (D06) 新增固定项目主数据样例 `04-demo/backend/tests/fixtures/project_master/abutment-projection-baseline.json`，同时包含历史 `bridge_abutment + cap_beam` 非桩构件、桥台 `pile`、仅含桩基的桥台、桥墩 `cap_beam` 和两个可并行桥台主体，并为每个源构件提供稳定 ID、数量、单位、启用状态和来源参数
- [X] T002 (D06) 扩展 `04-demo/backend/tests/project_master_fixture_helpers.py` 以统一加载、深拷贝和构造 T001 样例的 confirmed 版本摘要，保证 D01、D02、D06 测试复用同一输入且重复投影不污染夹具

**检查点**：固定样例可被项目主数据适配器和任务生成测试独立加载。

---

## Phase 2：共享类型与默认配置基础

**目标**：先建立所有故事共同依赖的合法类型、开放元数据和“不新增桥台资源池”的配置边界；本阶段完成前不得开始故事实现。

### 共享契约测试（先写测试）

- [X] T003 [P] (D06) 在 `04-demo/backend/tests/test_contracts_project_master.py` 增加契约测试，证明项目主数据同时合法支持 `abutment_body` 与 `cap_beam`，且类型校验不依赖结构物名称、构件名称或 ID
- [X] T004 [P] (D06) 在 `04-demo/backend/tests/test_contracts_scheduling.py` 增加契约测试，证明 `ResourcePool(resource_mode="UNLIMITED", quantity=null, max_quantity=null)` 合法，并且 `GeneratedScheduleInput.source_summary` 可兼容投影版本开放元数据

### 共享基础实现

- [X] T005 (D01) 在 `04-demo/backend/app/project_master/definitions.py` 的项目主数据构件类型定义中增加 `abutment_body`（显示名“桥台”、允许“个”等现有合法单位），同时保留 `cap_beam`，使工作簿校验和导入模型共享同一类型源
- [X] T006 [P] (D02) 在 `04-demo/backend/app/scenario_data.py` 的 `default_resource_pools()` 验证并保持不新增 `pool-abutment / abutment_team` 默认池，使桥台继续通过资源池缺失的通用默认充足语义处理
- [X] T007 [P] (D02) 在 `04-demo/backend/app/default_scenario_config.json` 验证并保持部署默认不新增桥台资源池，同时不复制或改写现有 `abutment_body_standard` 工艺定义

**检查点**：规范类型、资源模型和开放元数据能通过共享契约校验；默认场景与部署配置中不存在桥台资源池。

---

## Phase 3：用户故事 1——从项目主数据生成规范桥台任务（优先级：P1）

**目标**：`bridge_abutment` 下启用且工程量有效的非桩构件统一投影为 `abutment_body`，桥台桩基和桥墩盖梁保持原规则；只有桩基的桥台不补造主体。

**独立测试**：对 T001 样例调用项目主数据适配器；断言父结构类型驱动映射、来源字段完整、桥台桩基不变、仅桩基桥台无主体、桥墩盖梁不变。

**覆盖**：FR-001～FR-005、FR-008、FR-016、FR-018；SC-001、SC-002 的桥墩盖梁回归部分。

### 用户故事 1 的测试（先写测试并确认旧实现失败或缺少断言）

- [X] T008 [P] [US1] (D01) 在 `04-demo/backend/tests/test_project_master_adapter.py` 增加 T001 样例测试：历史桥台非桩 `cap_beam` 变为 `abutment_body`，桥台 `pile` 与桥墩 `cap_beam` 不变，只有桩基的桥台不补造 `abutment_body`，且源 component/structure ID、数量、单位、启用状态和参数均保持
- [X] T009 [P] [US1] (D01) 在 `04-demo/backend/tests/test_project_master_workbook.py` 增加工作簿类型验证与往返测试，证明新数据可直接写入 `abutment_body`、`cap_beam` 仍合法，空 ID、无效数量和禁用构件继续走通用校验/跳过路径

### 用户故事 1 的实现

- [X] T010 [US1] (D01) 在 `04-demo/backend/app/project_master/scheduling_adapter.py` 的下部结构投影中以父级 `structure_type=bridge_abutment` 规范化构件：`pile` 沿用现有映射，其他有效非桩构件投影为 `abutment_body`；不得读取名称、ID、排序、参数文本或工期数值，不得凭父结构名称补造不存在的主体，并保留全部来源引用
- [X] T011 [US1] (D01) 修改 `01-customer-validation/泸古1标/validation-results/_scripts/build_lugu_project_master.mjs`，基于父结构物规范类型输出桥台非桩 `component_type=abutment_body`，同步类型验证列表且保留桥墩 `cap_beam` 与桥台 `pile`；不得再用“台帽/盖梁”等名称决定规范类型
- [X] T012 [US1] (D01) 按 `03-requirements/specs/046-unified-abutment-task-rules/quickstart.md` 场景 A、D 运行 `04-demo/backend/tests/test_project_master_adapter.py`、`04-demo/backend/tests/test_project_master_workbook.py` 和 `01-customer-validation/泸古1标/validation-results/_scripts/build_lugu_project_master.mjs`，核对桥台主体、仅桩基桥台和桥墩盖梁回归

**检查点**：用户故事 1 可独立证明规范映射正确，且没有改写或补造桥台桩基、桥台主体和桥墩盖梁。

---

## Phase 4：用户故事 2——统一工艺、15 天工期与默认充足资源（优先级：P2）

**目标**：规范 `abutment_body` 只通过现有工艺库和通用资源链路生成“桥台施工”、15 天/个、空兼容资源、无具名资源/分配/等待；缺失桥台工艺时通用报错且不回退盖梁工艺。

**独立测试**：直接用规范 `abutment_body` 且不配置 `abutment_team` 资源池生成并求解，不依赖 US1 的历史数据映射；使用两个无其他互斥约束的桥台任务验证不被资源串行化，并移除桥台默认工艺验证错误路径。

**覆盖**：FR-006～FR-013、FR-018；SC-002～SC-004。

### 用户故事 2 的测试（先写测试并确认缺少桥台专项回归）

- [X] T013 [P] [US2] (D02) 在 `04-demo/backend/tests/test_scheduler.py` 增加规范桥台生成与缺失工艺测试：正常时断言 `abutment_body_standard → 桥台施工 → fixed_days/count → 15 天/个`、数量 1 时 `duration_days=15`、`compatible_resource_types=[]`；移除 `abutment_body_standard` 时产生通用工艺缺失错误且不回退 `cap_beam_standard`，桥墩盖梁仍为盖梁施工 10 天
- [X] T014 [P] [US2] (D02) 在 `04-demo/backend/tests/scheduling/test_solver_constraints.py` 增加两个桥台主体任务的求解回归，断言 `ScheduleInput.resources` 和 `ScheduleResult.resource_allocations` 均无 `abutment_team`，资源等待为 0，且任务不因桥台资源互斥而串行
- [X] T015 [P] [US2] (D02) 在 `04-demo/backend/tests/test_local_scenario_config.py` 增加部署默认、旧本地配置子集、资源池缺失/禁用/`UNLIMITED` 的兼容测试，断言默认配置不补入桥台资源池，三种输入均通过现有通用默认充足语义处理

### 用户故事 2 的通用链路复核

- [X] T016 [US2] (D02) 使用 T013～T015 覆盖 `04-demo/backend/app/scheduling/application/_scenario.py` 现有 `_apply_required_resource_types`、`expand_resource_pools` 和求解器空兼容资源路径；若测试暴露通用缺陷，仅在该通用路径修复，禁止增加 `bridge_abutment`、`abutment_body`、名称或 10/15 特殊分支，并按 `03-requirements/specs/046-unified-abutment-task-rules/quickstart.md` 场景 B 运行目标测试

**检查点**：用户故事 2 可独立证明工期来自工艺库、缺失工艺不错误回退、资源来自标准通用语义，且不存在桥台专属绕路。

---

## Phase 5：用户故事 3——历史主数据按版本化规范重新投影（优先级：P3）

**目标**：历史 confirmed 快照保持不可变，每次生成/求解按当前规范重新投影；新派生结果携带投影版本，持久化旧派生结果由实际当前性消费者写入 `status=stale`，且后续指纹查找不得返回或复用该结果。

**独立测试**：对同一 T001 历史快照重复生成两次，并构造缺少/不匹配投影版本的持久化派生结果，核对确定性、仓储当前性和失效语义。

**覆盖**：FR-014、FR-015、FR-018；SC-005。

### 用户故事 3 的测试（先写测试并确认旧结果缺少版本闭环）

- [X] T017 [P] [US3] (D06) 在 `04-demo/backend/tests/test_project_master_adapter.py` 增加重复投影与版本元数据测试，断言源 confirmed 快照序列化结果不变、两次规范 ProjectModel 相同，且每个项目桥梁 `import_source` 携带单一稳定 `scheduling_projection_version`
- [X] T018 [P] [US3] (D06) 在 `04-demo/backend/tests/test_scheduling_routes.py` 增加历史 `project_data_version_id` 的生成/求解 API 回归，断言每次入口都重新调用当前投影、`source_summary` 同时包含源版本和投影版本，现有路径与状态码不变
- [X] T019 [P] [US3] (D06) 在 `04-demo/backend/tests/test_project_master_invalidation.py` 增加持久化派生结果当前性测试：当前版本可复用；缺少或不匹配 `scheduling_projection_version` 的项目主数据生成/求解快照必须持久化为 `status=stale`，后续指纹查找不得返回或复用该快照；非项目主数据历史结果保持兼容

### 用户故事 3 的实现

- [X] T020 [US3] (D06) 在 `04-demo/backend/app/project_master/scheduling_adapter.py` 定义唯一稳定的项目主数据排程投影版本常量，并写入 `ProjectBridge.import_source.scheduling_projection_version`；不得更新历史 `project_master_versions` 或构件行
- [X] T021 [US3] (D06) 在 `04-demo/backend/app/scheduling/application/_scenario.py` 从项目桥梁开放来源元数据汇总 `project_data_version_id` 与 `scheduling_projection_version` 到 `GeneratedScheduleInput.source_summary`，保持非项目主数据场景兼容
- [X] T022 [US3] (D04 实施、D06 契约复核，需 G00 路由) 在 `04-demo/backend/app/services/plan_control_repository.py` 的持久化派生结果读取/指纹复用路径实际比较项目主数据生成快照的 `source_summary.scheduling_projection_version` 与 T020 当前常量；缺失或不匹配时必须将该持久化快照写入 `status=stale`，并确保后续指纹查找排除所有 `stale` 快照，保留历史证据且不影响非项目主数据结果
- [X] T023 [US3] (D06) 按 `03-requirements/specs/046-unified-abutment-task-rules/quickstart.md` 场景 C 运行 `04-demo/backend/tests/test_scheduling_routes.py`、`04-demo/backend/tests/test_project_master_invalidation.py` 和 `04-demo/backend/tests/test_architecture_api_contract.py`，重复生成同一历史快照并确认结果确定、旧版本实际失效、无直接改库

**检查点**：用户故事 3 可独立证明历史来源不变、规范投影可重复、版本元数据有实际消费路径，旧派生结果不会与新规范结果混用。

---

## Phase 6：用户故事 4——工作台忠实展示后端结果与同版本权威名称（优先级：P4）

**目标**：任务工作台直接使用共享标签和后端任务字段；工点、桥梁、工区和幅别只在同一项目主数据版本的完整权威映射 ready 后展示，加载、失败、重试和版本切换均走通用路径。

**独立测试**：向任务视图输入规范桥台任务，并以可控异步请求覆盖首屏未就绪、全量成功、任一失败、失败重试、版本快速切换和旧请求晚到；断言 0 次原始 ID 冒充名称、0 次部分映射提交、0 个业务特例。

**覆盖**：FR-017～FR-019、FR-021～FR-026；SC-006～SC-011。

### 用户故事 4 的测试（先写测试并锁定行为与禁止项）

- [X] T024 [P] [US4] (D05) 新增 `04-demo/frontend/tests/taskViewPresenter.test.mjs`，验证 `abutment_body` 使用共享标签“桥台”，工艺和工期直接取后端 `process_name/duration_days`，空 `compatible_resource_types` 使用通用默认充足显示，空任务与生成错误使用通用状态
- [X] T025 [P] [US4] (D05/D06) 新增可执行行为测试 `04-demo/frontend/tests/taskViewProjectMasterDisplay.test.mjs`，使用仓库现有 `typescript` 工具链加载并直接执行生产状态协调模块，以可控 deferred 请求覆盖首屏 `loading`、全量成功原子 `ready`、任一失败 `error`、失败后重试、版本快速切换和旧请求晚到，断言不提交部分映射且旧身份响应被忽略
- [X] T026 [P] [US4] (D06) 扩展 `04-demo/frontend/tests/contractsCompatibility.test.mjs` 与 `04-demo/frontend/tests/taskView.test.mjs`，证明共享契约保留 `cap_beam`、`abutment_body`、开放 `source_summary` 和通用显示映射状态，并以静态断言禁止名称/ID/桥台类型/10/15 特殊分支及 `bridge_id/work_section_id/"-"` 可见名称兜底

### 用户故事 4 的实现

- [X] T027 [US4] (D05/D06) 新增 `04-demo/frontend/src/features/taskView/projectMasterDisplayState.ts`，实现仅由 `project_data_version_id + sorted(unique(workpoint_ids))` 驱动的通用请求身份、`loading/ready/error` 状态、整批原子提交、缓存命中、重试 generation 和过期响应忽略；模块不得解释 ID 业务含义或引用桥台类型
- [X] T028 [US4] (D05) 在 `04-demo/frontend/src/app/Workspace.tsx` 与 `04-demo/frontend/src/features/taskView/TaskViewWorkspace.tsx` 接入 T027：规范任务已到但映射未 ready 时只显示通用加载态，全部映射成功后一次性构建 rows，任一失败显示通用错误/不可用态与重试，版本切换不清空成“可显示的空映射”且不接受旧响应；同时移除 `Workspace.tsx` 中把 `task.bridge_id`、`task.work_section_id` 或 `"-"` 当作可见工点/桥梁/工区/幅别名称的兜底，内部稳定分组键仍可使用 ID
- [X] T029 [US4] (D05) 在 T028 完成后修改 `04-demo/frontend/src/features/taskView/presenter.ts`，保持名称映射只消费完整 `ProjectMasterWorkpoint` 权威字段，并确保缺少完整权威映射时返回通用不可用结果而非推导或拼接可见名称
- [X] T030 [US4] (D05/D06) 按 `03-requirements/specs/046-unified-abutment-task-rules/quickstart.md` 场景 E 运行 `04-demo/frontend/tests/taskViewProjectMasterDisplay.test.mjs`、`04-demo/frontend/tests/taskViewPresenter.test.mjs`、`04-demo/frontend/tests/taskView.test.mjs` 和前端构建，逐项核对首屏、成功、失败、重试和版本竞态

**检查点**：用户故事 4 可独立证明前端只是契约消费者，映射未就绪或失败时不会闪现原始 ID，旧版本映射不会与新任务混用。

---

## Phase 7：跨故事回归、禁硬编码验收与收尾

**目标**：由 D01、D02、D06、D05 分别提供责任证据，完成正常、异常、兼容、空态、历史和异步竞态场景的贯通验收。

- [X] T031 (D06) 按 `03-requirements/specs/046-unified-abutment-task-rules/quickstart.md` 场景 F 对 `04-demo/backend/app/project_master/`、`04-demo/backend/app/scheduling/`、`04-demo/frontend/src/app/Workspace.tsx`、`04-demo/frontend/src/features/taskView/`、`04-demo/frontend/src/features/projectMasterData/` 执行硬编码扫描并逐项分类，确认依据桥台名称、ID、特殊字符串、10/15 特殊值或原始 ID 显示兜底决定结果的业务分支数为 0
- [X] T032 (D01/D02/D06) 运行 `04-demo/backend/tests/` 全量 pytest 与 `04-demo/backend/tests/test_architecture_api_contract.py`，确认桥台桩基、桥墩盖梁、项目主数据、任务生成、缺失工艺、资源求解、历史投影及 API 契约无回归
- [X] T033 [P] (D05/D06) 运行 `04-demo/frontend/tests/` 全量测试、`04-demo/frontend/` TypeScript/Vite 构建以及根目录 `package.json` 的 `verify:architecture`，确认共享类型、任务视图、加载/错误/重试/竞态状态和架构边界无回归
- [X] T034 (D05) 使用 T001 对应的后端规范结果按 `03-requirements/specs/046-unified-abutment-task-rules/quickstart.md` 完成最终工作台显示验收，核对“桥台 / 桥台施工 / 15 天 / 默认充足或无受限资源”、同版本权威工点/桥梁/幅别、0 次原始 ID 闪现、桥台桩基和桥墩盖梁，并在本任务 T034 的实施记录中给出通过/不通过与证据路径
- [X] T035 (L03) 在全部测试和 D05 验收通过后只更新 `03-requirements/specs/046-unified-abutment-task-rules/spec.md` 的状态并引用实现/验证证据；未经用户另行明确授权不修改任何 `README.md`

### T034 实施记录（2026-07-17）

- 结论：**通过**。
- 后端权威输入：`04-demo/backend/tests/fixtures/project_master/abutment-projection-baseline.json` 经当前项目主数据投影、任务生成和求解链路执行；3 个 `abutment_body` 均为“桥台施工”、数量 1、工期 15 天、`compatible_resource_types=[]`，且同时从第 0 天开始。
- 资源边界：默认场景无 `abutment_team` 资源池，生成结果中桥台资源实例数为 0，求解结果中桥台资源分配数为 0；未新增 `pool-abutment`。
- 回归边界：桥台桩基任务数为 2 且仍为 `pile`；桥墩盖梁仍为“盖梁施工”、工期 10 天；来源摘要同时记录 `project_data_version_id=pmv-abutment-baseline` 与 `scheduling_projection_version=project-master-scheduling/v2`。
- 前端证据：`node --test tests/taskViewPresenter.test.mjs tests/taskViewProjectMasterDisplay.test.mjs tests/taskView.test.mjs` 共 13 项通过，覆盖权威名称、后端工艺/工期直显、默认充足、原子加载、失败重试、版本竞态及 0 次原始 ID/占位符可见兜底。
- 全量证据：后端 `425 passed, 3 skipped`；前端 `52 passed` 且 TypeScript/Vite 构建通过。获得用户单独授权后，已在 `03-requirements/specs/README.md` 登记 046；根级 `verify:architecture` 的代码、依赖、仓库卫生、文档链接、API 事实及治理测试全部通过，其中治理测试为 `43 passed`，T033 完成。

---

## 依赖与执行顺序

### 阶段依赖

- Phase 1 无依赖；T002 依赖 T001。
- Phase 2 依赖 Phase 1；T003、T004 先写测试，T005～T007 再实现共享基础。
- US1、US2 均依赖 Phase 2；US2 可对规范输入独立测试，不必等待历史投影完成。
- US3 依赖 US1 的规范投影实现，以验证历史数据重新投影、版本记录和持久化结果当前性。
- US4 依赖 Phase 2 的共享契约；使用模拟规范结果可独立测试，最终贯通验收依赖 US1～US3。
- Phase 7 依赖所有目标故事完成；T035 最后执行。

### 用户故事内部顺序

- US1：T008、T009 → T010、T011 → T012。
- US2：T013～T015 → T016；T006、T007 是该故事的共享配置前置。
- US3：T017～T019 → T020～T022 → T023。
- US4：T024～T026 → T027 → T028 → T029 → T030。
- 所有故事遵循“测试先写并确认旧实现失败或缺少断言 → 最小实现 → 独立验证”。

### 并行机会

- Phase 2 中 D06 的两个契约测试可并行；D01 类型定义与 D02 两份默认配置可在契约测试就绪后按文件并行。
- 基础完成后，D01 可推进 US1，D02 可用规范输入推进 US2，D05/D06 可用模拟规范响应准备 US4 测试。
- US3 的适配器、API 和持久化失效测试可按不同文件并行；US4 的 presenter、行为和契约测试可并行。
- T028 依赖 T027 并统一负责 `Workspace.tsx` 的状态接入与原始 ID 可见兜底移除；T029 依赖 T028 且只修改 `presenter.ts`，两项必须顺序执行。
- T033 可与不修改前端文件的后端回归准备并行，最终结论仍需汇总 T031～T034。

## 实施策略

### 最小闭环

1. 完成 Phase 1、Phase 2。
2. 完成 US1，先阻断错误 `cap_beam` 投影并守住仅桩基边界。
3. 完成 US2，证明工期和资源来自统一链路且缺失工艺不错误回退。
4. 完成 US3，覆盖历史数据、投影版本记录和旧结果实际失效。
5. 完成 US4 和 Phase 7，消除权威名称映射未就绪时的首屏闪错与版本竞态。

### 角色交接

| 角色 | 主责任务 | 交接证据 |
| --- | --- | --- |
| D01 | T005、T008～T012 | 固定主数据样例、适配器/工作簿测试、仅桩基边界、验证工作簿映射结果 |
| D02 | T006、T007、T013～T016 | 工艺/工期与缺失工艺断言、默认不新增桥台资源池、空资源与并行求解结果 |
| D06 | T001～T004、T017～T027、T030～T033 | 契约、投影版本实际失效、请求身份、可执行异步行为测试、硬编码扫描和跨模块回归 |
| D05 | T024、T025、T027～T030、T033、T034 | presenter/状态/页面测试、加载/错误/重试/竞态、构建和最终显示验收 |
| D04（G00 路由依赖） | T022 | 持久化计划/联合快照 `stale` 判定；D06 提供契约测试并复核 |
| L03 | T035 | 只回写本功能规格状态；不进入代码实现、不默认修改 README |

## 备注

- 本任务清单经用户确认且重新执行的 `$speckit-analyze` 无阻塞项后，才允许进入 `$speckit-implement`。
- 实施不得直接更新历史 confirmed 项目主数据快照，不得为桥台新增专属 API、资源模式、求解分支或前端兜底。
- `process_library_defaults.py` 中现有 `abutment_body_standard` 已满足 15 天/个；除非回归测试发现通用缺陷，不应复制或另建桥台工艺常量。
- 工作台异步修复必须保留当前工作区已有 D05 改动并在其基础上收敛，不得覆盖无关未提交工作。

---

## Phase 8：收敛补充——任务视图浏览器首屏回归

**触发原因**：用户在 046 完成后仍观察到任务视图首屏短暂显示原始 ID/`"-"`。当前源码、当前构建和 L03 对当前 Vite 的无网络拦截强制重载未复现生产实现遗漏，但 D05、D06 复核确认原 T025、T026、T030、T034 的 13 项前端证据只覆盖纯协调器、纯函数和源码断言，未完整覆盖 React 首次提交与真实浏览器 DOM；因此本阶段只补真实组件/运行时验证，不新增业务规则、共享字段或桥台特例。

- [X] T036 [US4] (D05) 根据 FR-026、SC-009 在 `04-demo/frontend/tests/taskViewRuntime.test.mjs` 建立可重复的真实 Chromium/Edge + 当前 Vite 运行时验证入口，并在 `04-demo/frontend/package.json` 增加独立验证命令；强制重载前安装 DOM MutationObserver，记录首次提交至 ready 的每次任务名称 DOM，断言只出现通用 loading 后一次性出现同 `project_data_version_id` 权威名称，`bridge_id`、`work_section_id`、section code 或 `"-"` 进入桥梁/工区/幅别可见单元格的次数均为 0，不得以源码正则、纯协调器测试或人工目测替代
- [X] T037 [US4] (D05) 根据 FR-024、SC-010 扩展 `04-demo/frontend/tests/taskViewRuntime.test.mjs` 的真实浏览器场景：受控令任一 workpoint 请求失败，断言页面从 loading 进入通用 error、任务名称行和部分映射提交均为 0；点击页面真实“重试”按钮并恢复全部权威响应后，只允许一次性渲染完整名称，整个序列原始 ID/`"-"` 可见次数为 0
- [X] T038 [US4] (D05) 根据 FR-025、SC-011 扩展 `04-demo/frontend/tests/taskViewRuntime.test.mjs` 的真实组件/浏览器场景：覆盖跨 `project_data_version_id` 切换、同版本规范化 workpoint ID 集合切换及旧请求晚到，记录每次 React DOM 提交并断言旧身份响应覆盖次数为 0、当前任务与映射版本一致率为 100%、部分映射和原始 ID/`"-"` 可见次数均为 0；若场景复现生产门控缺陷，只允许在 `04-demo/frontend/src/app/Workspace.tsx`、`04-demo/frontend/src/features/taskView/projectMasterDisplayState.ts` 或 `04-demo/frontend/src/features/taskView/TaskViewWorkspace.tsx` 修复通用状态门禁
- [X] T039 [US4] (D06) 根据 FR-019、FR-026、SC-007、SC-009～SC-011 独立复核并运行 `04-demo/frontend/tests/taskViewRuntime.test.mjs`、原 13 项任务视图测试、前端全量测试、typecheck、Vite build 和 `npm.cmd run verify:architecture`；确认真实浏览器场景全部通过、共享契约/API 无需变化、业务特例数为 0，并把当前 Vite 启动时间、页面强制重载转换序列和可见 DOM 证据追加到本阶段实施记录
- [X] T040 (L03) 根据 Spec Kit 状态闭环，在 T036～T039 由 D05/D06 常驻 thread 回交并全部通过后，将 `03-requirements/specs/046-unified-abutment-task-rules/spec.md` 状态恢复为 `completed` 并引用本阶段浏览器证据；在此之前不得再次用原 T034 的 Node 13 项证据单独宣称浏览器首屏验收完成，规格索引同步仍交 G00

### Phase 8 实施记录（2026-07-17）

- D05 常驻 thread `019f6a3a-60de-7db0-9308-f5df8a79ba8e` 完成 T036～T038；最终 Phase 8 改动为 `04-demo/frontend/tests/taskViewRuntime.test.mjs` 及此前已授权的 `test:task-view-runtime` 命令，未修改生产源码、后端或共享契约/API。
- D05 连续两次独立浏览器门禁 `3/3 PASS`：`.local-data/logs/20260717144659-task-view-runtime/task-view-runtime-summary.json`、`.local-data/logs/20260717144929-task-view-runtime/task-view-runtime-summary.json`；前端全量 `55/55 PASS` 中浏览器子门禁再次 `3/3 PASS`：`.local-data/logs/20260717145201-task-view-runtime/task-view-runtime-summary.json`。
- D06 常驻 thread `019f6a3c-1309-7113-8fb4-aa2c90f05346` 独立完成 T039 并判定 `PASS`：独立浏览器门禁 `.local-data/logs/20260717150317-task-view-runtime/task-view-runtime-summary.json` 为 `3/3 PASS`；全量中的第二次浏览器证据 `.local-data/logs/20260717150550-task-view-runtime/task-view-runtime-summary.json` 亦为 `3/3 PASS`；原 13 项 `13/13 PASS`、前端全量 `55/55 PASS`、typecheck、Vite build（1659 modules）与根级 `verify:architecture`（治理测试 `45/45`）全部通过。
- 浏览器验收：T036 `absent → empty → loading → ready(1586)`；T037 `loading → error(0 rows) → loading → ready(1586)`；T038 同版本与跨版本均为部分映射提交 0、旧响应覆盖 0、当前身份一致率 100%，且 `bridge_id`、`work_section_id`、section code、`"-"` 可见命中均为 0，业务特例分支数为 0。
- Node 22 未在本机取得，不阻断 T039；Netlify 发布前仍须在真实 Node 22 环境重跑浏览器门禁、前端全量、typecheck 与 build。规格索引的 40/40 同步继续由 G00 处理，本阶段未修改 README。

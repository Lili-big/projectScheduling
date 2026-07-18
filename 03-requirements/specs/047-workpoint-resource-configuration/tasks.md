---

description: "工点级资源配置实施任务清单"
---

# 任务清单：工点级资源配置

**状态**：completed（40/40）

**输入**：`spec.md`、`plan.md`、`research.md`、`data-model.md`、`contracts/resource-scope.openapi.yaml`、`quickstart.md`

**门禁**：本文件和最新 `$speckit-analyze` 结果必须先由用户明确确认；确认前不得执行任何未勾选实施任务，L03 不直接向 D 角色派发。

**测试要求**：先写定向契约/行为测试，再实现；最终由 D06 独立执行一个风险关键门禁和仓库约定全量验证。

## Phase 1：共享契约与测试基线

**目标**：先建立字段、兼容默认和跨前后端契约，避免各领域自行解释作用域。

- [x] T001 [P] (D06) 在 `04-demo/backend/tests/test_contracts_scheduling.py` 增加 `ResourceScopeMode`、`WorkpointResourceOverride`、`ResourcePool` 新字段和 `Resource` 显式作用域的契约测试；覆盖旧字段缺失默认 `PROJECT_SHARED`、显式空工点与 `null` 的差异、重复 override、负数及 `max_quantity < quantity`，并断言模型中无 `min_quantity`
- [x] T002 [P] (D06) 在 `04-demo/frontend/tests/contractsCompatibility.test.mjs` 增加与 `contracts/resource-scope.openapi.yaml` 对齐的前端类型兼容断言，覆盖共享、独享、旧配置和结构化 AI 更新，不允许可选字段被前端默认成“默认充足”
- [x] T003 (D06) 在 `04-demo/backend/app/contracts/_models.py`、相应 contracts 导出文件和 `04-demo/frontend/src/contracts/scheduler.ts` 实现 T001～T002 的共享类型；保持旧 `resource_updates`、现有端点和其他 ResourcePool 字段兼容，不新增新端点或 `min_quantity`
- [x] T004 (D06) 在 `04-demo/backend/tests/test_architecture_api_contract.py` 与 `04-demo/backend/tests/test_contracts_assistants.py` 固定现有 `/api/local-scenario-config`、`/api/generate-schedule-input`、`/api/solve-scenario`、`/api/solve-min-resources`、`/api/ai-resource-assistant/update-plan` 的增量契约和状态码，证明不创建平行 API

---

## Phase 2：用户故事 1——配置共享/独享并继承全局默认（P1）

**目标**：同一资源类型只有一个全局权威配置，工点覆盖可选，未配置工点按受限资源继承。

**独立测试**：执行 quickstart 场景 A、E、F，保存并重载两个桥梁工点的共享/独享配置。

**覆盖**：FR-001～FR-008、FR-019～FR-020、FR-023、FR-025；SC-002、SC-005、SC-009、SC-010。

### 后端标准化和兼容

- [x] T005 [P] [US1] (D02) 新增 `04-demo/backend/tests/scheduling/test_workpoint_resource_scope.py`，先写 `EffectiveResourcePool` 解析测试：共享一池、独享逐工点、未覆盖继承、字段级部分覆盖、工点去重排序、未知/旧版本工点、非桥梁工点排除、显式空获准集合和显式 `UNLIMITED`
- [x] T006 [US1] (D02) 新增 `04-demo/backend/app/scheduling/domain/resource_scope.py`（或该领域现有等价模块）实现唯一的资源池标准化/有效池解析入口；输入只读 `project_data_version_id + project.bridges + resource_pools`，输出稳定排序的 `EffectiveResourcePool` 和诊断，禁止名称/ID 格式/具体资源类型特例
- [x] T007 [P] [US1] (D06) 在 `04-demo/backend/tests/test_local_scenario_config.py` 增加 v1 旧配置、v2 标准配置、未知字段和重复保存测试，断言旧池统一迁移为项目共享且固定资源数量不变，保存后新字段完整，历史输入文件不被原地手工修改
- [x] T008 [US1] (D06) 在 `04-demo/backend/app/local_scenario_config.py` 和默认配置标准化路径实现统一兼容读取与 schema 升级；`_merge_by_id` 后必须调用同一标准化规则，不为具体项目或工点写补丁

### 前端配置页

- [x] T009 [P] [US1] (D05) 新增 `04-demo/frontend/tests/resourceWorkpointScope.test.mjs`，先写 `src/domain/resources.ts` 的共享/独享、继承、覆盖、null/空集合、稳定排序、恢复继承和旧配置迁移纯函数测试
- [x] T010 [US1] (D05) 在 `04-demo/frontend/src/domain/resources.ts` 实现与后端相同的无业务特例标准化和有效值展示辅助函数；不得用 `pool.type`、桥名或 ID 前缀决定作用域
- [x] T011 [US1] (D05) 修改 `04-demo/frontend/src/features/resources/ResourcesTab.tsx` 及该 feature 的样式/拆分组件，按资源类型展示作用域选择、全局数量、权威桥梁工点、继承/覆盖、恢复继承、加载/空态/错误/重试，并在共享模式固定显示“跨工点串行、转场时间按 0 天”
- [x] T012 [US1] (D05) 在 `04-demo/frontend/src/app/Workspace.tsx` 接入同一 `project_data_version_id` 的权威工点列表、保存返回值和语义指纹；工点或资源语义变化时清空/标记旧任务图、求解、AI 解释和方案对比，快速版本切换不得提交旧工点覆盖
- [x] T013 [US1] (D05) 扩展 `04-demo/frontend/tests/resourceWorkpointScope.test.mjs` 并按现有真实浏览器测试入口增加资源页行为场景，覆盖保存成功、失败重试、空态、版本快速切换/旧响应晚到和恢复继承；断言未配置工点显示“继承全局默认”，默认充足误判 0 次

---

## Phase 3：用户故事 2——正确生成候选并执行三类求解（P1）

**目标**：`ScenarioInput` 的配置被一次性解析为 `ScheduleInput` 显式资源作用域，求解只对合法候选应用现有互斥/容量约束。

**独立测试**：执行 quickstart 场景 A～D，贯通 `ScenarioInput → ScheduleInput → ScheduleResult`。

**覆盖**：FR-009～FR-017、FR-026～FR-030；SC-001、SC-003～SC-004、SC-008、SC-010。

- [x] T014 [P] [US2] (D02) 扩展 `04-demo/backend/tests/scheduling/test_workpoint_resource_scope.py`，先写固定资源和最大资源命名实例测试：共享按项目数量展开一次，独享按工点有效数量展开，ID 唯一稳定且测试证明候选逻辑不解析 ID
- [x] T015 [US2] (D02) 修改 `04-demo/backend/app/scheduling/application/_scenario.py` 复用 T006 有效池，替换当前按 type 单池的 `_apply_required_resource_types` 与 `expand_resource_pools` 输入；`GeneratedScheduleInput.source_summary` 写入规则版本、共享/独享池数、继承数和 `project_shared_transfer_time_days=0`
- [x] T016 [P] [US2] (D02) 在 `04-demo/backend/tests/scheduling/test_solver_constraints.py` 先写候选/互斥测试：共享 A/B 同实例不可重叠，独享 A/B 交叉候选为 0；已启用、`LIMITED`、正上限的资源缺 `bridge_id` 或工点不获准时阻断；显式停用、`UNLIMITED` 或零上限仍走既有统一默认充足 warning；无 override 必须先继承
- [x] T017 [US2] (D02) 修改 `04-demo/backend/app/scheduling/solver/engine.py` 的 `_resource_candidates_by_task`、资源覆盖校验和必要资源组元数据，只按 `type + eligible_workpoint_ids + exclusive_workpoint_id` 筛选；复用现有 `NoOverlap/AddCumulative`，不改变工艺逻辑、墩组、同结构绑定或目标函数
- [x] T018 [P] [US2] (D02) 在 `04-demo/backend/tests/scheduling/test_fixed_resource_application.py` 增加共享/独享有效池的固定资源测试，断言每个有效池严格使用 `quantity`，共享转场仅为 0 天诊断且不增加任务持续时间或前置关系
- [x] T019 [P] [US2] (D02) 在 `04-demo/backend/tests/scheduling/test_resource_search_application.py` 增加三类数量语义回归：增配建议每个有效池只搜索 `[quantity,max_quantity]`；固定工期最少资源的 lower bound 不读取 `quantity`，可返回低于当前投入；最大资源失败和 `UNKNOWN` 沿用现有状态
- [x] T020 [P] [US2] (D02) 在 `04-demo/backend/tests/scheduling/test_solver_results_diagnostics.py` 增加分配工点、作用域、当前/推荐数量和项目共享 0 天提示测试，确保诊断可追溯且不按名称/ID 推导
- [x] T021 [US2] (D02) 按 `03-requirements/specs/047-workpoint-resource-configuration/quickstart.md` 场景 A～D 运行 T005、T014、T016、T018～T020，保存机器可读样例到任务实施证据目录；断言跨工点独享候选 0、共享重叠 0、未配置默认充足误判 0、`min_quantity` 新增 0

---

## Phase 4：用户故事 3——AI、持久化与结果失效（P2）

**目标**：所有资源方案和快照保留作用域；AI 只建议既有作用域内的数量；语义变化使旧结果失效。

**独立测试**：执行 quickstart 场景 E、G，覆盖旧配置、AI 更新、稳定指纹和 stale。

**覆盖**：FR-021～FR-025、FR-029；SC-005～SC-007、SC-010。

### AI 资源助手

- [x] T022 [P] [US3] (D07) 在 `04-demo/backend/tests/test_ai_resource_scheduling_assistant.py` 和 `04-demo/backend/tests/test_contracts_assistants.py` 先写共享项目量、独享工点量、未知工点、超上限、旧 map 用于独享、作用域不可变和修改后 stale 的测试
- [x] T023 [US3] (D07) 修改 `04-demo/backend/app/services/ai_resource_scheduling_assistant.py` 与 `ai_resource_explainer.py`，让画像、LLM 上下文、fallback、校验、方案更新和结果解释保留作用域/工点；旧 `resource_updates` 只应用于共享，结构化更新应用于独享，禁止 AI 改 scope 或获准集合
- [x] T024 [US3] (D07) 修改 `04-demo/frontend/src/features/resourceAssistant/` 的计划卡、数量编辑和解释展示，按共享项目量或独享工点量呈现；采纳建议前不写回配置，采纳后触发 stale，不显示丢失作用域的旧解释为当前结果

### 计划快照与失效

- [x] T025 [P] [US3] (D04) 在 `04-demo/backend/tests/test_plan_control_repository.py`、`test_plan_control_api.py` 和必要 helper 中先写稳定指纹与失效测试：集合顺序等价指纹相同，scope/获准工点/override/数量/上限/启用/日历任一变化指纹不同，旧计划/预测/方案不得复用
- [x] T026 [US3] (D04) 在 `04-demo/backend/app/services/plan_control_repository.py`、`progress_forecast.py` 及现有指纹调用路径保留完整标准化资源字段；语义变化按现有状态机标记相关计划/预测 stale，保留历史快照且不直接改旧记录
- [x] T027 [US3] (D06) 在 `04-demo/backend/tests/test_local_scenario_config.py`、`test_architecture_storage_contract.py` 和共享序列化测试中复核本地配置、AI 方案、场景版本和计划快照均含新字段，旧快照能按默认读取，未知/旧版本工点不会被静默重绑
- [x] T028 [US3] (D07) 按 quickstart 场景 G 运行 AI 定向测试和 API 路由测试，记录共享旧格式兼容、独享结构化更新、作用域不可变、超上限拒绝及旧解释失效证据

---

## Phase 5：用户故事 4——页面与结果透明展示（P2）

**目标**：用户在配置和结果两端都能识别作用域、继承和 0 天转场限制。

**独立测试**：真实组件/浏览器覆盖共享、独享、继承、空态、错误、版本切换和求解结果。

**覆盖**：FR-018～FR-020、FR-026～FR-029；SC-002～SC-003、SC-007～SC-009。

- [x] T029 [P] [US4] (D05) 新增或扩展 `04-demo/frontend/tests/scheduleResultsPresenter.test.mjs`，先写结果 presenter 测试：共享/独享标签来自契约字段，分配工点来自权威映射，项目共享提示固定为转场 0 天；缺字段走通用不可用/兼容态，不解析资源 ID
- [x] T030 [US4] (D05) 修改 `04-demo/frontend/src/features/scheduleResults/presenter.ts`、`ScheduleResultsWorkspace.tsx` 及样式，在结果摘要和资源分配中展示作用域、工点、当前/推荐量，并在存在跨工点共享资源时明确提示“串行使用、转场时间按 0 天”
- [x] T031 [US4] (D05) 扩展现有前端真实浏览器门禁或新增 `04-demo/frontend/tests/resourceWorkpointRuntime.test.mjs`，覆盖配置加载/保存、共享/独享切换、继承、错误重试、空态、同/跨版本快速切换、结果展示；每次 DOM 提交中旧版本工点混用 0、默认充足误判 0、名称/ID 特例补值 0
- [x] T032 [US4] (D06) 扩展 `04-demo/frontend/tests/contractsCompatibility.test.mjs` 与架构兼容测试，确认页面只消费共享契约，不新增前端私有字段、`min_quantity`、桥名/工点 ID 格式/中文字符串/特殊数量判断

---

## Phase 6：跨故事回归与独立门禁

- [x] T033 [P] (D06) 对 `04-demo/backend/app/contracts/`、`scheduling/`、`services/`、`04-demo/frontend/src/contracts/`、`domain/resources.ts`、`features/resources/`、`features/resourceAssistant/`、`features/scheduleResults/` 和 `Workspace.tsx` 执行硬编码扫描并人工分类，确认按桥名、工点名、ID 格式、中文字符串、特殊数量或具体资源类型决定作用域的业务分支数为 0，新增 `min_quantity` 字段数为 0
- [x] T034 [P] (D02) 运行工点作用域、固定资源、资源搜索、求解约束和结果诊断定向 pytest，再运行 `04-demo/backend/tests/scheduling/` 全量；回交 quickstart A～D 的机器可读结果
- [x] T035 [P] (D07) 运行 AI 资源助手定向 pytest 与 assistants API/contract 测试，确认共享/独享结构化方案、上限和 stale 语义全绿
- [x] T036 [P] (D04) 运行计划管控 repository/API/forecast 定向测试，确认指纹稳定、语义变化失效及历史快照保留
- [x] T037 [P] (D05) 运行资源页/结果 presenter/真实浏览器定向测试和 typecheck，完成 quickstart F 的当前工作台可见验收；不重复执行前端全量与 build，二者统一留给 T038 的唯一全量门禁
- [x] T038 (D06) 在 T033～T037 主责证据完成后进行 R3 独立发布门禁：重跑一个最高风险的“独享 A/B + 共享串行 + 固定工期推荐低于 quantity”贯通场景，并集中执行本功能唯一一次后端全量、前端全量、typecheck、build、`npm.cmd run verify:architecture` 与 `python 00-governance/repository-tools/validate_docs.py`；确认共享契约、API、存储、业务特例 0 和 Node 22 发布基线，若环境无 Node 22 则明确阻断发布条件而不得伪报
- [x] T039 (D06) 使用 `03-requirements/specs/047-workpoint-resource-configuration/quickstart.md` 汇总正常、异常、空态、兼容、AI、版本切换和当前页面结果；逐项映射 FR-001～FR-030、SC-001～SC-010，任何遗漏追加任务并回交 G00，不由 L03中转实施进度
- [x] T040 (L03) 仅在 G00 汇总 T001～T039 主责和审查结论且全部通过后，核对证据路径并把 `03-requirements/specs/047-workpoint-resource-configuration/spec.md` 状态更新为 completed；未经用户另行授权不修改 README，不重复运行领域技术验证

## 依赖与执行顺序

### 阶段依赖

- Phase 1 是所有实现的共享前置：T001～T002 先失败，T003 实现，T004 锁定 API。
- Phase 2 后端 T005→T006→T007～T008；前端 T009→T010→T011→T012→T013，且 T010 依赖 T003。
- Phase 3：T014、T016、T018～T020 先写测试；T015 依赖 T006，T017 依赖 T003/T015；T021 最后贯通。
- Phase 4：T022→T023→T024/T028；T025→T026；T027 依赖 T003/T008/T026。
- Phase 5：T029→T030→T031；T032 可在 T030 后独立复核。
- Phase 6 依赖所有用户故事；T038 依赖 T033～T037，T039 依赖 T038，T040 最后。

### 可并行项

- 契约测试 T001/T002 可并行。
- T007、T009 可在 T006 的接口确定后并行。
- Phase 4 的 D07 与 D04 分支可并行，D05 结果展示可在共享契约稳定后并行准备。
- T034～T037 分属不同领域，可由 G00 并行派发；D06 T038 只能在其后执行。

## G00 派发分组（用户确认后使用）

| 建议主责 | 任务 | 主要依赖 | 建议审查 |
| --- | --- | --- | --- |
| D06 | T001～T004、T007～T008、T027、T032～T033、T038～T039 | 无；T038 等待各主责完成 | T038 为 R3 独立发布门禁 |
| D02 | T005～T006、T014～T021、T034 | T003 共享契约 | D06 |
| D07 | T022～T024、T028、T035 | T003、T006 | D06 |
| D04 | T025～T026、T036 | T003、T006 | D06 |
| D05 | T009～T013、T029～T031、T037 | T003、T006、T020 | D06 |
| L03 | T040 | G00 汇总 T001～T039 PASS | none |

该表只用于用户确认后的精简回交；L03 不自行向常驻 D thread 派发。

## 实施策略

### 最小闭环

1. 先完成共享契约与统一有效池解析。
2. 贯通任务生成、候选和三类求解。
3. 再接 AI、持久化、页面和结果。
4. 最后做真实浏览器、贯通样例、硬编码和全量门禁。

### 停止条件

- 发现 `Task.bridge_id` 不是当前桥梁工点权威 ID；
- 需要新增非桥梁工点、非零转场、调拨审批或跨项目共享；
- 需要新增 `min_quantity` 或改变既有目标函数；
- 现有 PRD/规则与已确认产品口径无法无损收敛；
- 连续验证失败或需要增加未登记实施角色。

发生以上情况，目标角色停止并按模板回交 G00，由 G00 请求用户决策。

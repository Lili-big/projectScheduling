---

description: "工点主导资源配置与范围共享流转实施任务清单"
---

# 任务清单：工点主导资源配置与范围共享流转

**状态**：实施完成 57/59；T057/T059 因外部 R3 门禁未关闭

**输入**：`spec.md`、`plan.md`、`research.md`、`data-model.md`、`contracts/workpoint-resource-allocation.openapi.yaml`、`quickstart.md`

**门禁**：本文件和最新 `$speckit-analyze` 结果必须由用户明确确认；确认前不得执行任何实施任务。能力编号表示当前主责 Thread 内加载的专业能力，不代表常驻 Thread 或跨 Thread 派发目标。

**测试要求**：所有契约、算法、页面、AI 和计划变更先写定向测试；各领域只运行最小定向门禁，后端全量、前端全量、typecheck、build 和架构门禁集中在 T057 仅执行一次。

## Phase 1：共享契约与测试基线

**目标**：先冻结池 ID、显式工点身份、同类型多池和逐池结果契约，阻止各领域继续按资源类型唯一定位。

- [x] T001 [P] (D06) 在 `04-demo/backend/tests/test_contracts_scheduling.py` 增加 `ResourcePool.workpoint_id`、工点本地记录、同类型多共享池、重复池 ID、非法字段组合和旧共享缺字段默认的契约测试，断言 `(workpoint_id,type)` 唯一且旧共享不拆分
- [x] T002 [P] (D06) 在 `04-demo/frontend/tests/contractsCompatibility.test.mjs` 增加与 `contracts/workpoint-resource-allocation.openapi.yaml` 对齐的前端类型断言，覆盖 `workpoint_id`、逐池数量结果和结构化数量更新
- [x] T003 (D06) 在 `04-demo/backend/app/contracts/_models.py` 及 `04-demo/backend/app/contracts/common.py`、`project.py`、`assistants.py` 导出中实现 T001 的加法式共享契约；保留 047 `workpoint_overrides` 读取，禁止 Pydantic 静默丢字段
- [x] T004 (D06) 在 `04-demo/frontend/src/contracts/scheduler.ts`、`04-demo/frontend/src/contracts/project.ts` 实现 T002 对应类型，并保持现有聚合导出兼容
- [x] T005 [P] (D06) 在 `04-demo/backend/tests/test_architecture_api_contract.py`、`test_contracts_assistants.py` 冻结现有保存、生成、三类求解和 AI 更新端点的状态码与增量 schema，证明不创建平行 API
- [x] T006 (D06) 在 `04-demo/backend/tests/fixtures/architecture/backend-baseline.json`、`04-demo/frontend/tests/fixtures/architecture/frontend-baseline.json` 更新经 T001～T005 证明的共享契约基线，不纳入未实现端点或排除项

**检查点**：共享契约可表达工点本地池、同类型多个共享池和逐池结果，旧输入仍可反序列化。

---

## Phase 2：基础标准化、迁移与资源目录

**目标**：建立所有用户故事共用的规范资源池解析；本阶段完成前不得进入页面或求解实现。

- [x] T007 [P] (D02) 在 `04-demo/backend/tests/scheduling/test_workpoint_resource_scope.py` 先写规范化测试：新工点本地池、同类型多共享池、动态全部工点、显式空范围、重复 ID/本地唯一键、未知工点及稳定排序
- [x] T008 (D02) 在 `04-demo/backend/app/scheduling/domain/resource_scope.py` 实现统一资源池标准化和有效池解析：以 `pool.id` 唯一，允许 `type` 重复，按 `workpoint_id` 解析本地池并独立保留每个共享池
- [x] T009 [P] (D06) 在 `04-demo/backend/tests/test_local_scenario_config.py` 先写旧共享池保真、047 legacy 独享无损展开、迁移阻断、同类型多池按 ID 合并和重复保存幂等测试
- [x] T010 (D06) 在 `04-demo/backend/app/local_scenario_config.py` 实现统一兼容标准化和本地 schema 升级；旧共享保持单池，legacy 独享只在无损时展开，失败时保留输入并阻断保存
- [x] T011 [P] (D02) 在 `04-demo/backend/tests/scheduling/test_workpoint_resource_scope.py` 和 `04-demo/frontend/tests/resourceWorkpointScope.test.mjs` 先写资源目录投影测试，覆盖任务可能资源、完整目录补充候选和无第二份持久化权威
- [x] T012 (D02) 在 `04-demo/backend/app/scenario_data.py`、`04-demo/frontend/src/domain/resources.ts` 实现资源目录与工点可能资源的确定性派生；复用工艺类型和标准池元数据，不按具体资源名称硬编码
- [x] T013 (D06) 在 `04-demo/backend/app/default_scenario_config.json` 和默认场景标准化路径复核/更新规范池形态，确保默认配置可重复加载且不把目录元数据误当实际投入

**检查点**：任意场景都能得到稳定的规范池、目录投影和迁移诊断，后续领域只消费该结果。

---

## Phase 3：用户故事 1——按工点维护当前资源（P1）

**目标**：计划工程师从工点入口维护本地数量、上限和状态，并从目录补充资源；页面没有反向适用工点配置。

**独立测试**：执行 quickstart 场景 A、J，保存并重载 A/B/C 工点资源，确认目录补充只影响当前工点且版本晚到不污染新状态。

**覆盖**：FR-001～FR-007、FR-031～FR-033；SC-001～SC-002、SC-009～SC-010。

- [x] T014 [P] [US1] (D05) 在 `04-demo/frontend/tests/resourceWorkpointScope.test.mjs` 先写工点一级投影、`(workpoint_id,type)` upsert、数量 0 保留、目录补充和稳定指纹纯函数测试
- [x] T015 [US1] (D05) 在 `04-demo/frontend/src/domain/resources.ts` 实现按工点分组、本地池 upsert/remove、目录投影、同类型多池标签和包含 `workpoint_id` 的稳定指纹；移除单值 `Map<type,pool>` 业务假设
- [x] T016 [P] [US1] (D05) 在 `04-demo/frontend/tests/resourceWorkpointRuntime.test.mjs` 先写真实页面行为：工点切换、默认可能资源、目录补充、数量/上限/状态编辑、空态、保存失败重试，断言“适用工点”勾选控件为 0
- [x] T017 [US1] (D05) 重构 `04-demo/frontend/src/features/resources/ResourcesTab.tsx` 为工点一级资源区，使用权威桥梁工点并只维护当前工点本地记录；架桥机和梁场不得进入目录或页面
- [x] T018 [P] [US1] (D05) 在 `04-demo/frontend/src/features/resources/styles.css` 实现工点导航、资源表、目录选择、加载/空态/错误态样式和可访问焦点，不改变其他 feature 样式
- [x] T019 [US1] (D05) 在 `04-demo/frontend/src/app/Workspace.tsx` 把资源更新从数组下标 patch 改为按 `pool.id/workpoint_id` 的 add/upsert/remove，复用版本 ID + 指纹拒绝晚到响应并触发统一结果失效
- [x] T020 [US1] (D05) 在 `04-demo/frontend/src/app/useWorkspaceController.ts` 和 `04-demo/frontend/tests/workspaceController.test.mjs` 中复核资源新增、删除、版本切换会清空任务图、求解、对比和集成快照，其他场景编辑行为不回归
- [x] T021 [US1] (D05) 运行 `04-demo/frontend/tests/resourceWorkpointScope.test.mjs`、`04-demo/frontend/tests/resourceWorkpointRuntime.test.mjs` 和 `04-demo/frontend/tests/workspaceController.test.mjs` 定向测试，对照 `03-requirements/specs/048-workpoint-first-resource-allocation/quickstart.md` 的 A/J 场景保存页面与机器可读证据，不执行前端全量或 build

**检查点**：用户故事 1 可独立演示，工点资源配置不依赖共享池页面。

---

## Phase 4：用户故事 2——合法候选与数量 0 阻断（P1）

**目标**：任务候选准确合并本地与共享实例；当前数量为 0 且无合法共享实例时阻断并提供结构化缺口诊断。

**独立测试**：执行 quickstart 场景 B、C、F，贯通 `ScenarioInput → ScheduleInput → ScheduleResult`。

**覆盖**：FR-006～FR-007、FR-014～FR-017、FR-022～FR-023、FR-032；SC-003、SC-008～SC-009。

- [x] T022 [P] [US2] (D02) 在 `04-demo/backend/tests/scheduling/test_workpoint_resource_scope.py`、`test_solver_constraints.py` 先写本地正数量、本地 0 + 共享补位、本地 0 + 无共享阻断、工点身份失配和诊断实体引用测试
- [x] T023 [US2] (D02) 在 `04-demo/backend/app/scheduling/application/_scenario.py` 修改资源可用性和 `_apply_required_resource_types`：当前模式按 `quantity` 判断合法实例，生成本地与所有匹配共享候选并输出工点/任务/类型/池 ID 诊断
- [x] T024 [P] [US2] (D02) 在 `04-demo/backend/tests/scheduling/test_fixed_resource_application.py` 先写当前实例展开测试，断言每个本地/共享池严格使用自身 `quantity`，0 数量不展开且不退化成默认充足
- [x] T025 [US2] (D02) 在 `04-demo/backend/app/scheduling/solver/engine.py` 复核并修正 `_resource_matches_task`、覆盖校验和资源组元数据，以 `pool_id + 显式工点字段` 生成候选和结构化缺口诊断，不解析实例 ID
- [x] T026 [P] [US2] (D02) 在 `04-demo/backend/tests/scheduling/test_resource_search_application.py` 先写三类数量语义：当前模式 0 阻断，增配/成本逐池搜索 `[quantity,max_quantity]`，最少资源逐池上界为 `max_quantity` 且可低于当前投入
- [x] T027 [US2] (D02) 在 `04-demo/backend/app/scheduling/application/_scenario.py` 和 `04-demo/backend/app/scheduling/solver/engine.py` 实现 T026 的模式感知预检和逐池结果，建议未采纳前不解除当前资源计划阻断
- [x] T028 [P] [US2] (D02) 在 `04-demo/backend/tests/scheduling/test_solver_results_diagnostics.py` 增加 `ResourceGapDiagnostic`、逐池当前/推荐量、本地/共享来源和状态原因测试
- [x] T029 [US2] (D02) 运行 `04-demo/backend/tests/scheduling/test_workpoint_resource_scope.py`、`04-demo/backend/tests/scheduling/test_solver_constraints.py`、`04-demo/backend/tests/scheduling/test_fixed_resource_application.py`、`04-demo/backend/tests/scheduling/test_resource_search_application.py` 和 `04-demo/backend/tests/scheduling/test_solver_results_diagnostics.py` 定向 pytest，对照 `03-requirements/specs/048-workpoint-first-resource-allocation/quickstart.md` 的 B/C/F 场景保存证据；断言默认充足误判 0、范围外候选 0、逐池数量回填准确

**检查点**：用户故事 2 可独立证明数量 0 和候选正确性，不依赖新共享池编辑页面。

---

## Phase 5：用户故事 3——多个范围共享池互斥流转（P1）

**目标**：同类型多个共享池独立维护范围和容量，任务可获得所有合法池候选，同一实例互斥且转场时间/成本为 0。

**独立测试**：执行 quickstart 场景 D、E 和性能样例。

**覆盖**：FR-008～FR-013、FR-018～FR-021、FR-032～FR-033；SC-004～SC-006、SC-010。

- [x] T030 [P] [US3] (D02) 在 `04-demo/backend/tests/scheduling/test_workpoint_resource_scope.py` 先写 P1(A/B)+P2(B/C) 同类型重叠共享池解析与候选矩阵测试，断言不再触发 `RESOURCE_SCOPE_DUPLICATE_TYPE`
- [x] T031 [US3] (D02) 在 `04-demo/backend/app/scheduling/domain/resource_scope.py` 删除类型唯一限制，增加池 ID 唯一、共享范围和工点本地唯一键校验，并保持每个共享池独立有效池 ID
- [x] T032 [P] [US3] (D02) 在 `04-demo/backend/tests/scheduling/test_resource_search_application.py` 先写重叠池容量下界测试，并在 `04-demo/backend/app/scheduling/solver/engine.py` 修正逐池下界重复计数，只对唯一候选池或候选池集合计算有效下界
- [x] T033 [P] [US3] (D05) 在 `04-demo/frontend/tests/resourceWorkpointRuntime.test.mjs` 先写独立共享池区域的新增、编辑、删除、同类型多池、重叠范围、“全部工点”与显式空范围阻断行为
- [x] T034 [US3] (D05) 在 `04-demo/frontend/src/features/resources/ResourcesTab.tsx`、`styles.css` 实现独立共享池区，以稳定 `pool.id` 管理同类型多池和工点范围，固定展示 0 天/0 成本提示
- [x] T035 [P] [US3] (D05) 在 `04-demo/frontend/tests/scheduleResultsPresenter.test.mjs` 先写两个同类型共享池分别展示、范围外不显示、实例来源和 0 天/0 成本提示测试
- [x] T036 [US3] (D05) 在 `04-demo/frontend/src/features/scheduleResults/presenter.ts`、`ScheduleResultsWorkspace.tsx` 按 `pool_id + pool_label` 展示来源池、工点和逐池数量，不再用资源类型取第一条池记录
- [x] T037 [P] [US3] (D02) 在 `04-demo/backend/tests/test_architecture_performance.py` 增加中等规模重叠共享池性能样例，记录候选/可选区间/状态/耗时并验证现有限时 `UNKNOWN` 语义，不新增池优先硬规则
- [x] T038 [US3] (D02) 运行 `04-demo/backend/tests/scheduling/test_workpoint_resource_scope.py`、`04-demo/backend/tests/scheduling/test_solver_constraints.py`、`04-demo/backend/tests/scheduling/test_resource_search_application.py` 和 `04-demo/backend/tests/test_architecture_performance.py` 的同类型多池、互斥、下界和性能定向 pytest，对照 `03-requirements/specs/048-workpoint-first-resource-allocation/quickstart.md` 的 D/E/性能场景保存证据；断言共享并发冲突 0、转场增量时间 0、成本 0、人工顺序字段 0

**检查点**：用户故事 3 可独立证明多池、范围、互斥和零转场，不依赖 AI 或计划快照。

---

## Phase 6：用户故事 4——旧配置与下游身份保真（P2）

**目标**：旧共享不拆分，同类型多池在 AI、计划、结果、镜像和指纹中不被类型键合并。

**独立测试**：执行 quickstart 场景 G、H、I，保存/重载、AI 更新、创建计划、修改单池并核对 stale。

**覆盖**：FR-024～FR-031、FR-033；SC-007～SC-010。

- [x] T039 [P] [US4] (D07) 在 `04-demo/backend/tests/test_ai_resource_scheduling_assistant.py`、`test_contracts_assistants.py` 先写同类型多共享池的生成、逐池编辑、上限、旧类型 map 歧义拒绝、单旧共享兼容和 stale 测试
- [x] T040 [US4] (D07) 在 `04-demo/backend/app/services/ai_resource_scheduling_assistant.py`、`ai_resource_explainer.py` 将画像、LLM/fallback、校验、数量回填、结果和解释改为 `resource_pool_id` 主键；旧 type map 只在唯一旧共享池时解析
- [x] T041 [P] [US4] (D05) 新增 `04-demo/frontend/tests/resourceAssistantPoolIdentity.test.mjs`，先写共享/本地结构化更新 payload、同类型多池独立编辑、标签和旧解释失效测试
- [x] T042 [US4] (D05) 在 `04-demo/frontend/src/domain/resourceAssistant.ts`、`features/resourceAssistant/ResourceAssistantPanel.tsx`、`ResourcePlanCard.tsx` 统一发送 `scoped_resource_updates` 并按池 ID 展示，不发送歧义类型 map
- [x] T043 [P] [US4] (D04) 在 `04-demo/backend/tests/test_plan_control_repository.py`、`test_plan_control_api.py`、`test_progress_forecast.py` 先写同类型多池顺序等价、单池语义变更指纹、历史保留和调整只改目标池测试
- [x] T044 [US4] (D04) 在 `04-demo/backend/app/services/plan_control_repository.py`、`progress_forecast.py` 保留 `workpoint_id` 和逐池身份，修改计划调整参数与 stale 链，禁止按资源类型广播到多个池
- [x] T045 [US4] (D04) 在 `04-demo/frontend/src/features/planControl/PlanControlPanel.tsx` 和新建 `04-demo/frontend/tests/planControlResourcePoolIdentity.test.mjs` 中把资源调整目标改为池/有效池身份，并明确同类型多池展示
- [x] T046 [P] [US4] (D06) 在 `04-demo/backend/tests/test_ai_parameter_assistant_scope.py`、`04-demo/backend/tests/test_ai_parameter_assistant_apply.py` 和 `04-demo/backend/tests/test_architecture_behavior_baseline.py` 中审计 AI 参数助手、默认配置、序列化与未部署 API mirror 的类型唯一假设，先写池身份保真失败用例
- [x] T047 [US4] (D06) 在 `04-demo/backend/app/services/ai_parameter_assistant.py`、`04-demo/tools/demo-api-mirror/api.mts` 修正 T046 证明的兼容差异；参考镜像不得扩展为正式后端或新增排除项
- [x] T048 [US4] (D06) 运行 `04-demo/backend/tests/test_local_scenario_config.py`、`04-demo/backend/tests/test_ai_resource_scheduling_assistant.py`、`04-demo/backend/tests/test_plan_control_repository.py`、`04-demo/backend/tests/test_ai_parameter_assistant_scope.py`、`04-demo/backend/tests/test_ai_parameter_assistant_apply.py` 和 `04-demo/backend/tests/test_architecture_behavior_baseline.py` 的旧共享/legacy 独享迁移、AI、计划、镜像和指纹定向测试，对照 `03-requirements/specs/048-workpoint-first-resource-allocation/quickstart.md` 的 G/H/I 场景保存证据；断言旧共享池数 1、字段保真 100%、同类型池误合并 0

**检查点**：用户故事 4 可独立证明旧数据和所有下游消费者保留池身份。

---

## Phase 7：跨故事回归、独立审查与收口

**目标**：核验全部用户故事和排除项，只执行一次完整发布门禁。

- [x] T049 [P] (D06) 对 `04-demo/backend/app/`、`04-demo/frontend/src/` 和 `04-demo/tools/demo-api-mirror/api.mts` 执行硬编码和身份扫描，人工分类 `Map<type,pool>`、`{pool.type:quantity}`、按名称/ID 格式判断和人工顺序字段，确认所有业务定位改为池 ID 且排除项新增 0
- [x] T050 [P] (D02) 运行 `04-demo/backend/tests/scheduling/test_workpoint_resource_scope.py`、`04-demo/backend/tests/scheduling/test_fixed_resource_application.py`、`04-demo/backend/tests/scheduling/test_resource_search_application.py`、`04-demo/backend/tests/scheduling/test_solver_constraints.py`、`04-demo/backend/tests/scheduling/test_solver_results_diagnostics.py` 和 `04-demo/backend/tests/test_architecture_performance.py` 的资源标准化、候选、固定资源、资源搜索、约束、结果诊断和性能定向 pytest，汇总 `03-requirements/specs/048-workpoint-first-resource-allocation/quickstart.md` 的 B～F 机器证据，不运行后端全量
- [x] T051 [P] (D05) 运行 `04-demo/frontend/tests/resourceWorkpointScope.test.mjs`、`04-demo/frontend/tests/resourceWorkpointRuntime.test.mjs`、`04-demo/frontend/tests/scheduleResultsPresenter.test.mjs`、`04-demo/frontend/tests/workspaceController.test.mjs` 和 `04-demo/frontend/tests/resourceAssistantPoolIdentity.test.mjs` 的工点页面、共享池页面、结果 presenter、Workspace 和资源助手定向测试，汇总 `03-requirements/specs/048-workpoint-first-resource-allocation/quickstart.md` 的 A/D/E/J 当前页面证据，不运行前端全量、typecheck 或 build
- [x] T052 [P] (D07) 运行 `04-demo/backend/tests/test_ai_resource_scheduling_assistant.py`、`04-demo/backend/tests/test_ai_parameter_assistant_scope.py`、`04-demo/backend/tests/test_ai_parameter_assistant_apply.py` 和 `04-demo/frontend/tests/resourceAssistantPoolIdentity.test.mjs` 的 AI 资源助手与参数助手定向 pytest/前端专项测试，确认逐池建议、旧格式兼容、上限和 stale 语义，不运行全量
- [x] T053 [P] (D04) 运行 `04-demo/backend/tests/test_plan_control_repository.py`、`04-demo/backend/tests/test_plan_control_api.py`、`04-demo/backend/tests/test_progress_forecast.py` 和 `04-demo/frontend/tests/planControlResourcePoolIdentity.test.mjs` 的计划 repository/API/forecast 和计划面板定向测试，确认逐池指纹、单池调整、历史保留和 stale，不运行全量
- [x] T054 [P] (D06) 运行 `04-demo/backend/tests/test_contracts_scheduling.py`、`04-demo/backend/tests/test_local_scenario_config.py`、`04-demo/backend/tests/test_architecture_api_contract.py` 和 `04-demo/backend/tests/test_architecture_behavior_baseline.py` 的共享契约、本地配置、API/存储架构和镜像差异定向测试，核对旧共享不拆分与 legacy 迁移证据，不运行全量
- [x] T055 (L03) 在 `03-requirements/product/资源配置页面需求文档_v1.2.md` 和 `03-requirements/rules/工点级资源作用域与求解规则需求文档_v1.0.md` 同步工点主导、多独立共享池、数量 0 阻断、零转场和旧共享兼容口径，并保留与 047 的演进说明
- [x] T056 (D06) 在 `03-requirements/specs/048-workpoint-first-resource-allocation/quickstart.md` 逐项核对场景 A～J、FR-001～FR-033、SC-001～SC-010 与 T049～T055 证据；发现缺口时先追加任务，不直接进入全量门禁
- [ ] T057 (D06) 在 T049～T056 全部通过后执行 R3 独立发布门禁：针对 `04-demo/backend/tests/`、`04-demo/frontend/tests/` 和 `04-demo/frontend/package.json` 重跑一个“本地 0 + 两个同类型重叠共享池 + 旧共享迁移 + 逐池 AI/计划”最高风险贯通样例，并集中执行本功能唯一一次后端全量、前端全量、typecheck、build、`npm.cmd run verify:architecture`、`python 00-governance/repository-tools/validate_docs.py` 和 `git diff --check`
- [x] T058 (D06) 在 `03-requirements/specs/048-workpoint-first-resource-allocation/spec.md` 的实施证据节汇总 R3 命令、退出码、环境版本、证据路径、FR/SC 覆盖和残余风险；任何失败保持工作项未完成，不重复无边界全量测试
- [ ] T059 (L03) 仅在本主责 Thread 核验 T001～T058 全部通过后，将 `03-requirements/specs/048-workpoint-first-resource-allocation/spec.md` 状态更新为 completed 并记录实施证据；未经用户另行授权不修改 README、不提交 Git

## 依赖与执行顺序

### 阶段依赖

- Phase 1 共享契约阻塞所有领域实现：T001/T002 先写失败测试，T003/T004 实现，T005/T006 固定增量基线。
- Phase 2 依赖 Phase 1：T007→T008，T009→T010，T011→T012，T013 在标准化稳定后完成。
- US1、US2、US3 均依赖 Phase 2；US1 页面和 US2 算法可以并行，US3 的共享池页面依赖 US1 的工点页面结构，算法分支依赖 US2 的模式感知基础。
- US4 依赖共享契约和规范池身份；D07、D04、D05 子分支可并行，T048 在其后统一兼容复核。
- Phase 7 依赖全部用户故事；T057 只能在 T049～T056 完成后执行，T059 最后收口。

### 用户故事依赖

- **US1（P1）**：Phase 2 后可独立交付工点资源页面。
- **US2（P1）**：Phase 2 后可独立交付候选与阻断，不依赖新共享池 CRUD。
- **US3（P1）**：算法部分依赖 US2 候选基础，页面部分依赖 US1 资源区结构；完成后独立证明多池流转。
- **US4（P2）**：依赖规范池和多池身份，完成后独立证明兼容与下游保真。

### 可并行项

- Phase 1 的后端/前端契约测试可并行。
- Phase 2 的标准化、迁移和目录测试可在不同文件并行。
- US1 前端与 US2 后端可并行实施，路径不重叠。
- US4 的 D07、D04 和前端展示可按不重叠文件并行；共享契约和镜像由 D06 串行收口。
- T049～T054 可由只读/测试 Subagent 并行；T055～T059 串行。

## 并行示例

```text
Subagent d05_workpoint_ui:
  allowed_paths:
    - 04-demo/frontend/src/domain/resources.ts
    - 04-demo/frontend/src/features/resources/
    - 04-demo/frontend/tests/resourceWorkpoint*.test.mjs

Subagent d02_resource_candidates:
  allowed_paths:
    - 04-demo/backend/app/scheduling/
    - 04-demo/backend/tests/scheduling/

Subagent d07_resource_ai:
  allowed_paths:
    - 04-demo/backend/app/services/ai_resource_*
    - 04-demo/frontend/src/features/resourceAssistant/
    - 04-demo/frontend/src/domain/resourceAssistant.ts
```

`Workspace.tsx`、共享 contracts、架构基线、`quickstart.md` 和最终证据属于共享文件，必须由主 Thread 串行修改或在隔离 Worktree 合并。

## 实施策略

### MVP 优先

1. 完成 Phase 1～2。
2. 并行完成 US1 工点页面与 US2 候选阻断。
3. 完成 US3 多共享池和互斥流转，形成核心 MVP。
4. 停下执行 A～F 定向验证。
5. 再完成 US4 兼容、AI 和计划下游。

### 停止条件

- 需要纳入架桥机、梁场、非零转场时间/费用、人工流转顺序、调拨审批或跨项目共享。
- 需要新增未经确认的本地优先、共享池优先或同结构跨池绑定规则。
- 旧共享配置无法保持单池、数量或范围；legacy 独享无法证明无损迁移。
- 任务 `bridge_id` 不能稳定对应当前权威桥梁工点。
- 多池性能需要改变现有目标函数、时间预算或结果语义。
- 实施路径超出本任务清单或连续验证失败需要扩大范围。

触发任一条件时，本主责 Thread 停止扩大范围并请求用户确认。

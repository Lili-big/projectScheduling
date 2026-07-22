---

description: "统一固定资源与最少资源求解实施任务清单"
---

# 任务清单：统一固定资源与最少资源求解

**输入**：`03-requirements/specs/056-unified-fixed-resource-solve/` 下的 `spec.md`、`plan.md`、`research.md`、`data-model.md`、`contracts/` 和 `quickstart.md`

**前置门禁**：本清单经用户确认后才能执行。当前所有任务保持未完成状态。

**测试要求**：本功能改变 CP-SAT 目标、固定资源/工期调用链、资源数量搜索、共享结果元数据和前端展示；测试任务必须先写并确认能识别旧行为，再实施对应代码。

## 格式

- `[P]`：不同文件且不存在实现依赖，可并行。
- `[US1]`：给定资源统一求解工期。
- `[US2]`：全局搜索最少资源后生成一次详细排程。
- `[US3]`：页面准确展示统一目标和结果来源。

## Phase 1：准备与工作树保护

**目标**：在当前存在并行未提交改动的工作树上建立 056 的最小修改边界，不覆盖其他工作项。

- [ ] T001 检查并记录 `04-demo/backend/app/scheduling/application/_scenario.py`、`04-demo/backend/app/scheduling/solver/engine.py`、`04-demo/backend/app/services/ai_resource_scheduling_assistant.py`、`04-demo/frontend/src/app/Workspace.tsx` 和相邻测试的现有 diff；实施时只编辑 056 对应符号并保留无关改动

**检查点**：已确认可安全编辑的函数/测试块及现有基线失败；没有还原、格式化或覆盖无关文件。

---

## Phase 2：用户故事 1 - 给定资源统一求解工期（优先级：P1）

**目标**：模拟固定资源和 AI 资源方案严格按输入数量调用同一个一阶段 solver，最大目标延期优先、总工期其次，不增配、不输出方案 2。

**独立测试**：同一范围化 `ScheduleInput` 经 simulation 与 AI 入口分别求解；断言 solver 调用各 1 次、命名资源快照相同、目标/四态相同、资源诊断不参与目标、方案 2 与增配次数为 0。

### 用户故事 1 的测试（先写）

- [ ] T002 [P] [US1] 在 `04-demo/backend/tests/scheduling/test_fixed_resource_application.py` 增加 simulation/AI 共用内核、严格资源数量、单次调用、空 `alternative_results` 和无扩资源的失败测试
- [ ] T003 [P] [US1] 在 `04-demo/backend/tests/scheduling/test_solver_objectives.py` 增加“最大目标延期 -> 总工期”的目标顺序、资源空闲/连续性 modeling gate 关闭但诊断保留、施工硬约束不变的失败测试
- [ ] T004 [P] [US1] 在 `04-demo/backend/tests/test_scheduler.py` 增加 `OPTIMAL/FEASIBLE/UNKNOWN/INFEASIBLE/MODEL_INVALID`、目标存在/缺失、延期/不延期的四态矩阵及有排程不丢失测试
- [ ] T005 [P] [US1] 在 `04-demo/backend/tests/test_ai_resource_scheduling_assistant.py` 增加 AI 单方案输入资源快照、`met` 推荐门禁、非 `met` 不推荐和共享来源/调用次数字段测试

### 用户故事 1 的实现

- [ ] T006 [US1] 在 `04-demo/backend/app/scheduling/solver/engine.py` 将现有 `solve_control_priority_schedule_once` 收敛为入口无关的权威固定资源一阶段函数：一次 CP-SAT 调用、目标顺序固定、资源组织目标禁用、通用调用/来源元数据完整
- [ ] T007 [US1] 在 `04-demo/backend/app/scheduling/solver/results.py` 与 `04-demo/backend/app/scheduling/solver/engine.py` 统一四态 `target_achievement` 分类、最大目标延期计算和兼容字段，使固定资源与后续最少资源详细排程复用同一纯结果规则
- [ ] T008 [US1] 在 `04-demo/backend/app/scheduling/application/_scenario.py` 建立 simulation/AI 共用的 `GeneratedScheduleInput` 包装，统一预算、范围诊断、场景结果组装和入口来源，且不得再次调用 solver
- [ ] T009 [US1] 在 `04-demo/backend/app/scheduling/application/_scenario.py` 与 `04-demo/backend/app/scheduling/application/fixed_resource.py` 将 `solve_scenario` 改接共享包装，停止运行 `_solve_fixed_resources_shortest_scenario`、最少资源/压力搜索、自动增配和方案 2，并保持 `alternative_results=[]` 兼容
- [ ] T010 [US1] 在 `04-demo/backend/app/scheduling/application/_scenario.py` 与 `04-demo/backend/app/services/ai_resource_scheduling_assistant.py` 将 `solve_ai_strict_fixed_resource_scenario` 改接同一包装，只保留 AI 资源方案、plan status 和推荐门禁职责，删除重复目标判定与入口专属 solver 元数据
- [ ] T011 [US1] 在 `04-demo/backend/tests/test_scheduling_routes.py` 和 `04-demo/backend/tests/test_contracts_scheduling.py` 增加 `/api/solve-scenario` 路径、顶层响应、旧扩展字段读取及新结果 `not_run/not_applicable` 兼容测试
- [ ] T012 [US1] 运行 `python -m pytest 04-demo/backend/tests/scheduling/test_fixed_resource_application.py 04-demo/backend/tests/scheduling/test_solver_objectives.py 04-demo/backend/tests/test_ai_resource_scheduling_assistant.py 04-demo/backend/tests/test_scheduling_routes.py -q`，修复 056 相关失败并记录 US1 独立通过证据

**检查点**：US1 可独立交付；两个入口共享一阶段函数且每请求仅一次求解，目标/状态一致，硬约束和诊断保留，无资源建议分支。

---

## Phase 3：用户故事 2 - 全局搜索最少资源后生成详细排程（优先级：P1）

**目标**：固定工期只执行一次 `0..max_quantity` 全局联合搜索，得到候选后只执行一次 US1 详细排程；任何非 `met` 结果都停止且不增配重试。

**独立测试**：用 spy 分别制造全局 `OPTIMAL/FEASIBLE/UNKNOWN/INFEASIBLE` 与详细四态，断言最多 1 次全局搜索和 1 次详细调用，二分/预检/压力/最佳努力调用为 0，候选验证只由详细 `met` 决定。

### 用户故事 2 的测试（先写）

- [ ] T013 [P] [US2] 在 `04-demo/backend/tests/scheduling/test_solver_objectives.py` 增加全局数量模型词典序目标测试：资源总数最少为第一目标、同数下总工期更短为第二目标，资源成本/空闲不参与
- [ ] T014 [P] [US2] 在 `04-demo/backend/tests/test_scheduler.py` 增加默认下限 0、推荐低于当前 `quantity`、池数量 0 不展开资源、稳定池身份/作用域和无合法候选阻断测试
- [ ] T015 [P] [US2] 在 `04-demo/backend/tests/scheduling/test_resource_search_application.py` 增加“1 次全局搜索 + 0/1 次详细求解”、候选四态验证、候选保留及所有预检/二分/压力/复排/重试为 0 的失败测试
- [ ] T016 [P] [US2] 在 `04-demo/backend/tests/scheduling/test_single_workpoint_solve.py` 增加 ALL/WORKPOINT 全局搜索隔离、同范围 fallback 目标和跨范围结果不复用测试

### 用户故事 2 的实现

- [ ] T017 [US2] 在 `04-demo/backend/app/scheduling/solver/engine.py` 调整 `_solve_capacity_model(..., minimize_resource_count=True)`：每池默认下限 0、上限 `max_quantity`，严格保持池身份/作用域/兼容/硬约束，并实现资源总数与总工期的两级裁决
- [ ] T018 [US2] 在 `04-demo/backend/app/scheduling/solver/engine.py` 简化 `solve_min_resources_schedule`：删除最大资源独立预检、独占下限提前结论、逐池二分、balanced/unbalanced/best-effort 复排和压力回退，只保留一次全局搜索的终态处理
- [ ] T019 [US2] 在 `04-demo/backend/app/scheduling/solver/engine.py` 按全局候选数量展开稳定命名资源并恰好调用一次 US1 权威固定资源函数；只在详细 `met` 时写入 `candidate_verified=true`，其他状态保留候选与详细排程并停止
- [ ] T020 [US2] 在 `04-demo/backend/app/scheduling/application/_scenario.py` 与 `04-demo/backend/app/scheduling/application/resource_search.py` 保持强制里程碑优先、同范围 `fallback_target_days` 次之的目标来源，补齐全局/详细来源、调用次数、验证和无重试元数据
- [ ] T021 [US2] 在 `04-demo/backend/tests/test_scheduling_routes.py` 与 `04-demo/backend/tests/test_contracts_scheduling.py` 增加 `/api/solve-min-resources` 候选、详细状态、验证状态和旧响应外壳兼容测试，不新增 API 路径或请求字段
- [ ] T022 [US2] 运行 `python -m pytest 04-demo/backend/tests/scheduling/test_resource_search_application.py 04-demo/backend/tests/scheduling/test_single_workpoint_solve.py 04-demo/backend/tests/scheduling/test_solver_objectives.py 04-demo/backend/tests/test_scheduling_routes.py -q`，修复 056 相关失败并记录 US2 独立通过证据

**检查点**：US2 可独立交付；全局终态不会触发回退，有候选时只跑一次同算法详细排程，候选验证与详细业务状态一致。

---

## Phase 4：用户故事 3 - 页面准确展示统一目标和结果来源（优先级：P2）

**目标**：模拟求解页不再把资源空闲/连续性展示为可选优化目标；固定资源与固定工期结果准确区分目标、solver 状态、候选、详细状态、验证和历史来源。

**独立测试**：渲染/检查模拟求解页面和结果 presenter；断言只读两级目标、诊断说明、候选/详细/验证分栏、新旧来源兼容以及现有范围和保存门禁不变。

### 用户故事 3 的测试（先写）

- [ ] T023 [P] [US3] 在 `04-demo/frontend/tests/workspaceController.test.mjs` 与 `04-demo/frontend/tests/scheduleResults.test.mjs` 增加只读目标顺序、无资源空闲优化控件、四态/solver 状态和“未自动增配”展示测试
- [ ] T024 [P] [US3] 在 `04-demo/frontend/tests/scheduleResultsPresenter.test.mjs` 增加最少资源候选、详细状态、`candidate_verified` 和旧多阶段来源的派生展示测试
- [ ] T025 [P] [US3] 在 `04-demo/frontend/tests/apiCompatibility.test.mjs`、`04-demo/frontend/tests/contractsCompatibility.test.mjs` 与 `04-demo/frontend/tests/deploymentContract.test.mjs` 增加三个接口、共享元数据和 Demo 镜像一致性测试

### 用户故事 3 的实现

- [ ] T026 [US3] 在 `04-demo/frontend/src/app/Workspace.tsx` 将固定资源/固定工期的“算法倾向选择”和权重编辑改为只读两级目标说明，并把资源空闲、连续性明确移入求解后诊断语义；资源成本优化入口保持原行为
- [ ] T027 [US3] 在 `04-demo/frontend/src/contracts/scheduler.ts`、`04-demo/frontend/src/features/scheduleResults/presenter.ts` 与 `04-demo/frontend/src/app/Workspace.tsx` 解析并展示业务四态、solver 状态、最大延期、调用次数、全局候选、详细验证和历史来源，保持缺字段旧结果可读
- [ ] T028 [US3] 在 `04-demo/tools/demo-api-mirror/api.mts` 同步新结果来源、调用次数、四态和候选验证语义，确保镜像不再模拟增配/方案 2 或用容量候选冒充详细成功
- [ ] T029 [US3] 运行 `npm.cmd --workspace 04-demo/frontend test -- --test-name-pattern="solve|objective|resource"`、`npm.cmd run typecheck` 和 `npm.cmd run build`，修复 056 相关失败并记录 US3 独立通过证据

**检查点**：US3 可独立交付；页面文案与实际算法一致，新旧结果均可解释，工点范围/指纹/保存/比较门禁不回归。

---

## Phase 5：横切兼容与完成验证

**目标**：确认 056 没有改变明确排除的业务边界，并通过一次完整门禁。

- [ ] T030 [P] 在 `04-demo/backend/tests/test_ai_resource_scheduling_assistant.py` 与 `04-demo/backend/tests/test_ai_workpoint_resource_comparison.py` 补齐仅 `met` 推荐、LLM 资源生成/人工调整不变及计划历史读取兼容验证
- [ ] T031 [P] 在 `04-demo/backend/tests/test_scheduler.py` 增加资源成本优化路径不调用统一最少资源简化分支、项目主数据/架梁专项入口不受影响的回归断言
- [ ] T032 对 `04-demo/backend/app/scheduling/application/_scenario.py`、`04-demo/backend/app/scheduling/solver/engine.py` 和相关导出执行 056 范围内死代码/未使用导入清理；只删除已由测试证明不再可达的固定资源增配、最少资源回退辅助代码，不触碰资源成本与其他工作项
- [ ] T033 按 `03-requirements/specs/056-unified-fixed-resource-solve/quickstart.md` 运行最终定向样例，并仅运行一次 `npm.cmd run verify` 完整门禁；记录通过结果或有证据的既有无关失败，不重复执行完整门禁

**完成检查点**：FR-001～FR-025、SC-001～SC-010 均有实现和测试证据；相关验证通过；无未解释的共享契约、历史兼容或范围风险。

---

## 依赖与执行顺序

### 阶段依赖

1. Phase 1 必须先完成，保护并行工作树改动。
2. US1 是权威固定资源内核，必须先于 US2。
3. US2 依赖 US1 的 solver 函数，但不依赖 US3。
4. US3 的测试可在 US1/US2 实施期间按不同文件准备；最终接线依赖后端元数据稳定。
5. Phase 5 只在三个故事检查点通过后执行。

### 故事内部顺序

- 先完成对应“测试（先写）”任务并确认旧行为被捕获，再实施。
- US1：T006 → T007 → T008 → T009/T010 → T011/T012。
- US2：T017 → T018 → T019 → T020/T021 → T022。
- US3：T026 → T027/T028 → T029。
- 同一文件上的任务不得并行，必须合并现有未提交 diff 后顺序编辑。

### 可并行机会

- T002～T005 分属不同测试关注点，可并行准备。
- T013～T016 分属 solver/application/scope 测试，可并行准备。
- T023～T025 分属页面、presenter、契约测试，可并行准备。
- T030 与 T031 修改不同测试文件，可并行；T032 必须等待实现稳定。

## 需求追踪矩阵

| 规格 | 设计/实现任务 | 验证任务 |
|---|---|---|
| FR-001～FR-003 | T006、T008～T010 | T002、T005、T012 |
| FR-004～FR-006 | T006、T007 | T003、T004、T012 |
| FR-007～FR-010 | T007～T011 | T002、T004、T011、T012 |
| FR-011～FR-013 | T017、T018 | T013、T014、T022 |
| FR-014～FR-017 | T018～T020 | T015、T021、T022 |
| FR-018～FR-019 | T020 | T016、T021、T022 |
| FR-020～FR-021 | T026、T027 | T023、T024、T029 |
| FR-022～FR-025 | T010、T011、T027、T028、T030～T032 | T005、T025、T029～T033 |
| SC-001～SC-004 | T006～T012 | T002～T005、T012 |
| SC-005～SC-008 | T017～T022 | T013～T016、T022 |
| SC-009 | T020、T027、T028、T030～T032 | T016、T024、T025、T030、T031、T033 |
| SC-010 | T011、T021、T025～T033 | T029～T033 |

## 实施策略

1. 先交付 US1，使 simulation 与 AI 固定资源口径统一并可独立验证。
2. 再交付 US2，把固定工期压缩为一次全局搜索和一次详细排程。
3. 最后交付 US3，使页面、契约和镜像准确反映新行为。
4. 任一故事检查点失败时只修复该故事相关问题，不扩展到资源成本、LLM、项目主数据或架梁专项。
5. 全部验收满足后立即停止，不做无关重构或额外性能优化。

# 任务清单：单工点模拟求解

**输入**：`03-requirements/specs/054-single-workpoint-solve/` 下的 `spec.md`、`plan.md`、`research.md`、`data-model.md`、`contracts/` 和 `quickstart.md`

**实施门禁**：本清单及一致性结果必须由用户确认后才能执行 `$speckit-implement`。

## Phase 1：共享契约与范围基础

**目标**：先以失败测试冻结可选范围、响应元数据、完整资源作用域和里程碑匹配不变量，再建立两个用户故事共用的最小契约基础。

- [x] T001 [P] 在 `04-demo/backend/tests/test_scheduling_routes.py` 增加四个排程端点的可选 `workpoint_id`、缺省全项目、非法/过期/非桥梁 ID 返回 422 和 `solve_scope` 响应契约测试，并先确认新断言在实现前失败
- [x] T002 [P] 在 `04-demo/backend/tests/scheduling/test_single_workpoint_solve.py` 新增两工点样例，冻结单工点任务、关系、资源、里程碑、三类求解、备选结果、空任务和零资源 `RESOURCE_ALLOCATION_NO_LEGAL_CANDIDATE` 诊断不变量，并先确认新测试在实现前失败
- [x] T003 [P] 在 `04-demo/frontend/tests/singleWorkpointSolve.test.mjs` 增加范围化指纹、同范围固定工期基准、范围切换失效、迟到响应保护和结果范围展示测试，并先确认新测试在实现前失败
- [x] T004 [P] 在 `04-demo/frontend/tests/apiCompatibility.test.mjs` 增加前端 API 与 `04-demo/tools/demo-api-mirror/api.mts` 对可选查询字段、422 错误和 `solve_scope` 的兼容断言，并先确认新断言在实现前失败
- [x] T005 [P] 在 `04-demo/backend/app/contracts/_models.py` 定义并校验非持久化 `SolveScope`，给 `GeneratedScheduleInput` 增加必填 `solve_scope` 默认全项目字段，并在 `04-demo/backend/app/contracts/scheduling.py` 导出该类型
- [x] T006 [P] 在 `04-demo/frontend/src/contracts/scheduler.ts` 增加与后端一致的 `SolveScope`，并给 `GeneratedScheduleInput` 增加类型化 `solve_scope`
- [x] T007 [P] 将 `04-demo/backend/app/scheduling/solver/engine.py` 的里程碑任务匹配语义无变化抽取到 `04-demo/backend/app/scheduling/domain/milestone_scope.py`，让 solver 改用共享函数并保持现有里程碑测试通过

**检查点**：共享字段和里程碑匹配权威已建立，旧请求仍可解析为全项目范围。

---

## Phase 2：用户故事 1 - 选择单个工点进行试算（优先级：P1）

**目标**：在三个求解按钮中只生成并求解所选桥梁工点，同时保留完整资源事实和现有算法语义。

**独立测试**：用包含两个工点和项目共享/工点独享资源的样例分别执行三类求解，断言任务 100% 属于所选工点、关系无悬空、资源候选合法、里程碑全部命中且范围元数据一致。

- [x] T008 [US1] 在 `04-demo/backend/app/scheduling/application/_scenario.py` 实现项目物化后的单工点范围解析、只遍历所选桥梁的任务构建、工点内关系、合法有效池筛选、共享里程碑匹配和无任务阻断，同时保持资源有效值解析读取完整项目
- [x] T009 [US1] 在 `04-demo/backend/app/scheduling/application/_scenario.py` 将同一范围贯穿固定资源最短工期、最大资源分支、备选方案、固定工期最少资源、资源成本优化和所有回退生成调用，确保主结果与备选结果的 `solve_scope` 完全一致
- [x] T010 [US1] 在 `04-demo/backend/app/api/routers/scheduling.py` 给生成和三类求解端点接入可选 `workpoint_id`，在完整项目物化后校验桥梁工点并以稳定错误码返回 422，禁止非法范围回退全项目
- [x] T011 [P] [US1] 在 `04-demo/frontend/src/api/_schedulerApi.ts` 为生成和三类求解请求统一追加可选 `workpoint_id` 查询参数，缺省时保持原 URL 与请求体兼容
- [x] T012 [US1] 在 `04-demo/frontend/src/app/workflows/scenarioWorkflow.ts` 和 `04-demo/frontend/src/app/workflows/solveWorkflow.ts` 定义范围化指纹与同范围基准判断，让场景和工点范围共同决定生成、求解及固定工期结果有效性
- [x] T013 [US1] 在 `04-demo/frontend/src/app/Workspace.tsx` 复用 `currentResourceWorkpoints` 增加默认“全部工点”的求解范围状态和下拉菜单，将同一范围传入三个求解按钮，并实现加载/空态/失败态/忙碌禁用、切换失效和迟到响应丢弃
- [x] T014 [P] [US1] 在 `04-demo/frontend/src/features/scheduleResults/presenter.ts` 增加范围标签和名称回退展示函数，并在 `04-demo/frontend/src/app/Workspace.tsx` 的结果摘要中持续显示“全部工点”或“单工点试算：名称（ID）”
- [x] T015 [US1] 在 `04-demo/tools/demo-api-mirror/api.mts` 解析相同查询参数，按同一任务/关系/资源/里程碑范围生成结果，返回 `solve_scope`，并对非法工点返回 422 而不回退全项目
- [x] T016 [US1] 运行 `04-demo/backend/tests/test_scheduling_routes.py`、`04-demo/backend/tests/scheduling/test_single_workpoint_solve.py`、`04-demo/frontend/tests/singleWorkpointSolve.test.mjs` 和 `04-demo/frontend/tests/apiCompatibility.test.mjs`，确认用户故事 1 的正常、非法、空任务和资源阻断样例全部通过

**检查点**：用户可在三类求解中独立完成单工点试算，全项目之外的任务和关系不会进入模型。

---

## Phase 3：用户故事 2 - 保留全项目求解并隔离结果（优先级：P1）

**目标**：保持旧全项目行为，阻止单工点结果被保存为全项目方案或进入全项目比较，并使范围切换后的旧结果不可复用。

**独立测试**：先生成全项目结果再生成单工点结果，验证两者指纹和基准独立；全项目仍可保存和比较，单工点保存及任何包含单工点的比较均被前后端明确拒绝。

- [x] T017 [P] [US2] 在 `04-demo/backend/tests/scheduling/test_single_workpoint_solve.py` 和 `04-demo/backend/tests/test_scheduling_routes.py` 增加全项目结果可比较、单工点结果不可比较、混合范围不可比较及旧请求结果不变的失败测试
- [x] T018 [P] [US2] 在 `04-demo/frontend/tests/singleWorkpointSolve.test.mjs` 和 `04-demo/frontend/tests/workspaceController.test.mjs` 增加单工点保存/比较阻断、可见原因、全项目保存兼容和范围切换清理测试
- [x] T019 [US2] 在 `04-demo/backend/app/scheduling/application/_scenario.py` 校验 `compare_scenarios` 只接受全项目结果，并在 `04-demo/backend/app/api/routers/scheduling.py` 将单工点或混合范围比较映射为明确 422 错误
- [x] T020 [US2] 在 `04-demo/frontend/src/app/Workspace.tsx` 阻止单工点结果进入 `saveCurrentResult` 和 `compareSavedResults`，为禁用的保存动作展示“单工点结果仅用于试算”原因，同时保留全项目保存与比较行为
- [x] T021 [US2] 在 `04-demo/tools/demo-api-mirror/api.mts` 同步拒绝单工点和混合范围比较，保持静态演示环境与 FastAPI 的结果安全边界一致
- [x] T022 [US2] 运行 `04-demo/backend/tests/scheduling/test_single_workpoint_solve.py`、`04-demo/backend/tests/test_scheduling_routes.py`、`04-demo/frontend/tests/singleWorkpointSolve.test.mjs` 和 `04-demo/frontend/tests/workspaceController.test.mjs` 的 T017、T018 定向样例，确认单工点误保存、跨范围比较、跨范围基准复用和旧响应覆盖次数均为 0

**检查点**：全项目路径保持兼容，单工点试算不会被误用为正式全项目方案。

---

## Phase 4：跨层验证与收敛

**目标**：只运行与共享契约、资源/求解回归、前端构建和参考性能相匹配的最小完整门禁。

- [x] T023 更新 `04-demo/backend/tests/fixtures/architecture/backend-baseline.json` 和 `04-demo/frontend/tests/fixtures/architecture/frontend-baseline.json`，只纳入本功能新增查询参数、`SolveScope` 共享字段和受影响模块依赖，不接受无关架构漂移
- [x] T024 运行 `04-demo/backend/tests/scheduling/test_workpoint_resource_scope.py`、`04-demo/backend/tests/scheduling/test_solver_constraints.py`、`04-demo/backend/tests/scheduling/test_fixed_resource_application.py`、`04-demo/backend/tests/scheduling/test_resource_search_application.py` 和 `04-demo/backend/tests/scheduling/test_solver_results_diagnostics.py`，确认稳定池 ID、共享互斥、工点独享、数量为 0、诊断和现有三类求解语义无回归
- [x] T025 运行 `npm.cmd --workspace 04-demo/frontend test`、`npm.cmd run typecheck` 和 `npm.cmd run build`，确认范围交互、共享类型、镜像兼容和生产构建通过且无重复验证失败
- [x] T026 按 `03-requirements/specs/054-single-workpoint-solve/quickstart.md` 的 E 场景验证参考项目最大工点，记录全项目/单工点任务与关系数、求解状态、solver wall time 和端到端耗时到该文件的实施证据节，并确认任务下降至少 80%、合法资源下 8 秒内返回完整可行结果
- [ ] T027 运行 `npm.cmd run verify:architecture` 和 `git diff --check -- 03-requirements/specs/054-single-workpoint-solve 04-demo`，确认 OpenAPI、FastAPI、前端、Netlify 镜像、架构依赖和文档门禁一致后停止

---

## 依赖与执行顺序

### 阶段依赖

- **Phase 1**：先编写 T001～T004 的失败测试，再并行完成 T005～T007；这是两个故事的阻塞基础。
- **Phase 2 / US1**：依赖 T005～T007；T008 → T009 → T010，T011 可与后端链并行，T012 依赖 T011，T013 依赖 T012，T014 可在 T006 后并行，T015 依赖契约和范围规则，最后执行 T016。
- **Phase 3 / US2**：依赖 US1 的范围元数据和指纹；T017、T018 可并行，随后分别完成后端 T019、前端 T020 和镜像 T021，最后执行 T022。
- **Phase 4**：依赖两个故事完成；T023 后运行 T024、T025，随后执行有真实项目数据依赖的 T026，最后只运行一次 T027。

### 并行机会

- T001～T004 分属不同测试文件，可并行建立失败基线。
- T005、T006、T007 分属后端契约、前端契约和里程碑领域文件，可在失败测试就绪后并行。
- T011 与 T008～T010 的后端实现可并行；T014 可在范围响应类型确定后并行。
- T017 与 T018 可并行；T019、T020、T021 分属后端、前端和镜像，可在各自测试完成后并行。
- T024 与 T025 可并行，T026 需要本地确认项目和合法资源配置，不能与可能改变资源样例的实施步骤并行。

## 需求与成功标准覆盖

| 来源 | 覆盖任务 |
|---|---|
| US1；FR-001、FR-002、FR-003、FR-004、FR-005、FR-006、FR-007、FR-008、FR-009、FR-010、FR-013、FR-014、FR-015、FR-016 | T001～T016 |
| US2；FR-002、FR-010、FR-011、FR-012、FR-015、FR-016 | T017～T022 |
| 资源/算法不变量 FR-006、FR-007、FR-008、FR-009 | T002、T007～T009、T015、T024 |
| 共享契约与兼容 FR-010、FR-013、FR-015 | T001、T004～T006、T010～T015、T023、T027 |
| SC-001、SC-002、SC-005、SC-007 | T001～T003、T008～T016、T024 |
| SC-003 | T017～T022 |
| SC-004 | T002、T016、T026 |
| SC-006 | T001、T017、T023～T025、T027 |

## 实施边界

- 不创建新的场景持久化字段、数据库迁移、资源默认值或多工点组合模式。
- 不改变 solver 目标、权重、硬约束、资源数量/互斥和转场语义。
- 不写入或修改并发中的 `03-requirements/specs/052-*`、`053-ai-workpoint-resource-comparison/` 及其工作树内容。
- T001～T027 全部完成且相关验证通过后立即停止；任何范围语义、保存策略或比较策略变更必须返回用户确认，不在实施中自行扩展。


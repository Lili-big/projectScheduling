# 任务清单：目标指标建模门控

**输入**：来自 `specs/008-objective-model-gating/` 的设计文档  
**前置条件**：`plan.md`、`spec.md`、`research.md`、`data-model.md`、`contracts/objective-model-gating-contract.md`、`quickstart.md`

**测试要求**：本功能涉及 CP-SAT 建模范围、目标函数配置、结果诊断和前端展示，必须包含后端回归测试、前端构建验证和可复现手工场景。  
**组织方式**：任务按用户故事分组，确保每个故事都可独立实现和验证。用户确认本清单和分析报告前不得实施代码。

## Phase 1：准备（共享基础）

**目标**：确认当前工作树和实现入口，避免覆盖 007 或其他 agent 的改动。

- [X] T001 检查当前 `git status --short`，确认 `backend/app/scenario.py`、`backend/app/solver.py`、`.specify/feature.json`、`specs/007-objective-metric-config/` 的既有改动归属，实施时不得回退无关改动。
- [X] T002 复核 `specs/008-objective-model-gating/spec.md`、`plan.md`、`research.md`、`data-model.md`、`contracts/objective-model-gating-contract.md`，确认本功能只在 008 下继续。
- [X] T003 [P] 复核 `backend/app/models.py` 中 `ObjectiveTermId`、`DEFAULT_OBJECTIVE_TERM_WEIGHTS`、`effective_objective_weights()`、`objective_terms_used()` 的当前行为。
- [X] T004 [P] 复核 `backend/app/solver.py` 中 `solve_control_priority_schedule()`、`_build_resource_organization_terms()`、`_build_control_buffer_terms()`、`_build_control_wait_term_details()`、`_risk_related_control_wait_terms()` 的建模入口。
- [X] T005 [P] 复核 `frontend/src/types/scheduler.ts` 和 `frontend/src/app/App.tsx` 中目标项、状态字段和结果诊断展示入口。

---

## Phase 2：基础能力（阻塞前置）

**目标**：建立统一的目标建模门控、共享支持数据门控和禁用状态元数据，供所有用户故事复用。

- [X] T006 在 `backend/app/solver.py` 增加目标建模门控辅助逻辑，基于 `objective_weights` 输出每个目标项的 `modeling_enabled`、`status` 和 `reason`。
- [X] T007 在 `backend/app/solver.py` 增加禁用目标的空诊断构造逻辑，统一返回未启用或未评价状态、0 罚分和 0 建模规模。
- [X] T008 在 `backend/app/solver.py` 增加共享支持数据依赖判断，区分目标专属建模、最小共享支持数据和最佳努力放松诊断。
- [X] T009 在 `backend/app/solver.py` 调整 `weighted_objective` 汇总路径，确保被关闭目标没有隐藏贡献，最佳努力放松贡献单独保留。
- [X] T010 [P] 在 `frontend/src/types/scheduler.ts` 补充可选 `objective_modeling_gates`、目标评价状态和资源组织诊断状态类型。

**检查点**：目标门控元数据、共享支持数据判断和空诊断已可供后续资源目标、控制链目标、前端展示复用。

---

## Phase 3：用户故事 1 - 禁用指标不再拖慢精排（优先级：P1）

**目标**：关闭目标项后，不再构建对应 CP-SAT 优化模型。

**独立测试**：只启用 `control_node_late`，运行固定资源精排，关闭的资源类目标不产生路径节点、转移弧、资源组织罚分和已评价结果。

### 用户故事 1 的测试

- [X] T011 [US1] 在 `backend/tests/test_scheduler.py` 增加“只启用 `control_node_late` 时资源路径连续性不建模”的测试，断言路径节点数和转移弧数为 0。
- [X] T012 [US1] 在 `backend/tests/test_scheduler.py` 增加“全部资源类目标关闭时仍保留命名资源互斥”的测试，断言同一资源上的任务不重叠。
- [X] T013 [US1] 在 `backend/tests/test_scheduler.py` 增加“单独关闭 `resource_idle` 或 `resource_workload_balance` 不影响其他启用资源目标”的测试。
- [X] T014 [US1] 在 `backend/tests/test_scheduler.py` 增加“`risk_related_control_wait` 启用但 `control_buffer_risk` 关闭”的共享支持数据测试，断言只保留等待风险所需支持数据，`control_buffer_risk` 不标为已评价。
- [X] T015 [US1] 在 `backend/tests/test_scheduler.py` 增加“`makespan_and_soft_milestone` 关闭”的测试，断言总工期不进入目标贡献，但完工天数和固定工期检查仍保留。

### 用户故事 1 的实现

- [X] T016 [US1] 在 `backend/app/solver.py` 拆分 `_build_resource_organization_terms()` 的资源工作量、资源空闲、资源路径连续性建模分支，分别受目标门控控制。
- [X] T017 [US1] 在 `backend/app/solver.py` 调整 `_build_resource_path_continuity_terms()` 调用路径，`resource_path_continuity` 关闭时不创建路径节点、转移弧和 `Circuit` 约束。
- [X] T018 [US1] 在 `backend/app/solver.py` 拆分 `_build_control_buffer_terms()`、`_build_control_wait_term_details()` 和 `_risk_related_control_wait_terms()` 的共享支持数据与目标罚分构造，避免关闭项被当作已评价目标。
- [X] T019 [US1] 在 `backend/app/solver.py` 拆分总工期基础跨度计算和 `makespan_and_soft_milestone` 目标贡献，关闭该目标时仍保留结果展示和固定工期检查所需跨度。
- [X] T020 [US1] 在 `backend/app/solver.py` 确保资源互斥 `NoOverlap`、同结构同工序、任务前后置、工期和硬里程碑等硬约束不受目标门控影响。

**检查点**：用户故事 1 可独立运行和验证。

---

## Phase 4：用户故事 2 - 启用指标保持原有优化效果（优先级：P1）

**目标**：默认目标配置和启用目标项继续保持既有求解行为与结果解释。

**独立测试**：不传 `objective_terms` 或恢复默认目标配置，7 个当前目标项继续启用；启用的资源目标仍产生对应评价和目标贡献。

### 用户故事 2 的测试

- [X] T021 [US2] 在 `backend/tests/test_scheduler.py` 增加默认目标配置回归测试，断言 7 个当前目标项有效权重和既有默认值一致。
- [X] T022 [US2] 在 `backend/tests/test_scheduler.py` 增加启用 `resource_path_continuity` 时路径连续性仍被评价的测试。
- [X] T023 [US2] 在 `backend/tests/test_scheduler.py` 增加启用 `resource_idle` 和 `resource_workload_balance` 时资源空闲、工作量均衡仍被评价的测试。

### 用户故事 2 的实现

- [X] T024 [US2] 在 `backend/app/models.py` 保持现有 7 个目标项默认配置和兼容过滤规则，不新增目标项 ID，不恢复 `normal_balance`。
- [X] T025 [US2] 在 `backend/app/solver.py` 确保启用目标继续构建原有优化变量、约束、罚分项和结果诊断。
- [X] T026 [US2] 在 `backend/app/solver.py` 确保 `objective_terms_used`、`objective_weights`、`weighted_objective` 对默认配置保持向后兼容。

**检查点**：用户故事 2 可独立运行和验证。

---

## Phase 5：用户故事 3 - 结果解释与异常分支口径一致（优先级：P2）

**目标**：清楚区分未启用、未评价、已评价 0 分、最佳努力目标放松和最少资源候选精排。

**独立测试**：分别运行关闭资源类目标、默认目标、最佳努力分支和最少资源候选精排场景，确认结果来源、目标拆解和诊断状态互不混淆。

### 用户故事 3 的测试

- [X] T027 [US3] 在 `backend/tests/test_scheduler.py` 增加关闭项与已启用 0 罚分的状态区分测试，并断言 `objective_terms_used` 保留禁用项的请求启用状态、请求权重和有效权重 0。
- [X] T028 [US3] 在 `backend/tests/test_scheduler.py` 增加最佳努力放松分支测试，断言 `target_relaxation_penalty` 作为 `best_effort_refinement` 诊断保留，不改写 `control_node_late` 的关闭状态。
- [X] T029 [US3] 在 `backend/tests/test_scheduler.py` 增加最少资源候选精排复用目标门控的测试，断言候选方案不重新构建被关闭目标的专属模型。
- [X] T030 [P] [US3] 在 `frontend/src/types/scheduler.ts` 覆盖目标门控、资源组织诊断和 `best_effort_refinement` 相关字段类型。

### 用户故事 3 的实现

- [X] T031 [US3] 在 `backend/app/solver.py` 将 `objective_modeling_gates` 写入 `stats` 或 `objective_breakdown` 的兼容位置，供前端和测试解释建模门控。
- [X] T032 [US3] 在 `backend/app/solver.py` 调整最佳努力目标放松元数据，确保放松迟延与常规关闭目标项分开展示。
- [X] T033 [US3] 在 `backend/app/scenario.py` 检查固定资源严格精排、最佳努力精排、最少资源候选精排和回退结果的目标门控元数据透传，不覆盖既有 `schedule_source`。
- [X] T034 [US3] 在 `frontend/src/app/App.tsx` 调整结果展示逻辑，关闭项显示未启用或未评价，已启用且罚分为 0 的指标显示已评价无风险。
- [X] T035 [US3] 在 `frontend/src/app/App.tsx` 保持目标函数配置区仍只展示 7 个当前目标项，不新增可配置目标项。

**检查点**：全部用户故事均可独立运行和验证。

---

## Phase 6：收尾与横切事项

**目标**：完成验证、格式检查和工作区隔离确认。

- [X] T036 运行 `.\.venv\Scripts\python.exe -m pytest backend\tests\test_scheduler.py -q`，并按 `specs/008-objective-model-gating/quickstart.md` 对照后端预期。
- [X] T037 运行 `npm --prefix frontend run build`，并按 `specs/008-objective-model-gating/quickstart.md` 对照前端预期。
- [X] T038 在 `specs/008-objective-model-gating/quickstart.md` 复核手工验证步骤，确认导入 Excel 案例、默认配置回归、最佳努力分支和最少资源候选精排场景可复现。
- [X] T039 检查 `git status --short`，确认实施过程未修改 `specs/007-objective-metric-config/` 或切换 `.specify/feature.json` 到 008。

---

## 依赖与执行顺序

### 阶段依赖

- **Phase 1**：无依赖，可立即开始。
- **Phase 2**：依赖 Phase 1 完成，阻塞全部用户故事。
- **Phase 3 / US1**：依赖 Phase 2，是 MVP 范围。
- **Phase 4 / US2**：依赖 Phase 2，可与 US1 部分并行，但最终需与 US1 集成验证。
- **Phase 5 / US3**：依赖 Phase 2，可在 US1 后推进，结果展示依赖后端元数据稳定。
- **Phase 6**：依赖所有用户故事完成。

### 并行机会

- T003、T004、T005 可并行阅读不同文件。
- T010 可与 T006、T007、T008、T009 并行准备类型。
- T030 可与 T027、T028、T029 并行。
- 后端测试编写任务集中在同一文件，默认顺序执行以减少冲突。

## MVP 范围

MVP 为 Phase 1、Phase 2、Phase 3：只要能证明关闭资源类目标、控制链风险目标和总工期目标时不再构建对应专属模型，同时硬约束和必要基础结果仍保留，就能验证本需求的核心价值。

## 实施策略

1. 先完成后端门控和 US1 测试，让“不建模”可被诊断字段证明。
2. 再补默认行为回归，防止默认综合精排退化。
3. 最后完善前端状态展示、最佳努力分支和最少资源候选精排口径。
4. 每个故事完成后先运行对应后端测试，再进入下一故事。

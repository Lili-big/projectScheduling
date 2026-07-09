# 任务清单：resource_path_continuity 候选路径无窗口化

**输入**：来自 `/specs/021-resource-path-unbounded/` 的设计文档

**前置条件**：`plan.md`、`spec.md`、`research.md`、`data-model.md`、`contracts/resource-path-unbounded-contract.md`、`quickstart.md`

**测试要求**：本变更涉及排程算法、资源路径目标、CP-SAT 候选弧和诊断语义，必须包含后端自动化测试和可复现验证任务。

## Phase 1：准备（共享基础）

**目标**：确认当前工作区和既有窗口实现，避免覆盖无关改动。

- [X] T001 检查当前 git 状态并记录与本功能无关的既有改动：`D:\codex_workspace\排程算法`
- [X] T002 [P] 复核机械钻资源类型和钻机组聚合逻辑：`backend/app/solver.py`
- [X] T003 [P] 复核旧窗口规格和本次覆盖关系：`specs/017-stage1-route-continuity/spec.md`
- [X] T004 [P] 复核当前窗口相关测试断言：`backend/tests/test_scheduler.py`

---

## Phase 2：基础能力（阻塞前置）

**目标**：先建立可失败的测试口径，再改求解逻辑。

- [X] T005 在 `backend/tests/test_scheduler.py` 更新 `test_drill_group_stage1_same_side_uses_buildable_sequence_distance`，断言 `1# -> 7#` 被允许且顺序罚分为 0
- [X] T006 在 `backend/tests/test_scheduler.py` 更新 `test_drill_group_stage1_cross_side_uses_real_support_gap`，断言远距离跨幅被允许且顺序罚分为 0
- [X] T007 在 `backend/tests/test_scheduler.py` 更新窗口诊断测试，断言远距离有效转移不增加 `same_side_window_exceeded` 或 `cross_side_gap_exceeded`
- [X] T008 在 `backend/tests/test_scheduler.py` 将旧“窗口不可行不添加远距离兜底”测试改为“无窗口后不再因窗口不可行失败”

**检查点**：测试已表达新目标，当前实现应出现预期失败或断言不匹配。

---

## Phase 3：用户故事 1 - 保留机械桩基钻机组节点（优先级：P1）

**目标**：确保移除路径窗口时不破坏同结构物多桩聚合。

**独立测试**：运行机械钻机组聚合相关测试，确认组数、组内任务和最终任务 ID 不变。

### 用户故事 1 的测试

- [X] T009 [P] [US1] 在 `backend/tests/test_scheduler.py` 增加或强化旋挖、冲击、回旋三类机械桩基聚合测试
- [X] T010 [P] [US1] 在 `backend/tests/test_scheduler.py` 保留最终结果不输出 `drill_group:` 虚拟任务 ID 的断言

### 用户故事 1 的实现

- [X] T011 [US1] 在 `backend/app/solver.py` 确认 `_build_drill_group_nodes()` 不被本次窗口移除改动改变
- [X] T012 [US1] 在 `backend/app/solver.py` 保持 `_add_drill_group_contiguity_constraints()` 对组内桩基连续施工的约束不变

**检查点**：用户故事 1 可独立验证，机械桩基聚合不变量保持。

---

## Phase 4：用户故事 2 - 移除候选路径窗口硬过滤（优先级：P1）

**目标**：让同范围机械钻机组有序对全部进入候选路径，距离只进入诊断，不进入顺序罚分。

**独立测试**：运行同幅、跨幅和候选弧计数测试，验证远距离转移允许且顺序罚分为 0。

### 用户故事 2 的测试

- [X] T013 [P] [US2] 在 `backend/tests/test_scheduler.py` 增加 4 个同幅节点候选弧数为 12 的断言
- [X] T014 [P] [US2] 在 `backend/tests/test_scheduler.py` 增加左右幅 12 个节点候选弧数为 132 的断言

### 用户故事 2 的实现

- [X] T015 [US2] 在 `backend/app/solver.py` 修改 `_drill_group_stage1_transition_decision()`，移除同幅 `MECHANICAL_DRILL_PATH_SUPPORT_WINDOW` 允许条件
- [X] T016 [US2] 在 `backend/app/solver.py` 修改 `_drill_group_stage1_transition_decision()`，移除跨幅 `MECHANICAL_DRILL_CROSS_SIDE_SUPPORT_WINDOW` 允许条件
- [X] T017 [US2] 在 `backend/app/solver.py` 将同幅任意正序列距离保留为诊断，并将顺序罚分归零
- [X] T018 [US2] 在 `backend/app/solver.py` 将跨幅任意有效墩号差保留为诊断，并将顺序罚分归零
- [X] T019 [US2] 在 `backend/app/solver.py` 确保 `_build_drill_group_stage1_route_terms()` 不再因距离窗口跳过候选弧

**检查点**：用户故事 2 可独立验证，远距离候选弧进入模型且顺序罚分为 0。

---

## Phase 5：用户故事 3 - 诊断说明窗口已移除（优先级：P2）

**目标**：让结果诊断不再暗示窗口仍是硬约束，并保持旧字段兼容。

**独立测试**：运行诊断测试，确认候选模式、候选弧数量、拒绝计数、失败原因和目标关闭行为符合新语义。

### 用户故事 3 的测试

- [X] T020 [P] [US3] 在 `backend/tests/test_scheduler.py` 增加或更新 `stage1_route_candidate_mode` 或等价无窗口诊断断言
- [X] T021 [P] [US3] 在 `backend/tests/test_scheduler.py` 更新目标关闭场景，确认 `not_enabled` 和 0 罚分语义不变

### 用户故事 3 的实现

- [X] T022 [US3] 在 `backend/app/solver.py` 更新 `_empty_drill_group_stage1_route_terms()` 的默认诊断，兼容旧窗口字段并标明无窗口模式
- [X] T023 [US3] 在 `backend/app/solver.py` 移除或改写仅由窗口导致的 `stage1_route_window_infeasible` 失败语义
- [X] T024 [US3] 在 `backend/app/solver.py` 审计 `_resource_path_transition_candidate_allowed()` 是否影响机械钻机组主流程，必要时同步或记录不适用边界
- [X] T025 [US3] 审计 `frontend/src/types/scheduler.ts` 的诊断字段类型；需要类型对齐时补充可选字段，不需要时在实现说明中记录无改动原因
- [X] T026 [US3] 审计 `frontend/src/app/App.tsx` 的诊断展示文案；仍描述窗口拒绝时调整为无窗口语义，不需要时在实现说明中记录无改动原因

**检查点**：用户故事 3 可独立验证，诊断语义与无窗口候选路径一致。

---

## Phase 6：收尾与横切事项

**目标**：完成回归验证和风险记录。

- [X] T027 运行 `.\.venv\Scripts\python.exe -m pytest backend\tests\test_scheduler.py -k "stage1_route or mechanical_drill"` 并记录结果：`specs/021-resource-path-unbounded/quickstart.md`
- [X] T028 运行 `.\.venv\Scripts\python.exe -m pytest backend\tests\test_scheduler.py` 并记录结果：`specs/021-resource-path-unbounded/quickstart.md`
- [X] T029 如 T025 或 T026 修改前端，运行 `npm.cmd run build --prefix frontend`；如未修改前端，在实现说明中记录跳过原因：`frontend/src`
- [X] T030 运行 Excel 固定资源案例或记录无法运行原因，比较开启 `resource_path_continuity` 后是否不再出现窗口不可行或明显劣化结果：`backend/scripts/run_excel_case_solve.py`
- [X] T031 检查 `specs/021-resource-path-unbounded/` 与实现结果是否一致，准备后续 `$speckit-converge`

---

## 依赖与执行顺序

### 阶段依赖

- **准备（Phase 1）**：无依赖，可立即开始。
- **基础能力（Phase 2）**：依赖准备阶段完成，阻塞所有用户故事。
- **用户故事 1（Phase 3）**：依赖基础能力完成，应先验证聚合不变量。
- **用户故事 2（Phase 4）**：依赖基础能力完成，是核心算法改动。
- **用户故事 3（Phase 5）**：依赖用户故事 2 的诊断语义，可与前端类型审计小范围并行。
- **收尾（Phase 6）**：依赖目标用户故事完成。

### 用户故事依赖

- **用户故事 1（P1）**：基础能力完成后即可开始，不依赖其他故事。
- **用户故事 2（P1）**：基础能力完成后即可开始；实现时必须不破坏 US1。
- **用户故事 3（P2）**：依赖 US2 的候选和无顺序罚分语义。

### 并行机会

- T002、T003、T004 可并行复核不同文件。
- T009、T010 可并行编写聚合测试。
- T013、T014 可并行补充候选弧计数测试。
- T020、T021 可并行补充诊断和目标关闭测试。
- T025、T026 仅当前端需要变更时可在后端诊断字段稳定后并行处理。

## 实施策略

### MVP 优先

1. 完成 Phase 1 和 Phase 2。
2. 完成用户故事 1，确认机械桩基聚合不变量。
3. 完成用户故事 2，交付无窗口候选路径和顺序罚分归零。
4. 运行相关后端测试后再进入诊断和前端小范围对齐。

### 增量交付

1. 先保聚合，再移除窗口，再清理诊断。
2. 每个用户故事完成后运行对应测试子集。
3. 完成后执行完整后端回归；前端仅在类型或展示变更时构建验证。

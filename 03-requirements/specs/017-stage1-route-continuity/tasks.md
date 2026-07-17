# 任务清单：第一阶段钻机组路径连续性优化

> 当前实现校正（2026-07-09）：`resource_path_continuity` 已从当前目标项体系中移除；旧输入字段仅作为废弃兼容字段被忽略。当前目标项为 `control_node_late`、`makespan_and_soft_milestone`、`resource_idle`。第一阶段路径连续性、无窗口候选路径和资源路径罚分均为历史设计，不再建路径 circuit 或产生路径罚分；机械钻组聚合、组内升序和同组同资源保留为基础规则。

**输入**：来自 `specs/017-stage1-route-continuity/` 的设计文档

**前置条件**：`plan.md`、`spec.md`、`research.md`、`data-model.md`、`contracts/stage1-route-continuity-contract.md`、`quickstart.md`

**测试要求**：本功能涉及 CP-SAT 目标项、候选路径边界、失败语义和诊断契约，必须先补充后端回归测试，再实现求解器变更；如前端展示诊断字段，则补充前端构建验证。

**组织方式**：任务按用户故事分组，确保每个故事可独立实现和验证。

## Phase 1：准备

**目标**：确认现有钻机组两阶段精排触点和测试夹具，避免覆盖无关改动。

- [X] T001 检查当前 git 状态并记录既有未提交改动范围
- [X] T002 [P] 复核 `backend/app/solver.py` 中 `_build_drill_group_nodes`、`_build_drill_group_coarse_jump_terms`、`solve_control_priority_schedule` 的第一阶段调用路径
- [X] T003 [P] 复核 `backend/tests/test_scheduler.py` 中现有 `resource_path_continuity`、`drill_group_refinement`、`stage2` 测试夹具
- [X] T004 [P] 复核 `frontend/src/types/scheduler.ts` 与 `frontend/src/app/App.tsx` 中 `drill_group_refinement` 和 `continuity_objective` 的可选字段解析

---

## Phase 2：基础能力（阻塞前置）

**目标**：建立第一阶段空间路径规则的纯计算辅助能力和诊断契约。

- [X] T005 [P] 在 `backend/tests/test_scheduler.py` 增加同幅可施工序列距离辅助测试，覆盖 `[1, 2, 4, 7]` 的序号距离
- [X] T006 [P] 在 `backend/tests/test_scheduler.py` 增加跨幅真实墩号差辅助测试，覆盖墩号差 `0`、`1`、`3`
- [X] T007 在 `backend/app/solver.py` 增加第一阶段可施工序列构建辅助函数，按桥梁、工艺、幅别和资源候选范围排序钻机组
- [X] T008 在 `backend/app/solver.py` 增加第一阶段候选转移判定辅助函数，输出允许状态、惩罚和拒绝原因
- [X] T009 在 `backend/app/solver.py` 增加第一阶段路径诊断汇总结构，字段对齐 `contracts/stage1-route-continuity-contract.md`

**检查点**：可施工序列、候选转移和诊断字段可以脱离完整求解独立验证。

---

## Phase 3：用户故事 1 - 第一阶段按空间窗口选择钻机组路径（优先级：P1）

**目标**：资源连续性开启时，第一阶段粗排直接使用空间窗口内的钻机组路径候选。

**独立测试**：构造左右幅多墩组场景，验证第一阶段候选弧只包含允许窗口内的转移。

### 用户故事 1 的测试

- [X] T010 [P] [US1] 在 `backend/tests/test_scheduler.py` 增加第一阶段不生成同幅超窗口候选弧的测试
- [X] T011 [P] [US1] 在 `backend/tests/test_scheduler.py` 增加第一阶段不生成跨幅超窗口候选弧的测试
- [X] T012 [P] [US1] 在 `backend/tests/test_scheduler.py` 增加第一阶段候选弧数和诊断节点数断言

### 用户故事 1 的实现

- [X] T013 [US1] 在 `backend/app/solver.py` 将第一阶段粗排从相邻换机/洞洞跳墩惩罚调整为路径候选选择模型
- [X] T014 [US1] 在 `backend/app/solver.py` 将第一阶段候选路径惩罚并入 `resource_path_continuity` 目标项
- [X] T015 [US1] 在 `backend/app/solver.py` 保持第一阶段组内连续、资源互斥、工艺前后置和硬里程碑约束不变
- [X] T016 [US1] 在 `backend/app/solver.py` 将第一阶段空间路径诊断写入 `drill_group_refinement` 和必要的 `continuity_objective` 摘要

**检查点**：用户故事 1 可独立运行和验证，第一阶段已按空间窗口选择路径。

---

## Phase 4：用户故事 2 - 同幅惩罚按可施工序列距离计算（优先级：P1）

**目标**：稀疏可施工任务范围中，相邻可施工节点不罚，跳过一个可施工节点罚 1。

**独立测试**：使用 `[1, 2, 4, 7]` 场景验证同幅距离和罚分。

### 用户故事 2 的测试

- [X] T017 [P] [US2] 在 `backend/tests/test_scheduler.py` 增加 `1# -> 2#` 和 `4# -> 7#` 同幅惩罚为 0 的测试
- [X] T018 [P] [US2] 在 `backend/tests/test_scheduler.py` 增加 `1# -> 4#` 同幅惩罚为 1 的测试
- [X] T019 [P] [US2] 在 `backend/tests/test_scheduler.py` 增加 `1# -> 7#` 同幅序列距离为 3 且不生成候选弧的测试

### 用户故事 2 的实现

- [X] T020 [US2] 在 `backend/app/solver.py` 使用可施工序列位置差替代自然墩号差计算同幅窗口距离
- [X] T021 [US2] 在 `backend/app/solver.py` 实现同幅惩罚公式 `max(0, 可施工序列距离 - 1)`
- [X] T022 [US2] 在 `backend/app/solver.py` 将同幅窗口超限计入 `stage1_route_rejected_arc_counts.same_side_window_exceeded`

**检查点**：用户故事 2 可独立验证，稀疏同幅序列连续性口径正确。

---

## Phase 5：用户故事 3 - 不为硬里程碑放开远距离跳转（优先级：P1）

**目标**：窗口规则是严格边界，当前资源无法在窗口内满足时返回可解释失败或资源建议。

**独立测试**：构造只有远距离跳转才能满足硬里程碑的场景，验证系统不生成远距离兜底弧。

### 用户故事 3 的测试

- [X] T023 [P] [US3] 在 `backend/tests/test_scheduler.py` 增加硬里程碑压力下仍不生成远距离候选弧的测试
- [X] T024 [P] [US3] 在 `backend/tests/test_scheduler.py` 增加窗口导致不可行时返回失败语义或资源建议元数据的测试
- [X] T025 [P] [US3] 在 `backend/tests/test_scheduler.py` 增加第二阶段不得重新引入第一阶段禁止远跳路径的回归测试

### 用户故事 3 的实现

- [X] T026 [US3] 在 `backend/app/solver.py` 移除或替换第一阶段远距离兜底候选逻辑，确保窗口外转移不进入模型
- [X] T027 [US3] 在 `backend/app/solver.py` 为窗口不可行设置 `stage1_route_status = infeasible` 和明确失败原因
- [X] T028 [US3] 在 `backend/app/scenario.py` 复核当前资源失败和最少资源候选精排路径，确保失败语义不被成功标签掩盖

**检查点**：全部 P1 用户故事可独立运行和验证。

---

## Phase 6：用户故事 4 - 阶段诊断说明候选窗口和惩罚（优先级：P2）

**目标**：结果中能解释第一阶段路径节点、候选弧、拒绝原因和惩罚。

**独立测试**：后端结果包含第一阶段空间路径诊断，前端旧结果兼容。

### 用户故事 4 的测试

- [X] T029 [P] [US4] 在 `backend/tests/test_scheduler.py` 增加 `stage1_route_node_count`、`stage1_route_candidate_arc_count`、`stage1_route_rejected_arc_counts` 输出断言
- [X] T030 [P] [US4] 在 `backend/tests/test_scheduler.py` 增加目标关闭时诊断为 `not_enabled` 或未评估的断言
- [X] T031 [P] [US4] 如修改前端类型，在 `frontend/src/types/scheduler.ts` 和 `frontend/src/app/App.tsx` 变更后运行构建验证

### 用户故事 4 的实现

- [X] T032 [US4] 在 `backend/app/solver.py` 将第一阶段诊断同步到 `stats` 和 `objective_breakdown`
- [X] T033 [US4] 在 `frontend/src/types/scheduler.ts` 按需增加可选诊断字段类型，保持旧结果兼容
- [X] T034 [US4] 在 `frontend/src/app/App.tsx` 按需展示第一阶段路径窗口诊断，不改变目标项配置入口

**检查点**：用户可解释第一阶段路径窗口和拒绝原因，旧结果展示不报错。

---

## Phase 7：收尾与横切事项

**目标**：完成跨分支一致性、Netlify 检查和回归验证。

- [X] T035 [P] 检查 `netlify/functions/api.mts` 是否存在需要同步的钻机组资源连续性演示逻辑，并记录处理结论
- [X] T036 [P] 复核 `docs/固定资源满足分支详细排程算法文档_v1.6.md` 和 `docs/精排目标函数算法需求文档_v4.0.md` 是否需要后续 PRD 更新，不在本实现任务中默认修改
- [X] T037 运行 `python -m pytest backend/tests/test_scheduler.py` 验证后端排程回归
- [X] T038 如前端文件变更，运行 `npm.cmd run build --prefix frontend` 验证类型和构建
- [X] T039 按 `specs/017-stage1-route-continuity/quickstart.md` 复核稀疏同幅、跨幅窗口、无远跳兜底、目标关闭和回归场景
- [X] T040 检查实现后的 git 状态，确认未覆盖进入任务前已有的无关改动

---

## 依赖与执行顺序

### 阶段依赖

- **Phase 1**：无依赖，可立即开始。
- **Phase 2**：依赖 Phase 1，阻塞所有用户故事。
- **Phase 3 / US1**：依赖 Phase 2，是 MVP 核心。
- **Phase 4 / US2**：依赖 Phase 2，可与 US1 测试设计并行，但实现需和候选转移基础函数一致。
- **Phase 5 / US3**：依赖 Phase 2 和 US1 的候选模型，锁定失败边界。
- **Phase 6 / US4**：依赖后端诊断字段稳定。
- **Phase 7**：依赖目标用户故事完成。

### 用户故事依赖

- **US1**：交付第一阶段空间路径候选模型。
- **US2**：交付同幅可施工序列距离和惩罚口径。
- **US3**：交付无远距离兜底的失败边界。
- **US4**：交付诊断解释和兼容展示。

### 并行机会

- T002、T003、T004 可并行读取不同区域。
- T005、T006、T009 可并行。
- T010、T011、T017、T018、T019、T023、T029、T030 可在测试设计阶段并行，但实现前需统一测试夹具。
- T033 可在后端契约确定后与 T034 准备并行。
- T035、T036 可与最终验证准备并行。

## 实施策略

### MVP 优先

1. 完成 Phase 1 和 Phase 2。
2. 完成 US1，证明第一阶段已按空间窗口建候选路径。
3. 完成 US2，证明稀疏同幅序列惩罚正确。
4. 完成 US3，证明不允许远距离兜底。
5. 最后完成 US4 和收尾验证。

### 验证策略

- 后端先用纯规则测试锁住可施工序列和候选转移，再接入 CP-SAT 模型。
- 每个 P1 故事都必须有可复现场景。
- 目标关闭、当前资源失败、最少资源候选精排都必须保持可解释口径。
## 2026-07-08 补充任务：第一阶段最终排程

- [X] T041 在 `backend/app/solver.py` 将机械钻机组内桩基排序调整为优先按桩基序号升序，缺失桩号时回退现有排序。
- [X] T042 在 `backend/app/solver.py` 将自动钻机组流程调整为第一阶段可行后直接返回，不再进入第二阶段 `refined` 排程。
- [X] T043 在 `backend/tests/test_scheduler.py` 更新钻机组回归测试，覆盖第一阶段最终状态、跳过第二阶段和组内桩号升序。
- [X] T044 在 `frontend/src/types/scheduler.ts` 与 `frontend/src/app/App.tsx` 增加 `stage1_final` 展示兼容。

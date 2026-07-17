# 任务清单：现浇连续梁联级班组占用

**输入**：来自 `specs/016-continuous-beam-team-span/` 的设计文档

**前置条件**：`plan.md`、`spec.md`、`research.md`、`data-model.md`、`contracts/continuous-beam-team-span-contract.md`、`quickstart.md`

**测试要求**：本功能涉及 CP-SAT 资源约束、排程结果契约和前端类型兼容，必须先补充后端回归测试，再实现约束和展示。

**组织方式**：任务按用户故事分组，确保每个故事可独立实现和验证。

## Phase 1：准备

**目标**：确认现有连续梁、资源和展示触点，避免覆盖无关改动。

- [X] T001 检查当前 git 状态并记录既有未提交改动范围，重点确认 `frontend/src/app/App.tsx`、`frontend/src/styles.css` 中是否有用户改动
- [X] T002 [P] 复核连续梁任务生成逻辑和测试夹具，定位 `backend/app/scenario.py` 与 `backend/tests/test_scheduler.py` 中可复用的连续梁场景
- [X] T003 [P] 复核求解器命名资源互斥、容量求解和结果构造触点，定位 `backend/app/solver.py` 中需要保持一致语义的求解分支
- [X] T004 [P] 复核前端连续梁父级分组和资源展示触点，定位 `frontend/src/types/scheduler.ts` 与 `frontend/src/app/App.tsx` 的兼容入口

---

## Phase 2：基础能力（阻塞前置）

**目标**：建立所有用户故事共享的联识别、结果契约和测试基础。

- [X] T005 [P] 在 `backend/tests/test_scheduler.py` 增加连续梁联识别辅助断言，覆盖 `bridge_id + work_section_id + group_index` 区分左幅和右幅
- [X] T006 [P] 在 `backend/tests/test_scheduler.py` 增加连续梁联级资源结果辅助断言，检查联级占用窗口、班组归属和联内任务集合
- [X] T007 在 `backend/app/models.py` 扩展排程结果契约，支持连续梁联级班组占用摘要和任务所属联追溯字段
- [X] T008 在 `frontend/src/types/scheduler.ts` 对齐连续梁联级班组占用结果类型，保持旧结果字段可选兼容
- [X] T009 在 `backend/app/scenario.py` 为生成的连续梁任务补齐稳定的联级追溯属性，确保 `resource_neutral` 任务也能归入所属联
- [X] T010 在 `backend/app/solver.py` 增加连续梁联识别与诊断构建基础函数，遇到缺少关键字段的连续梁任务时输出可解释诊断

**检查点**：基础字段、联识别和测试辅助能力就绪，可开始用户故事实现。

---

## Phase 3：用户故事 1 - 一个班组按联串行施工（优先级：P1）

**目标**：`cast_in_place_continuous_beam_team.quantity = 1` 时，左幅、右幅或多联连续梁只能跨联串行占用同一班组。

**独立测试**：使用左右幅各一联且均具备施工条件的场景，验证联级占用窗口不重叠。

### 用户故事 1 的测试

- [X] T011 [P] [US1] 在 `backend/tests/test_scheduler.py` 增加 `quantity = 1` 时左右幅连续梁联级占用不得重叠的测试
- [X] T012 [P] [US1] 在 `backend/tests/test_scheduler.py` 增加 3 个连续梁联且 `quantity = 1` 时任意时刻最多 1 个联占用班组的测试

### 用户故事 1 的实现

- [X] T013 [US1] 在 `backend/app/solver.py` 为命名资源精排分支建立连续梁联级占用变量和班组选择变量
- [X] T014 [US1] 在 `backend/app/solver.py` 对同一连续梁班组的联级占用窗口添加跨联互斥约束
- [X] T015 [US1] 在 `backend/app/solver.py` 从连续梁任务级资源互斥中排除由联级占用接管的连续梁班组任务
- [X] T016 [US1] 在 `backend/app/solver.py` 构造 `ScheduleResult.stats.continuous_beam_team_spans`，输出 `quantity = 1` 场景的联级占用摘要

**检查点**：用户故事 1 可独立运行和验证，1 个连续梁班组不会跨联并行。

---

## Phase 4：用户故事 2 - 两个班组允许两联并行（优先级：P1）

**目标**：`cast_in_place_continuous_beam_team.quantity = 2` 时，最多两个连续梁联可并行施工，并分别归属不同班组。

**独立测试**：将同一场景的班组数量从 1 调整到 2，验证左右幅可并行且并行联数不超过 2。

### 用户故事 2 的测试

- [X] T017 [P] [US2] 在 `backend/tests/test_scheduler.py` 增加 `quantity = 2` 时左右幅连续梁联可并行且归属不同班组的测试
- [X] T018 [P] [US2] 在 `backend/tests/test_scheduler.py` 增加 3 个连续梁联且 `quantity = 2` 时任意时刻最多 2 个联占用班组的测试

### 用户故事 2 的实现

- [X] T019 [US2] 在 `backend/app/solver.py` 将连续梁联级占用约束接入容量求解分支，使最少资源和资源成本分支沿用联级数量语义
- [X] T020 [US2] 在 `backend/app/solver.py` 确保连续梁班组 `max_quantity` 在资源建议分支中表示可并行连续梁联上限
- [X] T021 [US2] 在 `backend/tests/test_scheduler.py` 补充固定资源结果与资源建议结果中连续梁联级占用摘要一致性的断言

**检查点**：用户故事 1 和 2 均可独立验证，连续梁班组数量语义在当前资源和增配分支中一致。

---

## Phase 5：用户故事 3 - 同一联内任务不因班组互斥被串行化（优先级：P1）

**目标**：同一连续梁联内任务继续按既有工艺约束排程，不因属于同一连续梁班组而被任务级互斥。

**独立测试**：验证同一联内左右悬臂标准段仍同步，且无任务级班组互斥造成的额外错开。

### 用户故事 3 的测试

- [X] T022 [P] [US3] 在 `backend/tests/test_scheduler.py` 增加同一联内左右标准段仍同步且不因班组互斥错开的测试
- [X] T023 [P] [US3] 在 `backend/tests/test_scheduler.py` 增加联内 `resource_neutral` 连续梁任务仍纳入联级占用但不生成任务级资源互斥的测试

### 用户故事 3 的实现

- [X] T024 [US3] 在 `backend/app/solver.py` 调整连续梁任务的资源分配结果构造，避免联内任务被误标为任务级班组占用
- [X] T025 [US3] 在 `backend/app/solver.py` 保留 `_add_continuous_beam_v18_constraints` 的同步和合龙间隔约束，并补充与联级资源规则的组合调用
- [X] T026 [US3] 在 `backend/tests/test_scheduler.py` 更新或新增回归断言，确保旧有连续梁生成、下部锚固、合龙间隔测试仍通过

**检查点**：全部 P1 用户故事可独立运行和验证。

---

## Phase 6：用户故事 4 - 结果可解释为联级班组组织（优先级：P2）

**目标**：用户能从结果中理解每个连续梁联由哪个班组负责，以及跨联等待来自班组占用而非联内资源缺失。

**独立测试**：后端结果包含联级占用摘要，前端类型和展示兼容旧结果与新结果。

### 用户故事 4 的测试

- [X] T027 [P] [US4] 在 `backend/tests/test_scheduler.py` 增加 `continuous_beam_team_spans` 输出字段、任务所属联追溯和诊断信息的断言
- [X] T028 [P] [US4] 在 `frontend/src/types/scheduler.ts` 与 `frontend/src/app/App.tsx` 变更后运行前端构建验证类型兼容

### 用户故事 4 的实现

- [X] T029 [US4] 在 `frontend/src/types/scheduler.ts` 增加连续梁联级占用摘要类型，字段保持可选以兼容旧结果
- [X] T030 [US4] 在 `frontend/src/app/App.tsx` 解析 `continuous_beam_team_spans` 并在资源组织或诊断区域展示连续梁联级班组归属
- [X] T031 [US4] 在 `frontend/src/app/App.tsx` 调整连续梁任务资源展示口径，当任务无任务级连续梁班组时优先展示所属联级班组信息

**检查点**：用户能解释连续梁联级班组组织，旧结果展示不报错。

---

## Phase 7：收尾与横切事项

**目标**：完成跨分支一致性检查、Netlify 检查和整体验证。

- [X] T032 [P] 检查 `netlify/functions/api.mts` 是否存在需要同步的连续梁资源求解或展示逻辑，并在必要时补齐同等语义
- [X] T033 [P] 复核 `docs/资源配置页面需求文档_v1.0.md` 或相关算法文档是否需要后续 PRD 更新，不在本实现任务中默认修改
- [X] T034 运行 `python -m pytest backend/tests/test_scheduler.py` 验证后端排程回归
- [X] T035 运行 `npm.cmd run build --prefix frontend` 验证前端类型和构建
- [X] T036 按 `specs/016-continuous-beam-team-span/quickstart.md` 复核 1 个班组、2 个班组、联内不互斥和旧结果兼容场景
- [X] T037 检查实现后的 git 状态，确认未覆盖进入任务前已有的无关前端改动

---

## 依赖与执行顺序

### 阶段依赖

- **Phase 1**：无依赖，可立即开始。
- **Phase 2**：依赖 Phase 1，阻塞所有用户故事。
- **Phase 3 / US1**：依赖 Phase 2，是 MVP 核心。
- **Phase 4 / US2**：依赖 Phase 2，可与 US1 的部分测试设计并行，但实现应在联级占用基础能力稳定后进行。
- **Phase 5 / US3**：依赖 Phase 2，可与 US1/US2 测试设计并行，最终需和联级互斥实现集成。
- **Phase 6 / US4**：依赖后端输出契约稳定。
- **Phase 7**：依赖目标用户故事完成。

### 用户故事依赖

- **US1**：基础能力完成后即可实施，交付 1 个班组跨联串行。
- **US2**：依赖联级占用基础，交付多个班组跨联并行语义。
- **US3**：依赖联级占用基础，交付联内不任务级互斥。
- **US4**：依赖后端结果契约，交付前端解释能力。

### 并行机会

- T002、T003、T004 可并行读取不同区域。
- T005、T006、T008 可并行。
- T011、T012、T017、T018、T022、T023、T027 可在测试设计阶段并行，但实现前需统一测试夹具。
- T029 可在后端契约确定后与 T030/T031 前置准备并行。
- T032、T033 可与最终验证准备并行。

## 实施策略

### MVP 优先

1. 完成 Phase 1 和 Phase 2。
2. 完成 US1，证明 `quantity = 1` 时跨联串行。
3. 完成 US3，证明联内任务不被任务级互斥压成串行。
4. 再完成 US2，把 `quantity = 2` 和资源建议分支统一。
5. 最后完成 US4 和收尾验证。

### 验证策略

- 后端先用可复现场景锁住资源语义，再修改求解器。
- 前端只在后端输出契约稳定后接入展示。
- 所有验证必须说明固定资源主结果、最少资源分支和旧结果兼容状态。


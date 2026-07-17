# 任务清单：固定资源方案2输出提示

**输入**：来自 `specs/020-fixed-resource-plan2-output/` 的设计文档。

**前置条件**：`plan.md`、`spec.md`、`research.md`、`data-model.md`、`contracts/fixed-resource-result-output-contract.md`、`quickstart.md`。

**测试要求**：本功能涉及排程结果契约、资源建议状态和前端展示口径，必须包含后端回归测试和前端构建验证。

**组织方式**：任务按用户故事分组，确保每个故事都可独立实现和验证。

## Phase 1：准备（共享基础）

**目标**：确认当前工作区和受影响文件，避免覆盖用户已有改动。

- [x] T001 检查当前 git 状态并记录既有改动范围，重点确认 `frontend/src/app/App.tsx`、`frontend/src/styles.css` 是否已有用户改动
- [x] T002 阅读固定资源主流程与资源建议返回路径：`backend/app/scenario.py`
- [x] T003 [P] 阅读结果模型和前端结果类型：`backend/app/models.py`、`frontend/src/types/scheduler.ts`
- [x] T004 [P] 阅读前端方案输出与诊断展示路径：`frontend/src/app/App.tsx`

---

## Phase 2：基础能力（阻塞前置）

**目标**：建立所有用户故事共享的方案输出状态契约和后端元数据写入基础。

- [x] T005 在 `backend/tests/test_scheduler.py` 增加方案输出状态公共断言 helper，覆盖 `alternative_output_status`、`alternative_output_reason`、`alternative_output_message`
- [x] T006 在 `backend/app/scenario.py` 增加固定资源方案输出状态元数据构造 helper，对齐 `contracts/fixed-resource-result-output-contract.md`
- [x] T007 在 `backend/app/scenario.py` 将方案输出状态同时写入 `ScheduleResult.stats` 与 `objective_breakdown`
- [x] T008 在 `frontend/src/app/App.tsx` 增加读取方案输出状态的轻量解析 helper，兼容旧结果缺失字段

**检查点**：共享状态字段和解析逻辑就绪，但尚未改变各业务分支行为。

---

## Phase 3：用户故事 1 - 当前资源目标失败仍保留方案1（优先级：P1）

**目标**：当前资源可查看但强制里程碑未满足时，固定资源结果仍以方案1输出，并保留任务、资源和里程碑迟延。

**独立测试**：运行当前资源目标失败场景，验证主结果可查看、`alternative_output_status` 正确、方案1不被资源建议失败覆盖。

### 用户故事 1 的测试

- [x] T009 [P] [US1] 在 `backend/tests/test_scheduler.py` 增加“当前资源可查看但里程碑未满足仍输出方案1”的回归测试
- [x] T010 [P] [US1] 在 `backend/tests/test_scheduler.py` 增加“新增资源失败不得覆盖方案1当前资源状态”的回归测试

### 用户故事 1 的实现

- [x] T011 [US1] 在 `backend/app/scenario.py` 为当前资源目标失败路径设置方案1保留状态和当前资源目标未满足原因
- [x] T012 [US1] 在 `backend/app/scenario.py` 确保当前资源目标失败时保留 `tasks`、`resource_allocations`、`milestone_results` 和 `target_achievement`
- [x] T013 [US1] 在 `frontend/src/app/App.tsx` 确保只有方案1时仍显示当前资源主结果和目标未满足摘要

**检查点**：用户故事 1 可独立证明当前资源结果不会被新增资源分支吞掉。

---

## Phase 4：用户故事 2 - 新增资源成功时输出方案2（优先级：P1）

**目标**：当前资源目标失败后，新增资源分支形成可展示候选时，结果包含方案1和方案2，并可在前端切换查看。

**独立测试**：运行当前资源失败但新增资源可满足目标的场景，验证 `alternative_results` 包含一个候选，方案2状态为已输出。

### 用户故事 2 的测试

- [x] T014 [P] [US2] 在 `backend/tests/test_scheduler.py` 增加“新增资源候选成功时方案2输出状态为 output”的回归测试
- [x] T015 [P] [US2] 在 `backend/tests/test_scheduler.py` 增加“方案2候选有独立资源数量和目标达成信息”的回归测试

### 用户故事 2 的实现

- [x] T016 [US2] 在 `backend/app/scenario.py` 为推荐资源验证成功路径设置 `alternative_output_status=output`
- [x] T017 [US2] 在 `backend/app/scenario.py` 确保方案2成功时 `alternative_results` 与方案输出状态一致
- [x] T018 [US2] 在 `frontend/src/app/App.tsx` 确保方案2存在时保留当前方案切换入口，并正确显示方案2标签和明细

**检查点**：用户故事 2 可独立证明方案2成功时展示稳定，不影响方案1。

---

## Phase 5：用户故事 3 - 新增资源失败时明确提示方案2未输出（优先级：P2）

**目标**：新增资源分支没有可展示候选时，只返回方案1，并向用户明确提示方案2未输出及原因类别。

**独立测试**：运行关键路径不可压缩、资源上限不足、候选复排失败、限时未确认等场景，验证没有空方案2入口且提示明确。

### 用户故事 3 的测试

- [x] T019 [P] [US3] 在 `backend/tests/test_scheduler.py` 增加“关键路径不可压缩时方案2未输出”的回归测试
- [x] T020 [P] [US3] 在 `backend/tests/test_scheduler.py` 增加“资源上限不足时方案2未输出”的回归测试
- [x] T021 [P] [US3] 在 `backend/tests/test_scheduler.py` 增加“候选复排失败时方案2未输出”的回归测试
- [x] T022 [P] [US3] 在 `backend/tests/test_scheduler.py` 增加“求解限时未确认时方案2未输出”的回归测试
- [x] T023 [P] [US3] 在 `backend/tests/test_scheduler.py` 增加“最大资源场景生成失败时方案2未输出”的回归测试

### 用户故事 3 的实现

- [x] T024 [US3] 在 `backend/app/scenario.py` 为资源建议未形成候选的所有返回路径设置 `alternative_output_status=not_output`
- [x] T025 [US3] 在 `backend/app/scenario.py` 为方案2未输出写入用户可见提示和原因类别
- [x] T026 [US3] 在 `frontend/src/app/App.tsx` 当 `alternative_output_status=not_output` 时展示方案2未输出提示，并隐藏空方案2切换入口
- [x] T027 [US3] 在 `frontend/src/app/App.tsx` 确保当前资源已满足、当前资源未确认和物理不可行时不显示方案2未输出提示

**检查点**：用户故事 3 可独立证明“没有方案2”和“当前资源没有结果”不会混淆。

---

## Phase 6：收尾与横切事项

**目标**：完成回归验证、文档同步和门禁检查。

- [x] T028 [P] 按需更新 `docs/排程算法当前实现交底文档_v1.2.md` 中固定资源方案输出和资源建议提示口径
- [x] T029 运行 `.\.venv\Scripts\python.exe -m pytest backend\tests\test_scheduler.py -q -k "fixed_resource"` 并记录结果
- [x] T030 运行 `.\.venv\Scripts\python.exe -m py_compile backend\app\scenario.py backend\tests\test_scheduler.py` 并记录结果
- [x] T031 如修改前端，运行 `npm.cmd run build` 并记录结果
- [x] T032 运行 `git diff --check -- backend\app\scenario.py backend\tests\test_scheduler.py frontend\src\app\App.tsx frontend\src\types\scheduler.ts docs\排程算法当前实现交底文档_v1.2.md`
- [x] T033 检查 `specs/020-fixed-resource-plan2-output/quickstart.md` 的三个验证场景是否已覆盖
- [x] T034 检查 `AGENTS.md` 和 `.specify/memory/constitution.md` 门禁仍满足本功能要求

---

## 依赖与执行顺序

### 阶段依赖

- **Phase 1 准备**：无依赖。
- **Phase 2 基础能力**：依赖 Phase 1，阻塞所有用户故事。
- **US1**：依赖 Phase 2，是 MVP。
- **US2**：依赖 Phase 2，可在 US1 后实现，需保持方案1不变。
- **US3**：依赖 Phase 2，可与 US2 部分并行，但前端展示需兼容方案2成功和未输出两类状态。
- **收尾**：依赖目标用户故事完成。

### 用户故事依赖

- **US1**：核心保底能力，必须先完成。
- **US2**：成功候选输出，依赖共享状态字段。
- **US3**：失败提示输出，依赖共享状态字段和前端解析 helper。

### 并行机会

- T003 与 T004 可并行。
- T009 与 T010 可并行。
- T014 与 T015 可并行。
- T019、T020、T021、T022、T023 可并行。
- T028 可与最终验证前的代码清理并行，但不得提前写入未验证行为。

## 并行示例：用户故事 3

```text
Task: "T019 在 backend/tests/test_scheduler.py 增加关键路径不可压缩时方案2未输出的回归测试"
Task: "T020 在 backend/tests/test_scheduler.py 增加资源上限不足时方案2未输出的回归测试"
Task: "T021 在 backend/tests/test_scheduler.py 增加候选复排失败时方案2未输出的回归测试"
Task: "T022 在 backend/tests/test_scheduler.py 增加求解限时未确认时方案2未输出的回归测试"
Task: "T023 在 backend/tests/test_scheduler.py 增加最大资源场景生成失败时方案2未输出的回归测试"
```

## 实施策略

### MVP 优先

1. 完成 Phase 1 和 Phase 2。
2. 完成 US1，证明当前资源目标失败时方案1稳定保留。
3. 运行 US1 相关后端测试。
4. 再补 US2 的方案2成功输出和 US3 的方案2未输出提示。

### 增量交付

1. 后端先补稳定状态字段并保证旧字段不破坏。
2. 前端以字段可缺失为前提增量展示。
3. 每个用户故事完成后运行对应测试，再进入下一故事。

## 备注

- 不得在用户确认 `$speckit-analyze` 前开始执行这些实现任务。
- 任务实施时必须保护当前工作区已有未提交改动，不得重置或覆盖无关文件。

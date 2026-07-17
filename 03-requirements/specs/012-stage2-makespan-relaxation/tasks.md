# 任务清单：放宽第二阶段工期上限

**输入**：来自 `specs/012-stage2-makespan-relaxation/` 的设计文档

**前置条件**：`plan.md`、`spec.md`、`research.md`、`data-model.md`、`contracts/stage2-makespan-relaxation-contract.md`、`quickstart.md`

**测试要求**：本功能涉及排程算法、CP-SAT 约束、两阶段结果接受规则和诊断契约，必须包含后端回归测试；若前端类型字段调整，需包含前端类型兼容验证。

## Phase 1：准备（共享基础）

**目标**：确认当前第二阶段硬上限、接受规则和诊断输出位置。

- [X] T001 复核第二阶段调用、`_hard_max_makespan_days` 和接受条件位置：`backend/app/solver.py`
- [X] T002 复核两阶段精排现有测试夹具和断言位置：`backend/tests/test_scheduler.py`
- [X] T003 [P] 复核前端调度结果类型对新增可选诊断字段的兼容点：`frontend/src/types/scheduler.ts`

---

## Phase 2：用户故事 1 - 第二阶段可在硬约束内优化路径（优先级：P1）

**目标**：移除第二阶段相对第一阶段总工期的硬限制和接受门槛。

**独立测试**：构造 `M2 > M1` 但硬约束满足的两阶段场景，验证系统接受第二阶段结果。

### 用户故事 1 的测试

- [X] T004 [P] [US1] 在 `backend/tests/test_scheduler.py` 增加第二阶段总工期晚于第一阶段但仍满足硬里程碑时接受 refined 结果的测试
- [X] T005 [P] [US1] 在 `backend/tests/test_scheduler.py` 增加第二阶段硬里程碑迟延时不得作为正常硬约束满足结果接受的测试

### 用户故事 1 的实现

- [X] T006 [US1] 在 `backend/app/solver.py` 移除 refined 阶段传入 `_hard_max_makespan_days=coarse_result.objective_days` 的逻辑
- [X] T007 [US1] 在 `backend/app/solver.py` 移除接受 refined 结果时对 `refined_result.objective_days <= coarse_result.objective_days` 的要求
- [X] T008 [US1] 在 `backend/app/solver.py` 移除单纯 `M2 > M1` 导致 `stage2_makespan_exceeded` 回退的逻辑

**检查点**：第二阶段可因路径连续性优化而晚于第一阶段，但仍必须满足真实硬约束。

---

## Phase 3：用户故事 2 - 总工期目标继续自然约束第二阶段（优先级：P2）

**目标**：确保不新增重复的 `M2 - M1` 求解目标，现有总工期目标继续发挥作用。

**独立测试**：检查目标贡献中不出现独立相对工期目标项，现有总工期项仍可用。

### 用户故事 2 的测试

- [X] T009 [P] [US2] 在 `backend/tests/test_scheduler.py` 增加目标贡献不包含独立 `M2 - M1` 项的断言

### 用户故事 2 的实现

- [X] T010 [US2] 在 `backend/app/solver.py` 保持现有 `makespan_and_soft_milestone` 目标，不新增相对第一阶段工期目标项

**检查点**：总工期目标没有被双重计分。

---

## Phase 4：用户故事 3 - 结果解释展示相对第一阶段差值（优先级：P3）

**目标**：为第二阶段成功结果提供相对第一阶段的工期诊断。

**独立测试**：运行两阶段成功场景，验证诊断包含 `M1`、`M2` 和 `M2 - M1`。

### 用户故事 3 的测试

- [X] T011 [P] [US3] 在 `backend/tests/test_scheduler.py` 增加第二阶段诊断输出 `stage1_makespan_days`、`stage2_makespan_days` 和 `stage2_makespan_delta_days` 的测试
- [X] T012 [P] [US3] 在 `frontend/src/types/scheduler.ts` 相关类型验证中确认新增诊断字段为可选字段或无需类型变更

### 用户故事 3 的实现

- [X] T013 [US3] 在 `backend/app/solver.py` 将 `stage1_makespan_days`、`stage2_makespan_days` 和 `stage2_makespan_delta_days` 写入 refined 成功诊断
- [X] T014 [US3] 按需在 `frontend/src/types/scheduler.ts` 补充两阶段诊断可选字段，保持旧结果兼容

**检查点**：用户能看懂第二阶段相对第一阶段提前、持平或晚于多少天。

---

## Phase 5：收尾与横切事项

**目标**：完成回归验证和 Spec Kit 门禁复核。

- [X] T015 运行后端排程回归测试并记录结果：`backend/tests/test_scheduler.py`
- [X] T016 按需运行前端类型或构建兼容验证：`frontend/src/types/scheduler.ts`
- [X] T017 检查 `specs/012-stage2-makespan-relaxation/tasks.md` 所有任务状态和剩余风险

---

## 依赖与执行顺序

### 阶段依赖

- **Phase 1 准备**：无依赖，可立即开始。
- **Phase 2 用户故事 1**：依赖准备完成，是 MVP。
- **Phase 3 用户故事 2**：可与 US1 测试设计并行，但实现应在 US1 后复核。
- **Phase 4 用户故事 3**：依赖 refined 成功接受逻辑稳定。
- **Phase 5 收尾**：依赖目标用户故事完成。

### 用户故事依赖

- **US1（P1）**：核心行为，必须先完成。
- **US2（P2）**：验证目标函数边界，不应改变 US1 行为。
- **US3（P3）**：补充解释字段，依赖 US1 的 refined 成功结果。

### 并行机会

- T003 可与 T001、T002 并行。
- T004、T005 可并行编写测试。
- T009、T011 可在不同断言场景中并行准备。

---

## 实施策略

### MVP 优先（用户故事 1）

1. 完成 T001-T002。
2. 增加 US1 测试。
3. 移除第二阶段相对第一阶段总工期硬上限和接受门槛。
4. 验证第二阶段 `M2 > M1` 且硬约束满足时被接受。

### 增量交付

1. US1：移除硬限制并验证接受规则。
2. US2：确认目标函数没有重复工期项。
3. US3：补充相对工期诊断。
4. 收尾：运行回归和兼容验证。

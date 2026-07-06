# 任务清单：移除未配置资源普通工程均衡目标

**输入**：来自 `specs/010-remove-unconfigured-normal-balance/` 的规格和设计文档。

**测试要求**：本变更涉及目标函数、CP-SAT 建模、前后端共享字段，必须包含后端测试和前端构建验证。

## Phase 1：准备

**目标**：确认本次只改 010 相关实现，不影响 009 已完成的同类资源工作量均衡移除。

- [X] T001 检查当前 git 状态并记录本次可触碰文件范围：`backend/app/models.py`、`backend/app/solver.py`、`backend/tests/test_scheduler.py`、`frontend/src/types/scheduler.ts`、`frontend/src/app/App.tsx`、`docs/精排目标函数算法需求文档_v4.0.md`

---

## Phase 2：基础契约

**目标**：先用测试锁定目标项集合、旧字段兼容和诊断保留。

- [X] T002 [P] 在 `backend/tests/test_scheduler.py` 更新默认目标项集合测试，断言 `unconfigured_normal_balance` 不在有效目标项和指标定义中
- [X] T003 [P] 在 `backend/tests/test_scheduler.py` 增加旧请求带 `unconfigured_normal_balance` 时被过滤且其他有效目标项保留的测试
- [X] T004 [P] 在 `backend/tests/test_scheduler.py` 增加只启用 `unconfigured_normal_balance` 时触发“至少一个目标项启用”校验的测试

**检查点**：测试应先体现当前实现缺口，随后由实现任务修复。

---

## Phase 3：用户故事 1 - 目标函数不再优化未配置资源普通工程均衡（优先级：P1）

**目标**：从后端目标函数和结果贡献中移除 `unconfigured_normal_balance`。

**独立测试**：后端求解含未配置资源普通工程场景，确认目标贡献和目标权重均无该项。

- [X] T005 [US1] 在 `backend/app/models.py` 从 `ObjectiveTermId`、`DEFAULT_OBJECTIVE_TERM_WEIGHTS`、`OBJECTIVE_METRIC_DEFINITIONS` 中移除 `unconfigured_normal_balance`
- [X] T006 [US1] 在 `backend/app/models.py` 将 `unconfigured_normal_balance` 加入废弃目标项集合并确保请求解析过滤
- [X] T007 [US1] 在 `backend/app/solver.py` 移除 `UNCONFIGURED_NORMAL_BALANCE_WEIGHT` 常量和 `unconfigured_normal_balance_enabled` 目标权重门控
- [X] T008 [US1] 在 `backend/app/solver.py` 停止调用 `_build_unconfigured_normal_balance_terms()` 作为 CP-SAT 目标构建
- [X] T009 [US1] 在 `backend/app/solver.py` 从 `modeled_terms` 和 `model.Minimize(...)` 中移除 `unconfigured_normal_balance` 加权项
- [X] T010 [US1] 在 `backend/app/solver.py` 从 `raw_penalties`、`objective_breakdown.objective_weights`、`objective_terms_used`、`objective_contributions` 当前输出中移除 `unconfigured_normal_balance`
- [X] T011 [US1] 在 `backend/tests/test_scheduler.py` 增加求解结果不含 `unconfigured_normal_balance` 目标贡献的测试

**检查点**：用户故事 1 完成后，后端目标函数不再包含未配置资源普通工程均衡。

---

## Phase 4：用户故事 2 - 历史配置兼容但不生效（优先级：P2）

**目标**：旧场景和旧结果不会把废弃目标重新带回当前目标函数解释。

**独立测试**：旧请求带该字段仍能在有其他有效目标项时求解；旧结果 fallback 不生成该贡献。

- [X] T012 [US2] 在 `backend/app/models.py` 确认废弃目标过滤发生在未知目标校验前，并保留现有未知目标报错
- [X] T013 [US2] 在 `frontend/src/app/App.tsx` 更新旧结果贡献 fallback，删除 `unconfigured_normal_balance_penalty` 和 `normal_balance_penalty` 到目标贡献的映射
- [X] T014 [US2] 在 `backend/tests/test_scheduler.py` 增加旧请求求解结果不含 `unconfigured_normal_balance` 的回归测试

**检查点**：用户故事 2 完成后，历史输入兼容，历史字段不再污染当前目标贡献。

---

## Phase 5：用户故事 3 - 普通工程分布仍可诊断但不称为目标（优先级：P3）

**目标**：前端移除配置项，同时保留普通工程分布复核数据。

**独立测试**：目标函数配置不再显示该行，`normal_balance_metrics` 仍有诊断数据。

- [X] T015 [US3] 在 `frontend/src/types/scheduler.ts` 从 `ObjectiveTermId` 删除 `unconfigured_normal_balance`
- [X] T016 [US3] 在 `frontend/src/app/App.tsx` 从 `objectiveTermDefinitions` 删除“未配置资源普通工程均衡”
- [X] T017 [US3] 在 `frontend/src/app/App.tsx` 调整普通工程诊断展示，确保不再显示为当前目标已启用
- [X] T018 [US3] 在 `backend/app/solver.py` 保留 `stats.normal_balance_metrics`，并将其计算调整为不依赖 CP-SAT 目标项变量

**检查点**：用户故事 3 完成后，用户看不到该目标项，但仍能复核普通工程分布。

---

## Phase 6：收尾与验证

**目标**：补齐文档和验证命令，确保前后端一致。

- [X] T019 [P] 更新 `docs/精排目标函数算法需求文档_v4.0.md` 中当前目标项列表，删除未配置资源普通工程均衡作为目标函数项的描述，并转为只读诊断说明
- [X] T020 运行 `python -m pytest backend/tests/test_scheduler.py -q` 验证后端目标项、兼容和求解行为
- [X] T021 运行 `npm.cmd --prefix frontend run build` 验证前端类型和构建
- [X] T022 对照 `specs/010-remove-unconfigured-normal-balance/quickstart.md` 记录 Excel 导入案例验证结果

---

## 依赖与执行顺序

### 阶段依赖

- **Phase 1**：无依赖。
- **Phase 2**：依赖 Phase 1，先锁定测试。
- **Phase 3**：依赖 Phase 2，完成核心后端移除。
- **Phase 4**：依赖 Phase 3，处理兼容边界。
- **Phase 5**：可在 Phase 3 后并行推进前端展示和诊断保留。
- **Phase 6**：依赖 Phase 3、Phase 4、Phase 5。

### 并行机会

- T002、T003、T004 可并行编写测试。
- T015、T016 可与后端实现并行，但 T017 需等目标项定义更新后检查展示。
- T019 可在核心口径稳定后与验证准备并行。

### MVP 范围

MVP 为用户故事 1：后端目标函数和结果贡献中移除 `unconfigured_normal_balance`。用户故事 2 和 3 用于保证兼容和页面解释完整。

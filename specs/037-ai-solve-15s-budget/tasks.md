# 任务清单：AI 单方案 15 秒求解预算

**输入**：来自 `specs/037-ai-solve-15s-budget/` 的 `spec.md`、`plan.md`、`research.md`、`data-model.md`、`contracts/` 和 `quickstart.md`

**前置条件**：用户确认本任务清单及 `$speckit-analyze` 结果后才可实施。

**测试要求**：本功能修改 AI 排程时限，采用测试先行；必须验证单方案、批量逐套、历史兼容、单阶段不变和真实 Excel 三方案。

## Phase 1：准备（共享基础）

**目标**：保护工作区已有改动并确认当前 60 秒预算传播基线。

- [x] T001 复核 `backend/app/services/ai_resource_scheduling_assistant.py`、`backend/tests/test_ai_resource_scheduling_assistant.py`、`backend/tests/test_scheduler.py`、`frontend/src/features/resourceAssistant/ResourceAssistantPanel.tsx` 和 `docs/AI资源配置与排程优化助手验证说明.md` 的现有未提交改动，仅做 037 范围内增量修改
- [x] T002 依据 `specs/037-ai-solve-15s-budget/quickstart.md` 记录当前默认 60 秒在单方案、批量、阶段摘要和目标评估中的传播基线

---

## Phase 2：基础测试能力

**目标**：复用现有 AI 单方案与批量求解夹具，能够核查预算、调用次数、状态和历史摘要。

- [x] T003 [P] 在 `backend/tests/test_ai_resource_scheduling_assistant.py` 整理默认预算传播断言，覆盖单方案、批量逐套和用户调整后重算
- [x] T004 [P] 在 `backend/tests/test_scheduler.py` 复用 AI 单阶段测试，确认传入 15 秒时唯一 `primary` 阶段完整获得该预算且不执行第二阶段

**检查点**：测试可以准确区分默认预算值变化与单阶段算法行为。

---

## Phase 3：用户故事 1 - 更快获得单方案结果（优先级：P1）

**目标**：经济、平衡、抢工及用户调整后的每套方案独立使用 15 秒，并保持一次固定资源工期求解。

**独立测试**：调用单方案和批量入口，断言每套方案的输入时限、总预算、唯一阶段预算和目标评估预算均为 15 秒，调用次数为 1 且不自动增配。

### 用户故事 1 的测试

- [x] T005 [US1] 在 `backend/tests/test_ai_resource_scheduling_assistant.py` 将默认 60 秒失败优先断言调整为 15 秒，并断言三处预算一致、批量每套独立 15 秒
- [x] T006 [P] [US1] 在 `backend/tests/test_scheduler.py` 增加或调整 15 秒单阶段回归，断言 `selected_stage=primary`、`secondary.attempted=false`、`solver_call_count=1`

### 用户故事 1 的实现

- [x] T007 [US1] 在 `backend/app/services/ai_resource_scheduling_assistant.py` 将 `AI_RESOURCE_PLAN_SOLVE_TIME_LIMIT_SECONDS` 从 60.0 调整为 15.0，不修改单阶段编排、目标或非 AI 时限
- [x] T008 [US1] 运行 `python -m pytest backend/tests/test_ai_resource_scheduling_assistant.py backend/tests/test_scheduler.py -q -k "time_limit or exact_resources or ai_single_stage"`，确认预算传播和单阶段不变量通过

**检查点**：后端新方案已统一为每套独立 15 秒，且仍只求解一次。

---

## Phase 4：用户故事 2 - 页面与结果口径一致（优先级：P2）

**目标**：页面与文档显示 15 秒当前口径，历史预算和阶段摘要继续原样读取。

**独立测试**：前端生产构建通过，页面当前说明只出现 15 秒；后端历史 60 秒摘要兼容测试仍通过。

### 用户故事 2 的测试与实现

- [x] T009 [P] [US2] 在 `frontend/src/features/resourceAssistant/ResourceAssistantPanel.tsx` 将单方案固定资源求解说明从最长 60 秒改为最长 15 秒
- [x] T010 [P] [US2] 在 `backend/tests/test_ai_resource_scheduling_assistant.py` 保留历史 60 秒与实际第二阶段摘要解析回归，证明当前默认值不会重写历史预算
- [x] T011 [US2] 运行 `npm.cmd run build`，确认 TypeScript 和生产构建通过，当前页面说明不再包含最长 60 秒

**检查点**：当前页面与实际 15 秒配置一致，历史结果无迁移。

---

## Phase 5：收尾与横切事项

**目标**：同步验证文档并完成完整、真实数据和范围隔离验证。

- [x] T012 [P] 更新 `docs/AI资源配置与排程优化助手验证说明.md`，将当前 AI 单方案预算和验证断言由 60 秒改为 15 秒，并说明历史预算保持原值
- [x] T013 运行 `python -m pytest backend/tests/test_scheduler.py backend/tests/test_ai_resource_scheduling_assistant.py backend/tests/test_plan_control_api.py backend/tests/test_bridge_import.py -q`，记录完整回归结果
- [x] T014 按 `specs/037-ai-solve-15s-budget/quickstart.md` 默认导入 `渠溪河特大桥结构设计表.xlsx`，串行求解经济、平衡、抢工三方案并记录预算、实际耗时、调用次数、状态、总工期、最大延期、资源快照和诊断
- [x] T015 复核 `specs/037-ai-solve-15s-budget/spec.md` 的 FR-001 至 FR-010 与 SC-001 至 SC-006，确认不恢复第二阶段、不隐藏延时、不改变非 AI 入口且未覆盖工作区无关改动

---

## 依赖与执行顺序

### 阶段依赖

- Phase 1 无依赖；Phase 2 依赖 Phase 1。
- US1 依赖基础测试能力，是本功能 MVP。
- US2 可在 US1 默认预算稳定后完成页面和历史兼容核查。
- Phase 5 依赖两个用户故事全部完成。

### 用户故事依赖图

```text
准备 -> 基础测试 -> US1 后端 15 秒预算 -> US2 页面与历史兼容 -> 收尾验证
```

### 并行机会

- T003 与 T004 修改不同测试文件，可并行准备。
- T006 与 T007 修改不同文件，但 T006 需先形成失败断言、T007 再实现。
- T009 与 T010 修改不同前后端文件，可并行。
- T012 可在后端预算值稳定后与前端构建并行。

## 实施策略

### MVP 优先（US1）

1. 完成 Phase 1 和 Phase 2。
2. 让 T005 的默认预算断言先证明当前代码仍为 60 秒。
3. 完成 T007，将统一入口预算改为 15 秒。
4. 运行 T008，独立交付每套方案 15 秒且一次求解。

### 增量交付

1. US1 完成后端预算与单阶段不变量。
2. US2 同步页面并证明历史兼容。
3. 最后运行完整回归和真实 Excel 三方案。

## 备注

- 所有 `[P]` 任务修改不同文件或只读验证，可并行执行。
- 不新增依赖、接口字段、持久化或用户可编辑时限。
- 不修改 `README.md`，不默认提交 Git。

## 实施记录（2026-07-14）

- 已将 `AI_RESOURCE_PLAN_SOLVE_TIME_LIMIT_SECONDS` 从 `60.0` 调整为 `15.0`，单方案、批量逐套和用户调整后重算均复用该预算。
- 单阶段目标、求解器、固定资源、三态、诊断、历史摘要和非 AI 入口未改变。
- 页面与验证文档已同步为“单方案固定资源求解最长 15 秒”，历史预算保持原值。
- 后端完整回归 `233 passed`，前端 `npm.cmd run build` 通过。
- 真实导入 `渠溪河特大桥结构设计表.xlsx` 后，经济、平衡、抢工分别得到 939、579、579 天，均为 `OPTIMAL`、最大延期 0、调用次数 1、预算 15 秒且未自动增配资源。


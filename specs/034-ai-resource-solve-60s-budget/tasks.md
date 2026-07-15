# 任务清单：AI 两阶段排程共享 60 秒预算

**输入**：来自 `/specs/034-ai-resource-solve-60s-budget/` 的 `spec.md`、`plan.md`、`research.md`、`data-model.md`、`contracts/ai-resource-solve-budget-api.md` 和 `quickstart.md`

**测试要求**：本功能改变 CP-SAT 求解时限，必须先调整预算传播断言，再实施默认值变更；必须运行后端全量回归、前端生产构建和真实 Excel 三方案串行验证。

**组织方式**：US1 交付单方案共享 60 秒求解；US2 交付页面与诊断口径一致；最终阶段完成兼容回归和真实案例证据。

## Phase 1：准备（共享基础）

**目标**：确认当前工作区、30 秒基线和精准影响面，避免覆盖 033 及其他用户修改。

- [x] T001 检查 `git status --short` 和相关 `git diff`，记录 `backend/app/services/ai_resource_scheduling_assistant.py`、`backend/app/scenario.py`、相关测试、前端说明和验证文档的现有修改重叠
- [x] T002 复核 `specs/033-ai-two-stage-resource-optimization/quickstart.md` 中 939/579/579 天及资源快照基线，并在 `specs/034-ai-resource-solve-60s-budget/quickstart.md` 确认真实 Excel 串行复测口径

---

## Phase 2：基础约束（阻塞前置）

**目标**：建立 60 秒预算的测试边界，并明确哪些现有 30 秒数据必须保留。

- [x] T003 在 `backend/tests/test_ai_resource_scheduling_assistant.py` 更新默认 AI 单方案和批量方案预算传播断言为 `60.0`，覆盖生成输入、阶段总预算、第一阶段配置预算和目标达成诊断
- [x] T004 [P] 在 `backend/tests/test_scheduler.py` 补充或调整代表性两阶段共享 60 秒用例，断言第二阶段仅使用剩余预算；保留显式 30 秒编排夹具和短预算隔离用例用于通用算法行为测试
- [x] T005 [P] 复核 `backend/tests/test_plan_control_api.py` 及模型序列化夹具中的 `30.0`，仅把它们作为历史响应兼容事实保留，并确保历史阶段摘要无需重写

**检查点**：测试能够区分“新 AI 默认预算 60 秒”“显式测试预算 30 秒”“历史记录 30 秒”和“LLM 超时 30 秒”。

---

## Phase 3：用户故事 1 - 给 AI 固定资源排程更多求解时间（优先级：P1）

**目标**：经济、平衡或抢工任一方案的两个阶段共享 60 秒，资源和目标规则完全不变。

**独立测试**：调用单方案求解，断言输入与阶段总预算为 60 秒、第二阶段预算来自剩余时间、资源快照一致且不扩资源。

### 用户故事 1 的测试

- [x] T006 [US1] 先运行 `python -m pytest backend/tests/test_ai_resource_scheduling_assistant.py backend/tests/test_scheduler.py -q`，确认新增 60 秒默认断言在实现前能够识别当前 30 秒行为

### 用户故事 1 的实现

- [x] T007 [US1] 将 `backend/app/services/ai_resource_scheduling_assistant.py` 中 `AI_RESOURCE_PLAN_SOLVE_TIME_LIMIT_SECONDS` 从 `30.0` 调整为 `60.0`，保持场景组装、固定资源和无增配路径不变
- [x] T008 [US1] 复核 `backend/app/scenario.py` 的剩余预算、模型构建预留和第二阶段跳过公式能直接接受 60 秒输入，不修改目标、阈值、回退原因或通用求解常量
- [x] T009 [US1] 运行 `python -m pytest backend/tests/test_ai_resource_scheduling_assistant.py backend/tests/test_scheduler.py -q`，验证默认 60 秒传播、共享预算、状态语义、固定资源及回退矩阵通过

**检查点**：后端新 AI 求解返回 `optimization_stages.total_budget_seconds=60.0`，且不存在两个阶段各 60 秒或资源自动增配。

---

## Phase 4：用户故事 2 - 准确识别求解预算及结果边界（优先级：P2）

**目标**：页面、接口诊断和验证文档统一说明单方案两阶段共享 60 秒，同时保留历史结果兼容。

**独立测试**：构建前端并查看 AI 多方案比选说明，确认显示共享 60 秒；读取新旧阶段摘要，确认 60 秒新结果和 30 秒历史结果都可解释。

### 用户故事 2 的实现与测试

- [x] T010 [P] [US2] 将 `frontend/src/features/resourceAssistant/ResourceAssistantPanel.tsx` 的“共享 30 秒”说明更新为“单方案两阶段共享 60 秒”，继续说明第二阶段只使用剩余时间
- [x] T011 [P] [US2] 更新 `docs/AI资源配置与排程优化助手验证说明.md` 中 AI 两阶段默认预算、阶段诊断示例和验证口径，明确不影响 LLM 超时与通用模拟求解
- [x] T012 [US2] 复核 `frontend/src/types/scheduler.ts` 和 `backend/app/models.py` 无需字段变更，运行 `npm.cmd run build` 验证新说明与历史可选阶段摘要类型兼容

**检查点**：用户可明确理解 60 秒的适用入口、单方案边界和两阶段共享关系；接口结构没有无必要变化。

---

## Phase 5：收尾与横切事项

**目标**：完成全链路回归、真实案例证据和 Spec Kit 收敛准备。

- [x] T013 运行 `python -m pytest backend/tests/test_plan_control_repository.py backend/tests/test_plan_control_api.py backend/tests/test_progress_forecast.py -q`，验证历史基准、设为基准和进度反馈读取兼容
- [x] T014 运行 `python -m pytest backend/tests -q`，确认通用模拟求解、最少资源、资源成本、里程碑和其他非 AI 时限保持不变
- [x] T015 按 `specs/034-ai-resource-solve-60s-budget/quickstart.md` 导入根目录 `渠溪河特大桥结构设计表.xlsx`，固定一次 LLM 三方案资源快照后串行求解经济、平衡、抢工三案
- [x] T016 将真实三方案的资源快照、阶段预算、状态、工期、最大延期、空闲、连续性、选择阶段、回退原因和总耗时补充到 `specs/034-ai-resource-solve-60s-budget/quickstart.md`，对照 939/579/579 天基线说明结果
- [x] T017 检查 `git diff --check`、共享字段前后端一致性、所有任务勾选状态及 `AGENTS.md`/Constitution 门禁，确认未误改 LLM 超时、通用求解常量、目标函数或资源扩充分支并准备 `$speckit-converge`

---

## 依赖与执行顺序

### 阶段依赖

- **Phase 1**：无依赖，先核对脏工作区和 30 秒基线。
- **Phase 2**：依赖 Phase 1，先建立准确测试边界。
- **US1（Phase 3）**：依赖 Phase 2，是 MVP 和后续展示口径的事实基础。
- **US2（Phase 4）**：依赖 US1 的最终预算事实，但 T010/T011 可在后端实现稳定后并行修改。
- **Phase 5**：依赖 US1/US2 全部完成；真实 Excel 不得与全量测试并行。

### 用户故事依赖

- **US1**：独立交付后端共享 60 秒预算，是建议 MVP。
- **US2**：依赖 US1 确认的实际预算值，仅同步说明和兼容验证，不改变算法。

### 并行机会

- T004 与 T005 修改不同测试关注面，可并行准备。
- T010 与 T011 修改前端和文档不同文件，可并行执行。
- 自动化单元测试可以分组执行，但 T014 全量回归与 T015 真实 CP-SAT 性能验证必须串行，避免 CPU 竞争。

## 并行示例：用户故事 2

```text
Task: "更新 frontend/src/features/resourceAssistant/ResourceAssistantPanel.tsx 的共享 60 秒说明"
Task: "更新 docs/AI资源配置与排程优化助手验证说明.md 的预算和验证口径"
```

## 实施策略

### MVP 优先（仅用户故事 1）

1. 完成 T001-T005，锁定当前事实和测试边界。
2. 完成 T006-T009，使 AI 单方案真实使用两阶段共享 60 秒。
3. 用针对性测试确认资源、目标、状态和回退不变。

### 增量交付

1. US1 先交付算法预算变更。
2. US2 同步页面与验证文档口径。
3. 最后执行兼容回归和真实 Excel 三案串行验证，形成可复现证据。

## 备注

- 不新增依赖、接口字段、持久化或用户时限配置。
- 不批量替换仓库内所有 `30.0`；LLM 超时、历史响应和显式算法夹具必须按原语义保留。
- 用户确认 `$speckit-analyze` 结果前，不执行 T001-T017。

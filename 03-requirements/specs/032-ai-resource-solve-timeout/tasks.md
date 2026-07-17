# 任务清单：AI 资源方案求解时限调整

**输入**：来自 `/specs/032-ai-resource-solve-timeout/` 的设计文档

**前置条件**：`plan.md`、`spec.md`、`research.md`、`data-model.md`、`contracts/ai-resource-solve-timeout-api.md`、`quickstart.md`

**测试要求**：本功能调整 AI 严格固定资源的 CP-SAT 求解预算，必须包含参数传递测试、固定资源边界回归、非 AI 入口兼容测试和真实 Excel 验证。

**组织方式**：任务按用户故事分组；先用测试锁定 30 秒专项预算，再实施最小服务层调整，最后验证其他入口不受影响。

## Phase 1：准备（共享基础）

**目标**：确认工作区现状与本功能的最小影响面，避免覆盖现有未提交改动。

- [x] T001 检查 `git status --short`，复核 `backend/app/services/ai_resource_scheduling_assistant.py`、`backend/tests/test_ai_resource_scheduling_assistant.py`、`backend/tests/test_scheduler.py` 和 `docs/AI资源配置与排程优化助手验证说明.md` 的现有改动，记录需要保留的用户修改
- [x] T002 运行 `backend/tests/test_ai_resource_scheduling_assistant.py` 中严格固定资源单方案测试并记录当前 15 秒/场景时限基线，确认变更前测试状态

---

## Phase 2：基础能力（阻塞前置）

**目标**：确认无需新增共享模型、接口字段、前端类型、依赖和持久化，并锁定现有诊断字段作为验收接口。

- [x] T003 核对 `backend/app/models.py`、`backend/app/scenario.py` 和 `backend/app/solver.py` 中 `time_limit_seconds`、`configured_time_limit_seconds`、`target_achievement.time_budget_seconds`、`solver_call_count`、`resource_expansion_attempted` 的现有传递链，确认实现仅需修改 AI 服务与相关测试

**检查点**：专项预算的输入、输出诊断和非目标入口边界已确认，可以开始用户故事实现。

---

## Phase 3：用户故事 1 - 使用更长预算求解 AI 资源方案（优先级：P1）

**目标**：经济、平衡、抢工方案进入严格固定资源求解时均使用 30 秒预算，并允许提前返回。

**独立测试**：拦截单方案和批量方案的严格求解调用，断言每个方案场景的 `time_limit_seconds=30.0`；真实响应继续能从现有诊断字段核查配置值。

### 用户故事 1 的测试

- [x] T004 [US1] 在 `backend/tests/test_ai_resource_scheduling_assistant.py` 增加单方案与批量方案 30 秒预算捕获测试，先证明当前实现仍传入原始场景时限

### 用户故事 1 的实现

- [x] T005 [US1] 在 `backend/app/services/ai_resource_scheduling_assistant.py` 定义 AI 资源方案专项 30 秒常量，并在 `_solve_single_plan()` 创建方案场景副本时应用该时限
- [x] T006 [US1] 在 `backend/tests/test_ai_resource_scheduling_assistant.py` 补充响应诊断断言，验证 `generated.schedule_input.time_limit_seconds`、`configured_time_limit_seconds` 和 `target_achievement.time_budget_seconds` 为 `30.0`

**检查点**：单方案与批量方案均使用 30 秒预算，US1 可独立验证。

---

## Phase 4：用户故事 2 - 保持既有严格资源求解边界（优先级：P2）

**目标**：延长时限时不修改资源数量、不新增求解阶段、不改变目标函数和状态语义。

**独立测试**：使用同一方案求解，断言实际命名资源数量与方案一致、`solver_call_count=1`、`resource_expansion_attempted=false`，三个目标项与权重不变。

### 用户故事 2 的测试与实现

- [x] T007 [US2] 调整 `backend/tests/test_ai_resource_scheduling_assistant.py` 中现有真实严格资源性能测试，通过可控测试预算或求解替身避免每次等待 30 秒，同时保留资源快照、单次调用、无增配和三态断言
- [x] T008 [US2] 在 `backend/tests/test_ai_resource_scheduling_assistant.py` 增加或强化目标函数配置回归断言，确认 30 秒调整不改变 `control_node_late`、`makespan_and_soft_milestone`、`resource_idle` 的启用状态和权重

**检查点**：时限变化与固定资源、单次求解、目标函数边界可分别核查。

---

## Phase 5：用户故事 3 - 保持其他求解入口兼容（优先级：P3）

**目标**：全局场景默认时限和非 AI 求解入口继续保持原有行为。

**独立测试**：默认场景仍为 15 秒；通用严格资源或其他非 AI 入口继续使用请求场景原值，不读取 AI 专项常量。

### 用户故事 3 的测试

- [x] T009 [US3] 在 `backend/tests/test_scheduler.py` 复核并按需强化默认场景 `time_limit_seconds=15` 与通用求解入口按请求值执行的回归断言
- [x] T010 [US3] 运行 `backend/tests/test_scheduler.py` 的时限、固定资源和目标函数相关用例，确认底层 `TARGET_SOLVE_TIME_LIMIT_SECONDS` 与通用编排未发生变化

**检查点**：AI 专项 30 秒未扩散到其他求解模式。

---

## Phase 6：收尾与横切事项

**目标**：同步文档并完成自动化和真实场景验证。

- [x] T011 [P] 更新 `docs/AI资源配置与排程优化助手验证说明.md`，说明每个 AI 单方案使用 30 秒最大预算、可提前返回且不承诺 `OPTIMAL`
- [x] T012 运行 `.\.venv\Scripts\python.exe -m pytest backend\tests\test_ai_resource_scheduling_assistant.py -q`，修复本功能相关回归
- [x] T013 运行 `.\.venv\Scripts\python.exe -m pytest backend\tests\test_scheduler.py -q` 和 `npm.cmd run build`，确认后端通用求解及前端生产构建通过
- [x] T014 按 `specs/032-ai-resource-solve-timeout/quickstart.md` 导入 `渠溪河特大桥结构设计表.xlsx`，至少实际求解一套 LLM 资源方案并记录 30 秒配置、实际耗时、状态、单次调用和无增配结果
- [x] T015 检查 `git diff --check`、任务勾选状态和 Constitution 门禁，记录未覆盖风险并准备 `$speckit-converge`

---

## 依赖与执行顺序

### 阶段依赖

- **Phase 1**：无依赖，可立即开始。
- **Phase 2**：依赖 Phase 1，确认现有字段链路后阻塞用户故事实现。
- **US1（Phase 3）**：依赖 Phase 2，是 MVP 和后续故事的实现基础。
- **US2（Phase 4）**：依赖 T005，验证实现没有改变严格资源和目标函数边界。
- **US3（Phase 5）**：可在 T005 后与 US2 并行验证，重点覆盖非 AI 入口。
- **Phase 6**：依赖 US1、US2、US3 完成。

### 用户故事依赖

- **US1**：基础能力完成后即可实施，交付 30 秒专项预算。
- **US2**：依赖 US1 的专项预算实现，但测试可先编写。
- **US3**：依赖 US1 后执行回归，与 US2 无业务依赖。

### 并行机会

- T004 的测试编写与 T003 的字段链复核可在确认测试锚点后交错进行。
- T008 与 T009 修改不同测试文件，可在 T005 完成后并行。
- T011 文档更新可与 US2、US3 的测试执行并行。
- T012、T013 不建议与真实求解 T014 并行，避免 CPU 竞争影响时限验证。

---

## 并行示例：用户故事 2 与用户故事 3

```text
Task: "在 backend/tests/test_ai_resource_scheduling_assistant.py 验证目标函数、固定资源和单次调用边界"
Task: "在 backend/tests/test_scheduler.py 验证默认 15 秒与非 AI 入口兼容"
```

---

## 实施策略

### MVP 优先（仅用户故事 1）

1. 完成 T001-T003。
2. 先完成 T004 的失败测试。
3. 完成 T005-T006，使 AI 单方案和批量方案使用 30 秒预算。
4. 独立运行 US1 测试，确认配置和诊断正确。

### 增量交付

1. US1 交付专项 30 秒预算。
2. US2 锁定固定资源、单次求解和目标函数不变。
3. US3 锁定其他入口不受影响。
4. 最后执行真实 Excel 求解和全量相关回归。

## 备注

- 所有实现任务均复用现有文件，不新增依赖、共享字段或页面配置。
- 自动化测试不应通过真实等待 30 秒证明常量值；参数捕获与真实 Excel 验证分工完成证据闭环。
- 未经用户确认 `$speckit-analyze` 结果前，不执行 T001-T015。

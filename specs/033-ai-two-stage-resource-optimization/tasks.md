# 任务清单：AI 固定资源两阶段排程优化

**输入**：来自 `/specs/033-ai-two-stage-resource-optimization/` 的设计文档

**前置条件**：`plan.md`、`spec.md`、`research.md`、`data-model.md`、`contracts/ai-two-stage-resource-solve-api.md`、`quickstart.md`

**测试要求**：本功能改变最大延期口径、CP-SAT 目标、固定资源编排、连续性目标和前后端共享字段，必须采用测试先行，并包含真实 Excel 三方案验证。

**组织方式**：任务按三个用户故事分组；US1 先交付稳定工期基线，US2 增加不退化的资源组织优化，US3 完成失败回退和历史兼容。

## Phase 1：准备（共享基础）

**目标**：确认工作区现状、现有性能基线和功能影响面，避免覆盖用户未提交修改。

- [x] T001 检查 `git status --short` 和 `git diff`，复核 `backend/app/models.py`、`backend/app/scenario.py`、`backend/app/solver.py`、`backend/app/services/ai_resource_scheduling_assistant.py`、相关测试及前端文件中的现有用户修改并记录重叠点
- [x] T002 按 `specs/033-ai-two-stage-resource-optimization/quickstart.md` 记录当前渠溪河特大桥三方案关闭/开启资源空闲的状态、工期、耗时、空闲与转场指标基线，作为实现后对照

---

## Phase 2：基础能力（阻塞前置）

**目标**：建立两个阶段共享的可选响应模型和前端兼容类型，不改变现有求解行为。

- [x] T003 在 `backend/app/models.py` 增加第一阶段摘要、第二阶段摘要、两阶段选择摘要及 `ResourceAssistantPlanResult.optimization_stages` 可选字段，保留历史响应默认值
- [x] T004 [P] 在 `frontend/src/types/scheduler.ts` 增加与契约一致的可选阶段摘要类型，并确保历史结果可省略该字段
- [x] T005 在 `backend/tests/test_ai_resource_scheduling_assistant.py` 增加新增模型序列化、旧响应缺少阶段字段和接口向后兼容测试

**检查点**：后端和前端能够表达阶段事实，旧结果仍可解析，可以开始算法故事实现。

---

## Phase 3：用户故事 1 - 优先获得稳定工期排程（优先级：P1）

**目标**：第一阶段只按“最大延期、总工期”严格排序，不构建资源空闲和连续性目标。

**独立测试**：构造多里程碑场景及总工期目标，验证最大延期取最大值、减少 1 天最大延期永远优先于任意总工期变化；真实固定资源方案第一阶段能独立返回排程和阶段摘要。

### 用户故事 1 的测试

- [x] T006 [P] [US1] 在 `backend/tests/test_scheduler.py` 增加最大延期 `[0,12,5]` 与固定超期 `8` 得到 `12`、无延期得到 `0`、无目标为空的第一阶段目标测试
- [x] T007 [P] [US1] 在 `backend/tests/test_scheduler.py` 增加严格字典序测试，覆盖最大延期优先、最大延期相同时总工期优先及第一阶段不构建 `resource_idle`/连续性目标门禁
- [x] T008 [P] [US1] 在 `backend/tests/test_ai_resource_scheduling_assistant.py` 增加严格固定资源第一阶段调用、30 秒总预算、无自动增配和工期阶段摘要测试

### 用户故事 1 的实现

- [x] T009 [US1] 在 `backend/app/solver.py` 抽取固定资源基础模型上下文，使现有任务、资源分配、执行约束、前后置、连续梁和里程碑构建可被阶段模式复用且旧入口默认行为不变
- [x] T010 [US1] 在 `backend/app/solver.py` 实现强制里程碑与固定总工期的 `max_target_delay` 变量及安全字典序第一阶段目标 `[max_target_delay, makespan]`
- [x] T011 [US1] 在 `backend/app/scenario.py` 增加 AI 固定资源两阶段编排骨架，先接入第一阶段、记录剩余预算并在无排程或预算耗尽时直接返回第一阶段
- [x] T012 [US1] 在 `backend/app/services/ai_resource_scheduling_assistant.py` 组装第一阶段摘要，并让工期三态与最优性证明读取第一阶段事实而非后续阶段状态
- [x] T013 [US1] 运行 `backend/tests/test_scheduler.py` 和 `backend/tests/test_ai_resource_scheduling_assistant.py` 的 US1 用例，确认第一阶段可独立交付且普通求解入口保持原行为

**检查点**：即使不实现第二阶段，AI 方案也能在共享预算内返回只受最大延期和总工期控制的稳定排程。

---

## Phase 4：用户故事 2 - 在不损害工期的前提下改善资源组织（优先级：P2）

**目标**：第二阶段使用剩余预算和第一阶段提示，在工期上限内严格优化资源空闲与页面一致的连续性罚分。

**独立测试**：给定第一阶段最大延期和总工期，第二阶段返回结果必须同时不超过两个上限，并按 `(累计资源空闲, 连续性罚分)` 严格改善；次目标未证明最优时仍保留第一阶段工期证明。

### 用户故事 2 的测试

- [x] T014 [P] [US2] 在 `backend/tests/test_scheduler.py` 增加第二阶段最大延期/总工期硬上限、资源空闲优先、连续性次优和安全整数上界测试
- [x] T015 [P] [US2] 在 `backend/tests/test_scheduler.py` 增加连续性弧罚分测试，覆盖跨墩 ×4、换幅 ×2、跨幅跳墩 ×6、路径组切换 ×1、缺少空间信息及第一阶段弧强制保留
- [x] T016 [P] [US2] 在 `backend/tests/test_ai_resource_scheduling_assistant.py` 增加第二阶段共享剩余预算、资源数量完全一致、`solver_call_count=2`、无增配和阶段状态独立测试

### 用户故事 2 的实现

- [x] T017 [US2] 在 `backend/app/solver.py` 扩展现有资源空闲构建能力，使其只在第二阶段创建，并输出累计空闲安全上界和诊断
- [x] T018 [US2] 在 `backend/app/solver.py` 实现与页面转场罚分一致的稀疏连续性路径节点、候选弧、弧成本、第一阶段路径提示和连续性安全上界
- [x] T019 [US2] 在 `backend/app/solver.py` 实现第二阶段安全字典序目标 `[resource_idle_days, continuity_penalty]`、第一阶段工期上限和开始/结束/资源/路径 warm start
- [x] T020 [US2] 在 `backend/app/scenario.py` 接入剩余预算计算、第二阶段调用、任务/资源/工期边界校验和次目标严格改善比较
- [x] T021 [US2] 在 `backend/app/services/ai_resource_scheduling_assistant.py` 输出第二阶段摘要、最终选择阶段、总耗时和次目标最优性，同时保持推荐只依据工期三态
- [x] T022 [US2] 在 `frontend/src/domain/resourceAssistant.ts`、`frontend/src/features/resourceAssistant/ResourcePlanCard.tsx` 和 `frontend/src/features/resourceAssistant/ResourceAssistantPanel.tsx` 增加“工期排程状态 / 资源组织状态”解释与阶段回退提示，不改变方案求解入口
- [x] T023 [US2] 运行 US2 后端用例和前端生产构建，验证第二阶段可独立改善资源组织且不改变第一阶段工期结论

**检查点**：有剩余预算时可获得工期不退化的资源组织改进；次目标状态与工期状态分别可见。

---

## Phase 5：用户故事 3 - 次目标失败时稳定回退（优先级：P3）

**目标**：第二阶段任何失败、越界或无改进都不影响第一阶段排程、工期状态、推荐和设为基准链路。

**独立测试**：分别模拟第二阶段 `UNKNOWN`、`INFEASIBLE`、模型错误、预算不足、工期越界、资源变化、任务缺失和无严格改善，全部返回第一阶段排程及对应回退原因。

### 用户故事 3 的测试

- [x] T024 [P] [US3] 在 `backend/tests/test_scheduler.py` 增加第二阶段 `UNKNOWN/INFEASIBLE/MODEL_INVALID`、预算不足和 warm start 候选不足的回退测试
- [x] T025 [P] [US3] 在 `backend/tests/test_ai_resource_scheduling_assistant.py` 增加工期越界、资源快照变化、任务集合变化、无次目标改善和第一阶段状态保持测试
- [x] T026 [P] [US3] 在 `backend/tests/test_plan_control_repository.py` 和 `backend/tests/test_plan_control_api.py` 增加历史无 `optimization_stages` 基准快照、两阶段新结果和进度反馈读取兼容测试

### 用户故事 3 的实现

- [x] T027 [US3] 在 `backend/app/scenario.py` 完成所有第二阶段跳过、拒绝和回退原因映射，确保最终始终保留第一阶段可行排程
- [x] T028 [US3] 在 `backend/app/services/ai_resource_scheduling_assistant.py` 完成第一阶段工期证明与第二阶段次目标证明解耦，覆盖单方案、批量比较和推荐链路
- [x] T029 [US3] 在 `frontend/src/domain/resourceAssistant.ts` 和 `frontend/src/features/resourceAssistant/ResourcePlanCard.tsx` 完成历史结果兼容、第二阶段未执行/已回退/未证明最优展示及缺失字段兜底
- [x] T030 [US3] 运行 US3、计划管控持久化和设为基准相关用例，确认失败回退与历史兼容可独立验证

**检查点**：所有次目标失败路径均稳定返回第一阶段，不影响后续基准计划和进度反馈。

---

## Phase 6：收尾与横切事项

**目标**：完成文档同步、全量回归、性能证据和 Spec Kit 收敛准备。

- [x] T031 [P] 更新 `docs/AI资源配置与排程优化助手验证说明.md`，说明两阶段目标、30 秒共享预算、工期不退化、连续性口径和回退状态
- [x] T032 运行 `python -m pytest backend/tests/test_ai_resource_scheduling_assistant.py backend/tests/test_scheduler.py -q`，修复算法和服务回归
- [x] T033 运行 `python -m pytest backend/tests/test_plan_control_repository.py backend/tests/test_plan_control_api.py backend/tests/test_progress_forecast.py -q`，确认基准计划和进度预测兼容
- [x] T034 运行 `python -m pytest backend/tests -q` 和 `frontend` 下 `npm.cmd run build`，确认完整后端测试与前端生产构建通过
- [x] T035 按 `specs/033-ai-two-stage-resource-optimization/quickstart.md` 导入 `渠溪河特大桥结构设计表.xlsx`，实际求解三套 LLM 资源方案并记录阶段状态、工期、最大延期、空闲、连续性、耗时、资源快照和回退情况
- [x] T036 对真实三方案断言最终工期不劣于 939/579/579 天基线、两阶段总预算不超过 30 秒加固定开销且资源增配次数为 0，并将证据补充到 `specs/033-ai-two-stage-resource-optimization/quickstart.md`
- [x] T037 检查 `git diff --check`、共享字段前后端一致性、任务勾选状态和 Constitution 门禁，记录剩余风险并准备 `$speckit-converge`

---

## 依赖与执行顺序

### 阶段依赖

- **Phase 1**：无依赖，可立即开始。
- **Phase 2**：依赖 Phase 1，阶段摘要模型阻塞各用户故事。
- **US1（Phase 3）**：依赖 Phase 2，是 MVP 和两个后续故事的工期基线。
- **US2（Phase 4）**：依赖 US1 的第一阶段排程、工期上限和阶段摘要。
- **US3（Phase 5）**：依赖 US1；完整回退覆盖依赖 US2 的第二阶段实现。
- **Phase 6**：依赖三个用户故事全部完成。

### 用户故事依赖

- **US1**：可独立交付第一阶段稳定工期排程，是建议 MVP。
- **US2**：在 US1 之上增加可回退的资源组织改进；即使未完成，US1 仍可运行。
- **US3**：补齐 US2 的失败矩阵和历史兼容，不改变 US1/US2 正常路径。

### 单个故事内部顺序

- 每个故事先编写并确认测试失败或覆盖缺失，再修改实现。
- `models.py` 和基础模型上下文先于服务及前端接入。
- 第一阶段先于第二阶段，第二阶段先于完整回退矩阵。
- 真实 Excel 验证不得与后端全量测试并行，避免 CPU 竞争污染时限证据。

### 并行机会

- T003 与 T004 修改后端/前端不同文件，可并行。
- T006/T007 与 T008 修改不同测试文件，可并行编写。
- T014/T015 与 T016 修改不同测试文件，可并行编写。
- T024、T025、T026 覆盖不同测试模块，可并行。
- T031 文档同步可在功能测试稳定后与前端兼容检查交错执行。

---

## 并行示例：用户故事 2

```text
Task: "在 backend/tests/test_scheduler.py 编写第二阶段工期上限、空闲和连续性目标测试"
Task: "在 backend/tests/test_ai_resource_scheduling_assistant.py 编写共享预算、固定资源和阶段状态测试"
```

---

## 实施策略

### MVP 优先（仅用户故事 1）

1. 完成 T001-T005。
2. 先完成 T006-T008 的失败测试。
3. 完成 T009-T012，使 AI 固定资源入口只按最大延期和总工期求解。
4. 完成 T013，使用真实或代表性场景验证稳定工期基线。

### 增量交付

1. US1 先恢复快速稳定的工期排程。
2. US2 在工期硬边界内增加空闲和连续性优化。
3. US3 补齐所有回退、历史兼容和后续计划链路。
4. 最后执行完整回归与真实 Excel 三方案证据闭环。

## 备注

- 不新增外部依赖、服务或持久化文件。
- 不恢复公开可配置的 `resource_path_continuity`，连续性仅作为 AI 第二阶段内部目标和诊断。
- 未经用户确认 `$speckit-analyze` 结果前，不执行 T001-T037。

## Phase 7：收敛补充

- [x] T038 根据 `data-model: ResourceAssistantSecondaryStageSummary` 与 `contract: 典型状态` 统一第二阶段未启动、无排程和校验失败的原因枚举及字段归位，并同步前端文案与回归测试（partial）

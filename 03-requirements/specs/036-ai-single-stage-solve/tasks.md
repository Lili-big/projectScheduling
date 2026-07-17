# 任务清单：AI 固定资源单阶段求解

**输入**：来自 `specs/036-ai-single-stage-solve/` 的 `spec.md`、`plan.md`、`research.md`、`data-model.md`、`contracts/` 和 `quickstart.md`

**前置条件**：用户确认本任务清单及 `$speckit-analyze` 结果后才可实施。

**测试要求**：本功能删除活动排程阶段和目标分支，采用测试先行；必须验证一次调用、完整预算、工期目标、诊断兼容和非 AI 隔离。

## Phase 1：准备（共享基础）

**目标**：保护工作区已有改动并记录当前两阶段基线。

- [x] T001 复核 `backend/app/scenario.py`、`backend/app/solver.py`、`backend/tests/test_scheduler.py`、`frontend/src/domain/resourceAssistant.ts`、`frontend/src/features/resourceAssistant/ResourceAssistantPanel.tsx` 和 `frontend/src/features/resourceAssistant/ResourcePlanCard.tsx` 的现有未提交改动，只在 036 范围内增量修改
- [x] T002 依据 `specs/036-ai-single-stage-solve/quickstart.md` 记录当前 AI 方案的求解调用次数、阶段摘要、预算分配、工期目标和诊断基线

---

## Phase 2：基础能力（阻塞前置）

**目标**：准备单阶段行为和历史兼容共用的测试夹具。

- [x] T003 [P] 在 `backend/tests/test_scheduler.py` 复用或整理固定资源 AI 场景和伪求解结果辅助能力，可记录调用阶段、配置时限、工期、资源空闲及连续性诊断
- [x] T004 [P] 在 `backend/tests/test_ai_resource_scheduling_assistant.py` 复用或整理单方案响应和阶段摘要夹具，支持新单阶段结果与历史两阶段结果并存验证

**检查点**：测试夹具就绪，可以开始用户故事实现。

---

## Phase 3：用户故事 1 - 一次求解直接返回工期排程（优先级：P1）

**目标**：每套 AI 固定资源方案只执行一次 `[最大目标延期, 总工期]` 求解并直接返回。

**独立测试**：对任一 AI 资源方案求解，断言只有一次 `primary` 调用、使用完整 60 秒、`solver_call_count=1`、最终阶段为 `primary` 且没有第二阶段预留或重试。

### 用户故事 1 的测试

- [x] T005 [P] [US1] 在 `backend/tests/test_scheduler.py` 增加失败优先测试，断言 `solve_ai_strict_fixed_resource_scenario()` 只调用一次工期求解、完整传入配置预算并直接采用该结果
- [x] T006 [P] [US1] 在 `backend/tests/test_scheduler.py` 增加失败优先目标测试，断言 AI 唯一阶段仍关闭资源空闲目标并保持最大延期优先、总工期其次

### 用户故事 1 的实现

- [x] T007 [US1] 在 `backend/app/scenario.py` 删除剩余预算、模型构建预留、第二阶段调用和采用校验编排，改为一次工期求解后直接生成结果
- [x] T008 [US1] 在 `backend/app/solver.py` 删除仅供 AI 第二阶段使用的入口参数、累计空闲严格改善边界、第二阶段目标和阶段统计分支，并将 AI 性能路径统一为 `ai_strict_fixed_resource_single_stage`
- [x] T009 [US1] 在 `backend/app/scenario.py` 生成单阶段兼容摘要：`secondary.attempted=false`、`skipped_reason=not_applicable`、`selected_stage=primary`、`solver_call_count=1`
- [x] T010 [US1] 运行 `python -m pytest backend/tests/test_scheduler.py -q -k "ai and single_stage"`，确认一次调用、完整预算、工期目标和失败直返场景通过

**检查点**：核心 AI 方案已成为可独立运行的一次固定资源工期求解。

---

## Phase 4：用户故事 2 - 保留诊断与历史结果兼容（优先级：P2）

**目标**：新结果继续提供空闲和连续性诊断，历史两阶段结果及基准快照继续可读。

**独立测试**：新单阶段结果返回现有诊断但不影响状态；历史 `selected_stage=secondary`、旧跳过原因和缺少阶段摘要的数据均可解析。

### 用户故事 2 的测试

- [x] T011 [P] [US2] 在 `backend/tests/test_scheduler.py` 增加求解后诊断测试，断言累计资源空闲和连续性继续返回，但不会触发额外调用或改变工期结果
- [x] T012 [P] [US2] 在 `backend/tests/test_ai_resource_scheduling_assistant.py` 增加新单阶段兼容摘要和历史两阶段响应解析回归
- [x] T013 [P] [US2] 在 `backend/tests/test_plan_control_api.py` 增加或复用历史第二阶段基准快照、推荐和进度反馈读取回归

### 用户故事 2 的实现

- [x] T014 [US2] 在 `backend/app/scenario.py` 保留最终排程的资源空闲、连续性、工期三态和固定资源诊断，并确保诊断不作为目标或重试条件
- [x] T015 [US2] 运行 `python -m pytest backend/tests/test_ai_resource_scheduling_assistant.py backend/tests/test_plan_control_api.py -q`，确认新结果和历史结果兼容链路通过

**检查点**：单阶段当前结果和两阶段历史结果均可独立读取与审计。

---

## Phase 5：用户故事 3 - 页面与下游链路统一为单阶段（优先级：P3）

**目标**：新结果只显示一次工期求解，推荐、基准和进度反馈继续使用现有工期事实。

**独立测试**：求解新方案后页面不显示两阶段或第二阶段未执行说明；加载历史两阶段结果时仍可显示历史阶段详情；场景变化继续使旧结果失效。

### 用户故事 3 的测试与实现

- [x] T016 [US3] 在 `frontend/src/domain/resourceAssistant.ts` 实现新单阶段摘要与历史两阶段摘要的明确展示分流：新结果只返回工期说明，历史实际第二阶段继续返回阶段说明，并由 TypeScript 构建验证
- [x] T017 [P] [US3] 在 `backend/tests/test_ai_resource_scheduling_assistant.py` 复核三方案推荐、固定资源数量、状态三态和场景指纹失效不依赖第二阶段
- [x] T018 [P] [US3] 在 `frontend/src/features/resourceAssistant/ResourceAssistantPanel.tsx` 将顶部说明改为单方案固定资源工期求解最长 60 秒
- [x] T019 [P] [US3] 在 `frontend/src/features/resourceAssistant/ResourcePlanCard.tsx` 对可选历史阶段说明做条件渲染，避免新结果出现空的第二阶段行
- [x] T020 [US3] 运行 `npm.cmd run build`，确认 TypeScript 和生产构建通过，页面当前口径中不存在两阶段或第二阶段优化说明

**检查点**：页面和下游业务链路与单阶段实际行为一致，历史展示不丢失。

---

## Phase 6：收尾与横切事项

**目标**：更新文档并完成全量、真实数据和范围隔离验证。

- [x] T021 [P] 更新 `docs/AI资源配置与排程优化助手验证说明.md`，将当前 AI 排程改为一次工期求解并说明诊断及历史兼容边界
- [x] T022 运行 `python -m pytest backend/tests/test_scheduler.py backend/tests/test_ai_resource_scheduling_assistant.py backend/tests/test_plan_control_api.py backend/tests/test_bridge_import.py -q`，记录完整回归结果
- [x] T023 按 `specs/036-ai-single-stage-solve/quickstart.md` 默认导入 `渠溪河特大桥结构设计表.xlsx`，依次真实求解经济、平衡、抢工三方案并记录调用次数、预算、工期、延期、资源快照和诊断
- [x] T024 复核 `specs/036-ai-single-stage-solve/spec.md` 的 FR-001 至 FR-014 与 SC-001 至 SC-007，确认没有活动第二阶段调用、非 AI 求解入口未改变且未覆盖工作区无关改动

---

## 依赖与执行顺序

### 阶段依赖

- Phase 1 无依赖；Phase 2 依赖 Phase 1。
- US1 依赖基础测试夹具，是本功能 MVP。
- US2 依赖 US1 的新结果结构；历史兼容测试可与部分前端准备并行。
- US3 依赖 US1 的单阶段语义和 US2 的历史兼容决策。
- Phase 6 依赖三个用户故事全部完成。

### 用户故事依赖图

```text
准备 -> 基础能力 -> US1 单阶段核心 -> US2 诊断与历史兼容 -> US3 页面与下游
                                                        \-> 收尾验证
```

### 并行机会

- T003 与 T004 可并行准备不同测试文件。
- T005 与 T006 可并行编写编排级和目标级失败测试。
- T011、T012、T013 可并行覆盖不同层次的兼容回归。
- T018 与 T019 修改不同前端组件，可并行。
- T017 与 T021 可在单阶段契约稳定后并行执行。

---

## 实施策略

### MVP 优先（US1）

1. 完成 Phase 1 和 Phase 2。
2. 先让 T005、T006 证明当前代码仍执行第二阶段。
3. 完成 T007～T009，交付一次固定资源工期求解。
4. 运行 T010 独立验证 MVP。

### 增量交付

1. US1 删除活动第二阶段。
2. US2 固化诊断和历史兼容。
3. US3 同步当前页面与下游口径。
4. 最后运行真实 Excel 三方案和完整回归。

## 备注

- 所有 `[P]` 任务修改不同文件或只读验证，可并行执行。
- 不新增依赖，不删除共享历史字段，不修改 `README.md`。
- 项目不存在规划技能所述的 Agent 上下文更新脚本，因此不手工改写 `AGENTS.md` 或 `agent.md`。

## 实施记录（2026-07-14）

- 已移除 AI 固定资源求解的剩余预算计算、第二阶段调用、空闲改善边界、warm start 和采用校验；唯一阶段使用完整配置预算。
- 新结果固定为 `selected_stage=primary`、`secondary.attempted=false`、`secondary.skipped_reason=not_applicable`、`solver_call_count=1`，历史两阶段字段继续兼容读取。
- 资源空闲和连续性继续作为最终排程诊断，不参与 AI 目标函数、重试或结果采用。
- 后端完整回归 `232 passed`；前端 `npm.cmd run build` 通过。
- 真实导入 `渠溪河特大桥结构设计表.xlsx` 后，经济、平衡、抢工三方案均为单次 `primary` 求解，预算均为 60 秒且未自动增配资源。


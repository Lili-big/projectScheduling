# 任务清单：AI资源助手分步求解与独立推荐

**输入**：来自 `specs/023-stepwise-resource-solve/` 的设计文档

**前置条件**：`plan.md`、`spec.md`、`research.md`、`data-model.md`、`contracts/resource-assistant-stepwise-api.md`

**测试要求**：本功能修改前后端共享字段和请求编排，必须包含后端回归测试、前端构建验证和可复现页面验证。

## Phase 1：准备

**目标**：确认改造只作用于资源助手，不改变 CP-SAT 行为。

- [X] T001 复核 `specs/023-stepwise-resource-solve/contracts/resource-assistant-stepwise-api.md` 与现有 `backend/app/services/ai_resource_scheduling_assistant.py` 的可复用函数边界
- [X] T002 [P] 为分步接口的状态、部分对比和 LLM 回退场景在 `backend/tests/test_ai_resource_scheduling_assistant.py` 补充失败测试

---

## Phase 2：基础能力

**目标**：建立三个独立请求的共享契约和后端编排，完成前不得接入页面。

- [X] T003 在 `backend/app/models.py` 新增单方案求解、结果对比、独立推荐的请求与响应模型
- [X] T004 [P] 在 `frontend/src/types/scheduler.ts` 增加与后端对应的分步请求与响应类型
- [X] T005 在 `backend/app/services/ai_resource_scheduling_assistant.py` 封装单方案求解、无求解对比和完整推荐服务函数，复用现有 `_solve_single_plan`、`build_comparison`、`build_deterministic_recommendation` 与回退解释
- [X] T006 在 `backend/app/main.py` 注册 `/solve-plan`、`/compare-results`、`/generate-recommendation` 路由，并保留 `/batch-solve` 兼容
- [X] T007 在 `frontend/src/api/schedulerApi.ts` 新增三类分步 API 客户端函数，不改动现有批量函数

**检查点**：单方案、轻量对比和独立推荐接口均可单独调用；前两者不调用外部 LLM。

---

## Phase 3：用户故事 1 - 手动求解单个资源方案（优先级：P1）

**目标**：用户能够通过 A/B/C 各自的按钮独立求解，并在返回后立即看到对应方案的结果。

**独立测试**：点击 A 后仅 A 进入求解中；B/C 保持可操作；A 响应不会覆盖 B/C 结果。

- [X] T008 [P] [US1] 在 `backend/tests/test_ai_resource_scheduling_assistant.py` 覆盖单方案只调用一次求解、异常转为目标方案 `failed` 结果且不触发解释的回归测试
- [X] T009 [US1] 在 `frontend/src/domain/resourceAssistant.ts` 增加按方案合并结果、判断单方案完成与失效推荐的领域 helper
- [X] T010 [US1] 在 `frontend/src/features/resourceAssistant/ResourceAssistantPanel.tsx` 将全量“确认并求解”替换为 A/B/C 独立按钮、独立忙碌状态、独立错误与结果合并
- [X] T011 [US1] 在 `frontend/src/features/resourceAssistant/ResourcePlanCard.tsx` 接入方案级求解操作、状态和重试入口

**检查点**：A、B、C 任一方案可独立完成并立即展示其计划视图，不等待其他方案。

---

## Phase 4：用户故事 2 - 逐步查看方案对比（优先级：P1）

**目标**：每次单方案完成后，对比区刷新已完成列，待求解方案不被误显示为无结果。

**独立测试**：先完成 A，再完成 B/C；对比表逐列补全，已完成列保持不变。

- [X] T012 [P] [US2] 在 `backend/tests/test_ai_resource_scheduling_assistant.py` 覆盖部分 `plan_results` 的对比结果、不可行原因和“无 CP-SAT/无 LLM”断言
- [X] T013 [US2] 在 `frontend/src/features/resourceAssistant/ResourceAssistantPanel.tsx` 于每次单方案响应后调用 `compare-results` 并维护部分比较状态
- [X] T014 [US2] 在 `frontend/src/features/resourceAssistant/MetricComparisonTable.tsx` 展示固定 A/B/C 列、待求解占位与已完成不可用原因

**检查点**：对比区在仅完成 A 时即可反映 A 指标，B/C 显示待求解；三套完成后完整对比。

---

## Phase 5：用户故事 3 - 手动生成完整推荐解释（优先级：P2）

**目标**：推荐按钮仅在三套方案完成时启用，并由用户显式触发确定性推荐与 LLM/本地解释。

**独立测试**：三方案未齐时按钮禁用；三方案完成后单击推荐只调用推荐接口；LLM 失败仍保留本地解释。

- [X] T015 [P] [US3] 在 `backend/tests/test_ai_resource_scheduling_assistant.py` 覆盖未齐三结果返回 422、完整结果生成推荐和 LLM 失败本地回退
- [X] T016 [US3] 在 `frontend/src/domain/resourceAssistant.ts` 增加完整三方案完成门禁和推荐失效判断
- [X] T017 [US3] 在 `frontend/src/features/resourceAssistant/ResourceAssistantPanel.tsx` 增加“生成 LLM 推荐”按钮、禁用提示、独立加载状态及推荐响应接入
- [X] T018 [US3] 在 `frontend/src/features/resourceAssistant/RecommendationPanel.tsx` 展示推荐请求中的加载、失败重试与现有本地/LLM来源状态

**检查点**：单方案求解永不调用 LLM；推荐请求仅在完整结果后发生，失败不清空方案结果。

---

## Phase 6：收尾与横切验证

- [X] T019 在 `frontend/src/features/resourceAssistant/ResourceAssistantPanel.tsx` 复核重新生成、切换场景和编辑资源后的结果/比较/推荐失效顺序
- [X] T020 [P] 更新 `docs/AI资源配置与排程优化助手验证说明.md`，将批量“确认并求解”流程替换为四按钮分步验证流程
- [X] T021 运行 `backend/tests/test_ai_resource_scheduling_assistant.py`、`npm.cmd run build` 并按 `specs/023-stepwise-resource-solve/quickstart.md` 完成默认场景手动验证

## 依赖与执行顺序

- Phase 1 → Phase 2 → US1 → US2 → US3 → 收尾。
- US2 依赖 US1 的结果合并；US3 依赖 US1 和 US2 的完整结果状态与比较。
- T003 与 T004 可并行；T008、T012、T015 分别可在对应实现前独立准备。

## 实施策略

先完成“单方案求解”闭环并验证；再接入逐步对比，最后接入独立推荐。整个过程中不修改 `backend/app/scenario.py`、`backend/app/solver.py` 或前端通用请求超时。

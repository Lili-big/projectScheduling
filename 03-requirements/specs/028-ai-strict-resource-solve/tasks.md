# 任务清单：AI 方案严格固定资源单次求解

**输入**：来自 `specs/028-ai-strict-resource-solve/` 的 `spec.md`、`plan.md`、`research.md`、`data-model.md`、`contracts/` 和 `quickstart.md`

**测试要求**：本功能改变 CP-SAT 调用编排、业务状态、推荐门禁和前后端共享字段，必须先补失败测试，再实施并运行后端、前端及页面验证。

## Phase 1：准备（共享基础）

**目标**：确认实现边界、共享测试输入和可观测计数方式。

- [x] T001 按 `specs/028-ai-strict-resource-solve/plan.md` 复核并记录实现前 git 状态、受影响文件和验证命令，确保不覆盖无关改动
- [x] T002 在 `backend/tests/test_ai_resource_scheduling_assistant.py` 增加可复用的严格资源方案、零工作量资源和目标日期测试输入构造器
- [x] T003 [P] 在 `backend/tests/test_scheduler.py` 增加可复用的一次完整目标求解调用计数器和固定资源目标样例

---

## Phase 2：基础契约（阻塞前置）

**目标**：建立四状态和资源输入快照的后端、前端共享类型，供后续故事复用。

- [x] T004 在 `backend/app/models.py` 增加 `ResourceAssistantPlanOutcomeStatus`，并为 `ResourceAssistantPlanResult` 增加可空 `plan_status`、可空 `solver_status`、`input_resource_quantities`、`resource_expansion_attempted` 向后兼容字段
- [x] T005 [P] 在 `frontend/src/types/scheduler.ts` 同步四状态枚举、`ResourceAssistantPlanResult` 增量字段及 `TargetAchievement` 的 `target_present`、`has_schedule`、`optimality_proven` 字段
- [x] T006 在 `backend/tests/test_ai_resource_scheduling_assistant.py` 增加新增响应字段默认值、序列化和旧输入兼容测试

**检查点**：共享契约可序列化，旧调用方无需提供新增字段。

---

## Phase 3：用户故事 1 - 严格使用当前资源完成一次排程（优先级：P1）

**目标**：一个 AI 单方案请求严格使用当前 `quantity`，只运行一次完整目标 CP-SAT，且不进入任何增配分支。

**独立测试**：对 LLM 数量和用户调整数量分别求解，断言任务图生成一次、CP-SAT 调用一次、资源增量调用零次、资源快照和命名资源数量一致。

### 用户故事 1 的测试

- [x] T007 [P] [US1] 在 `backend/tests/test_scheduler.py` 增加无基础排程的一次完整目标求解测试，断言三个目标项、硬约束、`solver_call_count=1`、基线未评估和通用入口兼容
- [x] T008 [US1] 在 `backend/tests/test_ai_resource_scheduling_assistant.py` 增加 LLM 数量、用户调整数量、零工作量资源、资源类型缺失及 `max_quantity` 不参与展开的严格输入测试
- [x] T009 [US1] 在 `backend/tests/test_ai_resource_scheduling_assistant.py` 增加 `solve-plan` 与兼容批量求解不调用基础排程、`solve_scenario()`、最大资源生成、最少资源搜索或候选复排的调用计数测试

### 用户故事 1 的实现

- [x] T010 [US1] 在 `backend/app/solver.py` 抽取可无 `baseline_result` 直接执行的完整目标模型内部能力，并保持现有 `solve_control_priority_schedule()` 的兼容入口行为
- [x] T011 [US1] 在 `backend/app/solver.py` 将基线依赖诊断改为可选，AI 无基线路径输出 `baseline_status=not_evaluated`、`warm_start_used=false`，且不伪造基线工期和任务偏差
- [x] T012 [US1] 在 `backend/app/scenario.py` 新增 AI 专用严格固定资源编排函数：生成一次任务图、调用一次完整目标求解、返回空 `alternative_results` 并写入 `ai_strict_fixed_resource_one_pass` 性能元数据
- [x] T013 [US1] 在 `backend/app/services/ai_resource_scheduling_assistant.py` 将 `_solve_single_plan()` 改为调用严格编排，组装当前数量快照并固定 `resource_expansion_attempted=false`
- [x] T014 [US1] 在 `backend/app/services/ai_resource_scheduling_assistant.py` 让 `batch_solve_resource_plans()` 对每个方案复用同一严格编排，同时保持逐方案结果隔离和现有页面主路径不变

**检查点**：US1 可独立证明“输入多少就排多少、每方案只求解一次、绝不自动增配”。

---

## Phase 4：用户故事 2 - 准确理解四种求解结论（优先级：P1）

**目标**：按证明状态和目标偏差输出 `met`、`not_met`、`unconfirmed`、`infeasible`，并保留可查看排程与诊断。

**独立测试**：状态矩阵的六类样例均返回约定状态、排程有无、延期和失败原因。

### 用户故事 2 的测试

- [x] T015 [P] [US2] 在 `backend/tests/test_scheduler.py` 增加 `OPTIMAL/FEASIBLE/UNKNOWN/INFEASIBLE`、目标缺失和资源覆盖错误的严格状态分类测试
- [x] T016 [US2] 在 `backend/tests/test_ai_resource_scheduling_assistant.py` 增加 `FEASIBLE + 延期 = unconfirmed`、`OPTIMAL + 延期 = not_met`、目标满足为 `met`、物理不可行为 `infeasible` 的接口测试
- [x] T017 [US2] 在 `backend/tests/test_ai_resource_scheduling_assistant.py` 增加技术失败不伪装成 `infeasible`、重新求解不沿用旧排程和旧状态的回归测试

### 用户故事 2 的实现

- [x] T018 [US2] 在 `backend/app/scenario.py` 实现严格状态分类和 `target_achievement` 归一化，写入 `target_present`、`has_schedule`、`optimality_proven`、延期字段和失败原因
- [x] T019 [US2] 在 `backend/app/services/ai_resource_scheduling_assistant.py` 将 `plan_status`、`solver_status` 和归一化 `metrics.target_status` 写入单方案结果，保留 `not_met` 和有 incumbent 的 `unconfirmed` 排程
- [x] T020 [P] [US2] 在 `frontend/src/domain/resourceAssistant.ts` 增加四状态中文标签、色调、延期摘要和未确认/不可行说明的纯函数
- [x] T021 [US2] 在 `frontend/src/features/resourceAssistant/ResourcePlanCard.tsx` 分开展示工作流状态与业务状态，并为 `not_met`、`unconfirmed`、`infeasible` 展示对应摘要或诊断入口
- [x] T022 [US2] 在 `backend/app/services/ai_resource_scheduling_assistant.py` 和 `frontend/src/features/resourceAssistant/MetricComparisonTable.tsx` 增加方案业务状态对比行，避免不可用指标沿用其他方案结果
- [x] T023 [US2] 在 `frontend/src/features/resourceAssistant/ResourceAssistantPanel.tsx` 确保方案调整、重新生成、项目变化和请求失败时同步清除旧业务状态、延期摘要与详情引用

**检查点**：US2 可独立验证状态语义和页面展示，不依赖推荐功能。

---

## Phase 5：用户故事 3 - 只从目标已满足方案中生成推荐（优先级：P2）

**目标**：确定性推荐和 LLM 解释只使用 `met` 方案；没有 `met` 时返回无推荐。

**独立测试**：分别输入一个、多个和零个 `met` 结果，核对候选集和 `recommended_scenario_id`。

### 用户故事 3 的测试

- [x] T024 [P] [US3] 在 `backend/tests/test_ai_resource_scheduling_assistant.py` 增加仅一个 `met`、多个 `met`、全部非 `met` 以及有总工期但明确延期的推荐门禁测试

### 用户故事 3 的实现

- [x] T025 [US3] 在 `backend/app/services/ai_resource_scheduling_assistant.py` 移除 `_target_met()` 的“指标存在即满足”兜底，并让确定性推荐只筛选 `plan_status=met`
- [x] T026 [US3] 在 `backend/app/services/ai_resource_scheduling_assistant.py` 为无 `met` 候选返回空推荐标识、本地可解释原因和风险提示，同时保持 LLM 只能解释后端结论
- [x] T027 [US3] 在 `frontend/src/features/resourceAssistant/ResourceAssistantPanel.tsx` 与现有推荐展示组件中呈现“暂无满足目标的推荐方案”，并继续保留三方案结果

**检查点**：US3 可独立证明延期或未确认方案不会因已有排程、成本或等待指标而进入推荐。

---

## Phase 6：收尾与横切事项

**目标**：完成性能、兼容、文档和页面闭环验证。

- [x] T028 [P] 在 `docs/AI资源配置与排程优化助手验证说明.md` 更新 AI 严格固定资源、单次求解、四状态和推荐门禁说明，不修改通用模拟求解文档口径
- [x] T029 在 `backend/tests/test_ai_resource_scheduling_assistant.py` 增加端到端耗时不超过 `time_limit_seconds + 2` 秒、任务图生成一次和资源增量调用零次的性能回归断言
- [x] T030 运行 `python -m pytest backend/tests/test_ai_resource_scheduling_assistant.py -q` 并修复本功能回归
- [x] T031 运行 `python -m pytest backend/tests/test_scheduler.py -q`，确认通用固定资源增量建议、目标函数和硬约束回归通过
- [x] T032 运行 `npm.cmd --workspace frontend run build`，确认 TypeScript 与生产构建通过
- [x] T033 按 `specs/028-ai-strict-resource-solve/quickstart.md` 完成 AI 多方案页面、四状态、零资源、重新求解和无推荐空态验证
- [x] T034 按 `specs/028-ai-strict-resource-solve/quickstart.md` 回归模拟求解入口仍可生成原有资源增量候选，并记录未覆盖风险

---

## 依赖与执行顺序

### 阶段依赖

- **Phase 1**：无依赖。
- **Phase 2**：依赖 Phase 1，阻塞全部用户故事。
- **US1（Phase 3）**：依赖 Phase 2，是 US2 和 US3 的求解数据基础。
- **US2（Phase 4）**：依赖 US1 的严格结果，但可先并行编写状态和前端纯函数测试。
- **US3（Phase 5）**：依赖 US2 的 `plan_status` 契约。
- **Phase 6**：依赖 US1、US2、US3 完成。

### 用户故事依赖图

```text
准备与共享契约
  -> US1 严格单次求解
      -> US2 四状态与展示
          -> US3 推荐门禁
              -> 全量验证
```

### 单个故事内部顺序

- 测试输入与失败断言先于实现。
- 底层模型能力先于场景编排，场景编排先于 AI 服务接入。
- 后端契约和状态先于前端展示。
- 推荐测试先于推荐规则修改。

### 并行机会

- T002 与 T003 可并行，分别修改两个测试文件。
- T004 与 T005 可并行，分别修改后端和前端类型。
- T007 与 T008 可先并行编写底层和服务失败测试。
- T015 与 T020 可并行，分别准备后端状态测试和前端状态纯函数。
- T024 与 T028 可并行，分别处理推荐测试和验证说明文档。

---

## 并行示例：用户故事 1

```text
Task: "在 backend/tests/test_scheduler.py 增加无基础排程的一次完整目标求解测试"
Task: "在 backend/tests/test_ai_resource_scheduling_assistant.py 增加严格资源数量和零工作量测试"
```

## 并行示例：用户故事 2

```text
Task: "在 backend/tests/test_scheduler.py 增加四状态底层分类测试"
Task: "在 frontend/src/domain/resourceAssistant.ts 增加四状态展示纯函数"
```

## 实施策略

### MVP 范围

MVP 必须同时完成 US1 和 US2：只做到单次求解但没有可靠状态，会继续把延期可行解误解为目标满足或资源不足。MVP 验证通过后再接入 US3 推荐门禁。

### 增量交付

1. 建立共享契约与失败测试。
2. 交付 US1，证明每方案一次求解、严格数量、零增配。
3. 交付 US2，证明四状态、延期和诊断可解释。
4. 交付 US3，封闭推荐候选集。
5. 完成性能、通用入口、前端和页面回归。

## 格式校验

- 全部任务均使用 `- [ ] T### [P?] [US?] 描述 + 文件路径` 格式。
- 用户故事阶段任务均包含 `[US1]`、`[US2]` 或 `[US3]`。
- 准备、基础和收尾任务不使用故事标签。
- 标记 `[P]` 的任务修改不同文件或只读验证，不与前置未完成任务冲突。

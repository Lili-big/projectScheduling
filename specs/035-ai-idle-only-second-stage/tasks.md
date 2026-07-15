# 任务清单：AI 第二阶段仅优化资源空闲

**输入**：来自 `specs/035-ai-idle-only-second-stage/` 的 `spec.md`、`plan.md`、`research.md`、`data-model.md`、`contracts/` 和 `quickstart.md`

**前置条件**：用户确认本任务清单及 `$speckit-analyze` 结果后才可实施。

**测试要求**：本功能修改 CP-SAT 第二阶段目标、阶段选择和前后端解释，采用测试先行；所有算法任务必须有可复现输入和断言。

**组织方式**：任务按用户故事分组，每个故事都提供独立测试标准。

## Phase 1：准备（共享基础）

**目标**：确认变更边界并保护当前工作区已有改动。

- [x] T001 复核并记录 `backend/app/solver.py`、`backend/app/scenario.py`、`backend/app/models.py`、`frontend/src/domain/resourceAssistant.ts`、`frontend/src/features/resourceAssistant/ResourceAssistantPanel.tsx` 及相关测试的现有未提交改动，只在本功能涉及行上增量修改
- [x] T002 以 `specs/035-ai-idle-only-second-stage/quickstart.md` 中的小样例和真实 Excel 场景记录实施前基线，包括第一阶段工期、累计资源空闲、连续性诊断、第二阶段模型统计和最终采用阶段

---

## Phase 2：基础能力（阻塞前置）

**目标**：建立所有用户故事共享的兼容原因契约和测试辅助能力。

- [x] T003 在 `backend/app/models.py` 为现有 `ResourceAssistantSecondaryStageSummary.skipped_reason` 增加向后兼容枚举值 `idle_already_zero`，不删除历史枚举值或响应字段
- [x] T004 [P] 在 `backend/tests/test_scheduler.py` 整理可复用的两阶段小场景与模型统计断言辅助函数，支持精确比较累计资源空闲、工期边界和连续性建模计数
- [x] T005 [P] 在 `backend/tests/test_ai_resource_scheduling_assistant.py` 整理固定资源 AI 方案结果构造辅助函数，确保测试不会触发资源增配或候选资源搜索

**检查点**：原因枚举与测试夹具就绪，可以按故事实现。

---

## Phase 3：用户故事 1 - 第二阶段只压缩资源内部空闲（优先级：P1）

**目标**：第二阶段只最小化累计资源空闲，并且只在空闲严格下降且工期不恶化时采用。

**独立测试**：构造第一阶段空闲 120 天的可行排程，验证第二阶段空闲 100 天时可采用、空闲仍为 120 天时回退、工期越界时回退；连续性诊断的好坏不改变上述结论。

### 用户故事 1 的测试

- [x] T006 [P] [US1] 在 `backend/tests/test_scheduler.py` 增加失败优先测试，断言 AI 第二阶段只建立累计资源空闲目标，不创建资源路径节点、候选转移弧、`AddCircuit` 或连续性目标项
- [x] T007 [P] [US1] 在 `backend/tests/test_ai_resource_scheduling_assistant.py` 增加失败优先测试，覆盖“空闲下降且连续性变差仍采用”“空闲相同且连续性变好仍回退”“空闲下降但最大延期或总工期越界仍回退”

### 用户故事 1 的实现

- [x] T008 [US1] 在 `backend/app/solver.py` 将 AI 第二阶段目标改为 `minimize(total_resource_idle_days)`，加入相对第一阶段至少减少 1 天的边界，关闭连续性路径节点、转移弧、环路、罚分变量及相关暖启动
- [x] T009 [US1] 在 `backend/app/scenario.py` 将第二阶段采用校验改为仅比较累计资源空闲，并继续校验最大延期、总工期、任务集合和固定资源快照，不再读取连续性罚分决定采用或回退
- [x] T010 [US1] 运行 `python -m pytest backend/tests/test_scheduler.py backend/tests/test_ai_resource_scheduling_assistant.py -q`，确认用户故事 1 的目标建模、严格改善和工期回退场景全部通过

**检查点**：第二阶段能够在固定资源和第一阶段工期边界内独立完成“只降资源空闲”的求解与选择。

---

## Phase 4：用户故事 2 - 保留连续性诊断但不影响排程选择（优先级：P2）

**目标**：继续输出资源路径连续性诊断供人工审核，但明确其不参与第二阶段模型、阶段选择或推荐。

**独立测试**：使用同一任务排程生成跳墩、换幅、跨幅跳墩、方向反转和路径组切换诊断，验证字段仍返回；修改诊断值不改变阶段选择，页面文字明确“仅供诊断”。

### 用户故事 2 的测试

- [x] T011 [P] [US2] 在 `backend/tests/test_scheduler.py` 增加连续性求解后诊断回归，断言最终排程仍生成现有连续性指标，但 AI 第二阶段模型统计中的路径节点和转移弧为 0
- [x] T012 [P] [US2] 在 `backend/tests/test_ai_resource_scheduling_assistant.py` 增加接口摘要回归，断言 `secondary.continuity_penalty` 继续可读且不参与 `selected_stage`、工期三态或推荐门禁

### 用户故事 2 的实现

- [x] T013 [US2] 在 `backend/app/scenario.py` 保留最终排程的连续性诊断计算和 `secondary.continuity_penalty` 回填，同时删除将该值作为第二阶段输入、严格改善条件或回退依据的内部依赖
- [x] T014 [P] [US2] 在 `frontend/src/domain/resourceAssistant.ts` 将 `no_secondary_improvement` 解释改为“累计资源空闲没有严格改善”，并保持历史连续性字段的兼容读取
- [x] T015 [P] [US2] 在 `frontend/src/features/resourceAssistant/ResourceAssistantPanel.tsx` 将阶段说明统一为“先锁定最大延期与总工期，再减少资源内部空闲”，并将连续性标注为求解后诊断而非优化目标
- [x] T016 [US2] 运行后端对应测试以及 `frontend/package.json` 中现有 TypeScript 校验脚本，确认连续性诊断保留且页面不再声称第二阶段优化连续性

**检查点**：连续性信息仍可审核，但已从模型、采用规则和推荐解释中完全退出。

---

## Phase 5：用户故事 3 - 保持现有回退和兼容链路（优先级：P3）

**目标**：保持 60 秒共享预算、固定资源、失败回退、历史结果、推荐、基准计划和进度反馈链路稳定。

**独立测试**：覆盖第一阶段空闲为 0、预算不足、第二阶段无排程/异常/越界/无改善等情况，验证均保留第一阶段；加载历史含连续性字段结果并验证推荐、基准和进度读取不变。

### 用户故事 3 的测试

- [x] T017 [P] [US3] 在 `backend/tests/test_ai_resource_scheduling_assistant.py` 增加失败优先测试，断言第一阶段空闲为 0 时第二阶段不启动且返回 `idle_already_zero`，并覆盖共享预算不足、无排程、模型异常、资源越界和空闲未改善回退
- [x] T018 [P] [US3] 在 `backend/tests/test_plan_control_api.py` 增加或更新历史阶段摘要、推荐方案、基准计划和进度反馈兼容回归，验证历史 `continuity_penalty` 与旧原因值无需迁移即可读取

### 用户故事 3 的实现

- [x] T019 [US3] 在 `backend/app/scenario.py` 增加第一阶段累计资源空闲为 0 时直接跳过第二阶段的编排分支，写入 `skipped_reason=idle_already_zero`，并保持 60 秒共享预算及其余回退原因不变
- [x] T020 [P] [US3] 在 `frontend/src/domain/resourceAssistant.ts` 增加 `idle_already_zero` 的用户可见解释，并确认旧阶段摘要缺字段或包含旧原因值时仍可解析
- [x] T021 [US3] 运行 `python -m pytest backend/tests/test_ai_resource_scheduling_assistant.py backend/tests/test_plan_control_api.py -q`，确认固定资源数量、工期三态、推荐、基准和进度反馈链路全部通过

**检查点**：全部用户故事可共同运行，且失败时始终安全回退第一阶段。

---

## Phase 6：收尾与横切事项

**目标**：完成说明、全量回归、前端构建和真实数据验证。

- [x] T022 [P] 更新 `docs/AI资源配置与排程优化助手验证说明.md`，将第二阶段口径、采用规则、`idle_already_zero`、连续性诊断定位和可复现验证步骤与本规格保持一致
- [x] T023 运行 `python -m pytest backend/tests/test_scheduler.py backend/tests/test_ai_resource_scheduling_assistant.py backend/tests/test_plan_control_api.py -q`，记录用例数量、耗时和失败详情
- [x] T024 运行 `frontend/package.json` 中现有 TypeScript 类型检查与生产构建命令，确认无新增类型错误且产物可构建
- [x] T025 按 `specs/035-ai-idle-only-second-stage/quickstart.md` 使用真实 Excel 导入后依次求解经济、平衡、抢工三方案，记录固定资源快照、两阶段耗时、工期、累计资源空闲、连续性诊断、模型路径计数和最终采用阶段
- [x] T026 复核 `specs/035-ai-idle-only-second-stage/spec.md` 的 FR-001 至 FR-015 与 SC-001 至 SC-007，确认无连续性求解残留、非 AI 求解入口未改变且工作区无无关文件被覆盖

---

## 依赖与执行顺序

### 阶段依赖

- **Phase 1**：无依赖，先保护现有工作区并记录基线。
- **Phase 2**：依赖 Phase 1，阻塞所有故事。
- **US1（Phase 3）**：依赖 Phase 2，是核心算法 MVP。
- **US2（Phase 4）**：依赖 US1 的阶段选择语义，诊断测试和前端文案可在 US1 稳定后实施。
- **US3（Phase 5）**：依赖 US1 的编排结果；历史兼容测试可与 US2 并行。
- **Phase 6**：依赖三个故事全部完成。

### 用户故事依赖

```text
准备 -> 基础能力 -> US1 核心算法 -> US2 诊断口径
                              \-> US3 回退兼容
US2 + US3 -> 收尾验证
```

### 并行机会

- T004 与 T005 可并行准备不同测试文件的辅助能力。
- T006 与 T007 可并行编写求解器级和编排级失败测试。
- T011 与 T012 可并行验证诊断计算和接口摘要。
- T014 与 T015 可并行修改不同前端文件。
- T017 与 T018 可并行覆盖 AI 编排和计划管控历史兼容。
- T020 与 T022 可在后端契约稳定后并行更新前端解释与文档。

---

## 并行示例：用户故事 1

```text
Task T006：在 backend/tests/test_scheduler.py 验证第二阶段无连续性路径模型。
Task T007：在 backend/tests/test_ai_resource_scheduling_assistant.py 验证阶段采用只看资源空闲及工期边界。
```

## 并行示例：用户故事 2 与 3

```text
Task T011/T012：并行验证连续性诊断兼容。
Task T017/T018：并行验证 AI 回退和历史计划兼容。
```

---

## 实施策略

### MVP 优先（US1）

1. 完成 Phase 1 和 Phase 2。
2. 先让 T006、T007 失败，证明当前实现仍在求解连续性。
3. 完成 T008、T009，只交付“第二阶段仅优化资源空闲”的核心行为。
4. 运行 T010，独立确认采用与回退口径。

### 增量交付

1. US1 收窄目标和采用规则。
2. US2 保留诊断并改正用户可见解释。
3. US3 补齐零空闲跳过、失败回退和历史链路。
4. 最后执行真实 Excel 三方案验证和完整回归。

## 备注

- 所有 `[P]` 任务修改不同文件或只读验证，可并行执行。
- 任务描述中的测试命令以仓库当前虚拟环境和 `frontend/package.json` 实际脚本为准，不新增依赖。
- 项目不存在规划技能所述的 Agent 上下文更新脚本，因此本功能不手工改写 `AGENTS.md` 或 `agent.md`。

## 实施记录

- 针对性新行为测试：7 项通过。
- `backend/tests/test_ai_resource_scheduling_assistant.py` 与 `backend/tests/test_plan_control_api.py`：44 项通过。
- `backend/tests/test_scheduler.py`：174 项通过、1 项失败；失败项为既有本地 Excel 选择测试，根目录新增“泸古工期表”后按文件名排序优先选中了非桥梁结构参数工作簿，与本次第二阶段目标变更无调用关系。
- 前端 `npm.cmd run build`：TypeScript 与 Vite 生产构建通过。
- 真实 `渠溪河特大桥结构设计表.xlsx`：351 个任务，经济/平衡/抢工三套固定资源均完成真实 60 秒预算求解；所有结果的资源路径节点和转移弧均为 0，连续性诊断仍返回，资源扩充均为 `false`。
- 真实案例结果：经济方案 952 天、最大延期 7 天、采用第二阶段且空闲 295 天；平衡方案 904 天、最大延期 0 天；抢工方案 887 天、最大延期 0 天。后两套第一阶段用满共享预算，按原规则跳过第二阶段。

# 任务清单：AI资源配置与排程优化助手

**输入**：来自 `specs/022-ai-resource-scheduling-assistant/` 的设计文档。

**前置条件**：`plan.md`、`spec.md`、`research.md`、`data-model.md`、`contracts/ai-resource-scheduling-assistant-contract.md`、`quickstart.md`。

**测试要求**：本功能涉及排程资源模型、三方案批量求解、结果指标契约、AI 解释和前后端共享字段，必须包含后端回归测试、前端构建验证和可复现演示验证。

**组织方式**：任务按用户故事分组，确保每个故事都可独立实现和验证。

## Phase 1：准备（共享基础）

**目标**：确认当前工作区、现有能力和受影响文件，避免覆盖用户已有改动。

- [X] T001 检查当前 git 状态并记录既有改动范围，重点保护 `LLM+CPSAT融合方案.md` 和当前 specs 目录
- [X] T002 阅读并标注现有三方案可复用入口：`backend/app/main.py`、`backend/app/scenario.py`、`frontend/src/api/schedulerApi.ts`
- [X] T003 [P] 阅读资源池、求解结果和前端类型：`backend/app/models.py`、`frontend/src/types/scheduler.ts`
- [X] T004 [P] 阅读前端主页面、甘特/资源展示和结果失效路径：`frontend/src/app/App.tsx`
- [X] T005 [P] 阅读现有 LLM 配置和回退模式：`backend/app/process_nl.py`、`backend/app/services/ai_parameter_ai_client.py`、`.local.env.example`

---

## Phase 2：基础能力（阻塞前置）

**目标**：建立三方案助手所需的共享契约、服务骨架、配置骨架和前端类型基础；本阶段完成前不得开始用户故事实现。

- [X] T006 在 `backend/app/models.py` 增加工程画像、AI 方案生成记录、资源方案、方案指标、批量求解响应、推荐解释和 LLM 配置状态模型
- [X] T007 在 `frontend/src/types/scheduler.ts` 增加与后端模型对齐的助手类型定义
- [X] T008 在 `backend/app/services/ai_resource_scheduling_assistant.py` 创建助手服务骨架，包含画像、AI 方案生成、方案校验、求解、指标、推荐解释的占位函数
- [X] T009 在 `backend/app/services/ai_resource_explainer.py` 创建外部 LLM 调用、本地回退生成和推荐解释服务骨架
- [X] T010 在 `backend/app/main.py` 增加助手相关 API 路由骨架，并只返回明确的未实现/空态响应
- [X] T011 在 `frontend/src/api/schedulerApi.ts` 增加助手 API 客户端函数
- [X] T012 在 `frontend/src/domain/resourceAssistant.ts` 增加资源方案、状态、指标和推荐解释的前端领域 helper 骨架
- [X] T013 在 `.local.env.example` 增加 AI 资源方案生成和推荐解释的占位配置项，不写入真实密钥
- [X] T014 [P] 在 `backend/tests/test_ai_resource_scheduling_assistant.py` 创建测试文件和基础 fixture，复用当前默认场景

**检查点**：共享模型、配置和服务入口存在，尚未实现业务行为；后续用户故事可基于同一契约推进。

---

## Phase 3：用户故事 1 - 生成三类资源方案并完成批量求解（优先级：P1）

**目标**：用户进入助手后能看到工程画像和 AI 生成的 A/B/C 三张方案卡片，并可一次性发起三方案独立求解。

**独立测试**：使用默认或本地导入场景调用助手入口，验证画像、AI/本地回退一次性生成三方案资源配置、生成来源、参考样例、桩机按类型分类、方案校验和三方案独立求解状态。

### 用户故事 1 的测试

- [X] T015 [P] [US1] 在 `backend/tests/test_ai_resource_scheduling_assistant.py` 增加工程画像生成测试，覆盖控制墩来源、主要资源类型和连续梁摘要
- [X] T016 [P] [US1] 在 `backend/tests/test_ai_resource_scheduling_assistant.py` 增加 A/B/C AI 初始方案生成测试，覆盖经济、平衡、抢工定位、同一次生成、参考样例、生成来源和施工组织策略
- [X] T017 [P] [US1] 在 `backend/tests/test_ai_resource_scheduling_assistant.py` 增加桩机按工艺资源类型分别生成和校验数量的测试
- [X] T018 [P] [US1] 在 `backend/tests/test_ai_resource_scheduling_assistant.py` 增加三方案批量求解状态互不覆盖的测试

### 用户故事 1 的实现

- [X] T019 [US1] 在 `backend/app/services/ai_resource_scheduling_assistant.py` 实现工程画像生成，复用现有任务图、资源池、控制链和连续梁诊断来源
- [X] T020 [US1] 在 `backend/app/services/ai_resource_scheduling_assistant.py` 实现 A/B/C 资源方案生成编排，基于工程画像、约束提示和参考样例优先调用外部 LLM 一次性生成初始数值和施工组织策略，失败时使用本地回退
- [X] T021 [US1] 在 `backend/app/services/ai_resource_scheduling_assistant.py` 实现单方案场景派生，确保 `resource_pools.quantity` 与 `max_quantity` 合法
- [X] T022 [US1] 在 `backend/app/services/ai_resource_scheduling_assistant.py` 实现三方案批量求解编排，任一方案失败不得覆盖其他方案
- [X] T023 [US1] 在 `backend/app/main.py` 接入助手初始化和批量求解接口
- [X] T024 [US1] 在 `frontend/src/features/resourceAssistant/ResourceAssistantPanel.tsx` 创建助手页面主体，展示工程画像、方案卡片和求解按钮
- [X] T025 [US1] 在 `frontend/src/app/App.tsx` 接入 AI资源配置与排程优化助手入口和基础状态管理
- [X] T026 [US1] 在 `frontend/src/domain/resourceAssistant.ts` 实现方案卡片资源展示、求解状态标签和不可用资源提示

**检查点**：用户故事 1 可独立演示工程画像、AI 初始 A/B/C 方案、方案校验和三方案求解状态。

---

## Phase 4：用户故事 2 - 对比三方案核心指标（优先级：P1）

**目标**：项目经理能通过核心指标表横向比较三方案的工期、控制墩、连续梁、资源利用、等待、转场和演示成本。

**独立测试**：完成三方案求解后，验证指标对比表包含全部必需指标，且不可用指标给出原因。

### 用户故事 2 的测试

- [X] T027 [P] [US2] 在 `backend/tests/test_ai_resource_scheduling_assistant.py` 增加总工期、完工日期和求解状态指标测试
- [X] T028 [P] [US2] 在 `backend/tests/test_ai_resource_scheduling_assistant.py` 增加控制墩释放和连续梁开工/展开指标测试
- [X] T029 [P] [US2] 在 `backend/tests/test_ai_resource_scheduling_assistant.py` 增加资源类型利用率、平均等待和最大等待指标测试
- [X] T030 [P] [US2] 在 `backend/tests/test_ai_resource_scheduling_assistant.py` 增加转场惩罚和演示成本估算测试
- [X] T031 [P] [US2] 在 `backend/tests/test_ai_resource_scheduling_assistant.py` 增加不可行或未知方案指标不可用原因测试

### 用户故事 2 的实现

- [X] T032 [US2] 在 `backend/app/services/ai_resource_scheduling_assistant.py` 实现总工期、预计完工日期和状态指标汇总
- [X] T033 [US2] 在 `backend/app/services/ai_resource_scheduling_assistant.py` 实现控制墩释放时间和连续梁开工/全部展开时间派生
- [X] T034 [US2] 在 `backend/app/services/ai_resource_scheduling_assistant.py` 实现按资源类型的利用率和等待指标汇总
- [X] T035 [US2] 在 `backend/app/services/ai_resource_scheduling_assistant.py` 实现演示转场惩罚汇总，基于现有连续性诊断且标识为诊断口径
- [X] T036 [US2] 在 `backend/app/services/ai_resource_scheduling_assistant.py` 实现演示默认价格成本估算，并标识 `demo_default_price`
- [X] T037 [US2] 在 `frontend/src/features/resourceAssistant/MetricComparisonTable.tsx` 创建核心指标对比表组件
- [X] T038 [US2] 在 `frontend/src/domain/resourceAssistant.ts` 实现指标格式化、不可用原因和来源标签
- [X] T039 [US2] 在 `frontend/src/features/resourceAssistant/ResourceAssistantPanel.tsx` 接入指标对比表和方案状态刷新

**检查点**：用户故事 2 可独立证明三方案核心指标可比较，并明确区分求解字段、派生诊断和演示估算。

---

## Phase 5：用户故事 3 - 查看甘特图、控制墩专项视图和资源利用（优先级：P2）

**目标**：计划工程师能在三方案间切换，查看项目甘特/资源占用、控制墩专项链路和资源利用分析。

**独立测试**：选择任一方案后，视图展示该方案任务和资源；切换方案后视图刷新，不沿用旧方案数据。

### 用户故事 3 的测试

- [X] T040 [P] [US3] 在 `backend/tests/test_ai_resource_scheduling_assistant.py` 增加控制墩专项任务链筛选测试
- [X] T041 [P] [US3] 在 `backend/tests/test_ai_resource_scheduling_assistant.py` 增加无控制墩或无连续梁任务时专项视图空态数据测试
- [X] T042 [P] [US3] 在 `frontend/src/features/resourceAssistant/ResourceAssistantPanel.tsx` 所在区域补充手动验证注释或测试钩子，确保方案切换可定位当前方案视图

### 用户故事 3 的实现

- [X] T043 [US3] 在 `backend/app/services/ai_resource_scheduling_assistant.py` 实现控制墩专项视图数据派生，包含下部结构到连续梁相关任务链
- [X] T044 [US3] 在 `backend/app/services/ai_resource_scheduling_assistant.py` 实现专项视图空态原因和等待区间摘要
- [X] T045 [US3] 在 `frontend/src/features/resourceAssistant/PlanVisualTabs.tsx` 创建整体计划、资源占用、控制墩专项三个视图切换
- [X] T046 [US3] 在 `frontend/src/features/resourceAssistant/ControlPierFocusView.tsx` 创建控制墩专项视图组件
- [X] T047 [US3] 在 `frontend/src/features/resourceAssistant/ResourceUtilizationView.tsx` 创建资源利用率和空闲风险组件
- [X] T048 [US3] 在 `frontend/src/features/resourceAssistant/ResourceAssistantPanel.tsx` 接入方案选择状态，使图表和专项视图跟随选中方案刷新

**检查点**：用户故事 3 可独立演示任一方案的可视化排程和控制墩专项分析。

---

## Phase 6：用户故事 4 - 基于求解结果生成 AI 推荐解释（优先级：P2）

**目标**：系统基于求解指标和轻量规则确定推荐方案，MVP 不做复杂推荐优化；AI 负责解释推荐证据、风险和边际收益；外部大模型同时服务三方案初始生成和推荐解释，且必须支持本地回退。

**独立测试**：在不同指标组合下验证推荐规则命中；无外部大模型配置时本地方案生成和本地解释可用；外部调用失败时回退。

### 用户故事 4 的测试

- [X] T049 [P] [US4] 在 `backend/tests/test_ai_resource_scheduling_assistant.py` 增加方案 B 满足节点且 C 边际收益低时推荐 B 的测试
- [X] T050 [P] [US4] 在 `backend/tests/test_ai_resource_scheduling_assistant.py` 增加只有方案 C 满足强节点时推荐 C 的测试
- [X] T051 [P] [US4] 在 `backend/tests/test_ai_resource_scheduling_assistant.py` 增加无可比较结果时不推荐的测试
- [X] T052 [P] [US4] 在 `backend/tests/test_ai_resource_scheduling_assistant.py` 增加本地解释至少引用 3 个指标证据的测试
- [X] T053 [P] [US4] 在 `backend/tests/test_ai_resource_scheduling_assistant.py` 增加外部大模型配置缺失或失败时回退本地方案生成和本地解释的测试

### 用户故事 4 的实现

- [X] T054 [US4] 在 `backend/app/services/ai_resource_explainer.py` 实现确定性推荐规则，覆盖强节点优先、C 边际收益低、A 控制墩等待长和无推荐场景
- [X] T055 [US4] 在 `backend/app/services/ai_resource_explainer.py` 实现本地模板化解释，至少输出推荐理由、风险、瓶颈和边际收益
- [X] T056 [US4] 在 `backend/app/services/ai_resource_explainer.py` 实现外部大模型调用适配器，支持方案生成和推荐解释两类请求，读取本地环境配置并隐藏密钥
- [X] T057 [US4] 在 `backend/app/services/ai_resource_scheduling_assistant.py` 将推荐解释接入批量求解响应，确保推荐结论先于 AI 文案确定
- [X] T058 [US4] 在 `frontend/src/features/resourceAssistant/RecommendationPanel.tsx` 创建推荐解释组件，展示推荐状态、证据、风险和 LLM 状态
- [X] T059 [US4] 在 `frontend/src/domain/resourceAssistant.ts` 实现推荐解释和 LLM 状态格式化
- [X] T060 [US4] 在 `frontend/src/features/resourceAssistant/ResourceAssistantPanel.tsx` 接入推荐解释区域，无求解结果时不展示推荐

**检查点**：用户故事 4 可独立证明推荐可复盘，AI 解释不越权。

---

## Phase 7：用户故事 5 - 调整资源数量并重新求解（优先级：P3）

**目标**：用户能在 AI 初始方案基础上调整资源数量，系统标记旧结果失效，并支持单方案或全量重新求解。

**独立测试**：修改方案 B 的连续梁班组数量后，方案 B 和推荐解释失效；重算后更新方案 B，方案 A/C 不被覆盖。

### 用户故事 5 的测试

- [X] T061 [P] [US5] 在 `backend/tests/test_ai_resource_scheduling_assistant.py` 增加资源数量调整后 `max_quantity` 合法化测试
- [X] T062 [P] [US5] 在 `backend/tests/test_ai_resource_scheduling_assistant.py` 增加单方案重算不覆盖其他方案结果的测试
- [X] T063 [P] [US5] 在 `frontend/src/domain/resourceAssistant.ts` 补充资源调整后失效状态的可验证 helper 测试或构建期校验

### 用户故事 5 的实现

- [X] T064 [US5] 在 `backend/app/services/ai_resource_scheduling_assistant.py` 实现资源方案更新与失效标记
- [X] T065 [US5] 在 `backend/app/main.py` 接入资源方案更新或单方案重算入口
- [X] T066 [US5] 在 `frontend/src/features/resourceAssistant/ResourcePlanCard.tsx` 创建可编辑资源数量控件
- [X] T067 [US5] 在 `frontend/src/features/resourceAssistant/ResourceAssistantPanel.tsx` 实现资源调整后的结果失效、重新求解和状态刷新
- [X] T068 [US5] 在 `frontend/src/domain/resourceAssistant.ts` 实现资源数量校验、自动同步 `max_quantity` 和失效状态 helper

**检查点**：用户故事 5 可独立演示调整资源、失效旧结果、重算并更新对比。

---

## Phase 8：收尾与横切事项

**目标**：完成验证、文档同步和门禁检查。

- [ ] T069 [P] 按需更新 `docs/排程算法当前实现交底文档_v1.2.md`，说明三方案助手指标中哪些是求解结果、哪些是诊断或演示估算
- [X] T070 [P] 按需新增 `docs/AI资源配置与排程优化助手验证说明.md`，记录 Demo 使用方式、LLM 配置和验收口径
- [X] T071 运行 `.\.venv\Scripts\python.exe -m pytest backend\tests\test_ai_resource_scheduling_assistant.py -q`
- [X] T072 运行 `.\.venv\Scripts\python.exe -m pytest backend\tests\test_scheduler.py -q`
- [X] T073 运行 `npm.cmd run build`
- [ ] T074 按 `specs/022-ai-resource-scheduling-assistant/quickstart.md` 完成默认闭环、参考样例非固定方案、桩机分类、控制墩视图、资源调整、LLM 回退和 LLM 启用验证
- [X] T075 运行 `git diff --check -- .specify specs backend frontend .local.env.example docs`
- [X] T076 检查 `AGENTS.md` 和 `.specify/memory/constitution.md` 门禁仍满足本功能要求

---

## 依赖与执行顺序

### 阶段依赖

- **Phase 1 准备**：无依赖。
- **Phase 2 基础能力**：依赖 Phase 1，阻塞所有用户故事。
- **US1**：依赖 Phase 2，是 MVP 的第一闭环。
- **US2**：依赖 US1 的三方案结果，是推荐解释和可视化的指标基础。
- **US3**：依赖 US1，可与 US4 的部分前端工作并行，但控制墩专项指标最好复用 US2 派生结果。
- **US4**：依赖 US2 的指标对比。
- **US5**：依赖 US1 的方案状态和 US2 的对比刷新。
- **收尾**：依赖目标用户故事完成。

### 用户故事依赖

- **US1（P1）**：工程画像、AI 初始方案、批量求解。
- **US2（P1）**：核心指标对比，依赖 US1 的结果容器。
- **US3（P2）**：可视化和专项视图，依赖 US1，部分依赖 US2 指标。
- **US4（P2）**：推荐解释，依赖 US2。
- **US5（P3）**：资源调整和重算，依赖 US1/US2。

### 并行机会

- T003、T004、T005 可并行。
- T006、T007、T008、T009、T011、T012、T014 可在 Phase 2 内并行，但模型命名需先对齐。
- US1 的 T015、T016、T017、T018 可并行。
- US2 的 T027、T028、T029、T030、T031 可并行。
- US4 的 T049、T050、T051、T052、T053 可并行。
- 前端组件任务可与后端测试任务并行，但最终需要统一契约验证。

## 并行示例：用户故事 2

```text
Task: "T027 在 backend/tests/test_ai_resource_scheduling_assistant.py 增加总工期、完工日期和求解状态指标测试"
Task: "T028 在 backend/tests/test_ai_resource_scheduling_assistant.py 增加控制墩释放和连续梁开工/展开指标测试"
Task: "T029 在 backend/tests/test_ai_resource_scheduling_assistant.py 增加资源类型利用率、平均等待和最大等待指标测试"
Task: "T030 在 backend/tests/test_ai_resource_scheduling_assistant.py 增加转场惩罚和演示成本估算测试"
Task: "T031 在 backend/tests/test_ai_resource_scheduling_assistant.py 增加不可行或未知方案指标不可用原因测试"
```

## 实施策略

### MVP 优先

1. 完成 Phase 1 和 Phase 2。
2. 完成 US1，证明工程画像、A/B/C 方案和批量求解闭环。
3. 完成 US2，证明核心指标对比可用。
4. 停下演示，不先做复杂视觉和 AI 解释扩展。

### 增量交付

1. 先后端服务与契约，保证数据可测。
2. 再前端接入，保证主流程可用。
3. 再增加控制墩专项视图和推荐解释。
4. 最后增加用户调整资源后的重算能力。

### 并行团队策略

1. 一人负责后端服务与测试，一人负责前端组件和状态管理。
2. 指标契约稳定后，前端可用 mock 响应并行开发。
3. 推荐解释在指标对比稳定后独立接入。

## 备注

- 不得在用户确认 `$speckit-analyze` 前开始执行这些实现任务。
- 任务实施时必须保护当前工作区已有未提交改动，不得重置或覆盖无关文件。
- `.local.env` 只允许用户本地创建；代码和文档只能提供 `.local.env.example` 占位配置。

# 任务清单：AI 多方案按工点推进资源

**输入**：`03-requirements/specs/053-ai-workpoint-resource-comparison/` 中的 `spec.md`、`plan.md`、`research.md`、`data-model.md`、`contracts/` 和 `quickstart.md`

**实施门禁**：本清单及一致性结果须经用户确认后，方可执行 `$speckit-implement`。

## Phase 1：共享契约基础

**目标**：先建立所有故事共同依赖的目标工点身份与兼容模型。

- [x] T001 在 `04-demo/backend/app/contracts/_models.py` 为 `ResourceAssistantInitialRequest` 增加必填 `target_workpoint_id`，为 `ResourceAssistantPlan` 增加历史兼容可空的 `target_workpoint_id` 和 `target_workpoint_name`，并保持现有计划快照可反序列化
- [x] T002 [P] 在 `04-demo/frontend/src/contracts/scheduler.ts` 同步初始化请求与资源方案目标工点字段，保持历史方案字段可空、新请求字段必填
- [x] T003 [P] 在 `04-demo/backend/tests/test_contracts_assistants.py` 增加新请求必填、方案历史缺失字段兼容和 OpenAPI 字段形态测试

**检查点**：前后端共享字段和历史读取策略一致，后续故事可使用稳定目标工点身份。

---

## Phase 2：用户故事 1 - 先选择要推进资源的工点（P1）

**目标**：用户必须显式选择当前项目的一个桥梁工点，页面和后端共同阻止无选择、无效身份或无可调资源的方案生成。

**独立测试**：双工点场景首次进入不自动选择且不能生成；选择有效工点后可生成并持续显示稳定身份；同名工点可区分；无工点、未知工点或无可调资源返回明确状态。

### 测试

- [x] T004 [P] [US1] 在 `04-demo/backend/tests/test_ai_resource_scheduling_assistant.py` 增加未传目标工点、未知工点、非桥梁工点和目标工点无合法可调本地池的初始化失败测试
- [x] T005 [P] [US1] 在 `04-demo/backend/tests/test_assistant_routes.py` 验证目标工点范围错误统一映射为 422 且保留可行动错误信息
- [x] T006 [P] [US1] 在 `04-demo/frontend/tests/resourceAssistantWorkpointSelection.test.mjs` 增加工点列表、初始未选择、生成门禁、同名选项区分和选择后请求携带稳定 ID 的前端契约测试

### 实现

- [x] T007 [US1] 在 `04-demo/backend/app/services/ai_resource_scheduling_assistant.py` 实现当前场景桥梁工点解析、稳定身份校验和目标工点合法可调本地资源投影，空集合时阻断初始化
- [x] T008 [US1] 在 `04-demo/frontend/src/features/resourceAssistant/ResourceAssistantPanel.tsx` 增加目标工点选择状态、未选择/无工点空态、生成门禁、初始化请求字段和当前目标工点可见说明
- [x] T009 [P] [US1] 在 `04-demo/frontend/src/features/resourceAssistant/styles.css` 为工点选择区、范围说明和窄屏布局补充现有设计体系内的最小样式

**检查点**：无需生成或求解即可独立验证工点选择与前后端门禁。

---

## Phase 3：用户故事 2 - 只推进所选工点资源并计算全项目排程（P1）

**目标**：LLM、本地回退和人工调整都只能改变目标工点本地资源；其他工点和共享池逐池冻结，求解、指标、推荐、详情与基准仍为全项目口径。

**独立测试**：双工点加共享池样例中，为 A 生成三方案后只有 A 本地池形成三档差异；B 和共享池保持不变；越权更新被拒绝；任一方案求解结果覆盖 A、B 全量任务，并可完成比较、推荐、详情和基准确认。

### 测试

- [x] T010 [P] [US2] 在 `04-demo/backend/tests/test_ai_resource_scheduling_assistant.py` 增加双工点加同类型多池/共享池样例，覆盖 LLM 合法输出、越权输出纠错后回退、确定性三档、逐池冻结、数量 0 与 `max_quantity` 边界
- [x] T011 [US2] 在 `04-demo/backend/tests/test_ai_resource_scheduling_assistant.py` 增加更新和求解边界测试，覆盖仅目标 `pool.id + workpoint_id` 可改、旧按类型更新拒绝、共享池/其他工点/未知池/停用池拒绝及全项目任务覆盖
- [x] T012 [P] [US2] 在 `04-demo/backend/tests/test_progress_forecast.py` 增加带目标工点方案可确认基准、缺失或失效目标身份不可确认且历史快照不删除的测试
- [x] T013 [P] [US2] 在 `04-demo/frontend/tests/resourceAssistantPoolIdentity.test.mjs` 增加方案卡只展示目标工点本地资源、共享池及其他工点无输入框、仍按 `pool.id` 更新的测试
- [x] T014 [P] [US2] 在 `04-demo/frontend/tests/resourceAssistantWorkpointSelection.test.mjs` 增加全项目口径说明、目标工点标签传递到方案/详情和生成后主流程保持可用的契约测试

### 实现

- [x] T015 [US2] 在 `04-demo/backend/app/services/ai_resource_scheduling_assistant.py` 将目标工点与可调池写入 LLM 上下文和生成指纹，并使原始输出校验只接受目标工点已有本地池的非负整数数量与逐记录上限
- [x] T016 [US2] 在 `04-demo/backend/app/services/ai_resource_explainer.py` 调整三方案提示与输出说明，明确只输出目标工点可调池、保留完整项目画像并禁止修改共享池和其他工点
- [x] T017 [US2] 在 `04-demo/backend/app/services/ai_resource_scheduling_assistant.py` 收敛确定性回退与三方案合并逻辑，只为目标工点形成经济/平衡/抢工梯度并把结果合回完整资源快照，非目标池逐字段保持输入值
- [x] T018 [US2] 在 `04-demo/backend/app/services/ai_resource_scheduling_assistant.py` 强制更新、求解、比较和推荐的目标工点一致性，求解前拒绝非目标资源篡改并将目标身份纳入方案输入指纹，同时保持现有全项目严格固定资源求解入口和 15 秒预算
- [x] T019 [US2] 在 `04-demo/backend/app/services/progress_forecast.py` 为新基准确认链路校验方案目标工点存在于当前项目版本，拒绝缺失/失效身份但保留既有历史计划只读能力
- [x] T020 [US2] 在 `04-demo/frontend/src/domain/resourceAssistant.ts` 增加按目标工点筛选可编辑本地资源、稳定标签和范围一致性辅助函数，禁止按资源类型合并同类型多池
- [x] T021 [US2] 在 `04-demo/frontend/src/features/resourceAssistant/ResourcePlanCard.tsx` 只渲染目标工点本地资源输入，展示目标工点与“全项目排程结果”说明，保留现有求解、详情和基准操作
- [x] T022 [US2] 在 `04-demo/frontend/src/features/resourceAssistant/ResourceAssistantPanel.tsx` 将目标工点贯穿更新、求解、比较、推荐、详情和基准确认，并拒绝没有目标身份的当前方案进入操作链路

**检查点**：完成“选择 A—生成三方案—全项目求解—比较/推荐—详情—确认基准”的最小完整闭环。

---

## Phase 4：用户故事 3 - 切换工点时清理旧比选状态（P2）

**目标**：切换工点或项目版本后，旧会话立即失效，任何迟到响应都不能写入新工点状态。

**独立测试**：A 已生成/求解或请求进行中时切换 B，A 的方案、结果、比较、推荐、详情、下载和本轮基准状态全部清空，A 的迟到响应不能覆盖 B；项目版本变化不按同名恢复选择。

### 测试

- [x] T023 [P] [US3] 在 `04-demo/frontend/tests/resourceAssistantWorkpointSelection.test.mjs` 增加工点切换、项目版本变化、详情退出、全部会话状态清空和生成/求解/更新/比较/推荐迟到响应隔离测试
- [x] T024 [P] [US3] 在 `04-demo/backend/tests/test_ai_resource_scheduling_assistant.py` 增加目标工点进入生成与求解指纹、不同目标工点方案不可混合比较/推荐及历史无身份方案不可复用测试

### 实现

- [x] T025 [US3] 在 `04-demo/frontend/src/features/resourceAssistant/ResourceAssistantPanel.tsx` 以 `scenarioFingerprint + targetWorkpointId` 建立会话范围令牌，切换工点或项目版本时原子清空全部旧状态并丢弃所有迟到响应
- [x] T026 [US3] 在 `04-demo/backend/app/services/ai_resource_scheduling_assistant.py` 将目标工点身份纳入生成/求解当前性校验并拒绝跨工点方案、结果、比较和推荐组合

**检查点**：跨工点和跨项目版本的当前状态复用次数为 0。

---

## Phase 5：共享契约收口与完成验证

**目标**：同步真实 API/架构基线并执行一次风险匹配的完整验证，不重复各故事定向检查。

- [x] T027 在 `04-demo/backend/tests/test_architecture_api_contract.py` 更新 AI 初始化请求、资源方案和基准确认的共享契约断言，并用 `04-demo/backend/scripts/capture_architecture_baseline.py` 更新 `04-demo/backend/tests/fixtures/architecture/backend-baseline.json`
- [x] T028 [P] 在 `04-demo/frontend/tests/contractsCompatibility.test.mjs` 和 `04-demo/frontend/tests/fixtures/architecture/frontend-baseline.json` 同步前端共享类型基线，确认历史可空方案字段与新请求必填字段一致
- [ ] T029 依次运行 `python -m pytest 04-demo/backend/tests/test_ai_resource_scheduling_assistant.py 04-demo/backend/tests/test_assistant_routes.py 04-demo/backend/tests/test_contracts_assistants.py 04-demo/backend/tests/test_progress_forecast.py -q`、`npm.cmd run typecheck`、`npm.cmd --workspace 04-demo/frontend test`、`npm.cmd run build`、OpenAPI YAML 解析、`python 00-governance/repository-tools/validate_docs.py` 和 `git diff --check`，并按 `03-requirements/specs/053-ai-workpoint-resource-comparison/quickstart.md` 记录双工点全项目闭环证据

  完成验证证据：053 定向后端与架构契约共 19 项通过；053 前端与共享契约共 10 项通过；类型检查、生产构建、OpenAPI YAML、14 份文档校验及差异空白检查通过。完整前端套件在已有 `resourceWorkpointRuntime.test.mjs` T015 长耗时用例处失败并触发 120 秒总超时；旧 `test_ai_resource_scheduling_assistant.py` 仍按全项目 AI 调整与默认资源池假设构造请求，与本功能的新必填工点契约不兼容，故 T029 保持未勾选。

## Phase 6：项目主数据工点来源修正

- [x] T030 修正 `spec.md` 与 `plan.md`，明确 AI 工点清单以 `project_data_version_id` 对应的项目主数据快照为权威来源
- [x] T031 在 `04-demo/frontend/src/app/Workspace.tsx` 与 `04-demo/frontend/src/features/resourceAssistant/ResourceAssistantPanel.tsx` 将完整权威桥梁工点清单传入 AI 下拉，禁止回退到旧场景中的不完整桥梁列表
- [x] T032 在 `04-demo/backend/app/api/routers/assistants.py` 与基准确认入口复用项目主数据排程投影，使初始化、求解和确认基准使用同一完整项目模型
- [x] T033 增加前后端回归测试并运行定向测试、类型检查、生产构建和差异检查

  修正验证证据：当前项目主数据版本返回 31 个工点，其中 13 个为 `bridge_supported` 桥梁工点；前端定向 5 项、后端定向 16 项通过，类型检查与生产构建通过。以旧场景中不存在的 `WP-BR-XR02` 调用初始化时，后端已进入“无本地资源”校验而非“未知工点”，证明目标身份来自项目主数据投影。

---

## 依赖与执行顺序

### 阶段依赖

1. **Phase 1** 建立共享字段，阻塞全部用户故事。
2. **US1** 依赖 Phase 1，完成目标工点选择与初始化门禁。
3. **US2** 依赖 US1 的目标身份和初始化链路，完成核心资源冻结及全项目闭环。
4. **US3** 依赖 US1/US2 的完整异步链路，完成跨工点失效隔离。
5. **Phase 5** 依赖所有故事实现，统一更新契约基线并运行一次完成验证。

### 并行机会

- T002 与 T003 可在 T001 模型形态确定后分别处理前端类型和后端契约测试。
- US1 的 T004、T005、T006 可并行编写；T009 与后端 T007 可并行实现。
- US2 的后端生成测试 T010、基准测试 T012 和前端测试 T013/T014 位于不同文件，可并行；实现阶段同一 `ai_resource_scheduling_assistant.py` 的 T015、T017、T018 必须串行。
- US3 的前后端测试 T023、T024 可并行；实现 T025、T026 位于不同端可并行。
- T028 可与 T027 并行准备，但最终基线确认及 T029 必须在全部实现后执行。

## 需求覆盖与一致性映射

| 来源 | 覆盖任务 |
|---|---|
| US1；FR-001～FR-005；同名、无工点、未选择、身份无效边界；SC-001、SC-006 | T004～T009 |
| US2；FR-006～FR-015、FR-021～FR-022；共享池冻结、数量 0、无可调资源、全项目口径边界；SC-002～SC-004、SC-007～SC-008 | T010～T022、T027～T029 |
| US3；FR-016～FR-020；切换、版本变化、迟到响应和历史兼容边界；SC-005 | T023～T026、T029 |
| 共享字段、API/前端契约与计划快照兼容 | T001～T003、T012、T019、T027～T029 |
| `pool.id`、同类型多池不合并、15 秒预算和全项目任务不变量 | T010～T011、T017～T021、T024、T029 |

一致性结论：22 条 FR、8 条 SC、3 个用户故事及全部显式边界均有实现任务或可复现验证任务；未发现无来源任务、术语冲突、重复全套验证或计划外路径。

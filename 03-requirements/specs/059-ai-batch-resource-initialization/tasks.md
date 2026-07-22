# 任务清单：AI 批量初始化工点工装资源

**输入**：`03-requirements/specs/059-ai-batch-resource-initialization/` 中的 `spec.md`、`plan.md`、`research.md`、`data-model.md`、`contracts/` 和 `quickstart.md`

**实施门禁**：本清单及一致性结果须经用户确认后，方可执行 `$speckit-implement`。

## Phase 1：共享契约基础

**目标**：先建立前后端、API 与真实模型状态共同依赖的批量初始化契约。

- [x] T001 在 `04-demo/backend/app/contracts/_models.py`、`04-demo/backend/app/contracts/assistants.py` 和 `04-demo/backend/app/contracts/__init__.py` 增加并导出 AI 工点资源初始化请求、响应、批次摘要及模型推荐结构，复用现有 `ScenarioInput`、`ResourcePool`、`ResourceAssistantLlmConfigStatus` 和 `ValidationMessage`
- [x] T002 [P] 在 `04-demo/frontend/src/contracts/scheduler.ts` 同步初始化请求、响应和摘要类型，确保前端契约不包含 API Key、endpoint 或 Authorization 字段
- [x] T003 [P] 在 `04-demo/backend/tests/test_contracts_assistants.py` 增加请求必填场景、响应新增池、正整数数量、摘要字段和 OpenAPI 形态测试
- [x] T004 [P] 在 `04-demo/frontend/tests/contractsCompatibility.test.mjs` 增加前端共享类型与 059 OpenAPI 契约一致性及密钥字段缺失测试

**检查点**：共享模型可表达“当前场景输入—整批新增池—逐工点摘要—真实模型状态”，且没有密钥穿透前端的路径。

---

## Phase 2：用户故事 1 - 一键生成全部桥梁工点的初始化资源（P1）

**目标**：一次点击使用当前项目主数据版本、结构物汇总和合法候选资源调用真实 LLM，为全部需要补充的桥梁工点生成可验证的初始化资源。

**独立测试**：双工点场景中，后端只向模型发送权威结构摘要和各工点缺失候选集合；模型一次返回后生成两个工点的本地资源，不包含已有、共享、跨工点、未知或排除资源。

### 测试

- [x] T005 [P] [US1] 在 `04-demo/backend/tests/test_ai_workpoint_resource_initializer.py` 建立双工点/多结构/部分候选样例，覆盖结构汇总、资源目录交集、`precast_beam_team` 排除、已有 `工点 ID + 资源类型` 排除、无候选工点摘要和稳定排序
- [x] T006 [US1] 在 `04-demo/backend/tests/test_ai_workpoint_resource_initializer.py` 增加真实 OpenAI-compatible 客户端测试，覆盖完整环境配置、单批 JSON 请求、模型和候选上下文、响应解析以及请求/错误不泄露 API Key
- [x] T007 [P] [US1] 在 `04-demo/backend/tests/test_assistant_routes.py` 增加新接口项目主数据物化、成功响应、输入 422、模型 503 和项目版本错误映射测试
- [x] T008 [P] [US1] 在 `04-demo/frontend/tests/aiResourceInitialization.test.mjs` 增加按钮位置、项目工点未就绪门禁、单次请求、防重复点击和处理中状态契约测试

### 实现

- [x] T009 [US1] 在 `04-demo/backend/app/scenario_data.py` 收敛后端资源目录与工点候选投影，加入与资源配置页一致的排除集合，并保证候选中文标签、默认日历和适用工艺稳定可复现
- [x] T010 [US1] 在 `04-demo/backend/app/services/ai_workpoint_resource_initializer.py` 实现权威桥梁遍历、结构物/构件聚合、缺失候选计算、模型上下文、输入指纹、稳定资源池 ID 和逐工点摘要构造
- [x] T011 [US1] 在 `04-demo/backend/app/services/ai_resource_explainer.py` 增加批量初始化专用严格 LLM 调用与输出提取，要求外部 provider、endpoint、model、API Key 完整，禁止本地回退，并支持一次结构化纠错请求
- [x] T012 [US1] 在 `04-demo/backend/app/api/routers/assistants.py` 增加 `POST /api/ai-resource-assistant/initialize-workpoint-resources`，先物化当前项目主数据，再调用初始化服务并区分 422、503 和项目版本错误
- [x] T013 [P] [US1] 在 `04-demo/frontend/src/api/_schedulerApi.ts` 和 `04-demo/frontend/src/api/resourceAssistantApi.ts` 增加批量初始化 API 客户端并只向本地后端发送当前场景
- [x] T014 [US1] 在 `04-demo/frontend/src/features/resources/ResourcesTab.tsx` 和 `04-demo/frontend/src/features/resources/styles.css` 增加“AI快速配置工装”按钮、加载/禁用状态和调用入口，保持现有工点标签与资源表格布局

**检查点**：在不保存、不求解的条件下，可独立验证一次真实模型调用生成全部可处理桥梁工点的合法新增资源响应。

---

## Phase 3：用户故事 2 - 在现有逐工点页面检查并统一保存（P1）

**目标**：将整批新增池一次性合入当前页面临时状态，用户继续逐工点检查和人工调整，最后复用现有保存入口一次性持久化。

**独立测试**：推荐成功后 A、B 工点各自只显示自己的新增资源；页面不出现全量预览或额外保存入口；保存前仅为脏状态，人工修改后点击现有保存可恢复整批最终配置。

### 测试

- [x] T015 [P] [US2] 在 `04-demo/frontend/tests/aiResourceInitialization.test.mjs` 增加一次状态合并、按池 ID 与 `工点 ID + 资源类型` 防重、逐工点展示、无全量预览、推荐后脏状态和不自动保存测试
- [x] T016 [P] [US2] 在 `04-demo/frontend/tests/resourceWorkpointScope.test.mjs` 增加 AI 新增资源沿用现有数量/上限/启停/移除控件、人工修改后完整保存及重新加载恢复测试

### 实现

- [x] T017 [US2] 在 `04-demo/frontend/src/domain/resources.ts` 增加 AI 新增资源池原子合并和语义指纹辅助函数，碰到 ID 或 `工点 ID + 资源类型` 冲突时整批拒绝且不改变原数组
- [x] T018 [US2] 在 `04-demo/frontend/src/app/Workspace.tsx` 增加一次性批量资源合并回调，把成功推荐追加到当前 `scenario.resource_pools` 并复用现有脏状态、保存和场景结果失效链路
- [x] T019 [US2] 在 `04-demo/frontend/src/features/resources/ResourcesTab.tsx` 将成功响应交给 Workspace 原子合并，显示新增数量、涉及工点、无需补充工点和模型名称摘要，并保持现有逐工点编辑与单一保存按钮

**检查点**：完成“AI推荐—逐工点检查—人工调整—现有保存—重新加载”的独立闭环，推荐成功本身不会持久化。

---

## Phase 4：用户故事 3 - 保护已有配置和真实模型边界（P1）

**目标**：已有池逐字段冻结；模型配置、服务、输出、版本或前端状态任一失败时整批零应用，且密钥不进入请求之外的敏感边界。

**独立测试**：部分已有资源场景中，分别模拟缺少密钥、401、超时、非法 JSON、未知工点、未知/重复资源、非整数、0、负数、上限倒置、部分非法和迟到响应；每种情况下完整资源快照均与调用前一致。

### 测试

- [x] T020 [US3] 在 `04-demo/backend/tests/test_ai_workpoint_resource_initializer.py` 增加已有池逐字段冻结、未知/额外/缺失工点、未知/重复资源、非法数量、上限倒置、部分合法批次、一次纠错和纠错失败零输出测试
- [x] T021 [P] [US3] 在 `04-demo/backend/tests/test_ai_resource_scheduling_assistant.py` 增加批量初始化严格配置边界，覆盖 local provider、缺 endpoint/model/API Key、401/403、超时、非 JSON 和脱敏错误，同时确认既有三方案本地回退行为不被修改
- [x] T022 [US3] 在 `04-demo/frontend/tests/aiResourceInitialization.test.mjs` 增加项目版本切换、资源状态变化、迟到响应、接口失败、合并冲突和重试测试，验证页面资源零变化且现有未保存人工修改保留

### 实现

- [x] T023 [US3] 在 `04-demo/backend/app/services/ai_workpoint_resource_initializer.py` 完成全批完整性/越权/数量校验、已有池深度冻结核对、一次纠错后的原子失败和不含凭据诊断，并只在全部合法时构造新增池
- [x] T024 [US3] 在 `04-demo/frontend/src/features/resources/ResourcesTab.tsx` 与 `04-demo/frontend/src/app/Workspace.tsx` 绑定 `project_data_version_id + resource semantic fingerprint` 请求令牌，丢弃迟到或过期响应，失败和冲突时显示可行动错误且不合并任何池
- [x] T025 [P] [US3] 在 `.local.env.example` 和 `README.md` 说明本功能复用 `AI_RESOURCE_ASSISTANT_*` 的真实模型配置、重启要求、无本地回退语义和密钥仅存 `.local.env` 的安全边界

**检查点**：所有失败态、越权态和并发变化均满足“已有资源差异 0、新增资源数量 0、密钥暴露 0”。

---

## Phase 5：共享契约与完成验证

**目标**：同步架构基线并执行一次与本功能风险匹配的完整验证，不重复各故事定向检查。

- [x] T026 在 `04-demo/backend/tests/test_architecture_api_contract.py`、`04-demo/backend/tests/fixtures/architecture/backend-baseline.json`、`04-demo/frontend/tests/apiCompatibility.test.mjs` 和 `04-demo/frontend/tests/fixtures/architecture/frontend-baseline.json` 同步新接口与共享类型基线，确认请求只含场景、响应不含密钥且既有接口不变
- [ ] T027 依次运行 `python -m pytest 04-demo/backend/tests/test_ai_workpoint_resource_initializer.py 04-demo/backend/tests/test_assistant_routes.py 04-demo/backend/tests/test_contracts_assistants.py 04-demo/backend/tests/test_ai_resource_scheduling_assistant.py -q`、`node --test 04-demo/frontend/tests/aiResourceInitialization.test.mjs 04-demo/frontend/tests/resourceWorkpointScope.test.mjs 04-demo/frontend/tests/contractsCompatibility.test.mjs`、`npm.cmd run typecheck`、`npm.cmd run build`、059 OpenAPI YAML 解析、`python 00-governance/repository-tools/validate_docs.py` 和 `git diff --check`，并按 `03-requirements/specs/059-ai-batch-resource-initialization/quickstart.md` 记录双工点成功闭环、失败原子性与密钥检查证据

---

## 依赖与执行顺序

### 阶段依赖

1. **Phase 1** 建立共享字段，阻塞后端服务、路由和前端 API。
2. **US1** 依赖 Phase 1，完成权威输入、真实模型调用和按钮发起能力。
3. **US2** 依赖 US1 的成功响应，完成现有页面原子合并与统一保存闭环。
4. **US3** 依赖 US1/US2 的完整调用与合并链路，补齐已有资源冻结、错误、过期和安全边界。
5. **Phase 5** 依赖全部故事完成，统一更新基线并执行完成验证。

### 单个故事内部顺序

- 测试任务先于对应实现任务。
- 后端候选投影先于初始化服务；初始化服务和严格客户端完成后再接路由。
- 前端共享类型和 API 完成后再接按钮；领域原子合并先于 Workspace 和 ResourcesTab 落地。
- 同一文件的任务按编号串行，避免并行覆盖工作树已有改动。

### 并行机会

- T002、T003、T004 位于不同契约/测试文件，可在 T001 模型形态确定后并行。
- T005、T007、T008 可并行准备；T013 可与后端 T009～T012 并行。
- T015、T016 位于不同前端测试文件，可并行。
- T021、T025 可与 T020 分别在后端测试和环境文档路径并行。
- T026 的前后端断言可并行准备，但生成基线和 T027 必须在全部实现后执行。

## 需求覆盖与一致性映射

| 来源 | 覆盖任务 |
|---|---|
| US1；FR-001、FR-002、FR-003、FR-004、FR-005、FR-006、FR-007、FR-008、FR-009、FR-010；无版本、无工点、缺结构、无候选、重复点击边界；SC-001、SC-003 | T001～T014、T026～T027 |
| US2；FR-013、FR-014、FR-015、FR-017、FR-019；逐工点检查、人工调整、未保存/保存边界；SC-004 | T015～T019、T026～T027 |
| US3；FR-006、FR-007、FR-008、FR-009、FR-010、FR-011、FR-012、FR-016、FR-018、FR-019；已有池冻结、严格模型、原子失败、过期响应和密钥边界；SC-002、SC-003、SC-005、SC-006 | T020～T027 |
| 数据模型与 API 契约：请求、结构汇总、候选资源、模型输出、新增池、摘要和状态转换 | T001～T013、T017～T019、T023～T027 |
| 计划决策：真实模型无回退、后端权威投影、模型只定数量、一次纠错、原页面临时状态、目录排除一致 | T005～T025、T027 |

一致性结论：19 条 FR、6 条 SC、3 个 P1 用户故事、全部边界场景和 6 项计划决策均至少映射到一项可执行任务；未发现无来源任务、路径越界、重复全套验证、术语冲突或未解决依赖。

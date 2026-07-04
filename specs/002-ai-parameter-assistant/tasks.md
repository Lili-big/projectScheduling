# 任务清单：AI 参数输入助手

**输入**：来自 `specs/002-ai-parameter-assistant/` 的 `spec.md`、`plan.md`、`research.md`、`data-model.md`、`contracts/` 和 `quickstart.md`

**前置条件**：已完成 `/speckit-specify`、`/speckit-clarify` 和 `/speckit-plan`。本文件完成 `/speckit-analyze` 修订后，仍需用户确认才能进入实现。

**测试要求**：本功能涉及排程参数、资源模型、里程碑、前后端共享字段和跨模块状态失效，必须包含后端测试、接口契约验证、前端构建验证和可复现场景验证。

## Phase 1：准备（共享基础）

**目标**：建立可复用的测试输入、功能入口、AI adapter 边界和依赖边界，确保后续故事可独立验证。

- [X] T001 [P] 在 `backend/tests/fixtures/ai_parameter_assistant_cases.json` 创建文本、Excel、PDF、Word、图片、冲突、20 条建议批次、结构参数负向和 store 过期 fixture
- [X] T002 [P] 在 `frontend/src/features/assistant/parameter/index.ts` 创建 AI 参数助手前端 feature 导出入口
- [X] T003 在 `requirements.txt` 和 `frontend/package.json` 复核 AI adapter、Word/PDF/OCR 辅助解析和前端功能的最小依赖边界

---

## Phase 2：基础能力（阻塞前置）

**目标**：完成所有用户故事共享的数据结构、AI adapter、短期 suggestion store、服务骨架、API 类型和前端状态基础；本阶段完成前不得开始用户故事实现。

- [X] T004 在 `backend/app/models.py` 增加 `ExtractionRun`、`UploadedMaterialSummary`、`ParameterSuggestion`、`SourceEvidence`、`ConflictGroup`、`CandidateAddition`、`SuggestionStoreEntry`、`ApplicationRequest`、`ApplicationSummary` 相关 Pydantic 模型
- [X] T005 [P] 在 `frontend/src/types/scheduler.ts` 增加 AI 参数助手请求、响应、建议、冲突、证据、候选新增、短期 store 过期和应用摘要类型
- [X] T006 [P] 在 `backend/app/services/ai_parameter_materials.py` 建立资料类型识别、数量限制、大小限制和资料摘要服务骨架
- [X] T007 [P] 在 `backend/app/services/ai_parameter_ai_client.py` 建立可配置 AI adapter、结构化 JSON schema、超时、错误映射和测试 mock 注入骨架
- [X] T008 [P] 在 `backend/app/services/ai_parameter_store.py` 建立短期 suggestion store、TTL、`run_id` 查询和不保存原文件的服务骨架
- [X] T009 [P] 在 `backend/app/services/ai_parameter_assistant.py` 建立解析、冲突归并、默认选择、当前方案应用和错误汇总服务骨架
- [X] T010 在 `frontend/src/api/schedulerApi.ts` 增加 `parseAiParameterAssistant` 和 `applyAiParameterSuggestions` API 封装
- [X] T011 在 `frontend/src/domain/aiParameterAssistant.ts` 增加建议分组、默认勾选、冲突是否已解决和可应用状态的纯函数
- [X] T012 在 `backend/app/main.py` 注册 `/api/ai-parameter-assistant/parse` 和 `/api/ai-parameter-assistant/apply` 路由骨架，保持解析和应用分离

**检查点**：共享模型、类型、AI adapter、短期 store、服务骨架和 API 入口就绪，用户故事可以按优先级推进。

---

## Phase 3：用户故事 1 - 提取候选排程参数（优先级：P1）

**目标**：用户上传资料后获得按工艺工效、资源数量和里程碑分组的建议，且解析阶段不修改当前方案。

**独立测试**：使用 fixture 调用解析接口，确认返回建议包含类别、目标、值、来源证据和置信度，同时输入 `ScenarioInput` 不变。

### 用户故事 1 的测试

- [X] T013 [P] [US1] 在 `backend/tests/test_ai_parameter_assistant_parse.py` 增加解析接口契约测试，覆盖多资料输入、三类建议、来源证据、写入短期 store 和当前方案不变
- [X] T014 [P] [US1] 在 `backend/tests/test_ai_parameter_assistant_limits.py` 增加文件数量、总大小、无资料、未知类型和 AI 服务失败测试
- [X] T015 [P] [US1] 在 `backend/tests/test_ai_parameter_ai_client.py` 增加 AI adapter 配置、结构化 schema、超时、错误映射和 mock 注入测试
- [X] T016 [P] [US1] 在 `backend/tests/test_ai_parameter_assistant_scope.py` 增加结构参数替换被排除且仅可作为定位依据的负向测试

### 用户故事 1 的实现

- [X] T017 [US1] 在 `backend/app/services/ai_parameter_materials.py` 实现文本、Word、Excel、PDF、图片的资料摘要和文件级错误处理
- [X] T018 [US1] 在 `backend/app/services/ai_parameter_ai_client.py` 实现正式 AI adapter 调用、结构化响应校验和 AI 不可用错误转换
- [X] T019 [US1] 在 `backend/app/services/ai_parameter_assistant.py` 实现 AI 结构化响应到 `ParameterSuggestion` 的标准化映射，fixture/mock 仅用于测试路径
- [X] T020 [US1] 在 `backend/app/main.py` 完成 `/api/ai-parameter-assistant/parse` multipart 请求解析、限制校验、短期 store 写入和错误状态映射
- [X] T021 [US1] 在 `frontend/src/features/assistant/parameter/ParameterAssistantPanel.tsx` 实现文件上传、文本输入、解析按钮、解析状态和资料级错误展示
- [X] T022 [US1] 在 `frontend/src/app/App.tsx` 接入 `ParameterAssistantPanel.tsx`，传入当前 `ScenarioInput` 并确保解析前后不更新当前方案
- [X] T023 [US1] 在 `frontend/src/styles.css` 增加 AI 参数助手上传区、解析状态和基础建议分组样式

**检查点**：用户可以运行解析并看到三类建议；没有点击应用时当前方案不变；正式路径通过 AI adapter 解析，mock 只服务测试。

---

## Phase 4：用户故事 2 - 应用前审阅、筛选和处理建议（优先级：P1）

**目标**：用户能在一个位置按类别、置信度和冲突状态审阅建议，并在应用前解决冲突或补充低置信内容。

**独立测试**：使用包含高置信、低置信、冲突值和至少 20 条建议的 fixture，确认默认勾选、待完善、冲突处理、批量展示和应用按钮状态符合规则。

### 用户故事 2 的测试

- [X] T024 [P] [US2] 在 `backend/tests/test_ai_parameter_assistant_review.py` 增加置信度等级、默认勾选、低置信待完善、无来源不得默认勾选和 20 条建议批次测试
- [X] T025 [P] [US2] 在 `backend/tests/test_ai_parameter_assistant_conflicts.py` 增加同一参数多来源冲突、当前值冲突和冲突未解决不可应用测试

### 用户故事 2 的实现

- [X] T026 [US2] 在 `backend/app/services/ai_parameter_assistant.py` 实现置信度分层、默认勾选资格、缺字段待人工完善、20 条建议批次整理和冲突组生成
- [X] T027 [US2] 在 `frontend/src/domain/aiParameterAssistant.ts` 实现建议按类别、置信度、冲突状态和待完善状态的分组与排序，保持 20 条以上建议可批量审阅
- [X] T028 [US2] 在 `frontend/src/features/assistant/parameter/ParameterSuggestionReview.tsx` 实现建议表、置信度显示、来源证据、变更前后值和待完善区域
- [X] T029 [US2] 在 `frontend/src/features/assistant/parameter/ParameterConflictResolver.tsx` 实现冲突组展示、选择来源值、保留当前值和手动填写
- [X] T030 [US2] 在 `frontend/src/features/assistant/parameter/ParameterAssistantPanel.tsx` 接入审阅组件、默认勾选规则和应用按钮可用性判断
- [X] T031 [US2] 在 `frontend/src/styles.css` 增加建议表、置信度、冲突组、来源证据、20 条批次展示和待完善区域样式

**检查点**：所有建议在应用前可审阅；冲突不会被自动选择；低置信建议默认不选中；至少 20 条建议可一次批量审阅。

---

## Phase 5：用户故事 3 - 仅应用已选建议到当前方案（优先级：P1）

**目标**：用户确认后只把已选建议应用到当前 `ScenarioInput`，项目级配置不自动保存，旧任务图和求解结果失效。

**独立测试**：选择部分建议并调用应用接口，确认仅当前方案变化，未选建议不生效，失败项不影响其他有效项，`run_id` 过期不应用，前端旧结果被清空或标记过期。

### 用户故事 3 的测试

- [X] T032 [P] [US3] 在 `backend/tests/test_ai_parameter_assistant_apply.py` 增加工艺工效、资源数量、里程碑局部应用和未选建议不生效测试
- [X] T033 [P] [US3] 在 `backend/tests/test_ai_parameter_assistant_apply_failures.py` 增加应用失败保留原值、部分失败继续应用和应用摘要测试
- [X] T034 [P] [US3] 在 `backend/tests/test_ai_parameter_suggestion_store.py` 增加 `run_id` 查询、过期或不存在返回 410、不保存原文件和解析后应用读取短期 store 测试

### 用户故事 3 的实现

- [X] T035 [US3] 在 `backend/app/services/ai_parameter_assistant.py` 实现工艺工效建议应用到 `ScenarioInput.process_library`
- [X] T036 [US3] 在 `backend/app/services/ai_parameter_assistant.py` 实现资源数量或上限建议应用到 `ScenarioInput.resource_pools`
- [X] T037 [US3] 在 `backend/app/services/ai_parameter_assistant.py` 实现里程碑建议应用到 `ScenarioInput.milestones`，无明确类型时默认内部软里程碑
- [X] T038 [US3] 在 `backend/app/main.py` 完成 `/api/ai-parameter-assistant/apply` 从短期 store 读取建议、请求校验、410 过期处理、部分失败处理和响应状态映射
- [X] T039 [US3] 在 `frontend/src/features/assistant/parameter/ParameterAssistantPanel.tsx` 实现已选建议应用、store 过期提示、失败项展示、应用摘要和待完善数量展示
- [X] T040 [US3] 在 `frontend/src/app/App.tsx` 实现 AI 参数应用后的当前方案更新、工艺/资源/里程碑 dirty 标记、任务图/求解结果/方案对比失效处理
- [X] T041 [US3] 在 `frontend/src/api/schedulerApi.ts` 对应用接口错误进行统一错误文本映射，覆盖 400、409、410、422 和 503

**检查点**：已选建议可以安全应用到当前方案；项目级配置不会被自动保存；旧排程结果不会继续作为有效结果展示；过期 `run_id` 不会修改方案。

---

## Phase 6：用户故事 4 - 安全新增候选配置项（优先级：P2）

**目标**：AI 发现当前方案不存在的工艺、资源或里程碑时，只以候选新增项展示，用户确认后才加入当前方案。

**独立测试**：使用包含新资源、新工艺或新里程碑的 fixture，确认候选项不会静默创建；被选择后只加入当前方案，被忽略后不变。

### 用户故事 4 的测试

- [X] T042 [P] [US4] 在 `backend/tests/test_ai_parameter_assistant_candidates.py` 增加候选工艺、候选资源、候选里程碑识别和忽略不生效测试

### 用户故事 4 的实现

- [X] T043 [US4] 在 `backend/app/services/ai_parameter_assistant.py` 实现缺失目标识别为 `CandidateAddition`，禁止解析阶段自动加入方案
- [X] T044 [US4] 在 `backend/app/services/ai_parameter_assistant.py` 实现已确认候选工艺、资源和里程碑加入当前 `ScenarioInput`
- [X] T045 [US4] 在 `frontend/src/features/assistant/parameter/ParameterCandidateList.tsx` 实现候选新增项展示、确认选择、忽略和来源证据
- [X] T046 [US4] 在 `frontend/src/features/assistant/parameter/ParameterAssistantPanel.tsx` 接入 `ParameterCandidateList.tsx` 并纳入应用摘要

**检查点**：候选项默认不是正式配置；只有用户选择并应用后才进入当前方案。

---

## Phase 7：用户故事 5 - 将图片解析作为低置信度输入验证（优先级：P2）

**目标**：图片和扫描材料可作为第一期输入参与验证，但不确定图片值默认低置信或待人工核验。

**独立测试**：使用图片 fixture 解析资源数量或里程碑日期，确认来源证据指向图片，默认不自动应用不确定值。

### 用户故事 5 的测试

- [X] T047 [P] [US5] 在 `backend/tests/test_ai_parameter_assistant_images.py` 增加图片资料解析、低置信默认、不可读图片和人工核验提示测试

### 用户故事 5 的实现

- [X] T048 [US5] 在 `backend/app/services/ai_parameter_materials.py` 实现图片资料类型识别、AI 输入元数据和不可读图片错误摘要
- [X] T049 [US5] 在 `backend/app/services/ai_parameter_assistant.py` 实现图片来源建议的保守置信度规则和人工核验状态
- [X] T050 [US5] 在 `frontend/src/features/assistant/parameter/ParameterSuggestionReview.tsx` 展示图片来源标记、图片区域说明和人工核验提示
- [X] T051 [US5] 在 `frontend/src/styles.css` 增加图片来源建议和人工核验提示的视觉状态

**检查点**：图片输入可参与建议流程；不确定图片值不会默认勾选或自动应用。

---

## Phase 8：收尾与横切事项

**目标**：完成兼容、验证、文档和治理检查，确保实现可以进入用户验收。

- [X] T052 [P] 在 `netlify/demo-functions/api.mts` 增加 AI 参数助手接口的明确演示兼容或不可用降级响应
- [X] T053 [P] 在 `docs/AI参数输入助手验证说明.md` 记录首期范围、用户确认规则、文件限制、图片低置信规则、短期 store 规则和项目级保存边界
- [X] T054 在 `specs/002-ai-parameter-assistant/quickstart.md` 按最终实现补充 fixture 名称、验证步骤和已知降级路径
- [X] T055 运行 `.\.venv\Scripts\python.exe -m pytest backend\tests -q` 并修复与 AI 参数助手相关的失败
- [X] T056 运行 `npm.cmd --prefix frontend run build` 并修复类型检查或构建失败
- [X] T057 按 `specs/002-ai-parameter-assistant/quickstart.md` 执行文本、表格、PDF、图片、冲突、局部应用、不持久化原文件、20 条建议批次、结构参数排除和短期 store 过期验证
- [X] T058 检查 `AGENTS.md`、`.specify/memory/constitution.md` 和 `specs/002-ai-parameter-assistant/tasks.md` 的门禁要求仍满足用户确认后再实现的流程

---

## 依赖与执行顺序

### 阶段依赖

| 阶段 | 依赖 |
|------|------|
| Phase 1 准备 | 无依赖 |
| Phase 2 基础能力 | 依赖 Phase 1 |
| Phase 3 US1 提取候选排程参数 | 依赖 Phase 2 |
| Phase 4 US2 应用前审阅、筛选和处理建议 | 依赖 Phase 2，可与 US1 的部分后端实现并行，但前端完整体验依赖 US1 上传解析结果 |
| Phase 5 US3 仅应用已选建议到当前方案 | 依赖 Phase 2 和 US2 冲突/选择状态 |
| Phase 6 US4 安全新增候选配置项 | 依赖 Phase 2，可在 US1 解析能力后并行推进 |
| Phase 7 US5 图片解析低置信验证 | 依赖 Phase 2，可在 US1 资料解析服务后并行推进 |
| Phase 8 收尾 | 依赖目标用户故事完成 |

### 用户故事依赖

| 用户故事 | 可独立验证方式 | MVP 关系 |
|----------|----------------|----------|
| US1 | 解析接口和上传面板返回三类建议，当前方案不变，正式路径通过 AI adapter | MVP 必需 |
| US2 | 审阅界面能处理高置信、低置信、冲突和 20 条建议批次 | MVP 必需 |
| US3 | 已选建议通过短期 store 应用到当前方案并使旧结果过期 | MVP 必需 |
| US4 | 候选新增项确认后才加入当前方案 | P2 增强 |
| US5 | 图片来源建议低置信或人工核验 | P2 增强 |

### 并行机会

Phase 1 中 T001、T002 可并行。Phase 2 中 T005、T006、T007、T008、T009 可并行。US1 的后端测试 T013、T014、T015、T016 可并行。US2 的 T024 和 T025 可并行。US3 的 T032、T033、T034 可并行。US4 和 US5 在 Phase 2 完成后可由不同人员并行推进，但最终都要经过 Phase 8 验证。

## 并行示例

US1 可并行启动：

```text
Task: T013 在 backend/tests/test_ai_parameter_assistant_parse.py 增加解析契约测试
Task: T014 在 backend/tests/test_ai_parameter_assistant_limits.py 增加限制和失败测试
Task: T015 在 backend/tests/test_ai_parameter_ai_client.py 增加 AI adapter 测试
Task: T016 在 backend/tests/test_ai_parameter_assistant_scope.py 增加结构参数负向测试
Task: T021 在 frontend/src/features/assistant/parameter/ParameterAssistantPanel.tsx 实现上传和解析状态
```

US2 可并行启动：

```text
Task: T024 在 backend/tests/test_ai_parameter_assistant_review.py 增加置信度和 20 条批次测试
Task: T025 在 backend/tests/test_ai_parameter_assistant_conflicts.py 增加冲突测试
Task: T028 在 frontend/src/features/assistant/parameter/ParameterSuggestionReview.tsx 实现审阅表
Task: T029 在 frontend/src/features/assistant/parameter/ParameterConflictResolver.tsx 实现冲突处理
```

US3 可并行启动：

```text
Task: T032 在 backend/tests/test_ai_parameter_assistant_apply.py 增加局部应用测试
Task: T033 在 backend/tests/test_ai_parameter_assistant_apply_failures.py 增加失败摘要测试
Task: T034 在 backend/tests/test_ai_parameter_suggestion_store.py 增加短期 store 测试
Task: T039 在 frontend/src/features/assistant/parameter/ParameterAssistantPanel.tsx 实现应用和过期提示
```

US4 和 US5 可并行启动：

```text
Task: T042 在 backend/tests/test_ai_parameter_assistant_candidates.py 增加候选新增测试
Task: T047 在 backend/tests/test_ai_parameter_assistant_images.py 增加图片低置信测试
Task: T045 在 frontend/src/features/assistant/parameter/ParameterCandidateList.tsx 实现候选新增展示
Task: T050 在 frontend/src/features/assistant/parameter/ParameterSuggestionReview.tsx 展示图片来源标记
```

## 实施策略

### MVP 优先

1. 完成 Phase 1 和 Phase 2。
2. 完成 US1，先证明可以通过正式 AI adapter 上传资料并得到可追溯建议。
3. 完成 US2，确保建议在应用前可审阅、可筛选、可处理冲突，并支持至少 20 条建议批次。
4. 完成 US3，确保已选建议通过短期 store 只影响当前方案且旧排程结果失效。
5. 运行后端测试、前端构建和 quickstart 中的核心场景。

### 增量交付

1. MVP 完成后再推进 US4 候选新增。
2. 再推进 US5 图片低置信验证。
3. 每个故事完成后独立验证，不让增强故事阻塞 P1 闭环。

### 实施边界

- 不修改 CP-SAT 目标函数或求解规则。
- 不把 AI 建议自动保存到项目级配置。
- 不持久化上传原文件。
- 不用 Demo、mock 或临时降级行为替代正式产品规则。
- 用户确认 `tasks.md` 和 `/speckit-analyze` 结果前，不进入代码实现。


# 实施计划：AI 参数输入助手

**分支/目录**：`002-ai-parameter-assistant` | **日期**：2026-07-01 | **规格**：[spec.md](./spec.md)

**输入**：来自 `specs/002-ai-parameter-assistant/spec.md` 的功能规格，以及已确认的用户补充口径。

**说明**：本计划由 `/speckit-plan` 阶段生成。当前阶段只完成设计与契约，不进入代码实现。

## 概要

新增一个面向排程场景的 AI 参数输入助手，允许用户上传文本、Word、Excel、PDF 和图片资料，AI 解析后生成“待确认建议”，覆盖首期范围内的工艺工效、资源数量和里程碑。建议不会直接改写配置，必须由用户在批量审阅界面确认后才应用；应用范围仅限当前方案，项目级配置仍由现有保存动作控制。

技术方向是在后端新增参数解析与建议归并能力，复用现有 `ScenarioInput`、`ProcessTemplate`、`ResourcePool`、`MilestoneConstraint` 等模型作为最终应用对象；前端新增上传、建议审阅、冲突处理、置信度展示和局部应用流程。应用成功后需要标记当前任务视图、求解结果和方案对比为过期，避免用户误用旧结果。

## 技术上下文

**语言/版本**：后端 Python 3.11 兼容 FastAPI 服务；前端 TypeScript/React/Vite；Netlify 演示函数使用 TypeScript。

**主要依赖**：复用 FastAPI、Pydantic、现有 multipart 上传处理和前端 API 封装。后端必须提供可配置 AI adapter，统一处理请求构造、超时、结构化 JSON schema 校验、AI 不可用错误和测试 mock 注入；fixture/mock 只能用于测试和本地确定性验证，不能作为正式解析主路径。文档、图片解析优先通过后端统一解析服务和可配置 AI 服务完成；如实现阶段必须引入 Word/PDF/OCR 辅助库，需要在任务和分析阶段单独说明理由、范围和降级策略。

**存储**：首期不新增数据库持久化。不持久化上传原文件；后端仅使用短期 suggestion store 保存当前解析流程的建议、冲突组、候选项、来源摘要和过期时间，供 `/apply` 通过 `run_id` 取回。被应用的参数只进入当前 `ScenarioInput`，不会自动写入项目级配置或默认工艺库。

**测试**：后端使用 pytest 覆盖解析契约、建议归并、冲突处理、局部应用和异常返回；前端使用构建检查和必要的组件/交互验证；接口契约以 `contracts/ai-parameter-assistant-contract.md` 为准。

**目标平台**：本地 FastAPI 服务与 React 前端为主；Netlify 演示 API 需要保持兼容或提供明确降级提示。

**项目类型**：跨前后端 Web 功能，涉及 AI 辅助解析、排程场景参数建议和当前方案应用。

**性能目标**：单次解析最多 10 个文件、总大小 50MB、前端最多展示 100 条建议；超限时给出明确错误，不进入部分解析。应用建议时应保持当前方案更新为同步操作，不触发排程求解。

**约束**：不改变 CP-SAT 求解目标、约束优先级和工期计算规则；不自动覆盖已有参数；不自动新增配置项；不自动保存项目级配置；高置信度仅可默认勾选，仍需用户点击应用；低置信度进入待人工完善；图片来源默认按较低置信度处理，除非 AI 返回可解释的高置信证据。

**规模/范围**：影响后端模型/API/服务、前端类型/API/助手界面、工艺工效/资源/里程碑应用逻辑、结果过期状态处理和测试。首期不覆盖结构参数导入替代、完整施工逻辑自动建模、自动求解和长期文件归档。

## Constitution 检查

*门禁：Phase 0 研究前必须通过；Phase 1 设计后再次检查。*

- 已完成需求发现和多轮用户确认，当前需求成立且属于排程参数与前后端联动能力，必须走 Spec Kit。
- `spec.md` 已记录用户补充口径、现有 Demo/代码事实和首期边界。
- 排程、资源、里程碑和前后端契约影响已明确；CP-SAT 求解规则不在本期修改范围内。
- 输入、输出、冲突、置信度、局部应用、失败态和验收标准均可测试。
- 不把 Demo 临时限制提升为正式产品目标；项目级保存仍沿用现有显式保存流程。
- Spec Kit 过程文档和阶段报告使用中文简体；代码标识符、文件路径、接口名、任务编号和必要英文缩写保持原文。

**Phase 0 结论**：通过。研究需重点收敛建议生命周期、文件保留、AI 服务边界、置信度、冲突处理和当前方案应用规则。

## 项目结构

### 本功能文档

```text
specs/002-ai-parameter-assistant/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── ai-parameter-assistant-contract.md
└── tasks.md
```

### 源码结构（仓库根目录）

```text
backend/
├── app/
│   ├── main.py
│   ├── models.py
│   ├── api/
│   │   └── multipart.py
│   ├── process_nl.py
│   ├── bridge_import.py
│   ├── local_scenario_config.py
│   └── services/
└── tests/

frontend/
├── src/
│   ├── app/
│   │   └── App.tsx
│   ├── api/
│   │   └── schedulerApi.ts
│   ├── domain/
│   ├── features/
│   └── types/
│       └── scheduler.ts

netlify/
└── demo-functions/
    └── api.mts
```

**结构决策**：在后端新增面向 AI 参数助手的模型、AI adapter、短期 suggestion store、服务和接口，复用现有上传处理和 `ScenarioInput` 应用模式；前端在现有排程页面内增加助手入口和审阅面板，复用当前“修改场景后清空/刷新任务视图和求解结果”的状态处理；Netlify 演示函数只承担兼容或降级，不作为首期真实 AI 解析主路径。

## Phase 0：研究输出

研究文件：[research.md](./research.md)

已解决的关键问题：

- 建议清单先行，解析阶段不修改方案。
- 上传原文件不持久化，只通过短期 suggestion store 保留建议、来源摘要、冲突组、候选项和应用所需状态。
- 允许后端配置 AI 服务处理文本、表格、PDF 和图片，测试 mock 不作为正式解析主路径。
- 置信度统一展示为 `High`、`Medium`、`Low` 加 0-100 分；仅高置信、无冲突、字段完整建议可默认勾选。
- 冲突不自动覆盖，用户选择候选值或手动填写。
- 支持局部应用，不完整内容保留为待人工完善。
- 里程碑无明确约束类型时默认内部软里程碑。
- 单次解析规模限制为 10 个文件、50MB、100 条建议。

## Phase 1：设计输出

设计文件：

- [data-model.md](./data-model.md)
- [contracts/ai-parameter-assistant-contract.md](./contracts/ai-parameter-assistant-contract.md)
- [quickstart.md](./quickstart.md)

设计要点：

- `ExtractionRun` 表示一次解析流程，不代表长期存储。
- `ParameterSuggestion` 是用户确认前的核心对象，必须包含类别、目标、当前值、建议值、置信度、来源证据和状态。
- `SuggestionStoreEntry` 是短期服务端状态，用于让 `/apply` 根据 `run_id` 找回已展示建议，不保存上传原文件。
- `ConflictGroup` 聚合指向同一参数的多个候选值，必须由用户解决后才能应用。
- `ApplicationRequest` 只对当前 `ScenarioInput` 生效，输出更新后的 `ScenarioInput` 和应用摘要。
- 解析接口和应用接口分离，防止上传即生效。

## Phase 1 Constitution 复查

- 输入对象、字段含义、默认值、枚举、单位和来源已在数据模型中定义。
- 输出对象、诊断信息、统计指标和展示口径已在契约中定义。
- 硬规则包括用户确认、冲突处理、文件限制、当前方案应用和不持久化原文件。
- 正常流程、异常流程、空态、失败态和兼容场景已在 quickstart 中给出验证路径。
- 无新增 CP-SAT 规则，无自动保存项目级配置，无未说明的大范围重构。

**复查结论**：通过。可进入 `/speckit-tasks` 生成任务，但在用户确认 `tasks.md` 和 `/speckit-analyze` 结果前不得进入实现。

## 复杂度跟踪

当前无 Constitution 违反项。

# 实施计划：AI 批量初始化工点工装资源

**分支/目录**：`059-ai-batch-resource-initialization` | **日期**：2026-07-21 | **规格**：[spec.md](./spec.md)

**输入**：来自当前 `SPECIFY_FEATURE_DIRECTORY/spec.md` 的功能规格

## 概要

在现有“工点资源配置”页面增加一次性批量 AI 初始化操作。前端把当前完整 `ScenarioInput` 发送到新接口；后端按 `project_data_version_id` 重新投影已确认项目主数据，汇总全部可排程桥梁工点的结构物与构件信息，并基于现有工艺库、后端资源目录和当前资源池确定每个工点仍缺失的候选资源。真实 OpenAI-compatible LLM 仅能在后端给出的工点和候选资源集合内推荐正整数投入与上限。

后端对整个模型结果执行工点身份、候选资源、数量、重复项、完整性和当前输入指纹校验，通过后生成可直接合并的 `WORKPOINT_EXCLUSIVE` 资源池；任何非法项均使整批失败。前端仅在响应仍对应当前项目版本与资源快照时一次性合并新增池，保留全部已有池，不自动保存；用户继续在原逐工点页检查，最终复用现有保存流程持久化完整资源配置。

## 技术上下文

**语言/版本**：Python 3.14 运行环境下的现有 FastAPI/Pydantic 代码；TypeScript 5.7、React 19、Node.js 现有工作区

**主要依赖**：FastAPI、Pydantic、标准库 `urllib.request` OpenAI-compatible 客户端、React、Vite；不新增第三方依赖

**存储**：不新增表或迁移；推荐在前端保持未保存临时状态，用户点击现有保存后进入本地场景配置；真实密钥只在根目录被忽略的 `.local.env`

**测试**：pytest 后端服务/路由/契约测试；Node `node:test` 前端契约与状态测试；TypeScript 类型检查；Vite 生产构建；OpenAPI YAML、文档与差异校验

**目标平台**：本地 FastAPI 后端与 Vite/静态前端；模型服务为用户配置的 OpenAI-compatible HTTPS endpoint

**项目类型**：跨前后端 Web 功能、共享 API 契约和本地运行配置变更

**性能目标**：一次用户操作只产生一个逻辑批次；当前 13 个桥梁工点在配置的模型超时时限内完成。前端合并为一次状态提交；不增加 CP-SAT 调用

**约束**：只新增缺失的工点独享受限资源；已有池逐字段冻结；不创建共享池；不推荐 `precast_beam_team` 等资源页已排除类型；全批原子应用；无真实模型配置时失败；不自动保存；迟到响应不得覆盖新版本或新资源状态

**规模/范围**：1 个资源配置页面按钮与状态区；1 个新后端接口；一组请求/响应/摘要契约；1 个严格 LLM 初始化方法；后端结构汇总、候选投影和资源池构造；环境模板、说明与定向测试

## 生命周期归属

- **规格归属引用**：[`spec.md#生命周期归属`](./spec.md#生命周期归属)
- **实施路径**：`04-demo/backend/app/contracts/`、`04-demo/backend/app/api/routers/assistants.py`、`04-demo/backend/app/services/`、`04-demo/backend/app/scenario_data.py`、`04-demo/frontend/src/api/`、`04-demo/frontend/src/contracts/`、`04-demo/frontend/src/app/Workspace.tsx`、`04-demo/frontend/src/features/resources/`、`.local.env.example`、`README.md` 及邻近测试

## Constitution 检查

*门禁：Phase 0 研究前已通过；Phase 1 设计后再次检查。*

- **可验收需求：通过。** 规格记录了按钮、真实模型、输入范围、已有资源保护、逐工点确认、统一保存、失败原子性和可衡量标准。
- **显式算法规则：通过。** 输入为权威项目投影、结构汇总、候选资源和当前资源快照；LLM 仅推荐缺失本地资源的投入与上限；后端确定性校验决定是否整批接纳，且不触发排程目标。
- **显式共享契约：通过。** 新接口定义请求、响应、错误码、模型状态、输入指纹、逐工点摘要和新增资源池；前后端类型及 OpenAPI 需要同步。
- **保留行为与最小设计：通过。** 复用现有项目主数据物化、资源目录、LLM HTTP 客户端、ResourcesTab、Workspace 场景状态和保存入口；不新增依赖、数据库或平行资源页面。
- **分阶段价值：通过。** 首批实现即可完成“点击—真实模型推荐—原子合并—逐工点检查—统一保存”的闭环。
- **验证与证据：通过。** 双工点样例、已有资源冻结、真实客户端模拟、非法批次、过期响应、保存前后状态和密钥边界均有明确验证入口。
- **资产与数据安全：通过。** `.local.env.example` 仅提供空值模板；真实 `.local.env` 保持忽略，密钥不进入前端、响应、日志或测试夹具。
- **无不适用门禁。** 本功能不迁移资产、不修改 CP-SAT、不删除持久数据，也不将 Demo 默认数量提升为正式业务规则。

## Phase 0：研究结论

关键决策与替代方案记录于 [research.md](./research.md)。结论是复用现有 `AI_RESOURCE_ASSISTANT_*` OpenAI-compatible 配置族，但为批量初始化提供严格调用路径：本地 provider、缺配置、调用失败或非法结果都返回失败，不沿用三方案功能的本地回退。工点、结构和候选资源由后端当前项目投影确定，前端不提交可被篡改的独立候选清单。

## Phase 1：设计

### 后端权威输入

1. 新接口接收完整场景，路由复用 `_materialize_project_master`，确保 `scenario.project` 来自当前已确认项目主数据版本。
2. 服务遍历投影后的 `bridge_supported` 桥梁，形成稳定工点 ID、名称、结构/构件类型、数量、工艺和关键参数的压缩汇总。
3. 复用并收敛 `derive_resource_catalog` 与 `derive_workpoint_possible_resource_types`，统一过滤资源页面禁止展示的类型；按 `工点 ID + 资源类型` 排除已有池，包括未保存的人工编辑。
4. 若没有工点、结构资料不完整或所有工点均无需补充，则不调用模型并返回明确成功/阻断摘要。

### 真实 LLM 调用与严格校验

1. 在现有 `ai_resource_explainer.py` 增加批量初始化专用调用函数，复用 provider、endpoint、model、API Key、超时、温度和 JSON response format 读取逻辑。
2. 该函数要求 provider 属于外部模型集合且 endpoint、model、API Key 齐全；`local/none/off` 直接报“真实模型未配置”，不得返回确定性替代结果。
3. 模型上下文按工点列出结构汇总、唯一允许的缺失候选资源和输出 schema；输出只包含工点 ID、资源类型、投入、上限和简短理由。
4. 后端要求模型返回所有待推荐工点且无额外工点；工点内资源不得重复，必须来自对应候选集合，`quantity >= 1`、`max_quantity >= quantity` 且均为整数。
5. 初次输出非法时允许携带确定性校验错误执行一次纠错；第二次仍非法、调用失败或响应不完整则整批失败、零新增。

### 资源池构造与原子响应

1. 验证通过后，后端按现有手工配置的稳定 ID 规则构造 `WORKPOINT_EXCLUSIVE`、`LIMITED`、启用的本地资源池。
2. 标签、默认日历和适用工艺来自后端候选资源；LLM 不得覆盖这些属性，也不得输出成本、共享范围或任意扩展字段。
3. 响应仅携带待新增的完整 `ResourcePool`、项目版本、输入指纹、模型配置状态和逐工点摘要，不回传模型请求中的认证信息。
4. 输入指纹覆盖项目版本和当前完整资源池语义；前端用请求时指纹和版本核对当前状态，任一变化即丢弃响应。

### 前端交互与保存

1. `ResourcesTab` 标题区增加“AI快速配置工装”按钮；项目工点未就绪、调用中或保存中时禁用。
2. `Workspace` 提供批量合并回调，在一次 `setScenario` 中按池 ID 与 `工点 ID + 资源类型` 再次防重，只追加响应中的缺失资源。
3. 成功后显示“新增资源数、无需补充工点数、模型名称”的简要通知；资源仍通过现有工点标签和表格逐个查看，不新增汇总编辑页。
4. AI 成功只使本地资源配置变为脏状态；用户人工修改后点击现有保存，一次提交完整池并沿用现有任务/求解结果失效机制。
5. 失败、取消、迟到或过期响应不调用合并回调，当前手工修改和已有资源保持不变。

### 契约与环境

1. 新增 `AiWorkpointResourceInitializationRequest/Response`、工点摘要、候选资源、推荐记录和批次摘要模型，并在前后端共享契约中保持一致。
2. 新增 `POST /api/ai-resource-assistant/initialize-workpoint-resources`；业务校验返回 422，真实模型配置缺失或调用失败返回 503，版本冲突沿用项目主数据错误映射。
3. `.local.env.example` 和 README 明确此功能复用 `AI_RESOURCE_ASSISTANT_*`；用户只需在 `.local.env` 填写真实 provider、endpoint、model 和 API Key。
4. 不新增 `VITE_*` 密钥变量，前端永远不能读取模型密钥。

## 项目结构

### 本功能文档

```text
03-requirements/specs/059-ai-batch-resource-initialization/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── ai-workpoint-resource-initialization.openapi.yaml
│   └── ui-behavior.md
└── tasks.md
```

### 生命周期与源码结构（仓库根目录）

```text
.local.env.example
README.md
04-demo/
├── backend/
│   ├── app/
│   │   ├── api/routers/assistants.py
│   │   ├── contracts/_models.py
│   │   ├── scenario_data.py
│   │   └── services/
│   │       ├── ai_resource_explainer.py
│   │       └── ai_workpoint_resource_initializer.py
│   └── tests/
└── frontend/
    ├── src/
    │   ├── api/
    │   ├── app/Workspace.tsx
    │   ├── contracts/
    │   └── features/resources/
    └── tests/
```

**结构决策**：资源初始化编排放在独立后端服务，避免继续扩大既有 2300 行三方案排程助手；通用 HTTP/环境读取仍复用 `ai_resource_explainer.py`。前端只扩展现有资源配置页和 Workspace 场景状态，不创建新的功能页面或持久化层。

## 复杂度跟踪

无 Constitution 违反项。

# 实施计划：AI 单方案 15 秒求解预算

**分支/目录**：`037-ai-solve-15s-budget` | **日期**：2026-07-14 | **规格**：[spec.md](./spec.md)

**输入**：来自 `specs/037-ai-solve-15s-budget/spec.md` 的功能规格

## 概要

将 AI 经济、平衡、抢工方案的唯一固定资源求解预算从 60 秒压缩为 15 秒。继续由 AI 资源助手入口统一覆盖单方案时限，单阶段编排和 `[最大目标延期, 总工期]` 目标不变；同步预算传播测试、页面说明和验证文档，并用默认真实 Excel 串行复测三套方案。

## 技术上下文

**语言/版本**：Python 3.12+（本地运行时兼容）、TypeScript 5.7、Node.js 24

**主要依赖**：FastAPI、Pydantic、OR-Tools CP-SAT、pytest、React 19、Vite 6

**存储**：不新增存储，不迁移或重写历史结果与基准计划快照

**测试**：pytest 预算传播与历史兼容回归、完整排程回归、TypeScript/Vite 生产构建、真实 Excel 三方案串行求解

**目标平台**：本地 FastAPI 后端与 React Web Demo

**项目类型**：AI 资源助手算法配置、页面说明与验证文档的窄范围前后端变更

**性能目标**：每套 AI 固定资源方案最多配置 15 秒求解时间；三套方案分别独立计时；仍只调用一次排程

**约束**：不改变目标函数、求解器参数、固定资源、自动增配、第二阶段状态、LLM 超时、非 AI 求解时限或历史契约

**规模/范围**：1 个后端预算常量、AI 助手与排程测试断言、1 处页面说明、1 份验证文档和 1 份真实 Excel 三方案回归

## Constitution 检查

*门禁：Phase 0 研究前与 Phase 1 设计后均已检查。*

- [x] 已按排程时限变更进入完整 Spec Kit，用户目标和范围明确。
- [x] `spec.md` 已引用现有 60 秒、单阶段规格、验证文档和当前代码事实。
- [x] 已明确输入方案、15 秒时限、输出预算字段、状态、异常和历史兼容。
- [x] 目标函数、硬约束、资源边界、非 AI 入口和 LLM 超时均明确不变。
- [x] 复用现有预算常量、阶段摘要、页面组件和测试结构，不新增依赖或共享字段。
- [x] 已定义真实 Excel 三方案和历史结果的可复现验收。
- [x] 全部 Spec Kit 产物使用中文简体，无 Constitution 违反项。

**设计后复检**：通过。该方案仅改变 AI 入口的统一预算值及其用户可见说明，响应结构和历史读取不变。

## 项目结构

### 本功能文档

```text
specs/037-ai-solve-15s-budget/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── ai-solve-15s-api.md
├── checklists/
│   └── requirements.md
└── tasks.md
```

### 源码结构（仓库根目录）

```text
backend/
├── app/services/
│   └── ai_resource_scheduling_assistant.py
└── tests/
    ├── test_ai_resource_scheduling_assistant.py
    └── test_scheduler.py

frontend/src/features/resourceAssistant/
└── ResourceAssistantPanel.tsx

docs/
└── AI资源配置与排程优化助手验证说明.md
```

**结构决策**：继续由 `AI_RESOURCE_PLAN_SOLVE_TIME_LIMIT_SECONDS` 作为 AI 多方案比选的统一入口预算；`scenario.py` 读取已经覆盖为 15 秒的 `ScenarioInput` 并完整交给唯一 `primary` 阶段，无需修改求解器或响应模型。

## Phase 0：研究与决策

研究结论见 [research.md](./research.md)。核心决策：15 秒是每套方案独立预算，不是三方案总预算；唯一阶段完整获得 15 秒；未获得排程时沿用现有状态，不回退 60 秒。

## Phase 1：设计与契约

### 预算传播

1. 单方案或批量中的每套方案进入 AI 求解服务。
2. 服务将该方案的 `time_limit_seconds` 统一覆盖为 15 秒。
3. 单阶段编排把 15 秒完整传给唯一 `primary` 求解。
4. `optimization_stages.total_budget_seconds`、`primary.configured_budget_seconds` 和目标评估预算均记录 15 秒。
5. 实际耗时按真实求解记录，可小于或略高于配置时限（包含模型构建和结果组装）。

### 状态与兼容

- 仍只执行一次求解，`secondary` 固定不适用，禁止隐藏延时或重试。
- `OPTIMAL/FEASIBLE/UNKNOWN/INFEASIBLE/MODEL_INVALID` 沿用现有分类和诊断。
- 历史 30 秒、60 秒或其他阶段摘要原样解析，不做迁移。
- 不修改接口字段、前端类型、持久化结构或状态码。

### 页面与文档

- AI 多方案比选顶部说明由最长 60 秒改为最长 15 秒。
- 验证说明中的当前默认预算和断言同步为 15 秒，历史说明保留为历史事实时不改写旧数据。

## Phase 2：实施顺序

1. 先调整预算传播测试，断言默认单方案和批量逐套预算均为 15 秒，历史摘要仍可解析。
2. 将 AI 资源助手入口预算常量从 60 秒改为 15 秒，不修改单阶段编排和求解器。
3. 更新页面说明与验证文档。
4. 运行针对性后端测试、完整回归和前端生产构建。
5. 默认导入真实桥梁 Excel，串行求解经济、平衡、抢工三方案并记录预算、调用次数、状态、工期与延期。

## 复杂度跟踪

无 Constitution 违反项，无需复杂度豁免。项目不存在 Agent 上下文更新脚本，因此不修改 `AGENTS.md` 或 `agent.md`。

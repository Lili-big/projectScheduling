# 实施计划：AI 两阶段排程共享 60 秒预算

**分支/目录**：`034-ai-resource-solve-60s-budget` | **日期**：2026-07-14 | **规格**：[spec.md](./spec.md)

**输入**：来自 `/specs/034-ai-resource-solve-60s-budget/spec.md` 的功能规格

## 概要

将 AI 多方案比选中单方案严格固定资源两阶段排程的共享总预算由 30 秒提高为 60 秒。复用现有动态预算编排，不修改两阶段目标、资源快照、次目标判断和失败回退；同步后端预算常量、测试断言、页面说明及验证文档，并用真实 Excel 的三套固定 LLM 资源快照串行复测。

## 技术上下文

**语言/版本**：Python 3.14（本地运行时）、TypeScript 5.7、Node.js（项目现有前端运行时）

**主要依赖**：FastAPI、Pydantic、OR-Tools CP-SAT、pytest、React 19、Vite 6

**存储**：不新增存储；历史基准计划继续使用现有本地持久化结构

**测试**：pytest 后端针对性测试与全量回归、TypeScript/Vite 生产构建、真实 Excel 三方案串行求解

**目标平台**：本地 FastAPI 后端与 React Web 前端

**项目类型**：前后端 Web 应用中的算法配置与说明同步

**性能目标**：每个 AI 单方案的两阶段 CP-SAT 共享配置预算为 60 秒；三套方案分别独立计时；端到端耗时允许包含少量模型构建和结果组装开销

**约束**：不改变目标函数、权重、硬约束、固定资源数量、自动增配规则、LLM 超时、通用模拟求解时限或历史响应结构

**规模/范围**：1 个后端入口常量、现有两阶段编排预算传播验证、AI 助手与排程测试、1 处页面说明、1 份现有验证文档和真实 351 任务 Excel 案例

## Constitution 检查

*门禁：Phase 0 研究前已通过；Phase 1 设计后再次检查仍通过。*

- [x] 由于修改 CP-SAT 求解时限，已按完整 Spec Kit 门禁处理。
- [x] `spec.md` 已引用 `AGENTS.md`、项目手册、现有验证文档、032/033 规格及当前代码事实。
- [x] 输入为现有 AI 固定资源方案，输出继续使用现有阶段诊断，算法影响仅为共享预算值。
- [x] 两阶段目标、资源边界、异常回退、历史兼容和真实样例验收均已明确。
- [x] 未将通用模拟求解、LLM 超时或每阶段独立 60 秒扩大到本次范围。
- [x] 全部 Spec Kit 产物使用中文简体，无 Constitution 违反项。

## 项目结构

### 本功能文档

```text
specs/034-ai-resource-solve-60s-budget/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── ai-resource-solve-budget-api.md
├── checklists/
│   └── requirements.md
└── tasks.md
```

### 源码结构（仓库根目录）

```text
backend/
├── app/
│   ├── scenario.py
│   └── services/
│       └── ai_resource_scheduling_assistant.py
└── tests/
    ├── test_ai_resource_scheduling_assistant.py
    └── test_scheduler.py

frontend/
└── src/features/resourceAssistant/
    └── ResourceAssistantPanel.tsx

docs/
└── AI资源配置与排程优化助手验证说明.md
```

**结构决策**：预算默认值继续归属 AI 资源助手入口；`scenario.py` 只负责读取传入预算并在两个阶段之间动态分配，原则上无需改变编排算法。现有响应模型和前端类型已经支持数值型 `total_budget_seconds`，无需增加共享字段或数据迁移。

## Phase 0：研究结论

研究结论见 [research.md](./research.md)。核心决策是提高单方案共享预算，不拆成两个阶段各 60 秒；只修改 AI 入口默认值，不调整通用求解或 LLM 调用时限。

## Phase 1：设计与契约

- [data-model.md](./data-model.md)：复用现有阶段摘要，仅将本入口的预算不变量更新为 60 秒。
- [contracts/ai-resource-solve-budget-api.md](./contracts/ai-resource-solve-budget-api.md)：请求和字段结构不变，说明响应预算值及兼容口径。
- [quickstart.md](./quickstart.md)：提供后端、前端和真实 Excel 三方案验证步骤。

设计后 Constitution 复核：无新增模块、依赖、接口字段或持久化；真实 Excel 验证串行执行，避免 CPU 竞争污染 60 秒性能证据。

## 实施顺序

1. 先补充或调整预算传播测试，断言默认单方案预算为 60 秒、第二阶段只用剩余预算，隔离用例仍可覆盖自定义短预算。
2. 将 AI 方案求解入口常量从 30 秒改为 60 秒，不修改两阶段编排公式。
3. 更新页面共享预算说明和验证文档，不改方案交互或接口字段。
4. 运行针对性与完整后端回归、前端生产构建。
5. 固定同一份真实 LLM 资源快照，串行求解经济、平衡、抢工三案，记录阶段时限、耗时、工期、空闲、连续性、资源快照及回退情况。

## 复杂度跟踪

无 Constitution 违反项，无需复杂度豁免。

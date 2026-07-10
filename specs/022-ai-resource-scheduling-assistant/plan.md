# 实施计划：AI资源配置与排程优化助手

**分支/目录**：`022-ai-resource-scheduling-assistant` | **日期**：2026-07-09 | **规格**：[spec.md](./spec.md)

**输入**：来自 `specs/022-ai-resource-scheduling-assistant/spec.md` 的功能规格。

**说明**：本计划只完成设计与任务拆解，不进入代码实现；需等待用户确认 `tasks.md` 和 `$speckit-analyze` 结果后再实施。

## 概要

本功能在现有桥梁施工排程 Demo 上新增一个“AI资源配置与排程优化助手”闭环：用户导入或选择项目数据后，系统生成工程画像，LLM 基于画像、约束提示和参考样例一次性生成 A/B/C 三类资源配置初始方案和施工组织策略；系统完成基础校验，用户确认或调整后分别以固定资源方式求解，汇总工期、控制墩、连续梁、资源利用、等待、转场和演示成本指标，再由确定性推荐规则给出推荐结论，AI 基于指标生成解释。实现方向是复用现有 `ScenarioInput`、资源池、任务生成、CP-SAT 求解、连续梁班组诊断、资源组织诊断和前端甘特/资源展示能力，补齐 LLM 方案生成、三方案包装、输出校验、指标汇总、推荐解释和 LLM 配置回退。原 A/B/C 数值只作为 LLM 参考样例，不作为正式固定方案。

## 技术上下文

**语言/版本**：Python 3.x、TypeScript、Node.js。

**主要依赖**：FastAPI、React、OR-Tools CP-SAT、pytest、Vite；外部大模型调用复用当前项目已有 OpenAI-compatible / HTTP 适配器模式。

**存储**：不新增正式数据库。MVP 使用内存态三方案求解结果与现有本地配置；外部大模型配置通过 `.local.env` 或部署环境变量读取，密钥不进入前端和文档。

**测试**：后端 `python -m pytest backend/tests/test_scheduler.py`；前端 `npm.cmd run build`；必要时增加针对三方案指标、推荐规则和 LLM 回退的定向测试。

**目标平台**：本地 FastAPI 后端与 React 前端。Netlify 演示 API 不作为本功能第一验收面；若后续要求云端镜像能力，再补充对应合同。

**项目类型**：桥梁施工排程 Web 应用，涉及后端求解编排、结果指标契约、AI 解释服务和前端新助手体验。

**性能目标**：
- 三方案求解允许串行或受控并行执行，不额外触发无限资源搜索。
- 单个方案默认沿用当前求解时限；三方案整体进度必须可见。
- 指标汇总和本地解释生成耗时相对求解耗时可忽略。

**约束**：
- 不改变现有 CP-SAT 硬约束、连续梁班组联级占用和当前目标函数口径。
- 不让 AI 生成最终施工计划，也不让 AI 直接决定最优方案。
- 不引入真实成本库、GIS 距离、天气日历、无限资源搜索或复杂推荐优化。
- 不把演示成本、演示转场惩罚写成正式产品成本或真实空间分析。
- 不默认修改 `README.md`、提交 git 或推送。

**规模/范围**：
- 后端：新增或扩展三方案求解编排、资源方案生成、指标汇总、推荐规则、AI 解释服务与本地配置读取。
- 模型契约：新增面向助手的响应结构；复用 `ScenarioInput`、`ResourcePool`、`ScheduleResult`、`ScenarioSolveResult` 的核心字段。
- 前端：新增助手页面/视图，展示工程画像、方案卡片、求解进度、指标对比、甘特/控制墩/资源利用视图和解释区域。
- 测试：覆盖 LLM/本地回退资源方案生成、AI 输出校验、桩机按类型分类、指标汇总、推荐规则、失效状态、LLM 回退和核心前端构建。

## Constitution 检查

- [x] 已完成需求评审，并形成“调整后推进”的结论。
- [x] `spec.md` 已引用用户材料、现有文档、Demo/代码事实和明确不做范围。
- [x] 排程、资源、工期、CP-SAT、前后端契约影响已明确。
- [x] 输入、输出、约束、边界场景和验收标准可测试。
- [x] 未把 Demo 临时限制提升为正式产品规则；演示成本与演示转场均明确标识。
- [x] Spec Kit 过程文档使用中文简体；代码标识符、字段名、路径和必要英文缩写保留原文。
- [x] 本阶段不进入代码实现，待 `tasks.md` 和 `$speckit-analyze` 经用户确认后再实施。

## 项目结构

### 本功能文档

```text
specs/022-ai-resource-scheduling-assistant/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── ai-resource-scheduling-assistant-contract.md
└── tasks.md
```

### 源码结构

```text
backend/
├── app/
│   ├── models.py
│   ├── scenario.py
│   ├── solver.py
│   ├── local_config.py
│   └── services/
└── tests/
    ├── test_scheduler.py
    └── test_ai_parameter_ai_client.py

frontend/
└── src/
    ├── app/App.tsx
    ├── api/schedulerApi.ts
    ├── types/scheduler.ts
    ├── domain/
    └── features/
```

**结构决策**：本功能横跨求解编排、结果指标和前端体验。后端优先在场景编排层聚合三方案结果，求解器只在指标缺失且无法从现有结果派生时补充诊断。前端优先复用现有 API 客户端、类型、资源/甘特展示和状态失效模式，避免建立并行的排程模型。

## 复杂度跟踪

| 违反项 | 为什么需要 | 拒绝更简单替代方案的原因 |
|--------|------------|--------------------------|
| 无 | 不适用 | 不适用 |

## Phase 0：研究结论

见 [research.md](./research.md)。关键结论：
- 三方案初始资源数值和施工组织策略由 LLM 一次性生成，但必须受项目资源类型、数量合法性、参考样例和用户确认流程约束。
- 原 A/B/C 固定数值降级为参考样例和本地回退基准，不作为正式固定方案。
- 指标汇总必须分层：直接求解字段、现有诊断派生、MVP 演示估算。
- MVP 推荐不做复杂优化搜索；推荐结论由确定性规则生成，AI 仅解释求解后的推荐证据，不直接判断最优。
- 外部大模型配置必须具备本地回退。

## Phase 1：设计产物

- [data-model.md](./data-model.md)：定义工程画像、AI 方案生成记录、资源方案、批量求解结果、核心指标、推荐解释和 LLM 配置状态。
- [contracts/ai-resource-scheduling-assistant-contract.md](./contracts/ai-resource-scheduling-assistant-contract.md)：定义助手入口、三方案求解、推荐解释和失效状态的前后端契约。
- [quickstart.md](./quickstart.md)：定义本地验证路径、数据样例、测试命令和期望结果。

## Phase 1 后 Constitution 复检

- [x] 设计产物仍区分业务规则、求解结果、诊断指标和演示估算。
- [x] 设计未改变现有 CP-SAT 目标函数和硬约束，仅新增批量编排和指标解释。
- [x] 已明确前后端契约、状态展示、错误/空态、密钥安全和结果失效规则。
- [x] 已明确后端测试、前端构建和端到端演示验证。
- [x] 仍需用户确认 `tasks.md` 和 `$speckit-analyze` 后才能实现。

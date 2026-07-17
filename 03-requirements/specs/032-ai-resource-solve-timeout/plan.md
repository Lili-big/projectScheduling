# 实施计划：AI 资源方案求解时限调整

**分支/目录**：`032-ai-resource-solve-timeout` | **日期**：2026-07-13 | **规格**：[spec.md](./spec.md)

**输入**：来自 `specs/032-ai-resource-solve-timeout/spec.md` 的功能规格

## 概要

将“AI 多方案比选”经济、平衡、抢工三类严格固定资源方案的单次求解预算统一从当前场景的 15 秒提升为 30 秒。专项预算在 AI 资源助手进入严格求解前生效，继续复用现有任务生成、单次完整三目标求解、状态判定和结果诊断。通用场景求解、最少资源、资源成本及全局 `ScenarioInput` 默认值保持不变。

## 技术上下文

**语言/版本**：Python 3.12+、TypeScript 5.7、Node.js 22+

**主要依赖**：FastAPI、Pydantic、OR-Tools CP-SAT、React 19、Vite 6

**存储**：不新增存储；求解时限仅存在于当前请求及响应诊断

**测试**：pytest 针对性单元与集成测试、真实 Excel 接口求解验证；前端无代码变更时不要求新增页面构建基线，但最终仍运行现有前端生产构建作为回归检查

**目标平台**：本地 FastAPI 服务与 React Web Demo

**项目类型**：后端 AI 资源方案求解编排的窄范围算法参数调整

**性能目标**：单个 AI 资源方案最多使用 30 秒求解预算；达到终态可提前返回；接口固定处理开销继续控制在求解器耗时之外约 2 秒内

**约束**：不修改目标函数、权重、任务、里程碑、资源数量、状态规则、资源增配规则和非 AI 求解入口；不新增依赖或共享字段

**规模/范围**：影响 `backend/app/services/ai_resource_scheduling_assistant.py` 的单方案和兼容批量方案求解路径、相关后端测试与 AI 资源助手验证文档

## Constitution 检查

*门禁：Phase 0 研究前与 Phase 1 设计后均已检查。*

- [x] 用户已明确要求调整 AI 资源方案求解时限，范围已结合当前对话收敛。
- [x] `spec.md` 已引用现有文档、Spec 028、真实 Demo 和代码事实。
- [x] 已明确输入只在 AI 严格求解前获得 30 秒专项预算；输出继续复用现有诊断字段。
- [x] 目标函数、硬约束、资源边界、异常状态和兼容入口均已定义。
- [x] 不修改全局默认值，不把 AI 专项预算扩展为其他求解模式规则。
- [x] 规格、计划、研究、数据模型、契约、验证指南和任务均使用中文简体。
- [x] 不修改实现代码，直至 `tasks.md` 和 `$speckit-analyze` 经用户确认。

**设计后复检**：通过。不存在 Constitution MUST 级冲突，无需复杂度豁免。

## 项目结构

### 本功能文档

```text
specs/032-ai-resource-solve-timeout/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── ai-resource-solve-timeout-api.md
├── checklists/
│   └── requirements.md
└── tasks.md
```

### 源码结构（仓库根目录）

```text
backend/
├── app/
│   └── services/
│       └── ai_resource_scheduling_assistant.py
└── tests/
    └── test_ai_resource_scheduling_assistant.py

docs/
└── AI资源配置与排程优化助手验证说明.md

frontend/
└── src/                         # 仅回归验证，不计划修改
```

**结构决策**：在现有 AI 资源助手服务边界内设置专项 30 秒预算，再调用已有 `solve_ai_strict_fixed_resource_scenario()`。这样单方案与批量求解自动复用同一规则，同时不触碰全局场景默认值、通用编排和底层目标函数。

## Phase 0：研究与决策

研究结论见 [research.md](./research.md)。核心决策：

1. 30 秒仅在 AI 资源助手服务构建待求解方案场景时覆盖，原始页面场景和其他入口不变。
2. 使用单一模块级专项常量表达固定预算，避免散落魔法数字，也不新增用户配置项或环境变量。
3. 单方案和批量方案均继续通过 `_solve_single_plan()`，天然保持一致。
4. 继续依赖现有 `generated.schedule_input.time_limit_seconds`、`stats.configured_time_limit_seconds` 和 `stats.target_achievement.time_budget_seconds` 证明预算生效，不新增契约字段。
5. 测试分为快速捕获测试与真实求解验证：自动化测试不等待完整 30 秒，真实 Excel 验证至少执行一个方案并检查返回诊断。

## Phase 1：设计与契约

### 后端处理

1. AI 资源助手接收页面原始 `ScenarioInput` 和所选 `ResourceAssistantPlan`。
2. 构建方案场景时继续替换方案标识、名称和资源池，并把该方案的求解时限设为 30 秒。
3. 调用现有严格固定资源编排；底层任务生成把 30 秒写入 `ScheduleInput`，求解器按现有机制配置最大时间。
4. 求解若提前达到终态则立即返回；若限时仅获得 `FEASIBLE` 或没有排程，继续沿用现有业务状态与原因。
5. 响应继续包含实际资源快照、配置时限、实际耗时、单次调用和未扩资源信息。

### 测试设计

- 快速单元测试拦截严格求解调用，断言传入方案场景的 `time_limit_seconds=30.0`。
- 单方案和批量路径分别验证 30 秒规则，防止只有一个入口生效。
- 既有严格资源测试显式缩短测试预算或替换求解器，避免自动化套件每次等待 30 秒，同时继续断言单次求解和资源不扩充。
- 通用默认场景仍断言 15 秒，证明没有修改全局默认值。
- 真实 Excel 验证检查 351 个任务场景的返回 `configured_time_limit_seconds=30.0`，并记录实际状态与耗时；不把必须得到 `OPTIMAL` 作为验收条件。

### 接口兼容

接口仍为 `POST /api/ai-resource-assistant/solve-plan` 和兼容批量接口，不新增请求或响应字段。详细契约见 [contracts/ai-resource-solve-timeout-api.md](./contracts/ai-resource-solve-timeout-api.md)。

## Phase 2：实施顺序

1. 先补充 AI 单方案与批量路径的 30 秒预算捕获测试，以及全局 15 秒默认值回归断言。
2. 在 AI 资源助手服务中定义并应用专项 30 秒预算。
3. 调整现有严格资源性能测试，使其快速运行且继续验证单次求解、固定资源和无增配。
4. 更新 AI 资源助手验证文档的求解时限说明。
5. 运行针对性测试、完整相关回归、前端生产构建和真实 Excel 单方案验证。

## 复杂度跟踪

无 Constitution 违反项。本功能不新增服务、共享模型、接口字段、依赖、持久化或页面配置。

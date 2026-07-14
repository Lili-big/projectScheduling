# 实施计划：AI 固定资源单阶段求解

**分支/目录**：`036-ai-single-stage-solve` | **日期**：2026-07-14 | **规格**：[spec.md](./spec.md)

**输入**：来自 `specs/036-ai-single-stage-solve/spec.md` 的功能规格

## 概要

将 AI 经济、平衡、抢工方案的严格固定资源排程从两阶段收敛为一次工期求解。唯一阶段继续使用 `[最大目标延期, 总工期]` 字典序目标并获得完整 60 秒预算；不再计算剩余预算、不再调用第二阶段、不再以累计资源空闲或连续性影响最终排程。现有阶段摘要结构继续返回兼容壳：第一阶段记录真实结果，第二阶段为 `attempted=false`、`skipped_reason=not_applicable`，最终阶段固定为 `primary`。资源空闲和连续性继续从最终排程派生为诊断；历史两阶段快照继续解析。

## 技术上下文

**语言/版本**：Python 3.12+（本地运行时兼容）、TypeScript 5.7、Node.js 24

**主要依赖**：FastAPI、Pydantic、OR-Tools CP-SAT、React 19、Vite 6

**存储**：不新增存储，不迁移或重写本地基准计划快照

**测试**：pytest、AI 资源助手回归、计划管控回归、完整排程回归、TypeScript 类型检查、Vite 生产构建、真实 Excel 三方案验证

**目标平台**：本地 FastAPI 服务与 React Web Demo

**项目类型**：后端排程编排、求解目标分支、前端阶段说明和验证文档的跨层调整

**性能目标**：每套方案只发生一次排程调用；唯一阶段可使用完整 60 秒；不得再预留第二阶段模型构建时间

**约束**：严格固定资源、不自动增配；第一阶段工期目标、任务、工艺、里程碑、硬约束和三态不变；诊断保留；不新增依赖；非 AI 求解入口不变

**规模/范围**：覆盖真实 Excel 数百任务的经济、平衡、抢工三方案，重点影响 `scenario.py`、`solver.py`、AI 资源助手阶段测试、前端阶段解释和验证说明

## Constitution 检查

*门禁：Phase 0 研究前与 Phase 1 设计后均已检查。*

- [x] 已定义唯一输入、输出、工期目标优先级、固定资源硬边界、时限、状态和失败流程。
- [x] 已区分优化目标与求解后诊断。
- [x] 已明确新结果和历史两阶段结果的兼容契约。
- [x] 已定义页面入口、当前状态说明、历史展示和下游失效规则。
- [x] 复用现有求解、模型、组件、接口和测试，不新增依赖或服务。
- [x] 已提供真实 Excel 和可复现小场景验证方向。
- [x] 实施前必须完成 `tasks.md`、`speckit-analyze` 并取得用户确认。

**设计后复检**：通过。方案删除活动求解分支，不新增共享字段、存储或外部依赖；兼容壳避免历史迁移，符合 Constitution MUST 原则。

## 项目结构

### 本功能文档

```text
specs/036-ai-single-stage-solve/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── ai-single-stage-api.md
├── checklists/
│   └── requirements.md
└── tasks.md
```

### 源码结构（仓库根目录）

```text
backend/
├── app/
│   ├── scenario.py
│   └── solver.py
└── tests/
    ├── test_ai_resource_scheduling_assistant.py
    ├── test_plan_control_api.py
    └── test_scheduler.py

frontend/src/
├── domain/resourceAssistant.ts
├── features/resourceAssistant/
│   ├── ResourceAssistantPanel.tsx
│   └── ResourcePlanCard.tsx
└── types/scheduler.ts

docs/
└── AI资源配置与排程优化助手验证说明.md
```

**结构决策**：继续使用 `solve_ai_strict_fixed_resource_scenario()` 作为 AI 专用编排入口，内部只调用一次 `solve_control_priority_schedule_once(..., optimization_stage="primary")`。删除活动第二阶段参数、目标和调用分支；保留响应模型及历史解析。非 AI 调用继续走现有分支。

## Phase 0：研究与决策

研究结论见 [research.md](./research.md)。核心决策：

1. 唯一求解阶段获得完整 60 秒，目标保持 `[最大目标延期, 总工期]`。
2. AI 编排不再计算剩余预算、模型构建预留或第二阶段校验，也不再调用 `optimization_stage="secondary"`。
3. 删除求解器中仅服务于 AI 第二阶段的累计空闲严格改善边界和第二阶段目标分支，通用资源空闲目标能力不变。
4. 新结果保留 `optimization_stages` 外壳，第二阶段固定为不适用，避免共享字段和历史快照迁移。
5. 资源空闲和连续性仍从最终 `ScheduledTask` 计算，明确为诊断。
6. 当前页面只展示一次固定资源工期求解；历史结果存在实际第二阶段时继续展示历史阶段信息。
7. 推荐、基准计划、进度反馈和结果失效继续读取现有工期事实及场景指纹。

## Phase 1：设计与契约

### 单阶段编排

1. 生成当前方案的固定命名资源 `ScheduleInput`。
2. 将完整配置时限传给唯一工期求解。
3. 求解目标保持最大目标延期优先、总工期其次。
4. 直接以该结果生成三态、诊断、核心指标和下游方案结果。
5. 不执行任何第二次排程调用。

### 求解器收敛

- 保留 AI 工期阶段分支，用于关闭通用软目标并构建工期字典序目标。
- 删除 AI 第二阶段入口参数、第一阶段空闲/工期边界传递、第二阶段累计空闲目标和阶段统计。
- 通用求解中的资源空闲目标、任务/资源暖启动和诊断帮助函数不因本功能改变。
- 新性能路径标记为 `ai_strict_fixed_resource_single_stage`，求解调用数固定为 1。

### 响应与历史兼容

- `optimization_stages.primary`：记录唯一阶段状态、最大延期、总工期、证明状态、耗时和 60 秒配置预算。
- `optimization_stages.secondary`：`attempted=false`、`skipped_reason=not_applicable`，其他求解值为空或默认值。
- `selected_stage=primary`、`fallback_reason=null`、`solver_call_count=1`。
- 不删除 `ResourceAssistantSecondaryStageSummary`、`continuity_penalty`、`idle_already_zero` 或历史原因枚举。
- 历史 `selected_stage=secondary` 仍按原值解析和展示。

### 页面交互

- 顶部说明改为“单方案固定资源求解最长 60 秒，目标为最大延期优先、总工期其次”。
- 新结果只展示工期求解说明，不显示“资源空闲未执行”或第二阶段回退行。
- 历史结果的第二阶段实际执行记录仍可显示。
- 修改方案或场景后继续清除旧求解、对比和推荐。

### 失败与状态

- `OPTIMAL/FEASIBLE` 继续生成现有工期三态和最大延期。
- `UNKNOWN/INFEASIBLE/MODEL_INVALID` 直接返回现有无排程或异常事实，不进行第二次尝试。
- 目标缺失、资源覆盖缺失和固定资源诊断口径不变。

### 前后端契约

接口路径、请求和共享字段不变，字段语义见 [contracts/ai-single-stage-api.md](./contracts/ai-single-stage-api.md)。新结果通过既有字段表达“单阶段”，不新增版本或迁移任务。

## Phase 2：实施顺序

1. 先增加一次调用、完整预算、无第二阶段和诊断保留的失败测试。
2. 收敛 `scenario.py` 为一次求解编排并生成兼容阶段摘要。
3. 删除 `solver.py` 中 AI 第二阶段活动参数、目标和统计分支，保留非 AI 能力。
4. 同步历史快照、推荐、基准和进度反馈回归。
5. 更新前端单阶段说明及新旧结果展示分流。
6. 更新验证文档并运行后端、前端及真实 Excel 三方案验证。

## 复杂度跟踪

无 Constitution 违反项。保留第二阶段响应模型属于历史兼容，不代表继续执行第二阶段；活动求解路径和用户可见当前流程均收敛为一次求解。

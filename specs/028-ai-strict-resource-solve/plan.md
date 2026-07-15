# 实施计划：AI 方案严格固定资源单次求解

**分支/目录**：`028-ai-strict-resource-solve` | **日期**：2026-07-13 | **规格**：[spec.md](./spec.md)

**输入**：来自 `specs/028-ai-strict-resource-solve/spec.md` 的功能规格

## 概要

为 AI 多方案比选建立专用固定资源求解编排：严格使用 LLM 推荐或用户调整后的 `quantity`，任务图和命名资源只生成一次，直接运行一次保留现有三目标项的完整 CP-SAT 模型。AI 路径不进入基础排程和资源增量建议。结果在原始求解器状态之外增加 `met`、`not_met`、`unconfirmed`、`infeasible` 四种业务状态，并让确定性推荐只接收 `met` 方案。通用模拟求解继续保留原有资源增量行为。

## 技术上下文

**语言/版本**：Python 3.12+（本地 3.14.3）、TypeScript 5.7、Node.js 24

**主要依赖**：FastAPI、Pydantic、OR-Tools CP-SAT、React 19、Vite 6

**存储**：不新增存储；沿用页面会话状态和当前请求响应

**测试**：pytest、TypeScript 类型检查、Vite 生产构建、必要的本地页面验证

**目标平台**：本地 FastAPI 服务与 React Web Demo

**项目类型**：跨后端算法编排、共享响应契约和 AI 多方案比选页面的 Web 功能变更

**性能目标**：每个 AI 单方案请求只调用一次 CP-SAT，不触发资源增量搜索；端到端耗时不超过求解时间上限加 2 秒固定处理开销

**约束**：目标函数三项、权重、硬约束和工艺逻辑保持不变；不新增依赖；通用模拟求解不变；工作量为 0 的工艺资源保持 0；只允许 `met` 参与推荐

**规模/范围**：影响 AI 单方案与兼容批量求解、方案结果模型、推荐规则、方案卡及对比展示；不修改 LLM 生成和计划基准/进度预测模块

## Constitution 检查

*门禁：Phase 0 研究前与 Phase 1 设计后均已检查。*

- [x] 已完成需求评审与优化方向收敛，结论为建议推进。
- [x] `spec.md` 已引用现有文档、Demo 和真实代码路径。
- [x] 已明确输入、输出、硬约束、目标函数、状态优先级、失败态及推荐门禁。
- [x] 已定义后端字段、前端展示、失效行为、接口兼容与通用入口回归边界。
- [x] 未把 Demo 临时限制提升为正式产品目标；本期只收敛 AI 入口的求解语义。
- [x] 规格、计划、研究、数据模型、契约、验证指南和任务使用中文简体。
- [x] 不修改代码，直至 `tasks.md` 和 `$speckit-analyze` 经用户确认。

**设计后复检**：通过。不存在 Constitution MUST 级冲突，无需复杂度豁免。

## 项目结构

### 本功能文档

```text
specs/028-ai-strict-resource-solve/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── ai-strict-resource-solve-api.md
├── checklists/
│   └── requirements.md
└── tasks.md
```

### 源码结构（仓库根目录）

```text
backend/
├── app/
│   ├── models.py
│   ├── scenario.py
│   ├── solver.py
│   └── services/
│       └── ai_resource_scheduling_assistant.py
└── tests/
    ├── test_ai_resource_scheduling_assistant.py
    └── test_scheduler.py

frontend/src/
├── types/scheduler.ts
├── domain/resourceAssistant.ts
└── features/resourceAssistant/
    ├── ResourceAssistantPanel.tsx
    ├── ResourcePlanCard.tsx
    └── MetricComparisonTable.tsx
```

**结构决策**：保留现有 API 路径和页面组件。后端在 `scenario.py` 增加 AI 专用严格固定资源编排，在 `solver.py` 提供不依赖基础排程的一次完整目标模型入口；AI 服务只负责将资源方案写入场景、调用专用编排、组装指标和推荐。通用 `solve_scenario()` 及 `_fixed_resource_recommendation()` 不改行为。

## Phase 0：研究与决策

研究结论见 [research.md](./research.md)。核心决策如下：

1. AI 入口绕过通用 `solve_scenario()`，避免目标延期后自动进入资源建议。
2. 从现有 `solve_control_priority_schedule()` 中抽取可直接执行完整目标模型的内部能力；通用入口继续保留基础排程兼容行为。
3. 基础排程只用于旧流程的基线比较和部分诊断，不是当前三目标模型成立的前提；AI 路径将基线字段标记为未评估。
4. 业务状态与 CP-SAT 原始状态并存，避免将 `FEASIBLE` 的延期结果误判为已证明资源不足。
5. 推荐不再使用“存在可行排程”的兜底，只比较 `plan_status=met`。

## Phase 1：设计与契约

### 后端求解分层

1. `generate_schedule_input_from_scenario()` 按方案当前 `quantity` 生成一次任务图和命名资源。
2. 新增 AI 严格编排函数，调用一次无基础排程的完整目标求解入口，并使用同一请求时间上限。
3. 求解入口保留现有资源覆盖、前后置、资源互斥、连续梁班组、里程碑及三个目标项；仅让 `baseline_result` 对诊断可选。
4. 编排函数根据求解状态、目标是否存在及延期数据生成四种业务状态，返回无候选方案的 `ScenarioSolveResult`。
5. AI 服务将状态和输入资源快照写入 `ResourceAssistantPlanResult`，并保留现有指标计算。

### 状态判定顺序

```text
输入或运行环境错误 -> 请求失败，不生成业务状态
资源覆盖错误 / CP-SAT INFEASIBLE -> infeasible
CP-SAT UNKNOWN -> unconfirmed
无目标依据 -> unconfirmed
OPTIMAL/FEASIBLE 且目标无延期 -> met
OPTIMAL 且目标延期 -> not_met
FEASIBLE 且目标延期 -> unconfirmed
```

### 前后端契约

接口保持 `POST /api/ai-resource-assistant/solve-plan`。`ResourceAssistantPlanResult` 增加向后兼容字段：

- `plan_status`：四种业务状态；技术失败时允许为空。
- `solver_status`：原始求解状态；技术失败时允许为空。
- `input_resource_quantities`：本次实际采用的资源类型与数量快照。
- `resource_expansion_attempted`：AI 路径固定为 `false`。

现有 `result.stats.target_achievement` 继续承载目标是否存在、强制里程碑延期合计、固定工期超期、失败原因和时间预算；其中 `target_status` 在 AI 路径归一为四种业务状态。详细契约见 [contracts/ai-strict-resource-solve-api.md](./contracts/ai-strict-resource-solve-api.md)。

### 页面交互

- 工作流状态 `pending/solving/failed/...` 与业务结果状态分开显示。
- 方案卡显示“目标已满足 / 已证明延期 / 限时未确认 / 物理不可行”。
- `not_met` 显示延期摘要；`unconfirmed` 显示“未证明更优解不存在”；`infeasible` 显示诊断入口。
- 对比结果加入方案业务状态；只有 `met` 进入推荐。
- 资源数量或项目变化继续沿用现有结果失效逻辑。

## Phase 2：实施顺序

1. 先补充状态分类、单次调用和无增配分支的后端失败测试。
2. 抽取一次完整目标求解能力，使基础排程诊断可选并保持通用入口回归。
3. 实现 AI 专用严格编排和响应字段，修正推荐门禁。
4. 同步前端类型、方案卡与对比展示。
5. 运行针对性后端测试、通用求解回归、前端构建和页面验证。

## 复杂度跟踪

无 Constitution 违反项。新增专用编排是为了隔离 AI 严格资源语义与通用模拟求解的资源建议语义；没有新增服务、依赖或持久化层。

# 实施计划：AI 固定资源两阶段排程优化

**分支/目录**：`033-ai-two-stage-resource-optimization` | **日期**：2026-07-13 | **规格**：[spec.md](./spec.md)

**输入**：来自 `specs/033-ai-two-stage-resource-optimization/spec.md` 的功能规格

## 概要

将 AI 多方案比选的严格固定资源单次混合目标求解改为共享 30 秒预算的两阶段编排。第一阶段不构建资源空闲和路径连续性变量，以“最大目标延期、总工期”的严格字典序获得工期基线；第二阶段在最大延期和总工期不恶化的硬边界内，使用第一阶段排程作为提示，按“累计资源空闲、资源连续性罚分”的严格字典序尽力改善资源组织。第二阶段无结果、越界或无改进时回退第一阶段；通用求解入口和 LLM 资源生成保持不变。

## 技术上下文

**语言/版本**：Python 3.12+（本地 3.14.3）、TypeScript 5.7、Node.js 24

**主要依赖**：FastAPI、Pydantic、OR-Tools CP-SAT、React 19、Vite 6

**存储**：不新增存储；响应阶段摘要随当前页面会话使用，历史结果通过可选字段兼容

**测试**：pytest、真实 Excel 可复现实验、TypeScript 类型检查、Vite 生产构建、必要的本地页面验证

**目标平台**：本地 FastAPI 服务与 React Web Demo

**项目类型**：后端排程算法、AI 专用求解编排、共享响应契约和 AI 多方案比选展示的跨层变更

**性能目标**：单方案两个阶段共享 30 秒总预算；第一阶段耗尽预算时不启动第二阶段；接口固定处理开销维持在现有量级

**约束**：严格使用 LLM 推荐或用户调整资源；不自动增配；工艺、任务、硬约束和里程碑定义不变；不新增依赖；不恢复公开可配置的废弃连续性目标；通用求解入口不变

**规模/范围**：重点覆盖真实 Excel 的 351 任务、19 至 38 个命名资源三方案；影响 `models.py`、`scenario.py`、`solver.py`、AI 资源助手服务、前端类型与方案结果展示及相关测试

## Constitution 检查

*门禁：Phase 0 研究前与 Phase 1 设计后均已检查。*

- [x] 用户已确认继续推进已评审的两阶段优化方向。
- [x] `spec.md` 已引用现有文档、Spec、真实 Demo 与代码事实。
- [x] 已明确输入、输出、固定资源硬边界、两个阶段的目标顺序、预算、失败回退和状态兼容。
- [x] 已区分当前资源连续性诊断与本功能新增的第二阶段优化目标。
- [x] 已定义共享字段、页面状态、历史兼容和完整验收场景。
- [x] 未把真实 Excel 基线数值提升为所有项目的产品承诺，仅作为可复现回归样例。
- [x] 全部 Spec Kit 产物使用中文简体；代码标识符、路径和命令保留原文。
- [x] 不修改实现代码，直至 `tasks.md` 和 `$speckit-analyze` 经用户确认。

**设计后复检**：通过。两阶段专用编排用于隔离 AI 固定资源语义，不新增服务、依赖或持久化层，不存在 Constitution MUST 级冲突。

## 项目结构

### 本功能文档

```text
specs/033-ai-two-stage-resource-optimization/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── ai-two-stage-resource-solve-api.md
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
    ├── test_plan_control_repository.py
    └── test_scheduler.py

frontend/src/
├── types/scheduler.ts
├── domain/resourceAssistant.ts
└── features/resourceAssistant/
    ├── ResourceAssistantPanel.tsx
    └── ResourcePlanCard.tsx
```

**结构决策**：保留现有 API 路径和 AI 页面结构。`solver.py` 承担两个阶段的模型构建、目标和提示；`scenario.py` 提供 AI 专用两阶段编排与结果选择；AI 服务组装阶段摘要；前端只解释阶段状态。普通 `solve_scenario()`、最少资源和成本求解不调用新编排。

## Phase 0：研究与决策

研究结论见 [research.md](./research.md)。核心决策如下：

1. 第一阶段最大延期使用强制里程碑延期和固定总工期超期的最大值，不再以累计延期作为阶段目标。
2. 两个阶段内部均采用有上界保证的字典序目标，不依赖经验权重表达优先级。
3. 第二阶段只固定第一阶段最大延期和总工期上限，不固定全部任务日期，以保留资源组织改进空间。
4. 第二阶段连续性与页面 `transfer_penalty` 统一，不重新开放已废弃的共享 `resource_path_continuity` 配置项。
5. 第二阶段路径候选必须稀疏化并始终纳入第一阶段实际转移弧，避免路径模型排除 warm start。
6. 最终是否采用第二阶段按“工期边界、资源快照、任务完整性、次目标严格改善”四重校验；否则回退第一阶段。
7. 工期业务状态使用第一阶段最优性事实，资源组织最优性单独展示，避免第二阶段 `FEASIBLE` 错误降级工期状态。

## Phase 1：设计与契约

### 两阶段求解编排

1. `generate_schedule_input_from_scenario()` 继续按方案当前资源数量只生成一次业务输入；两个阶段使用其深拷贝，任务、逻辑和资源保持一致。
2. 第一阶段构建命名资源、前后置、里程碑、执行约束和资源互斥模型，但不构建资源空闲及路径连续性变量。
3. 第一阶段建立 `max_target_delay`，其值为所有强制里程碑延期和固定总工期超期的最大值；目标为严格字典序 `[max_target_delay, makespan]`。
4. 第二阶段重新构建同一基础模型，增加 `max_target_delay <= primary.max_target_delay` 和 `makespan <= primary.makespan`，并提示第一阶段的任务时间、资源分配和资源路径。
5. 第二阶段构建资源内部空闲及稀疏路径转移目标，按严格字典序 `[resource_idle_days, continuity_penalty]` 求解。
6. 第二阶段使用第一阶段结束后的剩余请求预算；剩余预算低于安全启动阈值时标记跳过。
7. 第二阶段结果通过选择校验且次目标严格改善时采用，否则返回第一阶段排程。

### 字典序目标

第一阶段使用排程时间范围上界保证优先级：

```text
primary_score = max_target_delay * (horizon + 1) + makespan
```

第二阶段先计算连续性罚分安全上界，再保证空闲优先：

```text
secondary_score = resource_idle_days * (continuity_upper_bound + 1) + continuity_penalty
```

两个上界必须来自当前模型可证明的范围，并在建模前校验目标系数及最大目标值处于安全整数范围。

### 连续性建模

- 连续性罚分采用 `jump_pier_count * 4 + side_switch_count * 2 + cross_side_jump_count * 6 + path_group_switch_count`。
- 路径节点优先按同桥、同幅、同墩、同构件、同工艺聚合，机械桩基复用现有墩组粒度。
- 候选转移弧限制为相邻/邻近空间节点、合法跨幅节点和第一阶段实际后继弧；不建立全量任务两两连接。
- 缺少空间信息的节点不产生虚构空间罚分，但保留可用的路径组切换诊断。
- 第一阶段实际路径弧必须加入候选并获得提示，使第二阶段至少拥有一份可复现的工期不退化候选。

### 预算与回退

- AI 单方案入口继续配置 30 秒请求预算。
- 第一阶段可使用全部剩余预算；若提前结束，第二阶段使用剩余预算。
- 第一阶段无排程、已耗尽预算或剩余时间不足时不启动第二阶段。
- 第二阶段 `UNKNOWN`、`INFEASIBLE`、模型异常、越界、资源变化、任务缺失或无严格次目标改善时回退第一阶段。
- `solver_call_count` 为实际调用次数；`performance_path` 更新为两阶段专用值；自动增配标记始终为 `false`。

### 状态与结果选择

- 最终 `ScheduleResult.status` 反映被选中排程对应求解阶段的原始状态。
- `target_achievement` 增加第一阶段状态与工期最优性来源，工期三态不再从第二阶段原始状态推断。
- 第一阶段 `OPTIMAL` 且存在延期时仍可证明“工期目标未满足”；第二阶段 `FEASIBLE` 不改变该证明。
- 第二阶段 `FEASIBLE` 仅表示资源组织已改善但未证明次目标最优。
- 历史结果没有阶段摘要时，前端继续按现有 `schedule_outcome_status`、`plan_status` 和 `solver_status` 展示。

### 前后端契约

接口保持 `POST /api/ai-resource-assistant/solve-plan` 与现有批量求解入口。`ResourceAssistantPlanResult` 增加可选 `optimization_stages`，包含第一阶段摘要、第二阶段摘要、最终选择阶段、总预算和回退原因；完整字段见 [contracts/ai-two-stage-resource-solve-api.md](./contracts/ai-two-stage-resource-solve-api.md)。

方案卡和详情增加简洁说明：

- “工期排程已证明最优 / 工期排程限时未确认”；
- “资源组织已优化 / 尚未证明最优 / 未执行 / 已回退”；
- 仍以三态工期状态作为推荐和基准计划判断依据。

## Phase 2：实施顺序

1. 先补最大延期字典序、第二阶段工期不退化和回退的后端失败测试。
2. 抽取可复用的固定资源基础模型上下文，保持旧求解路径默认行为不变。
3. 实现第一阶段工期模型和阶段摘要。
4. 实现第二阶段空闲、稀疏连续性目标、warm start 和剩余预算控制。
5. 实现结果校验、阶段选择、工期状态证明来源和 API 可选字段。
6. 同步前端类型、方案卡与详情说明，保留历史结果兼容。
7. 运行针对性测试、完整排程回归、持久化回归、前端构建和真实 Excel 三方案验证。

## 复杂度跟踪

无 Constitution 违反项。连续性优化需要新增第二阶段内部路径目标，但不恢复为用户可配置公共目标，不扩大到通用求解入口；稀疏候选和失败回退用于控制复杂度。

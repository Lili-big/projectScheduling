# 实施计划：AI 第二阶段仅优化资源空闲

**分支/目录**：`035-ai-idle-only-second-stage` | **日期**：2026-07-14 | **规格**：[spec.md](./spec.md)

**输入**：来自 `specs/035-ai-idle-only-second-stage/spec.md` 的功能规格

## 概要

收窄 AI 多方案比选的严格固定资源两阶段排程：第一阶段继续按 `[最大目标延期, 总工期]` 求解，第二阶段在第一阶段工期上限内只最小化累计资源空闲，不再构建资源路径节点、候选转移弧、连续性罚分或连续性改善约束。连续性指标继续在最终排程生成后计算并作为诊断返回；第二阶段只有累计资源空闲严格下降才可采用，否则回退第一阶段。60 秒共享预算、固定资源、不增配、工期三态、推荐和基准计划链路保持不变。

## 技术上下文

**语言/版本**：Python 3.12+（本地运行时兼容）、TypeScript 5.7、Node.js 24

**主要依赖**：FastAPI、Pydantic、OR-Tools CP-SAT、React 19、Vite 6

**存储**：不新增存储；阶段摘要继续随接口响应和现有基准计划快照使用

**测试**：pytest、AI 资源助手回归、计划管控持久化回归、TypeScript 类型检查、Vite 生产构建、真实 Excel 三方案验证

**目标平台**：本地 FastAPI 服务与 React Web Demo

**项目类型**：后端排程算法、AI 专用两阶段编排、前端阶段说明和验证文档的跨层调整

**性能目标**：单方案两阶段继续共享 60 秒；第二阶段不再构建连续性路径模型，模型构建和搜索复杂度不得高于当前实现；第一阶段空闲为 0 时可直接跳过第二阶段

**约束**：严格使用 LLM 推荐或用户调整后的固定资源；不自动增配；第一阶段目标、任务、工艺、里程碑和硬约束不变；连续性诊断保留；不新增依赖；非 AI 求解入口不变

**规模/范围**：重点覆盖真实 Excel 的数百任务、多命名资源三方案；影响 `solver.py`、`scenario.py`、AI 资源助手阶段测试、前端阶段文案和验证说明，不新增服务或持久化模型

## Constitution 检查

*门禁：Phase 0 研究前与 Phase 1 设计后均已检查。*

- [x] 用户已明确要求第二阶段不求解资源连续性。
- [x] `spec.md` 已引用现有两阶段 Spec、验证文档、Demo 与代码事实。
- [x] 已明确输入、输出、固定资源硬边界、目标优先级、预算、回退和历史兼容。
- [x] 已区分“连续性优化目标”和“求解后连续性诊断”。
- [x] 已定义第二阶段只按累计资源空闲严格改善的采用规则。
- [x] 未把 Demo 基线数值提升为正式产品承诺。
- [x] 全部 Spec Kit 产物使用中文简体。
- [x] 不修改实现代码，直至 `tasks.md` 和 `$speckit-analyze` 经用户确认。

**设计后复检**：通过。本方案在现有两阶段编排中删除一组目标建模能力，不新增模块、依赖、响应字段或持久化层；仅对现有 `secondary.skipped_reason` 增加向后兼容枚举值，不存在 Constitution MUST 级冲突。

## 项目结构

### 本功能文档

```text
specs/035-ai-idle-only-second-stage/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── ai-idle-only-secondary-api.md
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
└── features/resourceAssistant/
    └── ResourceAssistantPanel.tsx

docs/
└── AI资源配置与排程优化助手验证说明.md
```

**结构决策**：复用现有 `solve_ai_strict_fixed_resource_scenario()` 两阶段编排和 `solve_control_priority_schedule_once()` 阶段参数。`solver.py` 只构建第二阶段资源空闲目标；`scenario.py` 只按空闲判断严格改善和回退；连续性继续通过最终 `ScheduledTask` 诊断生成。API 与模型字段保持兼容，前端只同步阶段说明。

## Phase 0：研究与决策

研究结论见 [research.md](./research.md)。核心决策如下：

1. 第二阶段目标直接变为 `minimize(sum(resource_idle_days))`，不再使用连续性安全上界拼接字典序分数。
2. 第二阶段不调用资源路径目标构建，不生成路径节点、转移弧、`AddCircuit` 或连续性罚分变量；任务时间和资源分配暖启动继续保留。
3. 第二阶段增加 `resource_idle_days <= primary_resource_idle_days - 1` 的严格改善边界；第一阶段空闲为 0 时直接跳过。
4. 采用校验只比较第二阶段与第一阶段的累计资源空闲；连续性诊断变好或变差均不影响阶段选择。
5. `continuity_penalty`、`continuity_metrics` 等现有字段继续返回诊断值，避免历史结果和前端类型迁移，但不再称为第二阶段目标或改善条件。
6. 第二阶段仍固定第一阶段最大延期和总工期上限，仍严格使用当前资源快照和完整任务集合。
7. 非 AI 通用求解中的连续性配置和诊断不在本次范围内，避免扩大影响。

## Phase 1：设计与契约

### 第二阶段模型

1. 继续从第一阶段排程获得最大延期、总工期、累计资源空闲和任务/资源提示。
2. 第一阶段无排程、剩余预算不足或累计资源空闲为 0 时不启动第二阶段。
3. 第二阶段重新使用同一固定资源基础模型，增加：
   - `max_target_delay <= primary.max_target_delay`；
   - `makespan <= primary.makespan`；
   - `total_resource_idle <= primary.resource_idle - 1`。
4. 第二阶段只创建各已使用命名资源的工作量、首个开始、最后结束和内部空闲变量。
5. 第二阶段目标为 `minimize(total_resource_idle)`，不创建连续性路径建模变量。
6. 继续提示第一阶段的任务开始、结束和资源分配；不再提示资源路径弧。

### 结果复核与采用

第二阶段结果必须同时满足：

1. 状态为 `OPTIMAL` 或 `FEASIBLE` 且有完整排程；
2. 最大延期不超过第一阶段；
3. 总工期不超过第一阶段；
4. 任务 ID 集合完整且一致；
5. 所用资源均属于当前固定资源快照；
6. 累计资源空闲严格小于第一阶段。

连续性诊断不参与上述判断。若任一条件失败，返回第一阶段排程；`no_secondary_improvement` 的业务解释调整为“资源空闲没有严格改善”。

### 连续性诊断兼容

- 最终排程仍执行现有连续性统计，生成跳墩、换幅、跨幅跳墩、方向反转、路径组切换和连续性得分。
- `ResourceAssistantSecondaryStageSummary.continuity_penalty` 保留为可选诊断字段，新结果可继续填充值。
- 页面可以展示连续性诊断，但不得描述为第二阶段优化目标、采用条件或推荐门禁。
- 历史结果无需迁移；旧结果的字段仍可解析。

### 预算与状态

- 每套方案继续获得 60 秒共享预算；第二阶段只使用第一阶段结束后的剩余预算。
- 第一阶段空闲为 0 时，第二阶段摘要固定使用 `skipped_reason = "idle_already_zero"` 表达“累计资源空闲已为 0，无需继续优化”；这是对现有可选枚举的向后兼容扩展。
- 第二阶段 `FEASIBLE` 仍表示获得空闲改善但尚未证明空闲目标最优；不影响第一阶段工期证明。
- 工期三态、推荐门禁、设为基准和进度反馈继续读取现有工期事实。

### 前后端契约

接口路径、请求结构和响应结构保持不变，字段语义见 [contracts/ai-idle-only-secondary-api.md](./contracts/ai-idle-only-secondary-api.md)。重点更新：

- `secondary.resource_idle_days`：唯一第二阶段优化指标；
- `secondary.continuity_penalty`：兼容诊断字段；
- `secondary.skipped_reason=idle_already_zero`：第一阶段累计资源空闲已到达数学下界；
- `no_secondary_improvement`：仅表示累计资源空闲没有严格下降；
- 用户可见说明统一为“第二阶段优化资源空闲，连续性仅作诊断”。

## Phase 2：实施顺序

1. 先调整第二阶段目标、无路径模型、空闲严格改善和连续性不参与采用的失败测试。
2. 修改第二阶段建模开关和目标，移除连续性路径变量、上界和内部参数依赖。
3. 修改两阶段编排：空闲为 0 时跳过，仅按空闲复核和采用，连续性只写诊断摘要。
4. 同步 AI 服务回归、阶段兼容和计划管控历史读取测试。
5. 更新前端阶段文案和验证说明，保留连续性诊断展示。
6. 运行针对性后端测试、完整排程回归、计划管控回归、前端类型检查和生产构建。
7. 使用真实 Excel 三方案验证工期不退化、空闲严格改善、无连续性路径建模和固定资源不变。

## 复杂度跟踪

无 Constitution 违反项。本次从第二阶段删除连续性建模，整体复杂度下降；保留诊断字段是为了接口和历史数据兼容，不构成继续求解连续性的例外。

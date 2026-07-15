# 实施计划：AI 方案状态三态化与最大延期口径优化

**分支/目录**：`029-ai-status-delay-consolidation` | **日期**：2026-07-13 | **规格**：[spec.md](./spec.md)

**输入**：来自 `specs/029-ai-status-delay-consolidation/spec.md` 的功能规格

## 概要

在不改变 CP-SAT 求解和旧四状态兼容字段的前提下，为 AI 方案结果增加三态主状态、状态原因与最大延期字段。后端统一计算三态和最大延期，前端方案卡、对比表与推荐使用新字段，并在缺失时按旧四状态和求解事实回退映射。历史基准快照继续原样读取，不迁移、不重写。

## 技术上下文

**语言/版本**：Python 3.12+（当前本地虚拟环境）、TypeScript 5.7、Node.js 22+

**主要依赖**：FastAPI、Pydantic、OR-Tools CP-SAT、React 19、Vite 6

**存储**：沿用 `.local-data/plan-control-store.json` 的本地计划版本存储；不新增存储，不迁移或重写历史文件

**测试**：pytest、TypeScript 类型检查、Vite 生产构建、本地页面端到端验证

**目标平台**：本地 FastAPI 单服务 Demo 与 React Web 页面

**项目类型**：跨后端结果契约、推荐规则、前端状态展示和历史快照兼容的 Web 功能变更

**性能目标**：只增加结果聚合与映射，不增加 CP-SAT 调用；单方案新增处理开销低于 10 毫秒

**约束**：不修改目标函数、硬约束、求解时间、资源数量、自动增配、逐里程碑日期、基准资格和进度预测算法；不新增依赖

**规模/范围**：影响 AI 单方案结果、三方案对比、推荐、方案卡、共享类型、目标评估元数据、历史基准快照读取和相关文档测试

## Constitution 检查

*门禁：Phase 0 研究前与 Phase 1 设计后均已检查。*

- [x] 需求已完成评审并经用户确认实施，业务目标与范围明确。
- [x] `spec.md` 已引用 Spec 027、Spec 028、现有验证文档和真实 Demo/代码事实。
- [x] 输入、输出、状态优先级、延期公式、推荐门禁、历史兼容和异常场景均可测试。
- [x] 前后端共享字段、页面显示、失效行为和持久化兼容已明确。
- [x] 不修改 CP-SAT 目标、约束、资源和工期明细计算，不提升 Demo 临时限制。
- [x] 所有 Spec Kit 产物使用中文简体。
- [x] 在 `tasks.md` 与 `$speckit-analyze` 经用户确认前不进入代码实施。

**设计后复检**：通过。新增字段是避免破坏历史快照和现有客户端的最小兼容方案，不存在 Constitution MUST 级冲突。

## 项目结构

### 本功能文档

```text
specs/029-ai-status-delay-consolidation/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── ai-status-delay-api.md
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
│   └── services/
│       ├── ai_resource_scheduling_assistant.py
│       └── progress_forecast.py
└── tests/
    ├── test_ai_resource_scheduling_assistant.py
    ├── test_scheduler.py
    ├── test_plan_control_api.py
    └── test_plan_control_repository.py

frontend/src/
├── types/scheduler.ts
├── domain/resourceAssistant.ts
└── features/resourceAssistant/
    ├── ResourcePlanCard.tsx
    └── MetricComparisonTable.tsx

docs/
└── AI资源配置与排程优化助手验证说明.md
```

**结构决策**：复用当前结果评估、AI 服务、领域展示函数和计划版本模型。`scenario.py` 继续产生旧四状态并同时生成三态、原因与最大延期；AI 服务把新字段写入方案结果并用三态执行推荐门禁；前端领域层统一负责新字段优先、旧字段回退和中文显示。无需修改 API 路由、求解器、Netlify 或计划存储结构。

## Phase 0：研究与决策

研究结论见 [research.md](./research.md)。核心决策如下：

1. 三态采用新增字段，不复用或删除 `plan_status`，避免旧基准快照反序列化失败。
2. 新状态原因保留“已证明延期 / 限时延期 / 限时无排程 / 已证明不可行 / 资源覆盖失败 / 目标缺失”区别。
3. 最大延期由后端从逐里程碑结果和固定总工期超期统一计算，所有前端入口直接使用同一字段。
4. 旧累计延期和逐里程碑明细保持不变；最大延期只改变摘要和三态零值判断。
5. 推荐优先使用新三态，历史数据缺失新字段时回退旧 `plan_status=met`。
6. 目标缺失不是三种正常业务结果，返回空三态和 `target_missing` 原因。

## Phase 1：设计与契约

### 后端评估顺序

```text
请求/运行技术失败 -> 工作流失败，三态为空
目标缺失 -> 三态为空，原因 target_missing
存在排程且 max_target_delay_days = 0 -> duration_target_met
存在排程且 max_target_delay_days > 0 -> duration_target_not_met
不存在排程且 UNKNOWN -> no_feasible_schedule / time_limit_no_schedule
不存在排程且 INFEASIBLE -> no_feasible_schedule / proven_infeasible 或 resource_coverage_missing
```

`plan_status` 与 `target_status` 继续按 Spec 028 生成，用于兼容和精细诊断。详细字段与回退规则见 [contracts/ai-status-delay-api.md](./contracts/ai-status-delay-api.md)。

### 最大延期

```text
hard_milestone_late_days = 所有强制里程碑延期之和（保留）
fixed_duration_overrun_days = 固定总工期超期（保留）
max_target_delay_days = max(每个强制里程碑延期, fixed_duration_overrun_days)
```

空集合以固定总工期超期为候选；两者均无可评估目标时三态为空，不使用 `0` 推断满足。

### 历史兼容

- 新结果同时返回新三态字段和旧 `plan_status`。
- 历史快照缺少新字段时，前端和推荐服务按旧状态、`solver_status`、`has_schedule` 与目标存在性映射。
- 旧 `met` 映射为 `duration_target_met`；旧 `not_met` 映射为 `duration_target_not_met`；旧 `unconfirmed` 根据是否有排程和目标映射；旧 `infeasible` 映射为 `no_feasible_schedule`。
- Pydantic 模型只增加默认可空字段，因此计划存储无需迁移。

## Phase 2：实施顺序

1. 先增加共享类型与后端状态矩阵、最大延期和历史回退测试。
2. 在 AI 严格结果评估中生成新字段，保持旧四状态输出不变。
3. 更新推荐门禁和对比结果，增加新三态优先与旧字段回退。
4. 更新前端类型、领域显示、方案卡和对比表。
5. 补齐历史计划读取、结果失效、基准和进度链路回归。
6. 更新验证文档并运行 quickstart 全部场景。

## 复杂度跟踪

无 Constitution 违反项。新字段与兼容映射是避免改写历史计划数据的必要最小复杂度；不新增服务、依赖、页面或持久化层。

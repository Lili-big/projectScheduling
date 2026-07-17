# 实施计划：架梁专项与综合排程融合

**分支/目录**：`041-girder-scheduling-integration` | **日期**：2026-07-15 | **规格**：[spec.md](./spec.md)

**输入**：来自 `specs/041-girder-scheduling-integration/spec.md` 的功能规格

## 概要

将独立“架梁倒排”能力迁入当前排程主产品，形成统一项目数据、架梁专项配置、分跨架梁任务、综合 CP-SAT 排程、闭环收敛、统一发布和架梁实绩滚动重排。正式架梁计算由后端单一实现负责；原 TypeScript 逻辑仅作为迁移期黄金样例来源。现有 `ScenarioInput -> GeneratedScheduleInput -> ScheduleResult` 主链路保持兼容，通过可选架梁配置、领域适配器和联合编排服务扩展，不把库存与路线模拟细节耦合进通用求解器。

## 技术上下文

**语言/版本**：Python 3.12（Docker 运行基线）、TypeScript 5.7、Node.js 22（构建基线）

**主要依赖**：FastAPI、Pydantic、OR-Tools CP-SAT、openpyxl、React 19、Vite 6；不新增第三方运行时依赖

**存储**：沿用 `.local-data/plan-control-store.json` 的线程安全原子写入模式，升级存储模型以容纳项目主数据版本、方案配置版本、联合计算快照和架梁实绩；保留旧 `plan-control/v1` 数据读取兼容

**测试**：pytest 后端单元/集成测试、现有前端 Node 测试、TypeScript 编译与 Vite 构建、黄金样例对照、真实项目影子验证

**目标平台**：本地 FastAPI 单服务、开发态 Vite 前端、Docker 后端和 Netlify 静态前端

**项目类型**：前后端 Web 应用，包含确定性架梁领域算法、CP-SAT 联合排程、版本持久化和滚动计划管控

**性能目标**：在不少于 50 个桥梁幅别节点、300 个架梁分跨、2 个梁场、2 条启用路线和 800 个综合任务的固定夹具下，联合计算在 10 分钟内返回 `converged`、`not_converged`、`infeasible` 或 `blocked` 明确状态；单次计算默认最多 10 轮，并在检测到状态循环时提前终止

**约束**：路线节点顺序不由求解器改变；桥梁全局唯一架设；库存不得为负；通道开放是硬约束；倒排建议日期默认是高优先级软控制；只有明确承诺是硬里程碑；已发生实绩不可改写；不得静默降低约束；未收敛结果不可发布；不迁移旧计算结果；不修改 README、不提交或推送

**规模/范围**：新增一个后端架梁领域包、一个联合编排服务、一个任务适配服务、一组版本与实绩模型、新接口契约、一个前端 `girderPlanning` 功能模块，并扩展现有方案求解、计划发布、进度快照和滚动预测测试

## Constitution 检查

*门禁：Phase 0 研究前必须通过；Phase 1 设计后再次检查。*

- [x] 已通过逐项需求发现确认业务目标、MVP、边界、规则、迁移和验收门槛。
- [x] `spec.md` 已引用来源文档、现有计划管控规格、Demo 行为和代码事实。
- [x] 已明确架梁算法、CP-SAT、资源、工期、库存、通道、前后端契约和版本影响。
- [x] 已定义输入、输出、硬约束、软控制、结果状态、边界场景和可复现验收故事。
- [x] 未将原应用的临时限制直接提升为正式规则；多路线共享桥梁等冲突口径已由用户确认。
- [x] 全部 Spec Kit 产物使用中文简体，代码标识符和路径保持原文。
- [x] 实施前仍需完成 `tasks.md`、`$speckit-analyze` 并获得用户确认。

**Phase 1 设计后复核**：通过。数据模型区分配置事实、派生归属和结果快照；接口包含版本指纹、失效和冲突状态；通用求解器与架梁领域保持单向 DTO 边界；未发现 Constitution 违反项。

## 项目结构

### 本功能文档

```text
specs/041-girder-scheduling-integration/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── girder-scheduling-api.yaml
├── checklists/
│   └── requirements.md
└── tasks.md
```

### 源码结构（仓库根目录）

```text
backend/
├── app/
│   ├── models.py                         # 共享请求、结果、计划与实绩模型
│   ├── main.py                           # 现有 API 入口及新增架梁/联合排程接口
│   ├── scenario.py                       # 通用任务生成，接收架梁任务适配结果
│   ├── solver.py                         # 保持通用 CP-SAT 求解职责
│   ├── girder_planning/
│   │   ├── models.py                     # 架梁领域内部模型
│   │   ├── validation.py                 # 映射、路线、覆盖和物料完整性
│   │   ├── import_service.py             # 旧工点输入规范化
│   │   ├── ownership.py                  # 最早到达与唯一架梁归属
│   │   ├── supply_simulator.py           # 产梁和库存日序列
│   │   ├── route_simulator.py            # 固定路线推进和转场
│   │   ├── passage_service.py            # 通道释放日期和依赖
│   │   ├── backward_scheduler.py         # 建议最迟日期与风险
│   │   └── diagnostics.py                # 统一诊断构造
│   └── services/
│       ├── girder_schedule_adapter.py    # 架梁结果转为通用分跨任务与关系
│       ├── integrated_schedule.py        # 联合迭代、收敛和快照
│       ├── plan_control_repository.py    # 三层版本与原子失效
│       └── progress_forecast.py          # 架梁实绩与剩余计划联算
└── tests/
    ├── fixtures/girder_planning/
    ├── test_girder_planning.py
    ├── test_integrated_schedule.py
    ├── test_girder_progress_forecast.py
    ├── test_plan_control_repository.py
    └── test_scheduler.py

frontend/
└── src/
    ├── api/schedulerApi.ts
    ├── types/scheduler.ts
    ├── app/App.tsx
    └── features/
        ├── girderPlanning/
        │   ├── GirderPlanningPanel.tsx
        │   ├── RouteEditor.tsx
        │   ├── YardMachineEditor.tsx
        │   ├── GirderResultPanel.tsx
        │   ├── GirderDiagnostics.tsx
        │   └── adapter.ts
        └── planControl/PlanControlPanel.tsx
```

**结构决策**：架梁领域包只处理确定性业务规则，不直接调用 CP-SAT；`girder_schedule_adapter.py` 负责将派生结果转换为现有 `Task`、`PrecedenceLink`、资源需求和时间窗；`integrated_schedule.py` 是唯一循环编排入口；`solver.py` 不理解路线和库存。前端原生接入现有 `App` 状态与 `schedulerApi.ts`，不复制原应用根组件或保留浏览器正式算法。

## Phase 0：研究结论

研究结论见 [research.md](./research.md)。所有技术未知项已收敛，没有遗留 `NEEDS CLARIFICATION`。

## Phase 1：设计与契约

- 数据实体、关系、校验和状态迁移见 [data-model.md](./data-model.md)。
- 新增和扩展接口见 [girder-scheduling-api.yaml](./contracts/girder-scheduling-api.yaml)。
- 端到端验证与黄金样例运行方式见 [quickstart.md](./quickstart.md)。
- 当前 Spec Kit 集成未提供 `update-agent-context.ps1`，因此没有自动修改 `AGENTS.md` 或 agent 上下文；本计划遵循现有 `AGENTS.md`、`agent.md` 和 Constitution，且不需要人工改写这些治理文件。

## 兼容与迁移策略

1. `ScenarioInput.girder_planning` 为可选；未启用专项的旧场景保持现有任务和求解行为。
2. 计划管控存储新增字段均提供空列表或可空默认值；读取 `plan-control/v1` 时完成内存升级，首次写入后保存为新版本。
3. 旧架梁输入经规范化和人工确认后保存为统一项目/方案版本；旧计算结果只用于黄金对照，不进入正式计划版本。
4. 原 TypeScript 算法和测试不复制为第二套生产逻辑；迁移期将固定输入与期望输出转存到本仓库测试夹具。
5. 新规则与旧结果不一致时按 `spec.md` 验收，并在黄金样例元数据中标记 `legacy_parity` 或 `confirmed_rule_change`。
6. 影子验证通过且取得外部仓库操作授权后，将旧项目切换为只读归档并记录入口关闭和归档状态；在授权前不得自动修改外部仓库。

## 复杂度跟踪

无 Constitution 违反项。新增领域包、编排服务和版本实体均直接对应已确认的独立业务职责；未引入新基础设施或第三方依赖。

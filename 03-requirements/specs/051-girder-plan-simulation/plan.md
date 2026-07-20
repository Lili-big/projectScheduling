# 实施计划：架梁计划推演

**分支/目录**：`051-girder-plan-simulation` | **日期**：2026-07-19 | **规格**：[spec.md](./spec.md)

**输入**：来自当前 `SPECIFY_FEATURE_DIRECTORY/spec.md` 的功能规格

## 概要

在不修改现有“架梁专项策划”业务行为的前提下，新增独立“架梁计划推演”页面和后端领域边界。新能力直接引用已确认项目主数据快照，以线路、里程和人工连接确认形成线路图；每个梁场维护分梁型片日产能、库存和单条人工排序架梁线路；后端使用确定性逐日事件仿真生成固定顺序下的最早可行架梁日期，并倒排路桥隧工点最晚交付日期。方案和计算快照使用独立本地状态仓储，不写回 `GirderPlanningConfig`、综合联算或计划版本。

## 技术上下文

**语言/版本**：Python 3.14 当前本地运行时；TypeScript 5.7；React 19；Node.js 24 当前本地运行时

**主要依赖**：FastAPI、Pydantic、React、Vite；复用标准库日期/图遍历能力和现有稳定指纹工具，不新增求解器或前端图形依赖

**存储**：已确认项目主数据继续由现有 SQLite 仓储提供；新增策划方案与计算快照保存到 `.local-data/state/girder-plan-simulation-store.json`，通过 `state_path()` 保持生命周期分区和旧路径兼容

**测试**：pytest 后端领域/API/持久化/性能测试；Node `node:test` 前端契约、交互和边界测试；TypeScript typecheck、Vite build、架构基线和仓库验证器

**目标平台**：本地 FastAPI 单服务＋Vite/React Web 页面；演示 API 镜像保持契约同步但不替代 FastAPI 权威实现

**项目类型**：跨前后端 Web 功能，包含共享契约、独立领域服务、持久化、页面和可复现算法

**性能目标**：500 个线路工点、10 个梁场、300 个待架桥梁幅别在本地标准演示环境中 10 秒内返回成功或阻断终态

**约束**：现有架梁专项页面、API、`GirderPlanningConfig`、联合计算和发布门禁行为不变；人工顺序为硬约束；单位统一为片、片/天和自然日；当日产梁下一自然日可用；不得把排程可行写成工程技术可行

**规模/范围**：新增一个后端领域包、一个 API router、一个独立状态仓储、一组共享后端/前端契约、一个前端 feature 页面和定向测试；调整应用路由注册、导航、工作区组合、演示 API 镜像和架构基线消费者

## 生命周期归属

- **规格归属引用**：[`spec.md#生命周期归属`](./spec.md#生命周期归属)
- **实施路径**：`04-demo/backend/app/contracts/girder_plan_simulation.py`、`04-demo/backend/app/girder_plan_simulation/`、`04-demo/backend/app/api/routers/girder_plan_simulation.py`、`04-demo/backend/tests/test_girder_plan_simulation_*.py`、`04-demo/frontend/src/contracts/girderPlanSimulation.ts`、`04-demo/frontend/src/api/girderPlanSimulationApi.ts`、`04-demo/frontend/src/features/girderPlanSimulation/`、相关工作区/导航/镜像/契约测试

## Constitution 检查

*门禁：Phase 0 研究前与 Phase 1 设计后均已检查。*

- **可验收需求：通过。** `spec.md` 已记录业务目标、用户、来源、默认假设、27 条功能需求和 10 条成功标准。
- **显式算法规则：通过。** 输入、输出、数量单位、日界口径、硬约束、最早可行目标、冲突和固定样例均已明确；控制日期和风险只作为结果与诊断。
- **显式共享契约：通过。** 计划通过独立 OpenAPI、后端 Pydantic、前端类型、演示镜像和契约测试保持一致，并定义草稿、可计算、已计算、已确认、失效、阻断及 HTTP 失败状态。
- **保留行为与最小设计：通过。** 复用项目主数据快照、指纹、`state_path()` 和现有应用组合；不修改现有专项模型和服务，不新增外部依赖。
- **分阶段可验证价值：通过。** 先建立线路与能力，再完成固定顺序仿真，再输出交付控制，最后增加独立版本确认。
- **验证与完成证据：通过。** 计划包含固定输入/期望输出、库存不变量、循环依赖、失效、前端旅程、性能和现有专项兼容回归。
- **资产与数据安全：通过。** 规格归属唯一；新持久状态进入 `.local-data/state/`，不会作为缓存或临时文件清理；不包含客户原始材料或凭据。
- **资产迁移：不适用。** 本功能不移动或删除现有资产。

Phase 1 设计后复核结论：没有新增违反项；独立仓储和 API 命名避免将新策划结果混入现有专项及计划发布生命周期。

## 项目结构

### 本功能文档

```text
03-requirements/specs/051-girder-plan-simulation/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── girder-plan-simulation.openapi.yaml
└── tasks.md
```

### 生命周期与源码结构（仓库根目录）

```text
04-demo/backend/app/
├── contracts/
│   └── girder_plan_simulation.py
├── girder_plan_simulation/
│   ├── __init__.py
│   ├── topology.py
│   ├── validation.py
│   ├── simulator.py
│   ├── repository.py
│   └── service.py
├── api/routers/girder_plan_simulation.py
└── bootstrap.py

04-demo/backend/tests/
├── fixtures/girder_plan_simulation/
├── test_girder_plan_simulation_topology.py
├── test_girder_plan_simulation_validation.py
├── test_girder_plan_simulation_simulator.py
├── test_girder_plan_simulation_repository.py
├── test_girder_plan_simulation_api.py
└── test_girder_plan_simulation_performance.py

04-demo/frontend/src/
├── contracts/girderPlanSimulation.ts
├── api/girderPlanSimulationApi.ts
├── features/girderPlanSimulation/
│   ├── GirderPlanSimulationPanel.tsx
│   ├── LineGraphView.tsx
│   ├── YardPlanEditor.tsx
│   ├── RouteSequenceEditor.tsx
│   ├── SimulationResultPanel.tsx
│   ├── adapter.ts
│   ├── styles.css
│   └── index.ts
├── features/layout/WorkspaceNavigation.tsx
├── app/Workspace.tsx
└── contracts/scheduler.ts

04-demo/frontend/tests/
├── girderPlanSimulation.test.mjs
└── featureBoundaries.test.mjs

04-demo/tools/demo-api-mirror/
├── api.mts
└── verify.mjs
```

**结构决策**：后端新能力作为 `girder_plan_simulation` 独立领域包，直接读取项目主数据服务并拥有独立仓储；只复用现有 `girder_planning.fingerprints` 的稳定指纹工具，不调用现有专项计算或计划发布服务。前端使用独立 feature、API client、样式和契约，通过 `Workspace.tsx` 与导航增加入口；现有 `features/girderPlanning/` 不修改。新契约放入独立领域文件而非继续扩大 `_models.py`，并由公共 contracts 入口显式重导出。

## Phase 0：研究结论

详见 [research.md](./research.md)。没有未解决的实现阻塞项；关键决策为：

1. 线路图以项目主数据 `alignment_code + start/end mileage + sort_order` 形成每条主走廊的相邻图，缺失、重叠冲突、断点和多义连接由方案级人工连接确认补充。
2. 待架目标来自确认快照中的桥梁上部结构，按“桥梁＋幅别”聚合梁型和梁片数量；缺少幅别、梁型或片数时阻断正式片级计算。
3. 使用确定性逐日事件仿真而非 CP-SAT；固定顺序、库存、片日能力和跨线路依赖可以直接求最早可行日，循环依赖通过图检测解释。
4. 独立 JSON 仓储保留方案版本和只读快照，避免扩展现有 plan-control store 及其失效链。

## Phase 1：设计产物

- [data-model.md](./data-model.md)：定义线路图、方案、分梁型产能、单线顺序、逐日台账、架梁日期、工点控制、诊断、版本和状态转换。
- [contracts/girder-plan-simulation.openapi.yaml](./contracts/girder-plan-simulation.openapi.yaml)：定义线路图、方案版本、校验、计算、查询和独立确认 API。
- [quickstart.md](./quickstart.md)：提供双梁场、混合梁型、共享通道、库存不足、循环依赖、失效和兼容验证旅程。
- `.specify/scripts/powershell/` 当前没有 agent-context 更新脚本，因此本计划不虚构或手工替代该步骤；根 `AGENTS.md` 保持不变。

## 复杂度跟踪

无 Constitution 违反项，不需要复杂度豁免。

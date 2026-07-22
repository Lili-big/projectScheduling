# 实施计划：统一固定资源与最少资源求解

**分支/目录**：`056-unified-fixed-resource-solve` | **日期**：2026-07-20 | **规格**：[spec.md](./spec.md)

**输入**：来自当前 `03-requirements/specs/056-unified-fixed-resource-solve/spec.md` 的功能规格

## 概要

把模拟固定资源求工期、AI 资源方案求工期和最少资源候选详细排程收敛到同一个 solver 单阶段内核，并让 simulation/AI 共用 application 包装：严格展开本次输入资源，只调用一次 `solve_control_priority_schedule_once`，按“最大目标延期最小、同等延期下总工期最短”求解，资源空闲与连续性仅从结果派生诊断。固定工期求资源则保留一次全局联合数量优化，以 `0..max_quantity` 搜索资源总数最少、同数下总工期更短的候选；候选只进入一次上述固定资源内核，详细排程无论是否满足目标都不增加资源、不回退、不重试。现有 API、范围隔离和响应外壳保持兼容，前端把算法倾向改为准确的只读目标说明。

## 技术上下文

**语言/版本**：Python 3.12；TypeScript 5.7；Node.js 22

**主要依赖**：FastAPI、Pydantic、OR-Tools CP-SAT、React 19、Vite 6

**存储**：不新增存储；只改变新请求的求解调用链和结果元数据，不迁移或重写历史求解结果

**测试**：pytest；Node `node:test`；TypeScript 类型检查；Vite 生产构建；OpenAPI/架构兼容与仓库文档校验

**目标平台**：本地/容器 FastAPI 排程服务、React 模拟求解页面、Demo API 镜像

**项目类型**：前后端 Web 应用与 CP-SAT 排程服务的跨层算法收敛

**性能目标**：固定资源每请求恰好 1 次排程调用；固定工期每请求最多 1 次全局数量搜索和 1 次详细排程；不再产生预检、二分、并行复排或增配调用

**约束**：固定资源数量不得静默补足；最少资源下限为 0；不改变现有施工硬约束、资源作用域、任务生成与里程碑匹配；不改变资源成本优化、LLM 方案生成、项目主数据和架梁专项；接口路径和共享响应结构兼容

**规模/范围**：后端 scheduling application/solver、AI 方案包装、共享契约元数据、模拟求解页面目标展示、Demo API 镜像及定向测试；无依赖和数据库变更

## 生命周期归属

- **规格归属引用**：[`spec.md#生命周期归属`](./spec.md#生命周期归属必填)
- **实施路径**：`04-demo/backend/app/scheduling/application/_scenario.py`、`04-demo/backend/app/scheduling/solver/engine.py`、`04-demo/backend/app/services/ai_resource_scheduling_assistant.py`、`04-demo/frontend/src/app/Workspace.tsx`、`04-demo/frontend/src/contracts/scheduler.ts`、`04-demo/tools/demo-api-mirror/api.mts` 及相邻定向测试

## Constitution 检查

*门禁：Phase 0 研究前与 Phase 1 设计后均已检查。*

- [x] 用户已确认统一目标、详细排程失败不增配重试和全局搜索下限为 0。
- [x] `spec.md` 已引用现有 AI 单阶段、模拟多阶段、最少资源回退和单工点范围代码事实。
- [x] 固定资源与最少资源的输入、输出、硬约束、目标顺序、状态矩阵、调用次数和边界场景均可测试。
- [x] 共享契约保持现有 API 路径和响应外壳，只规范已有 `stats`/`objective_breakdown` 元数据与历史兼容语义。
- [x] 不把资源空闲、连续性、Demo 时间预算或当前资源数量提升为新的业务目标或硬规则。
- [x] 复用现有 CP-SAT 求解器、Scenario 生成、资源池身份、范围和诊断，不引入第二套排程模型或无关抽象。
- [x] 规格唯一归属为 `03-requirements/specs/056-unified-fixed-resource-solve/`，实现只引用该规格。
- [x] 不迁移、不删除、不重写本地状态、用户输入或历史成果。
- [x] 设计后复核无 Constitution 违反项，无需复杂度豁免。

## Phase 0：研究结论

研究决策见 [research.md](./research.md)。所有阻塞性未知项已解决：统一共享 solver 一阶段内核，而不是让模拟入口依赖 AI service 或让 solver 反向依赖 application；simulation/AI 再共用 application 结果包装；保留一次 CP-SAT 全局数量搜索；详细排程复用固定资源内核；结果采用四态业务状态与原始 solver 状态并存；旧阶段字段保留但对新结果标记未执行或不适用。

## Phase 1：设计

### 1. 权威固定资源内核

1. 在 `04-demo/backend/app/scheduling/solver/engine.py` 以现有 `solve_control_priority_schedule_once` 为基础建立权威固定资源单阶段函数。它只接受 `ScheduleInput` 和可选固定工期目标，完成一次 CP-SAT 调用、统一目标元数据与四态判定；不得生成资源或依赖 Scenario、AI service、页面范围。
2. 在 `04-demo/backend/app/scheduling/application/_scenario.py` 建立接收 `GeneratedScheduleInput` 的共享 application 包装，统一预算、来源、范围诊断和 `ScenarioSolveResult` 组装；simulation 与 AI 入口都调用该包装，AI service 只补充方案快照与推荐门禁。
3. 模拟 `solve_scenario` 移除当前 `_solve_fixed_resources_shortest_scenario` 对基础/完整排程、最少资源搜索、资源压力搜索和 `alternative_results` 方案 2 的运行依赖。响应仍返回 `alternative_results=[]` 以保持结构兼容。
4. 最少资源候选详细排程直接调用同一 solver 一阶段函数，不反向依赖 application；application 只负责把该结果包装为场景响应。
5. 共享内核固定启用控制目标主阶段语义：最大目标延期优先，总工期其次。`resource_idle`、连续性和负载均衡不建模为该内核的优化目标；现有结果诊断计算继续保留。

### 2. 四态与结果来源

1. 业务状态统一为 `met | not_met | unconfirmed | infeasible`，写入现有 `target_achievement.target_status`，同时保留 `ScheduleResult.status` 原始求解器状态。
2. 有目标时：`OPTIMAL/FEASIBLE + 零延期` 为 `met`；`OPTIMAL + 延期` 为 `not_met`；`FEASIBLE + 延期` 为 `unconfirmed`；`UNKNOWN` 为 `unconfirmed`；资源覆盖失败、`MODEL_INVALID` 或已证明无解为 `infeasible`。无可评估目标且已有排程时为 `unconfirmed`。
3. 目标偏差统一记录强制里程碑延期、固定工期超期和两者最大值。存在可用排程时，无论业务状态是否满足都保留任务、资源分配、里程碑和诊断。
4. 新结果用稳定来源值区分 `unified_fixed_resources`、`global_minimum_resource_search` 和 `minimum_resources_fixed_detail`；取消的基础阶段、二阶段、增配和回退字段标记 `not_run`/`not_applicable`，不删除旧字段读取兼容。

### 3. 固定工期全局最少资源

1. `solve_min_resources_schedule` 保留资源覆盖与目标存在性校验，然后恰好调用一次 `_solve_capacity_model(..., minimize_resource_count=True)`。每个有效池的默认下限为 0，上限为 `max_quantity`；调用方只有显式业务下限时才传 `minimum_resource_counts`，模拟固定工期入口不得从当前 `quantity` 派生下限。
2. 全局模型以资源数量总和为第一目标，以在同一最小数量下总工期更短为第二目标；保持资源池 ID、兼容类型、授权范围、容量、工艺和目标工期硬约束。
3. 全局模型返回 `UNKNOWN`、`INFEASIBLE` 或 `MODEL_INVALID` 时直接形成对应业务结果，不再运行最大资源独立预检、独占容量剪枝结论、逐池二分、压力搜索或候选排程。
4. 全局模型返回候选时，按候选数量从原有稳定资源池生成命名资源输入，并调用共享固定资源内核恰好一次。容量模型排程只作为搜索证据/热启动数据（若无需新增 solver 调用），不得代替详细排程结论。
5. 详细业务状态仅为 `met` 时设置 `candidate_verified=true`；其他状态保留候选数量及真实详细排程，不改变候选、不提高下限、不再搜索或复排。

### 4. 目标来源、范围与兼容

1. 固定工期优先使用当前求解范围内可匹配强制里程碑；没有匹配目标时才接受前端提供的、与 `scenario + solve_scope` 指纹一致的固定资源结果工期。
2. `ALL` 与 `WORKPOINT` 继续复用 054 已建立的生成、资源裁剪、指纹、保存和比较隔离。共享内核只接收范围化后的输入，不自行跨范围查找资源或目标。
3. `POST /api/solve-scenario`、`POST /api/solve-min-resources`、`POST /api/ai-resource-assistant/solve-plan` 的路径、请求主体和顶层响应模型不变。新增/规范的元数据位于现有扩展字典中，旧客户端可忽略。
4. Demo API 镜像同步接受相同请求和返回相同状态/来源字段；若镜像不运行 CP-SAT，其 fixture/模拟结果也不得表达已取消的回退或增配行为。

### 5. 前端交互与展示

1. 模拟求解页不再允许用户把资源空闲或连续性配置为本功能两种求解的优化目标。将“算法倾向选择/权重”改为只读目标说明：优先减少最大目标延期，其次缩短总工期；资源组织指标注明为求解后诊断。
2. 固定资源结果显示业务四态、原始 solver 状态、最大目标延期、总工期、调用次数和“未自动增配”。固定工期结果额外分开展示全局候选资源、详细排程状态及 `candidate_verified`。
3. 历史结果若仍含旧目标贡献、方案 2 或回退来源，继续按原始来源展示并标识历史结果；不得重写为统一新算法结果。

### 6. 测试与验收策略

1. 后端 application 测试通过 monkeypatch/spy 精确断言固定资源 1 次 solver 调用、最少资源 1 次全局搜索 + 1 次详细调用、两个入口调用同一内核以及所有禁用分支 0 次。
2. solver 定向测试覆盖全局目标词典序、默认下限 0、同数量下总工期裁决、稳定池身份、数量 0 和无合法候选。
3. 状态矩阵测试覆盖 `OPTIMAL/FEASIBLE/UNKNOWN/INFEASIBLE/MODEL_INVALID`、目标存在/缺失、延期/不延期及详细候选验证门禁。
4. 范围、API、AI 推荐、前端展示、历史兼容和 Demo 镜像使用现有测试文件增量验证；最后只运行一次与风险匹配的组合门禁。

### 设计产物

- 数据模型：[data-model.md](./data-model.md)
- API/元数据契约：[contracts/unified-fixed-resource-solve.openapi.yaml](./contracts/unified-fixed-resource-solve.openapi.yaml)
- 实施验证步骤：[quickstart.md](./quickstart.md)

## 项目结构

### 本功能文档

```text
03-requirements/specs/056-unified-fixed-resource-solve/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── unified-fixed-resource-solve.openapi.yaml
└── tasks.md
```

### 生命周期与源码结构（仓库根目录）

```text
04-demo/backend/app/
├── api/routers/
│   ├── assistants.py
│   └── scheduling.py
├── contracts/_models.py
├── scheduling/
│   ├── application/_scenario.py
│   └── solver/engine.py
└── services/ai_resource_scheduling_assistant.py

04-demo/backend/tests/
├── scheduling/
│   ├── test_fixed_resource_application.py
│   ├── test_resource_search_application.py
│   ├── test_single_workpoint_solve.py
│   └── test_solver_objectives.py
├── test_ai_resource_scheduling_assistant.py
├── test_scheduler.py
└── test_scheduling_routes.py

04-demo/frontend/src/
├── app/Workspace.tsx
├── contracts/scheduler.ts
└── features/scheduleResults/

04-demo/frontend/tests/
├── apiCompatibility.test.mjs
├── contractsCompatibility.test.mjs
├── scheduleResults.test.mjs
├── singleWorkpointSolve.test.mjs
└── workspaceController.test.mjs

04-demo/tools/demo-api-mirror/api.mts
```

**结构决策**：共享算法属于现有 scheduling solver，simulation/AI 的共同场景包装属于 scheduling application，不放入 AI service 或新业务模块；CP-SAT 固定资源目标和数量模型继续同层复用且不反向依赖 application；状态与来源复用现有可扩展结果字典；前端在既有模拟求解页和结果 feature 内收敛展示。实现不新增业务目录、不复制求解器、不迁移顶层契约。

## 复杂度跟踪

无 Constitution 违反项。

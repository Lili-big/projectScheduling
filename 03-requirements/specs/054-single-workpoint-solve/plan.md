# 实施计划：单工点模拟求解

**分支/目录**：`054-single-workpoint-solve` | **日期**：2026-07-20 | **规格**：[spec.md](./spec.md)

**输入**：来自当前 `03-requirements/specs/054-single-workpoint-solve/spec.md` 的功能规格

## 概要

在不改变 `ScenarioInput` 持久化语义和现有 CP-SAT 约束/目标的前提下，为任务生成和三类场景求解端点增加可选的单工点请求范围。后端先物化完整项目并解析完整资源作用域，再只生成所选桥梁工点的任务、工点内关系、合法资源和匹配里程碑；响应携带类型化范围元数据。前端复用已加载的桥梁工点列表提供下拉选择，把范围纳入请求指纹、结果失效和固定工期基准判断，并阻止单工点结果保存为全项目方案或与全项目结果混合比较。Netlify 演示镜像同步相同契约和裁剪语义。

## 技术上下文

**语言/版本**：Python 3.12；TypeScript 5.7；Node.js 22

**主要依赖**：FastAPI、Pydantic、React 19、OR-Tools CP-SAT、Vite 6

**存储**：不新增存储；求解范围是请求级临时上下文，不写入 `ScenarioInput`、项目主数据或 `.local-data`

**测试**：pytest；Node `node:test`；TypeScript 类型检查；Vite 构建；OpenAPI/架构基线与仓库文档校验

**目标平台**：本地/容器 FastAPI 服务、React 前端、Netlify 演示 API 镜像

**项目类型**：前后端 Web 应用与 CP-SAT 排程服务的跨层增量功能

**性能目标**：当前参考项目最大单工点任务量相对全项目减少至少 80%；合法资源条件和 3 秒求解预算下端到端 8 秒内返回完整 `FEASIBLE` 或 `OPTIMAL` 结果

**约束**：不改变硬约束、软目标、权重、资源数量语义和转场语义；不按资源类型合并同类型池；数量为 0 或无合法候选继续阻断；旧请求缺少范围时保持全项目行为；单工点结果不得进入全项目保存和混合比较

**规模/范围**：4 个现有排程端点、后端共享契约/生成/求解/比较、前端请求/工作流/模拟求解页/结果展示、Netlify 镜像及定向测试；无数据库迁移

## 生命周期归属

- **规格归属引用**：[`spec.md#生命周期归属`](./spec.md#生命周期归属必填)
- **实施路径**：`04-demo/backend/app/contracts/`、`04-demo/backend/app/api/routers/scheduling.py`、`04-demo/backend/app/scheduling/`、`04-demo/backend/tests/`、`04-demo/frontend/src/`、`04-demo/frontend/tests/`、`04-demo/tools/demo-api-mirror/api.mts`

## Constitution 检查

*门禁：Phase 0 研究前与 Phase 1 设计后均已检查。*

- [x] 用户已确认可行性结论、三类求解共用范围、全项目兼容和结果隔离边界。
- [x] `spec.md` 已引用用户请求、当前代码事实、运行验证和既有工点资源规格。
- [x] 输入、输出、硬约束、软目标、默认范围、资源冲突、里程碑和无解处理均已显式定义。
- [x] API 查询字段、响应范围元数据、加载/空态/失败态、指纹失效和旧请求兼容已纳入设计。
- [x] 单工点范围只是求解输入裁剪，不作为新优化目标，不把验证数据或 Demo 默认值提升为产品规则。
- [x] 复用现有 `ScenarioInput`、项目主数据物化、资源作用域、生成、求解、结果和工点列表；只为跨生成/求解共享的里程碑匹配抽取一个领域函数。
- [x] 规格唯一归属为 `03-requirements/specs/054-single-workpoint-solve/`，实施只建立引用。
- [x] 不迁移、不删除、不重写本地状态、用户输入或正式成果。
- [x] 设计后复核无 Constitution 违反项，无需复杂度豁免。

## Phase 0：研究结论

研究决策见 [research.md](./research.md)。所有阻塞性未知项已解决：采用可选查询参数承载临时范围；以 `GeneratedScheduleInput.solve_scope` 作为响应范围权威；完整项目解析资源、选中工点生成任务；复用同一个里程碑匹配规则；前后端共同阻止跨范围比较。

## Phase 1：设计

### 请求与范围解析

1. `POST /api/generate-schedule-input`、`/api/solve-scenario`、`/api/solve-min-resources`、`/api/solve-resource-cost` 增加可选查询参数 `workpoint_id`；缺省为全项目。
2. Router 保持“先项目主数据物化、后范围校验”的顺序。单工点 ID 必须对应物化项目中的桥梁工点；非法 ID 返回 422，不回退全项目。
3. 应用层公共生成和三类求解函数接收同一个可选范围参数，所有最大资源、回退、备选方案和资源搜索生成调用必须继续传递该范围。

### 范围化生成

1. `_build_tasks` 只遍历所选桥梁；资源有效值解析仍读取完整 `scenario.project.bridges`，以保留共享池授权、稳定池 ID 和其他工点配置的原始语义。
2. 资源覆盖校验仅针对选中任务执行；展开资源只保留其授权范围包含所选工点的有效池，但不改写池 ID、授权集合或共享/独享模式。
3. 工艺逻辑和生成链接只在选中任务集合内建立。现有里程碑任务匹配函数从 solver 私有实现提取到 `scheduling/domain/milestone_scope.py`，生成与求解共用；单工点 `ScheduleInput` 只携带能匹配所选任务的里程碑。
4. 无任务时继续形成生成层阻断诊断，不调用求解器。无合法资源继续使用 `RESOURCE_ALLOCATION_NO_LEGAL_CANDIDATE`。

### 共享契约与结果安全

1. 新增非持久化 `SolveScope`：`mode=ALL|WORKPOINT`、可空 `workpoint_id`、可空 `workpoint_name`。`WORKPOINT` 必须同时具有 ID 和名称；`ALL` 两者为空。
2. `GeneratedScheduleInput.solve_scope` 是请求、主结果和备选结果的范围权威；前端和镜像同步类型。`source_summary` 可保留统计字段，但不得成为第二个范围权威。
3. `compare_scenarios` 只接受全部为 `ALL` 的结果；任何 `WORKPOINT` 结果或混合范围请求均返回明确错误。前端在按钮层提前阻止，后端作为契约兜底。

### 前端状态与交互

1. `Workspace` 保存请求级 `selectedSolveWorkpointId`，空字符串代表全项目；复用 `currentResourceWorkpoints` 生成“全部工点 + 桥梁工点”下拉选项。
2. `generateScheduleInput` 和三类 solve API 均追加同一个查询参数。求解指纹改为 `scenario + solve scope`，固定工期基准只在范围化指纹相等时复用。
3. 切换范围时清理生成输入、当前求解结果和比较状态；求解忙碌时禁用下拉。请求返回后以发起时指纹校验，丢弃迟到响应。
4. 结果页显示“全部工点”或“单工点试算：名称（ID）”。单工点结果的保存按钮禁用并显示原因；全项目保存和比较行为保持。

### 契约、模型与验证

- 数据模型见 [data-model.md](./data-model.md)。
- API 增量契约见 [contracts/single-workpoint-solve.openapi.yaml](./contracts/single-workpoint-solve.openapi.yaml)。
- 端到端验证步骤见 [quickstart.md](./quickstart.md)。

## 项目结构

### 本功能文档

```text
03-requirements/specs/054-single-workpoint-solve/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── single-workpoint-solve.openapi.yaml
└── tasks.md
```

### 生命周期与源码结构（仓库根目录）

```text
04-demo/backend/app/
├── api/routers/scheduling.py
├── contracts/_models.py
├── contracts/scheduling.py
└── scheduling/
    ├── application/_scenario.py
    ├── domain/milestone_scope.py
    └── solver/engine.py

04-demo/backend/tests/
├── test_scheduling_routes.py
└── scheduling/test_single_workpoint_solve.py

04-demo/frontend/src/
├── api/_schedulerApi.ts
├── app/Workspace.tsx
├── app/workflows/scenarioWorkflow.ts
├── app/workflows/solveWorkflow.ts
├── contracts/scheduler.ts
└── features/scheduleResults/presenter.ts

04-demo/frontend/tests/
├── singleWorkpointSolve.test.mjs
├── scheduleResultsPresenter.test.mjs
└── workspaceController.test.mjs

04-demo/tools/demo-api-mirror/api.mts
```

**结构决策**：范围字段属于请求/结果共享契约，定义在现有 scheduling contract；任务裁剪和范围传递属于 scheduling application；里程碑匹配是生成与 solver 共用的领域规则；UI 继续由 `Workspace` 组合现有结果 feature。除一个共享里程碑匹配模块和定向测试外不新增业务目录或第二套求解模型。

## 复杂度跟踪

无 Constitution 违反项。

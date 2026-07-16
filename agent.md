# 项目 Agent 工作手册

`AGENTS.md` 决定需求评审、文档、实现和 Spec Kit 的工作流；本文件只维护项目事实、模块所有权、调用链、兼容边界和修改/验证矩阵。开始任务时先读 `AGENTS.md`，再读本文件和目标领域文档。

## 1. 项目事实

本项目是 `FastAPI + React + OR-Tools CP-SAT` 的桥梁施工排程模块化单体 Demo。前端维护 `ScenarioInput`，后端生成任务图和 `ScheduleInput`，求解器返回 `ScheduleResult`/`ScenarioSolveResult`，前端展示任务、甘特、资源、里程碑、目标拆解、诊断和方案比较。

```text
ScenarioInput
  -> GeneratedScheduleInput / ScheduleInput
  -> ScheduleResult / ScenarioSolveResult
```

当前扩展能力包括：

- 桥梁结构参数 Excel 导入和本体映射。
- 固定资源最短工期、固定工期最少资源、资源成本优化。
- AI 参数输入助手和自然语言工艺设置。
- AI 资源方案生成、求解、比较和推荐。
- 架梁项目/方案版本、专项导入、校验、预览和综合排程。
- 计划基线、进度快照、预测、调整和采纳。

边界：`041-girder-scheduling-integration` 仍为 74/95，统一发布、完整实绩滚动和影子验证等 21 项未完成；不得写成现状。生产权限、审计、租户/项目隔离、正式数据接入也未形成产品级实现。

## 2. 取证顺序

1. 用户当前要求和明确约束。
2. `AGENTS.md` 工作流门禁。
3. `README.md`、本文件、[文档索引](./docs/README.md) 和相关 current 文档。
4. [模块地图](./docs/architecture/module-map.md)、源码、测试、配置和运行结果。
5. [规格索引](./specs/README.md) 与目标 `spec.md`/`plan.md`/`tasks.md`。

解释当前实现时，代码和测试优先；评审/PRD 同时列出文档口径、代码事实和用户新要求。无法判断目标口径时，列出冲突并请求决策，不自行编造业务规则。

## 3. 当前模块所有权

042 已把主要全局热点收敛为兼容 façade。旧入口继续可用，新业务必须进入拥有该领域的模块。

### 后端

| 能力 | 当前入口/所有权 | 验证 |
| --- | --- | --- |
| FastAPI 启动、CORS、静态和 SPA | `bootstrap.py`、`api/routers/`；`main.py` 为兼容入口 | API 契约、真实 HTTP、单服务冒烟 |
| 共享请求/响应契约 | `contracts/`；`models.py` 完整重导出 | schema/dump 与旧导入兼容测试 |
| 场景、任务生成、资源搜索、比较 | `scheduling/generation/`、`scheduling/application/`；`scenario.py` 兼容 | `test_scheduler.py`、行为基线 |
| CP-SAT 约束、目标、策略、结果 | `scheduling/solver/`；`solver.py` 兼容 | 求解器回归、固定等价、性能 |
| 桥梁导入 | `importing/bridge.py`；旧 bridge/service 兼容 | `test_bridge_import.py` |
| AI 参数助手 | `assistants/parameter/`；旧 service 兼容 | `test_ai_parameter_*` |
| AI 资源助手 | `assistants/resource/`；旧 service 兼容 | `test_ai_resource_scheduling_assistant.py` |
| 架梁专项 | `girder_planning/` application/adapter | `test_girder_*`、`test_integrated_schedule.py` |
| 计划管控 | `plan_control/`；旧 services 兼容 | `test_plan_control_*`、`test_progress_forecast.py` |
| 本地/发布配置 | `config/`、`default_scenario_config.json`；旧配置模块兼容 | 配置与存储契约测试 |

### 前端

| 能力 | 当前入口/所有权 | 验证 |
| --- | --- | --- |
| 应用装配和跨 feature 状态 | `app/App.tsx`、`Workspace.tsx`、`app/workflows/`、`useWorkspaceController.ts` | Node 工作流、类型检查、构建 |
| 共享类型 | `contracts/`；`types/scheduler.ts` 完整重导出 | contracts 兼容测试 |
| API | `api/*Api.ts`；`schedulerApi.ts` 保留 40 个函数重导出 | API 兼容测试 |
| 工艺/逻辑/资源/里程碑 | 对应 `features/` 目录和 `domain/` 纯函数 | 构建、领域测试、页面冒烟 |
| AI 助手 | `features/assistant`、`features/resourceAssistant` | Node 测试、页面流程 |
| 架梁/计划管控 | `features/girderPlanning`、`features/planControl` | 对应 Node 测试和后端契约 |
| 任务与结果 | `features/taskView`、`features/scheduleResults`；`Workspace.tsx` 负责组合 | presenter/纯函数测试 |
| 样式 | `styles/tokens.css`、`base.css`、`layout.css` 与 feature CSS；`styles.css` 聚合 | 构建、视觉对比 |

### 仓库资产

| 资产 | 当前所有权 | 验证 |
| --- | --- | --- |
| 产品/算法/验证/调研文档 | `docs/product`、`engineering`、`validation`、`research` | 文档索引与链接门禁 |
| 可复现样例 | `examples/bridge-import`、`examples/result-viewer` | 导入测试、Docker 契约 |
| PPT 与参考 API | `tools/ai-ppt-system`、`tools/demo-api-mirror` | 各工具 `verify` |
| 交付物构建与正式文件 | `tools/delivery-builders`、`deliverables` | 固定构建、导入复核、二进制哈希 |
| 预览/检查中间件 | `artifacts` | 默认忽略，不作为正式交付物 |
| 本地数据和日志 | `.local-data` | Git 卫生、日志落点门禁 |

更完整的所有权和依赖方向见 [模块地图](./docs/architecture/module-map.md) 与 [依赖规则](./docs/architecture/dependency-rules.md)。

## 4. 关键调用链

### 综合排程

```text
GET /api/demo-scenario
  -> default_scenario + 发布默认 + 本地覆盖
POST /api/generate-schedule-input
  -> 结构/工艺/逻辑/资源派生任务图
POST /api/solve-scenario | solve-min-resources | solve-resource-cost
  -> scenario application -> CP-SAT solver
POST /api/compare-scenarios
  -> 统一比较摘要
```

### AI 参数助手

```text
资料/文本 -> POST /api/ai-parameter-assistant/parse
  -> 候选建议 + 证据 + 冲突（不修改场景）
人工选择 -> POST /api/ai-parameter-assistant/apply
  -> 更新 ScenarioInput -> 任务/求解/比较失效
```

### AI 资源助手

```text
ScenarioInput -> initialize -> 三套资源计划
  -> update-plan / solve-plan 或 batch-solve
  -> compare-results -> generate-recommendation
```

资源推荐与最终排程是两个边界：LLM 可生成/解释候选资源，后端确定性校验和 CP-SAT 求解决定排程结果。外部模型失败时保留本地策略。

### 架梁专项与综合排程

```text
项目数据版本 -> 确认
方案版本 -> 架梁导入/配置 -> 校验 -> 专项确认
  -> preview 或 integrated-schedules
```

只有当前实现和测试覆盖的流程可称为已实现；统一发布、完整实绩滚动和影子验证仍属于 041 未完成项。

### 计划管控

```text
基线计划 -> 进度快照 -> 预测 -> 调整建议 -> 采纳新版本
```

仓储位于 `.local-data/plan-control-store.json`，具有版本冲突和稳定指纹语义，但仍是单机演示存储。

## 5. 契约与兼容边界

- FastAPI 保持 45 个 `/api` 路由、方法、schema、状态码和错误 `detail`。
- `uvicorn app.main:app --app-dir backend` 和 `app.main:app` 保持有效。
- `backend/app/main.py`、`backend/app/models.py`、`backend/app/scenario.py`、`backend/app/solver.py` 是受测试保护的短兼容入口；`app.models`、`app.scenario`、`app.solver` 旧公开导入保持有效。
- 前端 `src/App.tsx` 默认导出、`types/scheduler.ts` 导出和 `schedulerApi.ts` 40 个函数保持。
- 配置合并顺序保持：代码默认 → `default_scenario_config.json` → `.local-data/scheduler-config.json`。
- `.local-data/project-structure-params.json`、`.local-data/plan-control-store.json` 路径/schema 保持。
- `stable_id`、`stable_fingerprint`、场景指纹和旧结果失效语义保持。
- CP-SAT seed、worker、时间预算、warm start、阶段路由和资源搜索顺序不因纯重构变化。
- Netlify 只发布静态前端；`tools/demo-api-mirror/api.mts` 是未部署参考镜像，不是正式 FastAPI 后端。

架构门禁：

```powershell
npm.cmd run verify:architecture
```

## 6. 修改矩阵

| 修改类型 | 首先定位 | 必须同步检查 | 最小验证 |
| --- | --- | --- | --- |
| API 路径/状态码 | 对应 router / `main.py` 兼容入口 | 前端 API、OpenAPI 基线、错误映射 | API 专项 + 前端测试 |
| 共享字段/默认值 | 后端 contracts/`models.py` | 前端 contracts/types、存储、API、Netlify 参考差异 | schema/dump + typecheck + 构建 |
| 任务生成/工期 | scheduling generation/`scenario.py` | 工艺库、结构本体、里程碑、结果失效 | 固定输入任务图 + 全量后端 |
| 硬约束 | solver constraints | 所有策略、不可行诊断、性能 | 小样例 + 策略回归 |
| 软目标/目标函数 | solver objectives/strategies | objective_breakdown、前端标签、算法文档 | 目标贡献断言 + 等价/性能 |
| 资源搜索 | scheduling application resource_search | 上限、回退、成本、推荐口径 | 最少资源/成本回归 |
| AI 参数 | assistants/parameter 或旧 service | 短期 store、证据、冲突、应用后失效 | 参数助手专项 |
| AI 资源 | assistants/resource 或旧 service | LLM 降级、确定性校验、求解时限 | 资源助手专项 |
| 架梁专项 | `girder_planning/` | 版本/指纹、计划管控、综合快照 | girder + integrated 专项 |
| 计划管控 | `plan_control/` 或旧 services | 仓储版本、事实冻结、预测/调整 | repository + forecast 专项 |
| 前端状态 | app controller/workflows | generated/solve/comparison/integrated 失效 | Node + 构建 |
| 样式 | feature CSS / 聚合入口 | 导入顺序、弹层、响应式 | 构建 + 同视口视觉对比 |
| 部署 | Dockerfile/netlify.toml/runtime 文档 | 样例数据、环境变量、健康/SPA | Docker/Netlify/单服务冒烟 |

## 7. 算法解释规则

回答算法问题时至少区分：

- 输入对象、字段、单位、默认值和来源。
- 任务生成规则。
- 硬约束：不可违反，违反通常导致 infeasible/blocked。
- 软目标：可权衡，进入 CP-SAT objective。
- 诊断：解释/评价结果，不一定参与求解。
- 展示转换：前端标签或聚合，不是业务规则。

优先读取目标模块、`backend/tests/test_scheduler.py`、相关专项测试和 [算法当前实现文档](./docs/engineering/排程算法当前实现交底文档_v1.2.md)。不要把诊断指标写成目标项，也不要把 Demo 默认值写成正式产品规则。

## 8. 运行与验证

```powershell
# 后端全量
.\.venv\Scripts\python.exe -m pytest backend\tests -q

# 前端测试和构建
npm.cmd --workspace frontend test
npm.cmd run build

# 架构/仓库/文档
npm.cmd run verify:architecture

# 类型、全量测试、构建、包体和架构统一门禁
npm.cmd run verify
```

单服务：

```powershell
npm.cmd run build
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --app-dir backend
```

详细环境和部署边界见 [运行部署文档](./docs/architecture/runtime-and-deployment.md)，资产放置见 [仓库与资产治理](./docs/architecture/repository-governance.md)。

后台启动需要落盘日志时，统一使用 `tools/local-runtime/start_logged_process.ps1`，输出到 `.local-data/logs/<启动时间>/`。禁止在仓库根目录创建 `*.log`；历史根日志只能按 042 资产清单移动到 `.local-data/logs/legacy/`，不得未经确认删除。

## 9. 文档维护规则

- `README.md`：项目定位、当前能力、快速启动、验证和最短地图。
- `AGENTS.md`：工作分流与治理门禁，不写代码百科。
- `agent.md`：当前事实、所有权、调用链和修改矩阵。
- `docs/README.md`：文档状态、权威范围和替代关系。
- `docs/architecture/`：系统、模块、依赖、运行与 ADR。
- `specs/README.md`：规格状态；历史规格不移动不重编号。

修改模块、API、命令、环境变量、部署或规格状态时，同批更新对应入口并运行文档门禁。资产移动、取消跟踪或交付件重分区必须先提供逐文件清单并取得用户二次确认。

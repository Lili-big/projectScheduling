# 项目 Agent 工作手册

`AGENTS.md` 是执行规则；本文件只维护项目事实、模块所有权、调用链、兼容边界和修改矩阵，缺少这些事实时按需读取。

## 1. 项目事实

本项目是基建施工排程产品全生命周期工作区。`codex/road-pavement-engineering` 分支已实现路面首版，页面默认进入路面，`?engineering_domain=bridge` 保留桥梁入口。`01-customer-validation` 统一客户调研与验证、`02-solution-analysis` 方案、`03-requirements` 需求、`04-demo` 实现、`06-delivery` 交付，仓库规则由 `00-governance` 维护。主 Demo 是 `FastAPI + React + OR-Tools CP-SAT` 模块化单体；前端维护 `ScenarioInput`，后端生成任务图和 `ScheduleInput`，求解器返回 `ScheduleResult`/`ScenarioSolveResult`。

路面基础能力见 [`063-road-pavement-adaptation`](./03-requirements/specs/063-road-pavement-adaptation/spec.md)，当前支持段/幅/层主数据、三类工效、共享或独立机组、FS/SS/FF/SF及层间间歇、配套工序和实际相邻转场。仅支持固定机组、最早施工完成目标，连续日历天，不计末尾养生；配套及养生资源按充足考虑，未建模天气/温度和交通限制。按[`067-pavement-pending-last`](./03-requirements/specs/067-pavement-pending-last/spec.md)，待移交段纳入任务，在正常段所有任务完成后附条件排程；可行结果显示需移交日和预计施工完成日，不回写实际移交事实。当前客户25段100层已接入，结果日期仅来自通过硬约束校验的可行计划。

[068贪心初步计划](./03-requirements/specs/068-pavement-greedy-cpsat/spec.md)与[069限时并行优化及实时最好方案](./03-requirements/specs/069-pavement-live-optimization/spec.md)已接入：三种确定性贪心构造并校验完整初解，原模型以提示及工期上界继续搜索，最多8worker、seed0、内置LNS；CPU不足时降低worker。time_limit_seconds覆盖校验、构造、建模和优化，缺省15秒；已有合法方案时正常终态保留最好者，未证明最优则FEASIBLE，无方案才可能UNKNOWN。页面通过POST NDJSON先展示初解，再更新严格改善与最终状态；旧同步API仍可用。真实100任务15秒实测324→310天、缩短14天、计算15.051秒；独立HTTP验收首解0.341秒收到、最终311天，页面验收310天。并行结果存在波动，未接入专项下界、不承诺最优。

路面实时求解在输入/范围改变或组件卸载后取消旧连接，旧结果仅作历史查看；断连请求停止本次求解并释放线程，不创建持久作业或自动重算。未修改客户主数据、资源、工效和保存配置。

[070路面结果可视化](./03-requirements/specs/070-pavement-results-visualization/spec.md)已接入：运行时显示活动与本地已等待时间，施工段/工序两级表格对应横道和真实逻辑箭线，工艺等待可点击查看；机组里程轴按工点/桩号系列/幅别分区，以到访序号表达实际施工先后，连续同段合并、返回保留。跨桩号系列段单独显示无法定位，未推算地理距离。待移交显示“本方案最晚需移交日”，仍是该段最早开工前的移交要求。全部使用同次结果快照，算法及共享接口保持069行为。21项定向测试、构建和100任务宽窄屏检查通过；实际证据与限制见对应tasks。

[071单机资源时间图](./03-requirements/specs/071-pavement-resource-timeline/spec.md)已接入计划横道图与机组施工顺序之间：每套实际机组一行，日期横轴，可筛选、查看作业/转场/期间空闲详情及定位最长空闲。作业率分母为该机组首次开工至末次完工，期外不计空闲；缺失转场或异常数据降级提示，不自动归因窝工。21项前端测试、构建与宽窄屏核验通过；底部精简仍单独待办。历史按米厚度校验已移除，87项后端回归通过。用户之后停用全部19条沥青，当前19段76任务，6段匝道/连接线保持停用；FS+7、沥青转场1天与1000m/天保留，数量和启停由用户维护。m2/m3/t沿用原厚度规则，实际证据及规格完成状态见071任务记录。

[076路面班制工效](./03-requirements/specs/076-pavement-shift-productivity/spec.md)已接入：项目级多段单/双班区间配置在工序链页维护，双班日产出按基准工效×2；任务工期为开始日期的函数（逐日分段累计），贪心构造、CP-SAT 变量工期（每任务工期表约束）与逐解独立复核共用 `scheduling/domain/shift_regime.py` 唯一实现，班制随 ScheduleInput 进入指纹使旧结果自动失效。养生间歇按自然天、转场天数不变；无配置时与原实现逐位一致（HEAD 快照等价测试锁定）。结果页含单/双班拆分、双班区间横道标注与摘要说明；窝工优化在班制下可用。100任务15秒实测374→347天、构建0.25秒，性能与现状同量级。

```text
ScenarioInput
  -> GeneratedScheduleInput / ScheduleInput
  -> ScheduleResult / ScenarioSolveResult
```

[072机组流转图](./03-requirements/specs/072-pavement-crew-tl-flow/spec.md)已交付后按用户新批注简化为施工段分格的顺序示意图：各幅施工段按里程排序、等宽展示，全部到访编号及工序简名可见，同段回访向外分层，箭线严格连接实际相邻到访。取消日期刻度和时间作业条，位置/间距为示意，实际日期保留详情；全程/局部、高亮、节点间距及键盘导航可用。沿用既有顺序数据及异常处理，保留071资源时间图，不改求解或配置。验证及历史限制见072任务记录。

桥梁工作区保留的扩展能力包括：

- 桥梁结构参数 Excel 导入和本体映射。
- 固定资源最短工期、固定工期最少资源、资源成本优化。
- AI 参数输入助手和自然语言工艺设置。
- AI 资源方案生成、求解、比较和推荐。
- 架梁项目/方案版本、专项导入、校验、预览和综合排程。
- 计划基线、进度快照、预测、调整和采纳。

边界：规格完成状态以 [`03-requirements/specs/README.md`](./03-requirements/specs/README.md) 和对应 `tasks.md` 为准，不在本手册复制计数；未完成规格不得写成现状。生产权限、审计、租户/项目隔离、正式数据接入也未形成产品级实现。

## 2. 定位入口

模块入口不清时读取 [模块地图](./00-governance/architecture/module-map.md) 和下文修改矩阵；规格状态读取 [规格索引](./03-requirements/specs/README.md)。当前实现以代码、测试和运行结果为准，产品口径以已确认需求/规则为准。

## 3. 当前模块所有权

042 已把主要全局热点收敛为兼容 façade。旧入口继续可用，新业务必须进入拥有该领域的模块。

### 后端（根路径：`04-demo/backend/app/`）

| 能力 | 当前入口/所有权 | 验证 |
| --- | --- | --- |
| FastAPI 启动、CORS、静态和 SPA | `bootstrap.py`、`api/routers/`；`main.py` 为兼容入口 | API 契约、真实 HTTP、单服务冒烟 |
| 共享请求/响应契约 | `contracts/`；`models.py` 完整重导出 | schema/dump 与旧导入兼容测试 |
| 场景、任务生成、资源搜索、比较 | `scheduling/generation/`、`scheduling/application/`；`scenario.py` 兼容 | `test_scheduler.py`、行为基线 |
| CP-SAT 约束、目标、策略、结果 | `scheduling/solver/`；`solver.py` 兼容 | 求解器回归、固定等价、性能 |
| 路面主数据、生成及固定机组求解 | `contracts/pavement.py`、`project_master/`、`scheduling/generation/pavement.py`、`scheduling/application/pavement.py`、`scheduling/solver/constraints/pavement.py`、`scheduling/solver/strategies/pavement.py` | `test_pavement_*.py` |
| 桥梁导入 | `importing/bridge.py`；旧 bridge/service 兼容 | `test_bridge_import.py` |
| AI 参数助手 | `assistants/parameter/`；旧 service 兼容 | `test_ai_parameter_*` |
| AI 资源助手 | `assistants/resource/`；旧 service 兼容 | `test_ai_resource_scheduling_assistant.py` |
| 架梁专项 | `girder_planning/` application/adapter | `test_girder_*`、`test_integrated_schedule.py` |
| 计划管控 | `plan_control/`；旧 services 兼容 | `test_plan_control_*`、`test_progress_forecast.py` |
| 本地/发布配置 | `config/`、`default_scenario_config.json`；旧配置模块兼容 | 配置与存储契约测试 |

### 前端（根路径：`04-demo/frontend/src/`）

| 能力 | 当前入口/所有权 | 验证 |
| --- | --- | --- |
| 应用装配和跨 feature 状态 | `app/App.tsx`、`Workspace.tsx`、`app/workflows/`、`useWorkspaceController.ts` | Node 工作流、类型检查、构建 |
| 共享类型 | `contracts/`；`types/scheduler.ts` 完整重导出 | contracts 兼容测试 |
| API | `api/*Api.ts`；`schedulerApi.ts` 保留既有函数重导出 | API 兼容测试 |
| 工艺/逻辑/资源/里程碑 | 对应 `features/` 目录和 `domain/` 纯函数 | 构建、领域测试、页面冒烟 |
| AI 助手 | `features/assistant`、`features/resourceAssistant` | Node 测试、页面流程 |
| 架梁/计划管控 | `features/girderPlanning`、`features/planControl` | 对应 Node 测试和后端契约 |
| 任务与结果 | `features/taskView`、`features/scheduleResults`；`Workspace.tsx` 负责组合 | presenter/纯函数测试 |
| 样式 | `styles/tokens.css`、`base.css`、`layout.css` 与 feature CSS；`styles.css` 聚合 | 构建、视觉对比 |

### 生命周期仓库资产

| 资产 | 当前所有权 | 验证 |
| --- | --- | --- |
| 客户调研与验证 | `01-customer-validation/<项目>/` | 客户资料、验证计划和验证结果可追溯 |
| 方案与决策 | `02-solution-analysis/proposals/` | 方案边界与引用检查 |
| PRD、算法和规格 | `03-requirements/product/`、`rules/`、`specs/` | 文档、Spec Kit 门禁 |
| Demo 代码与样例 | `04-demo/backend/`、`frontend/`、`examples/`、`standalone/` | 后端/前端/部署与工作包测试 |
| 正式交付与演示 | `06-delivery/deliverables/`、`workpackages/`、`presentations/` | 版本、哈希和生成关系 |
| 本地状态与生成物 | `.local-data/state|logs|cache|tmp|locks|archive` | 保护优先、默认 dry-run |

更完整的所有权和依赖方向见 [模块地图](./00-governance/architecture/module-map.md) 与 [依赖规则](./00-governance/architecture/dependency-rules.md)。工作包索引见 [`workpackages.json`](./00-governance/asset-policy/workpackages.json)。

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

仓储权威路径为 `.local-data/state/plan-control-store.json`，迁移期兼容旧路径；它具有版本冲突和稳定指纹语义，但仍是单机演示存储。

## 5. 契约与兼容边界

- FastAPI 的当前接口清单以 `04-demo/backend/tests/fixtures/architecture/backend-baseline.json` 和运行服务的 `/openapi.json` 为准；042 冻结的原有方法、schema、状态码和错误 `detail` 保持兼容，后续新增操作由当前架构基线继续冻结。
- `uvicorn app.main:app --app-dir 04-demo/backend` 和 `app.main:app` 保持有效。
- `04-demo/backend/app/main.py`、`04-demo/backend/app/models.py`、`04-demo/backend/app/scenario.py`、`04-demo/backend/app/solver.py` 是受测试保护的短兼容入口；`app.models`、`app.scenario`、`app.solver` 旧公开导入保持有效。
- 前端 `src/App.tsx` 默认导出、`types/scheduler.ts` 导出和 `schedulerApi.ts` 既有函数保持。
- 配置合并顺序保持：代码默认 → `default_scenario_config.json` → `.local-data/state/scheduler-config.json`（兼容旧路径读取）。
- 路面领域显式分派，本地 v5 配置使用 `pavement_profiles[project_id]`，含计划开始日期、版本引用、工效选择、工序及机组；桥梁顶层配置保留。旧请求省略领域仍按桥梁处理。
- `.local-data/state/project-structure-params.json`、`.local-data/state/plan-control-store.json` 的 schema 与兼容语义保持。
- `stable_id`、`stable_fingerprint`、场景指纹和旧结果失效语义保持。
- CP-SAT seed、worker、时间预算、warm start、阶段路由和资源搜索顺序不因纯重构变化。
- Netlify 只发布静态前端；`04-demo/tools/demo-api-mirror/api.mts` 是未部署参考镜像，不是正式 FastAPI 后端。

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
| 部署 | 根 Dockerfile/netlify.toml 与 `04-demo/runtime/` | 样例数据、环境变量、健康/SPA | Docker/Netlify/单服务冒烟 |

## 7. 算法解释

算法解释按需使用 [`demo-algorithm-explainer`](./.agents/skills/demo-algorithm-explainer/SKILL.md)；本手册不复制其分类、回答结构和取证流程。

## 8. 运行与验证

可执行命令以根目录 `package.json` 的 `scripts` 为唯一清单；按修改矩阵选择最小门禁，发布级验证使用 `npm.cmd run verify`。部署边界见 [运行部署文档](./00-governance/architecture/runtime-and-deployment.md)，后台进程与日志只按 [`04-demo/runtime/README.md`](./04-demo/runtime/README.md) 操作。

## 9. 文档维护规则

- `README.md`：项目定位、当前能力、快速启动、验证和最短地图。
- `AGENTS.md`：工作分流与治理门禁，不写代码百科。
- `agent.md`：当前事实、所有权、调用链和修改矩阵。
- 六阶段 README：阶段目的、进入/退出条件、权威资产和工作包索引。
- `00-governance/architecture/`：系统、模块、依赖、运行与 ADR。
- `03-requirements/specs/README.md`：规格状态；规格编号和历史内容保持。
- 工作包 README / `workpackage.json`：输入、入口、成果、跟踪和保留策略。

修改模块、API、命令、环境变量、部署或规格状态时，只更新受影响的权威入口并运行文档门禁；资产归属与高风险确认遵循 `AGENTS.md` 和确定性治理策略。

# 模块所有权地图

本地图描述 042 重构后的当前边界。旧入口作为兼容 façade 保留；新业务不得继续堆入全局热点。

## 后端

| 领域 | 当前权威实现 | 兼容边界 | 公开入口 |
| --- | --- | --- | --- |
| HTTP 启动/路由 | `bootstrap.py` + `api/routers/` | `main.py` 转发旧 endpoint | `app.main:app`、57 个 `/api` 操作（含原有 45 个兼容契约） |
| 共享契约 | `contracts/_models.py` + 六个领域入口 | `models.py` 完整重导出 | `app.contracts`、`app.models` |
| 场景与任务生成 | `scheduling/application/_scenario.py`、generation/application | `scenario.py` 模块别名 | `app.scheduling`、`app.scenario` |
| CP-SAT 求解 | `scheduling/solver/engine.py` + constraints/objectives/strategies | `solver.py` 模块别名 | `app.scheduling.solver`、`app.solver` |
| 桥梁导入 | `bridge_import.py`、`services/bridge_import_service.py` | `importing/` | 导入 API 与旧 service |
| AI 参数助手 | `services/ai_parameter_*.py` | `assistants/parameter/` | parse/apply API 与旧 service |
| AI 资源助手 | `services/ai_resource_*.py` | `assistants/resource/` | 6 个资源助手 API 与旧 service |
| 架梁专项 | `girder_planning/`、`services/girder_schedule_adapter.py`、`integrated_schedule.py` | 领域包 + application façade | 项目版本、专项、联合快照 API |
| 计划管控 | `services/plan_control_repository.py`、`progress_forecast.py` | `plan_control/` | 基线、实绩、预测、调整 API |
| 配置 | `local_config.py`、`local_scenario_config.py`、`process_repository.py` | `config/` | 环境变量、`.local-data` 兼容路径 |

## 前端

| 领域 | 当前权威实现 | 兼容边界 | 公开入口 |
| --- | --- | --- | --- |
| 应用装配 | `app/App.tsx`、`Workspace.tsx`、controller/workflows | 根 `src/App.tsx` 保持 | `04-demo/frontend/src/App.tsx` 默认导出 |
| 共享契约 | `contracts/scheduler.ts` + 分域入口 | `types/scheduler.ts` | `contracts/index.ts`、旧完整重导出 |
| API | `_schedulerApi.ts` + 六个领域 API | `api/schedulerApi.ts` | 旧文件 40 个函数重导出 |
| 任务视图 | `features/taskView/` | `Workspace.tsx` 组合复杂表格 | feature `index.ts` |
| 求解结果 | `features/scheduleResults/` | `Workspace.tsx` 组合复杂结果面板 | feature `index.ts` |
| 工艺/逻辑/资源/里程碑 | `features/process`、`logic`、`resources`、`milestones` | 保持 feature 所有权 | 各 feature `index.ts` 或组件入口 |
| AI 助手 | `features/assistant`、`resourceAssistant` | 保持独立 feature | app 负责组合 |
| 架梁/计划管控 | `features/girderPlanning`、`planControl` | 只通过公开入口组合 | 各自 `index.ts` |
| 样式 | tokens/base/layout + feature 样式 | `styles.css` 12 行聚合入口 | `styles.css` |

## 数据与部署

- `.local-data/state/scheduler-config.json`：本地场景覆盖配置。
- `.local-data/project-structure-params.json`：项目结构参数。
- `.local-data/state/plan-control-store.json`：计划版本、实绩、预测和专项版本仓储。
- `04-demo/backend/app/default_scenario_config.json`：随代码发布的默认覆盖；合并顺序是代码默认 → 发布默认 → 本地覆盖。
- `Dockerfile`：Python 3.12 单服务镜像，启动 `app.main:app`。
- `netlify.toml`：静态前端构建/发布，不包含正式后端函数目录。
- `04-demo/examples/bridge-import/`：当前默认桥梁 Excel。
- `04-demo/tools/demo-api-mirror/`：未部署的旧 Netlify API 参考镜像。
- `01/05/06` 各工作包与 `06-delivery/presentations/ai-ppt-system/`：独立辅助工具，不进入主应用依赖。
- `06-delivery/deliverables/`：正式二进制交付物；`.local-data/archive/rebuildable/`：忽略的可再生成输出。
- `.local-data/logs/`：后台服务唯一日志落点。

## 修改入口

修改前先查 [依赖规则](./dependency-rules.md) 和 `agent.md` 的修改矩阵。算法、共享字段、跨前后端或中大型改造仍必须走 `AGENTS.md` 规定的 Spec Kit 门禁。

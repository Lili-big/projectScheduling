# 桥梁施工排程综合 Demo

本项目用 FastAPI、React 和 OR-Tools CP-SAT，把桥梁结构、工艺工效、工艺逻辑、资源、里程碑和求解策略组合成可解释的施工排程。当前仓库还包含 AI 参数输入、AI 资源方案、架梁专项联算和计划管控闭环的 Demo 能力。

项目适合产品验证、算法验证和研发交底；生产级用户权限、审计、项目隔离、正式数据接入与高可用不在当前实现范围。

## 快速启动

环境基线：Docker 使用 Python 3.12，Netlify 使用 Node 22。本地推荐 Python 3.12 与 Node 22。

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt --cache-dir .pip-cache
npm.cmd install --cache .npm-cache
```

单服务演示（FastAPI 同时提供 API 和构建后的前端）：

```powershell
npm.cmd run build
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --app-dir backend
```

- 页面：`http://127.0.0.1:8000/`
- 健康检查：`http://127.0.0.1:8000/api/health`

前后端分离开发：

```powershell
# 窗口 A
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --app-dir backend --reload

# 窗口 B
npm.cmd run frontend:dev
```

开发页面在 `http://127.0.0.1:5173/`；Vite 将 `/api` 代理到 `127.0.0.1:8000`。

## 当前能力

- 场景配置：项目结构、工艺工效、下部/部分上部结构逻辑、资源池、日历、里程碑和求解策略。
- 结构导入：读取桥梁 Excel/本体配置，生成统一项目模型、质量提示和稳定标识。
- 任务生成：`ScenarioInput` 转换为任务、前后置、资源候选和诊断。
- 三类求解：固定资源最短工期、固定工期最少资源、固定工期资源成本优化，并支持方案比较。
- AI 参数助手：从文本/资料形成可审阅建议，人工选择后再应用；默认不直接改当前方案。
- AI 资源助手：生成多套资源方案、逐套求解、比较和推荐；外部模型不可用时保留确定性本地路径。
- 架梁专项：项目/方案版本、工作点与实绩导入、专项校验、预览和综合排程快照。
- 计划管控：基线计划、进度快照、预测、调整建议和采纳的本地演示闭环。

`specs/041-girder-scheduling-integration` 当前为 74/95：统一发布、完整架梁实绩滚动、黄金样例影子验证等 21 项仍未完成。入口文档不会把这些规格目标描述为已交付能力。

## 核心链路

```text
ScenarioInput
  -> GeneratedScheduleInput / ScheduleInput
  -> ScheduleResult / ScenarioSolveResult
  -> 方案比较 / 架梁联合快照 / 计划基线与预测
```

主 HTTP 链路：`GET /api/demo-scenario` → `POST /api/generate-schedule-input` → `POST /api/solve-scenario`、`POST /api/solve-min-resources` 或 `POST /api/solve-resource-cost` → `POST /api/compare-scenarios`。

FastAPI 当前公开 45 个 `/api` 路由。完整契约由 `backend/tests/fixtures/architecture/backend-baseline.json` 和架构测试冻结；不要只根据文档表格推断字段或状态码。

## 目录地图

```text
backend/app/       FastAPI、契约、场景生成、CP-SAT、助手、架梁和计划管控
backend/tests/     后端行为、接口、导入、存储和性能回归
frontend/src/      React 应用、features、领域纯函数、API 和共享类型
frontend/tests/    前端工作流与兼容 Node 测试
docs/              当前架构、PRD、算法、页面和调研材料
specs/             Spec Kit 规格；历史路径和重复编号保持不变
examples/          桥梁导入样例和离线结果查看器
tools/             仓库治理、PPT、参考 API、交付物和本地运行工具
deliverables/      经确认保留版本控制的正式交付物
artifacts/         本地预览、检查和可再生成输出；默认忽略
.local-data/       本地配置、存储、运行状态和日志；默认忽略
```

详细所有权见 [模块地图](./docs/architecture/module-map.md)，文档状态见 [docs 索引](./docs/README.md)，规格状态见 [specs 索引](./specs/README.md)。开发/Agent 协作先读 `AGENTS.md`，项目事实和修改矩阵见 `agent.md`。

## 配置与本地数据

复制本地配置模板：

```powershell
Copy-Item .local.env.example .local.env
```

主要配置组：

- `BRIDGE_IMPORT_LLM_*`：桥梁导入适配器。
- `PROCESS_NL_LLM_*`：自然语言工艺设置的统一 LLM 适配器。
- `AI_RESOURCE_ASSISTANT_*`：资源助手可选覆盖；未设置时复用 `PROCESS_NL_LLM_*`。
- `AI_PARAMETER_ASSISTANT_*`：参数助手代码支持的可选外部模型配置；真实值只放 `.local.env`。
- `SCHEDULER_CORS_ORIGINS`、`SCHEDULER_CORS_ORIGIN_REGEX`：后端跨域。
- `VITE_API_BASE_URL`：生产前端连接完整后端的地址。

场景配置合并顺序：代码默认值 → `backend/app/default_scenario_config.json` → `.local-data/scheduler-config.json`。

其他本地数据：

- `.local-data/project-structure-params.json`：项目结构参数。
- `.local-data/plan-control-store.json`：计划管控、项目/方案版本和联合快照。
- `examples/bridge-import/渠溪河特大桥结构设计表.xlsx`：默认桥梁导入样例；读取器仍保留历史根路径兼容。

`.local.env` 和 `.local-data/` 已忽略，不要提交密钥或个人运行数据。

本地后台运行日志统一写入 `.local-data/logs/<启动时间>/`，不要再把 `*.out.log`、`*.err.log` 输出到仓库根目录。可使用统一启动辅助脚本：

```powershell
# 后端后台启动；命令会返回 PID 和 stdout/stderr 的实际路径
.\tools\local-runtime\start_logged_process.ps1 `
  -Name backend `
  -FilePath .\.venv\Scripts\python.exe `
  -ArgumentList @('-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', '8000', '--app-dir', 'backend')
```

原根目录 16 个历史日志已按确认清单移动到 `.local-data/logs/legacy/`，未删除且不提交 Git。详细规则见 [本地运行日志说明](./tools/local-runtime/README.md)。

## 验证

```powershell
# 后端全量
.\.venv\Scripts\python.exe -m pytest backend\tests -q

# 前端 Node 测试
npm.cmd --workspace frontend test

# TypeScript + 生产构建
npm.cmd run build

# 架构契约、依赖、仓库和文档门禁
npm.cmd run verify:architecture

# 类型、全量测试、构建、5% 包体和架构的统一门禁
npm.cmd run verify

# 单服务健康、静态资源和 SPA 回退
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\backend\scripts\smoke_single_service.ps1
```

`verify:architecture` 只运行架构子门禁；日常完整检查优先使用 `npm.cmd run verify`。算法改动还必须提供固定输入/期望输出或性能样例。

## 运行与部署

- 本地开发：Vite `5173` + FastAPI `8000`。
- 单服务演示：先构建 `frontend/dist`，再由 FastAPI 托管 SPA 和 API。
- Docker：当前镜像启动 `app.main:app` 并复制 `examples/` 样例；读取器仍兼容历史根样例路径。详见 [运行部署边界](./docs/architecture/runtime-and-deployment.md)。
- Netlify：`netlify.toml` 只构建并发布静态前端。生产必须设置 `VITE_API_BASE_URL` 指向独立 FastAPI/OR-Tools 后端。
- `tools/demo-api-mirror/api.mts` 是未部署的参考镜像，不能替代 45 路由 FastAPI 后端。

## 维护规则

- 不在 `app.main`、旧全局模型/场景/求解器或前端聚合入口继续新增无关业务；按 [依赖规则](./docs/architecture/dependency-rules.md) 找到所有权模块。
- 修改共享字段时同步检查后端契约、前端 contracts、API、持久化兼容和测试。
- 修改算法时明确硬约束、软目标、诊断和展示的区别。
- 涉及算法、资源、工期、共享字段或跨前后端中大型改动，按 `AGENTS.md` 走完整 Spec Kit。
- 不移动历史 specs，不批量删除/迁移资产；资产物理迁移必须提供逐文件清单并取得用户二次确认。
- 新资产按 [仓库与资产治理](./docs/architecture/repository-governance.md) 放置；当前迁移映射见 [路径迁移记录](./docs/archive/path-migration.md)。

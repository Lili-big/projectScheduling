# 基建施工排程工作区（公路路面适配）

当前分支 `codex/road-pavement-engineering` 已实现公路路面首版：按施工段、幅别和实际结构层导入主数据，配置碎石、水稳、沥青三类工艺及独立机组，生成任务并计算施工、养生、转场和末层可用日期。自动样例闭环已验证，真实客户数据核对待开展。

页面默认进入路面工作区；`?engineering_domain=bridge` 保留桥梁入口。新路面项目保持待导入空态，不自动填入演示数据。启动后按下方所选模式打开对应地址。

本机默认路面项目已录入用户提供的15个施工段（左幅8段、右幅7段，合计34,582m）。K675+120-CK0+000段宽度14m，其余14段宽度9.2m。结构层挂在各施工段下，可编辑并保存到本地；碎石垫层0.16m，三层水稳各0.20m、水稳密度2.38t/m³，沥青层停用。厚度、密度及工程量属于具体结构层，吨位按施工长度×宽度×层厚×密度计算并取整数展示；排程计量仍按施工长度。数据保存在本机项目主数据存储中，不自动注入其他项目或新环境。

## 快速启动

以下命令用于 Windows PowerShell，均在仓库根目录执行。先切换目录（项目在其他位置时修改路径）：

```powershell
Set-Location 'D:\codex_workspace\基建版本'
```

**首次使用才需要安装依赖。**已有可用的 `.venv` 和 `node_modules` 时直接选择下面一种启动方式。环境基线：Docker 使用 Python 3.12，Netlify 使用 Node 22；本地推荐 Python 3.12 与 Node 22。

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt --cache-dir .pip-cache
npm.cmd ci --cache .npm-cache
```

`py -3.12` 是 Windows Python 启动器命令。如果未安装启动器，使用已安装的 Python 3.12 可执行文件完整路径执行 `-m venv .venv`。后续后端命令统一使用项目内的 `.venv`。

**方式 A：单服务演示（一个终端，适合直接使用页面）。**先构建前端，再由 FastAPI 同时提供页面和 API：

```powershell
npm.cmd run build
if ($LASTEXITCODE -eq 0) {
  .\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --app-dir 04-demo/backend
}
```

- 页面：[http://127.0.0.1:8000/](http://127.0.0.1:8000/)
- 健康检查：[http://127.0.0.1:8000/api/health](http://127.0.0.1:8000/api/health)

看到 `Uvicorn running on http://127.0.0.1:8000` 后打开页面。该命令会持续占用终端，属于正常运行；关闭终端或按 `Ctrl+C` 会停止服务。修改前端代码后，单服务模式需重新构建。

**方式 B：前后端分离开发（两个终端，支持前端热更新）。**两个终端都先切换到仓库根目录；不要将两段命令依次粘贴到同一个终端。

终端 A 启动后端：

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --app-dir 04-demo/backend --reload
```

终端 B 启动前端（固定使用5174端口）：

```powershell
npm.cmd run frontend:dev -- --port 5174 --strictPort
```

打开 [http://127.0.0.1:5174/](http://127.0.0.1:5174/)。Vite 将 `/api` 代理到 `127.0.0.1:8000`，因此两个服务都必须保持运行。`--strictPort` 会在5174被占用时报错，不会悄悄换端口。省略端口参数时，`npm.cmd run frontend:dev` 默认从5173开始寻找可用端口，以启动日志为准。

检查启动结果（可在第三个终端执行）：

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/health
# 仅方式 B：同时检查前端到后端的代理
Invoke-RestMethod http://127.0.0.1:5174/api/health
```

两种方式共用8000端口，不要重复启动后端。后台启动、日志和停止方式见 [本地运行说明](./04-demo/runtime/README.md)。

常见问题：

- `py` 无法识别：已有虚拟环境时直接使用 `.\.venv\Scripts\python.exe`；首次安装请使用 Python 3.12 可执行文件完整路径创建虚拟环境。
- `npm` 提示脚本执行被禁止：使用示例中的 `npm.cmd`，无需修改系统执行策略。
- 找不到 `package.json` 或 `.venv`：确认终端当前目录是仓库根目录。
- 8000或5174端口被占用：先检查该地址是否已有本项目服务，再决定复用或停止自己启动的服务，不要按进程名批量终止。
- 前端页面可打开但请求失败：先检查8000的健康接口；只启动 Vite 不会启动后端。

本仓库不再只是 Demo 代码集合，而是覆盖前期需求调研、过程方案分析、需求文档设计、Demo 实现、客户验证和正式交付的产品全生命周期工作区。FastAPI、React 和 OR-Tools CP-SAT Demo 是其中的实现与验证环节。

根目录按“阶段”表达业务所有权；每个可独立运行的专项再按工作包组织输入、脚本、成果与保留策略。项目仍适合产品验证、算法验证和研发交底；生产级用户权限、审计、项目隔离、正式数据接入与高可用不在当前实现范围。

## 生命周期导航

| 阶段 | 回答的问题 | 主要入口 |
| --- | --- | --- |
| [`00-governance`](./00-governance/README.md) | 仓库如何治理、归类、校验和回退？ | 架构、资产策略、治理工具、迁移历史 |
| [`01-customer-validation`](./01-customer-validation/README.md) | 客户资料说明什么，产品判断是否成立？ | 客户资料、验证计划、验证结果 |
| [`02-solution-analysis`](./02-solution-analysis/README.md) | 有哪些方案，为什么选择当前路径？ | 产品方向、融合方案、MVP、决策 |
| [`03-requirements`](./03-requirements/README.md) | 已确认口径如何变成可验收需求？ | PRD、算法规则、Spec Kit 规格 |
| [`04-demo`](./04-demo/README.md) | 如何实现并运行 Demo？ | 后端、前端、样例、独立展示工具 |
| [`06-delivery`](./06-delivery/README.md) | 哪些成果可正式交付和传播？ | 交付物、案例总结、演示材料 |

最短查找路径：先选阶段，再打开阶段 README；独立专项继续进入其 `workpackage.json` 和 README。全仓工作包索引见 [`workpackages.json`](./00-governance/asset-policy/workpackages.json)。

## 当前能力

路面工作区：

- 主数据：复用 Excel 导入、问题预览、版本确认和回读；支持段/幅/层、原始桩号、确认净长、层厚、工程量及路床可用日期。
- 工艺工效：碎石、水稳、沥青三类，支持 m、m2、m3、t 与对应日工效，按单套机组计算并向上取整。
- 工序：按实际层序建立关系，逐层确认养生/冷却和验收可用条件；透层、封层、黏层作为可配置配套步骤。
- 资源与求解：三类独立机组分别配置数量、范围、转场天数；增加机组用于并行工作面，养生不占主机组。按实际相邻作业计转场，以整体最早可用日期为目标。
- 保存与结果：按项目保存工效、工序、资源及计划开始日期；输入变化标记旧结果过期，展示施工、等待、机组路径、转场和可用日期。

保留的桥梁工作区能力：

- 场景配置：项目结构、工艺工效、下部/部分上部结构逻辑、资源池、里程碑和求解策略。
- 结构导入：读取桥梁 Excel/本体配置，生成统一项目模型、质量提示和稳定标识。
- 任务生成：`ScenarioInput` 转换为任务、前后置、资源候选和诊断。
- 三类求解：固定资源最短工期、固定工期最少资源、固定工期资源成本优化，并支持方案比较。
- AI 参数助手：从文本/资料形成可审阅建议，人工选择后再应用；默认不直接改当前方案。
- AI 资源助手：生成多套资源方案、逐套求解、比较和推荐；外部模型不可用时保留确定性本地路径。
- 架梁专项：项目/方案版本、工作点与实绩导入、专项校验、预览和综合排程快照。
- 计划管控：基线计划、进度快照、预测、调整建议和采纳的本地演示闭环。

路面首版边界：只支持固定机组求解，配套班组及养生管理资源按充足考虑，采用连续日历天，未实现天气、温度窗口、交通组织或拌合站产能优化。路面导航隐藏桥梁 AI 助手、架梁专项、资源成本优化和计划管控等不适用模块及空分组，后端仍拒绝不支持的请求。桥梁通用共享资源的原有转场与日历边界保持不变。

架梁专项 041 当前完成 74/95，仍有 21 项任务未完成，包括统一发布、完整架梁实绩滚动、黄金样例影子验证等。各规格状态以 [specs 索引](./03-requirements/specs/README.md) 和对应 `tasks.md` 为准，未完成项不作为已交付能力。

## 核心链路

```text
ScenarioInput
  -> GeneratedScheduleInput / ScheduleInput
  -> ScheduleResult / ScenarioSolveResult
  -> 方案比较 / 架梁联合快照 / 计划基线与预测
```

主 HTTP 链路：`GET /api/demo-scenario` → `POST /api/generate-schedule-input` → `POST /api/solve-scenario`、`POST /api/solve-min-resources` 或 `POST /api/solve-resource-cost` → `POST /api/compare-scenarios`。

上述完整策略链属于桥梁。路面通过 `engineering_domain=pavement` 和 `project_id` 读取配置，确认主数据版本后调用生成及固定机组求解；最少资源和资源成本接口明确拒绝路面请求。

FastAPI 的接口清单和契约以 `04-demo/backend/tests/fixtures/architecture/backend-baseline.json`、架构测试及运行服务的 `/openapi.json` 为准。启动后可访问 [接口文档](http://127.0.0.1:8000/docs)，不要只根据文档表格推断字段或状态码。

## 目录地图

```text
00-governance/          架构、资产规则、治理工具和迁移历史
01-customer-validation/ 客户资料、验证计划和验证结果工作包
02-solution-analysis/   产品方向、方案比较、技术可行性与决策
03-requirements/        PRD、算法规则和 specs/<编号>-<功能名>
04-demo/                主 Demo 后端/前端、样例、运行工具与独立展示
06-delivery/            正式交付物、案例总结与演示材料
.local-data/            状态、日志、缓存、临时和可再生成归档；默认忽略
```

详细所有权见 [模块地图](./00-governance/architecture/module-map.md)，规格状态见 [specs 索引](./03-requirements/specs/README.md)。开发/Agent 协作先读 `AGENTS.md`，项目事实和修改矩阵见 `agent.md`。

## 新任务放到哪里

资产位置由 [`placement-rules.json`](./00-governance/asset-policy/placement-rules.json) 和治理验证器决定；人类导航见 [仓库与资产治理](./00-governance/architecture/repository-governance.md)。未知资产先完成分类，不创建通用兜底目录。

## 配置与本地数据

基础页面和本地排程无需配置外部模型密钥。需要覆盖默认配置时，仅在 `.local.env` 不存在时复制模板，避免覆盖已有配置：

```powershell
if (-not (Test-Path .local.env)) {
  Copy-Item .local.env.example .local.env
}
```

主要配置组：

- `BRIDGE_IMPORT_LLM_*`：桥梁导入适配器。
- `PROCESS_NL_LLM_*`：自然语言工艺设置的统一 LLM 适配器。
- `AI_RESOURCE_ASSISTANT_*`：资源助手可选覆盖；未设置时复用 `PROCESS_NL_LLM_*`。“AI快速配置工装”必须配置真实外部 provider、endpoint、model 和 API Key，调用失败时不会使用本地推荐回退；修改 `.local.env` 后需重启后端。
- `AI_PARAMETER_ASSISTANT_*`：参数助手代码支持的可选外部模型配置；真实值只放 `.local.env`。
- `SCHEDULER_CORS_ORIGINS`、`SCHEDULER_CORS_ORIGIN_REGEX`：后端跨域。
- `VITE_API_BASE_URL`：前端连接独立后端的地址；单服务同源部署及默认 Vite 开发代理可不设置，Netlify 静态部署需配置。

场景配置合并顺序：代码默认值 → `04-demo/backend/app/default_scenario_config.json` → `.local-data/state/scheduler-config.json`。

路面使用该文件 v5 的 `pavement_profiles[project_id]` 独立保存，不复用桥梁工艺默认值。工效初值只是参考值；养生、验收、净量及转场必须按项目确认。

其他本地数据：

- `.local-data/state/project-structure-params.json`：项目结构参数。
- `.local-data/state/project-master.db`：默认项目主数据 SQLite 存储，可通过 `PROJECT_MASTER_DB_PATH` 覆盖；模板显式配置的路径以模板值为准。
- `.local-data/state/plan-control-store.json`：计划管控、项目/方案版本和联合快照。
- `04-demo/examples/bridge-import/渠溪河特大桥结构设计表.xlsx`：默认桥梁导入样例。

`.local.env` 和 `.local-data/` 已忽略，不要提交密钥或个人运行数据。模型密钥只放后端 `.local.env`，不得使用 `VITE_*` 变量或传给浏览器。

后台进程、PID、stdout/stderr 和历史日志处理只按 [`04-demo/runtime/README.md`](./04-demo/runtime/README.md) 操作。

## 验证

```powershell
# 后端全量
.\.venv\Scripts\python.exe -m pytest 04-demo\backend\tests -q

# 前端 Node 测试
npm.cmd --workspace 04-demo/frontend test

# TypeScript + 生产构建
npm.cmd run build

# 架构契约、依赖、仓库和文档门禁
# 聚合脚本调用 python，先将项目虚拟环境加入当前终端 PATH
$env:Path = (Resolve-Path .\.venv\Scripts).Path + ";" + $env:Path
npm.cmd run verify:architecture

# 类型、全量测试、构建、包体预算、架构和生命周期的统一门禁
npm.cmd run verify

# 单服务健康、静态资源和 SPA 回退
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\04-demo\backend\scripts\smoke_single_service.ps1
```

`verify:architecture` 只运行架构子门禁；日常完整检查优先使用 `npm.cmd run verify`。算法改动还必须提供固定输入/期望输出或性能样例。

063 的路面专项验收、真实 HTTP/页面记录及全量测试既有失败对照见 [验证指南](./03-requirements/specs/063-road-pavement-adaptation/quickstart.md)。当前不能宣称全仓验证全绿。

## 运行与部署

- 本地开发：Vite `5173` + FastAPI `8000`。
- 单服务演示：先构建 `04-demo/frontend/dist`，再由 FastAPI 托管 SPA 和 API。
- Docker：当前镜像启动 `app.main:app` 并复制 `04-demo/examples/` 样例。详见 [运行部署边界](./00-governance/architecture/runtime-and-deployment.md)。
- Netlify：`netlify.toml` 只构建并发布静态前端。生产必须设置 `VITE_API_BASE_URL` 指向独立 FastAPI/OR-Tools 后端。
- `04-demo/tools/demo-api-mirror/api.mts` 是未部署的参考镜像，不能替代完整 FastAPI 后端。

## 维护规则

- 不在 `app.main`、旧全局模型/场景/求解器或前端聚合入口继续新增无关业务；按 [依赖规则](./00-governance/architecture/dependency-rules.md) 找到所有权模块。
- 修改共享字段时同步检查后端契约、前端 contracts、API、持久化兼容和测试。
- 修改算法时明确硬约束、软目标、诊断和展示的区别。
- 涉及算法、资源、工期、共享字段或跨前后端中大型改动，按 `AGENTS.md` 走完整 Spec Kit。
- 不移动历史 specs；资产归属、迁移和不可逆操作按 `AGENTS.md` 及仓库治理规则处理。
- 新资产按 [仓库与资产治理](./00-governance/architecture/repository-governance.md) 放置；当前迁移映射见 [路径迁移记录](./00-governance/history/path-migration.md)。

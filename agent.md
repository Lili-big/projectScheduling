# 项目 Agent 导览

本文档面向后续进入本仓库的 agent 和工程师，用于快速理解项目业务架构、技术架构、核心数据流和协作边界。

## 1. 项目定位

本项目是一个桥梁施工自动排程 Demo，核心目标是把桥梁结构物参数、施工工艺工效、工艺逻辑、资源配置和里程碑目标统一建模，再通过 OR-Tools CP-SAT 求解器生成可执行的施工排程计划。

当前系统已经从单一 WBS 原型升级为“场景化模拟”模型。前端维护完整的 `ScenarioInput`，后端将其转换为 `ScheduleInput`，求解器输出 `ScheduleResult`，最终由前端展示甘特图、资源分配、里程碑偏差、诊断信息和方案对比。

核心链路：

```text
ScenarioInput -> ScheduleInput -> ScheduleResult
```

当前业务范围以桥梁下部结构为主，包括桩基、承台、扩大基础、地系梁、中系梁、墩柱、盖梁、桥台等；同时已纳入部分上部现浇结构任务派生，例如现浇箱梁、现浇连续梁/连续刚构。简支梁当前主要作为结构参数和展示信息保留，不生成现场架梁排程任务。

## 2. 业务架构

### 2.1 核心业务对象

- 项目结构参数：按 `ProjectModel -> ProjectBridge -> WorkSection -> StructureModel -> ComponentModel` 组织，表示项目、桥梁、工区/幅别、墩台和构件。
- 上部结构参数：通过 `UpperStructureComponent` 表示跨号、支座范围、跨径、结构类型和连续梁配置，用于派生部分上部现浇任务。
- 工艺工效库：通过 `ProcessTemplate` 和 `ProductivityOption` 维护“构件类型 -> 施工工艺 -> 工效分组 -> 默认资源”的关系。
- 工艺逻辑：通过 `LogicRule` 和 `UpperStructureLogicRule` 描述 FS/SS/FF/SF 前后置关系、滞后天数和候选前置回退策略。
- 资源池：通过 `ResourcePool` 定义资源类型、数量、最大数量、日历和启用状态，后端会展开为命名资源。
- 里程碑：通过 `MilestoneConstraint` 表示合同节点、强控节点和内部节点，可作用于项目、桥梁、工区、结构物、构件类型或单个构件。
- 排程结果：`ScheduleResult` 包含任务起止日期、资源分配、里程碑结果、诊断、统计指标和目标函数拆解。

### 2.2 业务模块

- 项目参数：展示结构树，导入或接入桥梁结构参数，配置构件工艺和工效。
- 工艺工效库：维护施工工艺、工效分组、默认工效和默认资源类型。
- 工艺逻辑：维护构件之间的前后置关系，支持同一墩台内逻辑和跨结构顺序扩展。
- 资源配置：维护资源池数量、最大数量、资源模式、日历和启用状态。
- 里程碑：维护合同、强控、内部节点及软硬约束。
- 任务视图/模拟结果：生成任务图、调用求解器、展示甘特图、资源分配、连续性指标、诊断和方案对比。

### 2.3 业务数据流

```text
初始化默认场景或导入 Excel/结构参数 API
  -> 形成 ScenarioInput.project
  -> 用户编辑工艺、工效、逻辑、资源、里程碑
  -> POST /api/generate-schedule-input 生成任务图
  -> POST /api/solve-scenario 固定资源求最短工期
     或 POST /api/solve-min-resources 固定工期求最少资源
  -> 展示甘特图、资源分配、里程碑偏差、诊断和连续性指标
  -> 可保存多个结果并通过 POST /api/compare-scenarios 做方案对比
```

影响任务、资源、工期或逻辑的配置变更后，应清空旧的生成结果和求解结果，避免展示过期排程。

## 3. 技术架构

### 3.1 前端

- 技术栈：React 19、Vite、TypeScript、lucide-react。
- 入口文件：`frontend/src/App.tsx`。
- 样式文件：`frontend/src/styles.css`。
- 开发代理：`frontend/vite.config.ts` 将 `/api` 代理到 `http://127.0.0.1:8000`。
- 前端维护同一个 `ScenarioInput` 状态，并通过 API 调用后端生成任务图、求解、导入 Excel、应用自然语言工艺设置和保存工艺库。

### 3.2 后端

- 技术栈：FastAPI、Pydantic、OR-Tools CP-SAT、openpyxl、psycopg。
- API 入口：`backend/app/main.py`。
- 数据模型：`backend/app/models.py`。
- 默认场景：`backend/app/scenario_data.py`。
- 工艺工效默认库及迁移：`backend/app/process_library_defaults.py`。
- 场景转换与业务编排：`backend/app/scenario.py`。
- 求解器：`backend/app/solver.py`。
- Excel/结构参数导入：`backend/app/bridge_import.py`。
- 自然语言工艺设置：`backend/app/process_nl.py`。
- 工艺库持久化：`backend/app/process_repository.py`。

后端主要职责是校验输入、生成可求解任务网络、展开资源、构建 CP-SAT 模型、计算里程碑结果和返回诊断信息。

### 3.3 求解器

`backend/app/solver.py` 使用 OR-Tools CP-SAT 建模：

- 为每个任务建立开始、结束和区间变量。
- 根据 `PrecedenceLink` 添加 FS/SS/FF/SF 约束。
- 根据候选资源建立可选区间，并对每个命名资源添加 `NoOverlap`。
- 将软里程碑迟延转为目标函数罚分。
- 固定资源最短工期模式最小化总工期、软里程碑罚分和施工连续性惩罚。
- 固定工期最少资源模式使用资源池 `max_quantity` 作为上限，输出推荐资源数量。

求解结果中包含 `continuity_metrics`，用于评价同构件工艺拆分、跳墩、换幅、跨幅跳转和方向反转等施工连续性问题。

### 3.4 数据导入与本体配置

- 桥梁结构本体：`backend/app/ontology/bridge_structure_ontology.v1.json`。
- 工艺逻辑本体：`backend/app/ontology/bridge_schedule_logic_ontology.v1.json`。
- Excel 导入默认使用本地本体适配器，支持读取 `.xlsx/.xlsm`，标准化合并表头和合并单元格，并映射为 `ProjectModel`。
- 实际工程中，结构物参数 API 应作为权威数据源；Excel 导入作为补充导入、历史兼容或校核能力。

### 3.5 持久化与外部服务

- 工艺工效库可通过 Supabase PostgreSQL session pool 持久化到 `public.process_relationships`。
- 浏览器端不应暴露 Supabase 写入凭据，保存工艺库必须经由后端 `PUT /api/process-library`。
- 本地配置通过 `.local.env` 加载，常用变量包括：
  - `SUPABASE_POSTGRES_SESSION_POOL_URL`
  - `SUPABASE_POSTGRES_POOL_SIZE`
  - `BRIDGE_IMPORT_LLM_PROVIDER`
  - `PROCESS_NL_LLM_PROVIDER`
  - `PROCESS_NL_LLM_ENDPOINT`
  - `PROCESS_NL_LLM_MODEL`
  - `PROCESS_NL_LLM_API_KEY`

### 3.6 Netlify 演示 API

- Netlify 配置：`netlify.toml`。
- Netlify Functions 入口：`netlify/functions/api.mts`。
- 该函数提供前端部署场景下的演示 API，实现默认场景、任务生成、求解、导入和自然语言工艺设置等能力的 TypeScript 版本。
- Python 后端仍是本地工程化和测试验证的主要实现。

## 4. API 总览

- `GET /api/health`：健康检查。
- `GET /api/demo-scenario`：返回完整默认 `ScenarioInput`，并尝试加载持久化工艺库。
- `GET /api/process-library`：获取标准化后的工艺工效库。
- `PUT /api/process-library`：保存工艺工效库到后端持久化存储。
- `POST /api/import-bridge-params`：multipart 上传 Excel、当前 `ScenarioInput` 和可选目标桥名，返回更新后的场景、Canonical Bridge JSON、质量检查和告警。
- `POST /api/import-local-bridge-params`：导入项目根目录下的本地 Excel 样例。
- `POST /api/apply-process-natural-language`：根据自然语言批量修改构件工艺。
- `POST /api/generate-schedule-input`：将 `ScenarioInput` 转换为任务图和求解输入。
- `POST /api/solve-scenario`：固定资源数量求最短工期。
- `POST /api/solve-min-resources`：固定目标工期求最少资源。
- `POST /api/compare-scenarios`：对多个求解结果做方案对比。
- 兼容接口：`GET /api/demo`、`POST /api/generate-wbs`、`POST /api/solve`。

## 5. 关键模块索引

- `backend/app/main.py`：FastAPI 路由、CORS、静态前端托管和 multipart 导入解析。
- `backend/app/models.py`：前后端共享的核心业务模型和响应模型。
- `backend/app/scenario.py`：场景到求解输入的转换、上部结构任务派生、资源展开、方案求解编排和方案对比。
- `backend/app/solver.py`：CP-SAT 建模、求解、里程碑评估、连续性指标和最少资源模式。
- `backend/app/bridge_import.py`：Excel 解析、本体映射、Canonical Bridge JSON 和 `ProjectModel` 转换。
- `backend/app/process_repository.py`：Supabase 工艺工效库读写。
- `backend/app/process_nl.py`：本地规则或 LLM 适配的自然语言工艺设置。
- `backend/app/process_library_defaults.py`：历史工效数据升级到标准 `ProcessTemplate + ProductivityOption`。
- `backend/app/scenario_data.py`：默认场景、默认资源池、默认里程碑和默认工艺逻辑。
- `frontend/src/App.tsx`：前端状态、页面模块、API 调用、任务视图和结果展示。
- `frontend/src/styles.css`：前端样式。
- `netlify/functions/api.mts`：Netlify 部署场景的 TypeScript 演示 API。

## 6. 开发与验证

### 6.1 安装依赖

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt --cache-dir .pip-cache
npm --prefix frontend install --cache .npm-cache
```

如果当前机器没有把 `npm` 加入 `PATH`，按 README 使用完整路径执行 npm 命令。

### 6.2 本地运行

推荐先构建前端，再由 FastAPI 同时托管页面和 API：

```powershell
npm --prefix frontend run build
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --app-dir backend
```

访问：

- 页面：`http://127.0.0.1:8000/`
- 健康检查：`http://127.0.0.1:8000/api/health`

前后端分离开发：

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --app-dir backend --reload
npm --prefix frontend run dev
```

Vite 默认访问 `http://127.0.0.1:5173/`。

### 6.3 验证命令

```powershell
.\.venv\Scripts\python.exe -m pytest backend\tests -q
npm --prefix frontend run build
```

文档类改动通常不需要完整业务测试作为必需项，但提交前至少应人工检查 Markdown 标题层级、路径和命令是否与 README 保持一致。

## 7. 协作注意事项

- 本仓库包含中文文档和中文业务术语，编辑文档时保持 UTF-8。
- 不要重置、覆盖或回滚不是自己本轮产生的未提交改动。
- 修改 `models.py` 的接口字段时，应同步检查 `frontend/src/App.tsx` 中的 TypeScript 类型和 Netlify Functions 类型。
- 修改排程业务逻辑时，应同步补充或更新 `backend/tests/test_scheduler.py`。
- 修改 Excel 导入、结构本体或自然语言工艺设置时，应同步检查 `backend/tests/test_bridge_import.py`。
- 修改工艺工效默认库时，应确保每个 `ProcessTemplate` 至少有一个 `ProductivityOption`，且只有一个默认工效。
- Supabase、LLM 和外部适配器凭据只能通过后端 `.local.env` 或部署环境变量配置，不要写入前端代码或仓库文档示例的真实值。
- `bridge_schedule_logic_ontology.v1.json` 可由产品或业务人员维护默认工艺逻辑，但新增构件类型时必须同步后端模型、前端标签、工艺库和测试。


# 项目 Agent 工作手册

本文档面向后续进入本仓库的 agent、研发和测试，用于快速理解项目定位、文件结构、核心数据流、开发验证方式和协作边界。

本文只保留对长期协作有价值的项目知识。梳理文件时应关注源码、配置、需求文档、样例数据和项目技能，并排除本地密钥、依赖、缓存、日志、构建产物和 `__pycache__`。

## 1. 项目定位

本项目是一个桥梁施工自动排程 Demo，使用 `FastAPI + React + OR-Tools CP-SAT` 将桥梁结构物参数、施工工艺工效、工艺逻辑、资源配置和里程碑目标统一建模，生成可执行的施工排程计划。

系统已从单一 WBS 原型升级为“场景化模拟”模型。前端维护完整 `ScenarioInput`，后端转换为 `ScheduleInput`，求解器输出 `ScheduleResult`，前端再展示任务视图、甘特图、资源分配、里程碑偏差、诊断信息、连续性指标和方案对比。

核心链路：

```text
ScenarioInput -> GeneratedScheduleInput / ScheduleInput -> ScheduleResult
```

已实现业务范围以桥梁下部结构为主，包括桩基、承台、扩大基础、地系梁、中系梁、墩身、盖梁、桥台等；同时已纳入现浇箱梁、现浇连续梁/连续刚构等部分上部现浇结构任务派生。简支梁、钢箱梁和桥面系主要作为结构参数、工艺模板或后续扩展对象保留，不生成对应现场任务。

## 2. 文件索引

### 2.1 根目录文件

- `.gitignore`：忽略本地环境、依赖、缓存、日志、构建产物，以及 `docs/` 和 `skills/` 下的新增内容。
- `.local.env.example`：本地配置模板，包含 Supabase、Excel 导入 AI 适配器和自然语言工艺设置适配器变量示例。
- `README.md`：项目简介、本地运行、端口清理、验证命令、Supabase 和本体配置说明。
- `agent.md`：本文件，项目 agent 工作手册。
- `requirements.txt`：Python 依赖，包含 FastAPI、openpyxl、uvicorn、OR-Tools、pytest、psycopg。
- `package.json` / `package-lock.json`：根目录 Netlify Functions 演示依赖，主要包含 `read-excel-file`。
- `netlify.toml`：Netlify 构建和 Functions 配置。
- `渠溪河特大桥结构设计表.xlsx`：本地桥梁结构设计样例，用于 Excel 结构参数导入和测试。

不要把 `.local.env` 写入文档或代码；它是本地私密配置，应始终保持忽略。

### 2.2 后端文件

- `backend/app/main.py`：FastAPI 入口，注册 API、CORS、静态前端托管和 multipart 导入。
- `backend/app/models.py`：前后端共享业务模型和响应模型，包括 `ScenarioInput`、`ScheduleInput`、`ScheduleResult` 等。
- `backend/app/scenario.py`：场景转换、任务生成、资源展开、固定资源求解、最少资源求解、资源成本求解和方案对比编排。
- `backend/app/solver.py`：OR-Tools CP-SAT 建模与求解，处理前后置、资源互斥、里程碑、连续性、最少资源和资源成本优化。
- `backend/app/wbs.py`：早期 WBS 兼容逻辑、工期计算和基础前后置生成。
- `backend/app/scenario_data.py`：默认场景、默认资源池、默认里程碑、默认工艺逻辑和业务默认值。
- `backend/app/sample_data.py`：早期 demo 的桥梁、工效、逻辑和资源样例数据。
- `backend/app/process_library_defaults.py`：历史工效数据升级为 `ProcessTemplate + ProductivityOption`。
- `backend/app/process_repository.py`：Supabase PostgreSQL session pool 读写 `public.process_relationships`。
- `backend/app/process_nl.py`：本地规则或 LLM 适配的自然语言工艺设置。
- `backend/app/bridge_import.py`：Excel 解析、本体映射、Canonical Bridge JSON 和 `ProjectModel` 转换。
- `backend/app/local_config.py`：启动时读取 `.local.env` 到环境变量。
- `backend/app/api/multipart.py`：multipart 请求解析工具。
- `backend/app/services/process_library_service.py`：默认场景与工艺库加载/保存服务封装。
- `backend/app/services/bridge_import_service.py`：上传 Excel 和本地样例 Excel 导入服务封装。
- `backend/app/ontology/bridge_structure_ontology.v1.json`：桥梁结构本体配置。
- `backend/app/ontology/bridge_schedule_logic_ontology.v1.json`：桥梁施工逻辑本体配置。
- `backend/tests/test_scheduler.py`：排程、工期、资源、里程碑、连续性、最少资源、资源成本和方案对比测试。
- `backend/tests/test_bridge_import.py`：Excel 导入、结构映射、自然语言工艺设置和 multipart 接口测试。

### 2.3 前端文件

- `frontend/package.json` / `frontend/package-lock.json`：前端依赖和脚本，主要脚本为 `dev`、`build`、`preview`。
- `frontend/vite.config.ts`：Vite 配置，开发时将 `/api` 代理到 `http://127.0.0.1:8000`。
- `frontend/tsconfig.json`：TypeScript 配置。
- `frontend/index.html`：Vite HTML 入口。
- `frontend/src/main.tsx`：React 挂载入口。
- `frontend/src/App.tsx`：兼容导出入口，转发到 `frontend/src/app/App.tsx`。
- `frontend/src/app/App.tsx`：主应用状态、任务视图、模拟结果、API 调用和页面编排。
- `frontend/src/types/scheduler.ts`：前端核心类型定义，对齐后端 Pydantic 模型。
- `frontend/src/api/client.ts`：通用 HTTP client。
- `frontend/src/api/schedulerApi.ts`：后端 API 调用封装，包含生成任务、求解、资源成本求解、导入、自然语言设置和保存工艺库。
- `frontend/src/domain/constants.ts`：资源模式、资源成本、默认资源映射和 UI 常量。
- `frontend/src/domain/labels.ts`：构件、工期算法、工程量来源、状态和诊断中文标签。
- `frontend/src/domain/logic.ts`：工艺逻辑表格行、上部结构规则统计、规则追踪和暂不生成任务说明。
- `frontend/src/domain/upperStructureLogic.ts`：上部结构逻辑规则定义与默认合并。
- `frontend/src/domain/resources.ts`：资源池、资源候选、成本和默认资源推断。
- `frontend/src/domain/productivity.ts`：工效单位、墩身节段工效和工效选项归一化。
- `frontend/src/domain/scenarioMutations.ts`：任务/构件工艺和工效覆盖更新。
- `frontend/src/domain/projectTree.ts`：项目树查找工具。
- `frontend/src/domain/milestones.ts`：里程碑状态和范围展示。
- `frontend/src/domain/scheduleDerived.ts`：求解状态派生展示。
- `frontend/src/features/layout/WorkspaceNavigation.tsx`：侧边导航和页签条。
- `frontend/src/features/process/ProcessTab.tsx`：工艺工效库页面。
- `frontend/src/features/logic/LogicTab.tsx`：工艺逻辑约束页面。
- `frontend/src/features/resources/ResourcesTab.tsx`：资源配置页面。
- `frontend/src/features/milestones/MilestonesTab.tsx`：里程碑页面。
- `frontend/src/features/assistant/GlobalProcessAssistant.tsx`：自然语言工艺设置助手。
- `frontend/src/components/common/PanelTitle.tsx`、`Metric.tsx`、`PredecessorPopover.tsx`：通用面板、指标和前置关系浮层。
- `frontend/src/styles.css`：全局样式。
- `frontend/src/vite-env.d.ts`：Vite 类型声明。

### 2.4 Netlify 文件

- `netlify/functions/api.mts`：Netlify 部署场景下的 TypeScript 演示 API。它复刻部分 Python 后端能力，包括默认场景、任务生成、简化求解、Excel 导入、自然语言工艺设置、最少资源、资源成本和方案对比。
- `netlify.toml`：指定 `npm --prefix frontend run build`、发布目录 `frontend/dist`、Functions 目录和 Node 版本。

Python 后端仍是本地工程化和测试验证的主要实现；Netlify Functions 主要用于前端部署演示。

### 2.5 需求文档

`docs/` 目录是项目需求和架构知识资产。由于该目录被 `.gitignore` 覆盖，新增或更新文档时需要显式检查目录内容：

- `docs/项目排程系统整体说明_v1.1.md`：系统总览、模块划分、数据输入输出、内部流转和调用关系。
- `docs/project-parameters-requirements.md`：项目参数/结构参数页面需求。
- `docs/施工工艺及工效库需求文档_v1.1.md`：施工工艺及工效库需求。
- `docs/工艺逻辑约束需求文档_v1.0.md`：工艺逻辑约束需求，包含工艺逻辑页面口径。
- `docs/任务视图页面需求文档_v1.0.md`：任务视图页面需求，包含求解前任务网络核验口径。

整理需求或写 PRD 时应先读取这些文档，再看代码。

### 2.6 项目技能

PRD 输出统一使用全局 `$write-prd`，不再维护项目内 PRD skill 分叉。由于 `skills/` 被 `.gitignore` 覆盖，若未来新增项目技能，需要显式检查目录内容。

当用户要求写、改、沉淀或完善需求文档时，应优先使用 `$write-prd`。默认走产品 PRD 模式；当用户明确要求算法、目标函数、约束规则、指标解释、CP-SAT 或排程算法交底时，由 `$write-prd` 切换到算法 / 规则交底模式。

全局技能中新增 `requirement-review`，用于需求评审、文档评审、方案评审和变更评审。用户提供初始需求文档并明确要“评审”时，应优先使用 `$requirement-review`，把用户文档放到当前项目 Demo、代码和已有文档中对照分析，先共同确认为什么改、改什么、怎么改，再输出可落地的变更说明文档。

需求评审、Demo 实现和 PRD 输出需要区分处理：

- 需求评审：使用 `$requirement-review`，默认不改代码、不直接生成 PRD，先输出评审结论、待确认项和变更说明。
- Demo 实现：进入代码实现流程，读取真实前后端、算法和测试路径，修改源码并运行合适验证。
- PRD 输出：使用全局 `$write-prd`，基于已确认的产品口径输出或更新 `docs/` 下的研发交底 PRD；明确算法 / 规则交底时使用同一 skill 的算法 / 规则模式。

### 2.7 本地运行产物边界

以下目录/文件通常不应纳入项目梳理，也不应提交：

- `.venv/`、`node_modules/`、`frontend/node_modules/`
- `.npm-cache/`、`.pip-cache/`、`.pytest_cache/`
- `.netlify/`、`.netlify-cli-runtime/`、`.edge-profile/`
- `logs/`、`*.log`
- `frontend/dist/`
- `__pycache__/`、`*.pyc`
- `.local.env`、`.env`、`*.local.env`

## 3. 核心业务对象

- 项目结构参数：`ProjectModel -> ProjectBridge -> WorkSection -> StructureModel -> ComponentModel`，表示项目、桥梁、工区/幅别、墩台和构件。
- 上部结构参数：`UpperStructureComponent` 表示跨号、支座范围、跨径、结构类型和连续梁配置，用于派生部分上部现浇任务。
- 工艺工效库：`ProcessTemplate` 和 `ProductivityOption` 维护“构件类型 -> 施工工艺 -> 工效分组 -> 默认资源”。
- 工艺逻辑：`LogicRule` 和 `UpperStructureLogicRule` 描述 FS/SS/FF/SF 前后置关系、滞后天数和候选前置回退策略。
- 资源池：`ResourcePool` 定义资源类型、数量、最大数量、资源模式、日历、启用状态和增量成本。
- 里程碑：`MilestoneConstraint` 表示合同节点、强控节点和内部节点，可作用于项目、桥梁、工区、结构物、构件类型或单个构件。
- 排程结果：`ScheduleResult` 包含任务起止日期、资源分配、里程碑结果、诊断、统计指标、连续性指标和目标函数拆解。

## 4. 业务模块

- 任务视图：导入或接入结构参数，生成求解前任务图，核验结构物、构件、工艺、工效、工程量、工期、资源候选和前置关系。生成任务视图不执行 CP-SAT。
- 工艺工效库：维护施工工艺、工效分组、默认工效、工效单位、标准节高和默认资源类型。
- 工艺逻辑：统一展示下部结构规则和桥梁上部规则，支持编辑逻辑关系和时间间隔，展示适用范围与暂不生成任务说明。
- 资源配置：维护资源池数量、最大数量、资源模式、日历、启用状态和成本参数。
- 里程碑：维护合同、强控、内部节点及软硬约束。
- 模拟结果：调用固定资源求最短工期、固定工期求最少资源、固定工期求最低资源成本、方案对比，并展示甘特图、资源分配、诊断和连续性指标。
- AI 操作助手：使用本地规则或 OpenAI-compatible/HTTP 适配器，从自然语言批量设置构件工艺。

## 5. 技术架构

### 5.1 前端

- 技术栈：React 19、Vite、TypeScript、lucide-react。
- 真实入口：`frontend/src/App.tsx -> frontend/src/app/App.tsx`。
- 样式：`frontend/src/styles.css`。
- 开发代理：`frontend/vite.config.ts` 将 `/api` 代理到 `http://127.0.0.1:8000`。
- 状态模型：前端维护同一个 `ScenarioInput`，各页面通过局部 mutation 更新它；影响任务、资源、工期或逻辑的配置变化后，应清空或标记旧任务图、求解结果和方案对比失效。

### 5.2 后端

- 技术栈：FastAPI、Pydantic、OR-Tools CP-SAT、openpyxl、psycopg。
- API 入口：`backend/app/main.py`。
- 领域模型：`backend/app/models.py`。
- 场景编排：`backend/app/scenario.py`。
- 求解器：`backend/app/solver.py`。
- 结构导入：`backend/app/bridge_import.py`。
- 自然语言设置：`backend/app/process_nl.py`。
- 持久化：`backend/app/process_repository.py`。

后端主要职责是校验输入、生成可求解任务网络、展开资源、构建 CP-SAT 模型、计算里程碑结果和返回诊断信息。

### 5.3 求解器

`backend/app/solver.py` 使用 OR-Tools CP-SAT 建模：

- 为每个任务建立开始、结束和区间变量。
- 根据 `PrecedenceLink` 添加 FS/SS/FF/SF 约束。
- 根据候选资源建立可选区间，并对每个命名资源添加 `NoOverlap`。
- 将软里程碑迟延转为目标函数罚分。
- 固定资源最短工期模式最小化总工期、软里程碑罚分和施工连续性惩罚。
- 固定工期最少资源模式使用资源池 `max_quantity` 作为上限，输出推荐资源数量。
- 固定工期资源成本模式按增量资源成本推荐低成本资源组合。

求解结果包含 `continuity_metrics`，用于评价同构件工艺拆分、跳墩、换幅、跨幅跳转和方向反转等施工连续性问题。

## 6. API 总览

- `GET /api/health`：健康检查。
- `GET /api/demo`：早期 demo 数据，兼容接口。
- `GET /api/demo-scenario`：返回完整默认 `ScenarioInput`，并尝试加载持久化工艺库。
- `GET /api/process-library`：获取标准化后的工艺工效库。
- `PUT /api/process-library`：保存工艺工效库到后端持久化存储。
- `POST /api/import-bridge-params`：multipart 上传 Excel、当前 `ScenarioInput` 和可选目标桥名，返回更新后的场景、Canonical Bridge JSON、质量检查和告警。
- `POST /api/import-local-bridge-params`：导入项目根目录下的本地 Excel 样例。
- `POST /api/apply-process-natural-language`：根据自然语言批量修改构件工艺。
- `POST /api/generate-wbs`：早期 WBS 生成，兼容接口。
- `POST /api/solve`：直接求解 `ScheduleInput`，兼容接口。
- `POST /api/generate-schedule-input`：将 `ScenarioInput` 转换为任务图和求解输入。
- `POST /api/solve-scenario`：固定资源数量求最短工期。
- `POST /api/solve-min-resources`：固定目标工期求最少资源。
- `POST /api/solve-resource-cost`：固定目标工期求最低资源成本组合。
- `POST /api/compare-scenarios`：对多个求解结果做方案对比。

## 7. 关键数据流

```text
默认场景 / Excel 导入 / 结构参数 API
  -> ScenarioInput.project
  -> 用户编辑工艺、工效、逻辑、资源、里程碑、管控级别
  -> POST /api/generate-schedule-input
  -> GeneratedScheduleInput / ScheduleInput
  -> POST /api/solve-scenario
     或 POST /api/solve-min-resources
     或 POST /api/solve-resource-cost
  -> ScheduleResult / ScenarioSolveResult
  -> 甘特图、资源分配、里程碑偏差、诊断、连续性指标、资源推荐
  -> POST /api/compare-scenarios 做方案对比
```

影响任务、资源、工期或逻辑的配置变化后，不应继续展示旧任务图或旧求解结果作为当前方案结果。

## 8. 开发与验证

### 8.1 安装依赖

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt --cache-dir .pip-cache
npm --prefix frontend install --cache .npm-cache
```

如果运行环境没有把 `npm` 加入 `PATH`，按 README 使用完整路径执行 npm 命令。

### 8.2 本地运行

推荐先构建前端，再由 FastAPI 同时托管页面和 API：

```powershell
npm --prefix frontend run build
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --app-dir backend
```

访问：

- 页面：`http://127.0.0.1:8000/`
- 健康检查：`http://127.0.0.1:8000/api/health`

需要让局域网同事临时访问时，不改默认脚本，仍先构建前端并由 FastAPI 单服务托管，只把后端监听地址改为 `0.0.0.0`：

```powershell
npm --prefix frontend run build
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --app-dir backend
```

同事应访问 `http://<本机IPv4>:8000/`，其中本机 IPv4 可通过 `ipconfig` 查看；`0.0.0.0` 只用于监听，不作为浏览器地址。若无法访问，优先检查同一局域网/VPN、Windows 防火墙入站规则和端口占用。

前后端分离开发：

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --app-dir backend --reload
npm --prefix frontend run dev
```

Vite 默认访问 `http://127.0.0.1:5173/`。

### 8.3 验证命令

```powershell
.\.venv\Scripts\python.exe -m pytest backend\tests -q
npm --prefix frontend run build
```

文档类改动通常不需要完整业务测试；至少应复读文档并运行：

```powershell
git diff --check -- <changed-files>
```

## 9. 常见修改路线

- 修改模型字段：同步检查 `backend/app/models.py`、`frontend/src/types/scheduler.ts`、`netlify/functions/api.mts`、前端 API 调用和相关测试。
- 修改排程逻辑：重点看 `backend/app/scenario.py`、`backend/app/solver.py`，并更新 `backend/tests/test_scheduler.py`。
- 修改 Excel 导入：重点看 `backend/app/bridge_import.py`、本体 JSON、`backend/app/services/bridge_import_service.py` 和 `backend/tests/test_bridge_import.py`。
- 修改工艺工效库：保持每个 `ProcessTemplate` 至少一个 `ProductivityOption`，且只有一个默认工效；同步检查前端 `ProcessTab`、`domain/productivity.ts` 和后端默认库。
- 修改工艺逻辑：同步检查 `bridge_schedule_logic_ontology.v1.json`、`backend/app/scenario.py`、`frontend/src/domain/logic.ts`、`LogicTab.tsx` 和前置关系追踪展示。
- 修改资源/成本：同步检查 `ResourcePool` 字段、`frontend/src/domain/resources.ts`、`ResourcesTab.tsx`、`solve_resource_cost_scenario` 和资源成本相关测试。
- 需求评审：用户明确“评审、审一下、方案评审、变更评审”时，优先使用全局 `$requirement-review`，先读用户初始文档，再扫描当前项目 `agent.md`、`README.md`、`docs/`、相关前后端代码和测试，输出“为什么改、改什么、怎么改、影响范围、验收标准”的变更说明。
- 修改需求文档或输出 PRD：使用全局 `$write-prd`，再读相关 `docs/` 文档和代码，避免把 demo 临时限制写成工程化产品目标。

## 10. 配置与安全

- `.local.env` 由 `backend/app/local_config.py` 启动时读取，禁止提交或写入真实值。
- Supabase 写入凭据只允许后端使用，浏览器端不应暴露。
- LLM/HTTP/OpenAI-compatible 适配器凭据只能通过后端 `.local.env` 或部署环境变量配置。
- README 和 `.local.env.example` 里的连接串和 API key 只能使用占位符。

常用变量：

- `SUPABASE_POSTGRES_SESSION_POOL_URL`
- `SUPABASE_POSTGRES_POOL_SIZE`
- `BRIDGE_IMPORT_LLM_PROVIDER`
- `BRIDGE_IMPORT_LLM_ENDPOINT`
- `BRIDGE_IMPORT_LLM_MODEL`
- `BRIDGE_IMPORT_LLM_API_KEY`
- `PROCESS_NL_LLM_PROVIDER`
- `PROCESS_NL_LLM_ENDPOINT`
- `PROCESS_NL_LLM_MODEL`
- `PROCESS_NL_LLM_API_KEY`
- `PROCESS_NL_LLM_TEMPERATURE`
- `PROCESS_NL_LLM_RESPONSE_FORMAT`

## 11. 协作注意事项

- 本仓库包含中文文档和中文业务术语，编辑文档时保持 UTF-8。
- 修改前先查看 `git status`；不要回滚、覆盖或格式化无关改动。
- 文档梳理时要区分源码事实、需求文档口径、demo 限制和实际工程目标。
- `docs/` 和 `skills/` 被 `.gitignore` 覆盖，但仍可能包含重要业务资产；需要读取时用显式路径。
- 变更业务逻辑时，优先补测试；变更前端展示时，优先检查类型、状态失效和移动端/宽屏文本可读性。
- `bridge_schedule_logic_ontology.v1.json` 可由产品或业务人员维护默认工艺逻辑，但新增构件类型时必须同步后端模型、前端标签、工艺库、Netlify 演示 API 和测试。

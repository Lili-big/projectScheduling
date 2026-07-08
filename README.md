# 桥梁施工自动排程 Demo

## 本地启动命令

### 首次安装依赖

在项目根目录执行：

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt --cache-dir .pip-cache
npm.cmd install --cache .npm-cache
```

如果本机没有 Python 3.12，可先使用 `py -3 -m venv .venv` 创建虚拟环境；当前 Dockerfile 使用 Python 3.12，项目最低 Python 版本未在配置文件中声明，需确认。

如果 `npm.cmd` 不在 `PATH` 中，可使用完整路径：

```powershell
& 'C:\Program Files\nodejs\npm.cmd' install --cache .npm-cache
```

### 演示模式：单服务启动

适用于演示、验收或给同事临时查看。前端先构建为静态文件，再由 FastAPI 同时提供页面和 API。

```powershell
npm.cmd run build
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --app-dir backend
```

访问地址：

- 页面：`http://127.0.0.1:8000/`
- 健康检查：`http://127.0.0.1:8000/api/health`

修改前端代码后需要重新执行 `npm.cmd run build`；修改后端代码后需要重启后端服务并重新求解。

### 开发模式：前后端分离启动

适用于频繁修改前端、后端算法或接口联调。需要打开两个 PowerShell 窗口。

窗口 A 启动后端：

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --app-dir backend --reload
```

窗口 B 启动前端：

```powershell
npm.cmd run frontend:dev
```

访问地址：

- 页面：`http://127.0.0.1:5173/`
- 后端健康检查：`http://127.0.0.1:8000/api/health`

开发模式下，`frontend/vite.config.ts` 会把 `/api` 代理到 `http://127.0.0.1:8000`。不要用 `http://127.0.0.1:8000/` 检查前端热更新效果；`8000` 读取的是上一次构建后的静态文件，开发模式看 `5173`。

### 局域网访问

临时让同一局域网内同事访问时，推荐仍使用单服务模式：

```powershell
npm.cmd run build
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --app-dir backend
```

启动后用 `ipconfig` 查看本机 IPv4 地址，例如 `192.168.1.23`，同事访问 `http://192.168.1.23:8000/`。

`0.0.0.0` 是服务监听地址，不是浏览器访问地址。如果无法访问，检查是否在同一局域网或 VPN，并确认 Windows 防火墙允许当前 Python/uvicorn 服务或 `8000` 端口入站。

### 停止服务

前台启动的服务可在对应 PowerShell 窗口按 `Ctrl+C` 停止。

如果端口被旧进程占用，先查询 PID：

```powershell
Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue |
  Select-Object LocalAddress, LocalPort, OwningProcess
```

再结束进程：

```powershell
Stop-Process -Id <PID> -Force
```

开发模式下如 `5173` 被占用，可用同样方式查询并停止。

## 项目简介

本项目是桥梁施工自动排程 Demo，用于把项目结构参数、施工工艺及工效、工艺逻辑、资源配置、里程碑目标和求解策略统一建模，并通过 OR-Tools CP-SAT 输出施工计划、资源分配、里程碑偏差、资源建议、连续性指标和方案对比结果。

当前实现以桥梁施工排程验证为主，前端提供可操作的配置与结果页面，后端负责默认场景、结构参数导入、任务生成、CP-SAT 求解、本地配置读写和演示静态页面托管。详细算法口径见 `docs/排程算法当前实现交底文档_v1.0.md`。

## 核心功能

- 项目结构建模：使用 `ProjectModel -> ProjectBridge -> WorkSection -> StructureModel -> ComponentModel` 表达项目、桥梁、工区、墩台和构件。
- 结构参数导入：支持 `.xlsx`、`.xlsm` 桥梁结构参数表，结合本体配置生成项目结构参数、质量检查和告警。
- 工艺工效库：维护构件类型、施工工艺、工程量来源、工期算法、工效值、默认资源类型。
- 工艺逻辑：维护下部结构同结构内逻辑、跨结构顺序逻辑，以及现浇箱梁、现浇连续梁相关上部结构逻辑。
- 任务视图：从 `ScenarioInput` 生成求解前任务图，输出任务、前后置、资源候选和诊断。
- 资源配置：维护受限 / 不受限资源池、当前数量、最大数量、启用状态、成本属性和资源日历。
- 里程碑配置：维护桥梁、工点或项目层级的关键目标日期，并参与结果评价。
- 模拟求解：支持固定资源最短工期、固定工期最少资源、资源成本优化和方案对比。
- AI 参数输入助手：支持文本和资料文件提取工艺、资源、里程碑参数建议，经人工审阅后应用。
- 自然语言工艺设置：支持用自然语言批量调整构件工艺，默认先使用本地解析，可选接入外部模型。

## 适用场景

- 产品和研发共同验证桥梁施工排程 Demo 的功能闭环。
- 基于结构参数、资源和里程碑快速生成可解释的施工计划。
- 对比不同资源配置、工艺配置或工期目标下的排程结果。
- 作为需求评审、研发交底、算法说明和 Spec Kit 规格化开发的项目样例。

不适合作为正式生产排程系统直接使用；生产级用户、权限、审计、持久化、项目级配置隔离和正式数据接入仍需确认。

## 技术栈

- 后端：Python、FastAPI、Pydantic、OR-Tools CP-SAT、openpyxl、pytest。
- 前端：React 19、TypeScript、Vite 6、lucide-react。
- 本地运行：PowerShell、Python 虚拟环境、npm workspace。
- 部署配置：Netlify 静态前端、Docker FastAPI 后端。

## 目录结构

```text
.
├── AGENTS.md                 # 项目工作分流与治理规则
├── agent.md                  # 项目 Agent 工作手册和项目知识索引
├── README.md                 # 项目入口说明、启动、配置、测试和部署
├── requirements.txt          # 后端 Python 依赖
├── package.json              # 前端 npm workspace 根配置
├── Dockerfile                # FastAPI 后端容器构建配置
├── netlify.toml              # Netlify 前端构建与发布配置
├── backend/
│   ├── app/                  # FastAPI、模型、任务生成、求解器、导入和本地配置
│   └── tests/                # 后端测试
├── frontend/
│   ├── src/                  # React 页面、领域逻辑、API 客户端和类型
│   └── vite.config.ts        # Vite 开发代理配置
├── docs/                     # PRD、算法交底、页面需求和验证说明
├── specs/                    # Spec Kit 规格化开发产物
├── .agents/                  # 项目内 Spec Kit / Agent 技能
├── .specify/                 # Spec Kit 配置
└── .local-data/              # 本地运行生成的配置数据，已被 git 忽略
```

根目录下的 `.xlsx` 文件会被 `backend/app/project_structure_params.py` 作为本地结构参数来源之一读取。当前仓库中可见示例文件为 `渠溪河特大桥结构设计表.xlsx`。

## 环境要求

- Windows PowerShell：当前命令示例以 Windows 为主。
- Python：Dockerfile 使用 `python:3.12-slim`；本地最低版本未在项目配置中声明，需确认。
- Node.js / npm：Netlify 构建环境声明 `NODE_VERSION = "22"`；Vite 6 依赖要求 Node 18+，`@vitejs/plugin-react` 当前依赖要求 `^20.19.0 || >=22.12.0`。
- 网络：首次安装 Python 和 npm 依赖需要访问包源；项目运行本身不要求公网，除非配置外部 AI / LLM 适配器。

## 安装依赖

后端依赖：

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt --cache-dir .pip-cache
```

前端依赖：

```powershell
npm.cmd install --cache .npm-cache
```

常用 npm 脚本：

```powershell
npm.cmd run build
npm.cmd run frontend:dev
npm.cmd run frontend:preview
```

## 配置说明

### `.local.env`

项目根目录支持 `.local.env`，后端启动时会自动读取。该文件已加入 `.gitignore`，不要提交真实密钥。

首次配置可复制模板：

```powershell
Copy-Item .local.env.example .local.env
```

当前模板包含以下配置组：

| 配置组 | 作用 |
| --- | --- |
| `BRIDGE_IMPORT_LLM_*` | 桥梁 Excel 导入适配器。默认 `local`，可选接入 HTTP 适配器。 |
| `PROCESS_NL_LLM_*` | 自然语言工艺设置适配器。默认 `local`，可选接入 OpenAI-compatible 或自定义 HTTP 适配器。 |
| `SUPABASE_POSTGRES_*` | 后端服务端连接 Supabase PostgreSQL 的配置；当前 README 未在代码路径中确认其生产使用方式，需确认。 |

代码中还支持 `AI_PARAMETER_ASSISTANT_*` 作为 AI 参数输入助手的外部模型配置，但 `.local.env.example` 当前未提供模板项，需确认是否补充。

### 本地配置数据

后端读取 `/api/demo-scenario` 时的配置合并顺序：

1. `backend/app/scenario_data.py` 生成默认场景。
2. 叠加 `backend/app/default_scenario_config.json` 中随代码发布的默认配置。
3. 叠加 `.local-data/scheduler-config.json` 中本地保存的配置。

`.local-data/` 已被 git 忽略，用于本地模拟配置库；浏览器刷新或本地服务重启后仍会读取。需要随代码发布的默认值应更新到 `backend/app/default_scenario_config.json`。

当前本地配置可保存：

- `process_library`：工艺工效库。
- `logic_rules`：下部结构工艺逻辑。
- `upper_structure_logic_rules`：上部结构逻辑。
- `resource_pools`：资源配置。
- `milestones`：里程碑配置。

项目结构参数另存为 `.local-data/project-structure-params.json`。如果该文件不存在，后端会尝试读取根目录第一个非临时 `.xlsx` 文件；仍未找到时使用默认示例项目。

### 本体配置

结构参数导入和工艺逻辑依赖本地本体 JSON：

- `backend/app/ontology/bridge_structure_ontology.v1.json`
- `backend/app/ontology/bridge_schedule_logic_ontology.v1.json`

修改本体会影响结构识别、任务生成和前后置规则，应结合测试验证。

## 主要 API

| API | 作用 |
| --- | --- |
| `GET /api/health` | 健康检查 |
| `GET /api/demo-scenario` | 读取合并后的默认排程场景 |
| `GET /api/process-library` | 读取工艺工效库 |
| `PUT /api/process-library` | 保存工艺工效库 |
| `PUT /api/local-scenario-config` | 保存工艺、逻辑、资源、里程碑等本地配置 |
| `GET /api/project-structure-params` | 读取项目结构参数 |
| `PUT /api/project-structure-params` | 保存项目结构参数 |
| `POST /api/apply-project-structure-params` | 将项目结构参数应用到当前场景 |
| `POST /api/generate-schedule-input` | 由场景生成任务图和求解输入 |
| `POST /api/solve-scenario` | 固定资源最短工期求解 |
| `POST /api/solve-min-resources` | 固定工期最少资源求解 |
| `POST /api/solve-resource-cost` | 固定工期资源成本优化 |
| `POST /api/compare-scenarios` | 多方案结果对比 |
| `POST /api/apply-process-natural-language` | 自然语言工艺设置 |
| `POST /api/ai-parameter-assistant/parse` | AI 参数输入助手解析资料 |
| `POST /api/ai-parameter-assistant/apply` | 应用 AI 参数建议 |
| `POST /api/import-bridge-params` | 上传 Excel 并导入结构参数 |
| `POST /api/import-local-bridge-params` | 使用本地结构参数来源导入 |

兼容接口仍保留：`GET /api/demo`、`POST /api/generate-wbs`、`POST /api/solve`。

## 常用命令

```powershell
# 后端健康检查
Invoke-RestMethod http://127.0.0.1:8000/api/health

# 后端测试
.\.venv\Scripts\python.exe -m pytest backend\tests -q

# 前端构建
npm.cmd run build

# 前端开发服务
npm.cmd run frontend:dev

# 前端预览构建产物
npm.cmd run frontend:preview
```

## 测试方式

后端测试：

```powershell
.\.venv\Scripts\python.exe -m pytest backend\tests -q
```

前端类型检查和构建：

```powershell
npm.cmd run build
```

文档或配置改动至少应运行相关轻量验证。算法、资源、工期、CP-SAT、前后端共享字段或结果口径变更，应补充或运行对应后端测试，并说明未覆盖场景。

## 部署说明

当前仓库保留“Netlify 静态前端 + Docker FastAPI 后端”的拆分部署配置。

### Netlify 前端

`netlify.toml` 当前配置：

- 构建命令：`npm run build`
- 发布目录：`frontend/dist`
- Node 版本：`22`
- 单页应用重定向：`/* -> /index.html`

前端 API 客户端会读取 `VITE_API_BASE_URL`。生产环境部署到 Netlify 且未配置该变量时，前端会主动报错，提示无法连接完整 FastAPI / OR-Tools 后端。

示例：

```env
VITE_API_BASE_URL=https://your-backend.example.com
```

### Docker 后端

`Dockerfile` 使用 `python:3.12-slim`，安装 `requirements.txt`，复制 `backend/` 和根目录 `.xlsx` 文件，启动命令为：

```bash
uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --app-dir backend
```

后端跨域配置：

| 环境变量 | 作用 |
| --- | --- |
| `SCHEDULER_CORS_ORIGINS` | 逗号分隔的允许来源，建议包含 Netlify 生产域名。 |
| `SCHEDULER_CORS_ORIGIN_REGEX` | 可选，默认允许 `https://<deploy-id>--project-scheduling-lili-big.netlify.app` 形式的 Netlify 预览域名。 |

生产后端实际托管平台、正式域名、持久化存储和备份方式未在仓库配置中完整确认，需确认。

### Netlify Functions

`netlify/demo-functions/api.mts` 保留为演示 / 参考 API。当前 `netlify.toml` 未配置 Functions 发布目录，完整排程能力以 FastAPI 后端为准。

## 开发规范

- 进入项目后先看 `AGENTS.md` 判断工作流，再结合 `agent.md`、`README.md` 和相关 `docs/` 理解项目事实。
- 涉及算法、排程、资源、工期、CP-SAT、前后端联动或中大型改动时，按 `AGENTS.md` 进入 Spec Kit。
- 不把 Demo、Mock、兼容接口或本地 `.local-data` 写成正式产品规则。
- 不提交 `.local.env`、真实密钥、个人凭据、`.local-data/`、缓存目录或构建产物。
- 优先复用现有模型、服务、组件、接口和测试结构，避免无关重构。
- 修改共享字段或结果口径时，同步检查 `backend/app/models.py`、`frontend/src/types/scheduler.ts`、相关 API 调用和测试。
- 文档更新应基于当前代码、配置和 docs 事实；不确定内容写入“需确认”，不要自行补全为确定结论。

## 主要文档

- `docs/项目排程系统整体说明_v1.1.md`：系统定位、模块和数据模型总览。
- `docs/排程算法当前实现交底文档_v1.0.md`：当前算法实现、目标函数、约束、资源规则和诊断口径。
- `docs/模拟求解-MVP页面需求文档_v1.2.md`：模拟求解 MVP 页面需求。
- `docs/任务视图页面需求文档_v1.0.md`：任务视图页面需求。
- `docs/资源配置页面需求文档_v1.0.md`：资源配置页面需求。
- `docs/工艺逻辑约束需求文档_v1.1.md`：工艺逻辑约束需求。
- `docs/施工工艺及工效库需求文档_v1.1.md`：施工工艺及工效库需求。
- `docs/AI参数输入助手验证说明.md`：AI 参数输入助手验证说明。

## 常见问题

### 页面打不开或接口请求失败

先确认后端是否启动：

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/health
```

开发模式请访问 `http://127.0.0.1:5173/`，演示模式请访问 `http://127.0.0.1:8000/`。

### 修改前端后页面没有变化

如果使用演示模式，需要重新执行：

```powershell
npm.cmd run build
```

如果使用开发模式，访问 `5173`，不要访问 `8000` 检查热更新。

### Netlify 页面提示无法连接后端

确认 Netlify 环境变量 `VITE_API_BASE_URL` 已设置为 FastAPI 后端公开 HTTPS 地址，并确认后端 CORS 允许该前端域名。

### 本地保存的工艺、逻辑或资源配置没有同步到云端

`.local-data/scheduler-config.json` 是本地模拟配置库，已被 git 忽略。需要随代码发布的默认配置应更新到 `backend/app/default_scenario_config.json` 并随 Git 发布。

### Excel 导入失败

确认文件后缀为 `.xlsx` 或 `.xlsm`，不要上传 Excel 临时锁文件 `~$*.xlsx`。如使用外部导入适配器，检查 `BRIDGE_IMPORT_LLM_*` 配置。

### AI 参数助手无法调用外部模型

代码支持 `AI_PARAMETER_ASSISTANT_PROVIDER`、`AI_PARAMETER_ASSISTANT_ENDPOINT`、`AI_PARAMETER_ASSISTANT_MODEL`、`AI_PARAMETER_ASSISTANT_API_KEY`、`AI_PARAMETER_ASSISTANT_RESPONSE_FORMAT`、`AI_PARAMETER_ASSISTANT_TIMEOUT_SECONDS`。当前 `.local.env.example` 未包含该配置组，需确认是否补充模板。

## 待确认事项

- 本地运行支持的最低 Python 版本。当前 Dockerfile 使用 Python 3.12，但 `requirements.txt` 未声明最低版本。
- 本地运行推荐的 Node.js 版本。Netlify 使用 Node 22，Vite 6 依赖 Node 18+，`@vitejs/plugin-react` 当前依赖要求 `^20.19.0 || >=22.12.0`。
- 生产后端的正式托管平台、域名、持久化存储、备份和权限策略。
- `SUPABASE_POSTGRES_*` 在当前项目中的实际启用范围和数据写入边界。
- 是否将 `AI_PARAMETER_ASSISTANT_*` 补充到 `.local.env.example`。
- 是否需要为云端默认配置建立明确发布流程，避免本地 `.local-data` 与代码内置默认值混淆。

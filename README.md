# 桥梁下部结构 CP-SAT 自动排程 Demo

这个 demo 用 `FastAPI + React + OR-Tools CP-SAT` 模拟桥梁下部结构自动排程。当前版本已经从单一 WBS 原型升级为“场景化模拟”：项目桥梁参数、施工工艺及工效库、工艺逻辑、资源配置和关键里程碑分开建模，再统一生成求解输入。

## 当前能力

- 项目模型：`ProjectModel -> Bridge -> WorkSection -> Structure -> Component`。
- 桥梁参数导入：支持上传 `.xlsx/.xlsm` 桥梁结构参数表，先标准化合并表头和合并单元格，再按本体配置理解左右幅、墩台、构件尺寸并覆盖项目参数。
- 工艺库：桩基支持旋挖钻、冲击钻、人工挖孔，其他构件支持承台、墩柱、盖梁、桥台模板工效。
- 逻辑库：支持 FS/SS、滞后天数、候选前置回退，并预留跨墩台顺序规则。
- 资源约束：资源池按数量展开为命名资源，CP-SAT 对每个命名资源做 `NoOverlap`。
- 里程碑：硬节点作为 CP-SAT 日期约束，软节点转为迟延变量并进入加权目标。
- 前端页签：项目参数、工艺工效库、工艺逻辑、资源配置、里程碑、模拟结果。


## 后端接口

- `GET /api/demo-scenario`：返回完整默认模拟场景。
- `POST /api/generate-schedule-input`：把场景配置转换为任务图和求解输入。
- `POST /api/solve-scenario`：执行 CP-SAT 求解，返回排程、资源分配、里程碑结果和诊断。
- `POST /api/compare-scenarios`：输入多个场景结果，返回对比摘要。
- `POST /api/import-bridge-params`：multipart 上传 Excel、当前 `ScenarioInput` 和可选目标桥名，返回覆盖项目桥梁参数后的场景、Canonical Bridge JSON、质量检查和告警。
- 兼容接口仍保留：`/api/demo`、`/api/generate-wbs`、`/api/solve`。

## 本地运行

项目包含两个部分：

- 后端：`FastAPI + OR-Tools CP-SAT`，默认监听 `127.0.0.1:8000`。
- 前端：`React + Vite`，构建产物在 `frontend/dist`，构建后由后端同一个服务托管。

### 1. 安装依赖

如果 `.venv` 不存在，先创建 Python 虚拟环境：

```powershell
py -3 -m venv .venv
```

第一次运行或依赖变化后执行：

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt --cache-dir .pip-cache
cd frontend
npm install --cache ..\.npm-cache
cd ..
```

如果当前机器没有把 `npm` 加到 `PATH`，把相关命令写成完整路径，例如：

```powershell
& 'C:\Program Files\nodejs\npm.cmd' install --cache ..\.npm-cache
& 'C:\Program Files\nodejs\npm.cmd' run build
& 'C:\Program Files\nodejs\npm.cmd' run dev
```

### 2. 演示模式：构建前端后启动单个后端服务

这种方式最接近最终部署形态，适合演示、验收或给同事临时查看：先构建前端，再由 FastAPI 同时提供页面和接口。

```powershell
cd frontend
npm.cmd run build
cd ..
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --app-dir backend
```

启动成功后访问：

- 页面：`http://127.0.0.1:8000/`
- 健康检查：`http://127.0.0.1:8000/api/health`

演示模式下，前端代码已经被打包到 `frontend/dist`。如果修改了前端代码，需要重新执行 `npm.cmd run build` 并刷新页面；如果修改了后端 Python 代码，需要重启后端服务后重新求解。

如果需要让同一局域网内的同事访问，仍推荐使用单个后端服务托管前端和 API，只把监听地址改为 `0.0.0.0`：

```powershell
cd frontend
npm.cmd run build
cd ..
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --app-dir backend
```

启动后先用 `ipconfig` 查看当前 Wi-Fi 或以太网的 IPv4 地址，例如 `192.168.1.23`。同事访问：

- 页面：`http://192.168.1.23:8000/`
- 健康检查：`http://192.168.1.23:8000/api/health`

`0.0.0.0` 只是服务监听地址，不是浏览器访问地址。如果同事打不开页面，先确认双方在同一局域网或同一 VPN，并在 Windows 防火墙中允许当前 Python/uvicorn 服务或 `8000` 端口入站。

如果 `8000` 被占用，可以换一个端口，例如：

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8002 --app-dir backend
```

此时访问 `http://127.0.0.1:8002/`。

### 3. 开发模式：后端和前端分别启动，支持自动更新

需要频繁修改前端、后端算法或联调接口时，推荐使用开发模式。开发模式需要开两个 PowerShell 窗口。

窗口 A 启动后端：

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --app-dir backend --reload
```

窗口 B 启动 Vite 前端：

```powershell
cd frontend
npm.cmd run dev
```

开发模式下访问：

- 页面：`http://127.0.0.1:5173/`
- 后端健康检查：`http://127.0.0.1:8000/api/health`

前端的 `/api` 请求会通过 `frontend/vite.config.ts` 代理到 `http://127.0.0.1:8000`。

开发模式的更新规则：

- 修改前端 `frontend/src/` 下的代码后，Vite 会自动热更新；多数情况下页面会自己更新，如果没有变化，刷新 `http://127.0.0.1:5173/` 即可看到新效果。
- 修改后端 Python 代码后，`--reload` 会自动重载后端服务；如果是算法逻辑变化，需要在页面上重新点击求解，已有求解结果不会自动重算。
- 不要用 `http://127.0.0.1:8000/` 检查前端热更新效果；`8000` 在演示模式下读取的是上一次构建后的静态文件，开发模式请看 `5173`。

## 云端部署

当前生产部署采用“Netlify 静态前端 + Docker FastAPI 后端”的拆分形态：

- Netlify 绑定本仓库 `main` 分支后，从根目录执行 `npm run build`，发布 `frontend/dist`。
- Netlify 项目环境变量需要设置 `VITE_API_BASE_URL`，值为 Docker 后端的公开 HTTPS 地址，例如 `https://your-backend.example.com`。
- 完整排程能力由 Docker 后端提供，包含 FastAPI、OR-Tools CP-SAT、Excel 导入和本地规则解析。
- 后端镜像内置 `backend/app/default_scenario_config.json` 作为随代码发布的默认配置，云端打开页面时会先读取这份默认资源、工艺和逻辑配置。
- `netlify/demo-functions/api.mts` 只保留为早期演示 API 参考，不会作为生产 `/api` 部署。

Docker 后端可在支持 Docker 的云服务中绑定同一个 Git 仓库自动部署。构建入口使用仓库根目录的 `Dockerfile`，运行命令已在镜像中定义为：

```bash
uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --app-dir backend
```

后端跨域配置通过环境变量控制：

- `SCHEDULER_CORS_ORIGINS`：逗号分隔的允许来源，建议包含 Netlify 生产域名，例如 `https://project-scheduling-lili-big.netlify.app`。
- `SCHEDULER_CORS_ORIGIN_REGEX`：可选，默认允许 `https://<deploy-id>--project-scheduling-lili-big.netlify.app` 形式的 Netlify 预览域名。

第一版云端部署不配置持久化存储，工艺库、资源配置、项目参数等保存接口写入的 `.local-data` 内容可能在实例重启或重新部署后丢失；需要长期固化的默认值应更新到 `backend/app/default_scenario_config.json` 并随 Git 发布。

## 关闭服务

### 常规关闭

如果服务是在当前 PowerShell 窗口前台启动的，按 `Ctrl+C` 即可停止：

- 单服务模式：在运行 `uvicorn` 的窗口按 `Ctrl+C`。
- 开发模式：分别在后端窗口和前端 Vite 窗口按 `Ctrl+C`。

### 端口被旧进程占用时强制关闭

先查询端口对应的进程：

```powershell
Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue |
  Select-Object LocalAddress, LocalPort, OwningProcess
```

再结束对应进程，把 `<PID>` 替换为上一步查到的 `OwningProcess`：

```powershell
Stop-Process -Id <PID> -Force
```

开发模式下如果 `5173` 也被占用，同样查询并关闭：

```powershell
Get-NetTCPConnection -LocalPort 5173 -State Listen -ErrorAction SilentlyContinue |
  Select-Object LocalAddress, LocalPort, OwningProcess

Stop-Process -Id <PID> -Force
```

也可以一次性清理本项目常用端口：

```powershell
foreach ($port in 8000, 8002, 5173) {
  Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue |
    ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }
}
```

## 验证

```powershell
.\.venv\Scripts\python.exe -m pytest backend\tests -q
cd frontend
npm run build
```

项目根目录支持本地配置文件 `.local.env`，后端启动时会自动读取。该文件已加入 `.gitignore`，不会随 git 推送。首次配置时可以复制模板：

```powershell
Copy-Item .local.env.example .local.env
```

桥梁 Excel 导入默认使用本地本体适配器。需要接外部 AI 服务时，在 `.local.env` 中配置：

```env
BRIDGE_IMPORT_LLM_PROVIDER=http
BRIDGE_IMPORT_LLM_ENDPOINT=https://your-adapter.example.com/bridge-import
BRIDGE_IMPORT_LLM_MODEL=your-model
BRIDGE_IMPORT_LLM_API_KEY=your-api-key
```

项目参数页“工艺快速设置”默认先尝试本地解析。需要直接调用公网模型时，推荐使用 OpenAI-compatible 配置：

```env
PROCESS_NL_LLM_PROVIDER=openai_compatible
PROCESS_NL_LLM_ENDPOINT=https://your-provider.example.com/v1/chat/completions
PROCESS_NL_LLM_MODEL=your-model
PROCESS_NL_LLM_API_KEY=your-api-key
PROCESS_NL_LLM_TEMPERATURE=0
PROCESS_NL_LLM_RESPONSE_FORMAT=json_object
```

常见兼容接口只需要把 `PROCESS_NL_LLM_ENDPOINT`、`PROCESS_NL_LLM_MODEL`、`PROCESS_NL_LLM_API_KEY` 换成供应商提供的值即可。`PROCESS_NL_LLM_PROVIDER` 也可以写成 `deepseek`、`qwen`、`siliconflow`，内部都会按 Chat Completions 格式调用。

如果你的公网模型不支持 `response_format`，可以关闭强制 JSON：

```env
PROCESS_NL_LLM_RESPONSE_FORMAT=none
```

如果你仍想接一个自定义中间适配器，可以使用：

```env
PROCESS_NL_LLM_PROVIDER=http
PROCESS_NL_LLM_ENDPOINT=https://your-adapter.example.com/process-intent
PROCESS_NL_LLM_MODEL=your-model
PROCESS_NL_LLM_API_KEY=your-api-key
```

适配器返回 JSON 即可，例如：

```json
{
  "intents": [
    {
      "component_type": "pile",
      "process_method_id": "manual_pile",
      "process_name": "人工挖孔",
      "sides": ["left"],
      "support_nos": ["3#墩", "4#墩"],
      "action": "指定墩桩基工艺"
    }
  ],
  "warnings": []
}
```

服务启动后也可以快速检查后端是否可用：

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/health
```
## 本地配置模拟

后端启动 `/api/demo-scenario` 时会先构造默认场景，再叠加 `backend/app/default_scenario_config.json` 中随代码发布的默认配置，最后叠加 `.local-data/scheduler-config.json` 中保存的本地配置。`.local-data` 文件用于临时模拟配置库，不随 git 提交。

当前保存的配置范围包括：

- `process_library`：工艺工效库。
- `logic_rules`：下部结构工艺逻辑。
- `upper_structure_logic_rules`：上部结构关联逻辑。
- `resource_pools`：资源配置。

前端“工艺工效库”“工艺逻辑”“资源配置”页签均使用显式保存按钮。保存会调用后端本地配置接口并写入上述 JSON 文件；刷新浏览器或重启本地服务后仍会读取该配置。

相关接口：

- `GET /api/process-library`：读取本地叠加后的工艺工效库。
- `PUT /api/process-library`：仅保存工艺工效库。
- `PUT /api/local-scenario-config`：一次保存工艺工效库、工艺逻辑和资源配置。

## 本地本体配置

工艺逻辑规则由本地 JSON 维护，文件路径：

```text
backend/app/ontology/bridge_schedule_logic_ontology.v1.json
```

产品经理可直接维护其中的 `logic_rules`：

- `id`：规则稳定编号，供系统引用。
- `scope`：`same_structure` 表示同一墩台内约束，`structure_sequence` 表示跨墩台顺序约束。
- `structure_type`：`pier` 表示桥墩，`abutment` 表示桥台，`null` 表示都适用。
- `to_component`：当前/后续构件类型，例如 `cap`、`pier_body`、`abutment_body`。
- `predecessor_candidates`：候选前置构件类型，按数组顺序表达优先级。
- `predecessor_strategy`：`all` 表示候选前置全部满足，`first_available` 表示按顺序优先回退。
- `relationship`：`FS` 表示前置完成后开始，`SS` 表示前置开始后开始。
- `lag_days`：逻辑间隔天数。
- `note`：页面展示和诊断使用的中文说明。

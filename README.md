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

## 需求文档

- [项目排程系统整体说明](docs/project-scheduling-system-overview.md)：说明系统模块划分、数据输入输出、内部数据流转和后端调用关系。
- [项目参数页面需求文档](docs/project-parameters-requirements.md)：说明项目参数页在实际工程中的页面定位、主要功能、数据来源、接口规则和验收标准。
- [工艺工效库页面需求文档](docs/process-productivity-library-requirements.md)：说明工艺工效库页的历史数据升级、工效分组、桩基工效单位和接口保存规则。

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

### 2. 推荐启动方式：构建前端后启动单个后端服务

这种方式最接近最终部署形态：先构建前端，再由 FastAPI 同时提供页面和接口。

```powershell
cd frontend
npm run build
cd ..
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --app-dir backend
```

启动成功后访问：

- 页面：`http://127.0.0.1:8000/`
- 健康检查：`http://127.0.0.1:8000/api/health`

如果 `8000` 被占用，可以换一个端口，例如：

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8002 --app-dir backend
```

此时访问 `http://127.0.0.1:8002/`。

### 3. 开发模式：后端和前端分别启动

需要频繁改前端时，可以开两个 PowerShell 窗口。

窗口 A 启动后端：

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --app-dir backend --reload
```

窗口 B 启动 Vite 前端：

```powershell
cd frontend
npm run dev
```

开发模式下访问 `http://127.0.0.1:5173/`。前端的 `/api` 请求会通过 `frontend/vite.config.ts` 代理到 `http://127.0.0.1:8000`。

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
## Supabase 工艺关系表

后端启动 `/api/demo-scenario` 时会先构造默认场景，再从 Supabase `public.process_relationships` 读取工艺工效库并覆盖 `scenario.process_library`。前端“工艺工效库”页签点击“保存到 Supabase”时，会调用后端 `PUT /api/process-library`，由后端通过 PostgreSQL session pool 写入，不在浏览器端暴露 Supabase 写入凭据。

需要在 `.local.env` 配置 Supabase Database 的 session pooler 连接串：

```env
SUPABASE_POSTGRES_SESSION_POOL_URL=postgresql://postgres.PROJECT_REF:PASSWORD@aws-0-region.pooler.supabase.com:5432/postgres?sslmode=require
SUPABASE_POSTGRES_POOL_SIZE=5
```

已创建的表：`public.process_relationships`。一行对应一个工艺模板，`productivity_options` 和 `applicability` 使用 `jsonb` 存储，以保持和前端 `ProcessTemplate` 数据结构一致。

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

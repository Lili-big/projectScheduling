# 运行与部署边界

## 本地开发

后端：

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --app-dir 04-demo/backend --reload
```

前端：

```powershell
npm.cmd run frontend:dev -- --port 5174 --strictPort
```

前后端命令须在两个终端执行。上述开发页面为 `127.0.0.1:5174`，Vite 将 `/api` 代理到 `127.0.0.1:8000`。指定端口被占用时直接报错；省略端口参数则默认从5173开始寻找可用端口，以启动日志为准。根脚本将 `--` 后的参数继续转发给前端工作区，避免端口被当成项目目录。前端请求超时为90秒。

前台运行时日志直接留在当前终端。后台运行需要重定向时使用 `04-demo/runtime/start_logged_process.ps1`，stdout/stderr 统一进入 `.local-data/logs/<启动时间>/`；仓库根目录不作为运行日志目录。

## 单服务演示

```powershell
npm.cmd run build
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --app-dir 04-demo/backend
```

FastAPI 在检测到 `04-demo/frontend/dist` 后挂载 `/assets` 并提供 SPA 回退。修改前端后必须重新构建。

## Docker

`Dockerfile` 基于 Python 3.12，安装根 `requirements.txt`，从 `04-demo/backend/` 和 `04-demo/examples/` 复制容器内后端与样例，并启动 `app.main:app`。容器没有构建 React 前端，因此当前镜像主要保证 FastAPI API 和样例输入可用。

## Netlify

`netlify.toml` 执行根 `npm run build` 并发布 `04-demo/frontend/dist`，所有前端路由回退到 `index.html`。生产页面必须配置 `VITE_API_BASE_URL` 指向独立部署的完整 FastAPI/OR-Tools 后端，否则前端会主动报错。

`04-demo/tools/demo-api-mirror/api.mts` 是参考 API 镜像；当前 `netlify.toml` 未配置 Functions 目录，它不是正式后端。完整接口以运行服务的 `/openapi.json` 和后端架构基线为准。

## 配置和数据

- 根 `.local.env` 由后端启动加载，真实密钥不得提交。
- `SCHEDULER_CORS_ORIGINS` 和 `SCHEDULER_CORS_ORIGIN_REGEX` 控制后端跨域。
- `VITE_API_BASE_URL` 控制前端 API 基址；单服务同源部署及默认 Vite 开发代理可不设置，Netlify 静态部署需配置。
- `.local-data/` 是单机演示持久化；迁移模块不得改变现有文件名、schema 和版本冲突行为。

## 验证入口

```powershell
.\.venv\Scripts\python.exe -m pytest 04-demo\backend\tests -q
npm.cmd --workspace 04-demo/frontend test
npm.cmd run build
$env:Path = (Resolve-Path .\.venv\Scripts).Path + ";" + $env:Path
npm.cmd run verify:architecture
npm.cmd run verify
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\04-demo\backend\scripts\smoke_single_service.ps1
```

该虚拟环境路径只是本地示例，CI 可以使用环境中的 Python 执行同一测试模块。

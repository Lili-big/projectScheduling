# 运行与部署边界

## 本地开发

后端：

```powershell
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --app-dir 04-demo/backend --reload
```

前端：

```powershell
npm.cmd run frontend:dev
```

Vite 在 `127.0.0.1:5173` 提供页面并把 `/api` 代理到 `127.0.0.1:8000`。前端请求超时为 90 秒。

前台运行时日志直接留在当前终端。后台运行需要重定向时使用 `04-demo/runtime/start_logged_process.ps1`，stdout/stderr 统一进入 `.local-data/logs/<启动时间>/`；仓库根目录不作为运行日志目录。

## 单服务演示

```powershell
npm.cmd run build
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --app-dir 04-demo/backend
```

FastAPI 在检测到 `04-demo/frontend/dist` 后挂载 `/assets` 并提供 SPA 回退。修改前端后必须重新构建。

## Docker

`Dockerfile` 基于 Python 3.12，安装根 `requirements.txt`，从 `04-demo/backend/` 和 `04-demo/examples/` 复制容器内后端与样例，并启动 `app.main:app`。容器没有构建 React 前端，因此当前镜像主要保证 FastAPI API 和样例输入可用。

## Netlify

`netlify.toml` 执行根 `npm run build` 并发布 `04-demo/frontend/dist`，所有前端路由回退到 `index.html`。生产页面必须配置 `VITE_API_BASE_URL` 指向独立部署的完整 FastAPI/OR-Tools 后端，否则前端会主动报错。

`04-demo/tools/demo-api-mirror/api.mts` 是参考 API 镜像；当前 `netlify.toml` 未配置 Functions 目录，它不是正式后端，也不保证覆盖当前 57 个 FastAPI 操作。

## 配置和数据

- 根 `.local.env` 由后端启动加载，真实密钥不得提交。
- `SCHEDULER_CORS_ORIGINS` 和 `SCHEDULER_CORS_ORIGIN_REGEX` 控制后端跨域。
- `VITE_API_BASE_URL` 控制前端 API 基址。
- `.local-data/` 是单机演示持久化；迁移模块不得改变现有文件名、schema 和版本冲突行为。

## 验证入口

```powershell
.\.venv\Scripts\python.exe -m pytest 04-demo\backend\tests -q
npm.cmd --workspace frontend test
npm.cmd run build
npm.cmd run verify:architecture
npm.cmd run verify
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\04-demo\backend\scripts\smoke_single_service.ps1
```

该虚拟环境路径只是本地示例，CI 可以使用环境中的 Python 执行同一测试模块。

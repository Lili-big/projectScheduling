# 本地运行日志

后台服务 stdout/stderr 的唯一标准落点是 `.local-data/logs/<启动时间>/`。该目录已随 `.local-data/` 被 Git 忽略；仓库根目录不放运行日志。

## 启动示例

以下命令在仓库根目录执行，依赖安装见根 README。脚本隐藏后台窗口并保存日志；可在同一终端依次启动两个服务。

后端：

```powershell
.\04-demo\runtime\start_logged_process.ps1 `
  -Name backend `
  -FilePath .\.venv\Scripts\python.exe `
  -ArgumentList @('-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', '8000', '--app-dir', '04-demo/backend')
```

前端：

```powershell
.\04-demo\runtime\start_logged_process.ps1 `
  -Name frontend `
  -FilePath npm.cmd `
  -ArgumentList @('run', 'frontend:dev', '--', '--port', '5174', '--strictPort')
```

脚本返回进程 PID、stdout 和 stderr 路径。返回 PID 仅代表进程已创建，还需检查接口确认启动成功：

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/health
Invoke-RestMethod http://127.0.0.1:5174/api/health
```

页面为 `http://127.0.0.1:5174/`。失败时查看返回的 stderr/stdout 日志。8000或5174已被占用时，先确认是否能复用已有服务。

停止服务时只处理本次返回的 PID 及其子进程；npm 会启动命令行和 Node 子进程，不能只停止父进程后就认为端口已释放。不要按进程名批量终止无关服务。

## 维护规则

- 前台调试优先保留终端输出，不必生成日志文件。
- 后台运行必须通过统一脚本或显式写入 `.local-data/logs/`。
- 同次启动的 stdout/stderr 放在同一个时间戳目录，避免不同服务和历史运行互相覆盖。
- 日志可能包含文件路径、请求和错误上下文，不进入 Git，也不作为正式交付物。
- 历史根目录日志迁入 `.local-data/logs/legacy/` 前先确认服务已停止；只移动，不删除。
- 需要清理旧日志时由维护者按时间和问题复现需求人工确认，不设置未经确认的自动删除。

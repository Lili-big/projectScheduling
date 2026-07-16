# 本地运行日志

后台服务 stdout/stderr 的唯一标准落点是 `.local-data/logs/<启动时间>/`。该目录已随 `.local-data/` 被 Git 忽略；仓库根目录不放运行日志。

## 启动示例

后端：

```powershell
.\tools\local-runtime\start_logged_process.ps1 `
  -Name backend `
  -FilePath .\.venv\Scripts\python.exe `
  -ArgumentList @('-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', '8000', '--app-dir', 'backend')
```

前端：

```powershell
.\tools\local-runtime\start_logged_process.ps1 `
  -Name frontend `
  -FilePath npm.cmd `
  -ArgumentList @('--workspace', 'frontend', 'run', 'dev')
```

脚本返回进程 PID、stdout 和 stderr 路径。停止服务时只处理返回的 PID；不要按进程名批量终止无关服务。

## 维护规则

- 前台调试优先保留终端输出，不必生成日志文件。
- 后台运行必须通过统一脚本或显式写入 `.local-data/logs/`。
- 同次启动的 stdout/stderr 放在同一个时间戳目录，避免不同服务和历史运行互相覆盖。
- 日志可能包含文件路径、请求和错误上下文，不进入 Git，也不作为正式交付物。
- 历史根目录日志迁入 `.local-data/logs/legacy/` 前先确认服务已停止；只移动，不删除。
- 需要清理旧日志时由维护者按时间和问题复现需求人工确认，不设置未经确认的自动删除。

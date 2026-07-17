# 本地产物分区

`.local-data/` 是仓库唯一的本地状态与运行产物入口。除本 README 外，目录内容默认忽略，不作为正式交付物提交。

| 分区 | 内容 | 保护/清理规则 |
| --- | --- | --- |
| `state/` | SQLite、调度配置、计划管控和其他持久状态 | 最高保护；不得成为自动删除候选 |
| `logs/` | 当前运行日志与历史散落日志归档 | 迁移或清理前检查活动进程；默认只预览 |
| `cache/` | 依赖、浏览器、工具等可再生成缓存 | 只有显式指定类别并使用 `-Apply` 才可处理 |
| `tmp/` | Python 缓存、中间目录和短期临时文件 | 先确认不是用户输入或正式成果 |
| `locks/` | Office 锁和本地互斥文件 | 确认关联程序已退出后才可处理 |
| `archive/` | 可再生成输出、迁移空壳和需留档的本地产物 | 默认保留；`rebuildable/` 可进入清理预览 |

## 输入与正式成果

- 工作包客户/用户输入放在对应工作包 `input/` 或 `inputs/`，tracking 为 `local-only` 时仍受保护。
- 正式成果必须进入 `01`～`06` 的权威阶段或工作包并使用 `formal-output`，不能放进 cache/tmp。
- `.local.env` 始终原位、local-only；治理工具只检查路径和文件名，不复制真实值。

## 日志

后台服务通过 `04-demo/runtime/start_logged_process.ps1` 启动，stdout/stderr 写入 `.local-data/logs/<时间>/`。历史散落日志位于 `logs/legacy-unclassified/`，均为移动留档，未删除。

## 清理

```powershell
# 默认 dry-run：只列候选、大小、保护和未知项
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\00-governance\repository-tools\cleanup-workspace.ps1

# 实际处理必须同时指定非保护类别和 -Apply
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\00-governance\repository-tools\cleanup-workspace.ps1 -Category cache -Apply
```

`persistent-state`、`user-input`、`formal-output` 永远不是自动清理类别。未知项保持不动并要求人工归类。

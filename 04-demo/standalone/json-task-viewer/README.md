# 本地 JSON 任务视图

## 目的

把通用排程 JSON 转换为可离线查看的 HTML，独立于主 Demo 运行。

## 输入

- 输入：`input/第一版本.json`

`input/` 为用户本地输入，不提交 Git；可复制批准样例后再运行。

## 运行

双击 `生成任务视图.cmd`，或在项目根目录执行：


```powershell
node .\04-demo\standalone\json-task-viewer\scripts\build-task-view-html.mjs
```

## 成果

- `output/第一版本.html`：离线任务视图。
- `output/` 下的 JSON、HTML 和截图均可由输入与脚本重新生成。

## 跟踪与保留

README、`workpackage.json` 和脚本跟踪；`input/` 为 local-only；`output/` 为 ignored/rebuildable。禁止把客户输入复制到受跟踪目录。

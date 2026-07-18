# 真实 JSON 工程排程结果评审

## 目的

对真实工程排程 JSON 生成可复核报告和 HTML 快照，明确区分本地输入、可复用脚本和可再生成结果。

## 输入

- 输入：`input/固定资源最小工期结果.v1.json`

## 运行

在项目根目录执行：

```powershell
node .\05-validation\workpackages\json-schedule-review\scripts\build-engineering-result-snapshot.mjs
```

也可双击 `生成研发结果快照.cmd`。

## 成果

- `output/固定资源最小工期结果.v1.report.json`
- `output/固定资源最小工期结果.v1.html`

## 闭环归属

- 主责角色：`L01｜客户调研与验证闭环`。
- 复核结论必须注明验证问题和来源；不通过项回流对应 D 角色或 L03，通过项可作为 L06 交付证据。

## 跟踪与保留

README、描述文件和脚本跟踪；`input/` 是 local-only 用户输入；`output/` 是 ignored/rebuildable。清理工具不得把输入列为删除候选。

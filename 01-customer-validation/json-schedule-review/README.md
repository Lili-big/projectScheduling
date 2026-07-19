# 真实 JSON 工程排程结果评审

## 目的

对真实工程排程 JSON 生成可复核报告和 HTML 快照，区分客户资料、可复用脚本和验证结果。

## 输入

- `customer-materials/固定资源最小工期结果.v1.json`

## 运行

```powershell
node .\01-customer-validation\json-schedule-review\validation-results\_scripts\build-engineering-result-snapshot.mjs
```

也可运行 `validation-results/_scripts/生成研发结果快照.cmd`。

## 成果

- `validation-results/固定资源最小工期结果.v1.report.json`
- `validation-results/固定资源最小工期结果.v1.html`

## 闭环归属

- 主责角色：`L01｜需求发现与验证闭环`。
- 复核结论必须注明验证问题和来源；不通过项回流对应工作项，达到正式标准的结果可进入 `06-delivery`。

## 跟踪与保留

README、工作包契约和脚本跟踪；真实输入 local-only；报告和 HTML 为 ignored/rebuildable，但保留在 `validation-results/` 便于查找。

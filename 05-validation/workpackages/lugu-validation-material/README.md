# 泸古客户验证材料

## 目的

依据客户验证计划生成并检查验证工作簿，同时保留统一工点主数据的构建、映射和验收证据。

## 输入

- `plans/泸古项目客户验证计划_20260715.md`
- `project-master/results/` 中的批准主数据样例。

## 运行

```powershell
node .\05-validation\workpackages\lugu-validation-material\scripts\build_validation_workbook.mjs
node .\05-validation\workpackages\lugu-validation-material\scripts\verify_validation_workbook.mjs
```

统一主数据专项入口位于 `project-master/scripts/`。

## 成果

- `project-master/results/泸古TJ-1标统一工点及桥梁结构物导入数据.xlsx`
- `project-master/results/泸古TJ-1标统一主数据_mapping-report.json`

## 跟踪与保留

计划、构建校验脚本和批准成果跟踪；数据库、截图和中间检查文件按清单保留，不因属于缓存目录而自动删除。

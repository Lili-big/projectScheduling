# 泸古客户验证

## 目的

集中维护泸古项目的客户资料、验证计划和验证结果，覆盖客户事实还原、计划版本比较、价值验证和统一项目主数据复核。

## 输入

- `customer-materials/`：客户原始表格、调研记录和来源结构分析。
- `validation-plans/`：访谈提纲、价值验证表和验证计划。
- 新增客户敏感原文必须记录来源，并按敏感性决定 tracked 或 local-only。

## 运行

```powershell
python .\01-customer-validation\lugu\customer-materials\_scripts\build_report.py
python .\01-customer-validation\lugu\customer-materials\_scripts\build_planning_logic_report.py
python .\01-customer-validation\lugu\validation-results\_scripts\compare_plan_versions.py --old <4月27日计划.xlsx> --new <6月6日计划.xlsx> --output .\01-customer-validation\lugu\validation-results\plan_version_comparison.json
node .\01-customer-validation\lugu\validation-results\_scripts\build_lugu_project_master.mjs
```

## 成果

- `customer-materials/泸古项目7月15日上午调研验证记录_20260715.docx`
- `customer-materials/泸古项目7月16日前期工期策划思路分析_20260715.docx`
- `validation-results/泸古项目计划管理方式变化验证记录_20260716_v3.docx`
- `validation-results/泸古TJ-1标统一工点及桥梁结构物导入数据.xlsx`

## 闭环归属

- 主责角色：`L01｜需求发现与验证闭环`。
- 调研事实、验证假设、判定标准和验证结论在同一工作包内分目录保存，不复制第二份权威文件。

## 跟踪与保留

批准的客户资料、计划、脚本和验证结果跟踪；客户敏感原文按 local-only 保留；预览、检查 NDJSON 和本地数据库进入 `.local-data/archive/rebuildable/customer-validation/lugu/`。

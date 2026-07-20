# 泸古1标客户验证

## 目的

集中维护泸古1标的客户资料、验证计划和验证结果，覆盖客户事实还原、计划版本比较、价值验证和统一项目主数据复核。

## 输入

- `customer-materials/`：客户提供、未经分析加工的原始表格和来源材料。
- `validation-plans/`：访谈提纲、价值验证表和验证计划。
- `validation-results/`：调研分析总结、数据结构分析、方案比较、系统结果和客户验证结论。

## 运行

```powershell
python .\01-customer-validation\泸古1标\validation-results\_scripts\build_report.py
python .\01-customer-validation\泸古1标\validation-results\_scripts\build_planning_logic_report.py
python .\01-customer-validation\泸古1标\validation-results\_scripts\compare_plan_versions.py --old <4月27日计划.xlsx> --new <6月6日计划.xlsx> --output .\01-customer-validation\泸古1标\validation-results\plan_version_comparison.json
node .\01-customer-validation\泸古1标\validation-results\_scripts\build_lugu_project_master.mjs
```

## 成果

- `customer-materials/2026Q3-0718上午-泸古1标工程部长-调研录音文字记录.docx`
- `validation-results/2026Q3-0718上午-泸古1标工程部长-客户价值验证调研记录表.xlsx`
- `validation-results/2026Q3-0718上午-泸古1标工程部长-调研分析报告.docx`
- `validation-results/2026Q3-0718上午-泸古1标工程部长-产品价值验证领导汇报.md`
- `validation-results/泸古项目7月15日上午调研验证记录_20260715.docx`
- `validation-results/泸古项目7月16日前期工期策划思路分析_20260715.docx`
- `validation-results/2026Q2-5月集中调研-泸古1标-项目总工-分析总结-20260527.pdf`
- `validation-results/来源与完整性索引.md`
- `validation-results/泸古项目计划管理方式变化验证记录_20260716_v3.docx`
- `validation-results/泸古TJ-1标统一工点及桥梁结构物导入数据.xlsx`

## 闭环归属

- 主责角色：`L01｜需求发现与验证闭环`。
- 调研事实、验证假设、判定标准和验证结论在同一工作包内分目录保存，不复制第二份权威文件。

## 跟踪与保留

正式客户资料、验证计划、分析总结和验证结果进入 Git；迁移来源名称映射不属于验证材料或结果，保留为 local-only。预览、检查 NDJSON 和本地数据库进入 `.local-data/archive/rebuildable/customer-validation/lugu/`。远端转为私有前不得推送含客户或人员信息的文件。

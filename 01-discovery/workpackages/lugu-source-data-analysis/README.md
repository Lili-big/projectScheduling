# 泸古来源工作簿结构分析

## 目的

分析来源 Excel 的工作表、桥梁进度字段和结构分布，为参数化导入、验证材料和需求判断提供证据。

## 输入

- `inputs/泸古1标架梁工点导入模板.xlsx`

## 运行

```powershell
python .\01-discovery\workpackages\lugu-source-data-analysis\scripts\analyze_bridge_schedule_workbook.py
```

## 成果

- `results/bridge_schedule_structure.json`
- `results/bridge_progress_profile.json`

## 闭环归属

- 主责角色：`L01｜客户调研与验证闭环`。
- 本工作包保存来源结构证据；用于客户验证时由 `05-validation/workpackages/lugu-validation-material/` 引用，不复制第二份来源模板。

## 跟踪与保留

当前来源样例、脚本和结构化分析结果均经批准跟踪；替换真实客户数据时必须重新判断是否仅本地保留。

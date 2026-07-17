# 泸古计划粒度比较与验证

## 目的

比较计划版本、任务粒度和业务管理方式变化，生成结构化差异与可复核验证记录。

## 输入

- `results/new_total_plan_profile.json`：本工作包当前批准的分析基线。
- 新版本原始表格应先登记来源，再决定 tracked 或 local-only。

## 运行

```powershell
python .\05-validation\workpackages\lugu-plan-granularity\scripts\compare_plan_versions.py
python .\05-validation\workpackages\lugu-plan-granularity\scripts\build_plan_granularity_validation.py
```

## 成果

- `results/plan_version_comparison.json`
- `results/泸古项目计划粒度验证记录_20260716_v2.docx`

## 跟踪与保留

分析脚本、结构化结果和确认版验证记录跟踪；临时渲染、解包或检查结果进入本地归档。

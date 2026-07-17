# 泸古客户调研与报告

## 目的

从访谈提纲和调研材料中还原业务事实、规划逻辑、待确认问题与产品机会，并生成可交付调研记录。

## 输入

- `inputs/泸古项目客户访谈提纲_20260715.md`
- 新增访谈原文或客户材料必须记录来源；敏感原文默认 local-only。

## 运行

```powershell
python .\01-discovery\workpackages\lugu-customer-research\scripts\build_report.py
python .\01-discovery\workpackages\lugu-customer-research\scripts\build_planning_logic_report.py
```

## 成果

- `results/泸古项目上午调研验证记录_20260715.docx`
- `results/泸古项目前期工期策划思路分析_20260715.docx`

## 跟踪与保留

批准的提纲、脚本和报告跟踪；临时转录、解包目录和检查缓存进入 `.local-data/tmp` 或 `.local-data/archive/rebuildable`。

# 工作包 60 秒抽样验收

## 验收方法

从根 `README.md` 进入阶段 README，再打开工作包的 `workpackage.json` 和 README。计时范围为定位工作包并提取第一个输入、运行入口、成果、状态和保留边界；门槛为 60 秒。

## 抽样结果

| 工作包 | 导航路径 | 自动契约提取耗时 | 输入 | 运行入口 | 成果 | 结论 |
| --- | --- | ---: | --- | --- | --- | --- |
| `json-task-viewer` | 根 → `04-demo` → `standalone/json-task-viewer` | 0.000628 秒 | `input/第一版本.json` | `scripts/build-task-view-html.mjs` | `output/第一版本.html` | 通过 |
| `lugu-validation-material` | 根 → `05-validation` → `workpackages/lugu-validation-material` | 0.000698 秒 | 客户验证计划 | `scripts/build_validation_workbook.mjs` | 统一工点导入工作簿 | 通过 |
| `ai-case-summary` | 根 → `06-delivery` → `workpackages/ai-case-summary` | 0.000694 秒 | 最早历史版本 | 无可确认脚本 | v1.2 与申报版 | 通过，且 `orphaned` 状态明确 |

三项均可在两次目录进入内找到，并能直接说明输入、命令/缺失命令、成果与保留边界。`ai-case-summary` 没有伪造生成脚本，缺口通过 `orphaned` 状态显式保留。

## 关系说明

```text
lugu-source-data-analysis -> lugu-validation-material -> lugu-plan-granularity
json-task-viewer ---------> json-schedule-review
ai-case-summary ----------> ai-ppt-system
```

关系只表达输入/验证/传播上的关联，不改变各工作包的唯一主阶段。

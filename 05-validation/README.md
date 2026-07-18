# 05 · 客户与方案验证

## 目的

维护验证计划、客户输入、分析或生成脚本、验证结果和结论，使方案与 Demo 的判断可以复现。本阶段是 L01“客户调研与验证闭环”的验证侧。

## 进入条件

- 方案、需求或 Demo 需要通过客户数据、验收场景或结果比较验证。
- 已明确输入来源、验证问题和结果判定口径。

## 退出条件

- 输入、步骤、脚本、结果、结论和限制完整关联。
- 问题可回流 `02-solution-analysis`、`03-requirements` 或 `04-demo`，通过项可进入 `06-delivery`。

## 权威资产

- `reports/`：通用验证报告。
- `workpackages/`：按验证主题组织的输入、脚本、结果和说明。

## 角色与闭环

- 主责角色：`L01｜客户调研与验证闭环`。
- 验证问题必须引用 `01-discovery/` 的调研证据，或引用 `02-solution-analysis/`、`03-requirements/`、`04-demo/` 中待验证的明确假设。
- 不通过项回流 L02/L03 或对应 D 角色，通过项进入 L06；验证结论不反向覆盖调研原文。

## 工作包索引

- [`json-schedule-review`](workpackages/json-schedule-review/)：真实 JSON 工程结果评审。
- [`lugu-validation-material`](workpackages/lugu-validation-material/)：泸古验证材料构建与校验。
- [`lugu-plan-granularity`](workpackages/lugu-plan-granularity/)：泸古计划粒度比较。
- [`dianfengwu-tj03-product-validation-2026q2`](workpackages/dianfengwu-tj03-product-validation-2026q2/)：垫丰武 TJ03 2026 Q2 历史客户验证记录。

## 相邻阶段

- 上游可来自 [01-discovery](../01-discovery/README.md)、`02-solution-analysis`、`03-requirements` 或 [04-demo](../04-demo/README.md)。
- 下一阶段：[06-delivery](../06-delivery/README.md)；结论不通过时回流 `02-solution-analysis` 或 `03-requirements`。

## 禁止内容

- 未登记来源的客户输入、无法复现的结果文件和主 Demo 源代码。
- 把验证结论直接覆盖正式产品规则而不回写需求。

## 维护触发条件

验证输入、脚本、判定标准、结果或结论变化时，更新工作包描述和引用链。

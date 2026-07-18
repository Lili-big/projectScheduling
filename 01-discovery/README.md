# 01 · 前期需求调研

## 目的

保存客户访谈、调研提纲、业务现状、来源文件和数据结构分析，形成后续方案、需求与验证问题的证据基础。本阶段是 L01“客户调研与验证闭环”的调研侧。

## 进入条件

- 问题、角色、流程或来源数据仍需通过客户材料确认。
- 需要区分事实、推断、待确认问题和产品机会。

## 退出条件

- 输入来源、调研过程、结论和未决问题可追溯。
- 可向 `02-solution-analysis` 提供方案比较依据，或向 `03-requirements` 提供已确认口径。

## 权威资产

- 调研输入与访谈材料。
- 来源工作簿、结构分析脚本和调研总结。

## 角色与闭环

- 主责角色：`L01｜客户调研与验证闭环`。
- 业务事实、痛点、产品假设和待验证问题在本阶段形成；正式验证计划、脚本、结果与结论进入 `05-validation/`。
- 两个阶段只互相引用，不复制访谈原文、客户数据或验证结果的第二份权威文件。

## 工作包索引

- [`lugu-customer-research`](workpackages/lugu-customer-research/)：泸古客户调研与报告生成。
- [`lugu-source-data-analysis`](workpackages/lugu-source-data-analysis/)：泸古来源工作簿结构分析。
- [`infrastructure-version-research-2026q2`](workpackages/infrastructure-version-research-2026q2/)：基建版本 2026 Q2 历史客户调研整理稿迁移与脱敏索引。

## 相邻阶段

- 上一阶段：[00-governance](../00-governance/README.md)。
- 后续方案进入 [02-solution-analysis](../02-solution-analysis/README.md)，已确认需求可进入 `03-requirements`，待验证问题进入 [05-validation](../05-validation/README.md)。

## 禁止内容

- 未经证据确认的产品规则和实现承诺。
- Demo 代码、客户验收结果或对外交付定稿。

## 维护触发条件

新增访谈、来源文件、调研脚本或调研结论时，更新对应工作包的输入、脚本、成果与保留策略。

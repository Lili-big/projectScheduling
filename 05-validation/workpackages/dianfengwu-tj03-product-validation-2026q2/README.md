# 垫丰武 TJ03 产品验证记录（2026 Q2）

## 目的

保存旧作业空间迁入的垫丰武 TJ03 客户验证记录，保留当时对系统展示、计划偏差、关键节点风险和使用动力的验证证据。调研事实仍由 01-discovery 工作包负责，本工作包只保存验证侧材料。

## 输入

- inputs/legacy-pdf-summaries/：4 份历史 PDF 验证记录。
- PDF 含客户、项目和人员信息，仅在本地保留，不进入 Git。
- asset-index.md 使用脱敏名称、文件大小和 SHA-256 记录迁移基线。

## 运行

当前缺少原始沟通记录、验证计划和生成脚本，无法重新生成这些 PDF，因此工作包状态为 orphaned。

## 成果

- asset-index.md：脱敏资产索引和迁移校验基线。
- 历史 PDF 中的判断不得直接覆盖当前产品规则；需要复核时应补充当前验证问题、判定标准和客户数据。

## 跟踪与保留

- README.md、workpackage.json、asset-index.md 和本地忽略规则为 tracked 正式成果。
- PDF 与 source-map.local.json 为 local-only 用户输入，不得提交或作为公开样例。
- 不清理原始 PDF；后续替换或迁移前必须核对 SHA-256。

## 关联工作包

- 01-discovery/workpackages/infrastructure-version-research-2026q2/


# 基建版本历史客户调研（2026 Q2）

## 目的

集中接收旧作业空间迁入的基建版本客户调研整理稿，作为后续业务流程、角色诉求和产品假设分析的历史证据。本文档不把整理稿中的产品判断直接视为已验证事实。

## 输入

- inputs/legacy-pdf-summaries/：11 份历史 PDF 调研整理稿。
- PDF 含客户、项目和人员信息，仅在本地保留，不进入 Git。
- asset-index.md 使用脱敏名称、文件大小和 SHA-256 记录迁移基线。

## 运行

当前缺少原始访谈转写和生成脚本，无法从源材料重新生成这些 PDF，因此工作包状态为 orphaned。

## 成果

- asset-index.md：脱敏资产索引和迁移校验基线。
- 本工作包暂不输出新的跨客户调研总结；需要总结时另行使用 research-summary，并区分事实、推断、产品判断和待验证问题。

## 跟踪与保留

- README.md、workpackage.json、asset-index.md 和本地忽略规则为 tracked 正式成果。
- PDF 与 source-map.local.json 为 local-only 用户输入，不得提交或作为公开样例。
- 不清理原始 PDF；后续替换或迁移前必须核对 SHA-256。

## 关联工作包

- 05-validation/workpackages/dianfengwu-tj03-product-validation-2026q2/
- 01-discovery/workpackages/lugu-customer-research/


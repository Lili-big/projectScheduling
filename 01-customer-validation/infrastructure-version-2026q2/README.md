# 基建版本历史客户资料（2026 Q2）

## 目的

保存旧作业空间迁入的基建版本客户调研整理稿，作为后续业务流程、角色诉求和产品假设分析的历史证据。整理稿中的产品判断不直接视为已验证事实。

## 输入

- `customer-materials/`：11 份历史 PDF 调研整理稿及本地来源映射。
- PDF 含客户、项目和人员信息，仅在本地保留，不进入 Git。

## 运行

当前缺少原始访谈转写和生成脚本，无法从源材料重新生成这些 PDF，因此工作包状态为 orphaned。

## 成果

- `validation-results/asset-index.md`：脱敏资产索引、文件大小和 SHA-256 迁移基线。

## 跟踪与保留

README、workpackage.json、脱敏索引和本地忽略规则跟踪；PDF 与 `source-map.local.json` 为 local-only 用户输入。迁移或替换前必须核对 SHA-256，不清理原始 PDF。

## 关联工作包

- `../dianfengwu-tj03/`
- `../lugu/`

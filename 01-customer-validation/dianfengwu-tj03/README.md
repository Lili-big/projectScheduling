# 垫丰武 TJ03 客户验证（2026 Q2）

## 目的

保存旧作业空间迁入的垫丰武 TJ03 客户资料和验证记录，保留当时对系统展示、计划偏差、关键节点风险和使用动力的验证证据。

## 输入

- `customer-materials/`：4 份历史 PDF 验证记录及本地来源映射。
- PDF 含客户、项目和人员信息，仅在本地保留，不进入 Git。

## 运行

当前缺少原始沟通记录、验证计划和生成脚本，无法重新生成这些 PDF，因此工作包状态为 orphaned。

## 成果

- `validation-results/asset-index.md`：脱敏资产索引、文件大小和 SHA-256 迁移基线。

## 跟踪与保留

README、workpackage.json、脱敏索引和本地忽略规则跟踪；PDF 与 `source-map.local.json` 为 local-only 用户输入。历史判断不得直接覆盖当前产品规则。

## 关联工作包

- `../infrastructure-version-2026q2/`

# 00 · 仓库治理

## 目的

维护全仓库的生命周期目录、资产归属、协作契约、兼容入口、治理脚本和迁移历史。本阶段定义规则，不承载具体客户项目的业务成果。

## 进入条件

- 任务会改变仓库结构、Agent 工作方式、资产分类、保留策略或质量门禁。
- 现有资产没有唯一主归属，或入口变更需要兼容和回退设计。

## 退出条件

- 机器规则、人工说明、测试和回退边界同步更新。
- 新路径可被根导航找到，且治理校验可以识别错误放置。

## 权威资产

- `architecture/`：架构说明与当前结构事实。
- `asset-policy/`：阶段、工作包、放置和清理策略。
- `asset-policy/thread-roles/`：仅保存 G00、L01 常驻 Thread 的注册信息和专属边界。
- `repository-tools/`：仓库校验、迁移和安全清理工具。
- `history/`：旧路径映射与历史治理记录。

## 工作包索引

- `lifecycle-workspace-governance`：当前仓库生命周期重构，规格位于 `../03-requirements/specs/045-lifecycle-workspace-governance/`。
- [全仓工作包注册表](asset-policy/workpackages.json)：列出 14 个独立工作包的阶段、路径、状态和用途。

```text
01-customer-validation -> 泸古1标 / 中铁23局集团及公司 / 垫丰武TJ03标 / 垫丰武TJ08标 / 江泸宜01标 / 沪渝垫长段三分部 / json-schedule-review / ai-assistants
04-demo      -> json-task-viewer / schedule-result-viewer
06-delivery  -> ai-case-summary / ai-ppt-system / product-agent-practice-kit
```

## 相邻阶段

- 下一阶段：[01-customer-validation](../01-customer-validation/README.md)。治理规则也可以直接约束 `02-solution-analysis` 至 `06-delivery`。

## 禁止内容

- 客户原始输入、Demo 业务代码、验证结果和正式交付物。
- 仅为一次任务存在、没有复用价值的临时脚本或输出。

## 维护触发条件

新增根目录、阶段、工作包、资产类别、常驻 Thread、兼容入口或清理类别时必须更新本 README、`asset-policy/` 和对应测试。

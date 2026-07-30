# 06 · 正式交付与传播

## 目的

维护可对外、可归档的正式文档、案例总结、演示材料和生成工具，区分当前成果、草稿和历史版本。

## 进入条件

- 成果已经完成验证，或明确达到正式留档、客户交付或演示传播标准。
- 来源、版本、维护人和生成关系可以登记。

## 退出条件

- 当前版本、历史版本、输入模板和生成脚本边界明确。
- 正式成果可独立找到，且本地构建缓存不混入交付目录。

## 权威资产

- `deliverables/`：正式交付文件。
- `workpackages/`：案例等独立交付闭环。
- `presentations/`：演示材料及其可复用生成工具。

## 工作包索引

- [`ai-case-summary`](workpackages/ai-case-summary/)：AI 案例总结及历史版本。
- [`ai-ppt-system`](presentations/ai-ppt-system/)：企业级演示材料生成系统。
- [`product-agent-practice-kit`](workpackages/product-agent-practice-kit/)：可直接转发并通过初始化 Prompt 启动的产品 Agent 项目 ZIP。

## 相邻阶段

- 上游实现来自 [04-demo](../04-demo/README.md)，正式交付前由 [01-customer-validation](../01-customer-validation/README.md) 提供验证证据。
- 下一轮输入可回到 [01-customer-validation](../01-customer-validation/README.md)；方案复盘进入 `02-solution-analysis`。

## 禁止内容

- 未验证草稿伪装成正式成果、客户隐私输入、运行日志、依赖和构建缓存。
- 无法说明来源或生成关系却标记为当前正式版本的资产。

## 维护触发条件

交付版本、案例来源、演示模板、生成命令或当前/历史状态变化时，更新对应工作包和索引。

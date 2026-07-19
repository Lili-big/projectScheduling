# 03 · 需求文档设计

## 目的

维护产品需求、算法规则、研发交底和 Spec Kit 规格，使已确认口径可验收、可计划、可实施。

## 进入条件

- 方案和产品口径已经确认，准备形成 PRD、算法规则或规格化开发资产。
- 输入、输出、约束、异常和验收方向已经可以说明。

## 退出条件

- 需求和算法规则不混淆，Demo 临时限制已显式标注。
- Spec Kit 的 spec、plan、tasks 与检查表通过门禁并获用户确认。

## 权威资产

- `product/`：产品需求和研发交底。
- `rules/`：算法、资源、工期和计算规则。
- `specs/`：按编号维护的 Spec Kit 功能规格。
- `templates/`：后续新增的需求模板。

## 工作包索引

- [`045-lifecycle-workspace-governance`](specs/045-lifecycle-workspace-governance/)：本次生命周期目录治理。
- 其他规格以 `specs/<编号>-<功能名>/` 为唯一主路径。

## 相邻阶段

- 上一阶段：[02-solution-analysis](../02-solution-analysis/README.md)。
- 下一阶段：[04-demo](../04-demo/README.md)；验收设计也可直接进入 [01-customer-validation](../01-customer-validation/README.md)。

## 禁止内容

- 客户原始调研材料、构建产物、运行日志和本地状态。
- 未确认需求对应的实现代码或任务清单。

## 维护触发条件

产品口径、共享字段、算法目标、约束或验收标准变化时，更新对应文档、规格、接口契约和任务。

# 04 · Demo 实现

## 目的

维护桥梁施工排程 Demo 的后端、前端、运行入口、样例、部署配置和独立展示工具。

## 进入条件

- 需求已确认进入实现或明确缺陷修复。
- 涉及算法、共享模型或跨端改动时已完成 Spec Kit 门禁。

## 退出条件

- 代码、接口、测试和运行说明一致。
- 输入、输出、异常和兼容场景可复现，结果可交给 `05-validation` 验证。

## 权威资产

- `backend/`、`frontend/`：Demo 服务和页面。
- `runtime/`、`tools/`：本地运行与 Demo 工具。
- `examples/`：可复现样例。
- `standalone/`：与主 Demo 解耦的独立展示工具。

## 工作包索引

- [`json-task-viewer`](standalone/json-task-viewer/)：通用 JSON 任务展示。
- [`schedule-result-viewer`](standalone/schedule-result-viewer/)：固定排程结果离线查看。
- `bridge-scheduling-demo`：主后端、前端、运行与部署资产。

## 相邻阶段

- 上一阶段：[03-requirements](../03-requirements/README.md)。
- 下一阶段：[05-validation](../05-validation/README.md)；经验证的正式成果进入 `06-delivery`。

## 禁止内容

- 客户原始资料、PRD 唯一原文、正式验收记录和本地日志缓存。
- 无归属的一次性脚本、截图或构建输出。

## 维护触发条件

运行命令、接口字段、共享模型、部署入口或独立工具路径变化时，更新本 README、根入口和相关测试。

# 常驻 Thread 角色治理

本目录是项目长期常驻 Codex task/thread 的权威职责源。对话上下文可以压缩或过期，但角色编号、职责、路径和交接规则必须从本目录恢复。

## 编号体系

- `G00`：全局治理、任务路由和跨角色协调。
- `Lxx`：生命周期角色，编号与阶段目录对应。`L04` 不单设，Demo 技术工作由 `D01`～`D07` 承担。
- `Dxx`：`04-demo/` 内的稳定技术领域角色，不与生命周期目录编号混用。

## 每次任务的读取顺序

1. 读取根目录 `AGENTS.md`。
2. 在 `registry.yaml` 中确认自己的 `ROLE_ID`、thread ID、名称和契约文件。
3. 完整读取 `<ROLE_ID>.md`，再读取目标阶段 README、`agent.md` 和任务材料。
4. 如果当前标题、旧对话说明和契约冲突，以仓库契约为准并报告冲突。

## 快速修改职责

1. 先修改 `registry.yaml` 中的名称、路径或交接关系，并递增 `version`、更新 `updated_at`。
2. 同步修改对应 `<ROLE_ID>.md`；新增或停用角色时同步本 README 和测试。
3. 运行 `python -m pytest 00-governance/repository-tools/tests/test_thread_role_registry.py 00-governance/repository-tools/tests/test_task_classification.py -q`。
4. 最后在 Codex 中改名并向对应 thread 发送新的角色绑定消息。不要只改对话标题。

## 当前角色

| ID | 名称 | 主轴 |
|---|---|---|
| G00 | 项目总控与资产治理 | 全局治理 |
| L01 | 用户调研与证据总结 | `01-discovery/` |
| L02 | 方案分析与产品决策 | `02-solution-analysis/` |
| L03 | 需求文档与规格管理 | `03-requirements/` |
| L05 | 客户验证与方案验收 | `05-validation/` |
| L06 | 正式交付与演示传播 | `06-delivery/` |
| D01 | 项目主数据与结构底座 | Demo 主数据 |
| D02 | 综合排程算法内核 | Demo 排程求解 |
| D03 | 架梁专项与综合联算 | Demo 架梁领域 |
| D04 | 计划管控与进度预测 | Demo 计划管控 |
| D05 | 工作台与结果体验 | Demo 前端体验 |
| D06 | 架构契约与技术质量 | Demo 契约质量 |
| D07 | AI 参数与资源助手 | Demo AI 助手 |

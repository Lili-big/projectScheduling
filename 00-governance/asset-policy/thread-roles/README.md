# Thread 与能力治理

本目录是项目 Codex 协作方式的权威来源。对话上下文可以压缩或过期，但常驻 Thread、工作项规则、能力边界和 Subagent 策略必须从本目录恢复。

## 运行模型

- `G00`：项目治理、工作项建档、依赖和组合状态协调。
- `L01`：跨需求的客户调研、需求发现和验证证据闭环。
- 工作项 Thread：一项真实需求对应一个主责 Thread，由它端到端完成澄清、决策、规格、实现、验证和关闭。
- `L02`、`L03`、`L06`、`D01`～`D07`：可复用能力编号，不绑定常驻 Thread。主责 Thread 按需加载对应契约。

## 每项工作的读取顺序

1. 读取根目录 `AGENTS.md`。
2. 读取 `registry.yaml`，确认自己是 G00、L01 还是绑定了 `WORK_ID` 的工作项 Thread。
3. 工作项 Thread 读取 `REQUIREMENT_THREAD_TEMPLATE.md` 和所需能力契约，再读取目标阶段 README、`agent.md` 与任务材料。
4. 如果 thread 标题、旧对话和仓库契约冲突，以仓库契约为准并报告冲突。

## 规则分层

- 根目录 `AGENTS.md` 是所有项目 Thread 的公共执行规则。
- `registry.yaml` 提供机器可读的常驻 Thread、工作项、能力、Subagent 和审查策略。
- `G00.md`、`L01.md` 是常驻职责；其余 L/D 文件是能力契约，不提供 thread ID 或独立最终权威。
- [REQUIREMENT_THREAD_TEMPLATE.md](REQUIREMENT_THREAD_TEMPLATE.md) 定义工作项初始化和收口记录。

## Subagent

工作项 Thread 可以直接使用 Subagent 进行调研、实现、测试和审查。允许能力型临时名称，不限制为一个或只读；并行写入必须使用互不重叠的路径，或通过隔离 Worktree 避免冲突。主 Thread 始终负责汇总和最终完成声明。

## 修改治理

1. 先修改 `registry.yaml` 并递增 `version`、更新 `updated_at`。
2. 同步修改 `AGENTS.md`、相关常驻/能力契约、模板和测试。
3. 运行 `python -m pytest 00-governance/repository-tools/tests/test_thread_role_registry.py 00-governance/repository-tools/tests/test_task_classification.py -q`。
4. 最后同步 G00、L01 的标题和绑定；停用的旧 Thread 只归档，不删除历史。

## 当前常驻 Thread

| ID | 名称 | 主轴 |
|---|---|---|
| G00 | 项目治理与工作项协调 | 全局治理 |
| L01 | 需求发现与验证闭环 | `01-discovery/` + `05-validation/` |

## 当前能力

| ID | 能力 | 主轴 |
|---|---|---|
| L02 | 方案分析与产品决策 | `02-solution-analysis/` |
| L03 | 需求文档与规格管理 | `03-requirements/` |
| L06 | 正式交付与演示传播 | `06-delivery/` |
| D01 | 项目主数据与结构底座 | Demo 主数据 |
| D02 | 综合排程算法内核 | Demo 排程求解 |
| D03 | 架梁专项与综合联算 | Demo 架梁领域 |
| D04 | 计划管控与进度预测 | Demo 计划管控 |
| D05 | 工作台与结果体验 | Demo 前端体验 |
| D06 | 架构契约与技术质量 | Demo 契约质量 |
| D07 | AI 参数与资源助手 | Demo AI 助手 |

---
name: speckit-tasks
description: 根据当前规格和实施计划生成可执行的 tasks.md，完成跨产物一致性检查，并输出供用户确认的实施摘要。适用于规划完成后形成任务和实施门禁；不得自动开始实现。
---

# 任务生成与一致性检查

## 工作流

1. 在仓库根目录运行一次：

   ```powershell
   .specify/scripts/powershell/setup-tasks.ps1 -Json
   ```

   使用返回的 `FEATURE_DIR`、`TASKS_TEMPLATE` 和 `AVAILABLE_DOCS`。

2. 读取 `spec.md`、`plan.md`、Constitution，以及当前功能实际存在的 `research.md`、`data-model.md`、`contracts/` 和 `quickstart.md`。
3. 按用户故事和可独立验证的增量组织任务：

   - 每项任务包含稳定编号、目标文件或目录、完成动作和验证方式。
   - 标识可以并行的任务，但不得把有依赖的修改伪装为并行。
   - 建立需求、设计、任务和验证之间的追溯关系。
   - 保留错误态、空态、兼容、数据迁移和诊断任务。

4. 写入 `tasks.md`，不得加入规格和计划没有授权的新能力。
5. 执行一次跨产物一致性检查，至少识别：

   - 需求没有任务。
   - 任务没有需求依据。
   - 数据、契约或范围冲突。
   - Constitution 违反项。
   - 缺少验证或迁移处理。

6. 对有证据支持的遗漏修复一次；涉及业务语义、范围、权限或迁移决策时停止并请求确认。

## 实施门禁

向用户输出：

- `tasks.md` 路径。
- 任务数量、阶段和并行机会。
- 需求覆盖和一致性结论。
- 已知风险、假设和阻塞项。
- 明确提示“尚未开始实施”。

只有用户明确确认 `tasks.md` 和一致性结果后，后续任务才能调用 `$speckit-implement`。

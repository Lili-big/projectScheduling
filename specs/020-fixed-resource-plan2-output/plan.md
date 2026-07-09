# 实施计划：固定资源方案2输出提示

**分支/目录**：`020-fixed-resource-plan2-output` | **日期**：2026-07-09 | **规格**：[spec.md](./spec.md)

**输入**：来自 `specs/020-fixed-resource-plan2-output/spec.md` 的功能规格。

**说明**：本计划只完成设计与任务拆解，不进入代码实现；需等待用户确认 `tasks.md` 和分析结果后再实施。

## 概要

固定资源模拟求解需要稳定输出两类结果：当前资源可查看但目标未满足时，当前资源排程必须作为方案1保留；新增资源分支若最终形成可展示候选，则作为方案2输出；若没有候选，则只展示方案1并明确提示“方案2未输出”。本功能优先复用现有 `ScenarioSolveResult.result` 与 `alternative_results` 结构，通过补强后端结果元数据、验证信息和前端展示判断，避免新增资源失败覆盖当前资源主结果。

## 技术上下文

**语言/版本**：Python 3.x、TypeScript、Node.js。

**主要依赖**：FastAPI、React、OR-Tools CP-SAT、pytest、Vite。

**存储**：不新增持久化存储；方案2输出状态随本次 `ScheduleResult.stats` 与 `objective_breakdown` 返回。

**测试**：后端 `python -m pytest backend/tests/test_scheduler.py`；前端 `npm.cmd run build`；必要时补充定向类型/构建验证。

**目标平台**：本地 FastAPI 后端与 React 前端；Netlify 演示 API 不作为本期主验收面，若计划阶段确认存在同字段镜像再同步。

**项目类型**：桥梁施工排程 Web 应用，涉及后端求解编排、结果契约和前端模拟求解展示。

**性能目标**：不增加固定资源主求解和新增资源分支的求解轮次；只补充状态记录、提示和展示判断，新增处理耗时应相对求解耗时可忽略。

**约束**：
- 不改变 CP-SAT 硬约束、目标函数权重、资源搜索轮次和候选验证规则。
- 不改变“当前资源满足目标时无需新增资源”的路径。
- 不把新增资源诊断、失败候选或最佳努力结果包装成方案2。
- 不新增数据库表、本地配置字段或长期方案存储。
- 不默认修改 `README.md`、提交 git 或推送。

**规模/范围**：
- 后端：`backend/app/scenario.py` 的固定资源分支与资源建议返回元数据。
- 模型契约：复用 `backend/app/models.py` 中 `ScheduleResult.stats`、`objective_breakdown`、`ScenarioSolveResult.alternative_results`。
- 前端：`frontend/src/app/App.tsx` 的方案输出区、诊断摘要和结果状态文案；必要时同步 `frontend/src/types/scheduler.ts` 的轻量类型辅助。
- 测试：`backend/tests/test_scheduler.py` 增加方案1保留、方案2成功、方案2未输出提示的回归用例。

## Constitution 检查

- [x] 需求已建立 `spec.md`，并引用 `AGENTS.md`、`agent.md`、`README.md`、算法交底文档和当前代码事实。
- [x] 算法相关输入、输出、边界、目标达成和异常场景已在规格中定义。
- [x] 前后端契约影响已限定在求解结果元数据和展示口径，不新增持久化模型。
- [x] 方案复用现有固定资源分支、资源建议分支和前端方案列表结构，不引入新依赖。
- [x] 实施前不进入代码修改，待 `tasks.md` 和 `$speckit-analyze` 经用户确认后再实现。

## 项目结构

### 本功能文档

```text
specs/020-fixed-resource-plan2-output/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── fixed-resource-result-output-contract.md
└── tasks.md
```

### 源码结构

```text
backend/
├── app/
│   ├── scenario.py
│   └── models.py
└── tests/
    └── test_scheduler.py

frontend/
└── src/
    ├── app/App.tsx
    └── types/scheduler.ts
```

**结构决策**：本功能是结果输出与展示口径调整，优先在固定资源编排层补充元数据并在前端读取展示；`solver.py` 不应修改，除非实现时发现当前目标达成字段缺失且必须从求解器补齐。

## 复杂度跟踪

| 违反项 | 为什么需要 | 拒绝更简单替代方案的原因 |
|--------|------------|--------------------------|
| 无 | 不适用 | 不适用 |

## Phase 0：研究结论

见 [research.md](./research.md)。关键结论：
- 方案1必须继续绑定当前资源主结果，新增资源失败不能覆盖它。
- 方案2只在新增资源分支形成可展示候选时输出。
- 需要一个稳定、可被前端读取的方案2输出状态，避免依赖零散文案判断。

## Phase 1：设计产物

- [data-model.md](./data-model.md)：定义方案输出状态、方案1、方案2和资源建议状态之间的关系。
- [contracts/fixed-resource-result-output-contract.md](./contracts/fixed-resource-result-output-contract.md)：定义固定资源求解结果中的方案输出契约。
- [quickstart.md](./quickstart.md)：定义本地验证路径和预期结果。

## Phase 1 后 Constitution 复检

- [x] 设计产物仍保持业务结果口径与 CP-SAT 求解规则分离。
- [x] 未新增外部服务、数据库或新依赖。
- [x] 已明确后端测试和前端构建验证。
- [x] 仍需用户确认 `tasks.md` 和 `$speckit-analyze` 后才能实现。

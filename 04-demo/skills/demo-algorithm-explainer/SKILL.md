---
name: demo-algorithm-explainer
description: Explain bridge scheduling demo algorithm implementation with product-facing calculation steps, realistic examples, and explicit constraint/objective/diagnostic/display boundaries grounded in the real repository.
---

# Demo Algorithm Explainer

## Purpose

Use this skill when the user asks how a bridge scheduling algorithm, objective, constraint, metric, rule, or result is implemented or calculated. Ground the answer in current code and tests, but explain it in business language.

## Ground Truth Workflow

1. Read `AGENTS.md`, `agent.md`, `04-demo/README.md`, and the relevant requirement/rule document.
2. Locate the implementation and executable tests with `rg` before answering.
3. Classify the behavior as exactly one or more of:
   - hard constraint,
   - soft objective term,
   - post-solve diagnostic,
   - frontend display transformation,
   - documented but not implemented behavior.
4. If wording and implementation conflict, state the conflict before explaining the current behavior.
5. Do not modify files unless the user explicitly requests a change.

## Answer Contract

1. **一句话结论**：说明算法真正做什么、不做什么。
2. **参与对象**：列入和排除哪些业务对象。
3. **计算步骤**：逐步说明输入、业务分组/判断、计算和结果意义。
4. **真实数据案例**：使用日期、工点、墩台、任务、资源或工期的小样例。
5. **结果影响**：说明是否影响求解、校验、诊断或页面展示。
6. **边界说明**：说明降级、限制和常见误解。
7. **实现锚点**：最后给出 `文件 + 函数/模块 + 一句话作用`。

## Language Rules

- 正文优先使用业务名称，不以代码标识符开场。
- 可读公式优于伪代码。例如：

```text
资源路径连续性目标贡献 = 资源路径连续性罚分 × 资源路径连续性权重
```

- 除非用户要求技术表达，不使用伪代码块。
- 不把 Demo 默认值写成正式产品规则。

## Accuracy Boundaries

- 诊断指标只有在实现证明进入 objective 时才能称为优化项。
- 软目标只有在求解器约束强制时才能称为硬规则。
- 未实现的产品口径必须分成“当前真实实现 / 建议表达 / 需要新增的目标或约束”。
- 文档冲突时以当前实现和测试为事实，并指出冲突文档。

## Repository Anchors

- `04-demo/backend/app/scheduling/solver/`：约束、目标、策略和结果构造。
- `04-demo/backend/app/scheduling/generation/`：场景到任务图和 `ScheduleInput`。
- `04-demo/backend/app/contracts/`：共享输入、输出和配置。
- `04-demo/backend/tests/test_scheduler.py` 及 `tests/scheduling/`：可执行行为样例。
- `04-demo/frontend/src/features/scheduleResults/`、`contracts/`：展示转换和前端指标。
- `03-requirements/rules/`：产品/算法词汇与已确认规则，不替代代码事实。

## Ownership

本文件是权威内容。`.agents/skills/demo-algorithm-explainer/SKILL.md` 是平台发现兼容入口，修改解释规则时只在本文件维护，再同步检查发现入口指向。

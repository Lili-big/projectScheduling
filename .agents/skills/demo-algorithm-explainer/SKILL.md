---
name: demo-algorithm-explainer
description: Explain bridge scheduling demo algorithm implementation when the user asks how an algorithm, objective, constraint, metric, scheduling rule, or calculation is implemented. Use for product-facing answers grounded in the real repo, with step-by-step calculation logic and concrete numeric examples instead of code-level narration.
---

# Demo Algorithm Explainer

> **发现兼容入口**：权威 Skill 已迁入 `04-demo/skills/demo-algorithm-explainer/SKILL.md`。每次调用必须先完整读取该文件并以其规则为准；本入口不再作为路径和规则的权威来源。

## Purpose

Use this skill when the user asks how an algorithm in this bridge scheduling demo is implemented, how a scheduling result is calculated, how an objective or constraint works, or why an algorithm produced a certain outcome.

The answer must feel like a product/engineering handoff explanation: grounded in real code and tests, but written in business language with clear calculation steps and realistic data examples.

## Ground Truth Workflow

1. Read the project rules first when available: `AGENTS.md`, then `agent.md` if more project context is needed.
2. Locate the relevant implementation and tests before answering. Prefer `rg` over broad manual browsing.
3. Check whether the behavior is:
   - a hard constraint that the solver must satisfy,
   - a soft objective term that enters the weighted objective,
   - a diagnostic metric calculated after solving,
   - a frontend display transformation,
   - or only a documented/desired behavior not implemented yet.
4. If user wording conflicts with implementation, say so plainly before explaining the actual behavior.
5. Do not modify code or docs unless the user explicitly asks for a file change.

## Answer Style

Explain each algorithm with this shape:

1. **一句话结论**: State what the algorithm really does and what it does not do.
2. **参与对象**: List the business objects included and excluded from the calculation.
3. **计算步骤**: Break the algorithm into numbered steps. Each step must say:
   - what input is used,
   - what business judgment or grouping is applied,
   - how the value is calculated in product language,
   - what the result means.
4. **真实数据案例**: Provide a small realistic example with dates, task names, resource names, durations, or pier numbers.
5. **结果影响**: Explain whether the result affects solver optimization, validation, diagnostics, or frontend display.
6. **边界说明**: Call out important limits, fallback behavior, and common misunderstandings.

Keep the explanation concise, but do not skip calculation logic.

## Language Rules

- Use business names in the main text, such as "实际计划开始时间", "理想完成时间", "控制缓冲不足天数", "资源路径连续性罚分".
- Avoid code identifiers as the main explanation. Do not lead with function names, model variables, or helper names.
- Mention file/function references only briefly at the end or when the user asks for implementation anchors.
- Prefer "系统先...然后..." over "代码调用...".
- Use formulas only when they are readable as business formulas.
- Do not use pseudo-code blocks unless the user explicitly asks for technical expression.

Recommended formula style:

```text
资源路径连续性目标贡献 =
资源路径连续性罚分 × 资源路径连续性权重
```

Avoid code-like expressions such as:

```text
penalty = max(0, abs(a - b) - 1)
```

Rewrite them as:

```text
同幅跨墩跳跃罚分 =
两个墩台编号之间相隔的位置数 - 1

如果两个任务是相邻墩台，罚分为 0。
```

## Example Pattern

For a question like "资源连续性算法是怎么算的", answer in this style:

```markdown
一句话结论：资源连续性不是硬约束，而是一个软目标加诊断指标。系统不会绝对禁止跳墩或跳幅，但会让更连续的资源路径在精排目标里更占优。

1. 确定参与计算的资源路径

系统按命名资源统计任务顺序。例如：

| 资源 | 任务顺序 |
| --- | --- |
| 旋挖钻 1 | 左幅 1#墩桩基 -> 左幅 4#墩桩基 -> 右幅 4#墩桩基 |

2. 计算同幅跨墩跳跃

左幅 1#墩到左幅 4#墩，中间跨过 2#、3#附近的连续推进节奏。

同幅跨墩跳跃罚分 = 2。

3. 计算左右幅切换

左幅 4#墩到右幅 4#墩发生一次左右幅切换。

左右幅切换罚分 = 1。

4. 汇总目标贡献

资源路径连续性罚分 = 2 + 1 = 3。

如果当前权重是 3000，则目标贡献 = 3 × 3000 = 9000。

结果影响：该值进入精排目标函数。罚分越低，表示资源越倾向于按同幅、邻近墩台连续推进。
```

## Accuracy Boundaries

- Never describe a diagnostic metric as an optimized objective unless the implementation proves it enters the objective.
- Never describe a soft objective as a hard rule unless the solver enforces it as a constraint.
- If a product-friendly algorithm requested by the user is not implemented, distinguish:
  - "当前真实实现",
  - "用户建议的表达方式",
  - "如果要实现该口径，需要新增的目标或约束".
- When explaining outdated or conflicting docs, prefer the current implementation and tests as ground truth, and name the conflict.

## Repo Anchors

In this project, algorithm answers commonly need these anchors:

- `04-demo/backend/app/scheduling/solver/`: solver constraints, objectives, diagnostics, and result construction.
- `04-demo/backend/app/scheduling/generation/`: scenario-to-task conversion.
- `04-demo/backend/app/contracts/`: shared inputs, outputs, strategy config, and objective definitions.
- `04-demo/backend/tests/test_scheduler.py`: executable examples and expected behavior.
- `04-demo/frontend/src/features/scheduleResults/` and `04-demo/frontend/src/contracts/`: display parsing and frontend metrics.
- `03-requirements/rules/`: product and algorithm documents, useful for vocabulary but not always implementation truth.

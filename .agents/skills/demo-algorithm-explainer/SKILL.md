---
name: demo-algorithm-explainer
description: Explain bridge scheduling algorithms, constraints, objectives, diagnostics, and display calculations from current repository code and tests. Use for implementation-grounded algorithm or metric explanations, not product proposals.
---

# Demo Algorithm Explainer

1. Use `rg` to locate the smallest relevant implementation and executable test. Read `agent.md` or product rules only when code terminology is insufficient; do not reread unchanged context.
2. Classify each behavior as a hard constraint, soft objective, post-solve diagnostic, frontend transformation, or documented-only rule. State code/document conflicts before explaining them.
3. Explain the current behavior in business language: conclusion, participating objects, calculation steps, one realistic example, result impact, limits, and `file + function/module + role` anchors.
4. Do not call a diagnostic an objective or a soft objective a hard rule unless the solver proves it. Separate current behavior from recommendations and unimplemented product intent.
5. Stop when the cited code and tests are sufficient. Do not modify files unless the user asks for a change.

Primary anchors: `04-demo/backend/app/scheduling/`, `04-demo/backend/app/contracts/`, `04-demo/backend/tests/`, `04-demo/frontend/src/features/scheduleResults/`, and `03-requirements/rules/`.

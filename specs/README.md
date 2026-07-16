# Spec Kit 规格索引

规格目录保持历史编号和路径，不移动、不重编号。重复的 `002` 是历史事实。状态按当前 `tasks.md` 统计：`completed` 为任务全勾选，`active_partial` 为仍有未完成任务，`draft` 为尚未生成任务清单。

| 规格 | 状态 | 任务 |
| --- | --- | ---: |
| `001-cp-sat-fixed-resource` | completed | 65/65 |
| `002-ai-parameter-assistant` | completed | 58/58 |
| `002-objective-function-config` | completed | 31/31 |
| `003-refinement-milestone-objective` | completed | 28/28 |
| `004-normal-work-balance` | completed | 25/25 |
| `005-best-effort-refinement` | completed | 24/24 |
| `007-objective-metric-config` | completed | 42/42 |
| `008-objective-model-gating` | completed | 39/39 |
| `009-remove-resource-workload-balance` | completed | 22/22 |
| `010-remove-unconfigured-normal-balance` | completed | 22/22 |
| `011-drill-group-two-stage-refinement` | completed | 66/66 |
| `012-stage2-makespan-relaxation` | completed | 17/17 |
| `013-stage2-visible-distance-pruning` | completed | 10/10 |
| `016-continuous-beam-team-span` | completed | 37/37 |
| `017-stage1-route-continuity` | completed | 44/44 |
| `018-unified-target-solve` | completed | 59/59 |
| `019-pressure-resource-search` | active_partial | 30/32 |
| `020-fixed-resource-plan2-output` | completed | 34/34 |
| `021-resource-path-unbounded` | completed | 31/31 |
| `022-ai-resource-scheduling-assistant` | active_partial | 74/76 |
| `023-stepwise-resource-solve` | completed | 21/21 |
| `024-navigation-ai-comparison` | completed | 21/21 |
| `025-llm-project-context-export` | completed | 14/14 |
| `026-resource-plan-policy-baseline` | completed | 30/30 |
| `027-baseline-progress-forecast` | completed | 56/56 |
| `028-ai-strict-resource-solve` | completed | 34/34 |
| `029-ai-status-delay-consolidation` | completed | 29/29 |
| `030-task-parameter-quantity-split` | completed | 32/32 |
| `031-progress-quantity-consistency` | active_partial | 25/29 |
| `032-ai-resource-solve-timeout` | completed | 15/15 |
| `033-ai-two-stage-resource-optimization` | completed | 38/38 |
| `034-ai-resource-solve-60s-budget` | completed | 17/17 |
| `035-ai-idle-only-second-stage` | completed | 26/26 |
| `036-ai-single-stage-solve` | completed | 24/24 |
| `037-ai-solve-15s-budget` | completed | 15/15 |
| `038-ai-solve-stability` | draft | 无 tasks.md |
| `039-progress-actual-date-defaults` | completed | 20/20 |
| `040-progress-forecast-closed-loop` | completed | 40/40 |
| `041-girder-scheduling-integration` | active_partial | 74/95 |
| `042-repo-architecture-modernization` | active_partial | 实施中 |
| `043-unified-workpoint-structure` | draft | 仅有检查表，无 spec.md/tasks.md |

使用规则：先读目标目录的 `spec.md`、`plan.md` 和 `tasks.md`。`completed` 只表示该规格任务清单已勾选，不替代当前代码验证；`active_partial` 中未完成项不得在 README/agent 中写成已实现。

# Spec Kit 规格索引

规格目录保持历史编号和路径，不移动、不重编号。重复的 `002` 是历史事实。规格状态按当前 `tasks.md` 统计：`completed` 为任务全勾选，`active_partial` 为仍有未完成任务，`draft` 为尚未生成任务清单。阶段文档和成果另使用 `current`、`draft`、`superseded`、`historical` 表示当前版、草稿、被替代版和历史证据；两套状态不混用。

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
| `045-lifecycle-workspace-governance` | completed | 77/77 |
| `046-unified-abutment-task-rules` | completed | 40/40 |
| `047-workpoint-resource-configuration` | completed | 40/40 |
| `048-workpoint-first-resource-allocation` | active_partial | 57/59 |
| `051-girder-plan-simulation` | completed | 47/47 |
| `054-single-workpoint-solve` | active_partial | 26/27 |
| `056-unified-fixed-resource-solve` | active_partial | 0/33 |
| [`063-road-pavement-adaptation`](./063-road-pavement-adaptation/spec.md) | active_partial | 28/29，首版与自动样例验证完成；待客户数据 |
| [`064-pavement-roadbed-handover`](./064-pavement-roadbed-handover/spec.md) | completed | 10/10，路床三态已落地；原21段84任务排程口径已由067更新，历史证据保留 |
| [`065-pavement-shared-fleets`](./065-pavement-shared-fleets/spec.md) | completed | 10/10，共享机组配置与求解验证通过；客户已设共享1套 |
| [`066-pavement-task-preview`](./066-pavement-task-preview/spec.md) | completed | 10/10，任务自动准备与统一工序链已验证；层间FS+N、排除末尾养生 |
| [`067-pavement-pending-last`](./067-pavement-pending-last/spec.md) | completed | 11/11；25段100任务纳入，4段严格后置及条件日期已验证；客户15秒仍UNKNOWN |
| [`068-pavement-greedy-cpsat`](./068-pavement-greedy-cpsat/spec.md) | completed | 13/13；贪心初解＋CP-SAT限时优化规划完成，已完成实施 |
| [`069-pavement-live-optimization`](./069-pavement-live-optimization/spec.md) | completed | 14/14；8worker＋内置LNS、15秒预算与实时最好方案已接入；100任务实测324→310天，未证明最优，详见实施证据 |
| [`070-pavement-results-visualization`](./070-pavement-results-visualization/spec.md) | completed | 15/15；持续求解提示、两级表格横道与机组里程轴已接入，21项定向测试及宽窄屏验收通过，既有仓库检查问题见任务证据 |
| [`071-pavement-resource-timeline`](./071-pavement-resource-timeline/spec.md) | active_partial | 8/9；按米厚度约束修订及资源时间图完成，87项后端/21项前端测试、构建与宽窄屏验收通过；资源行含作业/转场/空闲及最长空闲定位，当前19段76任务；仅底部精简T005b暂缓，既有依赖审批/9处历史引用问题留证 |
| [`072-pavement-crew-tl-flow`](./072-pavement-crew-tl-flow/spec.md) | completed | 8/8；双幅共享固定里程轴、镜像实际日期、全程箭线及局部高亮/缩放/导航已接入；27项测试、构建和真实76工序宽窄屏验证通过，100工序投影/双机渲染及浏览器限制见任务证据 |
| [`073-pavement-fleet-pending-last`](./073-pavement-fleet-pending-last/spec.md) | completed | 8/8；初解、CP-SAT 与校验统一按实际机组后置，144 项后端及 21 项前端用例通过；既有架构/治理差异详见 tasks.md |
| [`074-pavement-idle-optimization`](./074-pavement-idle-optimization/spec.md) | completed | 11/11；独立窝工优化、固定工期上限与实时保底已接入，144项后端/47项前端验收及构建通过；既有架构/治理差异见tasks.md |

使用规则：先读目标目录的 `spec.md`、`plan.md` 和 `tasks.md`。`completed` 只表示该规格任务清单已勾选，不替代当前代码验证；`active_partial` 中未完成项不得在 README/agent 中写成已实现。

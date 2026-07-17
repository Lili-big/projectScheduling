# Feature Specification: CP-SAT Fixed Resource Scheduling

**Feature Branch**: `[001-cp-sat-fixed-resource]`

**Created**: 2026-07-01

**Status**: Draft

**Input**: User description: "基于当前项目已有文档，梳理并规格化 CP-SAT 固定资源算法实现；第一期包含固定资源满足后的精排；当前资源不满足时保留参考排程；最少资源候选验证通过后也要调用精排重算；同结构同工艺规则保留；控制目标来源限于任务控制属性和现浇连续梁规则。"

## Source & Review Context *(mandatory)*

- **Source Documents**:
  - `AGENTS.md`
  - `agent.md`
  - `README.md`
  - `docs/CP-SAT固定资源算法实现需求文档_v1.0.md`
  - `docs/CP-SAT_MVP算法实现文档_v1.0.md`
  - `docs/精排目标函数算法需求文档_v2.2.md`
  - `docs/资源配置页面需求文档_v1.0.md`
  - `docs/固定资源满足分支详细排程算法文档_v1.1.md`
- **Review Decision**: User-confirmed Spec Kit progression after requirement discovery. The user confirmed that the first phase includes fixed-resource refinement, preserves delayed schedules, keeps same-structure same-process resource rules, treats minimum-resource results as verified candidates rather than global optimum, and reruns refinement for verified minimum-resource candidates.
- **Demo/Code Facts Used**: Current project handbook defines the scheduling boundary as `ScenarioInput -> GeneratedScheduleInput / ScheduleInput -> ScheduleResult / ScenarioSolveResult`. Current solver orchestration already distinguishes task generation, fixed-resource shortest scheduling, hard milestone evaluation, refinement, resource recommendations, and alternative results.
- **Out of Scope**: Resource-cost optimization as the main flow, actual-progress locking, dynamic rescheduling, plan publishing and approval, user-edited mathematical objectives, strict lexicographic optimization, real transfer-time modeling, editable control-target configuration, resource calendar editing, resource-pool creation or deletion, and database schema replacement.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Check Current Resources Against Mandatory Milestones (Priority: P1)

As a planning engineer, I want to calculate the shortest reference schedule under the current resource quantities so that I can know whether the current equipment, templates, or crews can meet mandatory milestones.

**Why this priority**: This is the primary business decision. Without it, users cannot judge whether the current resource plan is acceptable.

**Independent Test**: Can be tested by preparing a project scenario with valid tasks, logic, resources, and mandatory milestones, then running fixed-resource scheduling and checking the milestone status, predicted dates, delay days, schedule tasks, and resource allocations.

**Acceptance Scenarios**:

1. **Given** a scenario where current resources can meet all matched mandatory milestones, **When** the user runs fixed-resource scheduling, **Then** the system returns a successful main result with schedule tasks, resource allocations, milestone results, and a clear indication that no resource increase is needed.
2. **Given** a scenario where current resources delay at least one matched mandatory milestone, **When** the user runs fixed-resource scheduling, **Then** the system keeps the current-resource reference schedule and reports which mandatory milestones are delayed, by how many days, and when they are expected to finish.

---

### User Story 2 - Produce Refined Plans When Resources Are Sufficient (Priority: P1)

As a planning engineer, I want the system to refine schedules that already satisfy mandatory milestones so that the plan is suitable for resource-lane review, construction organization discussion, and monthly planning.

**Why this priority**: The first phase must not stop at "resources are enough"; users need a detailed plan that is explainable and reviewable.

**Independent Test**: Can be tested by using a scenario whose current resources satisfy mandatory milestones and confirming that the final main result is a refined named-resource schedule, or a clearly marked fallback reference schedule if refinement cannot complete.

**Acceptance Scenarios**:

1. **Given** current resources satisfy all matched mandatory milestones, **When** refinement succeeds, **Then** the main result identifies itself as the refined current-resource schedule and includes business indicators for mandatory milestone status, control-buffer status, ordinary-work balance, and resource-path status.
2. **Given** current resources satisfy all matched mandatory milestones but refinement cannot produce a usable result within the allowed run, **When** the system returns a result, **Then** it falls back to the fixed-resource reference schedule and clearly explains that the resource sufficiency judgment remains valid while refinement did not complete.

---

### User Story 3 - Recommend Minimum Resources and Rerun Refinement (Priority: P2)

As a planning engineer, I want the system to recommend a verified resource-increase candidate when current resources delay mandatory milestones so that I can compare the current delayed plan with a feasible improved plan.

**Why this priority**: Resource recommendations are the natural next decision after a delayed current-resource schedule, but they must be presented as verified candidates rather than guaranteed global optimum.

**Independent Test**: Can be tested by using a scenario where current resources are insufficient and configured maximum quantities are sufficient, then confirming that the system returns the delayed current-resource result plus a verified minimum-resource candidate whose schedule has been refined or clearly marked as a refinement fallback.

**Acceptance Scenarios**:

1. **Given** current resources delay mandatory milestones and the theoretical critical path can still meet the target, **When** maximum configured resources are sufficient, **Then** the system returns recommended resource counts that do not exceed each resource pool's maximum quantity.
2. **Given** recommended resource counts are verified as feasible, **When** the candidate plan is returned, **Then** the candidate plan is recomputed by the refinement flow and marked as a minimum-resource refined candidate.
3. **Given** recommended resource counts are feasible but candidate refinement cannot complete, **When** the candidate plan is returned, **Then** the system falls back to the feasible verification schedule and clearly marks the fallback source.

---

### User Story 4 - Preserve Same-Structure Same-Process Resource Rules (Priority: P2)

As a planning engineer, I want resource continuity and parallel limits for the same structure and same process to be respected so that the result does not overstate parallel construction capability or split strongly continuous work unrealistically.

**Why this priority**: These rules materially affect whether the schedule is credible, especially for resources such as drilling equipment, templates, and continuous-beam teams.

**Independent Test**: Can be tested by preparing tasks under the same structure and same process with configured binding or parallel-limit rules, then verifying that both current-resource and minimum-resource candidate schedules obey those rules.

**Acceptance Scenarios**:

1. **Given** a resource pool requires same-structure same-process binding, **When** tasks from the same structure and process are scheduled, **Then** they are assigned consistently according to the configured binding rule.
2. **Given** a resource pool has a same-structure same-process parallel limit, **When** multiple eligible tasks could otherwise run together, **Then** the schedule never exceeds the configured limit.

---

### User Story 5 - Explain Control Targets and Plan Sources (Priority: P3)

As a planning engineer, I want to know why a task is treated as control-related and where each displayed schedule comes from so that I can trust and discuss the plan with the project team.

**Why this priority**: Result interpretation is needed for adoption, but it depends on the core current-resource and minimum-resource flows.

**Independent Test**: Can be tested by using scenarios with task control attributes and cast-in-place continuous beams, then confirming that the output identifies control-target sources and distinguishes current-resource reference, current-resource refinement, minimum-resource refinement, and fallback schedules.

**Acceptance Scenarios**:

1. **Given** a task is explicitly marked with a control attribute, **When** refinement analyzes control targets, **Then** the result identifies that task as control-related with the task attribute as its source.
2. **Given** a cast-in-place continuous beam exists in the scenario, **When** refinement analyzes control targets, **Then** related continuous-beam tasks are treated as control-related according to the project rule.
3. **Given** a schedule is displayed, **When** the user reviews result metadata, **Then** the schedule source is clear enough to distinguish refined results from reference or fallback results.

### Edge Cases

- Current resource scheduling returns no usable reference schedule: the system reports that milestone and recommendation evaluation cannot continue and does not show a misleading plan.
- Mandatory milestones do not match any generated tasks: affected milestones are marked as not evaluated and do not silently pass or fail the whole scenario.
- Current resources delay mandatory milestones, but the theoretical critical path already misses the target: the system does not recommend more resources and explains that resource increases cannot solve the target-date conflict.
- Current resources delay mandatory milestones, and maximum configured resources still cannot meet the target: the system reports the resource upper-bound failure and does not output an unverified candidate.
- Recommended resource counts pass feasibility verification, but refinement fails or times out: the minimum-resource candidate falls back to the verified feasible schedule and clearly identifies the fallback.
- A resource pool is disabled or has zero available quantity: related tasks are treated according to configured resource availability rules and diagnostics explain the effect.
- Multiple mandatory milestones exist: the resource sufficiency decision considers all matched mandatory milestones, not only the first one.
- Same-structure same-process binding or parallel-limit rules are absent: the system does not invent hidden restrictions based only on resource type.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST generate or reuse a complete schedulable task graph before fixed-resource scheduling, including task durations, relationships, candidate resource types, resources, milestones, and validation diagnostics.
- **FR-002**: System MUST calculate a current-resource reference schedule using the current resource quantities configured for each enabled limited resource pool.
- **FR-003**: System MUST evaluate all matched mandatory milestones after the current-resource reference schedule is produced.
- **FR-004**: System MUST preserve and return the current-resource reference schedule when current resources delay mandatory milestones, including expected finish dates, delay days, resource allocations, and milestone diagnostics.
- **FR-005**: System MUST clearly identify when current resources satisfy all matched mandatory milestones and when they do not.
- **FR-006**: System MUST run refinement for the current-resource plan when the current-resource reference schedule satisfies all matched mandatory milestones.
- **FR-007**: System MUST return a clearly marked fallback current-resource reference schedule if current-resource refinement cannot produce a usable refined plan.
- **FR-008**: System MUST avoid resource-increase recommendations when the theoretical no-wait critical path cannot satisfy the relevant mandatory milestone targets.
- **FR-009**: System MUST use configured maximum resource quantities as the upper bound when producing minimum-resource recommendations.
- **FR-010**: System MUST present minimum-resource recommendations as verified candidate quantities, not as guaranteed global optimum.
- **FR-011**: System MUST verify recommended resource quantities by producing a feasible schedule before returning them as a candidate.
- **FR-012**: System MUST rerun refinement for a verified minimum-resource candidate before displaying it as the preferred candidate plan.
- **FR-013**: System MUST return a clearly marked fallback candidate schedule if minimum-resource refinement cannot produce a usable refined plan after feasibility verification.
- **FR-014**: System MUST ensure recommended resource quantities never exceed their configured maximum quantities and never fall below current quantities when reported as additions.
- **FR-015**: System MUST enforce configured same-structure same-process binding rules in both current-resource refinement and minimum-resource candidate refinement.
- **FR-016**: System MUST enforce configured same-structure same-process parallel limits wherever those limits are configured.
- **FR-017**: System MUST NOT impose same-structure same-process binding or parallel limits solely because of a resource type when the corresponding configuration is absent.
- **FR-018**: System MUST limit first-phase control-target sources to explicit task control attributes and cast-in-place continuous-beam rule recognition.
- **FR-019**: System MUST NOT treat all tasks inside a milestone evaluation scope as control targets merely because they are used to evaluate a milestone.
- **FR-020**: System MUST identify each returned schedule's source, at minimum distinguishing current-resource reference, current-resource refinement, current-resource refinement fallback, minimum-resource refinement, and minimum-resource refinement fallback.
- **FR-021**: System MUST invalidate or require regeneration of stale task graphs, schedules, and scenario comparisons after resource quantities, resource maximums, resource enabled states, process choices, productivity, logic rules, milestones, or control-relevant scenario data change.
- **FR-022**: System MUST provide user-understandable diagnostics for generation errors, delayed mandatory milestones, critical-path infeasibility, resource upper-bound infeasibility, unresolved recommendations, refinement fallback, and unmatched milestones.
- **FR-023**: System MUST keep fixed-resource scheduling, minimum-resource recommendations, and refinement results comparable in the result view by returning consistent milestone, resource, schedule-source, and diagnostic information.

### Key Entities *(include if feature involves data)*

- **Scenario**: The complete business input for one scheduling run, including project structure, process choices, productivity, logic rules, resource configuration, milestones, strategy settings, and run budget.
- **Task Graph**: The schedulable representation produced from the scenario, including tasks, durations, relationships, resource candidates, named resources, and generation diagnostics.
- **Resource Pool**: A project or scenario-level resource configuration with current quantity, maximum quantity, enabled state, resource mode, calendar reference, and same-structure same-process rules.
- **Mandatory Milestone**: A target date that must be evaluated against a task scope and used to decide whether current resources are sufficient.
- **Current-Resource Reference Schedule**: The shortest schedule produced with current resource quantities and used as the first sufficiency judgment.
- **Refined Schedule**: A named-resource detailed plan that remains feasible while improving control-node protection, ordinary-work balance, and resource organization explainability.
- **Minimum-Resource Candidate**: A verified resource-increase candidate that meets milestone targets within configured maximum quantities and is refined again before display when possible.
- **Schedule Source**: A user-visible classification explaining whether the schedule is a reference, refined result, minimum-resource refined candidate, or fallback.
- **Diagnostic Message**: A user-facing or tester-facing explanation of why a result succeeded, delayed, fell back, could not recommend resources, or could not evaluate a milestone.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For a valid scenario with current resources sufficient for all matched mandatory milestones, users can identify milestone sufficiency, final plan dates, schedule source, and resource allocations from one scheduling result.
- **SC-002**: For a valid scenario where current resources delay at least one matched mandatory milestone, users can see the current-resource reference schedule and the delayed milestone name, target date, expected date, and delay days.
- **SC-003**: In scenarios where maximum configured resources can meet the target, every returned minimum-resource candidate includes verified recommended quantities, added quantities, maximum quantities, a candidate schedule, and a schedule-source label.
- **SC-004**: In scenarios where resource increases cannot solve the delay, the system returns a clear "not solved by resources" or "resource upper bound insufficient" explanation and does not return an unverified candidate.
- **SC-005**: In same-structure same-process test scenarios, schedule outputs never violate configured binding or parallel-limit rules.
- **SC-006**: Result interpretation distinguishes refined schedules from fallback schedules in 100% of returned current-resource and minimum-resource candidate results.
- **SC-007**: Test coverage includes at least one passing case for current-resource sufficient refinement, current-resource delayed schedule preservation, minimum-resource refined candidate, critical-path infeasible no-recommendation, upper-bound infeasible no-candidate, and same-structure same-process rule enforcement.
- **SC-008**: Planning users can compare the current delayed plan and the recommended candidate plan without needing to infer hidden result sources or manually calculate milestone delay.

## Assumptions

- The first implementation phase uses existing project scheduling data shapes and result concepts rather than introducing a separate product model.
- Current-resource insufficient scenarios do not attempt to force a refined current-resource plan that satisfies mandatory milestones; they preserve the delayed reference schedule and use resource recommendation to produce a feasible candidate when possible.
- Minimum-resource recommendations are verified candidates for the first phase and are not represented as global optimum across all future business constraints.
- Minimum-resource candidate refinement uses the same business interpretation rules as current-resource refinement so the two plans are comparable.
- All matched mandatory milestones participate in sufficiency evaluation.
- The first phase treats Python/FastAPI-backed local scheduling as the authoritative behavior. Any deployed demo or mirror implementation must either align with the same user-visible contract or clearly degrade without contradicting it.
- Existing resource configuration remains the source of current quantities, maximum quantities, enabled states, same-structure binding, and same-structure parallel limits.
- Control-target configuration UI is out of scope for this phase; control targets come only from task control attributes and cast-in-place continuous-beam recognition.

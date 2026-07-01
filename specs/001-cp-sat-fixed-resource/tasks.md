# Tasks: CP-SAT Fixed Resource Scheduling

**Input**: Design documents from `specs/001-cp-sat-fixed-resource/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/](contracts/), [quickstart.md](quickstart.md)

**Tests**: Required. This feature changes scheduling algorithms, resource constraints, shared result contracts, and frontend display behavior.

**Organization**: Tasks are grouped by user story so each story can be implemented and validated independently after the foundational phase.

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Establish the baseline files, vocabulary, and regression harness before changing scheduling behavior.

- [X] T001 Review existing fixed-resource and minimum-resource tests in `backend/tests/test_scheduler.py` and mark reusable fixtures or gaps for this feature.
- [X] T002 [P] Review current result display labels and recommendation rendering in `frontend/src/app/App.tsx`.
- [X] T003 [P] Review current scheduler frontend types in `frontend/src/types/scheduler.ts` against `specs/001-cp-sat-fixed-resource/contracts/fixed-resource-scheduling-contract.md`.
- [X] T004 [P] Review Netlify or demo scheduling behavior in `netlify/demo-functions/api.mts` and document whether it must align or degrade for this feature.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Define shared result categories and reusable validation helpers that all user stories depend on.

**CRITICAL**: No user story implementation should start until this phase is complete.

- [X] T005 Add backend test helpers for constructing milestone-sensitive scheduling scenarios in `backend/tests/test_scheduler.py`.
- [X] T006 Add backend assertions for schedule source, recommendation status, milestone delay, and alternative-result shape in `backend/tests/test_scheduler.py`.
- [X] T007 Normalize fixed-resource schedule-source and recommendation-status constants or helper functions in `backend/app/scenario.py`.
- [X] T008 Ensure `ScheduleResult` metadata writes schedule source and recommendation status consistently to both `stats` and `objective_breakdown` in `backend/app/scenario.py`.
- [X] T009 Update frontend schedule-source label mapping to include current-resource reference, current-resource refinement, current-resource fallback, minimum-resource refinement, and minimum-resource fallback in `frontend/src/app/App.tsx`.
- [X] T010 Update frontend scheduler types for any missing metadata fields required by the result contract in `frontend/src/types/scheduler.ts`.

**Checkpoint**: Result source and recommendation metadata can be asserted consistently before feature branches change behavior.

---

## Phase 3: User Story 1 - Check Current Resources Against Mandatory Milestones (Priority: P1) MVP

**Goal**: Users can run fixed-resource scheduling and see whether current resources meet mandatory milestones, including a preserved delayed schedule when they do not.

**Independent Test**: A scenario with sufficient current resources returns milestone success; a scenario with insufficient current resources preserves tasks, resource allocations, delayed milestone details, and recommendation status.

### Tests for User Story 1

- [X] T011 [P] [US1] Add a backend test for current resources satisfying all matched mandatory milestones in `backend/tests/test_scheduler.py`.
- [X] T012 [P] [US1] Add a backend test for current resources delaying a mandatory milestone while preserving an inspectable schedule in `backend/tests/test_scheduler.py`.
- [X] T013 [P] [US1] Add a backend test for unmatched mandatory milestones being marked not evaluated without silently passing or failing the whole scenario in `backend/tests/test_scheduler.py`.

### Implementation for User Story 1

- [X] T014 [US1] Ensure fixed-resource scheduling evaluates all matched mandatory milestones after the current-resource reference schedule in `backend/app/scenario.py`.
- [X] T015 [US1] Preserve current-resource scheduled tasks, resource allocations, and milestone delay diagnostics when mandatory milestones are delayed in `backend/app/scenario.py`.
- [X] T016 [US1] Ensure delayed current-resource results report expected date, target date, and delay days for each late mandatory milestone in `backend/app/scenario.py`.
- [X] T017 [US1] Ensure scenario metrics and diagnostics include current-resource sufficiency and delay state in `backend/app/scenario.py`.
- [X] T018 [US1] Update result rendering so delayed current-resource schedules are visible but not presented as milestone-success plans in `frontend/src/app/App.tsx`.

**Checkpoint**: User Story 1 is fully functional and testable independently.

---

## Phase 4: User Story 2 - Produce Refined Plans When Resources Are Sufficient (Priority: P1)

**Goal**: Users receive a named-resource refined plan when current resources meet mandatory milestones, or a clearly labeled fallback when refinement cannot complete.

**Independent Test**: A sufficient-current-resource scenario returns a refined schedule source and refinement indicators; a forced refinement-fallback scenario returns the current-resource reference schedule with fallback explanation.

### Tests for User Story 2

- [X] T019 [P] [US2] Add a backend test for successful current-resource refinement after milestone sufficiency in `backend/tests/test_scheduler.py`.
- [X] T020 [P] [US2] Add a backend test for current-resource refinement fallback preserving milestone sufficiency in `backend/tests/test_scheduler.py`.
- [X] T021 [P] [US2] Add a frontend-facing metadata assertion for current-resource refinement labels in `backend/tests/test_scheduler.py`.

### Implementation for User Story 2

- [X] T022 [US2] Ensure current-resource sufficient branch calls refinement with hard milestone enforcement in `backend/app/scenario.py`.
- [X] T023 [US2] Ensure successful current-resource refinement writes `current_resources_control_priority_balanced` source and `not_needed` recommendation status in `backend/app/scenario.py`.
- [X] T024 [US2] Ensure current-resource refinement fallback writes fallback source, fallback reason, and not-needed recommendation status in `backend/app/scenario.py`.
- [X] T025 [US2] Ensure refinement outputs or fallback diagnostics include control-buffer, ordinary-balance, and resource-path default status entries when detailed metrics are unavailable in `backend/app/scenario.py`.
- [X] T026 [US2] Update frontend current-resource result badges and explanatory text for refined versus fallback plans in `frontend/src/app/App.tsx`.

**Checkpoint**: User Stories 1 and 2 work independently and provide the first-phase current-resource loop.

---

## Phase 5: User Story 3 - Recommend Minimum Resources and Rerun Refinement (Priority: P2)

**Goal**: Users can compare a delayed current-resource plan with a verified minimum-resource candidate that has been refined again when possible.

**Independent Test**: An insufficient-current-resource scenario with enough maximum resources returns recommended counts, a verified candidate schedule, and a minimum-resource refinement source or fallback source.

### Tests for User Story 3

- [X] T027 [P] [US3] Add a backend test for critical-path infeasible current-resource delay producing no resource recommendation in `backend/tests/test_scheduler.py`.
- [X] T028 [P] [US3] Add a backend test for maximum-resource upper-bound infeasible delay producing no candidate plan in `backend/tests/test_scheduler.py`.
- [X] T029 [P] [US3] Add a backend test for verified minimum-resource recommendation quantities and candidate alternative result in `backend/tests/test_scheduler.py`.
- [X] T030 [P] [US3] Add a backend test that verified minimum-resource candidates rerun refinement before display in `backend/tests/test_scheduler.py`.
- [X] T031 [P] [US3] Add a backend test for minimum-resource refinement fallback after feasibility verification in `backend/tests/test_scheduler.py`.

### Implementation for User Story 3

- [X] T032 [US3] Keep critical-path and maximum-resource prechecks ahead of resource search in `_fixed_resource_recommendation` in `backend/app/scenario.py`.
- [X] T033 [US3] Ensure recommended resource counts include current, recommended, added, and maximum quantities in `backend/app/scenario.py`.
- [X] T034 [US3] Add a recommendation verification step that produces a feasible schedule before returning a candidate in `backend/app/scenario.py`.
- [X] T035 [US3] Rerun refinement for verified minimum-resource candidates and label successful candidates as `minimum_resources_control_priority_balanced` in `backend/app/scenario.py`.
- [X] T036 [US3] Return verified feasible candidate schedules as `minimum_resources_refinement_fallback` when candidate refinement fails in `backend/app/scenario.py`.
- [X] T037 [US3] Ensure minimum-resource alternative results carry generated input, result, milestone results, diagnostics, metrics, and role in `backend/app/scenario.py`.
- [X] T038 [US3] Update frontend alternative-result rendering to show minimum-resource refined versus fallback candidate sources in `frontend/src/app/App.tsx`.
- [X] T039 [US3] Update frontend recommendation count display to avoid implying global optimum in `frontend/src/app/App.tsx`.

**Checkpoint**: User Story 3 provides a complete delayed-current-resource plus verified-candidate comparison loop.

---

## Phase 6: User Story 4 - Preserve Same-Structure Same-Process Resource Rules (Priority: P2)

**Goal**: Resource binding and parallel-limit rules are respected in current-resource and minimum-resource refined schedules.

**Independent Test**: A scenario with same-structure same-process binding or parallel-limit configuration never violates those rules; absent rules do not create hidden restrictions.

### Tests for User Story 4

- [X] T040 [P] [US4] Add a backend test for same-structure same-process binding in refined current-resource schedules in `backend/tests/test_scheduler.py`.
- [X] T041 [P] [US4] Add a backend test for same-structure same-process parallel limits in refined current-resource schedules in `backend/tests/test_scheduler.py`.
- [X] T042 [P] [US4] Add a backend test proving absent same-structure rules do not impose hidden resource-type restrictions in `backend/tests/test_scheduler.py`.
- [X] T043 [P] [US4] Add a backend test for same-structure rules in minimum-resource candidate refinement in `backend/tests/test_scheduler.py`.

### Implementation for User Story 4

- [X] T044 [US4] Trace same-structure binding and parallel-limit fields from resource pools to generated named resources in `backend/app/scenario.py`.
- [X] T045 [US4] Enforce same-structure same-process binding during named-resource refinement in `backend/app/solver.py`.
- [X] T046 [US4] Enforce same-structure same-process parallel limits during current-resource and minimum-resource refined scheduling in `backend/app/solver.py`.
- [X] T047 [US4] Ensure capacity/reference scheduling does not overstate configured same-structure parallel capability where the contract requires the limit in `backend/app/solver.py`.
- [X] T048 [US4] Surface same-structure rule diagnostics or explanations when relevant in schedule result metadata in `backend/app/solver.py`.

**Checkpoint**: User Story 4 preserves business credibility of resource continuity and parallelism.

---

## Phase 7: User Story 5 - Explain Control Targets and Plan Sources (Priority: P3)

**Goal**: Users can understand why tasks are control-related and where each displayed schedule comes from.

**Independent Test**: Scenarios with task control attributes and cast-in-place continuous beams identify control sources; all displayed schedules show stable source labels.

### Tests for User Story 5

- [X] T049 [P] [US5] Add a backend test for task control attributes becoming control-target sources in `backend/tests/test_scheduler.py`.
- [X] T050 [P] [US5] Add a backend test for cast-in-place continuous beam recognition becoming a control-target source in `backend/tests/test_scheduler.py`.
- [X] T051 [P] [US5] Add a backend test proving milestone evaluation scope alone does not promote all scoped tasks to control targets in `backend/tests/test_scheduler.py`.

### Implementation for User Story 5

- [X] T052 [US5] Ensure refinement control-target analysis records task control attribute sources in `backend/app/solver.py`.
- [X] T053 [US5] Ensure refinement control-target analysis records cast-in-place continuous beam rule sources in `backend/app/solver.py`.
- [X] T054 [US5] Prevent milestone evaluation ranges from automatically becoming control targets in `backend/app/solver.py`.
- [X] T055 [US5] Update frontend control-target and schedule-source explanations in `frontend/src/app/App.tsx`.
- [X] T056 [US5] Update frontend labels or helper mappings for any new control-source values in `frontend/src/domain/labels.ts`.

**Checkpoint**: User Story 5 completes result explanation and reduces plan-review ambiguity.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Verify alignment, mirror behavior, and end-to-end validation after desired user stories are complete.

- [X] T057 [P] Align or explicitly degrade Netlify/demo scheduling contract behavior in `netlify/demo-functions/api.mts`.
- [X] T058 [P] Update any impacted scheduler API helper typing in `frontend/src/api/schedulerApi.ts`.
- [X] T059 [P] Review resource configuration page invalidation behavior for resource changes in `frontend/src/features/resources/ResourcesTab.tsx`.
- [X] T060 Implement stale task graph, solve result, and scenario comparison invalidation after resource, process, productivity, logic, milestone, or control-relevant scenario changes in `frontend/src/app/App.tsx`.
- [X] T061 Add a reproducible frontend validation path for stale-result invalidation to `specs/001-cp-sat-fixed-resource/quickstart.md`.
- [X] T062 Run backend scheduling tests with `.\.venv\Scripts\python.exe -m pytest backend\tests -q`.
- [X] T063 Run frontend build with `npm --prefix frontend run build`.
- [X] T064 Validate quickstart scenarios against `specs/001-cp-sat-fixed-resource/quickstart.md`.
- [X] T065 Verify Spec Kit governance remains satisfied against `specs/001-cp-sat-fixed-resource/spec.md`, `plan.md`, and `tasks.md`.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies.
- **Foundational (Phase 2)**: Depends on Setup and blocks all user stories.
- **US1 (Phase 3)**: Depends on Foundational and delivers the MVP current-resource judgment.
- **US2 (Phase 4)**: Depends on Foundational; should follow US1 for user-facing current-resource loop coherence.
- **US3 (Phase 5)**: Depends on Foundational and benefits from US1 delayed-result behavior.
- **US4 (Phase 6)**: Depends on Foundational and should complete before final algorithm validation.
- **US5 (Phase 7)**: Depends on Foundational and can proceed after refinement data is available.
- **Polish (Phase 8)**: Depends on desired user stories being complete.

### User Story Dependencies

- **US1**: No dependency on other user stories after Foundational.
- **US2**: Uses current-resource sufficiency state from US1 but can be tested independently with a sufficient scenario.
- **US3**: Uses delayed current-resource state from US1 and refinement behavior from US2 for candidate refinement.
- **US4**: Cross-cuts US2 and US3; tests should run against both current-resource and candidate refinement.
- **US5**: Cross-cuts US2 and US3; can be added once refinement analysis exists.

### Within Each User Story

- Write or update tests before implementation.
- Update backend orchestration before frontend display for result-flow stories.
- Update frontend types before frontend rendering if metadata shape changes.
- Complete story checkpoint before proceeding to the next priority story when working sequentially.

## Parallel Opportunities

- T002, T003, and T004 can run in parallel.
- T011, T012, and T013 can run in parallel after Foundational.
- T019, T020, and T021 can run in parallel after Foundational.
- T027 through T031 can run in parallel after Foundational.
- T040 through T043 can run in parallel after Foundational.
- T049 through T051 can run in parallel after Foundational.
- T057, T058, T059, and T061 can run in parallel after desired user stories are complete.
- Frontend display tasks can run in parallel with backend implementation only after metadata names and shapes are agreed.

## Parallel Example: User Story 3

```text
Task: "Add critical-path infeasible recommendation test in backend/tests/test_scheduler.py"
Task: "Add upper-bound infeasible recommendation test in backend/tests/test_scheduler.py"
Task: "Add verified minimum-resource candidate test in backend/tests/test_scheduler.py"
Task: "Add minimum-resource refinement fallback test in backend/tests/test_scheduler.py"
```

## Implementation Strategy

### MVP First

1. Complete Phase 1 and Phase 2.
2. Complete US1 to prove current-resource sufficiency and delayed schedule preservation.
3. Complete US2 so sufficient current resources produce a refined or fallback detailed plan.
4. Stop for validation if needed: US1 + US2 prove the first current-resource loop.

### Incremental Delivery

1. Add US3 to support verified minimum-resource candidate comparison.
2. Add US4 to lock same-structure same-process credibility across refined schedules.
3. Add US5 to improve explanation and schedule-source trust.
4. Finish Polish validation and mirror/degradation review.

### Governance Stop Point

Do not implement any task until the user confirms `spec.md`, `plan.md`, `tasks.md`, and `$speckit-analyze` results.

## Notes

- `[P]` tasks are parallelizable only when they do not edit the same file at the same time.
- Story labels map to the user stories in `spec.md`.
- Backend tests are intentionally first-class because this feature changes scheduling behavior and result contracts.
- Netlify/demo alignment is a polish task unless the user requires deployed demo parity in the first implementation pass.

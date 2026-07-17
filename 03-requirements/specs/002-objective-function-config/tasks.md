# Tasks: Objective Function Configuration

**Input**: Design documents from `specs/002-objective-function-config/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/](contracts/), [quickstart.md](quickstart.md)

**Tests**: Required. This feature changes CP-SAT objective behavior, shared frontend/backend fields, and a user-facing simulation workflow.

**Organization**: Tasks are grouped by user story so each story can be implemented and validated independently.

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Confirm current objective, strategy, and page surfaces before code changes.

- [X] T001 Review existing objective constants, `model.Minimize(...)`, and `objective_breakdown` in `backend/app/solver.py`.
- [X] T002 [P] Review existing strategy models in `backend/app/models.py` and `frontend/src/types/scheduler.ts`.
- [X] T003 [P] Review full simulation parameter layout in `frontend/src/app/App.tsx`.
- [X] T004 [P] Review Netlify demo schedule result shape in `netlify/demo-functions/api.mts`.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Add the shared objective-term contract and backend normalization before UI and solve behavior use it.

- [X] T005 Add backend objective-term ids, labels, defaults, and config models in `backend/app/models.py`.
- [X] T006 Add backend normalization and validation for missing terms, unknown terms, invalid weights, and all-disabled terms in `backend/app/models.py`.
- [X] T007 Update frontend scheduler types and default schedule strategy in `frontend/src/types/scheduler.ts` and `frontend/src/app/App.tsx`.
- [X] T008 Add backend tests for default compatibility and invalid objective configuration in `backend/tests/test_scheduler.py`.

**Checkpoint**: Shared request/response contract can be validated without changing page behavior.

---

## Phase 3: User Story 1 - Configure Objective Terms Before Solving (Priority: P1) MVP

**Goal**: Users can view, enable/disable, edit, and restore objective term settings on the full simulation page.

**Independent Test**: Full "模拟求解" page shows objective controls and updates scenario strategy when a checkbox or weight changes.

### Tests for User Story 1

- [X] T009 [P] [US1] Add frontend build coverage through typed objective controls in `frontend/src/app/App.tsx`.
- [X] T010 [P] [US1] Add backend test proving disabled terms return effective weight 0 in `backend/tests/test_scheduler.py`.

### Implementation for User Story 1

- [X] T011 [US1] Render objective configuration controls only for the full simulation page in `frontend/src/app/App.tsx`.
- [X] T012 [US1] Add enable, weight edit, and restore-default handlers for objective terms in `frontend/src/app/App.tsx`.
- [X] T013 [US1] Add responsive styles for objective controls in `frontend/src/styles.css`.
- [X] T014 [US1] Ensure objective-term edits are included in existing scenario fingerprint behavior in `frontend/src/app/App.tsx`.

**Checkpoint**: Full simulation page can configure objective terms before solving, while MVP page remains unchanged.

---

## Phase 4: User Story 2 - Preserve Existing Defaults (Priority: P1)

**Goal**: Existing scenarios without explicit objective terms solve with current defaults while legacy ordinary-balance inputs remain accepted and filtered out.

**Independent Test**: Backend tests prove no explicit objective terms produces current effective weights and legacy `normal_balance` / `enable_balance_objective` inputs do not re-enable the removed target.

### Tests for User Story 2

- [X] T015 [P] [US2] Add backend test for omitted objective terms matching previous default weights in `backend/tests/test_scheduler.py`.
- [X] T016 [P] [US2] Add backend test for legacy `enable_balance_objective` and `normal_balance` compatibility in `backend/tests/test_scheduler.py`.

### Implementation for User Story 2

- [X] T017 [US2] Preserve `enable_balance_objective` compatibility while filtering legacy `normal_balance` from current objective terms in `backend/app/models.py`.
- [X] T018 [US2] Return `objective_terms_used` and effective `objective_weights` for refinement results in `backend/app/solver.py`.

**Checkpoint**: Existing runs remain compatible and auditable.

---

## Phase 5: User Story 3 - Apply Configuration To Candidate Refinement (Priority: P2)

**Goal**: Current-resource and minimum-resource candidate refinement use the same request objective configuration.

**Independent Test**: A candidate refinement result reports the same effective objective mapping as the source request.

### Tests for User Story 3

- [X] T019 [P] [US3] Add backend test for objective configuration propagation to minimum-resource candidate refinement in `backend/tests/test_scheduler.py`.

### Implementation for User Story 3

- [X] T020 [US3] Apply effective objective weights in `solve_control_priority_schedule()` in `backend/app/solver.py`.
- [X] T021 [US3] Confirm minimum-resource candidate reoptimization copies the objective configuration in `backend/app/solver.py`.
- [X] T022 [US3] Keep resource-cost optimization's primary objective unchanged in `backend/app/solver.py`.

**Checkpoint**: Refinement paths consistently use the same objective configuration.

---

## Phase 6: User Story 4 - Validate Unsafe Inputs (Priority: P2)

**Goal**: Bad objective configuration fails clearly before solving.

**Independent Test**: Unknown term ids, invalid enabled weights, and all-disabled terms are rejected.

### Tests for User Story 4

- [X] T023 [P] [US4] Add backend validation tests for unknown terms, invalid weights, and all-disabled terms in `backend/tests/test_scheduler.py`.

### Implementation for User Story 4

- [X] T024 [US4] Ensure validation messages identify objective-term errors clearly in `backend/app/models.py`.
- [X] T025 [US4] Add frontend guardrails for numeric weight normalization in `frontend/src/app/App.tsx`.

**Checkpoint**: Invalid configurations are rejected or normalized before a solve request is accepted.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Align demo contract and validate the implementation.

- [X] T026 Align Netlify demo objective-term request/result compatibility in `netlify/demo-functions/api.mts`.
- [X] T027 Run backend scheduling tests with `.\.venv\Scripts\python.exe -m pytest backend\tests -q`.
- [X] T028 Run frontend build with `npm --prefix frontend run build`.
- [X] T029 Validate the full simulation page in the browser using `specs/002-objective-function-config/quickstart.md`.
- [X] T030 Verify Spec Kit analyze/converge status and update this task list to `[X]`.
- [X] T031 Remove deprecated `spatial_resource_assignment` from objective terms, solver objective assembly, frontend controls, Netlify contract, tests, and objective documentation.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies.
- **Foundational (Phase 2)**: Depends on Setup and blocks all user stories.
- **US1 (Phase 3)**: Depends on Foundational.
- **US2 (Phase 4)**: Depends on Foundational and should complete before full validation.
- **US3 (Phase 5)**: Depends on Foundational and uses the shared solver metadata.
- **US4 (Phase 6)**: Depends on Foundational.
- **Polish (Phase 7)**: Depends on desired stories being complete.

### Parallel Opportunities

- T002, T003, and T004 can run in parallel.
- T009 and T010 can run in parallel after Foundational.
- T015 and T016 can run in parallel after Foundational.
- T019 and T023 can run in parallel with separate backend test cases.

## Implementation Strategy

### MVP First

1. Complete Setup and Foundational contract work.
2. Complete US1 and US2 to prove visible configuration plus default compatibility.
3. Validate with backend tests and frontend build.

### Incremental Delivery

1. Add US3 candidate refinement propagation.
2. Add US4 validation hardening.
3. Align Netlify demo and run browser quickstart.

## Notes

- `[P]` tasks are parallelizable only when they do not edit the same file at the same time.
- Backend tests are required because this feature changes CP-SAT objective behavior.
- Do not update README, persist objective terms, commit, push, or deploy.

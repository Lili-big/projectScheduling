# Feature Specification: Objective Function Configuration

**Feature Branch**: `[002-objective-function-config]`

**Created**: 2026-07-03

**Status**: Draft

**Input**: User description: "在历史完整模拟求解页面上，把目标函数指标在计算前可视化，支持勾选启用、修改权重，并在计算时传入 CP-SAT；不改模拟求解-MVP 页面。"

## Current Implementation Correction (2026-07-08)

The current backend objective contract has been narrowed to 4 editable objective terms: `control_node_late`, `makespan_and_soft_milestone`, `resource_path_continuity`, and `resource_idle`. The earlier 7-term wording in this package is historical. `control_buffer_risk`, `risk_related_control_wait`, `resource_workload_balance`, `unconfigured_normal_balance`, `spatial_resource_assignment`, `same_structure_craft_split`, and `normal_balance` are deprecated compatibility inputs and must not be documented as current editable objective terms.

## Source & Review Context *(mandatory)*

- **Source Documents**:
  - `AGENTS.md`
  - `agent.md`
  - `README.md`
  - `docs/精排目标函数算法需求文档_v3.0.md`
  - `docs/模拟求解-MVP页面需求文档_v1.2.md`
  - `specs/001-cp-sat-fixed-resource/spec.md`
- **Review Decision**: User-confirmed direct implementation. The user approved the implementation plan and corrected the page scope to the historical full "模拟求解" page rather than "模拟求解-MVP".
- **Demo/Code Facts Used**: Current `ScheduleStrategyConfig` already travels through `ScenarioInput -> GeneratedScheduleInput / ScheduleInput -> ScheduleResult`; the full simulation page already exposes strategy, resource guarantee, and `enable_balance_objective`; `backend/app/solver.py` owns CP-SAT objective assembly and returns `objective_breakdown.objective_weights`.
- **Out of Scope**: The MVP simulation page, strict lexicographic optimization, editing hard constraints, changing resource-cost optimization's primary objective, adding database persistence, updating README, deployment, and git commit/push.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Configure Objective Terms Before Solving (Priority: P1)

As a planning engineer using the full simulation page, I want to see which refinement objective terms are active and adjust their weights before solving so that the next CP-SAT run reflects my planning preference.

**Why this priority**: This is the core workflow. Without visible pre-solve controls, users cannot understand or influence the refined plan tradeoffs.

**Independent Test**: Can be tested from the full "模拟求解" page by opening the objective configuration area, changing a checkbox and a weight, running fixed-resource scheduling, and confirming the result reports the chosen effective objective weights.

**Acceptance Scenarios**:

1. **Given** the user is on the full "模拟求解" page, **When** the page renders, **Then** it shows the current objective terms, each term's enabled state, and each term's weight before solving.
2. **Given** the user disables an objective term, **When** fixed-resource scheduling runs and reaches refinement, **Then** that term contributes an effective weight of 0 while hard constraints remain enforced.
3. **Given** the user edits an enabled term's weight, **When** fixed-resource scheduling runs and reaches refinement, **Then** the returned objective breakdown includes the edited weight for that term.

---

### User Story 2 - Keep Objective Configuration Compatible With Existing Runs (Priority: P1)

As a product and test user, I want existing scenarios without explicit objective-term configuration to behave as before so that the new controls do not regress existing scheduling results.

**Why this priority**: The project already has fixed-resource and refinement tests; default behavior must remain stable unless the user changes configuration.

**Independent Test**: Can be tested by solving a scenario with no `objective_terms` provided and confirming the default effective weights match the current 4 objective terms while legacy `enable_balance_objective` remains accepted but does not enable a removed objective.

**Acceptance Scenarios**:

1. **Given** a scenario omits `objective_terms`, **When** the backend receives it, **Then** defaults are merged and the run uses the previous objective weights.
2. **Given** a legacy scenario sets `enable_balance_objective` or sends `objective_terms.normal_balance`, **When** the backend normalizes the request, **Then** the legacy ordinary-work balance target is ignored and not returned as an active objective term.
3. **Given** a user edits objective terms, **When** the scenario fingerprint changes, **Then** stale solve results are not reused as the current result.

---

### User Story 3 - Apply Configuration To Minimum-Resource Candidate Refinement (Priority: P2)

As a planning engineer, I want minimum-resource candidate refinement to use the same objective settings as the current-resource refinement so that candidate plans are comparable with the chosen tradeoffs.

**Why this priority**: Minimum-resource candidate rerun refinement is already part of the fixed-resource workflow; using a different objective configuration would make comparisons confusing.

**Independent Test**: Can be tested by triggering a minimum-resource candidate rerun after changing objective settings and confirming the candidate's refinement result carries the same effective objective-term configuration.

**Acceptance Scenarios**:

1. **Given** a fixed-resource run produces a verified minimum-resource candidate, **When** candidate refinement runs, **Then** it uses the user's objective-term configuration.
2. **Given** the resource-cost optimization button is used, **When** it solves, **Then** resource cost remains the primary optimization objective and the objective-term controls do not override it.

---

### User Story 4 - Validate Unsafe Objective Inputs (Priority: P2)

As a tester or product user, I want invalid objective configuration to fail clearly so that hidden or malformed inputs do not silently corrupt scheduling behavior.

**Why this priority**: Objective weights materially affect CP-SAT behavior and must be bounded and explainable.

**Independent Test**: Can be tested by sending malformed objective term ids, invalid weights, or all-disabled terms and confirming validation fails with a clear message.

**Acceptance Scenarios**:

1. **Given** a request contains an unknown objective term id, **When** the backend validates the scenario, **Then** the request is rejected with a field-level validation error.
2. **Given** an enabled term has a weight outside `1..1_000_000_000`, **When** the backend validates the scenario, **Then** the request is rejected.
3. **Given** all objective terms are disabled, **When** the backend validates the scenario, **Then** the request is rejected because refinement needs at least one active soft objective.

### Edge Cases

- A legacy request includes the ordinary-work balance term: the backend ignores it so old browser state does not fail, but it is no longer listed, weighted, or returned as an active objective term.
- The user restores defaults: all 4 editable soft objective terms return to their default enabled state and weight.
- A legacy request contains `spatial_resource_assignment`: the backend ignores this deprecated term so old browser state does not fail, but it is no longer listed, weighted, or returned as an active objective term.
- A term is disabled and its saved weight is invalid or blank in the UI: the UI normalizes the value before submission; the backend still validates the final request.
- Refinement falls back or times out: the returned result still reports the effective objective terms that were attempted where a refinement result is available.
- Netlify demo receives objective terms: it accepts the contract and can echo effective defaults, but it does not claim full CP-SAT parity.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The full simulation page MUST show a pre-solve objective-function configuration area; the MVP simulation page MUST NOT be changed by this feature.
- **FR-002**: The objective configuration area MUST list the 4 currently implemented editable soft objective terms: `control_node_late`, `makespan_and_soft_milestone`, `resource_path_continuity`, and `resource_idle`.
- **FR-003**: Users MUST be able to enable or disable each listed objective term with a checkbox and edit each term's numeric weight.
- **FR-004**: The system MUST treat construction logic, task duration, resource compatibility, resource non-overlap, configured same-structure rules, and enforced hard milestones as hard constraints that cannot be disabled through objective controls.
- **FR-005**: `ScheduleStrategyConfig` MUST support objective-term configuration while retaining backward compatibility with existing `enable_balance_objective`.
- **FR-006**: Backend validation MUST reject unknown objective term ids, enabled term weights outside `1..1_000_000_000`, and configurations where no objective term is enabled.
- **FR-007**: The backend MUST merge missing objective terms with defaults so existing scenarios keep the current objective behavior.
- **FR-008**: Disabled terms MUST keep their configured display weight but contribute an effective solve weight of 0.
- **FR-009**: The CP-SAT refinement objective MUST use the effective term weights from `ScheduleStrategyConfig` for current-resource refinement.
- **FR-010**: Minimum-resource candidate refinement MUST use the same objective-term configuration as the request scenario.
- **FR-011**: Resource-cost optimization MUST keep resource cost as its primary objective and MUST NOT be overridden by the new refinement objective controls.
- **FR-012**: `ScheduleResult.objective_breakdown` MUST include `objective_terms_used` and keep `objective_weights` as the effective weight mapping for compatibility.
- **FR-013**: Frontend scenario fingerprints MUST include objective-term configuration so changed checkboxes or weights invalidate stale generated and solved results.
- **FR-014**: Netlify demo code MUST remain contract-compatible with objective-term fields and must not claim Python CP-SAT parity when only echoing/defaulting the configuration.
- **FR-015**: The system MUST completely remove `control_buffer_risk`, `risk_related_control_wait`, `resource_workload_balance`, `unconfigured_normal_balance`, `spatial_resource_assignment`, `same_structure_craft_split`, and `normal_balance` from editable objective terms, default objective weights, CP-SAT objective assembly, result metadata, and Netlify demo defaults; legacy payloads containing deprecated keys MUST be filtered rather than treated as active objectives.

### Key Entities *(include if feature involves data)*

- **Objective Term**: One editable soft objective item with stable id, label, description, default weight, enabled flag, and effective weight.
- **Schedule Strategy Configuration**: Scenario-level scheduling strategy settings, now including objective-term configuration and legacy ordinary-balance compatibility.
- **Objective Terms Used**: Result metadata showing each term's requested enabled state, requested weight, effective weight, and whether it contributed to the solve objective.
- **Full Simulation Page Objective Controls**: The visible pre-solve controls on the historical full simulation page.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users can identify all 4 editable objective terms, each enabled state, and each weight before clicking a solve button on the full simulation page.
- **SC-002**: For scenarios without explicit objective-term configuration, default solve output reports the same effective objective weights as the previous constants.
- **SC-003**: For a run with one disabled objective term, the returned `objective_terms_used` shows that term with effective weight 0 and all enabled terms with positive effective weights.
- **SC-004**: Invalid objective-term payloads are rejected before solving with a clear validation error in 100% of malformed test cases.
- **SC-005**: Minimum-resource candidate refinement reports the same objective-term effective mapping as the source request when a candidate refinement result is returned.
- **SC-006**: Frontend build and backend scheduler tests pass after the contract and UI changes.

## Assumptions

- User-confirmed defaults apply: all 4 current soft objective terms are editable; hard constraints stay locked; configuration is part of the current scenario request but is not saved to local scenario persistence in this phase.
- The Python FastAPI backend remains authoritative for CP-SAT behavior.
- Existing full simulation page layout can be extended within the "模拟参数" area without adding a new top-level tab.
- Objective weights are integer values and share the existing solver weight scale.

# Research: Objective Function Configuration

## Decision: Extend `ScheduleStrategyConfig`

**Rationale**: The current full simulation page stores schedule strategy settings in `ScenarioInput.schedule_strategy`, and the backend already passes that object into `ScheduleInput` and the solver. Extending this shape keeps objective configuration inside the existing scenario fingerprint and request contract.

**Alternatives considered**:

- Separate request wrapper for objective configuration: rejected because it would duplicate state and risk mismatched solve fingerprints.
- Global/local persistence in this phase: rejected because the user scoped persistence out of this MVP.

## Decision: Configure only soft objective weights

**Rationale**: The source objective-function document distinguishes hard constraints from soft objectives. The user specifically wants objective indicators and weights, not the ability to disable construction feasibility rules.

**Alternatives considered**:

- Expert mode for hard constraints: rejected because it would change scheduling validity semantics.
- Strict lexicographic optimization: rejected as out of scope and already called out as future work.

## Decision: Preserve default behavior through merged defaults

**Rationale**: Existing tests and scenarios rely on hard-coded objective constants. Missing objective-term configuration should be interpreted as "use defaults" to avoid regressions.

**Alternatives considered**:

- Require all requests to send every term: rejected because it would break old clients and saved scenarios.
- Store only user-overridden terms: accepted as wire-compatible behavior, with backend default merging.

## Decision: Keep `objective_weights` as effective weights

**Rationale**: Existing frontend and tests may read `objective_breakdown.objective_weights`. Keeping it as the effective mapping while adding richer `objective_terms_used` avoids breaking compatibility.

**Alternatives considered**:

- Replace `objective_weights` entirely: rejected due to contract drift.
- Only return requested weights: rejected because disabled terms need effective weight 0 to be auditable.

## Decision: Netlify demo remains contract-compatible only

**Rationale**: Python/OR-Tools is the authoritative CP-SAT implementation. The Netlify demo can accept and echo the field to avoid frontend contract errors, but it should not claim identical solver behavior.

**Alternatives considered**:

- Reimplement objective weighting in the demo: rejected because it would be a parallel scheduling model and is outside the requested MVP.

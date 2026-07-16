"""Fixed-resource and AI-strict scheduling use cases."""

from ._scenario import (
    _fixed_resource_recommendation,
    _minimum_resource_candidate_result,
    _solve_fixed_resources_shortest_scenario,
    solve_ai_strict_fixed_resource_scenario,
    solve_scenario,
)

__all__ = ["solve_ai_strict_fixed_resource_scenario", "solve_scenario"]

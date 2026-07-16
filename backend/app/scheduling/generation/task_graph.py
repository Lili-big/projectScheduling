"""Task graph, duration, precedence and resource expansion discovery surface."""

from ..application._scenario import (
    _apply_required_resource_types,
    _build_lower_to_upper_links,
    _build_tasks,
    _build_upper_structure_tasks,
    _task_from_component,
    expand_resource_pools,
    generate_schedule_input_from_scenario,
)

__all__ = ["expand_resource_pools", "generate_schedule_input_from_scenario"]

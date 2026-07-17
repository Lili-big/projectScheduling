"""Resource-calendar ownership marker.

Calendar intervals are built inside the engine model builders; this module is
the dependency target for future isolated calendar changes.
"""

from ..engine import _build_named_resource_assignment_model, _solve_capacity_model

__all__: list[str] = []

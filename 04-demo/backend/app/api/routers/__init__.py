"""HTTP router packages grouped by product capability."""

from .assistants import router as assistants_router
from .plan_control import router as plan_control_router
from .project_girder import router as project_girder_router
from .project_master import router as project_master_router
from .scheduling import router as scheduling_router
from .system import router as system_router

__all__ = [
    "assistants_router",
    "plan_control_router",
    "project_girder_router",
    "project_master_router",
    "scheduling_router",
    "system_router",
]

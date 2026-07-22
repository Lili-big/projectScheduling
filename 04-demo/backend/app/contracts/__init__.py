"""Public backend contracts grouped by domain.

The canonical definitions currently live in ``_models`` while the migration
keeps every legacy import stable. Domain modules provide the supported discovery
surface; ``app.models`` remains a compatibility façade.
"""

from ._models import *  # noqa: F401,F403
from .girder_plan_simulation import *  # noqa: F401,F403
from .project_master import *  # noqa: F401,F403

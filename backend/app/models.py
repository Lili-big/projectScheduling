"""Backward-compatible export of all public backend contracts.

New code should import from ``app.contracts.<domain>``. This module remains a
stable façade for existing integrations and historical specifications.
"""

from .contracts._models import *  # noqa: F401,F403

"""Compatibility alias for the scheduling application implementation."""

from __future__ import annotations

import sys

from .scheduling.application import _scenario as _implementation


# Alias the module object itself so legacy monkeypatches still modify the globals
# used by migrated functions. A copy-based re-export would break that contract.
sys.modules[__name__] = _implementation

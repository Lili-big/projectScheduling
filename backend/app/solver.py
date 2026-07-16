"""Compatibility alias for the scheduling solver engine."""

from __future__ import annotations

import sys

from .scheduling.solver import engine as _implementation


# Preserve private imports and monkeypatch semantics used by historical tests.
sys.modules[__name__] = _implementation

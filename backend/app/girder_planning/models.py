from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field


class RouteOccurrence(BaseModel):
    route_id: str
    route_node_id: str
    workpoint_id: str
    bridge_id: str | None = None
    side: Literal["left", "right", "both", "unknown"] = "unknown"
    arrival_date: date | None = None
    sequence_index: int = Field(ge=0)


class InventoryState(BaseModel):
    beam_yard_id: str
    beam_type: str
    date: date
    opening_inventory: float = Field(ge=0)
    produced: float = Field(ge=0)
    consumed: float = Field(ge=0)
    closing_inventory: float = Field(ge=0)


class PassageState(BaseModel):
    workpoint_id: str
    passable_date: date | None = None
    controlling_source: Literal[
        "erection_buffer",
        "explicit_readiness",
        "linked_condition",
        "actual_fact",
        "none",
    ] = "none"
    status: Literal["ready", "waiting", "blocked"] = "blocked"
    unresolved_refs: list[str] = Field(default_factory=list)


class IterationState(BaseModel):
    iteration_no: int = Field(ge=1)
    ownership_fingerprint: str
    date_state_fingerprint: str
    changed_owner_refs: list[str] = Field(default_factory=list)
    changed_date_refs: list[str] = Field(default_factory=list)

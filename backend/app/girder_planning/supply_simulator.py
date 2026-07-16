from __future__ import annotations

import math
from collections import defaultdict
from datetime import date, timedelta

from pydantic import BaseModel, Field

from ..contracts import BeamYardConfig, ValidationMessage, YardInventoryActual, YardInventoryPoint


class SupplyDemand(BaseModel):
    demand_id: str
    beam_yard_id: str
    beam_type: str = "default"
    quantity: float = Field(gt=0)
    required_date: date


class SupplyAllocation(BaseModel):
    demand_id: str
    available_date: date | None = None
    inventory_before: float = Field(default=0, ge=0)
    inventory_after: float = Field(default=0, ge=0)
    status: str = "ready"


def simulate_supply(
    yards: list[BeamYardConfig],
    demands: list[SupplyDemand],
    *,
    actuals: list[YardInventoryActual] | None = None,
) -> tuple[list[SupplyAllocation], list[YardInventoryPoint], list[ValidationMessage]]:
    yard_by_id = {item.beam_yard_id: item for item in yards if item.enabled}
    actual_by_key = {(item.beam_yard_id, item.beam_type): item for item in actuals or []}
    allocations: list[SupplyAllocation] = []
    points: list[YardInventoryPoint] = []
    diagnostics: list[ValidationMessage] = []
    states: dict[tuple[str, str], dict[str, object]] = {}

    for demand in sorted(demands, key=lambda item: (item.required_date, item.beam_yard_id, item.demand_id)):
        yard = yard_by_id.get(demand.beam_yard_id)
        if yard is None:
            allocations.append(SupplyAllocation(demand_id=demand.demand_id, status="blocked"))
            diagnostics.append(_message("error", "GIRDER_YARD_MISSING", f"供梁需求 {demand.demand_id} 引用的梁场不存在。", demand.demand_id))
            continue
        key = (yard.beam_yard_id, demand.beam_type)
        state = states.get(key)
        if state is None:
            actual = actual_by_key.get(key)
            initial = yard.initial_inventory_by_type.get(demand.beam_type, yard.initial_inventory_by_type.get("default", 0.0))
            if actual is not None:
                initial = actual.observed_inventory + actual.opening_inventory_adjustment
            state = {
                "date": yard.production_start_date - timedelta(days=1),
                "inventory": max(0.0, float(initial)),
                "points": {},
            }
            states[key] = state
        current_date = state["date"]
        inventory = float(state["inventory"])
        max_inventory = None
        if yard.max_inventory_by_type:
            max_inventory = yard.max_inventory_by_type.get(demand.beam_type, yard.max_inventory_by_type.get("default"))
        target_date = max(demand.required_date, yard.production_start_date)
        safety_days = 0
        while current_date < target_date or inventory + 1e-9 < demand.quantity:
            current_date = current_date + timedelta(days=1)
            production = float(yard.daily_production_capacity)
            if max_inventory is not None:
                production = min(production, max(0.0, float(max_inventory) - inventory))
            opening = inventory
            inventory += production
            point = YardInventoryPoint(
                beam_yard_id=yard.beam_yard_id,
                beam_type=demand.beam_type,
                date=current_date,
                opening_inventory=opening,
                produced=production,
                consumed=0,
                closing_inventory=inventory,
                max_inventory=max_inventory,
            )
            state["points"][current_date] = point
            safety_days += 1
            if safety_days > 20000 or (yard.daily_production_capacity <= 0 and inventory + 1e-9 < demand.quantity):
                diagnostics.append(_message("error", "GIRDER_SUPPLY_UNAVAILABLE", f"梁场 {yard.name} 无法满足需求 {demand.demand_id}。", demand.demand_id))
                allocations.append(SupplyAllocation(demand_id=demand.demand_id, status="blocked"))
                break
        else:
            before = inventory
            inventory -= demand.quantity
            point = state["points"].get(current_date)
            if point is None:
                point = YardInventoryPoint(
                    beam_yard_id=yard.beam_yard_id,
                    beam_type=demand.beam_type,
                    date=current_date,
                    opening_inventory=before,
                    produced=0,
                    consumed=demand.quantity,
                    closing_inventory=inventory,
                    max_inventory=max_inventory,
                )
            else:
                point = point.model_copy(update={"consumed": point.consumed + demand.quantity, "closing_inventory": inventory})
            state["points"][current_date] = point
            allocations.append(
                SupplyAllocation(
                    demand_id=demand.demand_id,
                    available_date=current_date,
                    inventory_before=before,
                    inventory_after=inventory,
                    status="ready",
                )
            )
        state["date"] = current_date
        state["inventory"] = max(0.0, inventory)

    for state in states.values():
        points.extend(state["points"].values())
    points.sort(key=lambda item: (item.date, item.beam_yard_id, item.beam_type))
    if any(item.closing_inventory < -1e-9 for item in points):
        diagnostics.append(_message("error", "GIRDER_NEGATIVE_INVENTORY", "库存日序列出现负值，已阻断计算。"))
    return allocations, points, diagnostics


def erection_duration_days(beam_count: int, daily_capacity: float) -> int:
    return max(1, math.ceil(beam_count / daily_capacity))


def _message(level: str, code: str, message: str, *refs: str) -> ValidationMessage:
    return ValidationMessage(level=level, code=code, message=message, subject_id=refs[0] if refs else None, entity_refs=list(refs))

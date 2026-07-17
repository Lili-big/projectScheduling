from __future__ import annotations

from datetime import date

from app.girder_planning.supply_simulator import SupplyDemand, simulate_supply
from app.models import BeamYardConfig


def test_supply_waits_for_production_and_keeps_inventory_non_negative() -> None:
    yard = BeamYardConfig(
        beam_yard_id="yard-1",
        name="一号梁场",
        mileage_m=0,
        corridor_id="main",
        production_start_date=date(2026, 1, 1),
        daily_production_capacity=2,
        initial_inventory_by_type={"T": 1},
    )
    allocations, points, diagnostics = simulate_supply(
        [yard],
        [SupplyDemand(demand_id="d-1", beam_yard_id="yard-1", beam_type="T", quantity=4, required_date=date(2026, 1, 1))],
    )

    assert diagnostics == []
    assert allocations[0].status == "ready"
    assert allocations[0].available_date == date(2026, 1, 2)
    assert all(point.closing_inventory >= 0 for point in points)


def test_supply_blocks_when_zero_capacity_cannot_cover_demand() -> None:
    yard = BeamYardConfig(
        beam_yard_id="yard-1",
        name="一号梁场",
        mileage_m=0,
        corridor_id="main",
        production_start_date=date(2026, 1, 1),
        daily_production_capacity=0,
    )
    allocations, _, diagnostics = simulate_supply(
        [yard],
        [SupplyDemand(demand_id="d-1", beam_yard_id="yard-1", quantity=1, required_date=date(2026, 1, 1))],
    )

    assert allocations[0].status == "blocked"
    assert any(item.code == "GIRDER_SUPPLY_UNAVAILABLE" for item in diagnostics)

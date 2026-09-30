"""Shift regimes make a task's duration a function of its start date.

Single source of truth for spec 076: greedy construction, the CP-SAT model
and the independent numeric validation must all call these functions, and an
empty regime list must reproduce the baseline fixed duration exactly.
"""
import math
from datetime import timedelta

QUANTITY_EPSILON = 1e-9
_SHIFT_RUN_CACHE: dict = {}


def shift_runs(regimes, start_date):
    """Constant-shift runs as (first_offset, last_offset_or_None, shifts).

    Offsets are days from the schedule start; runs are sorted and disjoint.
    Uncovered dates default to single shift, so runs partition the calendar.
    Overlapping regimes are a validation error upstream; this raises as a
    defensive guard so they can never silently enter the solver.
    """
    key = tuple(sorted((r.start_date, r.end_date, r.shifts) for r in regimes))
    cached = _SHIFT_RUN_CACHE.get(key)
    if cached is not None:
        return cached
    spans = []
    for regime in regimes:
        first = (regime.start_date - start_date).days
        last = None if regime.end_date is None else (regime.end_date - start_date).days
        if last is not None and last < first:
            continue
        spans.append((first, last, regime.shifts))
    spans.sort()
    merged = []
    for first, last, shifts in spans:
        if merged and (merged[-1][1] is None or first <= merged[-1][1]):
            raise ValueError("班制区间重叠")
        merged.append((first, last, shifts))
    _SHIFT_RUN_CACHE[key] = merged
    return merged


def shifts_for_day(regimes, day):
    """Shift count on one calendar date; uncovered dates are single shift."""
    for regime in regimes:
        if regime.start_date <= day and (regime.end_date is None or day <= regime.end_date):
            return regime.shifts
    return 1


def _days_for(remaining, daily_output):
    return max(1, math.ceil((remaining - QUANTITY_EPSILON) / daily_output))


def task_duration_for_start(task, start_offset, regimes, start_date):
    """Work-task duration when starting at start_offset (spec FR-003).

    Smallest k >= 1 with sum of daily outputs covering the quantity. Tasks
    without a productivity basis (ancillary steps) keep their fixed duration;
    an empty regime list returns the baseline duration unchanged so behaviour
    matches the pre-shift implementation bit for bit.
    """
    if not regimes:
        return task.duration_days
    value = task.properties.get("productivity_value")
    if value is None or task.quantity is None:
        return task.duration_days
    base_output = float(value)
    if base_output <= 0:
        return task.duration_days
    runs = shift_runs(regimes, start_date)
    remaining = float(task.quantity)
    duration = 0
    offset = start_offset
    index = 0
    while index < len(runs) and runs[index][1] is not None and runs[index][1] < offset:
        index += 1
    while True:
        if index >= len(runs):
            return duration + _days_for(remaining, base_output)
        first, last, shifts = runs[index]
        if offset < first:
            gap_days = first - offset
            if gap_days * base_output >= remaining - QUANTITY_EPSILON:
                return duration + _days_for(remaining, base_output)
            remaining -= gap_days * base_output
            duration += gap_days
            offset = first
        days_here = (last - offset + 1) if last is not None else None
        daily = base_output * shifts
        if days_here is None or days_here * daily >= remaining - QUANTITY_EPSILON:
            return duration + _days_for(remaining, daily)
        remaining -= days_here * daily
        duration += days_here
        offset = last + 1
        index += 1


def split_shift_days(start_offset, end_offset, regimes, start_date):
    """Days per shift count over [start_offset, end_offset); display only."""
    split = {}
    for offset in range(start_offset, end_offset):
        shifts = shifts_for_day(regimes, start_date + timedelta(days=offset))
        split[shifts] = split.get(shifts, 0) + 1
    return split or {1: 0}


def regimes_overlap(regimes):
    """True when two regimes share any calendar date (validation helper)."""
    ordered = sorted(regimes, key=lambda r: r.start_date)
    for previous, current in zip(ordered, ordered[1:]):
        if previous.end_date is None or current.start_date <= previous.end_date:
            return True
    return False


def shift_config_errors(regimes):
    """Business validation shared by generation and direct /solve payloads.

    Same-start duplicates always share dates, so the overlap rule rejects them.
    """
    errors = []
    for regime in regimes:
        if regime.end_date is not None and regime.end_date < regime.start_date:
            errors.append(f"shift_range:{regime.start_date}")
    if len(regimes) >= 2 and regimes_overlap(regimes):
        errors.append("shift_overlap")
    return errors

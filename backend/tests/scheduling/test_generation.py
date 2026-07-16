from __future__ import annotations

import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BACKEND_ROOT))

from app.scenario_data import default_scenario  # noqa: E402
from app.scheduling.generation.task_graph import generate_schedule_input_from_scenario  # noqa: E402


def test_generation_boundary_builds_stable_nonempty_task_graph() -> None:
    generated = generate_schedule_input_from_scenario(default_scenario())
    tasks = generated.schedule_input.tasks
    assert len(tasks) == 68
    assert len({task.id for task in tasks}) == len(tasks)
    assert generated.schedule_input.precedence_links

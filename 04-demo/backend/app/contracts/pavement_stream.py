"""Request-scoped pavement solve events; no persistent job state."""
from typing import Annotated, Literal

from pydantic import BaseModel, Field

from ._models import ScenarioSolveResult


class _Event(BaseModel):
    sequence: int = Field(ge=1)
    elapsed_seconds: float = Field(ge=0, allow_inf_nan=False)


class PavementSolveStarted(_Event):
    type: Literal["started"] = "started"
    time_budget_seconds: float = Field(gt=0, allow_inf_nan=False)


class PavementSolveSolution(_Event):
    type: Literal["solution"] = "solution"
    solution_kind: Literal["initial", "improvement"]
    solved: ScenarioSolveResult


class PavementSolveComplete(_Event):
    type: Literal["complete"] = "complete"
    solved: ScenarioSolveResult


class PavementSolveError(_Event):
    type: Literal["error"] = "error"
    code: str
    message: str


PavementSolveEvent = Annotated[
    PavementSolveStarted | PavementSolveSolution | PavementSolveComplete | PavementSolveError,
    Field(discriminator="type"),
]

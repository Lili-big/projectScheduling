"""Bounded, request-local delivery of pavement incumbents."""
import asyncio
import logging
from threading import Lock, Thread
from time import perf_counter

import anyio
from starlette.responses import StreamingResponse

from ..contracts import PavementSolveStarted, PavementSolveSolution, PavementSolveComplete, PavementSolveError
from ..scheduling.solver.strategies.pavement import HintInconsistent, SolveCancelled, SolveControl

logger = logging.getLogger(__name__)


class SolveMailbox:
    """Preserve the first plan and terminal, coalesce subsequent improvements."""
    def __init__(self, budget):
        self.lock = Lock()
        self.began = perf_counter()
        self.sequence = 1
        self.first = PavementSolveStarted(sequence=1, elapsed_seconds=0, time_budget_seconds=budget)
        self.initial = self.latest = self.terminal = None
        self.has_solution = False

    def _fields(self):
        self.sequence += 1
        return dict(sequence=self.sequence, elapsed_seconds=perf_counter() - self.began)

    def solution(self, solved):
        with self.lock:
            event = PavementSolveSolution(**self._fields(), solved=solved,
                solution_kind="improvement" if self.has_solution else "initial")
            if not self.has_solution:
                self.initial = event
                self.has_solution = True
            else:
                self.latest = event

    def complete(self, solved):
        with self.lock:
            self.terminal = PavementSolveComplete(**self._fields(), solved=solved)

    def error(self, code="PAVEMENT_SOLVE_FAILED", message="本次优化发生内部错误，未完成；已收到的方案可供查看，请查看服务日志。"):
        with self.lock:
            self.terminal = PavementSolveError(**self._fields(), code=code, message=message)

    def pop(self):
        with self.lock:
            for name in ("first", "initial", "latest", "terminal"):
                event = getattr(self, name)
                if event is not None:
                    setattr(self, name, None)
                    return event
        return None


def pavement_stream_response(run, budget):
    async def body():
        mailbox = SolveMailbox(budget)
        control = SolveControl()
        def worker():
            try:
                mailbox.complete(run(mailbox.solution, control))
            except SolveCancelled:
                pass
            except HintInconsistent as exc:
                logger.exception("Pavement optimization model inconsistent with retained plan")
                mailbox.error("PAVEMENT_OPTIMIZER_INCONSISTENT", f"{exc} 本次优化未完成，保留最后合法方案。")
            except Exception:
                logger.exception("Pavement streaming solve failed")
                mailbox.error()
        thread = Thread(target=worker, name="pavement-solve", daemon=True)
        thread.start()
        try:
            while True:
                event = mailbox.pop()
                if event is None:
                    await asyncio.sleep(.02)
                    continue
                yield event.model_dump_json() + "\n"
                if event.type in {"complete", "error"}:
                    break
        finally:
            control.cancel()
            # ASGI disconnect cancels iteration. Shield cleanup so the worker
            # cannot outlive this response, including the solver-start race.
            with anyio.CancelScope(shield=True):
                await anyio.to_thread.run_sync(thread.join)
    return StreamingResponse(body(), media_type="application/x-ndjson",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

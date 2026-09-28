import asyncio
import json
import sys
from pathlib import Path
from threading import Event, enumerate as threads
from time import perf_counter

import pytest
from types import SimpleNamespace

sys.path[:0] = [str(Path(__file__).resolve().parents[1]), str(Path(__file__).resolve().parent)]
from test_pavement_generation import shared_fleet_scenario
from test_project_master_api import _app
from asgi_client import request as asgi_request
from app.api.pavement_stream import SolveMailbox, pavement_stream_response
from app.scheduling.application.pavement import solve_pavement_scenario
from app.scheduling.solver.strategies.pavement import SolveControl, SolveCancelled, _optimize


def test_mailbox_preserves_initial_best_and_terminal_with_bounded_storage():
    solved = solve_pavement_scenario(shared_fleet_scenario())
    mailbox = SolveMailbox(15)
    for _ in range(100): mailbox.solution(solved)
    mailbox.complete(solved)
    events = [mailbox.pop() for _ in range(4)]
    assert [e.type for e in events] == ["started", "solution", "solution", "complete"]
    assert [e.sequence for e in events] == [1, 2, 101, 102]
    assert events[1].solution_kind == "initial" and events[2].solution_kind == "improvement"
    assert mailbox.pop() is None


def test_initial_reaches_reader_before_worker_finishes():
    solved = solve_pavement_scenario(shared_fleet_scenario())
    release = Event()
    calls = []
    def run(publish, control):
        calls.append(1); publish(solved)
        assert release.wait(2)
        return solved
    async def consume():
        response = pavement_stream_response(run, 15)
        it = response.body_iterator
        assert json.loads(await anext(it))["type"] == "started"
        assert json.loads(await anext(it))["type"] == "solution"
        release.set()
        assert json.loads(await anext(it))["type"] == "complete"
        with pytest.raises(StopAsyncIteration): await anext(it)
    asyncio.run(consume())
    assert calls == [1]
    assert not any(t.name == "pavement-solve" for t in threads())


def test_disconnect_stops_request_and_releases_thread():
    stopped = Event()
    def run(publish, control):
        try:
            assert control.cancelled.wait(2)
            control.check()
        finally: stopped.set()
    async def consume():
        it = pavement_stream_response(run, 15).body_iterator
        await anext(it)
        await it.aclose()
    asyncio.run(consume())
    assert stopped.is_set()
    assert not any(t.name == "pavement-solve" for t in threads())


def test_runtime_error_is_terminal_and_does_not_claim_success():
    def run(*args): raise RuntimeError("test private internals")
    async def consume():
        return [json.loads(line) async for line in pavement_stream_response(run, 15).body_iterator]
    events = asyncio.run(consume())
    assert [e["type"] for e in events] == ["started", "error"]
    assert "private internals" not in events[-1]["message"]


def test_control_cancels_before_binding_and_during_solver_start(monkeypatch):
    from ortools.sat.python import cp_model
    control = SolveControl(); control.cancel()
    with pytest.raises(SolveCancelled): _optimize(cp_model.CpModel(), 15, control=control)
    control = SolveControl()
    stopped = Event()
    def fake_solve(self, model, callback):
        control.cancel()  # stop request races with Solve creating its wrapper
        assert stopped.wait(1)
        return cp_model.UNKNOWN
    monkeypatch.setattr(cp_model.CpSolver, "Solve", fake_solve)
    monkeypatch.setattr(cp_model.CpSolver, "StopSearch", lambda self: stopped.set())
    with pytest.raises(SolveCancelled): _optimize(cp_model.CpModel(), 15, control=control)


def test_stream_api_domain_error_complete_and_read_only(tmp_path):
    from test_pavement_solver import fleet_pending_scenario
    scenario = fleet_pending_scenario(); before = scenario.model_dump_json()
    app = _app(tmp_path)
    content = app.openapi()["paths"]["/api/solve-scenario/stream"]["post"]["responses"]["200"]["content"]
    assert list(content) == ["application/x-ndjson"]
    async def streaming_app(scope, receive, send):
        scope["asgi"]["spec_version"] = "2.4"
        await app(scope, receive, send)
    def post(path, *, json):
        status, headers, body = asgi_request(streaming_app, "POST", path, json)
        return SimpleNamespace(status_code=status, headers=headers, text=body.decode())
    client = SimpleNamespace(post=post)
    response = client.post("/api/solve-scenario/stream", json=scenario.model_dump(mode="json"))
    assert response.status_code == 200 and "application/x-ndjson" in response.headers["content-type"]
    events = [json.loads(line) for line in response.text.splitlines()]
    assert events[0]["type"] == "started" and events[-1]["type"] == "complete"
    assert events[1]["type"] == "solution" and events[-1]["solved"]["result"]["tasks"]
    for event in events:
        if "solved" not in event:
            continue
        solved = event["solved"]
        assert solved["generated"]["schedule_input"]["pavement_handover_scope"]["pending_policy"] == "per_fleet_last"
        assert solved["result"]["stats"]["pavement_handover"]["pending_policy"] == "per_fleet_last"
    initial = {t["component_id"]: t for t in events[1]["solved"]["result"]["tasks"]}
    assert initial["B-1"]["start_date"] == "2027-04-22"
    assert initial["A-2"]["finish_date"] == "2027-04-28"
    assert scenario.model_dump_json() == before
    raw = scenario.model_dump(mode="json"); raw["engineering_domain"] = "bridge"
    assert client.post("/api/solve-scenario/stream", json=raw).status_code == 422
    raw = scenario.model_dump(mode="json"); raw["time_limit_seconds"] = "Infinity"
    assert client.post("/api/solve-scenario/stream", json=raw).status_code == 422
    invalid = scenario.model_copy(deep=True); invalid.resource_pools = []
    response = client.post("/api/solve-scenario/stream", json=invalid.model_dump(mode="json"))
    final = json.loads(response.text.splitlines()[-1])
    assert final["type"] == "complete" and final["solved"]["result"]["status"] == "MODEL_INVALID"


def test_idle_stream_improves_under_ten_day_cap_and_preserves_state(tmp_path):
    from test_pavement_api import idle_api_payload
    payload=idle_api_payload(); before=json.dumps(payload,sort_keys=True)
    app=_app(tmp_path)
    state_before={str(p):p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    async def streaming_app(scope,receive,send):
        scope["asgi"]["spec_version"]="2.4"
        await app(scope,receive,send)
    status,headers,body=asgi_request(streaming_app,"POST","/api/solve-scenario/idle/stream",payload)
    assert status==200,body
    events=[json.loads(line) for line in body.decode().splitlines()]
    assert [events[0]["type"],events[1]["solution_kind"],events[-1]["type"]]==["started","initial","complete"]
    plans=[e["solved"]["result"] for e in events if "solved" in e]
    assert plans[0]["pavement_idle_optimization"]["final_idle_days"]==8
    assert plans[-1]["pavement_idle_optimization"]["final_idle_days"]==0
    assert plans[-1]["pavement_idle_optimization"]["proved_optimal"]
    assert all(p["objective_days"]<=10 for p in plans)
    assert all(p["pavement_idle_optimization"]["makespan_cap_days"]==10 for p in plans)
    assert json.dumps(payload,sort_keys=True)==before
    assert {str(p):p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}==state_before


def test_idle_model_inconsistency_is_named_and_keeps_the_published_baseline():
    from test_pavement_hybrid import idle_case
    from app.scheduling.solver.strategies.pavement import HintInconsistent
    from app.contracts import ScenarioSolveResult, GeneratedScheduleInput
    s,r,seed,baseline=idle_case()
    solved=ScenarioSolveResult(scenario_id="test",scenario_name="test",generated=GeneratedScheduleInput(schedule_input=s),result=baseline)
    def run(publish,control):
        publish(solved)
        raise HintInconsistent("已有合法基准，但模型报告无解。")
    async def consume():
        return [json.loads(line) async for line in pavement_stream_response(run,15).body_iterator]
    events=asyncio.run(consume())
    assert [e["type"] for e in events]==["started","solution","error"]
    assert events[-1]["code"]=="PAVEMENT_OPTIMIZER_INCONSISTENT"
    assert "保留最后合法方案" in events[-1]["message"]

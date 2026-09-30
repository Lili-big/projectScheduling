import sys
import sqlite3
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Event

import pytest

sys.path[:0] = [str(Path(__file__).resolve().parents[1]), str(Path(__file__).resolve().parent)]
from asgi_client import json_request
from test_project_master_api import _app
from test_pavement_master import pavement_snapshot
from app.project_master.repository import ProjectMasterRepository


def publish(repo, snapshot, project="road"):
    from uuid import uuid4
    old = repo.get_current_version(project)
    batch = repo.create_import_batch(project_id=project, file_name="fixture.xlsx", file_sha256="test",
        expected_current_version_id=old.version_id if old else None, created_by="test")
    v = repo.create_draft_version(batch_id=batch.batch_id, project_id=project, content_fingerprint=uuid4().hex,
        snapshot=snapshot, issues=[], diff_entries=[], created_by="test", base_version_id=old.version_id if old else None)
    return repo.confirm_version(v.version_id, expected_current_version_id=old.version_id if old else None, confirmed_by="test")


def setup(tmp_path):
    app = _app(tmp_path)
    repo = app.state.project_master_service.repository
    snapshot = pavement_snapshot()
    for section in snapshot.workpoints[0].structures:
        for p in section.parameters:
            if p.parameter_code == "construction_length_m": p.value = 1790
    publish(repo, snapshot)
    return app, repo, snapshot


PATH = "/api/projects/road/pavement-progress"
ID = "A-left-W"
def cell(amount, day="2026-09-01", cid=ID):
    return {"component_id": cid, "progress_date": day, "completed_length_m": amount}
def save(app, view, *cells):
    return json_request(app, "PUT", PATH, {"expected_master_version_id": view["master_version_id"],
        "expected_revision": view["revision"], "cells": list(cells)})
def row(view, cid=ID):
    return next(r for r in view["rows"] if r["component_id"] == cid)


def test_read_current_master_without_solver_or_records(tmp_path):
    app, repo, snapshot = setup(tmp_path)
    status, view = json_request(app, "GET", PATH)
    assert status == 200, view
    assert len(view["rows"]) == 4 and view["entries"] == [] and view["revision"] == 0
    assert row(view)["design_length_m"] == 1790
    assert row(view)["width_m"] == 10 and row(view)["thickness_m"] == .2
    assert row(view)["start_chainage"] == "K0+000"
    assert json_request(app, "GET", "/api/projects/missing/pavement-progress")[0] == 404
    s = snapshot.workpoints[0].structures[0]
    s.parameters = [p for p in s.parameters if p.parameter_code not in ("width_m", "construction_length_m")]
    s.components[0].parameters = []
    s.components[0].unit = "t"
    publish(repo, snapshot)
    view = json_request(app, "GET", PATH)[1]
    assert row(view)["design_length_m"] is None and row(view)["width_m"] is None and row(view)["thickness_m"] is None
    status, view = save(app, view, cell(100))
    assert status == 200 and row(view)["completed_length_m"] == 100 and row(view)["remaining_length_m"] is None


def test_cross_month_replace_clear_zero_overrun_and_restart(tmp_path):
    app, repo, _ = setup(tmp_path)
    original = repo.get_current_version("road")
    master_before = repo.load_snapshot(original.version_id)
    view = json_request(app, "GET", PATH)[1]
    status, view = save(app, view, cell(300), cell(450,"2026-09-02"), cell(100,"2026-10-01"))
    assert status == 200 and row(view)["completed_length_m"] == 850 and row(view)["remaining_length_m"] == 940
    view = save(app, view, cell(320))[1]
    assert row(view)["remaining_length_m"] == 920
    view = save(app, view, cell(None,"2026-09-02"))[1]
    assert row(view)["remaining_length_m"] == 1370
    view = save(app, view, cell(0,"2026-09-02"),cell(1700))[1]
    assert row(view)["remaining_length_m"] == -10 and row(view)["overrun_length_m"] == 10
    revision = view["revision"]
    assert save(app,view,cell(1700))[1]["revision"] == revision
    assert any(e["completed_length_m"] == 0 for e in view["entries"])
    app.state.project_master_service.repository = ProjectMasterRepository(repo.path)
    assert json_request(app,"GET",PATH)[1] == view
    assert repo.get_current_version("road") == original and repo.load_snapshot(original.version_id) == master_before
    view = save(app,view,cell(.1),cell(.2,"2026-09-02"),cell(None,"2026-10-01"))[1]
    assert row(view)["completed_length_m"] == .3


@pytest.mark.parametrize("bad", [-1, True, "300", .0001, 1e20])
def test_invalid_amount_rolls_back_whole_batch(tmp_path,bad):
    app,_,_ = setup(tmp_path)
    before = json_request(app,"GET",PATH)[1]
    assert save(app,before,cell(100),cell(bad,"2026-09-02"))[0] == 422
    assert json_request(app,"GET",PATH)[1] == before


@pytest.mark.parametrize("cells", [[cell(1),cell(2)], [cell(1),cell(2,"2026-02-30")], [cell(1),cell(2,cid="foreign")]])
def test_invalid_keys_dates_roll_back(tmp_path,cells):
    app,_,_ = setup(tmp_path)
    before=json_request(app,"GET",PATH)[1]
    assert save(app,before,*cells)[0]==422
    assert json_request(app,"GET",PATH)[1]==before


def test_history_identity_and_master_conflicts(tmp_path):
    app,repo,snapshot=setup(tmp_path)
    base=json_request(app,"GET",PATH)[1]
    saved=save(app,base,cell(100))[1]
    assert save(app,base,cell(200))[0]==409
    s=snapshot.workpoints[0].structures[0]
    s.components[0].component_name="改名后的水稳"
    for p in s.parameters:
        if p.parameter_code=="construction_length_m": p.value=90
    publish(repo,snapshot)
    assert save(app,saved,cell(200))[1]["detail"]["code"]=="PAVEMENT_PROGRESS_MASTER_CHANGED"
    view=json_request(app,"GET",PATH)[1]
    assert row(view)["component_name"]=="改名后的水稳" and row(view)["remaining_length_m"]==-10
    s.components[0].enabled=False
    publish(repo,snapshot)
    view=json_request(app,"GET",PATH)[1]
    assert ID not in [r["component_id"] for r in view["rows"]]
    assert view["historical_rows"][0]["status"]=="disabled"
    assert save(app,view,cell(1))[0]==422
    s.components[0].enabled=True
    publish(repo,snapshot)
    assert row(json_request(app,"GET",PATH)[1])["completed_length_m"]==100
    s.components[0].component_id="replacement-same-name"
    publish(repo,snapshot)
    view=json_request(app,"GET",PATH)[1]
    assert row(view,"replacement-same-name")["completed_length_m"]==0
    assert view["historical_rows"][0]["status"]=="removed"
    assert view["historical_rows"][0]["completed_length_m"]==100


def test_two_connections_compare_and_commit_atomically(tmp_path):
    app,repo,_=setup(tmp_path)
    before=json_request(app,"GET",PATH)[1]
    app2=_app(tmp_path)
    gate=Barrier(2)
    def writer(target,value):
        gate.wait()
        return save(target,before,cell(value),cell(value,"2026-09-02"))[0]
    with ThreadPoolExecutor(2) as pool:
        futures=[pool.submit(writer,app,100),pool.submit(writer,app2,200)]
        assert sorted(f.result() for f in futures)==[200,409]
    view=json_request(app,"GET",PATH)[1]
    assert view["revision"]==1 and len(view["entries"])==2
    assert len({e["completed_length_m"] for e in view["entries"]})==1
    with repo.connection() as c:
        with pytest.raises(sqlite3.IntegrityError):
            c.execute("DELETE FROM project_master_versions WHERE version_id=?",(view["master_version_id"],))


def test_project_isolation_nonfinite_and_storage_error(tmp_path,monkeypatch):
    from app.contracts.project_master import PavementProgressCell
    from pydantic import ValidationError
    app,repo,snapshot=setup(tmp_path)
    publish(repo,snapshot,"other")
    view=json_request(app,"GET",PATH)[1]
    save(app,view,cell(42))
    assert json_request(app,"GET","/api/projects/other/pavement-progress")[1]["entries"]==[]
    for amount in (float("nan"),float("inf")):
        with pytest.raises(ValidationError): PavementProgressCell.model_validate(cell(amount))
    def fail(): raise sqlite3.OperationalError("fixture unavailable")
    monkeypatch.setattr(repo,"_connect",fail)
    assert json_request(app,"GET",PATH)[0]==503


def test_master_confirmation_cannot_interleave_with_progress_validation(tmp_path,monkeypatch):
    from app.project_master import pavement_progress as progress
    app,repo,snapshot=setup(tmp_path)
    view=json_request(app,"GET",PATH)[1]
    entered,release=Event(),Event()
    original=progress._master_rows
    def held(repository,connection,version):
        if not entered.is_set():
            entered.set()
            assert release.wait(5)
        return original(repository,connection,version)
    monkeypatch.setattr(progress,"_master_rows",held)
    snapshot.workpoints[0].structures[0].components[0].enabled=False
    second=ProjectMasterRepository(repo.path)
    with ThreadPoolExecutor(2) as pool:
        writing=pool.submit(save,app,view,cell(55))
        assert entered.wait(5)
        changing=pool.submit(publish,second,snapshot)
        assert not changing.done()
        release.set()
        assert writing.result()[0]==200
        changing.result()
    after=json_request(app,"GET",PATH)[1]
    assert after["historical_rows"][0]["completed_length_m"]==55
    assert save(app,view,cell(90))[0]==409

import json
import sys
from pathlib import Path

sys.path[:0]=[str(Path(__file__).resolve().parents[1]),str(Path(__file__).resolve().parent)]
from asgi_client import json_request, request
from test_project_master_api import _app, _multipart
from test_pavement_master import pavement_snapshot
from test_pavement_generation import sample_scenario, shared_fleet_scenario
from app.project_master.workbook import export_snapshot
from app.scenario_data import pavement_scenario
from app.contracts import PavementLayerCondition
from app.scheduling.generation.pavement import generate_pavement_input


def test_handover_save_roundtrip_and_stale_version(tmp_path):
    from test_pavement_layer_template import setup_project
    from app.project_master.workbook import parse_workbook
    app, service, base = setup_project(tmp_path)
    section_id = "A-left"
    path = f"/api/project-master/versions/{base}/pavement-sections/{section_id}/handover"
    payload = {"status":"handed_over", "available_date":None, "note":"路床已移交", "created_by":"tester"}
    status, saved = json_request(app, "PUT", path, payload)
    assert status == 200, saved
    current = saved["version_id"]
    assert current != base
    status, conflict = json_request(app, "PUT", path, {**payload, "status":"pending"})
    assert status == 409 and conflict["detail"]["code"] == "CURRENT_VERSION_CHANGED"
    for state, dt in [("dated", None), ("pending", "2026-01-01"), ("invalid", None)]:
        assert json_request(app, "PUT", path.replace(base, current), {**payload, "status":state, "available_date":dt})[0] == 422
    service = app.state.project_master_service
    old = service.repository.load_snapshot(base)
    new = service.repository.load_snapshot(current)
    assert new.workpoints[0].structures[0].components == old.workpoints[0].structures[0].components
    assert new.workpoints[0].structures[1:] == old.workpoints[0].structures[1:]
    status, _, blob = request(app, "GET", f"/api/project-master/versions/{current}/export")
    assert status == 200
    params = {p.parameter_code:p.value for p in parse_workbook(blob)[0].workpoints[0].structures[0].parameters}
    assert params["roadbed_handover_status"] == "handed_over" and not params.get("roadbed_available_date")


def test_mixed_master_scope_is_authoritative_and_pending_does_not_mask_other_errors(tmp_path):
    from app.contracts import ConfirmProjectMasterVersionRequest, ParameterValue
    app = _app(tmp_path)
    service = app.state.project_master_service
    snapshot = pavement_snapshot()
    sections = snapshot.workpoints[0].structures
    for section, status in zip(sections, ["dated", "handed_over", "pending", "dated"]):
        section.parameters = [p for p in section.parameters if p.parameter_code != "roadbed_available_date" or status == "dated"]
        section.parameters.append(ParameterValue(parameter_code="roadbed_handover_status", value_type="text", value=status))
    sections[2].parameters.append(ParameterValue(parameter_code="roadbed_handover_note", value_type="text", value="征地未解决"))
    sections[1].components[0].parameters.append(ParameterValue(parameter_code="roadbed_handover_status", value_type="text", value="pending"))
    batch = service.import_workbook(project_id="road", file_name="mixed.xlsx", content=export_snapshot(snapshot),created_by="tester",expected_current_version_id=None)
    version = service.confirm_version(batch.created_version_id, ConfirmProjectMasterVersionRequest(confirmed_by="tester", acknowledge_warning_codes=list({i.issue_code for i in batch.issues})))
    scenario = pavement_scenario("road")
    scenario.project_data_version_id = version.version_id
    for pool in scenario.resource_pools: pool.quantity=1; pool.transfer_days=1
    status, solved = json_request(app,"POST","/api/solve-scenario",scenario.model_dump(mode="json"))
    assert status == 200 and solved["result"]["status"] in {"FEASIBLE","OPTIMAL"}, solved
    assert len(solved["result"]["tasks"]) == 4
    scope = solved["result"]["stats"]["pavement_handover"]
    assert scope == solved["generated"]["source_summary"]["pavement_handover"]
    assert scope["included_section_count"] == 4 and scope["pending_sections"][0]["reason"] == "征地未解决"
    schedule = solved["generated"]["schedule_input"]
    schedule["tasks"][0]["properties"].update(roadbed_handover_status="pending",roadbed_available_date=None)
    assert json_request(app,"POST","/api/solve",schedule)[0] == 422
    for pool in scenario.resource_pools: pool.quantity=0
    _, invalid = json_request(app,"POST","/api/solve-scenario",scenario.model_dump(mode="json"))
    assert invalid["result"]["status"] == "MODEL_INVALID"
    assert "PAVEMENT_RESOURCE_MISSING" in {d["code"] for d in invalid["diagnostics"]}
    assert invalid["result"]["stats"]["pavement_handover"] == scope


def test_disable_pending_section_preserves_master_and_excludes_it_from_solve(tmp_path):
    from app.contracts import ConfirmProjectMasterVersionRequest, ParameterValue
    from test_pavement_layer_template import editable_layers, save_layers

    app = _app(tmp_path)
    service = app.state.project_master_service
    snapshot = pavement_snapshot()
    section = snapshot.workpoints[0].structures[0]
    section.parameters = [p for p in section.parameters if p.parameter_code != "roadbed_available_date"]
    section.parameters.append(ParameterValue(parameter_code="roadbed_handover_status", value_type="text", value="pending"))
    batch = service.import_workbook(project_id="road", file_name="disable.xlsx", content=export_snapshot(snapshot),
                                    created_by="tester", expected_current_version_id=None)
    base = service.confirm_version(batch.created_version_id, ConfirmProjectMasterVersionRequest(
        confirmed_by="tester", acknowledge_warning_codes=list({i.issue_code for i in batch.issues})))
    before = service.repository.load_snapshot(base.version_id)
    layers = editable_layers(before.workpoints[0].structures[0])
    status, saved = save_layers(app, base.version_id, [{**layer, "enabled": False} for layer in layers])
    assert status == 200, saved
    expected = before.model_copy(deep=True)
    for component in expected.workpoints[0].structures[0].components:
        component.enabled = False
    assert service.repository.load_snapshot(saved["version_id"]) == expected
    assert service.repository.load_snapshot(base.version_id) == before

    scenario = pavement_scenario("road")
    scenario.project_data_version_id = saved["version_id"]
    scenario.time_limit_seconds = 1
    for pool in scenario.resource_pools:
        pool.quantity = 1
        pool.transfer_days = 1
    status, solved = json_request(app, "POST", "/api/solve-scenario", scenario.model_dump(mode="json"))
    assert status == 200 and solved["result"]["status"] in {"FEASIBLE", "OPTIMAL"}, solved
    assert not [d for d in solved["diagnostics"] if d["level"] == "error"]
    assert {t["structure_id"] for t in solved["result"]["tasks"]} == {"A-right", "B-left", "B-right"}
    scope = solved["generated"]["schedule_input"]["pavement_handover_scope"]
    assert (scope["total_section_count"], scope["included_section_count"], scope["included_layer_count"]) == (3, 3, 3)
    assert scope["pending_sections"] == []
    assert solved["result"]["pavement_summary"]["pending_section_dates"] == []

    status, restored = save_layers(app, saved["version_id"], layers)
    assert status == 200, restored
    assert service.repository.load_snapshot(restored["version_id"]) == before
    scenario.project_data_version_id = restored["version_id"]
    status, generated = json_request(app, "POST", "/api/generate-schedule-input", scenario.model_dump(mode="json"))
    assert status == 200 and len(generated["schedule_input"]["tasks"]) == 4
    assert generated["schedule_input"]["pavement_handover_scope"]["pending_sections"][0]["structure_id"] == section.structure_id


def test_direct_shared_solve_enforces_capabilities_scope_and_task_identity(tmp_path):
    from copy import deepcopy
    app = _app(tmp_path)
    schedule = generate_pavement_input(shared_fleet_scenario()).schedule_input.model_dump(mode="json")
    status, result = json_request(app, "POST", "/api/solve", schedule)
    assert status == 200 and result["objective_days"] == 2, result
    for patch in ({"compatible_process_ids":[]}, {"compatible_process_ids":["pavement-cement_stabilized_base"]}, {"eligible_workpoint_ids":[]}):
        invalid = deepcopy(schedule)
        invalid["resources"][0].update(patch)
        assert json_request(app,"POST","/api/solve",invalid)[0] == 422
    invalid = deepcopy(schedule)
    invalid["tasks"][0]["pavement_context"].pop("process_id")
    status, result = json_request(app, "POST", "/api/solve", invalid)
    assert status == 422 and result["detail"]["code"] == "PAVEMENT_REFERENCE_INVALID"


def test_pending_direct_and_scenario_solve_have_same_dates_and_keep_facts(tmp_path):
    from test_pavement_solver import pending_last_scenario
    app = _app(tmp_path)
    s = pending_last_scenario()
    raw = s.model_dump(mode="json")
    status, response = json_request(app, "POST", "/api/solve-scenario", raw)
    assert status == 200 and response["result"]["status"] in {"OPTIMAL", "FEASIBLE"}, response
    schedule = response["generated"]["schedule_input"]
    assert schedule["pavement_handover_scope"]["pending_policy"] == "per_fleet_last"
    assert response["result"]["stats"]["pavement_handover"]["pending_policy"] == "per_fleet_last"
    from copy import deepcopy
    old = deepcopy(schedule)
    old["pavement_handover_scope"]["pending_policy"] = "strict_last"
    status, invalid = json_request(app, "POST", "/api/solve", old)
    assert status == 422 and invalid["detail"]["code"] == "PAVEMENT_INPUT_OUTDATED"
    assert "重新生成" in invalid["detail"]["message"]
    schedule.pop("pavement_handover_scope")
    status, direct = json_request(app, "POST", "/api/solve", schedule)
    assert status == 200, direct
    assert direct["pavement_summary"]["pending_section_dates"] == response["result"]["pavement_summary"]["pending_section_dates"]
    pending = next(t for t in direct["tasks"] if t["structure_id"] == "B")
    assert pending["properties"]["roadbed_handover_status"] == "pending"
    assert pending["properties"]["roadbed_available_date"] is None
    assert s.model_dump(mode="json") == raw
    from app.contracts import TaskOverride
    s.task_overrides["B-1"] = TaskOverride(productivity_option_id="missing")
    _, invalid = json_request(app, "POST", "/api/solve-scenario", s.model_dump(mode="json"))
    assert invalid["result"]["status"] == "MODEL_INVALID"
    assert invalid["result"].get("pavement_summary") is None


def test_shared_profile_api_save_reload_and_invalid_save_preserves_state(tmp_path, monkeypatch):
    from app.services import process_library_service as service
    from app.local_scenario_config import save_pavement_profile, apply_scenario_config
    path = tmp_path / "config.json"
    monkeypatch.setattr(service, "apply_local_scenario_config", lambda s: apply_scenario_config(s, path=path))
    monkeypatch.setattr(service, "save_pavement_profile", lambda s: save_pavement_profile(s, path=path))
    app = _app(tmp_path)
    scenario = shared_fleet_scenario()
    raw = scenario.model_dump(mode="json")
    payload = {k:raw[k] for k in ("engineering_domain", "process_library", "logic_rules", "resource_pools", "pavement_settings", "task_overrides")}
    payload["project_id"] = "shared-api"
    status, saved = json_request(app, "PUT", "/api/local-scenario-config", payload)
    assert status == 200, saved
    status, restored = json_request(app,"GET","/api/demo-scenario?engineering_domain=pavement&project_id=shared-api")
    assert status == 200 and restored["resource_pools"][1]["compatible_process_ids"] == raw["resource_pools"][1]["compatible_process_ids"]
    before = path.read_bytes()
    payload["resource_pools"][1]["compatible_process_ids"] = []
    assert json_request(app, "PUT", "/api/local-scenario-config", payload)[0] == 422
    assert path.read_bytes() == before


def test_empty_domain_template_and_invalid_domain(tmp_path):
    app=_app(tmp_path)
    status,scenario=json_request(app,"GET","/api/demo-scenario?engineering_domain=pavement&project_id=test-empty")
    assert status==200 and scenario["engineering_domain"]=="pavement"
    assert scenario["project"]["bridges"]==[]
    assert len(scenario["process_library"])==3
    assert json_request(app,"GET","/api/demo-scenario?engineering_domain=unknown")[0]==422
    assert request(app,"GET","/api/project-master/template?engineering_domain=pavement")[0]==200
    assert json_request(app,"GET","/api/projects/test-empty/project-master/versions/current")[0]==404


def test_import_confirm_reload_generate_solve_and_repeat(tmp_path):
    app=_app(tmp_path)
    snapshot = pavement_snapshot()
    second = snapshot.workpoints[0].model_copy(deep=True, update={"workpoint_id": "ROAD2", "workpoint_name": "演示工点二"})
    second.structures = second.structures[2:]
    for structure in second.structures:
        structure.workpoint_id = "ROAD2"
    snapshot.workpoints[0].structures = snapshot.workpoints[0].structures[:2]
    snapshot.workpoints.append(second)
    content=export_snapshot(snapshot)
    body,content_type=_multipart({"created_by":"tester"},content)
    status,_,data=request(app,"POST","/api/projects/road/project-master/imports",raw_body=body,extra_headers={"content-type":content_type})
    batch=json.loads(data)
    assert status==201,batch
    version=batch["created_version_id"]
    scenario=pavement_scenario("road")
    scenario.project_data_version_id=version
    assert json_request(app,"POST","/api/generate-schedule-input",scenario.model_dump(mode="json"))[0]==409
    assert json_request(app,"POST",f"/api/project-master/versions/{version}/confirm",{"confirmed_by":"tester","acknowledge_warning_codes":list({i["issue_code"] for i in batch["issues"]})})[0]==200
    for segment in ["A","B"]:
        for side in ["left","right"]:
            scenario.pavement_settings.layer_conditions.append(PavementLayerCondition(component_id=f"{segment}-{side}-W",wait_days=7,basis_note="演示验收条件"))
    for pool in scenario.resource_pools: pool.quantity=1; pool.transfer_days=1
    payload=scenario.model_dump(mode="json")
    status,generated=json_request(app,"POST","/api/generate-schedule-input",payload)
    assert status==200 and len(generated["schedule_input"]["tasks"])==4
    assert not [d for d in generated["validation"] if d["level"]=="error"],generated["validation"]
    status,solved=json_request(app,"POST","/api/solve-scenario?workpoint_id=ROAD",payload)
    assert status==200 and solved["result"]["status"] in {"FEASIBLE","OPTIMAL"},solved
    assert len(solved["result"]["tasks"]) == 2
    assert {t["bridge_id"] for t in solved["result"]["tasks"]} == {"ROAD"}
    assert solved["result"]["pavement_summary"]["project_data_version_id"]==version
    body,content_type=_multipart({"created_by":"tester","expected_current_version_id":version},content)
    _,_,data=request(app,"POST","/api/projects/road/project-master/imports",raw_body=body,extra_headers={"content-type":content_type})
    assert json.loads(data)["status"]=="unchanged"
    from app.project_master.repository import ProjectMasterRepository
    restored=ProjectMasterRepository(tmp_path/"project-master.db").load_snapshot(version)
    assert sum(len(w.structures) for w in restored.workpoints)==4
    assert restored.workpoints[0].structures[0].parameters
    payload["project"]["project_id"]="another"
    assert json_request(app,"POST","/api/solve-scenario",payload)[0]==409


def test_direct_solve_validation_and_unsupported_apis(tmp_path):
    app=_app(tmp_path)
    scenario=sample_scenario((700,))
    data=scenario.model_dump(mode="json")
    for route in ["solve-min-resources","solve-resource-cost"]:
        status,response=json_request(app,"POST",f"/api/{route}",{"scenario":data,"target_days":50})
        assert status==422 and response["detail"]["code"]=="PAVEMENT_STRATEGY_NOT_SUPPORTED",response
    status,response=json_request(app,"POST","/api/ai-resource-assistant/initialize-workpoint-resources",{"scenario":data})
    assert status==422 and response["detail"]["code"]=="PAVEMENT_FEATURE_NOT_SUPPORTED"
    schedule=generate_pavement_input(scenario).schedule_input.model_dump(mode="json")
    assert json_request(app,"POST","/api/solve",schedule)[0]==200
    for field in ["resources"]:
        status,_=json_request(app,"POST","/api/solve",{**schedule,field:[]})
        assert status==422
    schedule.pop("engineering_domain")
    assert json_request(app,"POST","/api/solve",schedule)[0]==422
    data["pavement_settings"]["input_kind"]="customer"
    assert json_request(app,"POST","/api/solve-scenario",data)[0]==409


def test_corrupt_config_and_stale_save_do_not_report_success(tmp_path,monkeypatch):
    from app.api.routers import system
    from app.local_scenario_config import LocalScenarioConfigError
    app=_app(tmp_path)
    def broken(*args,**kwargs): raise LocalScenarioConfigError("配置损坏")
    monkeypatch.setattr(system,"default_scenario_with_process_library",broken)
    assert json_request(app,"GET","/api/demo-scenario?engineering_domain=pavement")[0]==503
    s=sample_scenario()
    payload={key:s.model_dump(mode="json")[key] for key in ["engineering_domain","process_library","logic_rules","resource_pools","pavement_settings"]}
    payload.update(project_id="road",project_data_version_id="missing")
    assert json_request(app,"PUT","/api/local-scenario-config",payload)[0]==404


def test_demo_mirror_explicitly_rejects_pavement():
    mirror_source = (Path(__file__).resolve().parents[2] / "tools/demo-api-mirror/api.mts").read_text(encoding="utf-8")
    assert 'endsWith("/solve-scenario/stream")' in mirror_source
    code=(Path(__file__).resolve().parents[2]/"tools/demo-api-mirror/api.mts").read_text(encoding="utf-8")
    assert '"PAVEMENT_FEATURE_NOT_SUPPORTED"' in code
    assert 'req.clone().json()' in code


def test_direct_solve_rejects_ignored_strategy_and_invalid_auxiliary_wait(tmp_path):
    from copy import deepcopy
    app = _app(tmp_path)
    schedule = generate_pavement_input(sample_scenario((700,))).schedule_input.model_dump(mode="json")
    changed = deepcopy(schedule)
    changed["schedule_strategy"]["normal_earliest_start_offset"] = 20
    status, response = json_request(app, "POST", "/api/solve", changed)
    assert status == 422 and response["detail"]["code"] == "PAVEMENT_STRATEGY_NOT_SUPPORTED"
    scenario = sample_scenario((700,)).model_dump(mode="json")
    scenario["schedule_strategy"]["normal_earliest_start_offset"] = 20
    status, response = json_request(app, "POST", "/api/solve-scenario", scenario)
    assert status == 422 and response["detail"]["code"] == "PAVEMENT_STRATEGY_NOT_SUPPORTED"
    prep = deepcopy(schedule["tasks"][0])
    prep.update(id="invalid-prep", component_type="pavement_preparation", compatible_resource_types=[],
                properties={"roadbed_available_date":"2026-01-01", "wait_days": "bad", "accepted_available_offset": 0})
    prep["pavement_context"]["task_kind"] = "preparation"
    schedule["tasks"].append(prep)
    status, response = json_request(app, "POST", "/api/solve", schedule)
    assert status == 422 and response["detail"]["code"] == "PAVEMENT_DATA_INCOMPLETE"


def test_missing_fleet_reports_each_diagnostic_once(tmp_path):
    scenario = sample_scenario((700,))
    for pool in scenario.resource_pools:
        pool.quantity = 0
    status, response = json_request(_app(tmp_path), "POST", "/api/solve-scenario", scenario.model_dump(mode="json"))
    assert status == 200 and response["result"]["status"] == "MODEL_INVALID"
    identities = [json.dumps(d, sort_keys=True) for d in response["diagnostics"]]
    assert len(identities) == len(set(identities))


def test_chain_preview_api_and_direct_solve_use_same_duration_and_finish(tmp_path):
    app = _app(tmp_path)
    s = sample_scenario((1790,), ("granular_base",) + ("cement_stabilized_base",) * 3)
    for p in s.process_library:
        for o in p.productivity_options: o.productivity_value = 800
    payload = s.model_dump(mode="json")
    status, generated = json_request(app, "POST", "/api/generate-schedule-input", payload)
    assert status == 200 and generated["schedule_input"].get("readiness_conditions", []) == []
    status, direct = json_request(app, "POST", "/api/solve", generated["schedule_input"])
    assert status == 200, direct
    status, scenario = json_request(app, "POST", "/api/solve-scenario", payload)
    assert status == 200
    assert direct["plan_finish_date"] == scenario["result"]["plan_finish_date"]
    assert [t["duration_days"] for t in direct["tasks"]] == [3] * 4
    legacy = generated["schedule_input"]
    legacy["tasks"][-1]["properties"]["wait_days"] = 7
    status, response = json_request(app, "POST", "/api/solve", legacy)
    assert status == 422 and "重新生成" in json.dumps(response, ensure_ascii=False)


def test_asphalt_without_thickness_generates_and_solves_with_seven_day_cure(tmp_path):
    from app.contracts.pavement import PavementDependencyRule
    app = _app(tmp_path)
    scenario = sample_scenario((1001,), ("cement_stabilized_base",) * 3 + ("asphalt_course",))
    scenario.time_limit_seconds = 1
    for component in scenario.project.bridges[0].work_sections[0].structures[0].components:
        component.properties.pop("thickness_m")
    scenario.pavement_settings.dependency_rules = [
        PavementDependencyRule(predecessor_key="layer:cement_stabilized_base:3",
                               successor_key="layer:asphalt_course:1", relationship="FS", lag_days=7)]
    raw = scenario.model_dump(mode="json")
    status, generated = json_request(app, "POST", "/api/generate-schedule-input", raw)
    assert status == 200 and not [d for d in generated["validation"] if d["level"] == "error"], generated
    asphalt = next(t for t in generated["schedule_input"]["tasks"] if t["component_type"] == "asphalt_course")
    assert asphalt["duration_days"] == 2 and asphalt["properties"]["productivity_value"] == 1000
    assert "thickness_m" not in asphalt["properties"]
    link = next(l for l in generated["schedule_input"]["precedence_links"] if l["successor_id"] == asphalt["id"])
    assert (link["predecessor_id"], link["relationship"], link["lag_days"]) == ("pavement:A-3", "FS", 7)
    status, direct = json_request(app, "POST", "/api/solve", generated["schedule_input"])
    assert status == 200 and direct["status"] in {"OPTIMAL", "FEASIBLE"}, direct
    status, solved = json_request(app, "POST", "/api/solve-scenario", raw)
    assert status == 200 and solved["result"]["status"] in {"OPTIMAL", "FEASIBLE"}, solved
    for result in (direct, solved["result"]):
        tasks = {t["id"]: t for t in result["tasks"]}
        assert tasks[asphalt["id"]]["start_offset"] >= tasks["pavement:A-3"]["end_offset"] + 7
        assert len(tasks) == 4
    for pool in scenario.resource_pools:
        if pool.type == "asphalt_paving_crew":
            pool.quantity = 0
    _, invalid = json_request(app, "POST", "/api/solve-scenario", scenario.model_dump(mode="json"))
    assert invalid["result"]["status"] == "MODEL_INVALID"
    assert "PAVEMENT_RESOURCE_MISSING" in {d["code"] for d in invalid["diagnostics"]}
    assert not any("thickness_m" in d["message"] for d in invalid["diagnostics"])


def test_hybrid_fallback_both_api_paths_are_complete_and_read_only(tmp_path, monkeypatch):
    from test_pavement_generation import handover_scenario
    from app.scheduling.solver.strategies import pavement
    monkeypatch.setattr(pavement, "_optimize", lambda *args: (None, "UNKNOWN", .001))
    app = _app(tmp_path)
    scenario = handover_scenario()
    before = scenario.model_dump_json()
    data_before = {p.name: p.read_bytes() for p in tmp_path.iterdir() if p.is_file()}
    status, generated = json_request(app, "POST", "/api/generate-schedule-input", scenario.model_dump(mode="json"))
    assert status == 200
    status, direct = json_request(app, "POST", "/api/solve", generated["schedule_input"])
    assert status == 200
    status, solved = json_request(app, "POST", "/api/solve-scenario", scenario.model_dump(mode="json"))
    assert status == 200
    other = solved["result"]
    assert direct["tasks"] == other["tasks"]
    assert direct["pavement_summary"] == other["pavement_summary"]
    for result in [direct, other]:
        assert result["status"] == "FEASIBLE" and len(result["tasks"]) == 8
        assert result["pavement_optimization"]["optimizer_status"] == "UNKNOWN"
        assert result["pavement_optimization"]["selected_source"] == "greedy"
        assert result["pavement_summary"]["pending_section_dates"]
        assert not result["validation"]
    assert all(d["code"] == "PAVEMENT_ROADBED_PENDING" and d["level"] == "info" for d in solved["diagnostics"])
    assert scenario.model_dump_json() == before
    assert {p.name: p.read_bytes() for p in tmp_path.iterdir() if p.is_file()} == data_before


def idle_api_payload():
    from app.scheduling.application.pavement import solve_pavement_scenario
    from app.scheduling.solver.strategies import pavement as solver
    scenario=shared_fleet_scenario(1,0)
    baseline=solve_pavement_scenario(scenario)
    schedule=baseline.generated.schedule_input
    resources, candidate=solver.validate_idle_baseline(schedule,baseline.result)
    second=sorted(candidate.starts,key=candidate.starts.get)[-1]
    candidate.starts[second]=9; candidate.ends[second]=10; candidate.makespan=10
    baseline.result=solver.result_from_candidate(schedule,resources,candidate,"FEASIBLE",baseline.result.stats)
    return {"scenario":scenario.model_dump(mode="json"),"baseline":baseline.model_dump(mode="json")}


def test_idle_api_rejects_stale_and_corrupt_baselines_before_streaming(tmp_path):
    from copy import deepcopy
    app=_app(tmp_path); original={**idle_api_payload(), "time_budget_seconds":30}
    for kind in ["scope","scenario","fingerprint","task","cap","version","old_policy","budget"]:
        payload=deepcopy(original); path="/api/solve-scenario/idle/stream"
        if kind=="scope": path+="?workpoint_id=road"
        elif kind=="scenario": next(p for p in payload["scenario"]["resource_pools"] if p["enabled"] and p["quantity"])["transfer_days"]=2
        elif kind=="fingerprint": payload["baseline"]["result"]["pavement_summary"]["input_fingerprint"]="bad"
        elif kind=="task": payload["baseline"]["result"]["tasks"].pop()
        elif kind=="cap": payload["baseline"]["result"]["objective_days"]=11
        elif kind=="version": payload["baseline"]["generated"]["schedule_input"]["project_data_version_id"]="old"
        elif kind=="old_policy": payload["baseline"]["generated"]["schedule_input"]["pavement_handover_scope"]["pending_policy"]="strict_last"
        else: payload["scenario"]["time_limit_seconds"]="Infinity"
        status,response=json_request(app,"POST",path,payload)
        assert status==422,(kind,response)
    mirror=Path(__file__).resolve().parents[2]/"tools/demo-api-mirror/api.mts"
    assert '/solve-scenario/idle/stream' in mirror.read_text(encoding="utf-8")


def test_idle_api_rejects_invalid_runtime_budget_before_streaming(tmp_path):
    app = _app(tmp_path)
    original = idle_api_payload()
    for value in [0, -1, "Infinity", "NaN", "invalid"]:
        status, response = json_request(app, "POST", "/api/solve-scenario/idle/stream",
                                        {**original, "time_budget_seconds": value})
        assert status == 422, response

import math
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

sys.path[:0] = [str(Path(__file__).resolve().parents[1]), str(Path(__file__).resolve().parent)]
from asgi_client import json_request
from test_project_master_api import _app
from test_pavement_master import pavement_snapshot
from app.contracts.project_master import ConfirmProjectMasterVersionRequest, CreatePavementLayerDraftRequest, PavementLayerEdit
from app.contracts.pavement import PavementLayerCondition
from app.project_master.repository import ProjectMasterRepository
from app.project_master.workbook import export_snapshot, parse_workbook
from app.scenario_data import pavement_scenario


def setup_project(tmp_path):
    app = _app(tmp_path)
    service = app.state.project_master_service
    snapshot = pavement_snapshot()
    for s in snapshot.workpoints[0].structures:
        s.components = []
        s.remark = "保留客户净长及原始工期备注"
    batch = service.import_workbook(project_id="road", file_name="customer.xlsx", content=export_snapshot(snapshot),
                                    created_by="tester", expected_current_version_id=None)
    version = service.confirm_version(batch.created_version_id, ConfirmProjectMasterVersionRequest(
        confirmed_by="tester", acknowledge_warning_codes=list({i.issue_code for i in batch.issues})))
    return app, service, version.version_id


def payload():
    return {"section_ids": [f"{s}-{side}" for s in ["A", "B"] for side in ["left", "right"]],
            "layers": [{"name": name, "process_type": process, "thickness_m": thickness} for name, process, thickness in [
                ("碎石垫层", "granular_base", 0.16), ("水稳底基层", "cement_stabilized_base", 0.2), ("沥青下面层", "asphalt_course", 0.08)]],
            "created_by": "tester"}


def preview(app, base, data=None):
    return json_request(app, "POST", f"/api/project-master/versions/{base}/pavement-layer-drafts", data or payload())


def confirm(app, base, batch):
    return json_request(app, "POST", f"/api/project-master/versions/{batch['created_version_id']}/confirm", {
        "confirmed_by": "tester", "expected_current_version_id": base,
        "acknowledge_warning_codes": list({i["issue_code"] for i in batch["issues"]}),
    })


def test_template_confirm_reload_generate_preserves_source_and_net_length(tmp_path):
    app, service, base = setup_project(tmp_path)
    original = service.repository.load_snapshot(base)
    status, batch = preview(app, base)
    assert status == 200, batch
    assert batch["counts"]["components"] == 12
    assert service.repository.get_current_version("road").version_id == base
    assert service.repository.load_snapshot(base) == original
    assert preview(app, base)[1]["created_version_id"] == batch["created_version_id"]
    assert service.repository.list_versions("road")[1] == 2
    assert confirm(app, base, batch)[0] == 200
    version_id = batch["created_version_id"]
    restored = ProjectMasterRepository(tmp_path / "project-master.db").load_snapshot(version_id)
    for section, old in zip(restored.workpoints[0].structures, original.workpoints[0].structures):
        assert section.model_copy(update={"components": []}) == old
        assert [c.sort_order for c in section.components] == [1, 2, 3]
        assert [c.component_name for c in section.components] == [l["name"] for l in payload()["layers"]]
        length = next(p.value for p in old.parameters if p.parameter_code == "construction_length_m")
        assert all(c.quantity == length and c.unit == "m" for c in section.components)
        assert [next(p.value for p in c.parameters if p.parameter_code == "thickness_m") for c in section.components] == [0.16, 0.2, 0.08]
        assert all(c.source.sheet_name == "单段结构层模板" for c in section.components)
    assert restored.route_placements == original.route_placements
    roundtrip, issues, _ = parse_workbook(export_snapshot(restored))
    assert not issues
    assert [c.quantity for s in roundtrip.workpoints[0].structures for c in s.components] == [760] * 6 + [410] * 6
    scenario = pavement_scenario("road")
    scenario.project_data_version_id = version_id
    status, incomplete = json_request(app, "POST", "/api/generate-schedule-input", scenario.model_dump(mode="json"))
    assert status == 200 and len(incomplete["schedule_input"]["tasks"]) == 12
    assert any(d["level"] == "error" for d in incomplete["validation"])
    for section in restored.workpoints[0].structures:
        for c in section.components:
            scenario.pavement_settings.layer_conditions.append(PavementLayerCondition(
                component_id=c.component_id, wait_days=7 if c.component_type == "cement_stabilized_base" else 0, basis_note="测试明确给定"))
    for pool in scenario.resource_pools:
        pool.quantity = 1
        pool.transfer_days = 1
    status, generated = json_request(app, "POST", "/api/generate-schedule-input", scenario.model_dump(mode="json"))
    assert status == 200, generated
    assert not [d for d in generated["validation"] if d["level"] == "error"], generated["validation"]
    rates = {"granular_base": 800, "cement_stabilized_base": 700, "asphalt_course": 1000}
    for task in generated["schedule_input"]["tasks"]:
        length = 760 if "A-" in task["id"] else 410
        assert task["duration_days"] == math.ceil(length / rates[task["component_type"]])
    assert preview(app, base)[0] == 409
    status, existing = preview(app, version_id)
    assert status == 409 and existing["detail"]["code"] == "PAVEMENT_LAYERS_EXIST"


def test_rejects_invalid_inputs_without_creating_draft(tmp_path):
    app, service, base = setup_project(tmp_path)
    for change in [{"section_ids": []}, {"section_ids": ["A-left", "A-left"]}, {"section_ids": ["unknown"]},
                   {"created_by": " "}, {"layers": []}, {"layers": [{**payload()["layers"][0], "thickness_m": 0}]},
                   {"layers": [{**payload()["layers"][0], "process_type": "pile"}]}]:
        status, _ = preview(app, base, {**payload(), **change})
        assert status == 422
    with pytest.raises(ValidationError):
        CreatePavementLayerDraftRequest.model_validate({**payload(), "layers": [{**payload()["layers"][0], "thickness_m": float("inf")}]})
    assert service.repository.list_versions("road")[1] == 1


def test_selection_cancel_and_concurrent_confirmation(tmp_path):
    app, service, base = setup_project(tmp_path)
    status, batch = preview(app, base, {**payload(), "section_ids": ["A-left"]})
    assert status == 200
    draft = service.repository.load_snapshot(batch["created_version_id"])
    assert [len(s.components) for s in draft.workpoints[0].structures] == [3, 0, 0, 0]
    assert json_request(app, "POST", f"/api/project-master/imports/{batch['batch_id']}", {"cancelled_by": "tester"})[0] == 200
    assert service.repository.get_current_version("road").version_id == base
    _, batch = preview(app, base)
    _, concurrent = preview(app, base, {**payload(), "section_ids": ["A-left"]})
    assert confirm(app, base, concurrent)[0] == 200
    assert confirm(app, base, batch)[0] == 409
    latest = concurrent["created_version_id"]
    assert preview(app, latest, {**payload(), "section_ids": ["B-left", "A-left"]})[0] == 409
    snapshot = service.repository.load_snapshot(latest)
    assert [len(s.components) for s in snapshot.workpoints[0].structures] == [3, 0, 0, 0]


def initialize(app, version):
    return json_request(app, "POST", f"/api/project-master/versions/{version}/pavement-layers/initialize", {"created_by": "tester"})


def editable_layers(section):
    return [{"component_id": c.component_id, "name": c.component_name, "process_type": c.component_type,
             "thickness_m": next((p.value for p in c.parameters if p.parameter_code == "thickness_m"), None), "enabled": c.enabled}
            for c in section.components]


def save_layers(app, version, layers, section="A-left"):
    return json_request(app, "PUT", f"/api/project-master/versions/{version}/pavement-sections/{section}/layers", {"created_by": "tester", "layers": layers})


def test_default_layers_persist_once_without_inventing_thickness(tmp_path):
    app, service, base = setup_project(tmp_path)
    original = service.repository.load_snapshot(base)
    status, result = initialize(app, base)
    assert status == 200 and result["status"] == "confirmed", result
    assert result["counts"]["components"] == 20
    version = result["version_id"]
    saved = ProjectMasterRepository(tmp_path / "project-master.db").load_snapshot(version)
    for section, before in zip(saved.workpoints[0].structures, original.workpoints[0].structures):
        assert section.model_copy(update={"components": []}) == before
        assert [c.component_name for c in section.components] == ["碎石垫层", "水稳底基层", "水稳下基层", "水稳上基层", "沥青面层"]
        assert all(not any(p.parameter_code == "thickness_m" for p in c.parameters) for c in section.components)
        assert all(c.quantity == next(p.value for p in section.parameters if p.parameter_code == "construction_length_m") for c in section.components)
    assert initialize(app, version)[1]["version_id"] == version
    assert service.repository.list_versions("road")[1] == 2
    scenario = pavement_scenario("road")
    scenario.project_data_version_id = version
    _, generated = json_request(app, "POST", "/api/generate-schedule-input", scenario.model_dump(mode="json"))
    assert not any("thickness_m" in d["message"] for d in generated["validation"])
    assert len(generated["schedule_input"]["tasks"]) == 20
    assert service.repository.load_snapshot(base) == original


def test_section_edit_preserves_other_sections_and_supports_reverting_values(tmp_path):
    app, service, base = setup_project(tmp_path)
    _, initialized = initialize(app, base)
    version = initialized["version_id"]
    original = service.repository.load_snapshot(version)
    layers = editable_layers(original.workpoints[0].structures[0])
    assert save_layers(app, version, layers)[1]["version_id"] == version
    layers[1]["thickness_m"] = 0.22
    status, edited = save_layers(app, version, layers)
    assert status == 200, edited
    changed = service.repository.load_snapshot(edited["version_id"])
    assert changed.workpoints[0].structures[1:] == original.workpoints[0].structures[1:]
    assert editable_layers(changed.workpoints[0].structures[0]) == layers
    assert save_layers(app, version, layers)[0] == 409
    status, reverted = save_layers(app, edited["version_id"], editable_layers(original.workpoints[0].structures[0]))
    assert status == 200 and reverted["version_id"] != version, reverted
    assert service.repository.load_snapshot(reverted["version_id"]) == original
    assert service.repository.list_versions("road")[1] == 4


def test_layer_add_remove_reorder_disable_and_reference_protection(tmp_path):
    app, service, base = setup_project(tmp_path)
    _, initialized = initialize(app, base)
    version = initialized["version_id"]
    original = service.repository.load_snapshot(version)
    layers = editable_layers(original.workpoints[0].structures[0])
    removed = layers.pop(2)
    layers[2]["enabled"] = False
    layers.append({"component_id": None, "name": "沥青上面层", "process_type": "asphalt_course", "thickness_m": 0.04, "enabled": True})
    layers[0], layers[1] = layers[1], layers[0]
    service.reference_conflict_checker = lambda _, deleted: [removed["component_id"]] if removed["component_id"] in deleted else []
    assert save_layers(app, version, layers)[0] == 409
    assert service.repository.get_current_version("road").version_id == version
    service.reference_conflict_checker = None
    status, edited = save_layers(app, version, layers)
    assert status == 200, edited
    saved = service.repository.load_snapshot(edited["version_id"]).workpoints[0].structures[0]
    assert [c.component_id for c in saved.components[:4]] == [l["component_id"] for l in layers[:4]]
    assert saved.components[-1].component_id not in {c.component_id for c in original.workpoints[0].structures[0].components}
    assert [c.sort_order for c in saved.components] == [1, 2, 3, 4, 5]
    assert saved.components[2].enabled is False
    assert initialize(app, edited["version_id"])[1]["version_id"] == edited["version_id"]


def test_section_edit_rejects_foreign_layers_empty_list_and_bad_thickness(tmp_path):
    app, service, base = setup_project(tmp_path)
    _, initialized = initialize(app, base)
    version = initialized["version_id"]
    sections = service.repository.load_snapshot(version).workpoints[0].structures
    layers = editable_layers(sections[0])
    for invalid in [[], [layers[0], layers[0]], [{**layers[0], "component_id": sections[1].components[0].component_id}],
                    [{**layers[0], "thickness_m": -1}], [{**layers[0], "name": " "}]]:
        assert save_layers(app, version, invalid)[0] == 422
    assert save_layers(app, version, layers, "unknown")[0] == 404
    assert service.repository.get_current_version("road").version_id == version


def test_density_persists_roundtrips_and_preserves_length_scheduling_and_history(tmp_path):
    app, service, base = setup_project(tmp_path)
    _, initialized = initialize(app, base)
    version = initialized["version_id"]
    original = service.repository.load_snapshot(version)
    layers = editable_layers(original.workpoints[0].structures[0])
    layers[1].update(thickness_m=0.2, density_t_m3=2.38)
    layers[-1]["enabled"] = False
    status, edited = save_layers(app, version, layers)
    assert status == 200, edited
    saved = ProjectMasterRepository(tmp_path / "project-master.db").load_snapshot(edited["version_id"])
    assert service.repository.load_snapshot(version) == original
    assert saved.workpoints[0].structures[1:] == original.workpoints[0].structures[1:]
    section = saved.workpoints[0].structures[0]
    density = next(p for p in section.components[1].parameters if p.parameter_code == "density_t_m3")
    assert density.value == 2.38 and density.unit == "t/m3"
    assert all(c.quantity == 760 and c.unit == "m" for c in section.components)
    assert not section.components[-1].enabled
    assert all(not any(p.parameter_code == "density_t_m3" for p in c.parameters) for c in [section.components[0], section.components[-1]])
    exported, issues, _ = parse_workbook(export_snapshot(saved))
    assert not issues
    assert next(p.value for p in exported.workpoints[0].structures[0].components[1].parameters if p.parameter_code == "density_t_m3") == 2.38
    # Older callers omit density: they must not silently clear stored values.
    legacy = editable_layers(section)
    assert save_layers(app, edited["version_id"], legacy)[1]["version_id"] == edited["version_id"]
    legacy[1]["density_t_m3"] = None
    status, cleared = save_layers(app, edited["version_id"], legacy)
    assert status == 200, cleared
    restored = service.repository.load_snapshot(cleared["version_id"])
    assert not any(p.parameter_code == "density_t_m3" for p in restored.workpoints[0].structures[0].components[1].parameters)
    assert service.repository.load_snapshot(edited["version_id"]) == saved


def test_density_rejects_nonpositive_and_nonfinite_values_without_saving(tmp_path):
    app, service, base = setup_project(tmp_path)
    _, initialized = initialize(app, base)
    version = initialized["version_id"]
    layers = editable_layers(service.repository.load_snapshot(version).workpoints[0].structures[0])
    for invalid in [0, -1, "invalid"]:
        assert save_layers(app, version, [{**layers[0], "density_t_m3": invalid}])[0] == 422
    for invalid in [float("inf"), float("nan")]:
        with pytest.raises(ValidationError):
            PavementLayerEdit.model_validate({**layers[0], "density_t_m3": invalid})
    assert service.repository.get_current_version("road").version_id == version

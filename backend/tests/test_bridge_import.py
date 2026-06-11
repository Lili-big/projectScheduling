from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from app import process_nl  # noqa: E402
from app.bridge_import import BridgeImportConfigError, get_bridge_import_adapter, import_bridge_parameters  # noqa: E402
from app.main import apply_process_natural_language_endpoint, import_bridge_params_endpoint, import_local_bridge_params_endpoint  # noqa: E402
from app.models import ProcessNlRequest, ProductivityOption  # noqa: E402
from app.scenario import generate_schedule_input_from_scenario  # noqa: E402
from app.scenario_data import default_scenario  # noqa: E402


def sample_workbook_path() -> Path:
    matches = [path for path in PROJECT_ROOT.glob("*.xlsx") if not path.name.startswith("~$")]
    if not matches:
        pytest.fail("sample workbook is missing")
    return matches[0]


def test_bridge_excel_import_understands_sample_workbook() -> None:
    path = sample_workbook_path()
    response = import_bridge_parameters(
        file_name=path.name,
        content=path.read_bytes(),
        scenario=default_scenario(),
        target_bridge="渠溪河特大桥",
    )

    canonical = response.canonical_bridge
    assert canonical["bridge"]["name"] == "渠溪河特大桥"
    assert canonical["bridge"]["spanExpression"] == "9*40+(86+160+86)+12*40"

    carriageways = {item["side"]: item for item in canonical["carriageways"]}
    assert set(carriageways) == {"left", "right"}
    assert [support["supportNo"] for support in carriageways["left"]["supports"]][0] == "0#台"
    assert [support["supportNo"] for support in carriageways["right"]["supports"]][-1] == "24#台"
    assert len(carriageways["left"]["supports"]) == 25
    assert len(carriageways["right"]["supports"]) == 25
    assert [group["expression"] for group in carriageways["right"]["spanGroups"]] == ["9*40", "86+160+86", "12*40"]

    right_10 = next(support for support in carriageways["right"]["supports"] if support["supportIndex"] == 10)
    assert right_10["components"]["cap"]["dimensionsM"] == [13.6, 12.6, 5.0]
    assert right_10["components"]["pileFoundation"]["lengthM"] == 40.0
    assert right_10["components"]["pierColumn"]["heightM"] == 97.0
    right_0 = next(support for support in carriageways["right"]["supports"] if support["supportNo"] == "0#台")
    assert right_0["foundationType"] == "扩大基础"

    assert any(warning["id"] == "formula_error_normalized" for warning in response.warnings)
    assert any(check["id"] == "support_count_right" and check["status"] == "passed" for check in response.quality_checks)


def test_bridge_excel_import_maps_to_schedulable_scenario() -> None:
    path = sample_workbook_path()
    scenario = default_scenario()
    response = import_bridge_parameters(file_name=path.name, content=path.read_bytes(), scenario=scenario, target_bridge=None)

    imported = response.scenario
    assert imported.scenario_name == scenario.scenario_name
    assert imported.process_library[0].id == scenario.process_library[0].id
    assert imported.resource_pools[0].id == scenario.resource_pools[0].id
    assert imported.milestones[0].id == scenario.milestones[0].id

    bridge = imported.project.bridges[0]
    assert bridge.workpoint_type == "bridge"
    assert [section.side for section in bridge.work_sections] == ["left", "right"]
    assert bridge.work_sections[1].structures[10].support_no == "10#墩"
    left_1_components = {component.component_type: component for component in bridge.work_sections[0].structures[1].components}
    assert "ground_tie_beam" in left_1_components
    assert "middle_tie_beam" in left_1_components
    assert left_1_components["ground_tie_beam"].name == "1#墩-地系梁"
    assert left_1_components["middle_tie_beam"].name == "1#墩-中系梁"
    assert [len(section.upper_structures) for section in bridge.work_sections] == [24, 24]
    left_upper = bridge.work_sections[0].upper_structures
    assert left_upper[0].name == "0#台~1#墩-简支T梁"
    assert left_upper[0].span_length_m == 40.0
    assert left_upper[0].beam_count_per_span == 5
    assert [item.span_group_expression for item in left_upper[9:12]] == ["86+160+86", "86+160+86", "86+160+86"]

    generated = generate_schedule_input_from_scenario(imported)
    assert generated.schedule_input.tasks
    assert not any(message.level == "error" for message in generated.validation)
    assert any(task.bridge_id == "B1" and task.work_section_id == "WS-RIGHT" for task in generated.schedule_input.tasks)
    upper_ids = {upper.id for section in bridge.work_sections for upper in section.upper_structures}
    assert not any(task.component_id in upper_ids for task in generated.schedule_input.tasks)


def test_import_bridge_params_endpoint_accepts_multipart_upload() -> None:
    path = sample_workbook_path()
    scenario = default_scenario()
    request = FakeMultipartRequest(
        fields={"scenario": scenario.model_dump_json(), "target_bridge": "渠溪河特大桥"},
        file_name=path.name,
        file_content=path.read_bytes(),
    )

    response = asyncio.run(import_bridge_params_endpoint(request))

    assert response.summary["bridgeName"] == "渠溪河特大桥"
    assert response.scenario.project.bridges[0].work_sections[0].side == "left"
    assert response.scenario.process_library[0].id == scenario.process_library[0].id
    assert response.quality_checks


def test_import_local_bridge_params_endpoint_uses_project_workbook() -> None:
    scenario = default_scenario()

    response = import_local_bridge_params_endpoint(scenario)

    assert response.summary["bridgeName"] == "渠溪河特大桥"
    assert response.summary["lowerComponentCount"] == 211
    assert response.summary["upperComponentCount"] == 48
    assert response.scenario.project.bridges[0].work_sections[0].structures[1].support_no == "1#墩"
    assert response.scenario.process_library[0].id == scenario.process_library[0].id
    max_by_type = {pool.type: pool.max_quantity for pool in response.scenario.resource_pools}
    assert max_by_type["rotary_drill"] == 166
    assert max_by_type["spread_foundation_team"] == 2
    assert max_by_type["cap_team"] == 25
    assert max_by_type["pier_body_team"] == 46
    assert max_by_type["cap_beam_team"] == 42


def test_imported_spread_foundation_can_precede_abutment_body() -> None:
    imported = import_local_bridge_params_endpoint(default_scenario()).scenario
    generated = generate_schedule_input_from_scenario(imported)
    spread_tasks = [task for task in generated.schedule_input.tasks if task.component_type == "spread_foundation"]
    links = [
        link
        for link in generated.schedule_input.precedence_links
        if link.source_rule_id == "abutment_body_after_cap"
        and link.predecessor_id in {task.id for task in spread_tasks}
    ]

    assert len(spread_tasks) == 2
    assert links
    assert not any("桥台台身" in message.message and "未找到前置工作项" in message.message for message in generated.validation)


def test_pile_productivity_group_can_use_count_quantity_source() -> None:
    imported = import_local_bridge_params_endpoint(default_scenario()).scenario
    rotary_process = next(process for process in imported.process_library if process.method_id == "rotary_drill")
    rotary_process.productivity_options = [
        ProductivityOption(
            id="rotary-per-pile",
            name="按根计",
            duration_method="days_per_unit",
            quantity_source="count",
            productivity_value=2,
            productivity_unit="天/根",
            is_default=True,
        )
    ]
    rotary_process.duration_method = "days_per_unit"
    rotary_process.quantity_source = "count"
    rotary_process.productivity_value = 2
    rotary_process.productivity_unit = "天/根"

    generated = generate_schedule_input_from_scenario(imported)

    pile_task = next(task for task in generated.schedule_input.tasks if task.component_type == "pile")
    assert pile_task.quantity == 1
    assert pile_task.quantity_label == "1根"
    assert pile_task.duration_days == 2


def test_process_natural_language_updates_pile_methods(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PROCESS_NL_LLM_PROVIDER", "local")
    imported = import_local_bridge_params_endpoint(default_scenario()).scenario
    pile_count = sum(
        1
        for section in imported.project.bridges[0].work_sections
        for structure in section.structures
        for component in structure.components
        if component.component_type == "pile"
    )

    response = apply_process_natural_language_endpoint(
        ProcessNlRequest(
            scenario=imported,
            prompt="桩基默认采用旋挖钻施工，其中1#墩-1桩基、1#墩-2桩基采用人工挖孔桩。",
        )
    )

    left_1 = response.scenario.project.bridges[0].work_sections[0].structures[1]
    piles = [component for component in left_1.components if component.component_type == "pile"]
    assert [pile.method_id for pile in piles] == ["manual_pile", "manual_pile"]
    other_pile = response.scenario.project.bridges[0].work_sections[0].structures[2].components[0]
    assert other_pile.method_id == "rotary_drill"
    assert any(change.matched_count == pile_count for change in response.changes)
    assert any(change.matched_count == 4 for change in response.changes)


def test_process_natural_language_updates_side_pier_pile_scope(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PROCESS_NL_LLM_PROVIDER", "local")
    imported = import_local_bridge_params_endpoint(default_scenario()).scenario
    left_section = imported.project.bridges[0].work_sections[0]
    target_supports = {"3#墩", "4#墩"}
    expected_count = sum(
        1
        for structure in left_section.structures
        if structure.support_no in target_supports
        for component in structure.components
        if component.component_type == "pile"
    )

    response = apply_process_natural_language_endpoint(
        ProcessNlRequest(
            scenario=imported,
            prompt="左幅的3#墩和4#墩的桩基的工艺设置成“人工挖孔”",
        )
    )

    left_targets = [
        component
        for structure in response.scenario.project.bridges[0].work_sections[0].structures
        if structure.support_no in target_supports
        for component in structure.components
        if component.component_type == "pile"
    ]
    right_targets = [
        component
        for structure in response.scenario.project.bridges[0].work_sections[1].structures
        if structure.support_no in target_supports
        for component in structure.components
        if component.component_type == "pile"
    ]
    assert expected_count > 0
    assert all(component.method_id == "manual_pile" for component in left_targets)
    assert all(component.method_id == "rotary_drill" for component in right_targets)
    assert any(change.matched_count == expected_count for change in response.changes)
    assert not response.warnings


def test_process_natural_language_adds_climbing_form_for_continuous_girder_main_piers(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PROCESS_NL_LLM_PROVIDER", "local")
    imported = import_local_bridge_params_endpoint(default_scenario()).scenario

    response = apply_process_natural_language_endpoint(
        ProcessNlRequest(
            scenario=imported,
            prompt="渠溪河大桥连续梁主墩使用爬模施工。",
        )
    )

    climbing_components = [
        component
        for section in response.scenario.project.bridges[0].work_sections
        for structure in section.structures
        if structure.support_no in {"10#墩", "11#墩"}
        for component in structure.components
        if component.component_type == "pier_body"
    ]
    assert len(climbing_components) == 4
    assert all(component.method_id == "climbing_form" for component in climbing_components)
    climbing_process = next(process for process in response.scenario.process_library if process.method_id == "climbing_form")
    assert climbing_process.productivity_value == 7
    assert climbing_process.productivity_unit == "天/节"
    assert climbing_process.resource_type == "pier_body_team"
    assert any(pool.type == "pier_body_team" for pool in response.scenario.resource_pools)


def test_process_natural_language_updates_pier_bodies_by_height_condition(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PROCESS_NL_LLM_PROVIDER", "local")
    imported = import_local_bridge_params_endpoint(default_scenario()).scenario
    pier_bodies = [
        component
        for section in imported.project.bridges[0].work_sections
        for structure in section.structures
        for component in structure.components
        if component.component_type == "pier_body"
    ]
    expected_targets = [
        component
        for component in pier_bodies
        if (process_nl._component_numeric_value(component, "pier_height_m") or 0) > 6
    ]

    response = apply_process_natural_language_endpoint(
        ProcessNlRequest(
            scenario=imported,
            prompt="把墩高大于6m的墩柱的工艺统一设置成爬模",
        )
    )

    updated_by_id = {
        component.id: component
        for section in response.scenario.project.bridges[0].work_sections
        for structure in section.structures
        for component in structure.components
        if component.component_type == "pier_body"
    }
    assert expected_targets
    assert all(updated_by_id[component.id].method_id == "climbing_form" for component in expected_targets)
    assert any(change.matched_count == len(expected_targets) for change in response.changes)
    assert not response.warnings


def test_process_natural_language_accepts_openai_compatible_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    imported = import_local_bridge_params_endpoint(default_scenario()).scenario
    monkeypatch.setenv("PROCESS_NL_LLM_PROVIDER", "openai_compatible")
    monkeypatch.setenv("PROCESS_NL_LLM_ENDPOINT", "https://example.test/v1/chat/completions")
    monkeypatch.setenv("PROCESS_NL_LLM_MODEL", "test-model")
    monkeypatch.setenv("PROCESS_NL_LLM_API_KEY", "test-key")

    captured: dict[str, object] = {}

    def fake_urlopen(request, timeout: int = 0):  # type: ignore[no-untyped-def]
        captured["url"] = request.full_url
        captured["headers"] = dict(request.header_items())
        captured["payload"] = request.data.decode("utf-8")
        return FakeJsonResponse(
            {
                "choices": [
                    {
                        "message": {
                            "content": (
                                '{"intents":[{"component_type":"pile","process_method_id":"manual_pile",'
                                '"process_name":"人工挖孔","sides":["left"],"support_nos":["3#墩","4#墩"],'
                                '"action":"指定墩桩基工艺"}],"warnings":[]}'
                            )
                        }
                    }
                ]
            }
        )

    monkeypatch.setattr(process_nl.urllib.request, "urlopen", fake_urlopen)

    response = apply_process_natural_language_endpoint(
        ProcessNlRequest(
            scenario=imported,
            prompt="左幅的3#墩和4#墩的桩基的工艺设置成“人工挖孔”",
        )
    )

    payload = captured["payload"]
    assert "chat/completions" in captured["url"]
    assert "Bearer test-key" in captured["headers"].values()
    assert isinstance(payload, str) and '"messages"' in payload
    assert any(change.action == "指定墩桩基工艺" for change in response.changes)
    left_3_piles = [
        component
        for structure in response.scenario.project.bridges[0].work_sections[0].structures
        if structure.support_no == "3#墩"
        for component in structure.components
        if component.component_type == "pile"
    ]
    assert left_3_piles
    assert all(component.method_id == "manual_pile" for component in left_3_piles)
    assert not response.warnings


def test_external_ai_adapter_requires_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BRIDGE_IMPORT_LLM_PROVIDER", "http")
    monkeypatch.delenv("BRIDGE_IMPORT_LLM_ENDPOINT", raising=False)

    with pytest.raises(BridgeImportConfigError):
        get_bridge_import_adapter()


class FakeMultipartRequest:
    def __init__(self, *, fields: dict[str, str], file_name: str, file_content: bytes) -> None:
        boundary = "----codex-bridge-import-test"
        self.headers = {"content-type": f"multipart/form-data; boundary={boundary}"}
        self._body = _multipart_body(boundary, fields, file_name, file_content)

    async def body(self) -> bytes:
        return self._body


class FakeJsonResponse:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def __enter__(self) -> "FakeJsonResponse":
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:  # type: ignore[no-untyped-def]
        return None

    def read(self) -> bytes:
        import json

        return json.dumps(self._payload, ensure_ascii=False).encode("utf-8")


def _multipart_body(boundary: str, fields: dict[str, str], file_name: str, file_content: bytes) -> bytes:
    chunks: list[bytes] = []
    for name, value in fields.items():
        chunks.extend(
            [
                f"--{boundary}\r\n".encode("utf-8"),
                f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode("utf-8"),
                value.encode("utf-8"),
                b"\r\n",
            ]
        )
    chunks.extend(
        [
            f"--{boundary}\r\n".encode("utf-8"),
            f'Content-Disposition: form-data; name="file"; filename="{file_name}"\r\n'.encode("utf-8"),
            b"Content-Type: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet\r\n\r\n",
            file_content,
            b"\r\n",
            f"--{boundary}--\r\n".encode("utf-8"),
        ]
    )
    return b"".join(chunks)

from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError

from .bridge_import import default_local_bridge_workbook, import_bridge_parameters
from .contracts import ProjectModel, ProjectStructureParamsResponse, ScenarioInput
from .scenario_data import apply_resource_max_quantity_defaults, default_scenario, sync_bridge_completion_milestones
from .local_paths import LOCAL_DATA_ROOT, REPOSITORY_ROOT, state_path


PROJECT_ROOT = REPOSITORY_ROOT
LOCAL_DATA_DIR = LOCAL_DATA_ROOT
PROJECT_STRUCTURE_PARAMS_PATH = state_path("project-structure-params.json")


class ProjectStructureParamsError(RuntimeError):
    pass


def load_project_structure_params(
    *,
    path: Path = PROJECT_STRUCTURE_PARAMS_PATH,
) -> ProjectStructureParamsResponse:
    if path.exists():
        project = _read_project(path)
        return ProjectStructureParamsResponse(project=project, source="local_config", warnings=[])

    workbook = _first_project_workbook()
    if workbook is not None:
        response = import_bridge_parameters(
            file_name=workbook.name,
            content=workbook.read_bytes(),
            scenario=default_scenario(),
            target_bridge=None,
        )
        return ProjectStructureParamsResponse(
            project=response.scenario.project,
            source="local_workbook",
            warnings=response.warnings,
        )

    return ProjectStructureParamsResponse(
        project=default_scenario().project,
        source="default_demo",
        warnings=[{"id": "project_structure_default_demo", "message": "未找到本地结构参数，已使用默认示例项目。"}],
    )


def save_project_structure_params(
    project: ProjectModel,
    *,
    path: Path = PROJECT_STRUCTURE_PARAMS_PATH,
) -> ProjectStructureParamsResponse:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(project.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return ProjectStructureParamsResponse(project=project, source="local_config", warnings=[])


def apply_project_structure_params(scenario: ScenarioInput, project: ProjectModel) -> ScenarioInput:
    next_scenario = scenario.model_copy(deep=True)
    next_scenario.project = project
    sync_bridge_completion_milestones(next_scenario)
    apply_resource_max_quantity_defaults(next_scenario)
    return next_scenario


def _read_project(path: Path) -> ProjectModel:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ProjectStructureParamsError(f"结构参数 JSON 解析失败：{exc}") from exc
    if isinstance(payload, dict) and "project" in payload:
        payload = payload["project"]
    if not isinstance(payload, dict):
        raise ProjectStructureParamsError("结构参数 JSON 顶层必须是项目对象。")
    try:
        return ProjectModel.model_validate(payload)
    except ValidationError as exc:
        raise ProjectStructureParamsError(f"结构参数校验失败：{exc}") from exc


def _first_project_workbook() -> Path | None:
    return default_local_bridge_workbook(PROJECT_ROOT)

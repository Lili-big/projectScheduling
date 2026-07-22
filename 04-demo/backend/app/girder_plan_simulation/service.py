"""Application service for independent girder plan simulation."""

from __future__ import annotations

import threading
from copy import deepcopy

from ..contracts.girder_plan_simulation import (
    ConfirmSimulationRunRequest,
    CreateScenarioVersionRequest,
    CreateSimulationRunRequest,
    ExpectedFingerprintRequest,
    GirderPlanReadiness,
    GirderPlanScenarioVersion,
    GirderPlanSimulationRun,
    LineGraphSnapshot,
)
from ..project_master.repository import ProjectMasterRepositoryError
from ..project_master.service import ProjectMasterService, default_project_master_service
from .repository import (
    GirderPlanConflictError,
    GirderPlanRepository,
    GirderPlanRepositoryError,
    default_girder_plan_repository,
)
from .simulator import simulate
from .topology import build_line_graph
from .validation import prepare_scenario


class GirderPlanSimulationServiceError(RuntimeError):
    status_code = 503
    code = "GIRDER_PLAN_SIMULATION_SERVICE_ERROR"


class GirderPlanSimulationInputError(GirderPlanSimulationServiceError):
    status_code = 422
    code = "GIRDER_PLAN_SIMULATION_INPUT_INVALID"


class GirderPlanSimulationService:
    def __init__(self, project_master_service: ProjectMasterService, repository: GirderPlanRepository) -> None:
        self.project_master_service = project_master_service
        self.repository = repository

    def get_line_graph(self, project_master_version_id: str, *, connection_overrides=()) -> LineGraphSnapshot:
        summary = self.project_master_service.repository.get_version_summary(project_master_version_id)
        if summary.status != "confirmed":
            exc = GirderPlanConflictError("架梁计划推演只能引用已确认的项目主数据版本。")
            exc.code = "PROJECT_MASTER_VERSION_NOT_CONFIRMED"
            raise exc
        snapshot = self.project_master_service.repository.load_snapshot(project_master_version_id)
        return build_line_graph(
            project_id=summary.project_id,
            project_master_version_id=project_master_version_id,
            snapshot=snapshot,
            connection_overrides=connection_overrides,
        )

    def create_scenario(self, request: CreateScenarioVersionRequest) -> GirderPlanScenarioVersion:
        summary = self.project_master_service.repository.get_version_summary(request.project_master_version_id)
        if summary.status != "confirmed":
            exc = GirderPlanConflictError("架梁计划推演只能引用已确认的项目主数据版本。")
            exc.code = "PROJECT_MASTER_VERSION_NOT_CONFIRMED"
            raise exc
        if summary.project_id != request.project_id:
            raise GirderPlanSimulationInputError("项目标识与项目主数据版本不一致。")
        base_graph = self.get_line_graph(request.project_master_version_id)
        graph = self.get_line_graph(
            request.project_master_version_id,
            connection_overrides=request.connection_overrides,
        )
        if request.line_graph_id not in {base_graph.line_graph_id, graph.line_graph_id}:
            exc = GirderPlanConflictError("线路图已变化，请重新载入后保存方案。")
            exc.code = "LINE_GRAPH_CHANGED"
            raise exc
        normalized_request = request.model_copy(update={"line_graph_id": graph.line_graph_id})
        return self.repository.create_scenario_version(normalized_request)

    def list_scenarios(self, project_id: str | None = None) -> list[GirderPlanScenarioVersion]:
        return [self._refresh_external_staleness(item) for item in self.repository.list_scenario_versions(project_id)]

    def get_scenario(self, scenario_version_id: str) -> GirderPlanScenarioVersion:
        return self._refresh_external_staleness(self.repository.get_scenario_version(scenario_version_id))

    def validate_scenario(
        self,
        scenario_version_id: str,
        request: ExpectedFingerprintRequest,
    ) -> GirderPlanReadiness:
        scenario = self.get_scenario(scenario_version_id)
        self._assert_fingerprint(scenario, request.expected_input_fingerprint)
        graph = self.get_line_graph(
            scenario.project_master_version_id,
            connection_overrides=scenario.connection_overrides,
        )
        prepared = prepare_scenario(scenario, graph)
        self.repository.set_scenario_status(
            scenario_version_id,
            "blocked" if prepared.readiness.status == "blocking" else "ready",
        )
        return prepared.readiness

    def create_run(self, request: CreateSimulationRunRequest) -> GirderPlanSimulationRun:
        scenario = self.get_scenario(request.scenario_version_id)
        self._assert_fingerprint(scenario, request.expected_input_fingerprint)
        if scenario.status == "stale":
            exc = GirderPlanConflictError("方案输入已经失效，请基于当前输入创建新版本。")
            exc.code = "SCENARIO_STALE"
            raise exc
        if not request.force_recompute:
            reusable = self.repository.find_reusable_run(scenario.scenario_version_id, scenario.input_fingerprint)
            if reusable is not None:
                return reusable.model_copy(update={"reused_from_run_id": reusable.run_id}, deep=True)
        graph = self.get_line_graph(
            scenario.project_master_version_id,
            connection_overrides=scenario.connection_overrides,
        )
        prepared = prepare_scenario(scenario, graph)
        run = simulate(scenario, graph, prepared=prepared)
        return self.repository.save_run(run)

    def get_run(self, run_id: str) -> GirderPlanSimulationRun:
        run = self.repository.get_run(run_id)
        scenario = self.get_scenario(run.scenario_version_id)
        if scenario.status == "stale" and run.status != "stale":
            return run.model_copy(update={"status": "stale"}, deep=True)
        return run

    def confirm_run(self, run_id: str, request: ConfirmSimulationRunRequest) -> GirderPlanSimulationRun:
        run = self.repository.get_run(run_id)
        scenario = self.get_scenario(run.scenario_version_id)
        if scenario.status == "stale":
            exc = GirderPlanConflictError("方案输入已经失效，不能确认旧计算成果。")
            exc.code = "SCENARIO_STALE"
            raise exc
        self._assert_fingerprint(scenario, request.expected_input_fingerprint)
        return self.repository.confirm_run(run_id, request)

    @staticmethod
    def _assert_fingerprint(scenario: GirderPlanScenarioVersion, expected: str) -> None:
        if scenario.input_fingerprint != expected:
            exc = GirderPlanConflictError("方案输入指纹已变化，请重新载入。")
            exc.code = "SCENARIO_INPUT_FINGERPRINT_STALE"
            raise exc

    def _refresh_external_staleness(self, scenario: GirderPlanScenarioVersion) -> GirderPlanScenarioVersion:
        if scenario.status == "stale":
            return scenario
        try:
            summary = self.project_master_service.repository.get_version_summary(scenario.project_master_version_id)
            current = summary.status == "confirmed"
        except ProjectMasterRepositoryError:
            current = False
        if current:
            graph = self.get_line_graph(
                scenario.project_master_version_id,
                connection_overrides=scenario.connection_overrides,
            )
            if graph.line_graph_id == scenario.line_graph_id:
                return scenario
            return self.repository.set_scenario_status(
                scenario.scenario_version_id,
                "stale",
                stale_reason="项目线路投影或线路落位已变化，请基于当前双幅线路图创建新版本并重算。",
            )
        return self.repository.set_scenario_status(
            scenario.scenario_version_id,
            "stale",
            stale_reason="引用的项目主数据版本已被替代或不可用。",
        )


_default_lock = threading.Lock()
_default_service: GirderPlanSimulationService | None = None


def default_girder_plan_service() -> GirderPlanSimulationService:
    global _default_service
    with _default_lock:
        project_service = default_project_master_service()
        repository = default_girder_plan_repository()
        if (
            _default_service is None
            or _default_service.project_master_service is not project_service
            or _default_service.repository is not repository
        ):
            _default_service = GirderPlanSimulationService(project_service, repository)
        return _default_service


DOMAIN_ERRORS = (
    GirderPlanRepositoryError,
    GirderPlanSimulationServiceError,
    ProjectMasterRepositoryError,
)


__all__ = [
    "DOMAIN_ERRORS",
    "GirderPlanSimulationInputError",
    "GirderPlanSimulationService",
    "GirderPlanSimulationServiceError",
    "default_girder_plan_service",
]

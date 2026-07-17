from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path

from pydantic import ValidationError

from ..contracts import (
    AdjustmentProposal,
    ConfirmProjectDataVersionRequest,
    ConfirmSpecialtyRequest,
    CreatePlanningScenarioVersionRequest,
    CreateProjectDataVersionRequest,
    ForecastSchedule,
    IntegratedCalculationSnapshot,
    PlanChangeRecord,
    PlanControlProjectSummary,
    PlanControlStore,
    PlanVersion,
    PlanningScenarioVersion,
    ProjectDataVersion,
    ProgressCorrectionRecord,
    ProgressSnapshot,
)
from ..girder_planning.fingerprints import stable_fingerprint, stable_id
from ..local_paths import REPOSITORY_ROOT, state_path


PROJECT_ROOT = REPOSITORY_ROOT
PLAN_CONTROL_STORE_PATH = state_path("plan-control-store.json")


class PlanControlRepositoryError(RuntimeError):
    status_code = 503


class PlanControlNotFoundError(PlanControlRepositoryError):
    status_code = 404


class PlanControlConflictError(PlanControlRepositoryError):
    status_code = 409


class PlanControlRepository:
    def __init__(self, path: Path = PLAN_CONTROL_STORE_PATH) -> None:
        self.path = path
        self._lock = threading.RLock()

    def load(self) -> PlanControlStore:
        with self._lock:
            return self._load_unlocked()

    def list_project_data_versions(self, project_id: str) -> list[ProjectDataVersion]:
        return sorted(
            (item for item in self.load().project_data_versions if item.project_id == project_id),
            key=lambda item: item.version_no,
            reverse=True,
        )

    def get_project_data_version(self, project_data_version_id: str) -> ProjectDataVersion:
        version = next(
            (item for item in self.load().project_data_versions if item.project_data_version_id == project_data_version_id),
            None,
        )
        if version is None:
            raise PlanControlNotFoundError(f"项目主数据版本 {project_data_version_id} 不存在。")
        return version

    def create_project_data_version(self, request: CreateProjectDataVersionRequest) -> ProjectDataVersion:
        with self._lock:
            store = self._load_unlocked()
            project_id = request.project.project_id
            versions = [item for item in store.project_data_versions if item.project_id == project_id]
            latest_no = max((item.version_no for item in versions), default=0)
            if request.expected_latest_version_no is not None and request.expected_latest_version_no != latest_no:
                raise PlanControlConflictError("项目主数据版本已变化，请刷新后重试。")
            payload = {
                "project": request.project,
                "workpoints": request.workpoints,
                "source_evidence": request.source_evidence,
                "field_conflicts": request.field_conflicts,
            }
            input_fingerprint = stable_fingerprint(payload, prefix="project-data")
            duplicate = next((item for item in versions if item.input_fingerprint == input_fingerprint), None)
            if duplicate is not None:
                return duplicate
            created_at = datetime.now(timezone.utc)
            version = ProjectDataVersion(
                project_data_version_id=stable_id(
                    "project-data",
                    {"project_id": project_id, "version_no": latest_no + 1, "fingerprint": input_fingerprint},
                ),
                project_id=project_id,
                version_no=latest_no + 1,
                status="draft",
                project=request.project.model_copy(deep=True),
                workpoints=[item.model_copy(deep=True) for item in request.workpoints],
                source_evidence=[item.model_copy(deep=True) for item in request.source_evidence],
                field_conflicts=[item.model_copy(deep=True) for item in request.field_conflicts],
                input_fingerprint=input_fingerprint,
                created_by=request.created_by.strip(),
                created_at=created_at,
            )
            store.project_data_versions.append(version)
            self._write_unlocked(store)
            return version

    def confirm_project_data_version(
        self,
        project_data_version_id: str,
        request: ConfirmProjectDataVersionRequest,
    ) -> ProjectDataVersion:
        with self._lock:
            store = self._load_unlocked()
            version = next(
                (item for item in store.project_data_versions if item.project_data_version_id == project_data_version_id),
                None,
            )
            if version is None:
                raise PlanControlNotFoundError(f"项目主数据版本 {project_data_version_id} 不存在。")
            if version.input_fingerprint != request.expected_input_fingerprint:
                raise PlanControlConflictError("项目主数据版本输入已变化，请重新确认。")
            if version.status == "superseded":
                raise PlanControlConflictError("已被替代的项目主数据版本不能确认。")
            blocking = [
                item
                for item in version.field_conflicts
                if item.severity == "blocking" and item.status == "unresolved"
            ]
            if blocking:
                raise PlanControlConflictError("项目主数据仍存在未解决的阻断冲突。")
            if not request.confirmed_by.strip() or not request.confirmation_reason.strip():
                raise PlanControlConflictError("确认人和确认原因不能为空。")
            confirmed_at = datetime.now(timezone.utc)
            confirmed = version.model_copy(
                update={
                    "status": "confirmed",
                    "confirmed_by": request.confirmed_by.strip(),
                    "confirmed_at": confirmed_at,
                    "confirmation_reason": request.confirmation_reason.strip(),
                }
            )
            next_versions: list[ProjectDataVersion] = []
            for item in store.project_data_versions:
                if item.project_data_version_id == confirmed.project_data_version_id:
                    next_versions.append(confirmed)
                elif item.project_id == confirmed.project_id and item.status == "confirmed":
                    next_versions.append(item.model_copy(update={"status": "superseded"}))
                else:
                    next_versions.append(item)
            store.project_data_versions = next_versions
            self._write_unlocked(store)
            return confirmed

    def list_planning_scenario_versions(self, project_id: str) -> list[PlanningScenarioVersion]:
        project_version_ids = {
            item.project_data_version_id
            for item in self.load().project_data_versions
            if item.project_id == project_id
        }
        return sorted(
            (
                item
                for item in self.load().planning_scenario_versions
                if item.project_data_version_id in project_version_ids or item.scenario.project.project_id == project_id
            ),
            key=lambda item: (item.scenario_id, item.version_no),
            reverse=True,
        )

    def get_planning_scenario_version(self, scenario_version_id: str) -> PlanningScenarioVersion:
        version = next(
            (item for item in self.load().planning_scenario_versions if item.scenario_version_id == scenario_version_id),
            None,
        )
        if version is None:
            raise PlanControlNotFoundError(f"方案版本 {scenario_version_id} 不存在。")
        return version

    def create_planning_scenario_version(
        self,
        request: CreatePlanningScenarioVersionRequest,
    ) -> PlanningScenarioVersion:
        with self._lock:
            store = self._load_unlocked()
            project_version = next(
                (
                    item
                    for item in store.project_data_versions
                    if item.project_data_version_id == request.project_data_version_id
                ),
                None,
            )
            if request.project_data_version_id.startswith("pmv-"):
                from ..project_master.repository import ProjectMasterRepositoryError
                from ..project_master.service import default_project_master_service

                try:
                    master_version = default_project_master_service().repository.get_version_summary(
                        request.project_data_version_id
                    )
                except ProjectMasterRepositoryError as exc:
                    raise PlanControlNotFoundError(str(exc)) from exc
                if master_version.status != "confirmed":
                    raise PlanControlConflictError("方案版本只能引用已确认的项目主数据版本。")
                if request.scenario.project.project_id != master_version.project_id:
                    raise PlanControlConflictError("方案项目与项目主数据版本不一致。")
                if request.scenario.project_data_version_id not in {None, request.project_data_version_id}:
                    raise PlanControlConflictError("方案内项目主数据版本引用不一致。")
            else:
                if project_version is None:
                    raise PlanControlNotFoundError(f"项目主数据版本 {request.project_data_version_id} 不存在。")
                if project_version.status != "confirmed":
                    raise PlanControlConflictError("方案版本只能引用已确认的项目主数据版本。")
                if request.scenario.project.project_id != project_version.project_id:
                    raise PlanControlConflictError("方案项目与项目主数据版本不一致。")
                if stable_fingerprint(request.scenario.project) != stable_fingerprint(project_version.project):
                    raise PlanControlConflictError("方案中的项目结构与确认项目版本不一致。")
            versions = [
                item
                for item in store.planning_scenario_versions
                if item.scenario_id == request.scenario.scenario_id
            ]
            latest_no = max((item.version_no for item in versions), default=0)
            if request.expected_latest_version_no is not None and request.expected_latest_version_no != latest_no:
                raise PlanControlConflictError("方案版本已变化，请刷新后重试。")
            payload = {
                "scenario": request.scenario,
                "project_data_version_id": request.project_data_version_id,
                "girder_planning": request.girder_planning,
            }
            input_fingerprint = stable_fingerprint(payload, prefix="scenario-version")
            duplicate = next((item for item in versions if item.input_fingerprint == input_fingerprint), None)
            if duplicate is not None:
                return duplicate
            created_at = datetime.now(timezone.utc)
            version = PlanningScenarioVersion(
                scenario_version_id=stable_id(
                    "scenario-version",
                    {
                        "scenario_id": request.scenario.scenario_id,
                        "version_no": latest_no + 1,
                        "fingerprint": input_fingerprint,
                    },
                ),
                scenario_id=request.scenario.scenario_id,
                project_data_version_id=request.project_data_version_id,
                version_no=latest_no + 1,
                status="draft",
                scenario=request.scenario.model_copy(
                    deep=True,
                    update={"project_data_version_id": request.project_data_version_id},
                ),
                girder_planning=request.girder_planning.model_copy(deep=True),
                input_fingerprint=input_fingerprint,
                created_by=request.created_by.strip(),
                created_at=created_at,
            )
            store.planning_scenario_versions = [
                item.model_copy(update={"status": "superseded"})
                if item.scenario_id == version.scenario_id and item.status != "superseded"
                else item
                for item in store.planning_scenario_versions
            ]
            store.planning_scenario_versions.append(version)
            self._write_unlocked(store)
            return version

    def invalidate_project_master_reference(self, project_data_version_id: str) -> None:
        """Mark every downstream artifact derived from a superseded master version stale."""

        with self._lock:
            store = self._load_unlocked()
            stale_scenario_ids = {
                item.scenario_version_id
                for item in store.planning_scenario_versions
                if item.project_data_version_id == project_data_version_id
            }
            store.planning_scenario_versions = [
                item.model_copy(update={"status": "stale"})
                if item.scenario_version_id in stale_scenario_ids and item.status != "superseded"
                else item
                for item in store.planning_scenario_versions
            ]
            store.integrated_calculation_snapshots = [
                item.model_copy(update={"status": "stale"})
                if (
                    item.project_data_version_id == project_data_version_id
                    or item.scenario_version_id in stale_scenario_ids
                )
                else item
                for item in store.integrated_calculation_snapshots
            ]
            store.plan_versions = [
                item.model_copy(update={"status": "stale"})
                if item.project_data_version_id == project_data_version_id and item.status == "active"
                else item
                for item in store.plan_versions
            ]
            stale_plan_ids = {item.plan_version_id for item in store.plan_versions if item.status == "stale"}
            store.forecasts = [
                item.model_copy(update={"status": "stale"})
                if item.plan_version_id in stale_plan_ids and item.status != "stale"
                else item
                for item in store.forecasts
            ]
            self._write_unlocked(store)

    def confirm_specialty(
        self,
        scenario_version_id: str,
        request: ConfirmSpecialtyRequest,
    ) -> PlanningScenarioVersion:
        with self._lock:
            store = self._load_unlocked()
            version = next(
                (item for item in store.planning_scenario_versions if item.scenario_version_id == scenario_version_id),
                None,
            )
            if version is None:
                raise PlanControlNotFoundError(f"方案版本 {scenario_version_id} 不存在。")
            if version.status in {"stale", "superseded"}:
                raise PlanControlConflictError("失效或已替代的方案不能确认。")
            if version.input_fingerprint != request.expected_input_fingerprint:
                raise PlanControlConflictError("方案输入已变化，请重新校验后确认。")
            if not request.confirmed_by.strip() or not request.confirmation_reason.strip():
                raise PlanControlConflictError("确认人和确认原因不能为空。")
            confirmed = version.model_copy(
                update={
                    "status": "specialty_confirmed",
                    "specialty_confirmed_by": request.confirmed_by.strip(),
                    "specialty_confirmed_at": datetime.now(timezone.utc),
                    "specialty_confirmation_reason": request.confirmation_reason.strip(),
                }
            )
            store.planning_scenario_versions = [
                confirmed if item.scenario_version_id == scenario_version_id else item
                for item in store.planning_scenario_versions
            ]
            self._write_unlocked(store)
            return confirmed

    def get_integrated_snapshot(self, integrated_snapshot_id: str) -> IntegratedCalculationSnapshot:
        snapshot = next(
            (
                item
                for item in self.load().integrated_calculation_snapshots
                if item.integrated_snapshot_id == integrated_snapshot_id
            ),
            None,
        )
        if snapshot is None:
            raise PlanControlNotFoundError(f"联合计算快照 {integrated_snapshot_id} 不存在。")
        return snapshot

    def find_integrated_snapshot_by_fingerprint(self, input_fingerprint: str) -> IntegratedCalculationSnapshot | None:
        return next(
            (
                item
                for item in self.load().integrated_calculation_snapshots
                if item.input_fingerprint == input_fingerprint and item.status != "stale"
            ),
            None,
        )

    def add_integrated_snapshot(self, snapshot: IntegratedCalculationSnapshot) -> IntegratedCalculationSnapshot:
        with self._lock:
            store = self._load_unlocked()
            existing = next(
                (
                    item
                    for item in store.integrated_calculation_snapshots
                    if item.input_fingerprint == snapshot.input_fingerprint and item.status != "stale"
                ),
                None,
            )
            if existing is not None:
                return existing
            store.integrated_calculation_snapshots.append(snapshot)
            self._write_unlocked(store)
            return snapshot

    def get_plan_version(self, plan_version_id: str) -> PlanVersion:
        store = self.load()
        plan = next((item for item in store.plan_versions if item.plan_version_id == plan_version_id), None)
        if plan is None:
            raise PlanControlNotFoundError(f"计划版本 {plan_version_id} 不存在。")
        return plan

    def get_progress_snapshot(self, progress_snapshot_id: str) -> ProgressSnapshot:
        store = self.load()
        snapshot = next(
            (item for item in store.progress_snapshots if item.progress_snapshot_id == progress_snapshot_id),
            None,
        )
        if snapshot is None:
            raise PlanControlNotFoundError(f"进度快照 {progress_snapshot_id} 不存在。")
        return snapshot

    def get_forecast(self, forecast_id: str) -> ForecastSchedule:
        store = self.load()
        forecast = next((item for item in store.forecasts if item.forecast_id == forecast_id), None)
        if forecast is None:
            raise PlanControlNotFoundError(f"滚动预测 {forecast_id} 不存在。")
        return forecast

    def get_proposal(self, proposal_id: str) -> AdjustmentProposal:
        store = self.load()
        proposal = next((item for item in store.adjustment_proposals if item.proposal_id == proposal_id), None)
        if proposal is None:
            raise PlanControlNotFoundError(f"调整方案 {proposal_id} 不存在。")
        return proposal

    def project_summary(self, project_id: str) -> PlanControlProjectSummary:
        store = self.load()
        versions = sorted(
            (item for item in store.plan_versions if item.project_id == project_id),
            key=lambda item: item.version_no,
            reverse=True,
        )
        active = next((item for item in versions if item.status == "active"), None)
        snapshots = [item for item in store.progress_snapshots if active and item.plan_version_id == active.plan_version_id and item.is_current]
        snapshots.sort(key=lambda item: (item.status_date, item.revision_no), reverse=True)
        forecasts = [item for item in store.forecasts if active and item.plan_version_id == active.plan_version_id]
        forecasts.sort(key=lambda item: item.created_at, reverse=True)
        return PlanControlProjectSummary(
            project_id=project_id,
            active_plan=active,
            plan_versions=versions,
            current_progress_snapshot=snapshots[0] if snapshots else None,
            latest_forecast=forecasts[0] if forecasts else None,
        )

    def add_plan_version(self, version: PlanVersion) -> PlanVersion:
        with self._lock:
            store = self._load_unlocked()
            if any(item.plan_version_id == version.plan_version_id for item in store.plan_versions):
                raise PlanControlConflictError("计划版本已存在。")
            if any(
                item.project_id == version.project_id
                and item.plan_type == version.plan_type
                and item.version_no == version.version_no
                for item in store.plan_versions
            ):
                raise PlanControlConflictError("计划版本号冲突，请刷新后重试。")
            if version.status == "active":
                store.plan_versions = [
                    item.model_copy(update={"status": "superseded"})
                    if item.project_id == version.project_id and item.plan_type == version.plan_type and item.status == "active"
                    else item
                    for item in store.plan_versions
                ]
            store.plan_versions.append(version)
            self._write_unlocked(store)
        return version

    def add_progress_snapshot(
        self,
        snapshot: ProgressSnapshot,
        correction: ProgressCorrectionRecord | None = None,
        *,
        expected_revision_no: int | None = None,
    ) -> tuple[ProgressSnapshot, list[str], list[str]]:
        with self._lock:
            store = self._load_unlocked()
            current = next(
                (
                    item
                    for item in store.progress_snapshots
                    if item.plan_version_id == snapshot.plan_version_id
                    and item.status_date == snapshot.status_date
                    and item.is_current
                ),
                None,
            )
            if current and expected_revision_no != current.revision_no:
                raise PlanControlConflictError("进度快照已被更新，请刷新后重新提交更正。")
            if not current and expected_revision_no is not None:
                raise PlanControlConflictError("当前状态日期没有可更正的进度快照。")
            if current:
                store.progress_snapshots = [
                    item.model_copy(update={"is_current": False})
                    if item.progress_snapshot_id == current.progress_snapshot_id
                    else item
                    for item in store.progress_snapshots
                ]
            store.progress_snapshots.append(snapshot)
            if correction:
                store.correction_records.append(correction)
            stale_ids: list[str] = []
            next_forecasts: list[ForecastSchedule] = []
            for forecast in store.forecasts:
                if forecast.plan_version_id == snapshot.plan_version_id and forecast.status != "stale":
                    stale_ids.append(forecast.forecast_id)
                    next_forecasts.append(forecast.model_copy(update={"status": "stale"}))
                else:
                    next_forecasts.append(forecast)
            store.forecasts = next_forecasts
            store.adjustment_proposals = [
                item.model_copy(update={"status": "stale"}) if item.forecast_id in stale_ids else item
                for item in store.adjustment_proposals
            ]
            plan = next((item for item in store.plan_versions if item.plan_version_id == snapshot.plan_version_id), None)
            stale_integrated_ids: list[str] = []
            if plan and plan.scenario_version_id:
                next_integrated: list[IntegratedCalculationSnapshot] = []
                for item in store.integrated_calculation_snapshots:
                    if item.scenario_version_id == plan.scenario_version_id and item.status != "stale":
                        stale_integrated_ids.append(item.integrated_snapshot_id)
                        next_integrated.append(item.model_copy(update={"status": "stale"}))
                    else:
                        next_integrated.append(item)
                store.integrated_calculation_snapshots = next_integrated
            self._write_unlocked(store)
        return snapshot, stale_ids, stale_integrated_ids

    def add_forecast(self, forecast: ForecastSchedule) -> ForecastSchedule:
        with self._lock:
            store = self._load_unlocked()
            existing = next(
                (
                    item
                    for item in store.forecasts
                    if item.input_fingerprint == forecast.input_fingerprint and item.status != "stale"
                ),
                None,
            )
            if existing is not None:
                return existing
            store.forecasts.append(forecast)
            self._write_unlocked(store)
        return forecast

    def add_proposals(self, proposals: list[AdjustmentProposal]) -> list[AdjustmentProposal]:
        with self._lock:
            store = self._load_unlocked()
            existing = {item.proposal_id for item in store.adjustment_proposals}
            store.adjustment_proposals.extend(item for item in proposals if item.proposal_id not in existing)
            self._write_unlocked(store)
        return proposals

    def adopt(
        self,
        *,
        proposal_id: str,
        expected_plan_fingerprint: str,
        new_version: PlanVersion,
        change_record: PlanChangeRecord,
    ) -> tuple[PlanVersion, PlanVersion]:
        with self._lock:
            store = self._load_unlocked()
            proposal = next((item for item in store.adjustment_proposals if item.proposal_id == proposal_id), None)
            if proposal is None:
                raise PlanControlNotFoundError(f"调整方案 {proposal_id} 不存在。")
            if proposal.status != "feasible":
                raise PlanControlConflictError("只能采用未过期且可行的调整方案。")
            source = next((item for item in store.plan_versions if item.plan_version_id == proposal.plan_version_id), None)
            if source is None:
                raise PlanControlNotFoundError("来源计划版本不存在。")
            if source.input_fingerprint != expected_plan_fingerprint or source.status != "active":
                raise PlanControlConflictError("来源计划已经变化，请重新生成预测和调整方案。")
            if any(item.proposal_id == proposal_id for item in store.plan_change_records):
                raise PlanControlConflictError("该调整方案已经采用。")
            previous = source.model_copy(update={"status": "superseded"})
            store.plan_versions = [previous if item.plan_version_id == source.plan_version_id else item for item in store.plan_versions]
            store.plan_versions.append(new_version)
            store.plan_change_records.append(change_record)
            self._write_unlocked(store)
        return new_version, previous

    def next_version_no(self, project_id: str, plan_type: str = "master") -> int:
        store = self.load()
        return max(
            (item.version_no for item in store.plan_versions if item.project_id == project_id and item.plan_type == plan_type),
            default=0,
        ) + 1

    def current_snapshot_for_date(self, plan_version_id: str, status_date) -> ProgressSnapshot | None:
        store = self.load()
        return next(
            (
                item
                for item in store.progress_snapshots
                if item.plan_version_id == plan_version_id and item.status_date == status_date and item.is_current
            ),
            None,
        )

    def _load_unlocked(self) -> PlanControlStore:
        if not self.path.exists():
            return PlanControlStore()
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            if raw.get("schema_version") in {None, "plan-control/v1"}:
                raw["schema_version"] = "plan-control/v2"
                raw.setdefault("project_data_versions", [])
                raw.setdefault("planning_scenario_versions", [])
                raw.setdefault("integrated_calculation_snapshots", [])
            return PlanControlStore.model_validate(raw)
        except (OSError, json.JSONDecodeError, ValidationError) as exc:
            raise PlanControlRepositoryError(f"计划管控本地存储读取失败：{exc}") from exc

    def _write_unlocked(self, store: PlanControlStore) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(f"{self.path.suffix}.tmp")
        try:
            temporary.write_text(
                json.dumps(store.model_dump(mode="json"), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            temporary.replace(self.path)
        except OSError as exc:
            raise PlanControlRepositoryError(f"计划管控本地存储写入失败：{exc}") from exc


default_plan_control_repository = PlanControlRepository()

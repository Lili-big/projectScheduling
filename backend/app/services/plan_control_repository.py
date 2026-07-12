from __future__ import annotations

import json
import threading
from pathlib import Path

from pydantic import ValidationError

from ..models import (
    AdjustmentProposal,
    ForecastSchedule,
    PlanChangeRecord,
    PlanControlProjectSummary,
    PlanControlStore,
    PlanVersion,
    ProgressCorrectionRecord,
    ProgressSnapshot,
)


PROJECT_ROOT = Path(__file__).resolve().parents[3]
PLAN_CONTROL_STORE_PATH = PROJECT_ROOT / ".local-data" / "plan-control-store.json"


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
    ) -> tuple[ProgressSnapshot, list[str]]:
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
            self._write_unlocked(store)
        return snapshot, stale_ids

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

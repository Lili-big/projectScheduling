"""Independent JSON repository for girder plan scenarios and run snapshots."""

from __future__ import annotations

import json
import os
import threading
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from ..contracts.girder_plan_simulation import (
    ConfirmSimulationRunRequest,
    CreateScenarioVersionRequest,
    GirderPlanScenarioVersion,
    GirderPlanSimulationRun,
)
from ..girder_planning.fingerprints import stable_fingerprint
from ..local_paths import state_path


class GirderPlanRepositoryError(RuntimeError):
    status_code = 503
    code = "GIRDER_PLAN_SIMULATION_STORAGE_ERROR"


class GirderPlanNotFoundError(GirderPlanRepositoryError):
    status_code = 404
    code = "GIRDER_PLAN_SIMULATION_NOT_FOUND"


class GirderPlanConflictError(GirderPlanRepositoryError):
    status_code = 409
    code = "GIRDER_PLAN_SIMULATION_CONFLICT"


class GirderPlanRepository:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self._lock = threading.RLock()
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def create_scenario_version(self, request: CreateScenarioVersionRequest) -> GirderPlanScenarioVersion:
        with self._lock:
            store = self._load()
            scenario_id = request.scenario_id or f"gps-{uuid4().hex}"
            versions = [
                GirderPlanScenarioVersion.model_validate(item)
                for item in store["scenarios"].values()
                if item.get("scenario_id") == scenario_id
            ]
            latest_version_no = max((item.version_no for item in versions), default=0)
            if request.expected_latest_version_no is not None and request.expected_latest_version_no != latest_version_no:
                exc = GirderPlanConflictError("方案版本已变化，请基于最新版本重新保存。")
                exc.code = "SCENARIO_VERSION_CHANGED"
                raise exc
            version_no = latest_version_no + 1
            input_fingerprint = stable_fingerprint(_scenario_input_payload(request))
            for previous in versions:
                if previous.status not in {"stale", "blocked"} and previous.input_fingerprint != input_fingerprint:
                    stale = previous.model_copy(
                        update={
                            "status": "stale",
                            "stale_reason": "项目版本、线路拓扑、梁场能力、库存、人工顺序或缓冲参数已变化。",
                        }
                    )
                    store["scenarios"][stale.scenario_version_id] = stale.model_dump(mode="json")
                    for run_id, raw_run in list(store["runs"].items()):
                        if raw_run.get("scenario_version_id") == previous.scenario_version_id and raw_run.get("status") != "stale":
                            raw_run = {**raw_run, "status": "stale"}
                            store["runs"][run_id] = raw_run
            request_payload = request.model_dump()
            request_payload["scenario_id"] = scenario_id
            version = GirderPlanScenarioVersion(
                **request_payload,
                scenario_version_id=f"gpsv-{uuid4().hex}",
                version_no=version_no,
                status="draft",
                input_fingerprint=input_fingerprint,
                created_at=datetime.now(timezone.utc),
            )
            store["scenarios"][version.scenario_version_id] = version.model_dump(mode="json")
            self._save(store)
            return version.model_copy(deep=True)

    def list_scenario_versions(self, project_id: str | None = None) -> list[GirderPlanScenarioVersion]:
        with self._lock:
            values = [GirderPlanScenarioVersion.model_validate(item) for item in self._load()["scenarios"].values()]
        if project_id is not None:
            values = [item for item in values if item.project_id == project_id]
        return sorted(values, key=lambda item: (item.created_at, item.version_no), reverse=True)

    def get_scenario_version(self, scenario_version_id: str) -> GirderPlanScenarioVersion:
        with self._lock:
            raw = self._load()["scenarios"].get(scenario_version_id)
        if raw is None:
            raise GirderPlanNotFoundError(f"架梁计划方案版本 {scenario_version_id} 不存在。")
        return GirderPlanScenarioVersion.model_validate(deepcopy(raw))

    def set_scenario_status(
        self,
        scenario_version_id: str,
        status: str,
        *,
        stale_reason: str | None = None,
    ) -> GirderPlanScenarioVersion:
        with self._lock:
            store = self._load()
            raw = store["scenarios"].get(scenario_version_id)
            if raw is None:
                raise GirderPlanNotFoundError(f"架梁计划方案版本 {scenario_version_id} 不存在。")
            version = GirderPlanScenarioVersion.model_validate(raw).model_copy(
                update={"status": status, "stale_reason": stale_reason}
            )
            store["scenarios"][scenario_version_id] = version.model_dump(mode="json")
            self._save(store)
            return version.model_copy(deep=True)

    def save_run(self, run: GirderPlanSimulationRun) -> GirderPlanSimulationRun:
        with self._lock:
            store = self._load()
            if run.run_id in store["runs"]:
                raise GirderPlanConflictError(f"运行快照 {run.run_id} 已存在且不可覆盖。")
            if run.scenario_version_id not in store["scenarios"]:
                raise GirderPlanNotFoundError(f"架梁计划方案版本 {run.scenario_version_id} 不存在。")
            store["runs"][run.run_id] = run.model_dump(mode="json")
            scenario = GirderPlanScenarioVersion.model_validate(store["scenarios"][run.scenario_version_id])
            scenario_status = "calculated" if run.status == "calculated" else "blocked"
            scenario = scenario.model_copy(update={"status": scenario_status})
            store["scenarios"][scenario.scenario_version_id] = scenario.model_dump(mode="json")
            self._save(store)
        return run.model_copy(deep=True)

    def get_run(self, run_id: str) -> GirderPlanSimulationRun:
        with self._lock:
            raw = self._load()["runs"].get(run_id)
        if raw is None:
            raise GirderPlanNotFoundError(f"架梁计划运行 {run_id} 不存在。")
        return GirderPlanSimulationRun.model_validate(deepcopy(raw))

    def find_reusable_run(self, scenario_version_id: str, input_fingerprint: str) -> GirderPlanSimulationRun | None:
        with self._lock:
            runs = [GirderPlanSimulationRun.model_validate(item) for item in self._load()["runs"].values()]
        candidates = [
            item
            for item in runs
            if item.scenario_version_id == scenario_version_id
            and item.input_fingerprint == input_fingerprint
            and item.status in {"calculated", "confirmed"}
        ]
        return max(candidates, key=lambda item: item.finished_at).model_copy(deep=True) if candidates else None

    def confirm_run(self, run_id: str, request: ConfirmSimulationRunRequest) -> GirderPlanSimulationRun:
        with self._lock:
            store = self._load()
            raw = store["runs"].get(run_id)
            if raw is None:
                raise GirderPlanNotFoundError(f"架梁计划运行 {run_id} 不存在。")
            run = GirderPlanSimulationRun.model_validate(raw)
            if run.input_fingerprint != request.expected_input_fingerprint:
                exc = GirderPlanConflictError("运行输入指纹已变化，不能确认陈旧成果。")
                exc.code = "RUN_INPUT_FINGERPRINT_STALE"
                raise exc
            if run.status not in {"calculated", "confirmed"}:
                exc = GirderPlanConflictError(f"状态为 {run.status} 的运行不能确认。")
                exc.code = "RUN_NOT_CONFIRMABLE"
                raise exc
            now = datetime.now(timezone.utc)
            run = run.model_copy(
                update={
                    "status": "confirmed",
                    "confirmed_by": request.confirmed_by.strip(),
                    "confirmed_at": now,
                    "confirmation_reason": request.confirmation_reason.strip(),
                }
            )
            scenario = GirderPlanScenarioVersion.model_validate(store["scenarios"][run.scenario_version_id]).model_copy(
                update={
                    "status": "confirmed",
                    "confirmed_by": request.confirmed_by.strip(),
                    "confirmed_at": now,
                    "confirmation_reason": request.confirmation_reason.strip(),
                }
            )
            store["runs"][run_id] = run.model_dump(mode="json")
            store["scenarios"][scenario.scenario_version_id] = scenario.model_dump(mode="json")
            self._save(store)
            return run.model_copy(deep=True)

    def _load(self) -> dict:
        if not self.path.exists():
            return {"schema_version": 1, "scenarios": {}, "runs": {}}
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise GirderPlanRepositoryError(f"架梁计划状态文件不可读取：{exc}") from exc
        raw.setdefault("schema_version", 1)
        raw.setdefault("scenarios", {})
        raw.setdefault("runs", {})
        return raw

    def _save(self, store: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_name(f".{self.path.name}.{uuid4().hex}.tmp")
        try:
            temporary.write_text(json.dumps(store, ensure_ascii=False, sort_keys=True, indent=2), encoding="utf-8")
            os.replace(temporary, self.path)
        except OSError as exc:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass
            raise GirderPlanRepositoryError(f"架梁计划状态保存失败：{exc}") from exc


def _scenario_input_payload(request: CreateScenarioVersionRequest) -> dict:
    payload = request.model_dump(mode="json", exclude={"created_by", "expected_latest_version_no"})
    payload.pop("scenario_id", None)
    return payload


_default_lock = threading.Lock()
_default_repository: GirderPlanRepository | None = None
_default_path: Path | None = None


def default_girder_plan_repository() -> GirderPlanRepository:
    global _default_repository, _default_path
    path = state_path("girder-plan-simulation-store.json")
    with _default_lock:
        if _default_repository is None or _default_path != path:
            _default_repository = GirderPlanRepository(path)
            _default_path = path
        return _default_repository


__all__ = [
    "GirderPlanConflictError",
    "GirderPlanNotFoundError",
    "GirderPlanRepository",
    "GirderPlanRepositoryError",
    "default_girder_plan_repository",
]

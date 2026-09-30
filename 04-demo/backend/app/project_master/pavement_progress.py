"""Daily pavement lengths, independent of scheduling and master-data versions."""
from __future__ import annotations

import math
import sqlite3
from datetime import datetime, timezone
from decimal import Decimal

from ..contracts.project_master import PavementProgressView, PavementProgressRow, SavePavementProgressRequest
from .repository import ProjectMasterRepository, ProjectMasterRepositoryError

PROCESS_TYPES = {"granular_base", "cement_stabilized_base", "asphalt_course"}
MAX_LENGTH = Decimal("9007199254740.991")


def _error(status: int, code: str, message: str):
    error = ProjectMasterRepositoryError(message)
    error.status_code, error.code = status, code
    return error


def _current(connection, project_id):
    version = connection.execute(
        "SELECT version_id FROM project_master_versions WHERE project_id=? AND status='confirmed'", (project_id,)
    ).fetchone()
    if not version:
        raise _error(404, "PAVEMENT_PROGRESS_MASTER_NOT_FOUND", "该项目尚无已确认主数据，请先维护项目主数据。")
    revision = connection.execute("SELECT revision FROM pavement_progress_revisions WHERE project_id=?", (project_id,)).fetchone()
    return version[0], revision[0] if revision else 0


def _master_rows(repository, connection, version_id):
    snapshot = repository.load_snapshot(version_id, connection=connection)
    if any(w.workpoint_type != "pavement" for w in snapshot.workpoints):
        raise _error(422, "PAVEMENT_FEATURE_NOT_SUPPORTED", "实际进度表适用于路面项目主数据。")
    result = {}
    for workpoint in snapshot.workpoints:
        for section in workpoint.structures:
            params = {p.parameter_code: p.value for p in section.parameters}
            for component in section.components:
                if component.component_type not in PROCESS_TYPES:
                    continue
                cp = {p.parameter_code: p.value for p in component.parameters}
                result[component.component_id] = PavementProgressRow(
                    component_id=component.component_id, workpoint_id=workpoint.workpoint_id,
                    structure_id=section.structure_id, section_name=section.structure_name,
                    component_name=component.component_name, side=section.side, section_code=section.section_code,
                    start_chainage=str(params["start_chainage"]) if params.get("start_chainage") is not None else None,
                    end_chainage=str(params["end_chainage"]) if params.get("end_chainage") is not None else None,
                    source_version_id=version_id, status="active" if component.enabled else "disabled",
                    design_length_m=_number(params.get("construction_length_m")), width_m=_number(params.get("width_m")),
                    thickness_m=_number(cp.get("thickness_m")),
                )
    return result


def _number(value):
    if isinstance(value, bool) or value is None:
        return None
    try:
        n = float(value)
        return n if math.isfinite(n) and n > 0 else None
    except (TypeError, ValueError):
        return None


def _view(repository, connection, project_id):
    version, revision = _current(connection, project_id)
    rows = _master_rows(repository, connection, version)
    records = connection.execute(
        "SELECT * FROM pavement_daily_progress WHERE project_id=? ORDER BY updated_at, progress_date, component_id", (project_id,)
    ).fetchall()
    totals: dict[str, Decimal] = {}
    latest_versions = {}
    entries = []
    for record in records:
        cid = record["component_id"]
        amount = Decimal(record["completed_length_m"])
        totals[cid] = totals.get(cid, Decimal(0)) + amount
        latest_versions[cid] = record["source_version_id"]
        entries.append(dict(component_id=cid, progress_date=record["progress_date"], completed_length_m=float(amount)))
    historical_versions = {}
    for cid in totals:
        if cid not in rows:
            historical_version = latest_versions[cid]
            if historical_version not in historical_versions:
                historical_versions[historical_version] = _master_rows(repository, connection, historical_version)
            rows[cid] = historical_versions[historical_version][cid].model_copy(update={"status": "removed"})
    active, history = [], []
    for cid, row in rows.items():
        total = totals.get(cid, Decimal(0))
        if total > MAX_LENGTH:
            raise _error(422, "PAVEMENT_PROGRESS_INVALID_CELL", f"工序 {cid} 累计完成量超出可安全表示范围。")
        remainder = Decimal(str(row.design_length_m)) - total if row.design_length_m is not None else None
        row.completed_length_m = float(total)
        row.remaining_length_m = float(remainder) if remainder is not None else None
        row.overrun_length_m = float(max(-remainder, Decimal(0))) if remainder is not None else None
        if row.status == "active":
            active.append(row)
        elif cid in totals:
            history.append(row)
    return PavementProgressView(project_id=project_id, master_version_id=version, revision=revision,
        rows=active, historical_rows=history, entries=entries)


def read_progress(repository: ProjectMasterRepository, project_id: str) -> PavementProgressView:
    try:
        with repository.connection() as connection:
            connection.execute("BEGIN")
            return _view(repository, connection, project_id)
    except sqlite3.Error as exc:
        raise _error(503, "PAVEMENT_PROGRESS_STORAGE_ERROR", "进度数据暂时无法读取，请重试。") from exc


def save_progress(repository: ProjectMasterRepository, project_id: str, payload: SavePavementProgressRequest) -> PavementProgressView:
    try:
        with repository.transaction() as connection:
            version, revision = _current(connection, project_id)
            if version != payload.expected_master_version_id:
                raise _error(409, "PAVEMENT_PROGRESS_MASTER_CHANGED", "项目主数据已更新，请重新加载并核对未保存记录。")
            if revision != payload.expected_revision:
                raise _error(409, "PAVEMENT_PROGRESS_REVISION_CONFLICT", "进度已在其他页面保存，请重新加载并核对本地修改。")
            rows = _master_rows(repository, connection, version)
            seen = set()
            for cell in payload.cells:
                key = (cell.component_id, cell.progress_date)
                if key in seen or cell.component_id not in rows or rows[cell.component_id].status != "active":
                    raise _error(422, "PAVEMENT_PROGRESS_INVALID_CELL", f"{cell.component_id} / {cell.progress_date}：重复日格或不是本项目当前启用工序。")
                seen.add(key)
            now = datetime.now(timezone.utc).isoformat()
            changed = False
            for cell in payload.cells:
                key = (project_id, cell.component_id, cell.progress_date)
                old = connection.execute("SELECT completed_length_m FROM pavement_daily_progress WHERE project_id=? AND component_id=? AND progress_date=?", key).fetchone()
                if cell.completed_length_m is None:
                    if old:
                        connection.execute("DELETE FROM pavement_daily_progress WHERE project_id=? AND component_id=? AND progress_date=?", key)
                        changed = True
                else:
                    amount = Decimal(str(cell.completed_length_m))
                    if old and Decimal(old[0]) == amount:
                        continue
                    connection.execute("""INSERT INTO pavement_daily_progress VALUES (?,?,?,?,?,?)
                        ON CONFLICT(project_id,component_id,progress_date) DO UPDATE SET
                        completed_length_m=excluded.completed_length_m,source_version_id=excluded.source_version_id,updated_at=excluded.updated_at""",
                        (*key, format(amount, "f"), version, now))
                    changed = True
            if changed:
                connection.execute("""INSERT INTO pavement_progress_revisions VALUES (?,?,?)
                    ON CONFLICT(project_id) DO UPDATE SET revision=excluded.revision,updated_at=excluded.updated_at""",
                    (project_id, revision + 1, now))
            # Compute and validate the response before commit so even overflow rolls back the full batch.
            return _view(repository, connection, project_id)
    except sqlite3.Error as exc:
        raise _error(503, "PAVEMENT_PROGRESS_STORAGE_ERROR", "进度保存失败，本批记录未提交，请重试。") from exc

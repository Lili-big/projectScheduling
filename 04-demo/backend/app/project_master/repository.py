from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator
from uuid import uuid4

from ..contracts.project_master import (
    ParameterValue,
    ProjectMasterComponent,
    ProjectMasterCounts,
    ProjectMasterDiffCounts,
    ProjectMasterDiffEntry,
    ProjectMasterImportBatch,
    ProjectMasterImportIssue,
    ProjectMasterSnapshot,
    ProjectMasterStructure,
    ProjectMasterVersionDetail,
    ProjectMasterVersionSummary,
    ProjectMasterWorkpoint,
    ProjectMasterWorkpointPage,
    SourceEvidence,
)
from .schema import initialize_schema


class ProjectMasterRepositoryError(RuntimeError):
    status_code = 503
    code = "PROJECT_MASTER_STORAGE_ERROR"


class ProjectMasterNotFoundError(ProjectMasterRepositoryError):
    status_code = 404
    code = "PROJECT_MASTER_NOT_FOUND"


class ProjectMasterConflictError(ProjectMasterRepositoryError):
    status_code = 409
    code = "PROJECT_MASTER_CONFLICT"


class ProjectMasterRepository:
    def __init__(self, path: Path, *, busy_timeout_ms: int = 5000) -> None:
        self.path = Path(path)
        self.busy_timeout_ms = max(100, int(busy_timeout_ms))
        self._lock = threading.RLock()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as connection:
            initialize_schema(connection)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=self.busy_timeout_ms / 1000, check_same_thread=False)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute(f"PRAGMA busy_timeout = {self.busy_timeout_ms}")
        connection.execute("PRAGMA journal_mode = WAL")
        return connection

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        connection = self._connect()
        try:
            yield connection
        finally:
            connection.close()

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        with self._lock:
            connection = self._connect()
            try:
                connection.execute("BEGIN IMMEDIATE")
                yield connection
                connection.commit()
            except Exception:
                connection.rollback()
                raise
            finally:
                connection.close()

    def create_import_batch(
        self,
        *,
        project_id: str,
        file_name: str,
        file_sha256: str,
        expected_current_version_id: str | None,
        created_by: str,
    ) -> ProjectMasterImportBatch:
        batch_id = f"pmb-{uuid4().hex}"
        created_at = _utc_now()
        with self.transaction() as connection:
            connection.execute(
                """
                INSERT INTO import_batches(
                    batch_id, project_id, status, file_name, file_sha256,
                    expected_current_version_id, counts_json, diff_counts_json,
                    created_at, created_by
                ) VALUES (?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    batch_id,
                    project_id,
                    "validating",
                    file_name,
                    file_sha256,
                    expected_current_version_id,
                    _json(ProjectMasterCounts().model_dump()),
                    _json(ProjectMasterDiffCounts().model_dump()),
                    created_at,
                    created_by,
                ),
            )
        return self.get_import_batch(batch_id)

    def complete_blocked_batch(
        self,
        batch_id: str,
        *,
        issues: list[ProjectMasterImportIssue],
        counts: ProjectMasterCounts,
        content_fingerprint: str | None = None,
    ) -> ProjectMasterImportBatch:
        with self.transaction() as connection:
            self._replace_issues(connection, batch_id, issues)
            connection.execute(
                """
                UPDATE import_batches
                SET status='blocked', content_fingerprint=?, counts_json=?, completed_at=?
                WHERE batch_id=?
                """,
                (content_fingerprint, _json(counts.model_dump()), _utc_now(), batch_id),
            )
        return self.get_import_batch(batch_id)

    def complete_unchanged_batch(
        self,
        batch_id: str,
        *,
        existing_version_id: str,
        content_fingerprint: str,
        counts: ProjectMasterCounts,
        issues: list[ProjectMasterImportIssue],
    ) -> ProjectMasterImportBatch:
        with self.transaction() as connection:
            self._replace_issues(connection, batch_id, issues)
            connection.execute(
                """
                UPDATE import_batches SET status='unchanged', content_fingerprint=?,
                    existing_version_id=?, counts_json=?, completed_at=?
                WHERE batch_id=?
                """,
                (content_fingerprint, existing_version_id, _json(counts.model_dump()), _utc_now(), batch_id),
            )
        return self.get_import_batch(batch_id)

    def fail_batch(self, batch_id: str, message: str) -> ProjectMasterImportBatch:
        with self.transaction() as connection:
            connection.execute(
                "UPDATE import_batches SET status='failed', failure_message=?, completed_at=? WHERE batch_id=?",
                (message, _utc_now(), batch_id),
            )
        return self.get_import_batch(batch_id)

    def create_draft_version(
        self,
        *,
        batch_id: str,
        project_id: str,
        content_fingerprint: str,
        snapshot: ProjectMasterSnapshot,
        issues: list[ProjectMasterImportIssue],
        diff_entries: list[ProjectMasterDiffEntry],
        created_by: str,
        base_version_id: str | None,
    ) -> ProjectMasterVersionSummary:
        counts = _snapshot_counts(snapshot, issues)
        diff_counts = _diff_counts(diff_entries)
        created_at = _utc_now()
        version_id = f"pmv-{uuid4().hex}"
        with self.transaction() as connection:
            duplicate = connection.execute(
                "SELECT version_id FROM project_master_versions WHERE project_id=? AND content_fingerprint=?",
                (project_id, content_fingerprint),
            ).fetchone()
            if duplicate:
                raise ProjectMasterConflictError("相同项目主数据内容已经存在。")
            latest = connection.execute(
                "SELECT COALESCE(MAX(version_no), 0) AS version_no FROM project_master_versions WHERE project_id=?",
                (project_id,),
            ).fetchone()
            version_no = int(latest["version_no"]) + 1
            connection.execute(
                """
                INSERT INTO project_master_versions(
                    version_id, project_id, version_no, status, content_fingerprint,
                    source_batch_id, base_version_id, summary_json, created_at, created_by
                ) VALUES (?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    version_id,
                    project_id,
                    version_no,
                    "draft",
                    content_fingerprint,
                    batch_id,
                    base_version_id,
                    _json(counts.model_dump()),
                    created_at,
                    created_by,
                ),
            )
            self._insert_snapshot(connection, version_id, batch_id, snapshot)
            connection.executemany(
                """
                INSERT INTO version_diff_entries(
                    diff_id, version_id, base_version_id, object_kind, object_id,
                    change_type, field_name, before_value_json, after_value_json,
                    blocking_reference
                ) VALUES (?,?,?,?,?,?,?,?,?,?)
                """,
                [
                    (
                        entry.diff_id or f"pmd-{uuid4().hex}",
                        version_id,
                        base_version_id,
                        entry.object_kind,
                        entry.object_id,
                        entry.change_type,
                        entry.field_name,
                        _json(entry.before_value),
                        _json(entry.after_value),
                        int(entry.blocking_reference),
                    )
                    for entry in diff_entries
                ],
            )
            self._replace_issues(connection, batch_id, issues)
            connection.execute(
                """
                UPDATE import_batches SET status='ready', content_fingerprint=?,
                    created_version_id=?, counts_json=?, diff_counts_json=?, completed_at=?
                WHERE batch_id=?
                """,
                (
                    content_fingerprint,
                    version_id,
                    _json(counts.model_dump()),
                    _json(diff_counts.model_dump()),
                    _utc_now(),
                    batch_id,
                ),
            )
        # Import only needs the new version identity. Loading every first-import
        # diff row here can materialize 60k+ records before the API returns the
        # compact batch summary; callers can request version detail explicitly.
        return self.get_version_summary(version_id)

    def find_version_by_fingerprint(self, project_id: str, fingerprint: str) -> ProjectMasterVersionSummary | None:
        with self.connection() as connection:
            row = connection.execute(
                "SELECT * FROM project_master_versions WHERE project_id=? AND content_fingerprint=?",
                (project_id, fingerprint),
            ).fetchone()
        return self._version_summary(row) if row else None

    def get_import_batch(self, batch_id: str) -> ProjectMasterImportBatch:
        with self.connection() as connection:
            row = connection.execute("SELECT * FROM import_batches WHERE batch_id=?", (batch_id,)).fetchone()
            if row is None:
                raise ProjectMasterNotFoundError(f"导入批次 {batch_id} 不存在。")
            issue_rows = connection.execute(
                "SELECT * FROM import_issues WHERE batch_id=? ORDER BY severity, sheet_name, row_no, field_name",
                (batch_id,),
            ).fetchall()
        return ProjectMasterImportBatch(
            batch_id=row["batch_id"],
            project_id=row["project_id"],
            status=row["status"],
            file_name=row["file_name"],
            file_sha256=row["file_sha256"],
            content_fingerprint=row["content_fingerprint"],
            expected_current_version_id=row["expected_current_version_id"],
            created_version_id=row["created_version_id"],
            existing_version_id=row["existing_version_id"],
            cancelled_version_id=row["cancelled_version_id"],
            counts=ProjectMasterCounts(**_loads(row["counts_json"], {})),
            diff_counts=ProjectMasterDiffCounts(**_loads(row["diff_counts_json"], {})),
            issues=[self._issue(item) for item in issue_rows],
            created_at=row["created_at"],
            created_by=row["created_by"],
            completed_at=row["completed_at"],
            cancelled_at=row["cancelled_at"],
            cancelled_by=row["cancelled_by"],
            cancel_reason=row["cancel_reason"],
            failure_message=row["failure_message"],
        )

    def cancel_import_batch(self, batch_id: str, *, cancelled_by: str, cancel_reason: str | None) -> ProjectMasterImportBatch:
        with self.transaction() as connection:
            row = connection.execute("SELECT * FROM import_batches WHERE batch_id=?", (batch_id,)).fetchone()
            if row is None:
                raise ProjectMasterNotFoundError(f"导入批次 {batch_id} 不存在。")
            if row["status"] not in {"blocked", "ready"}:
                raise ProjectMasterConflictError(f"状态为 {row['status']} 的导入批次不能取消。")
            cancelled_version_id = row["created_version_id"]
            if cancelled_version_id:
                version = connection.execute(
                    "SELECT status FROM project_master_versions WHERE version_id=?",
                    (cancelled_version_id,),
                ).fetchone()
                if version is None or version["status"] != "draft":
                    raise ProjectMasterConflictError("只有未确认草稿版本可以取消。")
                connection.execute("DELETE FROM project_master_versions WHERE version_id=?", (cancelled_version_id,))
            connection.execute(
                """
                UPDATE import_batches SET status='cancelled', created_version_id=NULL,
                    cancelled_version_id=?, cancelled_at=?, cancelled_by=?, cancel_reason=?
                WHERE batch_id=?
                """,
                (cancelled_version_id, _utc_now(), cancelled_by, cancel_reason, batch_id),
            )
        return self.get_import_batch(batch_id)

    def list_versions(self, project_id: str, *, page: int = 1, page_size: int = 50) -> tuple[list[ProjectMasterVersionSummary], int]:
        offset = (page - 1) * page_size
        with self.connection() as connection:
            total = int(connection.execute(
                "SELECT COUNT(*) FROM project_master_versions WHERE project_id=?", (project_id,)
            ).fetchone()[0])
            rows = connection.execute(
                """
                SELECT * FROM project_master_versions WHERE project_id=?
                ORDER BY version_no DESC LIMIT ? OFFSET ?
                """,
                (project_id, page_size, offset),
            ).fetchall()
        return [self._version_summary(row) for row in rows], total

    def get_current_version(self, project_id: str) -> ProjectMasterVersionSummary | None:
        with self.connection() as connection:
            row = connection.execute(
                "SELECT * FROM project_master_versions WHERE project_id=? AND status='confirmed'",
                (project_id,),
            ).fetchone()
        return self._version_summary(row) if row else None

    def get_version_summary(self, version_id: str) -> ProjectMasterVersionSummary:
        with self.connection() as connection:
            row = connection.execute("SELECT * FROM project_master_versions WHERE version_id=?", (version_id,)).fetchone()
        if row is None:
            raise ProjectMasterNotFoundError(f"项目主数据版本 {version_id} 不存在。")
        return self._version_summary(row)

    def get_version_detail(self, version_id: str) -> ProjectMasterVersionDetail:
        summary = self.get_version_summary(version_id)
        with self.connection() as connection:
            rows = connection.execute(
                "SELECT * FROM version_diff_entries WHERE version_id=? ORDER BY object_kind, object_id, field_name",
                (version_id,),
            ).fetchall()
            warnings = connection.execute(
                "SELECT DISTINCT issue_code FROM import_issues WHERE batch_id=? AND severity='warning' ORDER BY issue_code",
                (summary.source_batch_id,),
            ).fetchall()
        entries = [
            ProjectMasterDiffEntry(
                diff_id=row["diff_id"],
                object_kind=row["object_kind"],
                object_id=row["object_id"],
                change_type=row["change_type"],
                field_name=row["field_name"],
                before_value=_loads(row["before_value_json"], None),
                after_value=_loads(row["after_value_json"], None),
                blocking_reference=bool(row["blocking_reference"]),
            )
            for row in rows
        ]
        return ProjectMasterVersionDetail(
            **summary.model_dump(),
            diff_counts=_diff_counts(entries),
            diff_entries=entries,
            warning_codes=[row["issue_code"] for row in warnings],
        )

    def confirm_version(
        self,
        version_id: str,
        *,
        expected_current_version_id: str | None,
        confirmed_by: str,
    ) -> ProjectMasterVersionDetail:
        with self.transaction() as connection:
            row = connection.execute("SELECT * FROM project_master_versions WHERE version_id=?", (version_id,)).fetchone()
            if row is None:
                raise ProjectMasterNotFoundError(f"项目主数据版本 {version_id} 不存在。")
            if row["status"] != "draft":
                exc = ProjectMasterConflictError("只有草稿版本可以确认；已确认历史版本不可修改。")
                exc.code = "VERSION_IMMUTABLE"
                raise exc
            current = connection.execute(
                "SELECT version_id FROM project_master_versions WHERE project_id=? AND status='confirmed'",
                (row["project_id"],),
            ).fetchone()
            current_id = current["version_id"] if current else None
            if current_id != expected_current_version_id:
                exc = ProjectMasterConflictError("当前确认版本已变化，请基于最新版本重新导入。")
                exc.code = "CURRENT_VERSION_CHANGED"
                raise exc
            if current_id:
                connection.execute(
                    "UPDATE project_master_versions SET status='superseded' WHERE version_id=?",
                    (current_id,),
                )
            now = _utc_now()
            connection.execute(
                """
                UPDATE project_master_versions
                SET status='confirmed', confirmed_at=?, confirmed_by=? WHERE version_id=?
                """,
                (now, confirmed_by, version_id),
            )
            connection.execute(
                "UPDATE import_batches SET status='confirmed' WHERE batch_id=?",
                (row["source_batch_id"],),
            )
        return self.get_version_detail(version_id)

    def load_snapshot(self, version_id: str) -> ProjectMasterSnapshot:
        self.get_version_summary(version_id)
        with self.connection() as connection:
            workpoint_rows = connection.execute(
                "SELECT * FROM workpoints WHERE version_id=? ORDER BY sort_order, workpoint_id", (version_id,)
            ).fetchall()
            structure_rows = connection.execute(
                "SELECT * FROM structures WHERE version_id=? ORDER BY workpoint_id, sort_order, structure_id", (version_id,)
            ).fetchall()
            component_rows = connection.execute(
                "SELECT * FROM components WHERE version_id=? ORDER BY structure_id, sort_order, component_id", (version_id,)
            ).fetchall()
            structure_parameters = connection.execute(
                "SELECT * FROM structure_parameters WHERE version_id=? ORDER BY structure_id, sort_order, parameter_code",
                (version_id,),
            ).fetchall()
            component_parameters = connection.execute(
                "SELECT * FROM component_parameters WHERE version_id=? ORDER BY component_id, sort_order, parameter_code",
                (version_id,),
            ).fetchall()
            evidence_rows = connection.execute(
                "SELECT * FROM source_evidence WHERE version_id=?", (version_id,)
            ).fetchall()
        evidence = {(row["object_kind"], row["object_id"], row["parameter_code"]): row for row in evidence_rows}
        component_params: dict[str, list[ParameterValue]] = {}
        for row in component_parameters:
            component_params.setdefault(row["component_id"], []).append(
                self._parameter(row, evidence.get(("component_parameter", row["component_id"], row["parameter_code"])))
            )
        components: dict[str, list[ProjectMasterComponent]] = {}
        for row in component_rows:
            components.setdefault(row["structure_id"], []).append(
                ProjectMasterComponent(
                    component_id=row["component_id"],
                    structure_id=row["structure_id"],
                    component_name=row["component_name"],
                    component_type=row["component_type"],
                    quantity=row["quantity"],
                    unit=row["unit"],
                    enabled=bool(row["enabled"]),
                    sort_order=row["sort_order"],
                    remark=row["remark"],
                    parameters=component_params.get(row["component_id"], []),
                    source=self._source(evidence.get(("component", row["component_id"], None))),
                )
            )
        structure_params: dict[str, list[ParameterValue]] = {}
        for row in structure_parameters:
            structure_params.setdefault(row["structure_id"], []).append(
                self._parameter(row, evidence.get(("structure_parameter", row["structure_id"], row["parameter_code"])))
            )
        structures: dict[str, list[ProjectMasterStructure]] = {}
        for row in structure_rows:
            structures.setdefault(row["workpoint_id"], []).append(
                ProjectMasterStructure(
                    structure_id=row["structure_id"],
                    workpoint_id=row["workpoint_id"],
                    structure_name=row["structure_name"],
                    structure_category=row["structure_category"],
                    structure_type=row["structure_type"],
                    side=row["side"],
                    section_code=row["section_code"],
                    section_name=row["section_name"],
                    control_level=row["control_level"],
                    sort_order=row["sort_order"],
                    remark=row["remark"],
                    parameters=structure_params.get(row["structure_id"], []),
                    components=components.get(row["structure_id"], []),
                    source=self._source(evidence.get(("structure", row["structure_id"], None))),
                )
            )
        return ProjectMasterSnapshot(
            workpoints=[
                ProjectMasterWorkpoint(
                    workpoint_id=row["workpoint_id"],
                    workpoint_name=row["workpoint_name"],
                    workpoint_type=row["workpoint_type"],
                    alignment_code=row["alignment_code"],
                    start_mileage_m=row["start_mileage_m"],
                    end_mileage_m=row["end_mileage_m"],
                    sort_order=row["sort_order"],
                    schedule_support=row["schedule_support"],
                    remark=row["remark"],
                    structures=structures.get(row["workpoint_id"], []),
                    source=self._source(evidence.get(("workpoint", row["workpoint_id"], None))),
                )
                for row in workpoint_rows
            ]
        )

    def list_workpoints(
        self,
        version_id: str,
        *,
        page: int = 1,
        page_size: int = 50,
        workpoint_type: str | None = None,
        keyword: str | None = None,
    ) -> ProjectMasterWorkpointPage:
        self.get_version_summary(version_id)
        clauses = ["version_id=?"]
        values: list[Any] = [version_id]
        if workpoint_type:
            clauses.append("workpoint_type=?")
            values.append(workpoint_type)
        if keyword:
            clauses.append("(workpoint_id LIKE ? OR workpoint_name LIKE ?)")
            pattern = f"%{keyword}%"
            values.extend([pattern, pattern])
        where = " AND ".join(clauses)
        with self.connection() as connection:
            total = int(connection.execute(f"SELECT COUNT(*) FROM workpoints WHERE {where}", values).fetchone()[0])
            rows = connection.execute(
                f"SELECT * FROM workpoints WHERE {where} ORDER BY sort_order, workpoint_id LIMIT ? OFFSET ?",
                [*values, page_size, (page - 1) * page_size],
            ).fetchall()
        items = [
            ProjectMasterWorkpoint(
                workpoint_id=row["workpoint_id"],
                workpoint_name=row["workpoint_name"],
                workpoint_type=row["workpoint_type"],
                alignment_code=row["alignment_code"],
                start_mileage_m=row["start_mileage_m"],
                end_mileage_m=row["end_mileage_m"],
                sort_order=row["sort_order"],
                schedule_support=row["schedule_support"],
                remark=row["remark"],
            )
            for row in rows
        ]
        return ProjectMasterWorkpointPage(page=page, page_size=page_size, total=total, items=items)

    def get_workpoint(self, version_id: str, workpoint_id: str) -> ProjectMasterWorkpoint:
        snapshot = self.load_snapshot(version_id)
        item = next((workpoint for workpoint in snapshot.workpoints if workpoint.workpoint_id == workpoint_id), None)
        if item is None:
            raise ProjectMasterNotFoundError(f"工点 {workpoint_id} 不存在。")
        return item

    def _insert_snapshot(
        self,
        connection: sqlite3.Connection,
        version_id: str,
        batch_id: str,
        snapshot: ProjectMasterSnapshot,
    ) -> None:
        workpoint_rows: list[tuple] = []
        structure_rows: list[tuple] = []
        structure_parameter_rows: list[tuple] = []
        component_rows: list[tuple] = []
        component_parameter_rows: list[tuple] = []
        source_rows: list[tuple] = []

        def append_source(
            object_kind: str,
            object_id: str,
            parameter_code: str | None,
            source: SourceEvidence | None,
        ) -> None:
            if source is None:
                return
            source_rows.append(
                (
                    f"pme-{uuid4().hex}",
                    version_id,
                    object_kind,
                    object_id,
                    parameter_code,
                    batch_id,
                    source.sheet_name,
                    source.row_no,
                    source.column_name,
                )
            )

        for workpoint in snapshot.workpoints:
            workpoint_rows.append(
                (
                    version_id,
                    workpoint.workpoint_id,
                    workpoint.workpoint_name,
                    workpoint.workpoint_type,
                    workpoint.alignment_code,
                    workpoint.start_mileage_m,
                    workpoint.end_mileage_m,
                    workpoint.sort_order,
                    workpoint.schedule_support,
                    workpoint.remark,
                )
            )
            append_source("workpoint", workpoint.workpoint_id, None, workpoint.source)
            for structure in workpoint.structures:
                structure_rows.append(
                    (
                        version_id,
                        structure.structure_id,
                        workpoint.workpoint_id,
                        structure.structure_name,
                        structure.structure_category,
                        structure.structure_type,
                        structure.side,
                        structure.section_code,
                        structure.section_name,
                        structure.control_level,
                        structure.sort_order,
                        structure.remark,
                    )
                )
                append_source("structure", structure.structure_id, None, structure.source)
                for parameter in structure.parameters:
                    structure_parameter_rows.append(
                        (
                            version_id,
                            structure.structure_id,
                            parameter.parameter_code,
                            parameter.value_type,
                            _json(parameter.value),
                            parameter.unit,
                            parameter.sort_order,
                        )
                    )
                    append_source(
                        "structure_parameter",
                        structure.structure_id,
                        parameter.parameter_code,
                        parameter.source,
                    )
                for component in structure.components:
                    component_rows.append(
                        (
                            version_id,
                            component.component_id,
                            structure.structure_id,
                            component.component_name,
                            component.component_type,
                            component.quantity,
                            component.unit,
                            int(component.enabled),
                            component.sort_order,
                            component.remark,
                        )
                    )
                    append_source("component", component.component_id, None, component.source)
                    for parameter in component.parameters:
                        component_parameter_rows.append(
                            (
                                version_id,
                                component.component_id,
                                parameter.parameter_code,
                                parameter.value_type,
                                _json(parameter.value),
                                parameter.unit,
                                parameter.sort_order,
                            )
                        )
                        append_source(
                            "component_parameter",
                            component.component_id,
                            parameter.parameter_code,
                            parameter.source,
                        )

        connection.executemany("INSERT INTO workpoints VALUES (?,?,?,?,?,?,?,?,?,?)", workpoint_rows)
        connection.executemany("INSERT INTO structures VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", structure_rows)
        connection.executemany("INSERT INTO structure_parameters VALUES (?,?,?,?,?,?,?)", structure_parameter_rows)
        connection.executemany("INSERT INTO components VALUES (?,?,?,?,?,?,?,?,?,?)", component_rows)
        connection.executemany("INSERT INTO component_parameters VALUES (?,?,?,?,?,?,?)", component_parameter_rows)
        connection.executemany("INSERT INTO source_evidence VALUES (?,?,?,?,?,?,?,?,?)", source_rows)

    def _insert_source(
        self,
        connection: sqlite3.Connection,
        version_id: str,
        batch_id: str,
        object_kind: str,
        object_id: str,
        parameter_code: str | None,
        source: SourceEvidence | None,
    ) -> None:
        if source is None:
            return
        connection.execute(
            "INSERT INTO source_evidence VALUES (?,?,?,?,?,?,?,?,?)",
            (
                f"pme-{uuid4().hex}",
                version_id,
                object_kind,
                object_id,
                parameter_code,
                batch_id,
                source.sheet_name,
                source.row_no,
                source.column_name,
            ),
        )

    def _replace_issues(
        self,
        connection: sqlite3.Connection,
        batch_id: str,
        issues: list[ProjectMasterImportIssue],
    ) -> None:
        connection.execute("DELETE FROM import_issues WHERE batch_id=?", (batch_id,))
        connection.executemany(
            "INSERT INTO import_issues VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            [
                (
                    issue.issue_id,
                    batch_id,
                    issue.severity,
                    issue.issue_code,
                    issue.sheet_name,
                    issue.row_no,
                    issue.field_name,
                    issue.object_kind,
                    issue.object_id,
                    issue.message,
                    issue.suggestion,
                )
                for issue in issues
            ],
        )

    def _version_summary(self, row: sqlite3.Row) -> ProjectMasterVersionSummary:
        return ProjectMasterVersionSummary(
            version_id=row["version_id"],
            project_id=row["project_id"],
            version_no=row["version_no"],
            status=row["status"],
            content_fingerprint=row["content_fingerprint"],
            source_batch_id=row["source_batch_id"],
            base_version_id=row["base_version_id"],
            counts=ProjectMasterCounts(**_loads(row["summary_json"], {})),
            created_at=row["created_at"],
            created_by=row["created_by"],
            confirmed_at=row["confirmed_at"],
            confirmed_by=row["confirmed_by"],
        )

    def _issue(self, row: sqlite3.Row) -> ProjectMasterImportIssue:
        return ProjectMasterImportIssue(
            issue_id=row["issue_id"],
            severity=row["severity"],
            issue_code=row["issue_code"],
            sheet_name=row["sheet_name"],
            row_no=row["row_no"],
            field_name=row["field_name"],
            object_kind=row["object_kind"],
            object_id=row["object_id"],
            message=row["message"],
            suggestion=row["suggestion"],
        )

    def _source(self, row: sqlite3.Row | None) -> SourceEvidence | None:
        if row is None:
            return None
        return SourceEvidence(
            batch_id=row["batch_id"],
            sheet_name=row["sheet_name"],
            row_no=row["row_no"],
            column_name=row["column_name"],
        )

    def _parameter(self, row: sqlite3.Row, source_row: sqlite3.Row | None) -> ParameterValue:
        return ParameterValue(
            parameter_code=row["parameter_code"],
            value_type=row["value_type"],
            value=_loads(row["value_json"], None),
            unit=row["unit"],
            sort_order=row["sort_order"],
            source=self._source(source_row),
        )


def _snapshot_counts(
    snapshot: ProjectMasterSnapshot,
    issues: list[ProjectMasterImportIssue] | None = None,
) -> ProjectMasterCounts:
    issues = issues or []
    return ProjectMasterCounts(
        workpoints=len(snapshot.workpoints),
        structures=sum(len(workpoint.structures) for workpoint in snapshot.workpoints),
        components=sum(
            len(structure.components)
            for workpoint in snapshot.workpoints
            for structure in workpoint.structures
        ),
        errors=sum(1 for issue in issues if issue.severity == "error"),
        warnings=sum(1 for issue in issues if issue.severity == "warning"),
    )


def _diff_counts(entries: list[ProjectMasterDiffEntry]) -> ProjectMasterDiffCounts:
    object_changes = {(entry.object_kind, entry.object_id, entry.change_type) for entry in entries}
    return ProjectMasterDiffCounts(
        added=sum(1 for _, _, change in object_changes if change == "added"),
        modified=sum(1 for _, _, change in object_changes if change == "modified"),
        deleted=sum(1 for _, _, change in object_changes if change == "deleted"),
    )


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _loads(value: str | None, default: Any) -> Any:
    if not value:
        return default
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return default


__all__ = [
    "ProjectMasterConflictError",
    "ProjectMasterNotFoundError",
    "ProjectMasterRepository",
    "ProjectMasterRepositoryError",
]

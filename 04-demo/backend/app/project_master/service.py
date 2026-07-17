from __future__ import annotations

import hashlib
import threading
from pathlib import Path
from typing import Callable
from zipfile import BadZipFile

from openpyxl.utils.exceptions import InvalidFileException

from ..config.environment import (
    project_master_db_path,
    project_master_import_max_bytes,
    project_master_sqlite_busy_timeout_ms,
)
from ..contracts.project_master import (
    CancelProjectMasterImportRequest,
    ConfirmProjectMasterVersionRequest,
    ProjectMasterCounts,
    ProjectMasterImportBatch,
    ProjectMasterSnapshot,
    ProjectMasterVersionDetail,
)
from .diff import diff_snapshots
from .repository import ProjectMasterConflictError, ProjectMasterRepository
from .validation import validate_snapshot
from .workbook import create_template_bytes, export_snapshot, parse_workbook


class ProjectMasterServiceError(RuntimeError):
    status_code = 503
    code = "PROJECT_MASTER_SERVICE_ERROR"


class ProjectMasterPayloadTooLargeError(ProjectMasterServiceError):
    status_code = 413
    code = "PAYLOAD_TOO_LARGE"


class ProjectMasterImportBlockedError(ProjectMasterServiceError):
    status_code = 422
    code = "IMPORT_BLOCKED"


ReferenceConflictChecker = Callable[[str, list[str]], list[str]]
VersionInvalidationHandler = Callable[[str], None]


class ProjectMasterService:
    def __init__(
        self,
        repository: ProjectMasterRepository,
        *,
        import_max_bytes: int = 25 * 1024 * 1024,
        reference_conflict_checker: ReferenceConflictChecker | None = None,
        version_invalidation_handler: VersionInvalidationHandler | None = None,
    ) -> None:
        self.repository = repository
        self.import_max_bytes = import_max_bytes
        self.reference_conflict_checker = reference_conflict_checker
        self.version_invalidation_handler = version_invalidation_handler

    def template_bytes(self) -> bytes:
        return create_template_bytes()

    def import_workbook(
        self,
        *,
        project_id: str,
        file_name: str,
        content: bytes,
        created_by: str,
        expected_current_version_id: str | None,
    ) -> ProjectMasterImportBatch:
        if len(content) > self.import_max_bytes:
            raise ProjectMasterPayloadTooLargeError(f"上传文件超过 {self.import_max_bytes} 字节限制。")
        batch = self.repository.create_import_batch(
            project_id=project_id.strip(),
            file_name=file_name,
            file_sha256=hashlib.sha256(content).hexdigest(),
            expected_current_version_id=expected_current_version_id,
            created_by=created_by.strip(),
        )
        try:
            try:
                snapshot, parse_issues, fingerprint = parse_workbook(content)
            except (BadZipFile, InvalidFileException) as invalid_file:
                exc = ProjectMasterServiceError("上传文件不是可读取的 XLSX/XLSM 工作簿。")
                exc.status_code = 422
                exc.code = "IMPORT_FILE_INVALID"
                raise exc from invalid_file
            issues = [*parse_issues, *validate_snapshot(snapshot)]
            counts = _counts(snapshot, issues)
            if any(issue.severity == "error" for issue in issues):
                return self.repository.complete_blocked_batch(
                    batch.batch_id,
                    issues=issues,
                    counts=counts,
                    content_fingerprint=fingerprint,
                )
            duplicate = self.repository.find_version_by_fingerprint(project_id, fingerprint)
            if duplicate is not None:
                return self.repository.complete_unchanged_batch(
                    batch.batch_id,
                    existing_version_id=duplicate.version_id,
                    content_fingerprint=fingerprint,
                    counts=counts,
                    issues=issues,
                )
            current = self.repository.get_current_version(project_id)
            if (current.version_id if current else None) != expected_current_version_id:
                exc = ProjectMasterConflictError("当前确认版本已变化，请基于最新版本重新导入。")
                exc.code = "CURRENT_VERSION_CHANGED"
                raise exc
            base_snapshot = self.repository.load_snapshot(current.version_id) if current else None
            differences = diff_snapshots(base_snapshot, snapshot)
            version = self.repository.create_draft_version(
                batch_id=batch.batch_id,
                project_id=project_id,
                content_fingerprint=fingerprint,
                snapshot=snapshot,
                issues=issues,
                diff_entries=differences,
                created_by=created_by,
                base_version_id=current.version_id if current else None,
            )
            return self.repository.get_import_batch(version.source_batch_id)
        except Exception as exc:
            try:
                self.repository.fail_batch(batch.batch_id, str(exc))
            except Exception:
                pass
            raise

    def confirm_version(
        self,
        version_id: str,
        request: ConfirmProjectMasterVersionRequest,
    ) -> ProjectMasterVersionDetail:
        detail = self.repository.get_version_detail(version_id)
        missing_warnings = sorted(set(detail.warning_codes) - set(request.acknowledge_warning_codes))
        if missing_warnings:
            exc = ProjectMasterConflictError(f"仍有未知悉告警：{', '.join(missing_warnings)}。")
            exc.code = "WARNING_NOT_ACKNOWLEDGED"
            raise exc
        if any(entry.blocking_reference for entry in detail.diff_entries):
            exc = ProjectMasterConflictError("待删除对象仍被计划或实绩引用，不能确认。")
            exc.code = "REFERENCE_CONFLICT"
            raise exc
        if self.reference_conflict_checker:
            deleted = [entry.object_id for entry in detail.diff_entries if entry.change_type == "deleted"]
            conflicts = self.reference_conflict_checker(version_id, deleted)
            if conflicts:
                exc = ProjectMasterConflictError("待删除对象仍被引用：" + "、".join(conflicts))
                exc.code = "REFERENCE_CONFLICT"
                raise exc
        if not request.confirmed_by.strip():
            raise ProjectMasterConflictError("确认人不能为空。")
        confirmed = self.repository.confirm_version(
            version_id,
            expected_current_version_id=request.expected_current_version_id,
            confirmed_by=request.confirmed_by.strip(),
        )
        if confirmed.base_version_id and self.version_invalidation_handler:
            self.version_invalidation_handler(confirmed.base_version_id)
        return confirmed

    def cancel_import(self, batch_id: str, request: CancelProjectMasterImportRequest) -> ProjectMasterImportBatch:
        if not request.cancelled_by.strip():
            raise ProjectMasterConflictError("取消人不能为空。")
        return self.repository.cancel_import_batch(
            batch_id,
            cancelled_by=request.cancelled_by.strip(),
            cancel_reason=(request.cancel_reason or "").strip() or None,
        )

    def export_version(self, version_id: str) -> bytes:
        return export_snapshot(self.repository.load_snapshot(version_id))


_default_lock = threading.Lock()
_default_service: ProjectMasterService | None = None
_default_path: Path | None = None


def default_project_master_service() -> ProjectMasterService:
    global _default_service, _default_path
    path = project_master_db_path()
    with _default_lock:
        if _default_service is None or _default_path != path:
            repository = ProjectMasterRepository(path, busy_timeout_ms=project_master_sqlite_busy_timeout_ms())
            from ..services.plan_control_repository import default_plan_control_repository

            _default_service = ProjectMasterService(
                repository,
                import_max_bytes=project_master_import_max_bytes(),
                version_invalidation_handler=default_plan_control_repository.invalidate_project_master_reference,
            )
            _default_path = path
        return _default_service


def _counts(snapshot: ProjectMasterSnapshot, issues) -> ProjectMasterCounts:
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


__all__ = [
    "ProjectMasterImportBlockedError",
    "ProjectMasterPayloadTooLargeError",
    "ProjectMasterService",
    "ProjectMasterServiceError",
    "default_project_master_service",
]

from __future__ import annotations

import hashlib
import math
import threading
from pathlib import Path
from typing import Callable
from zipfile import BadZipFile
from uuid import uuid4

from openpyxl.utils.exceptions import InvalidFileException

from ..config.environment import (
    project_master_db_path,
    project_master_import_max_bytes,
    project_master_sqlite_busy_timeout_ms,
)
from ..contracts.project_master import (
    CancelProjectMasterImportRequest,
    ConfirmProjectMasterVersionRequest,
    CreatePavementLayerDraftRequest,
    SavePavementSectionLayersRequest,
    SavePavementHandoverRequest,
    ParameterValue,
    ProjectMasterComponent,
    SourceEvidence,
    ProjectMasterCounts,
    ProjectMasterImportBatch,
    ProjectMasterSnapshot,
    ProjectMasterVersionDetail,
)
from .diff import diff_snapshots
from .repository import ProjectMasterConflictError, ProjectMasterNotFoundError, ProjectMasterRepository
from .validation import validate_snapshot
from .workbook import content_fingerprint, create_template_bytes, export_snapshot, parse_workbook


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

    def template_bytes(self, engineering_domain: str = "bridge") -> bytes:
        return create_template_bytes(engineering_domain)

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

    def create_pavement_layer_draft(
        self, version_id: str, request: CreatePavementLayerDraftRequest,
    ) -> ProjectMasterImportBatch:
        base = self.repository.get_version_summary(version_id)
        current = self.repository.get_current_version(base.project_id)
        if current is None or current.version_id != version_id:
            exc = ProjectMasterConflictError("当前主数据版本已变化，请重新加载后应用模板。")
            exc.code = "CURRENT_VERSION_CHANGED"
            raise exc
        original = self.repository.load_snapshot(version_id)
        snapshot = original.model_copy(deep=True)
        sections = {
            section.structure_id: section
            for workpoint in snapshot.workpoints if workpoint.workpoint_type == "pavement"
            for section in workpoint.structures if section.structure_type == "pavement_section"
        }
        unknown = set(request.section_ids) - sections.keys()
        if unknown:
            raise ProjectMasterImportBlockedError("施工段不属于当前路面版本：" + "、".join(sorted(unknown)))
        for section_id in request.section_ids:
            section = sections[section_id]
            if section.components:
                exc = ProjectMasterConflictError(f"{section.structure_name} 已有结构层，请勿重复应用模板。")
                exc.code = "PAVEMENT_LAYERS_EXIST"
                raise exc
            values = {p.parameter_code: p.value for p in section.parameters}
            length = values.get("construction_length_m")
            if (isinstance(length, bool) or not isinstance(length, (int, float))
                    or not math.isfinite(length) or length <= 0
                    or values.get("quantity_basis_confirmed") is not True):
                raise ProjectMasterImportBlockedError(f"{section.structure_name} 缺少已确认的有效施工长度。")
            section.components = [ProjectMasterComponent(
                component_id=f"{section_id}-L{index:02d}", structure_id=section_id,
                component_name=layer.name, component_type=layer.process_type,
                quantity=length, unit="m", sort_order=index,
                parameters=[
                    ParameterValue(parameter_code="thickness_m", value_type="number", value=layer.thickness_m, unit="m"),
                    ParameterValue(parameter_code="quantity_basis", value_type="text", value="entered"),
                ],
                source=SourceEvidence(sheet_name="单段结构层模板", row_no=index),
            ) for index, layer in enumerate(request.layers, 1)]
        issues = validate_snapshot(snapshot)
        if any(issue.severity == "error" for issue in issues):
            raise ProjectMasterImportBlockedError("；".join(issue.message for issue in issues if issue.severity == "error"))
        fingerprint = content_fingerprint(snapshot)
        duplicate = self.repository.find_version_by_fingerprint(base.project_id, fingerprint)
        if duplicate:
            return self.repository.get_import_batch(duplicate.source_batch_id)
        batch = self.repository.create_import_batch(
            project_id=base.project_id, file_name="单段结构层模板", file_sha256=fingerprint,
            expected_current_version_id=version_id, created_by=request.created_by,
        )
        try:
            draft = self.repository.create_draft_version(
                batch_id=batch.batch_id, project_id=base.project_id, content_fingerprint=fingerprint,
                snapshot=snapshot, issues=issues, diff_entries=diff_snapshots(original, snapshot),
                created_by=request.created_by, base_version_id=version_id,
            )
            return self.repository.get_import_batch(draft.source_batch_id)
        except Exception as exc:
            self.repository.fail_batch(batch.batch_id, str(exc))
            raise

    def _current_pavement_snapshot(self, version_id: str):
        base = self.repository.get_version_summary(version_id)
        current = self.repository.get_current_version(base.project_id)
        if current is None or current.version_id != version_id:
            exc = ProjectMasterConflictError("主数据已更新，请重新加载当前版本后再编辑。")
            exc.code = "CURRENT_VERSION_CHANGED"
            raise exc
        original = self.repository.load_snapshot(version_id)
        return base, original, original.model_copy(deep=True)

    @staticmethod
    def _new_pavement_layer(section, name: str, process_type: str, component_id: str, order: int):
        values = {p.parameter_code: p.value for p in section.parameters}
        length = values.get("construction_length_m")
        if (isinstance(length, bool) or not isinstance(length, (int, float))
                or not math.isfinite(length) or length <= 0 or values.get("quantity_basis_confirmed") is not True):
            raise ProjectMasterImportBlockedError(f"{section.structure_name} 缺少已确认的有效施工长度。")
        return ProjectMasterComponent(
            component_id=component_id, structure_id=section.structure_id, component_name=name,
            component_type=process_type, quantity=length, unit="m", sort_order=order,
            parameters=[ParameterValue(parameter_code="quantity_basis", value_type="text", value="entered")],
            source=SourceEvidence(sheet_name="施工段结构层编辑", row_no=order),
        )

    def initialize_pavement_layers(self, version_id: str, created_by: str) -> ProjectMasterVersionDetail:
        base, original, snapshot = self._current_pavement_snapshot(version_id)
        defaults = [
            ("碎石垫层", "granular_base"), ("水稳底基层", "cement_stabilized_base"),
            ("水稳下基层", "cement_stabilized_base"), ("水稳上基层", "cement_stabilized_base"),
            ("沥青面层", "asphalt_course"),
        ]
        for workpoint in snapshot.workpoints:
            if workpoint.workpoint_type != "pavement":
                continue
            for section in workpoint.structures:
                if section.structure_type != "pavement_section" or section.components:
                    continue
                section.components = [self._new_pavement_layer(
                    section, name, process, f"{section.structure_id}-L{index:02d}", index,
                ) for index, (name, process) in enumerate(defaults, 1)]
        return self._save_pavement_snapshot(base, original, snapshot, created_by, "施工段默认结构层")

    def save_pavement_section_layers(
        self, version_id: str, section_id: str, request: SavePavementSectionLayersRequest,
    ) -> ProjectMasterVersionDetail:
        base, original, snapshot = self._current_pavement_snapshot(version_id)
        section = next((s for w in snapshot.workpoints if w.workpoint_type == "pavement"
                        for s in w.structures if s.structure_id == section_id and s.structure_type == "pavement_section"), None)
        if section is None:
            raise ProjectMasterNotFoundError("当前版本不存在该路面施工段。")
        existing = {c.component_id: c for c in section.components}
        updated = []
        for order, layer in enumerate(request.layers, 1):
            if layer.component_id is not None:
                if layer.component_id not in existing:
                    raise ProjectMasterImportBlockedError("结构层不属于当前施工段，请重新加载后编辑。")
                component = existing[layer.component_id]
            else:
                component = self._new_pavement_layer(section, layer.name, layer.process_type, f"{section_id}-L{uuid4().hex[:12]}", order)
            component.component_name = layer.name
            component.component_type = layer.process_type
            component.sort_order = order
            component.enabled = layer.enabled
            thickness = next((p for p in component.parameters if p.parameter_code == "thickness_m"), None)
            if layer.thickness_m is None:
                component.parameters = [p for p in component.parameters if p.parameter_code != "thickness_m"]
            elif thickness is None or thickness.value != layer.thickness_m:
                component.parameters = [p for p in component.parameters if p.parameter_code != "thickness_m"]
                component.parameters.append(ParameterValue(
                    parameter_code="thickness_m", value_type="number", value=layer.thickness_m, unit="m",
                    source=SourceEvidence(sheet_name="施工段结构层编辑", row_no=order, column_name="实际层厚"),
                ))
            if "density_t_m3" in layer.model_fields_set:
                density = next((p for p in component.parameters if p.parameter_code == "density_t_m3"), None)
                if layer.density_t_m3 is None:
                    component.parameters = [p for p in component.parameters if p.parameter_code != "density_t_m3"]
                elif density is None or density.value != layer.density_t_m3:
                    component.parameters = [p for p in component.parameters if p.parameter_code != "density_t_m3"]
                    component.parameters.append(ParameterValue(
                        parameter_code="density_t_m3", value_type="number", value=layer.density_t_m3, unit="t/m3",
                        source=SourceEvidence(sheet_name="施工段结构层编辑", row_no=order, column_name="密度"),
                    ))
            updated.append(component)
        section.components = updated
        return self._save_pavement_snapshot(base, original, snapshot, request.created_by, f"编辑结构层：{section.structure_name}")

    def save_pavement_handover(self, version_id: str, section_id: str, request: SavePavementHandoverRequest):
        base, original, snapshot = self._current_pavement_snapshot(version_id)
        section = next((s for w in snapshot.workpoints if w.workpoint_type == "pavement"
                        for s in w.structures if s.structure_id == section_id and s.structure_type == "pavement_section"), None)
        if section is None:
            raise ProjectMasterNotFoundError("当前版本不存在该路面施工段。")
        values = {"roadbed_handover_status": request.status,
                  "roadbed_available_date": request.available_date.isoformat() if request.available_date else None,
                  "roadbed_handover_note": request.note.strip()}
        for code, value in values.items():
            old = next((p for p in section.parameters if p.parameter_code == code), None)
            if old and old.value == value: continue
            section.parameters = [p for p in section.parameters if p.parameter_code != code]
            if value is not None:
                section.parameters.append(ParameterValue(parameter_code=code, value_type="date" if code.endswith("_date") else "text", value=value))
        return self._save_pavement_snapshot(base, original, snapshot, request.created_by, f"路床移交：{section.structure_name}")

    def _save_pavement_snapshot(self, base, original, snapshot, created_by: str, label: str) -> ProjectMasterVersionDetail:
        content = content_fingerprint(snapshot)
        if content == content_fingerprint(original):
            return self.repository.get_version_detail(base.version_id)
        issues = validate_snapshot(snapshot)
        if any(issue.severity == "error" for issue in issues):
            raise ProjectMasterImportBlockedError("；".join(i.message for i in issues if i.severity == "error"))
        # Scope edit identity to its baseline so reverting an earlier value remains a new version.
        fingerprint = hashlib.sha256(f"pavement-edit/v1\n{base.version_id}\n{content}".encode()).hexdigest()
        duplicate = self.repository.find_version_by_fingerprint(base.project_id, fingerprint)
        if duplicate:
            draft = self.repository.get_version_detail(duplicate.version_id)
        else:
            batch = self.repository.create_import_batch(
                project_id=base.project_id, file_name=label, file_sha256=content,
                expected_current_version_id=base.version_id, created_by=created_by,
            )
            try:
                version = self.repository.create_draft_version(
                    batch_id=batch.batch_id, project_id=base.project_id, content_fingerprint=fingerprint,
                    snapshot=snapshot, issues=issues, diff_entries=diff_snapshots(original, snapshot),
                    created_by=created_by, base_version_id=base.version_id,
                )
                draft = self.repository.get_version_detail(version.version_id)
            except Exception as exc:
                self.repository.fail_batch(batch.batch_id, str(exc))
                raise
        # Saving incomplete master data is allowed; scheduling still checks completeness.
        return self.confirm_version(draft.version_id, ConfirmProjectMasterVersionRequest(
            confirmed_by=created_by, expected_current_version_id=base.version_id,
            acknowledge_warning_codes=draft.warning_codes,
        ))

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

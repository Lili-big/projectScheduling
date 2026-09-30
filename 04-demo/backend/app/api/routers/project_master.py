from __future__ import annotations

from urllib.parse import quote
from ...contracts.pavement import EngineeringDomain

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse, Response

from ..errors import project_master_http_error
from ..multipart import parse_multipart_request
from ...contracts.project_master import (
    CancelProjectMasterImportRequest,
    ConfirmProjectMasterVersionRequest,
    CreatePavementLayerDraftRequest,
    InitializePavementLayersRequest,
    SavePavementSectionLayersRequest,
    SavePavementHandoverRequest,
    ProjectMasterImportBatch,
    ProjectMasterVersionDetail,
    ProjectMasterVersionPage,
    ProjectMasterVersionSummary,
    ProjectMasterWorkpoint,
    ProjectMasterWorkpointPage,
    TaskViewDisplayMapRequest,
    TaskViewDisplayMapResponse,
    PavementProgressView,
    SavePavementProgressRequest,
)
from ...project_master.repository import ProjectMasterRepositoryError
from ...project_master.service import ProjectMasterService, ProjectMasterServiceError, default_project_master_service
from ...contracts import GirderWorkPoint
from ...girder_planning.ownership import derive_route_workpoints


router = APIRouter(tags=["project-master"])
XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _service(request: Request) -> ProjectMasterService:
    return getattr(request.app.state, "project_master_service", None) or default_project_master_service()


@router.get("/api/projects/{project_id}/pavement-progress", response_model=PavementProgressView)
def get_pavement_progress_endpoint(project_id: str, request: Request) -> PavementProgressView:
    try:
        return _service(request).get_pavement_progress(project_id)
    except (ProjectMasterRepositoryError, ProjectMasterServiceError) as exc:
        raise project_master_http_error(exc) from exc


@router.put("/api/projects/{project_id}/pavement-progress", response_model=PavementProgressView)
def save_pavement_progress_endpoint(project_id: str, payload: SavePavementProgressRequest, request: Request) -> PavementProgressView:
    try:
        return _service(request).save_pavement_progress(project_id, payload)
    except (ProjectMasterRepositoryError, ProjectMasterServiceError) as exc:
        raise project_master_http_error(exc) from exc


@router.get("/api/project-master/template")
def download_project_master_template_endpoint(request: Request, engineering_domain: EngineeringDomain = "bridge") -> Response:
    try:
        content = _service(request).template_bytes() if engineering_domain == "bridge" else _service(request).template_bytes(engineering_domain)
    except (ProjectMasterRepositoryError, ProjectMasterServiceError) as exc:
        raise project_master_http_error(exc) from exc
    return _xlsx_response(content, "项目主数据导入模板.xlsx")


@router.post("/api/projects/{project_id}/project-master/imports")
async def import_project_master_endpoint(project_id: str, request: Request) -> JSONResponse:
    try:
        fields, files = await parse_multipart_request(request)
        upload = files.get("file")
        if upload is None:
            exc = ProjectMasterServiceError("必须上传项目主数据 Excel 文件。")
            exc.status_code = 422
            exc.code = "IMPORT_FILE_REQUIRED"
            raise exc
        created_by = fields.get("created_by", "").strip()
        if not created_by:
            exc = ProjectMasterServiceError("必须提供 created_by。")
            exc.status_code = 422
            exc.code = "CREATED_BY_REQUIRED"
            raise exc
        batch = _service(request).import_workbook(
            project_id=project_id,
            file_name=str(upload["filename"]),
            content=bytes(upload["content"]),
            created_by=created_by,
            expected_current_version_id=fields.get("expected_current_version_id") or None,
        )
        status_code = 201 if batch.status == "ready" else 202
        return JSONResponse(status_code=status_code, content=batch.model_dump(mode="json"))
    except (ProjectMasterRepositoryError, ProjectMasterServiceError) as exc:
        raise project_master_http_error(exc) from exc


@router.get("/api/project-master/imports/{batch_id}", response_model=ProjectMasterImportBatch)
def get_project_master_import_endpoint(batch_id: str, request: Request) -> ProjectMasterImportBatch:
    try:
        return _service(request).repository.get_import_batch(batch_id)
    except (ProjectMasterRepositoryError, ProjectMasterServiceError) as exc:
        raise project_master_http_error(exc) from exc


@router.post("/api/project-master/imports/{batch_id}", response_model=ProjectMasterImportBatch)
def cancel_project_master_import_endpoint(
    batch_id: str,
    payload: CancelProjectMasterImportRequest,
    request: Request,
) -> ProjectMasterImportBatch:
    try:
        return _service(request).cancel_import(batch_id, payload)
    except (ProjectMasterRepositoryError, ProjectMasterServiceError) as exc:
        raise project_master_http_error(exc) from exc


@router.get("/api/projects/{project_id}/project-master/versions", response_model=ProjectMasterVersionPage)
def list_project_master_versions_endpoint(
    project_id: str,
    request: Request,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
) -> ProjectMasterVersionPage:
    try:
        items, total = _service(request).repository.list_versions(project_id, page=page, page_size=page_size)
        return ProjectMasterVersionPage(page=page, page_size=page_size, total=total, items=items)
    except (ProjectMasterRepositoryError, ProjectMasterServiceError) as exc:
        raise project_master_http_error(exc) from exc


@router.get(
    "/api/projects/{project_id}/project-master/versions/current",
    response_model=ProjectMasterVersionSummary,
)
def get_current_project_master_version_endpoint(project_id: str, request: Request) -> ProjectMasterVersionSummary:
    try:
        version = _service(request).repository.get_current_version(project_id)
        if version is None:
            from ...project_master.repository import ProjectMasterNotFoundError

            raise ProjectMasterNotFoundError(f"项目 {project_id} 尚无已确认的项目主数据版本。")
        return version
    except (ProjectMasterRepositoryError, ProjectMasterServiceError) as exc:
        raise project_master_http_error(exc) from exc


@router.get("/api/project-master/versions/{version_id}", response_model=ProjectMasterVersionDetail)
def get_project_master_version_endpoint(version_id: str, request: Request) -> ProjectMasterVersionDetail:
    try:
        return _service(request).repository.get_version_detail(version_id)
    except (ProjectMasterRepositoryError, ProjectMasterServiceError) as exc:
        raise project_master_http_error(exc) from exc


@router.post("/api/project-master/versions/{version_id}/confirm", response_model=ProjectMasterVersionDetail)
def confirm_project_master_version_endpoint(
    version_id: str,
    payload: ConfirmProjectMasterVersionRequest,
    request: Request,
) -> ProjectMasterVersionDetail:
    try:
        return _service(request).confirm_version(version_id, payload)
    except (ProjectMasterRepositoryError, ProjectMasterServiceError) as exc:
        raise project_master_http_error(exc) from exc


@router.post("/api/project-master/versions/{version_id}/pavement-layer-drafts", response_model=ProjectMasterImportBatch)
def create_pavement_layer_draft_endpoint(
    version_id: str, payload: CreatePavementLayerDraftRequest, request: Request,
) -> ProjectMasterImportBatch:
    try:
        return _service(request).create_pavement_layer_draft(version_id, payload)
    except (ProjectMasterRepositoryError, ProjectMasterServiceError) as exc:
        raise project_master_http_error(exc) from exc


@router.post("/api/project-master/versions/{version_id}/pavement-layers/initialize", response_model=ProjectMasterVersionDetail)
def initialize_pavement_layers_endpoint(version_id: str, payload: InitializePavementLayersRequest, request: Request):
    try:
        return _service(request).initialize_pavement_layers(version_id, payload.created_by)
    except (ProjectMasterRepositoryError, ProjectMasterServiceError) as exc:
        raise project_master_http_error(exc) from exc


@router.put("/api/project-master/versions/{version_id}/pavement-sections/{section_id}/handover", response_model=ProjectMasterVersionDetail)
def save_pavement_handover_endpoint(version_id: str, section_id: str, payload: SavePavementHandoverRequest, request: Request):
    try:
        return _service(request).save_pavement_handover(version_id, section_id, payload)
    except (ProjectMasterRepositoryError, ProjectMasterServiceError) as exc:
        raise project_master_http_error(exc) from exc


@router.put("/api/project-master/versions/{version_id}/pavement-sections/{section_id}/layers", response_model=ProjectMasterVersionDetail)
def save_pavement_section_layers_endpoint(version_id: str, section_id: str, payload: SavePavementSectionLayersRequest, request: Request):
    try:
        return _service(request).save_pavement_section_layers(version_id, section_id, payload)
    except (ProjectMasterRepositoryError, ProjectMasterServiceError) as exc:
        raise project_master_http_error(exc) from exc


@router.get(
    "/api/project-master/versions/{version_id}/workpoints",
    response_model=ProjectMasterWorkpointPage,
)
def list_project_master_workpoints_endpoint(
    version_id: str,
    request: Request,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    workpoint_type: str | None = None,
    keyword: str | None = None,
) -> ProjectMasterWorkpointPage:
    try:
        return _service(request).repository.list_workpoints(
            version_id,
            page=page,
            page_size=page_size,
            workpoint_type=workpoint_type,
            keyword=keyword,
        )
    except (ProjectMasterRepositoryError, ProjectMasterServiceError) as exc:
        raise project_master_http_error(exc) from exc


@router.get(
    "/api/project-master/versions/{version_id}/workpoints/{workpoint_id}",
    response_model=ProjectMasterWorkpoint,
)
def get_project_master_workpoint_endpoint(
    version_id: str,
    workpoint_id: str,
    request: Request,
) -> ProjectMasterWorkpoint:
    try:
        return _service(request).repository.get_workpoint(version_id, workpoint_id)
    except (ProjectMasterRepositoryError, ProjectMasterServiceError) as exc:
        raise project_master_http_error(exc) from exc


@router.post(
    "/api/project-master/versions/{version_id}/task-view-display-map",
    response_model=TaskViewDisplayMapResponse,
)
def get_task_view_display_map_endpoint(
    version_id: str,
    payload: TaskViewDisplayMapRequest,
    request: Request,
) -> TaskViewDisplayMapResponse:
    try:
        return _service(request).repository.get_task_view_display_map(version_id, payload.workpoint_ids)
    except (ProjectMasterRepositoryError, ProjectMasterServiceError) as exc:
        raise project_master_http_error(exc) from exc


@router.get("/api/project-master/versions/{version_id}/export")
def export_project_master_version_endpoint(version_id: str, request: Request) -> Response:
    try:
        summary = _service(request).repository.get_version_summary(version_id)
        content = _service(request).export_version(version_id)
    except (ProjectMasterRepositoryError, ProjectMasterServiceError) as exc:
        raise project_master_http_error(exc) from exc
    return _xlsx_response(content, f"项目主数据-v{summary.version_no}.xlsx")


@router.get(
    "/api/project-master/versions/{version_id}/girder-workpoints",
    response_model=list[GirderWorkPoint],
)
def list_project_master_girder_workpoints_endpoint(version_id: str, request: Request) -> list[GirderWorkPoint]:
    try:
        summary = _service(request).repository.get_version_summary(version_id)
        if summary.status != "confirmed":
            from ...project_master.repository import ProjectMasterConflictError

            exc = ProjectMasterConflictError("架梁路线只能选择已确认主数据版本派生的工点。")
            exc.code = "PROJECT_MASTER_VERSION_NOT_CONFIRMED"
            raise exc
        return derive_route_workpoints(_service(request).repository.load_snapshot(version_id))
    except (ProjectMasterRepositoryError, ProjectMasterServiceError) as exc:
        raise project_master_http_error(exc) from exc


def _xlsx_response(content: bytes, file_name: str) -> Response:
    return Response(
        content=content,
        media_type=XLSX_MIME,
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(file_name)}"},
    )


__all__ = [name for name in globals() if name == "router" or name.endswith("_endpoint")]

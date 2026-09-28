from __future__ import annotations

from fastapi import HTTPException, Request


def reject_pavement(scenario, *, strategy=False):
    if getattr(scenario, "engineering_domain", "bridge") == "pavement":
        raise HTTPException(status_code=422, detail={
            "code": "PAVEMENT_STRATEGY_NOT_SUPPORTED" if strategy else "PAVEMENT_FEATURE_NOT_SUPPORTED",
            "message": "路面首版支持固定机组排程，此功能暂不适用。",
        })


async def reject_pavement_feature_request(request: Request):
    """Guard bridge-only routes before invoking assistants or bridge planning."""
    import json
    if request.method in {"GET", "HEAD"}: return
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        try: payload = await request.json()
        except (ValueError, UnicodeDecodeError): return
    elif "multipart/form-data" in content_type:
        from .multipart import parse_multipart_request
        fields, _ = await parse_multipart_request(request)
        try: payload = json.loads(fields.get("scenario", "{}"))
        except ValueError: return
    else: return

    def contains_pavement(value):
        if isinstance(value, dict):
            return value.get("engineering_domain") == "pavement" or value.get("schedule_support") == "pavement_supported" or value.get("workpoint_type") == "pavement" or any(contains_pavement(v) for v in value.values())
        return isinstance(value, list) and any(contains_pavement(v) for v in value)
    if contains_pavement(payload):
        raise HTTPException(status_code=422, detail={"code":"PAVEMENT_FEATURE_NOT_SUPPORTED","message":"此桥梁专项功能暂不适用于路面。"})
    version_id = payload.get("project_data_version_id") if isinstance(payload, dict) else None
    if version_id:
        from ..project_master.service import default_project_master_service
        from ..project_master.repository import ProjectMasterRepositoryError
        service = getattr(request.app.state, "project_master_service", None) or default_project_master_service()
        try:
            snapshot = service.repository.load_snapshot(version_id)
        except ProjectMasterRepositoryError:
            return  # Existing route owns legacy-version/not-found semantics.
        if any(w.schedule_support == "pavement_supported" for w in snapshot.workpoints):
            raise HTTPException(status_code=422, detail={"code":"PAVEMENT_FEATURE_NOT_SUPPORTED","message":"关联主数据包含路面，不适用桥梁专项。"})


def http_error(exc: Exception, *, default_status: int = 503) -> HTTPException:
    """Map domain/service exceptions without changing the existing detail text."""

    return HTTPException(status_code=int(getattr(exc, "status_code", default_status)), detail=str(exc))


def plan_control_http_error(exc: Exception) -> HTTPException:
    return http_error(exc, default_status=503)


def project_master_http_error(exc: Exception) -> HTTPException:
    """Expose stable project-master error codes to API clients."""

    status_code = int(getattr(exc, "status_code", 503))
    code = str(getattr(exc, "code", "PROJECT_MASTER_STORAGE_ERROR"))
    return HTTPException(
        status_code=status_code,
        detail={"code": code, "message": str(exc)},
    )

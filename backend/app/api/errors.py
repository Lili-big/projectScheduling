from __future__ import annotations

from fastapi import HTTPException


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
